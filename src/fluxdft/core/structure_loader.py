"""
Universal Structure Loader for FluxDFT.

Handles all common DFT file formats using ASE + pymatgen.
Provides unified interface for structure file loading with automatic format detection.

FluxDFT IP: Format detection, error recovery, QE-specific handling.
Open-source: ASE (I/O), pymatgen (Structure object).

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Union, Optional, List, Tuple
from pathlib import Path
import logging
import json

logger = logging.getLogger(__name__)

# Core dependencies
try:
    from pymatgen.core import Structure, Molecule
    from pymatgen.io.ase import AseAtomsAdaptor
    HAS_PYMATGEN = True
except ImportError:
    HAS_PYMATGEN = False
    Structure = object

# Pymatgen-specific parsers
try:
    from pymatgen.io.vasp import Poscar
    from pymatgen.io.cif import CifParser
    from pymatgen.io.pwscf import PWInput
    HAS_PYMATGEN_IO = True
except ImportError:
    HAS_PYMATGEN_IO = False

# ASE for fallback and additional formats
try:
    from ase.io import read as ase_read
    HAS_ASE = True
except ImportError:
    HAS_ASE = False

from .structure_model import StructureModel


class StructureLoaderError(Exception):
    """Exception raised when structure loading fails."""
    pass


class StructureLoader:
    """
    Universal structure file loader.
    
    Supports:
        - POSCAR/CONTCAR (VASP)
        - CIF (Crystallographic Information File)
        - QE input/output (Quantum ESPRESSO)
        - XYZ (Atomic coordinates)
        - JSON (pymatgen serialization)
        - PDB (Protein Data Bank)
        - Any format ASE supports
        
    Usage:
        >>> model = StructureLoader.from_file("POSCAR")
        >>> model = StructureLoader.from_file("structure.cif")
        >>> model = StructureLoader.from_file("pw.in")
        
    The loader uses a priority system:
        1. Try specific format handlers based on extension
        2. Try pymatgen's universal loader
        3. Fallback to ASE
    """
    
    # Format detection by extension
    FORMAT_HANDLERS = {
        '.cif': '_load_cif',
        '.xyz': '_load_xyz',
        '.json': '_load_json',
        '.vasp': '_load_poscar',
        '.in': '_load_qe_input',
        '.out': '_load_qe_output',
        '.pdb': '_load_via_ase',
        '.extxyz': '_load_via_ase',
    }
    
    # Known VASP filename patterns
    VASP_FILENAMES = {'POSCAR', 'CONTCAR', 'CHGCAR', 'CHG'}
    
    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> StructureModel:
        """
        Load structure from file with automatic format detection.
        
        Args:
            filepath: Path to structure file
            
        Returns:
            StructureModel with loaded structure
            
        Raises:
            StructureLoaderError: If file cannot be loaded
            FileNotFoundError: If file does not exist
        """
        if not HAS_PYMATGEN:
            raise StructureLoaderError(
                "pymatgen is required for structure loading. "
                "Install with: pip install pymatgen"
            )
        
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Structure file not found: {filepath}")
        
        ext = filepath.suffix.lower()
        name = filepath.stem.upper()
        
        errors_encountered = []
        
        # Try specific handlers first based on extension
        if ext in cls.FORMAT_HANDLERS:
            handler_name = cls.FORMAT_HANDLERS[ext]
            handler = getattr(cls, handler_name)
            try:
                return handler(filepath)
            except Exception as e:
                errors_encountered.append(f"{handler_name}: {e}")
                logger.warning(f"Handler {handler_name} failed: {e}")
        
        # Check for POSCAR/CONTCAR naming convention (no extension)
        if name in cls.VASP_FILENAMES or ext == '':
            try:
                return cls._load_poscar(filepath)
            except Exception as e:
                errors_encountered.append(f"POSCAR handler: {e}")
                logger.warning(f"POSCAR handler failed: {e}")
        
        # Fallback to pymatgen universal loader
        try:
            structure = Structure.from_file(str(filepath))
            logger.info(f"Loaded structure via pymatgen universal loader: {filepath}")
            return StructureModel(structure)
        except Exception as e:
            errors_encountered.append(f"pymatgen universal: {e}")
            logger.warning(f"pymatgen universal loader failed: {e}")
        
        # Final fallback: ASE
        if HAS_ASE:
            try:
                return cls._load_via_ase(filepath)
            except Exception as e:
                errors_encountered.append(f"ASE: {e}")
                logger.warning(f"ASE loader failed: {e}")
        
        # All attempts failed
        error_details = "\n  ".join(errors_encountered)
        raise StructureLoaderError(
            f"Failed to load structure from {filepath}.\n"
            f"Attempted methods:\n  {error_details}"
        )
    
    @classmethod
    def from_string(
        cls, 
        content: str, 
        format: str = 'poscar'
    ) -> StructureModel:
        """
        Load structure from string content.
        
        Args:
            content: Structure data as string
            format: Format hint ('poscar', 'cif', 'xyz', 'json')
            
        Returns:
            StructureModel with loaded structure
        """
        format = format.lower()
        
        if format == 'poscar':
            poscar = Poscar.from_string(content)
            return StructureModel(poscar.structure)
        elif format == 'cif':
            parser = CifParser.from_string(content)
            structures = parser.get_structures(primitive=False)
            if structures:
                return StructureModel(structures[0])
            raise StructureLoaderError("No valid structure in CIF string")
        elif format == 'json':
            data = json.loads(content)
            structure = Structure.from_dict(data)
            return StructureModel(structure)
        elif format == 'xyz':
            # XYZ requires ASE
            if not HAS_ASE:
                raise StructureLoaderError("ASE required for XYZ string parsing")
            from io import StringIO
            from ase.io import read as ase_read_file
            atoms = ase_read_file(StringIO(content), format='xyz')
            structure = AseAtomsAdaptor.get_structure(atoms)
            return StructureModel(structure)
        else:
            raise StructureLoaderError(f"Unsupported string format: {format}")
    
    @classmethod
    def _load_poscar(cls, filepath: Path) -> StructureModel:
        """Load VASP POSCAR/CONTCAR format."""
        if not HAS_PYMATGEN_IO:
            raise StructureLoaderError("pymatgen.io.vasp not available")
        
        poscar = Poscar.from_file(str(filepath))
        logger.info(f"Loaded POSCAR: {poscar.comment}")
        return StructureModel(poscar.structure)
    
    @classmethod
    def _load_cif(cls, filepath: Path) -> StructureModel:
        """
        Load CIF format with primitive cell option.
        
        Note: By default, returns conventional cell (primitive=False).
        """
        if not HAS_PYMATGEN_IO:
            raise StructureLoaderError("pymatgen.io.cif not available")
        
        parser = CifParser(str(filepath))
        structures = parser.get_structures(primitive=False)
        
        if not structures:
            raise StructureLoaderError(f"No valid structure found in CIF: {filepath}")
        
        # If multiple structures, log warning and return first
        if len(structures) > 1:
            logger.warning(
                f"CIF contains {len(structures)} structures. "
                f"Returning first structure."
            )
        
        logger.info(f"Loaded CIF with {len(structures[0])} sites")
        return StructureModel(structures[0])
    
    @classmethod
    def _load_qe_input(cls, filepath: Path) -> StructureModel:
        """Load Quantum ESPRESSO input file."""
        if not HAS_PYMATGEN_IO:
            raise StructureLoaderError("pymatgen.io.pwscf not available")
        
        pw_input = PWInput.from_file(str(filepath))
        logger.info(f"Loaded QE input with {len(pw_input.structure)} sites")
        return StructureModel(pw_input.structure)
    
    @classmethod
    def _load_qe_output(cls, filepath: Path) -> StructureModel:
        """
        Load final structure from QE output file.
        
        Extracts the final atomic positions from a completed calculation.
        """
        # Try using FluxDFT's own output parser first
        try:
            from .output_parser import OutputParser
            parser = OutputParser(filepath)
            if hasattr(parser, 'final_structure') and parser.final_structure:
                logger.info("Loaded structure from QE output via OutputParser")
                return StructureModel(parser.final_structure)
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"OutputParser failed: {e}")
        
        # Fallback: Try pymatgen's QE output parser
        try:
            from pymatgen.io.pwscf import PWOutput
            pw_output = PWOutput(str(filepath))
            if hasattr(pw_output, 'final_structure') and pw_output.final_structure:
                return StructureModel(pw_output.final_structure)
        except Exception as e:
            logger.warning(f"PWOutput parser failed: {e}")
        
        raise StructureLoaderError(
            f"Could not extract structure from QE output: {filepath}"
        )
    
    @classmethod
    def _load_xyz(cls, filepath: Path) -> StructureModel:
        """Load XYZ format via ASE."""
        return cls._load_via_ase(filepath, format='xyz')
    
    @classmethod
    def _load_json(cls, filepath: Path) -> StructureModel:
        """Load pymatgen JSON serialization."""
        structure = Structure.from_file(str(filepath))
        logger.info(f"Loaded structure from JSON")
        return StructureModel(structure)
    
    @classmethod
    def _load_via_ase(
        cls, 
        filepath: Path, 
        format: Optional[str] = None
    ) -> StructureModel:
        """
        Fallback loader using ASE.
        
        ASE supports many formats including:
        - XYZ, extXYZ
        - PDB
        - Gaussian
        - LAMMPS
        - And many more...
        """
        if not HAS_ASE:
            raise StructureLoaderError(
                "ASE is required for this file format. "
                "Install with: pip install ase"
            )
        
        try:
            atoms = ase_read(str(filepath), format=format)
        except Exception as e:
            raise StructureLoaderError(f"ASE failed to read file: {e}")
        
        # Convert ASE Atoms to pymatgen Structure
        try:
            structure = AseAtomsAdaptor.get_structure(atoms)
        except Exception as e:
            # Might be a molecule (no periodicity)
            try:
                molecule = AseAtomsAdaptor.get_molecule(atoms)
                # Convert molecule to structure with large box
                coords = molecule.cart_coords
                species = [site.specie for site in molecule]
                
                # Create box large enough to contain molecule
                from pymatgen.core import Lattice
                max_extent = max(
                    coords.max(axis=0) - coords.min(axis=0)
                ) + 15.0  # 15 Å vacuum
                
                lattice = Lattice.cubic(max_extent)
                # Center molecule
                center_shift = max_extent / 2 - coords.mean(axis=0)
                centered_coords = coords + center_shift
                
                structure = Structure(
                    lattice,
                    species,
                    centered_coords,
                    coords_are_cartesian=True
                )
                logger.warning(
                    "Loaded molecule and placed in cubic box with 15 Å vacuum"
                )
            except Exception as e2:
                raise StructureLoaderError(
                    f"Could not convert ASE atoms to pymatgen: {e}, {e2}"
                )
        
        logger.info(f"Loaded structure via ASE with {len(structure)} sites")
        return StructureModel(structure)
    
    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """Return list of supported file extensions."""
        formats = list(cls.FORMAT_HANDLERS.keys())
        formats.extend(['.poscar', '.contcar', '(no extension)'])
        return formats
    
    @classmethod
    def detect_format(cls, filepath: Union[str, Path]) -> str:
        """
        Detect the format of a structure file.
        
        Returns:
            Format string (e.g., 'poscar', 'cif', 'xyz', 'qe_input', 'unknown')
        """
        filepath = Path(filepath)
        ext = filepath.suffix.lower()
        name = filepath.stem.upper()
        
        if name in cls.VASP_FILENAMES:
            return 'poscar'
        
        format_map = {
            '.cif': 'cif',
            '.xyz': 'xyz',
            '.json': 'json',
            '.vasp': 'poscar',
            '.in': 'qe_input',
            '.out': 'qe_output',
            '.pdb': 'pdb',
        }
        
        return format_map.get(ext, 'unknown')
