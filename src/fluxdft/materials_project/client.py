"""
Materials Project API Client.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
import json

try:
    from mp_api.client import MPRester
    from pymatgen.electronic_structure.bandstructure import BandStructure
    from pymatgen.electronic_structure.dos import CompleteDos
    HAS_MP_API = True
except ImportError:
    HAS_MP_API = False

from .cache import MPCache


@dataclass
class MPMaterial:
    """Reference material from Materials Project."""
    mp_id: str                          # e.g., "mp-149"
    formula: str                        # e.g., "Si"
    formula_pretty: str                 # e.g., "Si"
    band_gap: Optional[float] = None    # eV (PBE)
    is_gap_direct: Optional[bool] = None
    is_metal: bool = False
    is_magnetic: bool = False
    total_magnetization: Optional[float] = None  # μB/f.u.
    volume: Optional[float] = None      # Å³
    energy_above_hull: float = 0.0      # eV/atom (stability)
    spacegroup: str = ""
    crystal_system: str = ""
    nsites: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mp_id": self.mp_id,
            "formula": self.formula,
            "formula_pretty": self.formula_pretty,
            "band_gap": self.band_gap,
            "is_gap_direct": self.is_gap_direct,
            "is_metal": self.is_metal,
            "is_magnetic": self.is_magnetic,
            "total_magnetization": self.total_magnetization,
            "volume": self.volume,
            "energy_above_hull": self.energy_above_hull,
            "spacegroup": self.spacegroup,
            "crystal_system": self.crystal_system,
            "nsites": self.nsites,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MPMaterial":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class MaterialsProjectClient:
    """
    Client for Materials Project API v2.
    
    Requires user's API key (not bundled with FluxDFT).
    Caches results locally to minimize API calls.
    
    Usage:
        client = MaterialsProjectClient(api_key="your_key")
        materials = client.find_by_formula("Si")
        best = client.find_best_match("Si", spacegroup="Fd-3m")
    """
    
    BASE_URL = "https://api.materialsproject.org"
    
    def __init__(
        self,
        api_key: str,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize the MP client.
        
        Args:
            api_key: User's Materials Project API key
            cache_dir: Directory for local cache
        """
        if not HAS_MP_API:
            raise ImportError("mp-api library required for Materials Project integration. Please install it.")
        
        self.api_key = api_key
        self.cache = MPCache(cache_dir or Path.home() / ".fluxdft" / "mp_cache")
        self.mpr = MPRester(api_key=api_key)
    
    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)
    
    def test_connection(self) -> bool:
        """Test API connection."""
        try:
            # Simple query to check connectivity
            self.mpr.summary.search(formula="Si", fields=["material_id"], num_chunks=1, chunk_size=1)
            return True
        except Exception as e:
            print(f"MP Connection verification failed: {e}")
            return False
    
    def find_by_formula(
        self,
        formula: str,
        limit: int = 20,
    ) -> List[MPMaterial]:
        """
        Find materials by chemical formula.
        
        Args:
            formula: Chemical formula (e.g., "Si", "GaAs", "Fe2O3")
            limit: Maximum number of results
            
        Returns:
            List of matching materials, sorted by stability
        """
        # Check cache first
        cached = self.cache.get_formula(formula)
        if cached:
            return cached
        
        # Query MP API
        try:
            docs = self.mpr.summary.search(
                formula=formula,
                fields=[
                    "material_id",
                    "formula_pretty",
                    "band_gap",
                    "is_gap_direct",
                    "is_metal",
                    "is_magnetic",
                    "total_magnetization",
                    "volume",
                    "energy_above_hull",
                    "symmetry",
                    "nsites",
                ]
            )
        except Exception as e:
            print(f"MP API error: {e}")
            return []
        
        materials = []
        for doc in docs:
            symmetry = doc.symmetry
            materials.append(MPMaterial(
                mp_id=str(doc.material_id),
                formula=formula,
                formula_pretty=doc.formula_pretty,
                band_gap=doc.band_gap,
                is_gap_direct=doc.is_gap_direct,
                is_metal=doc.is_metal,
                is_magnetic=doc.is_magnetic,
                total_magnetization=doc.total_magnetization,
                volume=doc.volume,
                energy_above_hull=doc.energy_above_hull,
                spacegroup=symmetry.symbol if symmetry else "",
                crystal_system=symmetry.crystal_system if symmetry else "",
                nsites=doc.nsites,
            ))
        
        # Sort by stability (energy above hull)
        materials.sort(key=lambda m: m.energy_above_hull)
        
        # Cache results
        if materials:
            self.cache.set_formula(formula, materials)
        
        return materials

    def get_band_structure(self, mp_id: str) -> Optional[BandStructure]:
        """
        Fetch band structure for a material.
        
        Args:
            mp_id: Materials Project ID (e.g., "mp-149")
            
        Returns:
            pymatgen BandStructure object or None if not found/error
        """
        try:
            bs = self.mpr.get_bandstructure_by_material_id(mp_id)
            return bs
        except Exception as e:
            print(f"Error fetching band structure for {mp_id}: {e}")
            return None

    def get_dos(self, mp_id: str) -> Optional[CompleteDos]:
        """
        Fetch Density of States for a material.
        
        Args:
            mp_id: Materials Project ID
            
        Returns:
            pymatgen CompleteDos object or None
        """
        try:
            dos = self.mpr.get_dos_by_material_id(mp_id)
            return dos
        except Exception as e:
            print(f"Error fetching DOS for {mp_id}: {e}")
            return None
    
    def find_best_match(
        self,
        formula: str,
        spacegroup: Optional[str] = None,
        nsites: Optional[int] = None,
    ) -> Optional[MPMaterial]:
        """
        Find the best matching material.
        
        Matching priority:
        1. Exact formula + spacegroup + similar size
        2. Exact formula + ground state (lowest energy_above_hull)
        
        Returns None if no confident match.
        
        Args:
            formula: Chemical formula
            spacegroup: Optional spacegroup symbol for matching
            nsites: Optional number of sites for size matching
        """
        candidates = self.find_by_formula(formula)
        
        if not candidates:
            return None
        
        # Score candidates
        def score(m: MPMaterial) -> float:
            s = 0.0
            
            # Stability is most important (lower energy_above_hull = better)
            # Max 100 points, loses points for being above hull
            s += max(0, 100 - m.energy_above_hull * 1000)
            
            # Spacegroup match bonus
            if spacegroup and m.spacegroup:
                if m.spacegroup == spacegroup:
                    s += 50
                elif m.spacegroup.replace("-", "") == spacegroup.replace("-", ""):
                    s += 30  # Partial match
            
            # Size match bonus
            if nsites and m.nsites:
                size_diff = abs(m.nsites - nsites)
                if size_diff == 0:
                    s += 20
                elif size_diff <= 2:
                    s += 10
            
            return s
        
        best = max(candidates, key=score)
        
        # Confidence check: reject if too far above hull
        if best.energy_above_hull > 0.1:  # >100 meV/atom above hull
            return None
        
        return best
    
    def get_expectations(
        self,
        formula: str,
        spacegroup: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """
        Get pre-calculation expectations.
        
        Returns dict of expected properties with human-readable descriptions.
        """
        ref = self.find_best_match(formula, spacegroup)
        if not ref:
            return None
        
        expectations = {
            "mp_id": ref.mp_id,
            "formula": ref.formula_pretty,
            "spacegroup": ref.spacegroup,
        }
        
        if ref.is_metal:
            expectations["band_gap"] = "Metal (no gap expected)"
        elif ref.band_gap is not None:
            gap_type = "direct" if ref.is_gap_direct else "indirect"
            expectations["band_gap"] = f"~{ref.band_gap:.2f} eV ({gap_type}, PBE)"
        
        if ref.is_magnetic:
            mag = ref.total_magnetization or 0
            expectations["magnetic"] = f"Magnetic (~{mag:.1f} μB/f.u.)"
        else:
            expectations["magnetic"] = "Non-magnetic"
        
        if ref.volume:
            expectations["volume"] = f"~{ref.volume:.1f} Å³"
        
        return expectations
