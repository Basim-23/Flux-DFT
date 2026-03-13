"""
Pre-built workflow templates for common DFT calculations.

These templates provide ready-to-use workflows for typical
calculation scenarios.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
import numpy as np

# Standard k-paths for common crystal structures
KPATHS = {
    'fcc': [
        ('Γ', [0.0, 0.0, 0.0]),
        ('X', [0.5, 0.0, 0.5]),
        ('W', [0.5, 0.25, 0.75]),
        ('K', [0.375, 0.375, 0.75]),
        ('Γ', [0.0, 0.0, 0.0]),
        ('L', [0.5, 0.5, 0.5]),
        ('U', [0.625, 0.25, 0.625]),
        ('W', [0.5, 0.25, 0.75]),
        ('L', [0.5, 0.5, 0.5]),
        ('K', [0.375, 0.375, 0.75]),
    ],
    'bcc': [
        ('Γ', [0.0, 0.0, 0.0]),
        ('H', [0.5, -0.5, 0.5]),
        ('N', [0.0, 0.0, 0.5]),
        ('Γ', [0.0, 0.0, 0.0]),
        ('P', [0.25, 0.25, 0.25]),
        ('H', [0.5, -0.5, 0.5]),
        ('N', [0.0, 0.0, 0.5]),
        ('P', [0.25, 0.25, 0.25]),
    ],
    'hcp': [
        ('Γ', [0.0, 0.0, 0.0]),
        ('M', [0.5, 0.0, 0.0]),
        ('K', [1/3, 1/3, 0.0]),
        ('Γ', [0.0, 0.0, 0.0]),
        ('A', [0.0, 0.0, 0.5]),
        ('L', [0.5, 0.0, 0.5]),
        ('H', [1/3, 1/3, 0.5]),
        ('A', [0.0, 0.0, 0.5]),
    ],
    'simple_cubic': [
        ('Γ', [0.0, 0.0, 0.0]),
        ('X', [0.5, 0.0, 0.0]),
        ('M', [0.5, 0.5, 0.0]),
        ('Γ', [0.0, 0.0, 0.0]),
        ('R', [0.5, 0.5, 0.5]),
        ('X', [0.5, 0.0, 0.0]),
        ('M', [0.5, 0.5, 0.0]),
        ('R', [0.5, 0.5, 0.5]),
    ],
    'tetragonal': [
        ('Γ', [0.0, 0.0, 0.0]),
        ('X', [0.5, 0.0, 0.0]),
        ('M', [0.5, 0.5, 0.0]),
        ('Γ', [0.0, 0.0, 0.0]),
        ('Z', [0.0, 0.0, 0.5]),
        ('R', [0.5, 0.0, 0.5]),
        ('A', [0.5, 0.5, 0.5]),
        ('Z', [0.0, 0.0, 0.5]),
    ],
    'hexagonal': [
        ('Γ', [0.0, 0.0, 0.0]),
        ('M', [0.5, 0.0, 0.0]),
        ('K', [1/3, 1/3, 0.0]),
        ('Γ', [0.0, 0.0, 0.0]),
        ('A', [0.0, 0.0, 0.5]),
        ('L', [0.5, 0.0, 0.5]),
        ('H', [1/3, 1/3, 0.5]),
        ('A', [0.0, 0.0, 0.5]),
    ],
}

# Default convergence parameters by element type
DEFAULT_CUTOFFS = {
    # Light elements (s, p only)
    'H': 30, 'He': 40, 'Li': 40, 'Be': 40, 'B': 40, 'C': 40, 'N': 40, 'O': 40, 'F': 40, 'Ne': 40,
    # Second row
    'Na': 40, 'Mg': 40, 'Al': 40, 'Si': 40, 'P': 45, 'S': 45, 'Cl': 45, 'Ar': 45,
    # Transition metals (need higher cutoffs)
    'Ti': 55, 'V': 55, 'Cr': 55, 'Mn': 55, 'Fe': 60, 'Co': 60, 'Ni': 60, 'Cu': 55, 'Zn': 55,
    # Heavy elements
    'Pt': 60, 'Au': 60, 'Pb': 50,
    # Default
    'DEFAULT': 60,
}


@dataclass
class WorkflowTemplate:
    """
    Template for workflow creation.
    
    Provides pre-configured settings for common calculation types.
    """
    name: str
    description: str
    calculation_types: List[str]
    default_ecutwfc: float
    default_kgrid: Tuple[int, int, int]
    recommended_conv_thr: float
    estimated_time: str  # Human-readable time estimate
    
    def get_settings(self) -> Dict[str, Any]:
        """Get default settings for this template."""
        return {
            'ecutwfc': self.default_ecutwfc,
            'ecutrho': self.default_ecutwfc * 8,
            'kgrid': self.default_kgrid,
            'conv_thr': self.recommended_conv_thr,
        }


# Pre-defined workflow templates
TEMPLATES = {
    'quick_scf': WorkflowTemplate(
        name="Quick SCF",
        description="Fast single-point energy calculation. Good for initial testing.",
        calculation_types=['scf'],
        default_ecutwfc=40.0,
        default_kgrid=(4, 4, 4),
        recommended_conv_thr=1e-6,
        estimated_time="1-5 minutes",
    ),
    
    'accurate_scf': WorkflowTemplate(
        name="Accurate SCF",
        description="High-precision single-point energy. Publication quality.",
        calculation_types=['scf'],
        default_ecutwfc=80.0,
        default_kgrid=(12, 12, 12),
        recommended_conv_thr=1e-10,
        estimated_time="10-60 minutes",
    ),
    
    'band_structure': WorkflowTemplate(
        name="Band Structure",
        description="Electronic band structure along high-symmetry path.",
        calculation_types=['scf', 'bands'],
        default_ecutwfc=60.0,
        default_kgrid=(8, 8, 8),
        recommended_conv_thr=1e-8,
        estimated_time="15-45 minutes",
    ),
    
    'dos': WorkflowTemplate(
        name="Density of States",
        description="Total and projected DOS with fine energy resolution.",
        calculation_types=['scf', 'nscf', 'dos'],
        default_ecutwfc=60.0,
        default_kgrid=(8, 8, 8),  # SCF k-grid; NSCF uses 2x
        recommended_conv_thr=1e-8,
        estimated_time="20-60 minutes",
    ),
    
    'relaxation': WorkflowTemplate(
        name="Atomic Relaxation",
        description="Optimize atomic positions with fixed cell.",
        calculation_types=['relax'],
        default_ecutwfc=60.0,
        default_kgrid=(6, 6, 6),
        recommended_conv_thr=1e-8,
        estimated_time="30-120 minutes",
    ),
    
    'vc_relaxation': WorkflowTemplate(
        name="Full Relaxation",
        description="Optimize both atomic positions and cell parameters.",
        calculation_types=['vc-relax'],
        default_ecutwfc=60.0,
        default_kgrid=(6, 6, 6),
        recommended_conv_thr=1e-8,
        estimated_time="1-4 hours",
    ),
    
    'full_analysis': WorkflowTemplate(
        name="Full Electronic Analysis",
        description="Complete analysis: relax → SCF → bands → DOS.",
        calculation_types=['vc-relax', 'scf', 'bands', 'nscf', 'dos'],
        default_ecutwfc=60.0,
        default_kgrid=(8, 8, 8),
        recommended_conv_thr=1e-8,
        estimated_time="2-8 hours",
    ),
    
    'convergence_ecutwfc': WorkflowTemplate(
        name="Ecutwfc Convergence",
        description="Test energy convergence vs plane-wave cutoff.",
        calculation_types=['scf'] * 6,  # Multiple SCF at different cutoffs
        default_ecutwfc=40.0,  # Starting value
        default_kgrid=(6, 6, 6),
        recommended_conv_thr=1e-8,
        estimated_time="30-90 minutes",
    ),
    
    'convergence_kgrid': WorkflowTemplate(
        name="K-grid Convergence",
        description="Test energy convergence vs k-point density.",
        calculation_types=['scf'] * 5,  # Multiple SCF at different k-grids
        default_ecutwfc=60.0,
        default_kgrid=(4, 4, 4),  # Starting value
        recommended_conv_thr=1e-8,
        estimated_time="30-90 minutes",
    ),
    
    'magnetic': WorkflowTemplate(
        name="Magnetic Calculation",
        description="Spin-polarized calculation for magnetic systems.",
        calculation_types=['scf'],
        default_ecutwfc=60.0,
        default_kgrid=(8, 8, 8),
        recommended_conv_thr=1e-8,
        estimated_time="30-120 minutes",
    ),
    
    'phonon_gamma': WorkflowTemplate(
        name="Gamma Phonons",
        description="Phonon frequencies at Gamma point only.",
        calculation_types=['scf', 'phonon'],
        default_ecutwfc=60.0,
        default_kgrid=(8, 8, 8),
        recommended_conv_thr=1e-10,
        estimated_time="1-4 hours",
    ),
}


def get_kpath_for_structure(structure: 'Structure') -> List[Tuple[str, List[float]]]:
    """
    Determine appropriate k-path for a structure.
    
    Uses pymatgen's symmetry analysis to determine crystal system
    and returns corresponding standard k-path.
    
    Args:
        structure: pymatgen Structure object
        
    Returns:
        List of (label, coords) tuples for k-path
    """
    try:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        from pymatgen.symmetry.bandstructure import HighSymmKpath
        
        # Use pymatgen's high-symmetry k-path generator
        kpath_obj = HighSymmKpath(structure)
        kpath = kpath_obj.kpath
        
        # Convert to our format
        result = []
        for segment in kpath['path']:
            for label in segment:
                coords = kpath['kpoints'][label]
                result.append((label, list(coords)))
        
        return result
    
    except ImportError:
        # Fallback: determine crystal system from lattice
        lattice = structure.lattice
        a, b, c = lattice.abc
        alpha, beta, gamma = lattice.angles
        
        # Simple heuristics for crystal system
        if abs(a - b) < 0.01 and abs(b - c) < 0.01:
            if abs(alpha - 90) < 1 and abs(beta - 90) < 1 and abs(gamma - 90) < 1:
                return KPATHS['simple_cubic']
            elif abs(alpha - 60) < 5 and abs(beta - 60) < 5 and abs(gamma - 60) < 5:
                return KPATHS['fcc']
        elif abs(gamma - 120) < 1:
            return KPATHS['hexagonal']
        
        # Default to simple cubic
        return KPATHS['simple_cubic']


def estimate_ecutwfc(elements: List[str]) -> float:
    """
    Estimate appropriate ecutwfc based on elements.
    
    Args:
        elements: List of element symbols
        
    Returns:
        Recommended ecutwfc in Ry
    """
    max_cutoff = 0
    for elem in elements:
        cutoff = DEFAULT_CUTOFFS.get(elem, DEFAULT_CUTOFFS['DEFAULT'])
        if cutoff > max_cutoff:
            max_cutoff = cutoff
    
    return max_cutoff


def estimate_kgrid(structure: 'Structure', density: float = 30.0) -> Tuple[int, int, int]:
    """
    Estimate appropriate k-grid based on cell size.
    
    Uses the reciprocal cell length to determine k-point density.
    Target: roughly `density` k-points per reciprocal Angstrom.
    
    Args:
        structure: pymatgen Structure
        density: Target k-point density per Å⁻¹
        
    Returns:
        (nk1, nk2, nk3) k-grid
    """
    rec_lattice = structure.lattice.reciprocal_lattice
    rec_lengths = rec_lattice.abc
    
    kgrid = []
    for length in rec_lengths:
        nk = max(1, int(np.ceil(length * density / (2 * np.pi))))
        # Make it even for symmetry
        if nk % 2 == 1:
            nk += 1
        kgrid.append(nk)
    
    return tuple(kgrid)


def get_template(name: str) -> Optional[WorkflowTemplate]:
    """Get workflow template by name."""
    return TEMPLATES.get(name)


def list_templates() -> List[str]:
    """List available template names."""
    return list(TEMPLATES.keys())
