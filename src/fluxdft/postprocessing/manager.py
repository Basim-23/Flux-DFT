"""
Post-Processing Manager for FluxDFT.

Orchestrates automatic plot generation after job completion.
"""

from typing import List, Dict, Optional, Callable, Any
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

from .recipes import (
    PlotRecipe,
    PlotMetadata,
    PlotStyle,
    BandStructureRecipe,
    DOSRecipe,
    PDOSRecipe,
    CompositeBandsDOSRecipe,
    ConvergenceRecipe,
)


@dataclass
class PostProcessingResult:
    """Result of post-processing a completed job."""
    job_id: str
    job_type: str
    plots: List[PlotMetadata] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def success(self) -> bool:
        return len(self.plots) > 0 and len(self.errors) == 0


class PostProcessingManager:
    """
    Orchestrates automatic post-processing after job completion.
    
    Responsibilities:
    1. Detect job completion and type
    2. Parse output data
    3. Determine applicable plot recipes
    4. Execute recipes and collect results
    5. Notify UI of generated plots
    
    Usage:
        manager = PostProcessingManager(output_parser, settings)
        manager.on_plots_ready = lambda plots: update_ui(plots)
        
        # When job completes:
        result = manager.process_completed_job(job)
    """
    
    # Default recipe ordering (composite last as it needs multiple data sources)
    DEFAULT_RECIPES: List[PlotRecipe] = [
        ConvergenceRecipe(),
        BandStructureRecipe(),
        DOSRecipe(),
        PDOSRecipe(),
        CompositeBandsDOSRecipe(),
    ]
    
    def __init__(
        self,
        output_parser=None,
        settings: Optional[Dict] = None,
    ):
        """
        Initialize the post-processing manager.
        
        Args:
            output_parser: OutputParser instance for parsing QE output
            settings: Dict with auto_graphing settings
        """
        self.parser = output_parser
        self.settings = settings or {}
        self.recipes = list(self.DEFAULT_RECIPES)
        self.style = PlotStyle()
        
        # Initialize MP Client
        from fluxdft.materials_project.client import MaterialsProjectClient
        from fluxdft.utils.config import Config
        
        try:
            config = Config()
            api_key = config.get("mp_api_key")
            if api_key:
                self.mp_client = MaterialsProjectClient(api_key)
            else:
                self.mp_client = None
        except Exception as e:
            print(f"Failed to initialize MP Client: {e}")
            self.mp_client = None
        
        # Callbacks
        self.on_plots_ready: Optional[Callable[[List[PlotMetadata]], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    @property
    def auto_generate_enabled(self) -> bool:
        """Check if auto-generation is enabled."""
        return self.settings.get("auto_generate_plots", True)
    
    def process_completed_job(self, job) -> PostProcessingResult:
        """
        Process a completed job and generate appropriate plots.
        
        Args:
            job: Job object with work_dir, output_file, calculation_type, etc.
            
        Returns:
            PostProcessingResult with generated plot metadata
        """
        result = PostProcessingResult(
            job_id=getattr(job, 'id', 'unknown'),
            job_type=self._detect_job_type(job),
        )
        
        if not self.auto_generate_enabled:
            return result
        
        try:
            # 1. Parse output data
            parsed_data = self._parse_job_output(job)
            
            # 1b. Fetch MP Reference Data (if enabled)
            if self.mp_client and self.settings.get("mp_enabled", True):
                try:
                    mp_data = self._fetch_mp_data(job, parsed_data)
                    parsed_data.update(mp_data)
                except Exception as e:
                    print(f"Failed to fetch MP reference data: {e}")
            
            
            # 2. Create output directory
            output_dir = self._get_output_dir(job)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 3. Find applicable recipes and execute
            for recipe in self.recipes:
                try:
                    if recipe.is_applicable(result.job_type, parsed_data):
                        metadata = recipe.generate(
                            parsed_data,
                            output_dir,
                            self.style,
                        )
                        if metadata:
                            result.plots.append(metadata)
                except Exception as e:
                    error_msg = f"Recipe {recipe.recipe_id} failed: {e}"
                    result.errors.append(error_msg)
                    if self.on_error:
                        self.on_error(error_msg)
            
            # 4. Notify UI
            if result.plots and self.on_plots_ready:
                self.on_plots_ready(result.plots)
                
        except Exception as e:
            result.errors.append(f"Post-processing failed: {e}")
            if self.on_error:
                self.on_error(str(e))
        
        return result
    
    def _fetch_mp_data(self, job, parsed_data) -> Dict[str, Any]:
        """Fetch reference data from Materials Project."""
        mp_data = {}
        
        # Try to find formula from parsed data (if available) or filename
        formula = parsed_data.get("formula")
        
        # Fallback: try to guess from prefix or input/output
        if not formula:
            prefix = getattr(job, 'prefix', '')
            if prefix and prefix != 'pwscf':
                # Heuristic: sometimes prefix IS the formula (e.g. "Si")
                formula = prefix
        
        if not formula:
            return {}
            
        print(f"Post-processing: Fetching MP data for '{formula}'...")
        
        # Find best match
        try:
            material = self.mp_client.find_best_match(formula)
            if not material:
                print(f"  No match found for {formula}")
                return {}
                
            mp_data["mp_material"] = material
            print(f"  Matched: {material.mp_id} ({material.formula_pretty})")
            
            job_type = self._detect_job_type(job)
            
            # Fetch Bands
            if job_type in ["bands", "nscf"]:
                print("  Fetching reference bands...")
                bands = self.mp_client.get_band_structure(material.mp_id)
                if bands:
                    mp_data["mp_bands"] = bands
                    print("  Bands fetched successfully.")
                    
            # Fetch DOS
            if job_type in ["dos", "nscf"]:
                print("  Fetching reference DOS...")
                dos = self.mp_client.get_dos(material.mp_id)
                if dos:
                    mp_data["mp_dos"] = dos
                    print("  DOS fetched successfully.")
                    
        except Exception as e:
            print(f"  Error fetching MP data: {e}")
            
        return mp_data

    def _detect_job_type(self, job) -> str:
        """Detect calculation type from job."""
        calc_type = getattr(job, 'calculation_type', '')
        
        if 'bands' in calc_type.lower():
            return 'bands'
        if 'dos' in calc_type.lower():
            return 'dos'
        if 'projwfc' in calc_type.lower() or 'pdos' in calc_type.lower():
            return 'pdos'
        if 'nscf' in calc_type.lower():
            return 'nscf'
        if 'relax' in calc_type.lower() or 'vc-relax' in calc_type.lower():
            return 'relax'
        
        return 'scf'
    
    def _get_output_dir(self, job) -> Path:
        """Get output directory for plots."""
        work_dir = getattr(job, 'work_dir', Path('.'))
        if isinstance(work_dir, str):
            work_dir = Path(work_dir)
        return work_dir / 'plots'
    
    def _parse_job_output(self, job) -> Dict[str, Any]:
        """
        Parse all available output data from job.
        
        Returns dict with keys like:
        - fermi_energy
        - total_energy
        - eigenvalues
        - kpath
        - kpoint_labels
        - dos_energy
        - dos_total
        - scf_energies
        - forces_history
        """
        data = {}
        
        work_dir = getattr(job, 'work_dir', None)
        if isinstance(work_dir, str):
            work_dir = Path(work_dir)
        
        prefix = getattr(job, 'prefix', 'pwscf')
        
        # Parse main output file
        output_file = getattr(job, 'output_file', None)
        if output_file and self.parser:
            try:
                pw_output = self.parser.parse_pw_output(output_file)
                data['fermi_energy'] = pw_output.fermi_energy
                data['total_energy'] = pw_output.total_energy
                data['scf_energies'] = getattr(pw_output, 'scf_energies', [])
                data['forces_history'] = getattr(pw_output, 'forces_history', [])
            except Exception:
                pass
        
        if work_dir:
            # Parse bands
            bands_file = work_dir / f"{prefix}.bands.gnu"
            if bands_file.exists() and self.parser:
                try:
                    band_data = self.parser.parse_bands(bands_file)
                    data['eigenvalues'] = band_data.eigenvalues
                    data['kpath'] = band_data.kpoints
                    data['kpoint_labels'] = getattr(band_data, 'labels', [])
                except Exception:
                    pass
            
            # Parse DOS
            dos_file = work_dir / f"{prefix}.dos"
            if dos_file.exists() and self.parser:
                try:
                    dos_data = self.parser.parse_dos(dos_file)
                    data['dos_energy'] = dos_data.energy
                    data['dos_total'] = dos_data.dos
                except Exception:
                    pass
        
        return data
    
    def add_recipe(self, recipe: PlotRecipe):
        """Add a custom recipe."""
        self.recipes.append(recipe)
    
    def remove_recipe(self, recipe_id: str):
        """Remove a recipe by ID."""
        self.recipes = [r for r in self.recipes if r.recipe_id != recipe_id]
    
    def set_style(self, style: PlotStyle):
        """Set the plot style."""
        self.style = style
