"""
Materials Project Client for FluxDFT.

Fetches reference data from Materials Project for comparison with calculations.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)

# Will be evaluated lazily to prevent UI freezing on tab open
HAS_MP_API = None
HAS_PYMATGEN = None


@dataclass
class MPMaterial:
    """Material data from Materials Project."""
    material_id: str
    formula: str
    formula_pretty: str
    
    # Structure
    spacegroup: str
    crystal_system: str
    volume: float  # Å³
    density: float  # g/cm³
    
    # Electronic
    band_gap: float  # eV
    is_metal: bool
    is_magnetic: bool
    
    # Energetics
    formation_energy: float  # eV/atom
    energy_above_hull: float  # eV/atom
    
    # Stability
    is_stable: bool
    
    # Raw data
    raw_data: Dict[str, Any] = None


class MaterialsProjectClient:
    """
    Client for fetching data from Materials Project.
    
    Usage:
        client = MaterialsProjectClient(api_key="your_key")
        results = client.search_by_formula("Fe2O3")
        
        for mat in results:
            print(f"{mat.formula_pretty}: Band gap = {mat.band_gap} eV")
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the client.
        
        Args:
            api_key: Materials Project API key. 
                    If None, tries to use MP_API_KEY environment variable.
        """
        self.api_key = api_key
        self._rester = None
    
    def _check_mp_api(self):
        global HAS_MP_API
        if HAS_MP_API is None:
            try:
                import mp_api.client
                HAS_MP_API = True
            except ImportError:
                HAS_MP_API = False
                logger.warning("mp-api not installed. Install with: pip install mp-api")
        return HAS_MP_API

    @property
    def is_available(self) -> bool:
        """Check if MP API is available."""
        return self._check_mp_api() and self.api_key is not None
    
    def _get_rester(self):
        """Get or create MPRester instance."""
        if not self._check_mp_api():
            return None
        
        if self._rester is None and self.api_key:
            try:
                from mp_api.client import MPRester
                self._rester = MPRester(self.api_key)
            except Exception as e:
                logger.error(f"Failed to create MPRester: {e}")
        
        return self._rester

    def get_cif(self, material_id: str) -> Optional[str]:
        """Fetch the material structure as a CIF string."""
        if not self.is_available:
            return self._get_mock_cif(material_id)
        try:
            rester = self._get_rester()
            if not rester: return None
            
            docs = rester.summary.search(material_ids=[material_id], fields=["structure"])
            if docs and docs[0].structure:
                from pymatgen.io.cif import CifWriter
                from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                
                # Make sure we export the visual conventional cell, not the primitive
                analyzer = SpacegroupAnalyzer(docs[0].structure)
                conventional = analyzer.get_conventional_standard_structure()
                
                writer = CifWriter(conventional)
                return str(writer)
            return None
        except Exception as e:
            logger.error(f"Failed to get CIF for {material_id}: {e}")
            return None
    
    def search_by_formula(self, formula: str, max_results: int = 10) -> List[MPMaterial]:
        """
        Search for materials by formula.
        
        Args:
            formula: Chemical formula (e.g., "Fe2O3", "Si", "GaAs")
            max_results: Maximum number of results to return
        
        Returns:
            List of MPMaterial objects
        """
        if not self.is_available:
            # Return mock data for demo purposes
            return self._get_mock_data(formula)
        
        try:
            rester = self._get_rester()
            if not rester:
                return []
            
            docs = rester.summary.search(
                formula=formula,
                fields=[
                    "material_id", "formula_pretty", "composition",
                    "symmetry", "volume", "density",
                    "band_gap", "is_metal", "is_magnetic",
                    "formation_energy_per_atom", "energy_above_hull",
                    "is_stable"
                ],
                num_chunks=1,
                chunk_size=max_results
            )
            
            results = []
            for doc in docs:
                mat = MPMaterial(
                    material_id=doc.material_id,
                    formula=str(doc.composition),
                    formula_pretty=doc.formula_pretty,
                    spacegroup=doc.symmetry.symbol if doc.symmetry else "Unknown",
                    crystal_system=doc.symmetry.crystal_system if doc.symmetry else "Unknown",
                    volume=doc.volume or 0,
                    density=doc.density or 0,
                    band_gap=doc.band_gap or 0,
                    is_metal=doc.is_metal or False,
                    is_magnetic=doc.is_magnetic or False,
                    formation_energy=doc.formation_energy_per_atom or 0,
                    energy_above_hull=doc.energy_above_hull or 0,
                    is_stable=doc.is_stable or False,
                    raw_data=doc.dict()
                )
                results.append(mat)
            
            return results
            
        except Exception as e:
            logger.error(f"MP search failed: {e}")
            return []
    
    def get_by_id(self, material_id: str) -> Optional[MPMaterial]:
        """
        Get material by Materials Project ID.
        
        Args:
            material_id: MP ID (e.g., "mp-149" for Si)
        
        Returns:
            MPMaterial or None
        """
        results = self.search_by_id(material_id)
        return results[0] if results else None
    
    def search_by_id(self, material_id: str) -> List[MPMaterial]:
        """Search by MP ID."""
        if not self.is_available:
            return []
        
        try:
            rester = self._get_rester()
            if not rester:
                return []
            
            doc = rester.summary.get_data_by_id(material_id)
            if not doc:
                return []
            
            mat = MPMaterial(
                material_id=doc.material_id,
                formula=str(doc.composition) if doc.composition else "",
                formula_pretty=doc.formula_pretty or "",
                spacegroup=doc.symmetry.symbol if doc.symmetry else "Unknown",
                crystal_system=doc.symmetry.crystal_system if doc.symmetry else "Unknown",
                volume=doc.volume or 0,
                density=doc.density or 0,
                band_gap=doc.band_gap or 0,
                is_metal=doc.is_metal or False,
                is_magnetic=doc.is_magnetic or False,
                formation_energy=doc.formation_energy_per_atom or 0,
                energy_above_hull=doc.energy_above_hull or 0,
                is_stable=doc.is_stable or False,
                raw_data=doc.dict()
            )
            return [mat]
            
        except Exception as e:
            logger.error(f"MP get_by_id failed: {e}")
            return []
    
    def compare_properties(
        self,
        calculated: Dict[str, float],
        reference: MPMaterial
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare calculated properties with MP reference.
        
        Args:
            calculated: Dict of property names to calculated values
            reference: MPMaterial with reference values
        
        Returns:
            Dict with comparison for each property:
            {
                'band_gap': {
                    'calculated': 1.2,
                    'reference': 1.1,
                    'difference': 0.1,
                    'percent_diff': 9.1,
                    'status': 'good'  # good, warning, error
                },
                ...
            }
        """
        comparisons = {}
        
        ref_values = {
            'band_gap': reference.band_gap,
            'volume': reference.volume,
            'density': reference.density,
            'formation_energy': reference.formation_energy,
        }
        
        thresholds = {
            'band_gap': (0.2, 0.5),  # (warning, error) in eV
            'volume': (5, 15),  # percent
            'density': (5, 15),  # percent
            'formation_energy': (0.05, 0.1),  # eV/atom
        }
        
        for prop, calc_val in calculated.items():
            if prop in ref_values:
                ref_val = ref_values[prop]
                
                if ref_val != 0:
                    diff = abs(calc_val - ref_val)
                    pct_diff = 100 * diff / abs(ref_val)
                else:
                    diff = abs(calc_val)
                    pct_diff = 100 if calc_val != 0 else 0
                
                # Determine status
                warn_thresh, err_thresh = thresholds.get(prop, (10, 25))
                
                if prop in ['band_gap', 'formation_energy']:
                    # Absolute thresholds
                    if diff < warn_thresh:
                        status = 'good'
                    elif diff < err_thresh:
                        status = 'warning'
                    else:
                        status = 'error'
                else:
                    # Percentage thresholds
                    if pct_diff < warn_thresh:
                        status = 'good'
                    elif pct_diff < err_thresh:
                        status = 'warning'
                    else:
                        status = 'error'
                
                comparisons[prop] = {
                    'calculated': calc_val,
                    'reference': ref_val,
                    'difference': diff,
                    'percent_diff': pct_diff,
                    'status': status
                }
        
        return comparisons
    
    def _get_mock_data(self, formula: str) -> List[MPMaterial]:
        """Return mock data for demo when API is not available."""
        mock_db = {
            'Si': MPMaterial(
                material_id='mp-149',
                formula='Si',
                formula_pretty='Si',
                spacegroup='Fd-3m',
                crystal_system='cubic',
                volume=40.89,
                density=2.33,
                band_gap=1.11,
                is_metal=False,
                is_magnetic=False,
                formation_energy=0.0,
                energy_above_hull=0.0,
                is_stable=True
            ),
            'Fe2O3': MPMaterial(
                material_id='mp-19770',
                formula='Fe2O3',
                formula_pretty='Fe₂O₃',
                spacegroup='R-3c',
                crystal_system='trigonal',
                volume=100.89,
                density=5.24,
                band_gap=2.2,
                is_metal=False,
                is_magnetic=True,
                formation_energy=-1.52,
                energy_above_hull=0.0,
                is_stable=True
            ),
            'GaAs': MPMaterial(
                material_id='mp-2534',
                formula='GaAs',
                formula_pretty='GaAs',
                spacegroup='F-43m',
                crystal_system='cubic',
                volume=45.27,
                density=5.32,
                band_gap=1.42,
                is_metal=False,
                is_magnetic=False,
                formation_energy=-0.26,
                energy_above_hull=0.0,
                is_stable=True
            ),
        }
        
        if formula in mock_db:
            return [mock_db[formula]]
        
        # Generic mock
        return [
            MPMaterial(
                material_id='mp-mock',
                formula=formula,
                formula_pretty=formula,
                spacegroup='Unknown',
                crystal_system='Unknown',
                volume=100.0,
                density=5.0,
                band_gap=1.0,
                is_metal=False,
                is_magnetic=False,
                formation_energy=0.0,
                energy_above_hull=0.0,
                is_stable=True
            )
        ]

    def _get_mock_cif(self, material_id: str) -> Optional[str]:
        """Return a mock CIF string for demo purposes."""
        if material_id == 'mp-149': # Si
            return """data_Si
_symmetry_space_group_name_H-M   'F d -3 m'
_cell_length_a   5.468728
_cell_length_b   5.468728
_cell_length_c   5.468728
_cell_angle_alpha   90.000000
_cell_angle_beta   90.000000
_cell_angle_gamma   90.000000
loop_
 _atom_site_label
 _atom_site_type_symbol
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 Si1 Si 0.000000 0.000000 0.000000
 Si2 Si 0.250000 0.250000 0.250000"""
        elif material_id == 'mp-19770': # Fe2O3
            return """data_Fe2O3
_symmetry_space_group_name_H-M   'R -3 c'
_cell_length_a   5.038
_cell_length_b   5.038
_cell_length_c   13.772
_cell_angle_alpha   90.000000
_cell_angle_beta   90.000000
_cell_angle_gamma   120.000000
loop_
 _atom_site_label
 _atom_site_type_symbol
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 Fe1 Fe 0.000000 0.000000 0.355300
 O1 O 0.305900 0.000000 0.250000"""
        elif material_id == 'mp-2534': # GaAs
            return """data_GaAs
_symmetry_space_group_name_H-M   'F -4 3 m'
_cell_length_a   5.653
_cell_length_b   5.653
_cell_length_c   5.653
_cell_angle_alpha   90.000000
_cell_angle_beta   90.000000
_cell_angle_gamma   90.000000
loop_
 _atom_site_label
 _atom_site_type_symbol
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 Ga1 Ga 0.000000 0.000000 0.000000
 As1 As 0.250000 0.250000 0.250000"""
        
        return """data_Mock
_cell_length_a   5.0
_cell_length_b   5.0
_cell_length_c   5.0
_cell_angle_alpha   90.0
_cell_angle_beta   90.0
_cell_angle_gamma   90.0
loop_
 _atom_site_label
 _atom_site_type_symbol
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 X1 X 0.0 0.0 0.0"""
