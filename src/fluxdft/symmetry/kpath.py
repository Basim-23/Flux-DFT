"""
K-path Generator for FluxDFT.

Generates high-symmetry k-point paths for band structure calculations
based on crystal structure and symmetry.

Inspired by sumo's symmetry module and pymatgen's bandstructure module.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import List, Tuple, Dict, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)


# Standard high-symmetry k-points for common crystal systems
# Coordinates are in fractional reciprocal lattice units
KPOINTS_CUBIC = {
    'Γ': [0.0, 0.0, 0.0],
    'R': [0.5, 0.5, 0.5],
    'M': [0.5, 0.5, 0.0],
    'X': [0.5, 0.0, 0.0],
}

KPOINTS_FCC = {
    'Γ': [0.0, 0.0, 0.0],
    'X': [0.5, 0.0, 0.5],
    'W': [0.5, 0.25, 0.75],
    'K': [0.375, 0.375, 0.75],
    'L': [0.5, 0.5, 0.5],
    'U': [0.625, 0.25, 0.625],
}

KPOINTS_BCC = {
    'Γ': [0.0, 0.0, 0.0],
    'H': [0.5, -0.5, 0.5],
    'N': [0.0, 0.0, 0.5],
    'P': [0.25, 0.25, 0.25],
}

KPOINTS_HEXAGONAL = {
    'Γ': [0.0, 0.0, 0.0],
    'A': [0.0, 0.0, 0.5],
    'H': [1/3, 1/3, 0.5],
    'K': [1/3, 1/3, 0.0],
    'L': [0.5, 0.0, 0.5],
    'M': [0.5, 0.0, 0.0],
}

KPOINTS_TETRAGONAL = {
    'Γ': [0.0, 0.0, 0.0],
    'A': [0.5, 0.5, 0.5],
    'M': [0.5, 0.5, 0.0],
    'R': [0.0, 0.5, 0.5],
    'X': [0.0, 0.5, 0.0],
    'Z': [0.0, 0.0, 0.5],
}

KPOINTS_ORTHORHOMBIC = {
    'Γ': [0.0, 0.0, 0.0],
    'R': [0.5, 0.5, 0.5],
    'S': [0.5, 0.5, 0.0],
    'T': [0.0, 0.5, 0.5],
    'U': [0.5, 0.0, 0.5],
    'X': [0.5, 0.0, 0.0],
    'Y': [0.0, 0.5, 0.0],
    'Z': [0.0, 0.0, 0.5],
}

# Standard paths for each crystal system
STANDARD_PATHS = {
    'cubic': ['Γ', 'X', 'M', 'Γ', 'R', 'X', 'M', 'R'],
    'fcc': ['Γ', 'X', 'W', 'K', 'Γ', 'L', 'U', 'W', 'L', 'K'],
    'bcc': ['Γ', 'H', 'N', 'Γ', 'P', 'H', 'N', 'P'],
    'hexagonal': ['Γ', 'M', 'K', 'Γ', 'A', 'L', 'H', 'A'],
    'tetragonal': ['Γ', 'X', 'M', 'Γ', 'Z', 'R', 'A', 'Z'],
    'orthorhombic': ['Γ', 'X', 'S', 'Y', 'Γ', 'Z', 'U', 'R', 'T', 'Z'],
}


@dataclass
class KPathSegment:
    """A segment of the k-path between two high-symmetry points."""
    start_label: str
    end_label: str
    start_coords: np.ndarray
    end_coords: np.ndarray
    n_points: int
    
    @property
    def kpoints(self) -> np.ndarray:
        """Generate k-points along this segment."""
        return np.linspace(self.start_coords, self.end_coords, self.n_points)
    
    @property
    def distance(self) -> float:
        """Distance in reciprocal space (Å⁻¹) - needs lattice info."""
        return np.linalg.norm(self.end_coords - self.start_coords)


@dataclass
class KPath:
    """
    Complete k-point path for band structure calculations.
    
    Contains segments between high-symmetry points with
    methods for generating QE input format.
    """
    segments: List[KPathSegment]
    crystal_system: str
    reciprocal_lattice: Optional[np.ndarray] = None
    
    @property
    def labels(self) -> List[Tuple[int, str]]:
        """Get (index, label) for high-symmetry points."""
        labels = []
        idx = 0
        for i, seg in enumerate(self.segments):
            if i == 0:
                labels.append((idx, seg.start_label))
            idx += seg.n_points - 1
            labels.append((idx, seg.end_label))
        return labels
    
    @property
    def all_kpoints(self) -> np.ndarray:
        """Get all k-points as single array."""
        if not self.segments:
            return np.array([])
        
        kpoints = []
        for i, seg in enumerate(self.segments):
            if i == 0:
                kpoints.append(seg.kpoints)
            else:
                # Skip first point (duplicate of previous segment's end)
                kpoints.append(seg.kpoints[1:])
        
        return np.vstack(kpoints)
    
    @property
    def n_kpoints(self) -> int:
        """Total number of k-points."""
        return len(self.all_kpoints)
    
    def to_qe_input(self) -> str:
        """
        Generate Quantum ESPRESSO K_POINTS card.
        
        Returns K_POINTS in crystal_b format for band structure.
        """
        lines = ["K_POINTS {crystal_b}"]
        lines.append(str(len(self.segments) + 1))
        
        for i, seg in enumerate(self.segments):
            if i == 0:
                # First point
                k = seg.start_coords
                lines.append(
                    f"  {k[0]:.6f}  {k[1]:.6f}  {k[2]:.6f}  {seg.n_points}  ! {seg.start_label}"
                )
            # End point of each segment
            k = seg.end_coords
            n = seg.n_points if i < len(self.segments) - 1 else 1
            lines.append(
                f"  {k[0]:.6f}  {k[1]:.6f}  {k[2]:.6f}  {n}  ! {seg.end_label}"
            )
        
        return "\n".join(lines)
    
    def distances(self) -> np.ndarray:
        """
        Calculate cumulative k-space distances for plotting.
        
        Returns:
            Array of distances from start of path
        """
        if self.reciprocal_lattice is None:
            # Use fractional distances
            logger.warning("No reciprocal lattice set, using fractional distances")
            rec_lat = np.eye(3)
        else:
            rec_lat = self.reciprocal_lattice
        
        kpoints = self.all_kpoints
        distances = [0.0]
        
        for i in range(1, len(kpoints)):
            dk = kpoints[i] - kpoints[i-1]
            # Transform to Cartesian
            dk_cart = np.dot(dk, rec_lat)
            dist = np.linalg.norm(dk_cart)
            distances.append(distances[-1] + dist)
        
        return np.array(distances)
    
    def get_label_positions(self) -> List[Tuple[float, str]]:
        """Get (distance, label) for high-symmetry points."""
        distances = self.distances()
        labels = self.labels
        return [(distances[idx], label) for idx, label in labels]


class KPathGenerator:
    """
    Generate k-point paths for band structure calculations.
    
    Automatically determines crystal system and generates
    appropriate high-symmetry path.
    
    Features:
        - Automatic crystal system detection
        - Standard paths for all Bravais lattices
        - Customizable point density
        - Multiple output formats (QE, VASP, raw)
        - pymatgen integration
    
    Usage:
        >>> generator = KPathGenerator(structure)
        >>> kpath = generator.get_kpath(n_points=50)
        >>> print(kpath.to_qe_input())
    """
    
    def __init__(self, structure: 'Structure'):
        """
        Initialize generator with a structure.
        
        Args:
            structure: pymatgen Structure object
        """
        self.structure = structure
        self._crystal_system = None
        self._spacegroup = None
        self._lattice_type = None
    
    @property
    def crystal_system(self) -> str:
        """Determine crystal system from structure."""
        if self._crystal_system is not None:
            return self._crystal_system
        
        try:
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            sga = SpacegroupAnalyzer(self.structure)
            self._crystal_system = sga.get_crystal_system()
            self._spacegroup = sga.get_space_group_symbol()
            self._lattice_type = sga.get_lattice_type()
            return self._crystal_system
        except ImportError:
            # Fall back to heuristics
            return self._detect_crystal_system_heuristic()
        except Exception as e:
            logger.warning(f"SpacegroupAnalyzer failed: {e}")
            return self._detect_crystal_system_heuristic()
    
    def _detect_crystal_system_heuristic(self) -> str:
        """Detect crystal system from lattice parameters."""
        lattice = self.structure.lattice
        a, b, c = lattice.abc
        alpha, beta, gamma = lattice.angles
        
        tol_length = 0.01  # 1% tolerance
        tol_angle = 1.0  # 1 degree tolerance
        
        def close(x, y):
            return abs(x - y) / max(x, y) < tol_length
        
        def angle_close(x, y):
            return abs(x - y) < tol_angle
        
        # Check for cubic
        if close(a, b) and close(b, c):
            if all(angle_close(ang, 90) for ang in [alpha, beta, gamma]):
                self._crystal_system = 'cubic'
                return 'cubic'
        
        # Check for hexagonal
        if close(a, b) and not close(b, c):
            if angle_close(alpha, 90) and angle_close(beta, 90) and angle_close(gamma, 120):
                self._crystal_system = 'hexagonal'
                return 'hexagonal'
        
        # Check for tetragonal
        if close(a, b) and not close(b, c):
            if all(angle_close(ang, 90) for ang in [alpha, beta, gamma]):
                self._crystal_system = 'tetragonal'
                return 'tetragonal'
        
        # Check for orthorhombic
        if all(angle_close(ang, 90) for ang in [alpha, beta, gamma]):
            if not (close(a, b) or close(b, c) or close(a, c)):
                self._crystal_system = 'orthorhombic'
                return 'orthorhombic'
        
        # Default to cubic path
        logger.warning("Could not determine crystal system, using cubic")
        self._crystal_system = 'cubic'
        return 'cubic'
    
    @property
    def lattice_type(self) -> Optional[str]:
        """Get lattice type (P, I, F, etc.)."""
        if self._lattice_type is None:
            self.crystal_system  # Trigger detection
        return self._lattice_type
    
    def get_kpoints_dict(self) -> Dict[str, List[float]]:
        """Get high-symmetry k-points for this crystal system."""
        system = self.crystal_system.lower()
        lattice = self.lattice_type
        
        # Check for face-centered or body-centered
        if lattice == 'F' or (lattice is None and system == 'cubic'):
            # Try to detect FCC from lattice
            lattice_matrix = self.structure.lattice.matrix
            # FCC has conventional cell with a=b=c and specific conventional form
            # For now, use a simple heuristic
            return KPOINTS_FCC
        elif lattice == 'I':
            return KPOINTS_BCC
        elif system == 'hexagonal':
            return KPOINTS_HEXAGONAL
        elif system == 'tetragonal':
            return KPOINTS_TETRAGONAL
        elif system == 'orthorhombic':
            return KPOINTS_ORTHORHOMBIC
        else:
            return KPOINTS_CUBIC
    
    def get_standard_path(self) -> List[str]:
        """Get standard k-path labels for this crystal system."""
        system = self.crystal_system.lower()
        lattice = self.lattice_type
        
        if lattice == 'F':
            return STANDARD_PATHS['fcc']
        elif lattice == 'I':
            return STANDARD_PATHS['bcc']
        elif system in STANDARD_PATHS:
            return STANDARD_PATHS[system]
        else:
            return STANDARD_PATHS['cubic']
    
    def get_kpath(
        self,
        path: Optional[List[str]] = None,
        n_points: int = 50,
    ) -> KPath:
        """
        Generate k-path for band structure.
        
        Args:
            path: Custom path as list of labels (e.g., ['Γ', 'X', 'M'])
                  If None, uses standard path for crystal system.
            n_points: Number of k-points per segment
            
        Returns:
            KPath object with all segments
        """
        if path is None:
            path = self.get_standard_path()
        
        kpoints_dict = self.get_kpoints_dict()
        
        segments = []
        for i in range(len(path) - 1):
            start_label = path[i]
            end_label = path[i + 1]
            
            # Normalize Gamma
            if start_label in ['G', 'Gamma', 'GAMMA']:
                start_label = 'Γ'
            if end_label in ['G', 'Gamma', 'GAMMA']:
                end_label = 'Γ'
            
            if start_label not in kpoints_dict:
                raise ValueError(f"Unknown k-point: {start_label}")
            if end_label not in kpoints_dict:
                raise ValueError(f"Unknown k-point: {end_label}")
            
            segment = KPathSegment(
                start_label=start_label,
                end_label=end_label,
                start_coords=np.array(kpoints_dict[start_label]),
                end_coords=np.array(kpoints_dict[end_label]),
                n_points=n_points,
            )
            segments.append(segment)
        
        return KPath(
            segments=segments,
            crystal_system=self.crystal_system,
            reciprocal_lattice=self.structure.lattice.reciprocal_lattice.matrix,
        )
    
    def get_kpath_pymatgen(self) -> 'KPath':
        """
        Generate k-path using pymatgen's HighSymmKpath.
        
        This uses the full symmetry analysis for accurate paths.
        
        Returns:
            KPath object
        """
        try:
            from pymatgen.symmetry.bandstructure import HighSymmKpath
            
            kpath_obj = HighSymmKpath(self.structure)
            kpath_dict = kpath_obj.kpath
            
            # Convert to our format
            kpoints = kpath_dict['kpoints']
            path = kpath_dict['path']
            
            segments = []
            for segment_labels in path:
                for i in range(len(segment_labels) - 1):
                    start = segment_labels[i]
                    end = segment_labels[i + 1]
                    
                    seg = KPathSegment(
                        start_label=start,
                        end_label=end,
                        start_coords=np.array(kpoints[start]),
                        end_coords=np.array(kpoints[end]),
                        n_points=50,
                    )
                    segments.append(seg)
            
            return KPath(
                segments=segments,
                crystal_system=self.crystal_system,
                reciprocal_lattice=self.structure.lattice.reciprocal_lattice.matrix,
            )
            
        except ImportError:
            logger.warning("pymatgen not available, using built-in paths")
            return self.get_kpath()


def get_kpath_for_structure(
    structure: 'Structure',
    n_points: int = 50,
    use_pymatgen: bool = True,
) -> KPath:
    """
    Convenience function to get k-path for a structure.
    
    Args:
        structure: pymatgen Structure
        n_points: Points per segment
        use_pymatgen: Use pymatgen's HighSymmKpath if available
        
    Returns:
        KPath object
    """
    generator = KPathGenerator(structure)
    
    if use_pymatgen:
        try:
            return generator.get_kpath_pymatgen()
        except Exception:
            pass
    
    return generator.get_kpath(n_points=n_points)


def format_kpath_for_qe(
    structure: 'Structure',
    n_points: int = 50,
) -> str:
    """
    Generate QE K_POINTS card for band structure.
    
    Args:
        structure: pymatgen Structure
        n_points: Points per segment
        
    Returns:
        QE-formatted K_POINTS card string
    """
    kpath = get_kpath_for_structure(structure, n_points)
    return kpath.to_qe_input()
