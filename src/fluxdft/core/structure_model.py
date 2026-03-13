"""
Core Structure Model using methods from Pymatgen.
"""

from typing import Union, List, Tuple
import numpy as np

try:
    from pymatgen.core import Structure, Molecule
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    from pymatgen.io.ase import AseAtomsAdaptor
    HAS_PYMATGEN = True
except ImportError:
    HAS_PYMATGEN = False
    Structure = object

class StructureModel:
    """
    Wrapper around pymatgen Structure to provide unified interface.
    """
    
    def __init__(self, structure: Union[Structure, 'None'] = None):
        self._structure = structure
        self._supercell_matrix = np.eye(3)
        
    @property
    def structure(self) -> Structure:
        return self._structure
        
    @structure.setter
    def structure(self, val: Structure):
        self._structure = val
        
    @classmethod
    def from_file(cls, filename: str):
        """Load structure from file using generic pymatgen loader."""
        if not HAS_PYMATGEN:
            raise ImportError("Pymatgen not installed")
        
        # Pymatgen handles POSCAR, CIF, etc. automatically
        struct = Structure.from_file(filename)
        
        # Always convert to conventional standard structure for better visualization
        try:
            analyzer = SpacegroupAnalyzer(struct)
            conventional_struct = analyzer.get_conventional_standard_structure()
            struct = conventional_struct
        except Exception as e:
            print(f"Failed to get conventional structure: {e}")
            
        return cls(struct)
        
    @classmethod
    def from_ase(cls, atoms):
        """Convert ASE Atoms to StructureModel."""
        if not HAS_PYMATGEN:
             raise ImportError("Pymatgen not installed")
        struct = AseAtomsAdaptor.get_structure(atoms)
        return cls(struct)
        
    def to_ase(self):
        """Convert back to ASE Atoms (for legacy compatibility)."""
        if self._structure is None:
            return None
        return AseAtomsAdaptor.get_atoms(self._structure)
        
    def make_supercell(self, scaling_matrix):
        """Create a supercell structure."""
        if self._structure:
            self._structure.make_supercell(scaling_matrix)
            
    def get_positions(self) -> np.ndarray:
        if self._structure:
            return self._structure.cart_coords
        return np.array([])
        
    def get_atomic_numbers(self) -> List[int]:
        if self._structure:
            return [s.specie.number for s in self._structure]
        return []

    def get_chemical_symbols(self) -> List[str]:
        if self._structure:
            # Handle cases where species might be Element or Specie (with oxidation)
            return [s.specie.symbol for s in self._structure]
        return []
        
    def get_cell_matrix(self) -> np.ndarray:
        if self._structure:
            return self._structure.lattice.matrix
        return np.eye(3)
