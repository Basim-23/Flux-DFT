"""
Input File Builder for Quantum ESPRESSO.

Generates valid input files for QE executables (pw.x, bands.x, dos.x, etc.)
from a Python dictionary of parameters.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


@dataclass
class AtomicSpecies:
    """Atomic species definition."""
    symbol: str
    mass: float
    pseudopotential: str


@dataclass
class Atom:
    """Single atom with position."""
    symbol: str
    position: Tuple[float, float, float]
    if_pos: Tuple[int, int, int] = (1, 1, 1)  # Constraint flags


@dataclass
class CellParameters:
    """Unit cell definition."""
    vectors: np.ndarray  # 3x3 matrix
    units: str = "angstrom"  # angstrom, bohr, alat


@dataclass
class KPoints:
    """K-points specification."""
    mode: str = "automatic"  # automatic, gamma, crystal, crystal_b
    grid: Optional[Tuple[int, int, int]] = None  # For automatic
    shift: Tuple[int, int, int] = (0, 0, 0)  # For automatic
    points: Optional[List[Tuple[float, float, float, float]]] = None  # For explicit
    labels: Optional[List[str]] = None  # For band structure


@dataclass
class PWInput:
    """Complete pw.x input specification."""
    
    # Control namelist
    calculation: str = "scf"
    prefix: str = "pwscf"
    outdir: str = "./"
    pseudo_dir: str = "./"
    verbosity: str = "low"
    restart_mode: str = "from_scratch"
    tstress: bool = False
    tprnfor: bool = False
    
    # System namelist
    ibrav: int = 0
    celldm: Optional[List[float]] = None
    A: Optional[float] = None
    nat: int = 0
    ntyp: int = 0
    ecutwfc: float = 30.0
    ecutrho: Optional[float] = None
    occupations: str = "fixed"
    smearing: Optional[str] = None
    degauss: Optional[float] = None
    nbnd: Optional[int] = None
    tot_charge: float = 0.0
    nspin: int = 1
    
    # Electrons namelist
    conv_thr: float = 1.0e-8
    mixing_beta: float = 0.7
    mixing_mode: str = "plain"
    diagonalization: str = "david"
    electron_maxstep: int = 100
    
    # Ions namelist (for relax/md)
    ion_dynamics: Optional[str] = None
    
    # Cell namelist (for vc-relax)
    cell_dynamics: Optional[str] = None
    press: Optional[float] = None
    
    # Structure
    cell: Optional[CellParameters] = None
    species: List[AtomicSpecies] = field(default_factory=list)
    atoms: List[Atom] = field(default_factory=list)
    atomic_positions_units: str = "crystal"
    
    # K-points
    kpoints: KPoints = field(default_factory=KPoints)
    
    # Hybrid Functionals (HSE)
    input_dft: Optional[str] = None  # e.g., 'hse', 'pbe0'
    nqx1: Optional[int] = None # q-grid for exact exchange
    nqx2: Optional[int] = None
    nqx3: Optional[int] = None
    x_gamma_extrapolation: bool = True
    exx_div_treatment: str = "gyftopoulos"
    
    # Hubbard U (DFT+U)
    lda_plus_u: bool = False
    hubbard_u: Dict[str, float] = field(default_factory=dict)  # {Species: U_value}
    
    # Magnetism
    starting_magnetization: Dict[str, float] = field(default_factory=dict) # {Species: mag}
    noncolin: bool = False
    lspinorb: bool = False
    
    # Additional parameters (catch-all)
    extra_control: Dict[str, Any] = field(default_factory=dict)
    extra_system: Dict[str, Any] = field(default_factory=dict)
    extra_electrons: Dict[str, Any] = field(default_factory=dict)
    extra_ions: Dict[str, Any] = field(default_factory=dict)
    extra_cell: Dict[str, Any] = field(default_factory=dict)


class InputBuilder:
    """
    Builder class for generating QE input files.
    
    Usage:
        builder = InputBuilder()
        
        # Create Silicon SCF input
        pw_input = PWInput(
            calculation="scf",
            ecutwfc=40.0,
            ...
        )
        
        content = builder.build_pw_input(pw_input)
        builder.write_file("si.scf.in", content)
    """
    
    def __init__(self):
        pass
    
    def _format_value(self, value: Any) -> str:
        """Format a Python value for Fortran input."""
        if isinstance(value, bool):
            return ".true." if value else ".false."
        elif isinstance(value, str):
            return f"'{value}'"
        elif isinstance(value, float):
            # Use scientific notation for small values
            if abs(value) < 1e-4 and value != 0:
                return f"{value:.10e}".replace("e", "d")
            return f"{value}"
        elif isinstance(value, int):
            return str(value)
        else:
            return str(value)
    
    def _build_namelist(self, name: str, params: Dict[str, Any]) -> str:
        """Build a namelist block."""
        lines = [f"&{name}"]
        
        for key, value in params.items():
            if value is not None:
                formatted = self._format_value(value)
                lines.append(f"    {key} = {formatted},")
        
        lines.append("/")
        return "\n".join(lines)
    
    def build_pw_input(self, inp: PWInput) -> str:
        """Build a complete pw.x input file."""
        sections = []
        
        # CONTROL namelist
        control = {
            "calculation": inp.calculation,
            "prefix": inp.prefix,
            "outdir": inp.outdir,
            "pseudo_dir": inp.pseudo_dir,
            "verbosity": inp.verbosity,
            "restart_mode": inp.restart_mode,
            "tstress": inp.tstress if inp.tstress else None,
            "tprnfor": inp.tprnfor if inp.tprnfor else None,
            **inp.extra_control,
        }
        # Remove None values
        control = {k: v for k, v in control.items() if v is not None}
        sections.append(self._build_namelist("CONTROL", control))
        
        # SYSTEM namelist
        system = {
            "ibrav": inp.ibrav,
            "nat": inp.nat or len(inp.atoms),
            "ntyp": inp.ntyp or len(inp.species),
            "ecutwfc": inp.ecutwfc,
            "ecutrho": inp.ecutrho,
            "occupations": inp.occupations,
            "smearing": inp.smearing,
            "degauss": inp.degauss,
            "nbnd": inp.nbnd,
            "nspin": inp.nspin if inp.nspin != 1 else None,
            **inp.extra_system,
        }
        
        # Add lattice parameter if ibrav != 0
        if inp.ibrav != 0 and inp.celldm:
            for i, val in enumerate(inp.celldm, 1):
                if val is not None:
                    system[f"celldm({i})"] = val
        elif inp.ibrav != 0 and inp.A:
            system["A"] = inp.A
            
        # Add HSE parameters
        if inp.input_dft:
            system.update({
                "input_dft": inp.input_dft,
                "nqx1": inp.nqx1,
                "nqx2": inp.nqx2,
                "nqx3": inp.nqx3,
                "x_gamma_extrapolation": inp.x_gamma_extrapolation,
                "exx_div_treatment": inp.exx_div_treatment,
            })
        
        # Add Magnetism
        if inp.nspin == 2 or inp.noncolin:
            if inp.noncolin:
                system["noncolin"] = True
                if inp.lspinorb:
                    system["lspinorb"] = True

            for sp, mag in inp.starting_magnetization.items():
                # Find index of species (1-based)
                idx = -1
                for i, s in enumerate(inp.species, 1):
                    if s.symbol == sp:
                        idx = i
                        break
                if idx != -1:
                    system[f"starting_magnetization({idx})"] = mag
        
        # Add DFT+U parameters
        if inp.lda_plus_u:
            system["lda_plus_u"] = True
        
        system = {k: v for k, v in system.items() if v is not None}
        sections.append(self._build_namelist("SYSTEM", system))
        
        # ELECTRONS namelist
        electrons = {
            "conv_thr": inp.conv_thr,
            "mixing_beta": inp.mixing_beta,
            "mixing_mode": inp.mixing_mode,
            "diagonalization": inp.diagonalization,
            "electron_maxstep": inp.electron_maxstep,
            **inp.extra_electrons,
        }
        electrons = {k: v for k, v in electrons.items() if v is not None}
        sections.append(self._build_namelist("ELECTRONS", electrons))
        
        # IONS namelist (if applicable)
        if inp.calculation in ("relax", "md", "vc-relax", "vc-md"):
            ions = {
                "ion_dynamics": inp.ion_dynamics,
                **inp.extra_ions,
            }
            ions = {k: v for k, v in ions.items() if v is not None}
            if ions:
                sections.append(self._build_namelist("IONS", ions))
        
        # CELL namelist (if applicable)
        if inp.calculation in ("vc-relax", "vc-md"):
            cell = {
                "cell_dynamics": inp.cell_dynamics,
                "press": inp.press,
                **inp.extra_cell,
            }
            cell = {k: v for k, v in cell.items() if v is not None}
            if cell:
                sections.append(self._build_namelist("CELL", cell))
        
        # HUBBARD card (new style)
        if inp.lda_plus_u and inp.hubbard_u:
            hubbard_lines = ["HUBBARD (ortho-atomic)"]
            for sp, u_val in inp.hubbard_u.items():
                hubbard_lines.append(f"  U {sp}-3d {u_val}") # Default to 3d for now
            sections.append("\n".join(hubbard_lines))
        
        # ATOMIC_SPECIES card
        species_lines = ["ATOMIC_SPECIES"]
        for sp in inp.species:
            species_lines.append(f"  {sp.symbol}  {sp.mass}  {sp.pseudopotential}")
        sections.append("\n".join(species_lines))
        
        # ATOMIC_POSITIONS card
        pos_lines = [f"ATOMIC_POSITIONS {{{inp.atomic_positions_units}}}"]
        for atom in inp.atoms:
            x, y, z = atom.position
            line = f"  {atom.symbol}  {x:16.10f}  {y:16.10f}  {z:16.10f}"
            if atom.if_pos != (1, 1, 1):
                line += f"  {atom.if_pos[0]} {atom.if_pos[1]} {atom.if_pos[2]}"
            pos_lines.append(line)
        sections.append("\n".join(pos_lines))
        
        # K_POINTS card
        kpts = inp.kpoints
        if kpts.mode == "gamma":
            sections.append("K_POINTS {gamma}")
        elif kpts.mode == "automatic":
            grid = kpts.grid or (1, 1, 1)
            shift = kpts.shift
            sections.append(f"K_POINTS {{automatic}}\n  {grid[0]} {grid[1]} {grid[2]}  {shift[0]} {shift[1]} {shift[2]}")
        elif kpts.mode in ("crystal", "crystal_b", "tpiba_b"):
            lines = [f"K_POINTS {{{kpts.mode}}}"]
            if kpts.points:
                lines.append(f"  {len(kpts.points)}")
                for i, pt in enumerate(kpts.points):
                    x, y, z, w = pt
                    label = kpts.labels[i] if kpts.labels and i < len(kpts.labels) else ""
                    if label:
                        lines.append(f"  {x:10.6f} {y:10.6f} {z:10.6f}  {int(w):3d}  ! {label}")
                    else:
                        lines.append(f"  {x:10.6f} {y:10.6f} {z:10.6f}  {int(w):3d}")
            sections.append("\n".join(lines))
        
        # CELL_PARAMETERS card (if ibrav=0)
        if inp.ibrav == 0 and inp.cell is not None:
            cell_lines = [f"CELL_PARAMETERS {{{inp.cell.units}}}"]
            for i in range(3):
                v = inp.cell.vectors[i]
                cell_lines.append(f"  {v[0]:16.10f}  {v[1]:16.10f}  {v[2]:16.10f}")
            sections.append("\n".join(cell_lines))
        
        return "\n\n".join(sections) + "\n"
    
    def build_bands_input(
        self,
        prefix: str = "pwscf",
        outdir: str = "./",
        filband: str = "bands.out",
        lsym: bool = True,
        spin_component: Optional[int] = None,
    ) -> str:
        """Build a bands.x input file."""
        params = {
            "prefix": prefix,
            "outdir": outdir,
            "filband": filband,
            "lsym": lsym,
        }
        if spin_component is not None:
            params["spin_component"] = spin_component
        
        return self._build_namelist("BANDS", params) + "\n"
    
    def build_dos_input(
        self,
        prefix: str = "pwscf",
        outdir: str = "./",
        fildos: Optional[str] = None,
        Emin: Optional[float] = None,
        Emax: Optional[float] = None,
        DeltaE: float = 0.01,
        ngauss: int = 0,
        degauss: Optional[float] = None,
    ) -> str:
        """Build a dos.x input file."""
        params = {
            "prefix": prefix,
            "outdir": outdir,
            "fildos": fildos or f"{prefix}.dos",
            "Emin": Emin,
            "Emax": Emax,
            "DeltaE": DeltaE,
            "ngauss": ngauss,
            "degauss": degauss,
        }
        params = {k: v for k, v in params.items() if v is not None}
        
        return self._build_namelist("DOS", params) + "\n"
    
    def build_projwfc_input(
        self,
        prefix: str = "pwscf",
        outdir: str = "./",
        filpdos: Optional[str] = None,
        Emin: Optional[float] = None,
        Emax: Optional[float] = None,
        DeltaE: float = 0.01,
        ngauss: int = 0,
        degauss: Optional[float] = None,
    ) -> str:
        """Build a projwfc.x input file."""
        params = {
            "prefix": prefix,
            "outdir": outdir,
            "filpdos": filpdos or f"{prefix}",
            "Emin": Emin,
            "Emax": Emax,
            "DeltaE": DeltaE,
            "ngauss": ngauss,
            "degauss": degauss,
        }
        params = {k: v for k, v in params.items() if v is not None}
        
        return self._build_namelist("PROJWFC", params) + "\n"
    
    def build_ph_input(
        self,
        prefix: str = "pwscf",
        outdir: str = "./",
        fildyn: str = "matdyn",
        ldisp: bool = True,
        nq1: int = 1,
        nq2: int = 1,
        nq3: int = 1,
        tr2_ph: float = 1.0e-12,
        epsil: bool = False, # Dielectric constant
        lraman: bool = False, # Raman cross sections
    ) -> str:
        """
        Build a ph.x input file (Phonons).
        
        Args:
            ldisp (bool): If True, calculate phonon dispersion on a grid (nq1, nq2, nq3).
            epsil (bool): Calculate macroscopic dielectric constant and Born effective charges (q=0 only).
        """
        params = {
            "prefix": prefix,
            "outdir": outdir,
            "fildyn": fildyn,
            "tr2_ph": tr2_ph,
            "ldisp": ldisp,
            "nq1": nq1 if ldisp else None,
            "nq2": nq2 if ldisp else None,
            "nq3": nq3 if ldisp else None,
            "epsil": epsil,
            "lraman": lraman,
        }
        params = {k: v for k, v in params.items() if v is not None}
        
        return self._build_namelist("INPUTPH", params) + "\n"
    
    def write_file(self, filepath: str | Path, content: str) -> None:
        """Write input content to a file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w") as f:
            f.write(content)


