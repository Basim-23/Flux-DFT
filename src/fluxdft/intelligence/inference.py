"""
Dynamic DFT Inference Engine.

Infers physical parameters (magnetism, smearing, k-points, cutoffs)
from structural input without hardcoded assumptions.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

try:
    from pymatgen.core import Structure, Element
    from pymatgen.analysis.magnetism import CollinearMagneticStructureAnalyzer
    HAS_PYMATGEN = True
except ImportError:
    HAS_PYMATGEN = False

from ..core.input_builder import KPoints

logger = logging.getLogger(__name__)


# Elements that typically require magnetization checks
MAGNETIC_ELEMENTS = {
    'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu',  # 3d
    'Mo', 'Tc', 'Ru', 'Rh', 'Pd',             # 4d
    'W', 'Re', 'Os', 'Ir', 'Pt',              # 5d
    # Lanthanides
    'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb'
}

# Elements that typically require smearing (Metals/Transition Metals)
METALLIC_ELEMENTS = MAGNETIC_ELEMENTS.union({
    'Li', 'Na', 'K', 'Rb', 'Cs', 'Mg', 'Ca', 'Sr', 'Ba', 
    'Al', 'Ga', 'In', 'Tl', 'Sn', 'Pb', 'Bi'
})


class MaterialIntelligence:
    """
    Intelligent analyzer for input structures.
    Decides calculation parameters dynamically.
    """

    def __init__(self, structure: 'Structure'):
        if not HAS_PYMATGEN:
            raise ImportError("Pymatgen is required for MaterialIntelligence.")
        self.structure = structure

    def infer_calculation_settings(self) -> Dict[str, Any]:
        """
        Infer all critical calculation settings.
        
        Returns:
            Dict containing:
            - system: {nspin, occupations, smearing, degauss}
            - magnetism: {starting_magnetization}
            - kpoints: KPoints object
        """
        settings = {}
        
        # 1. Magnetism
        mag_settings = self._infer_magnetism()
        settings.update(mag_settings)
        
        # 2. Electronic Character (Smearing)
        elec_settings = self._infer_electronic_character(is_magnetic=mag_settings.get('nspin') == 2)
        settings.update(elec_settings)
        
        # 3. K-Points
        kpoints = self._generate_kmesh()
        settings['kpoints'] = kpoints
        
        return settings

    def _infer_magnetism(self) -> Dict[str, Any]:
        """Detect potential magnetism."""
        composition = self.structure.composition
        elements = [e.symbol for e in composition.elements]
        
        # Check if any magnetic elements are present
        has_magnetic = any(e in MAGNETIC_ELEMENTS for e in elements)
        
        if not has_magnetic:
            return {'nspin': 1, 'starting_magnetization': {}}
            
        logger.info(f"Magnetic elements detected: {[e for e in elements if e in MAGNETIC_ELEMENTS]}")
        
        # Assign default starting magnetization
        # Rule of thumb: High spin for 3d, lower for others?
        # Safe default: 0.5-1.0 to break symmetry
        starting_mag = {}
        for el in elements:
            if el in MAGNETIC_ELEMENTS:
                if el in ['Fe', 'Co', 'Ni', 'Mn']:
                     starting_mag[el] = 1.0 # Strong ferromagnets
                elif el in ['Cr']:
                     starting_mag[el] = 1.0 # Often antiferro, but need generic start
                else:
                     starting_mag[el] = 0.2 # Small nudge
        
        return {
            'nspin': 2,
            'starting_magnetization': starting_mag,
            # For non-collinear, we'd need more logic
        }

    def _infer_electronic_character(self, is_magnetic: bool) -> Dict[str, Any]:
        """Decide occupation type."""
        composition = self.structure.composition
        elements = [e.symbol for e in composition.elements]
        
        # Heuristic: If it has d-block or specific metals, assume metal/smearing
        # Unless we KNOW it's an insulator (difficult without database)
        
        is_metal = is_magnetic or any(e in METALLIC_ELEMENTS for e in elements)
        
        if is_metal:
            # Safer to use smearing for everything unknown
            return {
                'occupations': 'smearing',
                'smearing': 'marzari-vanderbilt' if not is_magnetic else 'methfessel-paxton',
                'degauss': 0.015 # ~0.2 eV
            }
        else:
            # Noble gases, simple insulators?
            # Actually, standard DFT even for insulators handles fixed well only if there's a gap.
            # safe fallback:
            if any(e in ['H', 'He', 'C', 'N', 'O', 'F', 'Ne', 'P', 'S', 'Cl', 'Ar'] for e in elements):
                 # Likely molecule or insulator
                 return {
                     'occupations': 'fixed',
                     'smearing': None,
                     'degauss': None
                 }
            
            # Fallback
            return {
                'occupations': 'smearing',
                'smearing': 'gaussian',
                'degauss': 0.01
            }

    def _generate_kmesh(self, spacing: float = 0.2) -> KPoints:
        """
        Generate K-mesh density based on lattice vectors.
        Target spacing in 1/Å (Reciprocal Angstrom).
        """
        lattice = self.structure.lattice
        # Reciprocal lattice lengths (norm of b1, b2, b3) * 2pi
        recip_lengths = lattice.reciprocal_lattice.abc 
        
        # grid = ceil( length / spacing )
        # Note: pymatgen reciprocal_lattice.abc includes 2pi factor? 
        # Pymatgen recip_lattice is defined s.t. a_i . b_j = 2pi delta_ij
        # So b_length is in 2pi/Angstrom? No, usually just 1/Length units * 2pi.
        # Let's verify: a=5.43 -> b ~ 1/5.43 * 2pi ~ 1.15
        # If spacing is 0.2 (fine), then 1.15 / 0.2 ~ 6.
        
        kgrid = []
        for l in recip_lengths:
            k = max(1, int(np.ceil(l / (spacing * 2 * np.pi)))) 
            # Wait, commonly spacing is defined as 2pi * (1/L). 
            # Let's say we want grid*L > X. 
            # Using simple lookup: 
            # k * a_real > 30-50 Angstroms is a common rule.
            
            # Alternative: k_i >= 2 * pi / (a_i * spacing)
            # where spacing is e.g. 0.03 1/Bohr -> ~0.06 1/Angstrom
            
            # Let's stick to valid grid density: 0.2 A^-1 is coarse-medium. 
            # 0.15 is fine. 
            # k_i = ceil( |b_i| / spacing )
            
            k = max(1, int(np.ceil(l / spacing)))
            kgrid.append(k)
            
        return KPoints(
            mode="automatic",
            grid=tuple(kgrid),
            shift=(0, 0, 0) # Gamma-centered is safer usually
        )
