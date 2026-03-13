"""
Structure file importer for FluxDFT.

Supports importing crystal structures from various file formats
and converting them to Quantum ESPRESSO input format.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

try:
    from ase import Atoms
    from ase.io import read as ase_read
    HAS_ASE = True
except ImportError:
    HAS_ASE = False


@dataclass
class ImportedStructure:
    """Imported structure data."""
    atoms: Any  # ASE Atoms object
    source_file: Path
    source_format: str
    formula: str
    n_atoms: int
    cell_parameters: List[List[float]]
    positions: List[Tuple[str, float, float, float]]
    
    @property
    def elements(self) -> List[str]:
        """Get unique elements."""
        return list(set(sym for sym, *_ in self.positions))


class StructureImporter:
    """
    Import crystal structures from various file formats.
    
    Supported formats:
    - POSCAR/CONTCAR (VASP)
    - CIF (Crystallographic Information File)
    - XYZ
    - PDB
    - Quantum ESPRESSO input (.pwi, .in)
    - LAMMPS data files
    - Extended XYZ
    
    Usage:
        importer = StructureImporter()
        structure = importer.import_file("POSCAR")
        qe_cards = importer.to_qe_format(structure)
    """
    
    # Supported formats and their file extensions
    SUPPORTED_FORMATS = {
        "vasp": [".poscar", ".contcar", ".vasp"],
        "cif": [".cif"],
        "xyz": [".xyz"],
        "pdb": [".pdb"],
        "qe": [".pwi", ".in", ".qe"],
        "lammps": [".lmp", ".lammps"],
        "extxyz": [".extxyz"],
    }
    
    # Format display names
    FORMAT_NAMES = {
        "vasp": "VASP POSCAR",
        "cif": "CIF",
        "xyz": "XYZ",
        "pdb": "PDB",
        "qe": "Quantum ESPRESSO",
        "lammps": "LAMMPS",
        "extxyz": "Extended XYZ",
    }
    
    def __init__(self):
        if not HAS_ASE:
            raise ImportError(
                "ASE (Atomic Simulation Environment) is required for structure import. "
                "Install with: pip install ase"
            )
    
    @classmethod
    def get_file_filter(cls) -> str:
        """Get file dialog filter string."""
        filters = []
        all_exts = []
        
        for fmt, exts in cls.SUPPORTED_FORMATS.items():
            name = cls.FORMAT_NAMES.get(fmt, fmt.upper())
            ext_str = " ".join(f"*{e}" for e in exts)
            filters.append(f"{name} ({ext_str})")
            all_exts.extend(f"*{e}" for e in exts)
        
        all_filter = f"All Structure Files ({' '.join(all_exts)})"
        return ";;".join([all_filter] + filters + ["All Files (*)"])
    
    def detect_format(self, filepath: Path) -> Optional[str]:
        """Detect format from file extension."""
        ext = filepath.suffix.lower()
        
        # Handle POSCAR/CONTCAR without extension
        if filepath.name.upper() in ("POSCAR", "CONTCAR"):
            return "vasp"
        
        for fmt, exts in self.SUPPORTED_FORMATS.items():
            if ext in exts:
                return fmt
        
        return None
    
    def import_file(
        self, 
        filepath: str | Path,
        format: Optional[str] = None,
    ) -> ImportedStructure:
        """
        Import structure from file.
        
        Args:
            filepath: Path to structure file
            format: Optional format hint (auto-detected if not provided)
            
        Returns:
            ImportedStructure with atoms and metadata
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Detect format
        fmt = format or self.detect_format(filepath)
        
        # Map to ASE format string
        ase_format = self._get_ase_format(fmt, filepath)
        
        # Read with ASE
        try:
            atoms = ase_read(str(filepath), format=ase_format)
        except Exception as e:
            raise ValueError(f"Could not read {filepath}: {e}")
        
        # Extract data
        formula = atoms.get_chemical_formula()
        n_atoms = len(atoms)
        
        # Cell parameters
        cell = atoms.get_cell()
        cell_parameters = cell.tolist()
        
        # Atomic positions (fractional)
        scaled_positions = atoms.get_scaled_positions()
        symbols = atoms.get_chemical_symbols()
        
        positions = [
            (sym, *pos) 
            for sym, pos in zip(symbols, scaled_positions)
        ]
        
        return ImportedStructure(
            atoms=atoms,
            source_file=filepath,
            source_format=fmt or "unknown",
            formula=formula,
            n_atoms=n_atoms,
            cell_parameters=cell_parameters,
            positions=positions,
        )
    
    def _get_ase_format(self, fmt: Optional[str], filepath: Path) -> Optional[str]:
        """Map our format to ASE format string."""
        if fmt == "vasp" or filepath.name.upper() in ("POSCAR", "CONTCAR"):
            return "vasp"
        elif fmt == "cif":
            return "cif"
        elif fmt == "xyz":
            return "xyz"
        elif fmt == "pdb":
            return "pdb"
        elif fmt == "qe":
            return "espresso-in"
        elif fmt == "lammps":
            return "lammps-data"
        elif fmt == "extxyz":
            return "extxyz"
        
        return None  # Let ASE auto-detect
    
    def to_qe_format(self, structure: ImportedStructure) -> Dict[str, str]:
        """
        Convert imported structure to QE input format.
        
        Returns dict with:
        - atomic_species: ATOMIC_SPECIES card content
        - atomic_positions: ATOMIC_POSITIONS card content
        - cell_parameters: CELL_PARAMETERS card content
        - system_params: Dict of SYSTEM namelist parameters
        """
        atoms = structure.atoms
        
        # CELL_PARAMETERS
        cell = atoms.get_cell()
        cell_lines = ["CELL_PARAMETERS angstrom"]
        for row in cell:
            cell_lines.append(f"  {row[0]:15.10f} {row[1]:15.10f} {row[2]:15.10f}")
        
        # ATOMIC_SPECIES (unique elements with placeholder pseudopotentials)
        elements = structure.elements
        species_lines = ["ATOMIC_SPECIES"]
        for el in sorted(elements):
            # Use standard naming convention for pseudopotentials
            pp_name = f"{el}.upf"
            mass = atoms[atoms.get_chemical_symbols().index(el)].mass
            species_lines.append(f"  {el:3s}  {mass:10.4f}  {pp_name}")
        
        # ATOMIC_POSITIONS
        positions_lines = ["ATOMIC_POSITIONS crystal"]
        scaled = atoms.get_scaled_positions()
        symbols = atoms.get_chemical_symbols()
        for sym, pos in zip(symbols, scaled):
            positions_lines.append(
                f"  {sym:3s}  {pos[0]:15.10f} {pos[1]:15.10f} {pos[2]:15.10f}"
            )
        
        # System parameters
        system_params = {
            "nat": len(atoms),
            "ntyp": len(elements),
            "ibrav": 0,  # Using explicit cell
        }
        
        return {
            "cell_parameters": "\n".join(cell_lines),
            "atomic_species": "\n".join(species_lines),
            "atomic_positions": "\n".join(positions_lines),
            "system_params": system_params,
            "formula": structure.formula,
        }
    
    def get_structure_info(self, structure: ImportedStructure) -> str:
        """Get human-readable structure information."""
        atoms = structure.atoms
        
        lines = [
            f"Formula: {structure.formula}",
            f"Atoms: {structure.n_atoms}",
            f"Elements: {', '.join(sorted(structure.elements))}",
            "",
            "Cell Parameters (Å):",
        ]
        
        cell = atoms.get_cell()
        lengths = cell.lengths()
        angles = cell.angles()
        
        lines.extend([
            f"  a = {lengths[0]:.4f}, b = {lengths[1]:.4f}, c = {lengths[2]:.4f}",
            f"  α = {angles[0]:.2f}°, β = {angles[1]:.2f}°, γ = {angles[2]:.2f}°",
            f"  Volume = {atoms.get_volume():.2f} Å³",
        ])
        
        return "\n".join(lines)