def create_silicon_scf_example() -> PWInput:
    """Create an example Silicon SCF calculation input."""
    import numpy as np
    
    # Silicon lattice constant
    a = 5.43  # Angstrom
    
    # FCC conventional cell vectors
    cell_vectors = np.array([
        [a, 0, 0],
        [0, a, 0],
        [0, 0, a],
    ])
    
    # Diamond structure: 8 atoms in conventional cell
    # Or use primitive cell with 2 atoms
    basis_fcc = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.5, 0.5],
        [0.5, 0.0, 0.5],
        [0.5, 0.5, 0.0],
    ])
    
    # Diamond has 2 basis atoms at each FCC site (shift by [0.25, 0.25, 0.25])
    atoms = []
    for base in [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]:
        atoms.append(Atom(symbol="Si", position=tuple(base)))
    
    # Use primitive FCC cell (2 atoms)
    cell_primitive = np.array([
        [0.0, a/2, a/2],
        [a/2, 0.0, a/2],
        [a/2, a/2, 0.0],
    ])
    
    return PWInput(
        calculation="scf",
        prefix="silicon",
        outdir="./tmp",
        pseudo_dir="./pseudo",
        ecutwfc=40.0,
        ecutrho=320.0,
        occupations="fixed",
        ibrav=0,
        cell=CellParameters(vectors=cell_primitive, units="angstrom"),
        species=[AtomicSpecies(symbol="Si", mass=28.0855, pseudopotential="Si.pbe-n-rrkjus_psl.1.0.0.UPF")],
        atoms=atoms,
        atomic_positions_units="crystal",
        kpoints=KPoints(mode="automatic", grid=(8, 8, 8), shift=(0, 0, 0)),
    )
