"""
Charge Analysis Module for FluxDFT.

Provides charge analysis including:
- Bader charge analysis
- Löwdin population analysis
- Mulliken charges
- Charge density visualization

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class AtomicCharge:
    """Charge information for a single atom."""
    atom_index: int
    species: str
    position: np.ndarray  # Cartesian coordinates
    
    # Charges from different methods
    bader_charge: Optional[float] = None  # Bader charge (from valence electrons)
    lowdin_charge: Optional[float] = None  # Löwdin population
    mulliken_charge: Optional[float] = None  # Mulliken population
    
    # Additional Bader data
    bader_volume: Optional[float] = None  # Volume of Bader basin
    min_dist: Optional[float] = None  # Min distance to basin surface
    
    # Reference for charge transfer
    valence_electrons: float = 0.0  # Expected valence electrons
    
    @property
    def charge_transfer(self) -> Optional[float]:
        """Net charge transfer (positive = loss of electrons)."""
        if self.bader_charge is not None:
            return self.valence_electrons - self.bader_charge
        return None
    
    @property
    def oxidation_state_estimate(self) -> Optional[int]:
        """Estimate oxidation state from charge transfer."""
        ct = self.charge_transfer
        if ct is not None:
            return round(ct)
        return None


@dataclass
class ChargeAnalysisResult:
    """
    Complete charge analysis results.
    """
    # Atomic charges
    atomic_charges: List[AtomicCharge]
    
    # System totals
    total_charge: float = 0.0
    total_electrons: float = 0.0
    
    # Method used
    method: str = "bader"  # 'bader', 'lowdin', 'mulliken'
    
    # Per-species totals
    species_charges: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    source_file: str = ""
    
    def get_atom(self, index: int) -> Optional[AtomicCharge]:
        """Get atomic charge by index."""
        for atom in self.atomic_charges:
            if atom.atom_index == index:
                return atom
        return None
    
    def get_species_atoms(self, species: str) -> List[AtomicCharge]:
        """Get all atoms of a species."""
        return [a for a in self.atomic_charges if a.species == species]
    
    def summarize(self) -> str:
        """Generate summary of charge analysis."""
        lines = ["=" * 50]
        lines.append(f"Charge Analysis ({self.method.upper()})")
        lines.append("=" * 50)
        lines.append(f"\nTotal electrons: {self.total_electrons:.4f}")
        lines.append(f"Total charge: {self.total_charge:.4f}")
        
        lines.append("\nPer-species charges:")
        for species, total in self.species_charges.items():
            n_atoms = len(self.get_species_atoms(species))
            avg = total / n_atoms if n_atoms > 0 else 0
            lines.append(f"  {species}: total={total:.4f}, avg={avg:.4f}")
        
        lines.append("\nPer-atom charges:")
        for atom in self.atomic_charges:
            charge = atom.bader_charge or atom.lowdin_charge or atom.mulliken_charge or 0
            ct = atom.charge_transfer
            ct_str = f"(Δ={ct:+.3f})" if ct is not None else ""
            lines.append(f"  {atom.atom_index:3d}  {atom.species:3s}  {charge:8.4f}  {ct_str}")
        
        lines.append("=" * 50)
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            'method': self.method,
            'total_electrons': self.total_electrons,
            'total_charge': self.total_charge,
            'species_charges': self.species_charges,
            'atoms': [
                {
                    'index': a.atom_index,
                    'species': a.species,
                    'bader_charge': a.bader_charge,
                    'lowdin_charge': a.lowdin_charge,
                    'charge_transfer': a.charge_transfer,
                }
                for a in self.atomic_charges
            ],
        }


class BaderChargeParser:
    """
    Parser for Bader charge analysis output.
    
    Supports output from:
        - Henkelman group's bader code
        - QE pp.x (charge density)
        - VASP AECCAR
    """
    
    @staticmethod
    def parse_acf(acf_file: Union[str, Path]) -> ChargeAnalysisResult:
        """
        Parse ACF.dat from Bader code.
        
        Format:
        #    X           Y           Z        CHARGE    MIN DIST   ATOMIC VOL
        1  0.000000    0.000000    0.000000    4.00000    1.234        12.34
        ...
        
        Args:
            acf_file: Path to ACF.dat file
            
        Returns:
            ChargeAnalysisResult
        """
        acf_file = Path(acf_file)
        
        atomic_charges = []
        total_charge = 0.0
        
        with open(acf_file, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            
            # Skip header and empty lines
            if not line or line.startswith('#') or line.startswith('-'):
                continue
            
            # Skip summary lines
            if 'VACUUM' in line.upper() or 'NUMBER' in line.upper():
                continue
            
            parts = line.split()
            
            if len(parts) >= 5:
                try:
                    atom_idx = int(parts[0])
                    x = float(parts[1])
                    y = float(parts[2])
                    z = float(parts[3])
                    charge = float(parts[4])
                    
                    min_dist = float(parts[5]) if len(parts) > 5 else None
                    volume = float(parts[6]) if len(parts) > 6 else None
                    
                    atom = AtomicCharge(
                        atom_index=atom_idx,
                        species="",  # Not in ACF.dat
                        position=np.array([x, y, z]),
                        bader_charge=charge,
                        min_dist=min_dist,
                        bader_volume=volume,
                    )
                    atomic_charges.append(atom)
                    total_charge += charge
                    
                except ValueError:
                    continue
        
        return ChargeAnalysisResult(
            atomic_charges=atomic_charges,
            total_electrons=total_charge,
            method='bader',
            source_file=str(acf_file),
        )
    
    @staticmethod
    def add_species_info(
        result: ChargeAnalysisResult,
        species_list: List[str],
        valence_electrons: Dict[str, float],
    ) -> ChargeAnalysisResult:
        """
        Add species information to charge analysis.
        
        Args:
            result: Existing ChargeAnalysisResult
            species_list: Species for each atom
            valence_electrons: Valence electrons per species
            
        Returns:
            Updated ChargeAnalysisResult
        """
        for i, atom in enumerate(result.atomic_charges):
            if i < len(species_list):
                atom.species = species_list[i]
                atom.valence_electrons = valence_electrons.get(atom.species, 0)
        
        # Calculate species totals
        species_charges = {}
        for atom in result.atomic_charges:
            if atom.species:
                if atom.species not in species_charges:
                    species_charges[atom.species] = 0.0
                species_charges[atom.species] += atom.bader_charge or 0
        
        result.species_charges = species_charges
        
        return result


class LowdinChargeParser:
    """
    Parser for Löwdin population analysis from QE.
    """
    
    @staticmethod
    def parse_qe_output(qe_output: Union[str, Path]) -> ChargeAnalysisResult:
        """
        Parse Löwdin charges from QE output.
        
        Args:
            qe_output: Path to QE output file
            
        Returns:
            ChargeAnalysisResult
        """
        import re
        
        qe_output = Path(qe_output)
        
        with open(qe_output, 'r') as f:
            content = f.read()
        
        atomic_charges = []
        
        # Find Löwdin charges section
        lowdin_pattern = re.compile(
            r'Atom\s+#\s*(\d+):\s*\w+.*?total charge\s*=\s*([\d.]+)',
            re.DOTALL
        )
        
        for match in lowdin_pattern.finditer(content):
            atom_idx = int(match.group(1))
            charge = float(match.group(2))
            
            atom = AtomicCharge(
                atom_index=atom_idx,
                species="",
                position=np.zeros(3),
                lowdin_charge=charge,
            )
            atomic_charges.append(atom)
        
        total = sum(a.lowdin_charge or 0 for a in atomic_charges)
        
        return ChargeAnalysisResult(
            atomic_charges=atomic_charges,
            total_electrons=total,
            method='lowdin',
            source_file=str(qe_output),
        )


class ChargeDensityAnalyzer:
    """
    Analyze charge density from cube files.
    
    Provides:
        - Charge integration
        - Slice visualization
        - Difference density calculation
    """
    
    def __init__(self, cube_file: Union[str, Path]):
        """
        Initialize analyzer from cube file.
        
        Args:
            cube_file: Path to Gaussian cube file
        """
        self.cube_file = Path(cube_file)
        self.origin = np.zeros(3)
        self.vectors = np.zeros((3, 3))
        self.n_points = np.zeros(3, dtype=int)
        self.data = None
        self.atoms = []
        
        self._parse_cube()
    
    def _parse_cube(self):
        """Parse cube file format."""
        with open(self.cube_file, 'r') as f:
            lines = f.readlines()
        
        # Skip comment lines
        idx = 2
        
        # Number of atoms and origin
        parts = lines[idx].split()
        n_atoms = abs(int(parts[0]))
        self.origin = np.array([float(x) for x in parts[1:4]])
        idx += 1
        
        # Grid vectors
        for i in range(3):
            parts = lines[idx].split()
            self.n_points[i] = int(parts[0])
            self.vectors[i] = [float(x) for x in parts[1:4]]
            idx += 1
        
        # Atom positions
        for _ in range(n_atoms):
            parts = lines[idx].split()
            atom = {
                'Z': int(parts[0]),
                'charge': float(parts[1]),
                'position': np.array([float(x) for x in parts[2:5]]),
            }
            self.atoms.append(atom)
            idx += 1
        
        # Volumetric data
        data_text = ' '.join(lines[idx:])
        values = [float(x) for x in data_text.split()]
        
        self.data = np.array(values).reshape(self.n_points)
    
    @property
    def voxel_volume(self) -> float:
        """Volume of a single voxel in Bohr³."""
        return abs(np.linalg.det(self.vectors))
    
    def integrate(self) -> float:
        """Integrate total charge."""
        return np.sum(self.data) * self.voxel_volume
    
    def get_slice(
        self,
        axis: int = 2,  # 0=x, 1=y, 2=z
        position: float = 0.5,  # Fractional position
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get 2D slice of charge density.
        
        Args:
            axis: Axis perpendicular to slice (0, 1, or 2)
            position: Fractional position along axis (0-1)
            
        Returns:
            Tuple of (X, Y, density) grids
        """
        idx = int(position * self.n_points[axis])
        idx = min(idx, self.n_points[axis] - 1)
        
        if axis == 0:
            slice_data = self.data[idx, :, :]
            axes = (1, 2)
        elif axis == 1:
            slice_data = self.data[:, idx, :]
            axes = (0, 2)
        else:
            slice_data = self.data[:, :, idx]
            axes = (0, 1)
        
        # Create coordinate grids
        n1, n2 = self.n_points[axes[0]], self.n_points[axes[1]]
        x = np.linspace(0, 1, n1)
        y = np.linspace(0, 1, n2)
        X, Y = np.meshgrid(x, y, indexing='ij')
        
        return X, Y, slice_data
    
    @staticmethod
    def difference_density(
        cube1: 'ChargeDensityAnalyzer',
        cube2: 'ChargeDensityAnalyzer',
    ) -> np.ndarray:
        """
        Calculate difference density (cube1 - cube2).
        
        Args:
            cube1: First cube file
            cube2: Second cube file
            
        Returns:
            Difference density array
        """
        if not np.allclose(cube1.n_points, cube2.n_points):
            raise ValueError("Cube files must have same grid dimensions")
        
        return cube1.data - cube2.data
    
    def plot_slice(
        self,
        ax=None,
        axis: int = 2,
        position: float = 0.5,
        cmap: str = 'RdBu_r',
        **kwargs,
    ):
        """
        Plot 2D slice of charge density.
        
        Args:
            ax: matplotlib axes
            axis: Slice axis
            position: Fractional position
            cmap: Colormap
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.error("matplotlib required for plotting")
            return
        
        if ax is None:
            fig, ax = plt.subplots()
        
        X, Y, data = self.get_slice(axis, position)
        
        im = ax.pcolormesh(X, Y, data, cmap=cmap, shading='auto')
        ax.set_aspect('equal')
        plt.colorbar(im, ax=ax, label='Charge density')
        
        return ax


# Common valence electron configurations
VALENCE_ELECTRONS = {
    'H': 1, 'He': 2,
    'Li': 1, 'Be': 2, 'B': 3, 'C': 4, 'N': 5, 'O': 6, 'F': 7, 'Ne': 8,
    'Na': 1, 'Mg': 2, 'Al': 3, 'Si': 4, 'P': 5, 'S': 6, 'Cl': 7, 'Ar': 8,
    'K': 1, 'Ca': 2,
    'Sc': 3, 'Ti': 4, 'V': 5, 'Cr': 6, 'Mn': 7, 'Fe': 8, 'Co': 9, 'Ni': 10, 'Cu': 11, 'Zn': 12,
    'Ga': 3, 'Ge': 4, 'As': 5, 'Se': 6, 'Br': 7, 'Kr': 8,
    # Add more as needed
}


def analyze_bader_charges(
    acf_file: Union[str, Path],
    species_list: List[str],
    valence_electrons: Optional[Dict[str, float]] = None,
) -> ChargeAnalysisResult:
    """
    Convenience function for Bader charge analysis.
    
    Args:
        acf_file: Path to ACF.dat
        species_list: Species for each atom
        valence_electrons: Valence electrons per species (uses defaults if None)
        
    Returns:
        ChargeAnalysisResult
    """
    if valence_electrons is None:
        valence_electrons = VALENCE_ELECTRONS
    
    result = BaderChargeParser.parse_acf(acf_file)
    result = BaderChargeParser.add_species_info(result, species_list, valence_electrons)
    
    return result
