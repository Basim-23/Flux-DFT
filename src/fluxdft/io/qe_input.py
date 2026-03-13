"""
Quantum ESPRESSO Input Generator for FluxDFT.

Comprehensive input file generator for all pw.x calculation types.
Supports SCF, NSCF, bands, DOS, relax, vc-relax, and more.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class CalculationType(Enum):
    """QE calculation types."""
    SCF = "scf"
    NSCF = "nscf"
    BANDS = "bands"
    RELAX = "relax"
    VC_RELAX = "vc-relax"
    MD = "md"
    VC_MD = "vc-md"


class Occupations(Enum):
    """Occupation types."""
    SMEARING = "smearing"
    TETRAHEDRA = "tetrahedra"
    TETRAHEDRA_LIN = "tetrahedra_lin"
    TETRAHEDRA_OPT = "tetrahedra_opt"
    FIXED = "fixed"
    FROM_INPUT = "from_input"


class SmearingType(Enum):
    """Smearing function types."""
    GAUSSIAN = "gaussian"
    METHFESSEL_PAXTON = "m-p"
    MARZARI_VANDERBILT = "m-v"
    FERMI_DIRAC = "f-d"
    COLD = "cold"


@dataclass
class PseudopotentialSpec:
    """Pseudopotential specification for an element."""
    element: str
    mass: float
    filename: str
    
    def to_qe_line(self) -> str:
        return f"  {self.element}  {self.mass:.4f}  {self.filename}"


@dataclass  
class AtomPosition:
    """Atomic position specification."""
    element: str
    x: float
    y: float
    z: float
    if_pos: Tuple[int, int, int] = (1, 1, 1)  # Constraint flags
    
    def to_qe_line(self, units: str = "crystal") -> str:
        line = f"  {self.element}  {self.x:.10f}  {self.y:.10f}  {self.z:.10f}"
        if self.if_pos != (1, 1, 1):
            line += f"  {self.if_pos[0]}  {self.if_pos[1]}  {self.if_pos[2]}"
        return line


@dataclass
class KPointsGrid:
    """K-points grid specification."""
    nk1: int
    nk2: int
    nk3: int
    sk1: int = 0  # Shift
    sk2: int = 0
    sk3: int = 0
    
    def to_qe_card(self) -> str:
        return f"""K_POINTS automatic
  {self.nk1} {self.nk2} {self.nk3}  {self.sk1} {self.sk2} {self.sk3}"""


@dataclass
class KPointsPath:
    """K-points path for band structure."""
    points: List[Tuple[str, List[float], int]]  # (label, coords, n_points)
    
    def to_qe_card(self) -> str:
        lines = ["K_POINTS {crystal_b}"]
        lines.append(str(len(self.points)))
        for label, coords, npts in self.points:
            lines.append(f"  {coords[0]:.6f}  {coords[1]:.6f}  {coords[2]:.6f}  {npts}  ! {label}")
        return "\n".join(lines)


@dataclass
class QEInputGenerator:
    """
    Complete Quantum ESPRESSO input file generator.
    
    Generates properly formatted input files for pw.x with
    all namelists and cards.
    
    Usage:
        >>> gen = QEInputGenerator.from_structure(structure)
        >>> gen.set_scf_parameters(ecutwfc=60, kgrid=(8, 8, 8))
        >>> input_str = gen.generate()
        >>> gen.write("scf.in")
    """
    
    # CONTROL namelist
    calculation: str = "scf"
    prefix: str = "pwscf"
    outdir: str = "./tmp"
    pseudo_dir: str = "./pseudo"
    verbosity: str = "high"
    tprnfor: bool = True
    tstress: bool = True
    restart_mode: str = "from_scratch"
    nstep: int = 100
    etot_conv_thr: float = 1e-5
    forc_conv_thr: float = 1e-4
    
    # SYSTEM namelist  
    ibrav: int = 0
    nat: int = 0
    ntyp: int = 0
    ecutwfc: float = 40.0
    ecutrho: Optional[float] = None  # Default: 4*ecutwfc for NC, 8*ecutwfc for US
    
    occupations: str = "smearing"
    smearing: str = "cold"
    degauss: float = 0.02
    
    nspin: int = 1
    starting_magnetization: Dict[str, float] = field(default_factory=dict)
    
    nbnd: Optional[int] = None
    tot_charge: float = 0.0
    
    input_dft: Optional[str] = None  # Override XC functional
    vdw_corr: Optional[str] = None  # 'grimme-d2', 'grimme-d3', etc.
    
    lda_plus_u: bool = False
    Hubbard_U: Dict[str, float] = field(default_factory=dict)
    
    noncolin: bool = False
    lspinorb: bool = False
    
    nosym: bool = False
    noinv: bool = False
    
    # ELECTRONS namelist
    electron_maxstep: int = 100
    conv_thr: float = 1e-8
    mixing_mode: str = "plain"
    mixing_beta: float = 0.7
    mixing_ndim: int = 8
    diagonalization: str = "david"
    diago_thr_init: Optional[float] = None
    startingpot: str = "atomic"
    startingwfc: str = "atomic+random"
    
    # IONS namelist
    ion_dynamics: str = "bfgs"
    upscale: float = 100.0
    bfgs_ndim: int = 1
    trust_radius_min: float = 1e-3
    trust_radius_max: float = 0.8
    trust_radius_ini: float = 0.5
    
    # CELL namelist
    cell_dynamics: str = "bfgs"
    press: float = 0.0
    cell_factor: float = 2.0
    cell_dofree: str = "all"
    press_conv_thr: float = 0.5
    
    # Atomic data
    pseudopotentials: List[PseudopotentialSpec] = field(default_factory=list)
    atomic_positions: List[AtomPosition] = field(default_factory=list)
    atomic_positions_units: str = "crystal"
    
    # Cell parameters
    cell_parameters: Optional[np.ndarray] = None  # 3x3 matrix in Angstrom
    cell_parameters_units: str = "angstrom"
    
    # K-points
    kpoints: Union[KPointsGrid, KPointsPath, None] = None
    
    @classmethod
    def from_structure(
        cls,
        structure: 'Structure',
        pseudo_dir: str = "./pseudo",
        pseudo_family: str = "SSSP_efficiency",
    ) -> 'QEInputGenerator':
        """
        Create input generator from pymatgen Structure.
        
        Args:
            structure: pymatgen Structure object
            pseudo_dir: Path to pseudopotential directory
            pseudo_family: Pseudopotential family to use
            
        Returns:
            Configured QEInputGenerator
        """
        gen = cls()
        gen.pseudo_dir = pseudo_dir
        
        # Set cell
        gen.cell_parameters = structure.lattice.matrix.copy()
        gen.nat = len(structure)
        gen.ntyp = len(structure.types_of_species)
        
        # Set atomic positions
        for site in structure:
            pos = AtomPosition(
                element=str(site.specie),
                x=site.frac_coords[0],
                y=site.frac_coords[1],
                z=site.frac_coords[2],
            )
            gen.atomic_positions.append(pos)
        
        # Set pseudopotentials
        for species in structure.types_of_species:
            element = str(species)
            pp = PseudopotentialSpec(
                element=element,
                mass=species.atomic_mass,
                filename=cls._get_pp_filename(element, pseudo_family),
            )
            gen.pseudopotentials.append(pp)
        
        # Set prefix from formula
        gen.prefix = structure.composition.reduced_formula.replace(" ", "")
        
        return gen
    
    @staticmethod
    def _get_pp_filename(element: str, family: str = "SSSP_efficiency") -> str:
        """Get pseudopotential filename for element."""
        # Common PP naming conventions
        pp_templates = {
            "SSSP_efficiency": f"{element}.pbe-n-kjpaw_psl.1.0.0.UPF",
            "SSSP_precision": f"{element}.pbe-n-rrkjus_psl.1.0.0.UPF",
            "pslibrary": f"{element}.pbe-n-kjpaw_psl.1.0.0.UPF",
            "sg15": f"{element}_ONCV_PBE-1.2.upf",
            "gbrv": f"{element.lower()}_pbe_v1.uspp.F.UPF",
        }
        return pp_templates.get(family, f"{element}.UPF")
    
    def set_scf_parameters(
        self,
        ecutwfc: float = 60.0,
        kgrid: Tuple[int, int, int] = (8, 8, 8),
        conv_thr: float = 1e-8,
        smearing: str = "cold",
        degauss: float = 0.02,
    ) -> 'QEInputGenerator':
        """Configure for SCF calculation."""
        self.calculation = "scf"
        self.ecutwfc = ecutwfc
        self.conv_thr = conv_thr
        self.smearing = smearing
        self.degauss = degauss
        self.kpoints = KPointsGrid(*kgrid, 1, 1, 1)
        return self
    
    def set_bands_parameters(
        self,
        kpath: List[Tuple[str, List[float], int]],
        nbnd: Optional[int] = None,
    ) -> 'QEInputGenerator':
        """Configure for bands calculation."""
        self.calculation = "bands"
        self.kpoints = KPointsPath(kpath)
        if nbnd:
            self.nbnd = nbnd
        return self
    
    def set_nscf_parameters(
        self,
        kgrid: Tuple[int, int, int] = (16, 16, 16),
        nbnd: Optional[int] = None,
    ) -> 'QEInputGenerator':
        """Configure for NSCF calculation (for DOS)."""
        self.calculation = "nscf"
        self.kpoints = KPointsGrid(*kgrid, 0, 0, 0)
        self.nosym = True
        if nbnd:
            self.nbnd = nbnd
        return self
    
    def set_relaxation_parameters(
        self,
        variable_cell: bool = False,
        forc_conv_thr: float = 1e-4,
        press_conv_thr: float = 0.5,
    ) -> 'QEInputGenerator':
        """Configure for structural relaxation."""
        self.calculation = "vc-relax" if variable_cell else "relax"
        self.forc_conv_thr = forc_conv_thr
        self.press_conv_thr = press_conv_thr
        return self
    
    def set_spin_polarized(
        self,
        starting_magnetization: Dict[str, float],
    ) -> 'QEInputGenerator':
        """Enable spin-polarized calculation."""
        self.nspin = 2
        self.starting_magnetization = starting_magnetization
        return self
    
    def set_hubbard_u(
        self,
        hubbard_u: Dict[str, float],
    ) -> 'QEInputGenerator':
        """Enable DFT+U."""
        self.lda_plus_u = True
        self.Hubbard_U = hubbard_u
        return self
    
    def generate(self) -> str:
        """
        Generate complete QE input file string.
        
        Returns:
            Formatted input file content
        """
        sections = []
        
        # CONTROL namelist
        sections.append(self._generate_control())
        
        # SYSTEM namelist
        sections.append(self._generate_system())
        
        # ELECTRONS namelist
        sections.append(self._generate_electrons())
        
        # IONS namelist (for relax/md)
        if self.calculation in ['relax', 'vc-relax', 'md', 'vc-md']:
            sections.append(self._generate_ions())
        
        # CELL namelist (for vc-relax/vc-md)
        if self.calculation in ['vc-relax', 'vc-md']:
            sections.append(self._generate_cell())
        
        # ATOMIC_SPECIES card
        sections.append(self._generate_atomic_species())
        
        # ATOMIC_POSITIONS card
        sections.append(self._generate_atomic_positions())
        
        # K_POINTS card
        if self.kpoints:
            sections.append(self._generate_kpoints())
        
        # CELL_PARAMETERS card
        if self.cell_parameters is not None:
            sections.append(self._generate_cell_parameters())
        
        return "\n\n".join(sections) + "\n"
    
    def _generate_control(self) -> str:
        """Generate CONTROL namelist."""
        lines = ["&CONTROL"]
        lines.append(f"  calculation = '{self.calculation}'")
        lines.append(f"  prefix = '{self.prefix}'")
        lines.append(f"  outdir = '{self.outdir}'")
        lines.append(f"  pseudo_dir = '{self.pseudo_dir}'")
        lines.append(f"  verbosity = '{self.verbosity}'")
        
        if self.calculation in ['relax', 'vc-relax', 'md', 'vc-md']:
            lines.append(f"  nstep = {self.nstep}")
            lines.append(f"  etot_conv_thr = {self.etot_conv_thr:.1e}")
            lines.append(f"  forc_conv_thr = {self.forc_conv_thr:.1e}")
        
        if self.tprnfor:
            lines.append("  tprnfor = .true.")
        if self.tstress:
            lines.append("  tstress = .true.")
        
        lines.append("/")
        return "\n".join(lines)
    
    def _generate_system(self) -> str:
        """Generate SYSTEM namelist."""
        lines = ["&SYSTEM"]
        lines.append(f"  ibrav = {self.ibrav}")
        lines.append(f"  nat = {self.nat}")
        lines.append(f"  ntyp = {self.ntyp}")
        lines.append(f"  ecutwfc = {self.ecutwfc}")
        
        if self.ecutrho:
            lines.append(f"  ecutrho = {self.ecutrho}")
        
        lines.append(f"  occupations = '{self.occupations}'")
        
        if self.occupations == "smearing":
            lines.append(f"  smearing = '{self.smearing}'")
            lines.append(f"  degauss = {self.degauss}")
        
        if self.nspin == 2:
            lines.append(f"  nspin = {self.nspin}")
            for elem, mag in self.starting_magnetization.items():
                # Find species index
                for i, pp in enumerate(self.pseudopotentials):
                    if pp.element == elem:
                        lines.append(f"  starting_magnetization({i+1}) = {mag}")
                        break
        
        if self.nbnd:
            lines.append(f"  nbnd = {self.nbnd}")
        
        if self.tot_charge != 0.0:
            lines.append(f"  tot_charge = {self.tot_charge}")
        
        if self.input_dft:
            lines.append(f"  input_dft = '{self.input_dft}'")
        
        if self.vdw_corr:
            lines.append(f"  vdw_corr = '{self.vdw_corr}'")
        
        if self.lda_plus_u:
            lines.append("  lda_plus_u = .true.")
            for elem, u_val in self.Hubbard_U.items():
                for i, pp in enumerate(self.pseudopotentials):
                    if pp.element == elem:
                        lines.append(f"  Hubbard_U({i+1}) = {u_val}")
                        break
        
        if self.nosym:
            lines.append("  nosym = .true.")
        if self.noinv:
            lines.append("  noinv = .true.")
        
        if self.noncolin:
            lines.append("  noncolin = .true.")
        if self.lspinorb:
            lines.append("  lspinorb = .true.")
        
        lines.append("/")
        return "\n".join(lines)
    
    def _generate_electrons(self) -> str:
        """Generate ELECTRONS namelist."""
        lines = ["&ELECTRONS"]
        lines.append(f"  electron_maxstep = {self.electron_maxstep}")
        lines.append(f"  conv_thr = {self.conv_thr:.1e}")
        lines.append(f"  mixing_mode = '{self.mixing_mode}'")
        lines.append(f"  mixing_beta = {self.mixing_beta}")
        lines.append(f"  mixing_ndim = {self.mixing_ndim}")
        lines.append(f"  diagonalization = '{self.diagonalization}'")
        lines.append(f"  startingpot = '{self.startingpot}'")
        lines.append(f"  startingwfc = '{self.startingwfc}'")
        
        if self.diago_thr_init:
            lines.append(f"  diago_thr_init = {self.diago_thr_init:.1e}")
        
        lines.append("/")
        return "\n".join(lines)
    
    def _generate_ions(self) -> str:
        """Generate IONS namelist."""
        lines = ["&IONS"]
        lines.append(f"  ion_dynamics = '{self.ion_dynamics}'")
        
        if self.ion_dynamics == "bfgs":
            lines.append(f"  upscale = {self.upscale}")
            lines.append(f"  bfgs_ndim = {self.bfgs_ndim}")
            lines.append(f"  trust_radius_min = {self.trust_radius_min}")
            lines.append(f"  trust_radius_max = {self.trust_radius_max}")
            lines.append(f"  trust_radius_ini = {self.trust_radius_ini}")
        
        lines.append("/")
        return "\n".join(lines)
    
    def _generate_cell(self) -> str:
        """Generate CELL namelist."""
        lines = ["&CELL"]
        lines.append(f"  cell_dynamics = '{self.cell_dynamics}'")
        lines.append(f"  press = {self.press}")
        lines.append(f"  cell_factor = {self.cell_factor}")
        lines.append(f"  cell_dofree = '{self.cell_dofree}'")
        lines.append(f"  press_conv_thr = {self.press_conv_thr}")
        lines.append("/")
        return "\n".join(lines)
    
    def _generate_atomic_species(self) -> str:
        """Generate ATOMIC_SPECIES card."""
        lines = ["ATOMIC_SPECIES"]
        for pp in self.pseudopotentials:
            lines.append(pp.to_qe_line())
        return "\n".join(lines)
    
    def _generate_atomic_positions(self) -> str:
        """Generate ATOMIC_POSITIONS card."""
        lines = [f"ATOMIC_POSITIONS {{{self.atomic_positions_units}}}"]
        for pos in self.atomic_positions:
            lines.append(pos.to_qe_line(self.atomic_positions_units))
        return "\n".join(lines)
    
    def _generate_kpoints(self) -> str:
        """Generate K_POINTS card."""
        if isinstance(self.kpoints, KPointsGrid):
            return self.kpoints.to_qe_card()
        elif isinstance(self.kpoints, KPointsPath):
            return self.kpoints.to_qe_card()
        return ""
    
    def _generate_cell_parameters(self) -> str:
        """Generate CELL_PARAMETERS card."""
        lines = [f"CELL_PARAMETERS {{{self.cell_parameters_units}}}"]
        for row in self.cell_parameters:
            lines.append(f"  {row[0]:.10f}  {row[1]:.10f}  {row[2]:.10f}")
        return "\n".join(lines)
    
    def write(self, filepath: Union[str, Path]) -> None:
        """Write input to file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            f.write(self.generate())
        
        logger.info(f"Input written to {filepath}")
    
    def validate(self) -> List[str]:
        """
        Validate input parameters.
        
        Returns:
            List of warning/error messages
        """
        issues = []
        
        if self.nat == 0:
            issues.append("ERROR: nat (number of atoms) is 0")
        
        if self.ntyp == 0:
            issues.append("ERROR: ntyp (number of species) is 0")
        
        if len(self.pseudopotentials) != self.ntyp:
            issues.append(f"WARNING: {len(self.pseudopotentials)} pseudopotentials for {self.ntyp} species")
        
        if len(self.atomic_positions) != self.nat:
            issues.append(f"WARNING: {len(self.atomic_positions)} positions for {self.nat} atoms")
        
        if self.ecutwfc < 20:
            issues.append(f"WARNING: ecutwfc={self.ecutwfc} Ry seems too low")
        
        if self.kpoints is None:
            issues.append("WARNING: No k-points specified")
        
        if self.calculation == "bands" and not isinstance(self.kpoints, KPointsPath):
            issues.append("WARNING: bands calculation should use k-point path")
        
        if self.nspin == 2 and not self.starting_magnetization:
            issues.append("WARNING: Spin-polarized but no starting magnetization")
        
        return issues


def generate_scf_input(
    structure: 'Structure',
    ecutwfc: float = 60.0,
    kgrid: Tuple[int, int, int] = (8, 8, 8),
    **kwargs,
) -> str:
    """
    Quick SCF input generation.
    
    Args:
        structure: pymatgen Structure
        ecutwfc: Wavefunction cutoff in Ry
        kgrid: K-point grid
        **kwargs: Additional parameters
        
    Returns:
        Input file string
    """
    gen = QEInputGenerator.from_structure(structure)
    gen.set_scf_parameters(ecutwfc=ecutwfc, kgrid=kgrid)
    
    for key, value in kwargs.items():
        if hasattr(gen, key):
            setattr(gen, key, value)
    
    return gen.generate()


def generate_bands_input(
    structure: 'Structure',
    kpath: List[Tuple[str, List[float], int]],
    ecutwfc: float = 60.0,
    **kwargs,
) -> str:
    """
    Quick bands input generation.
    
    Args:
        structure: pymatgen Structure
        kpath: K-point path
        ecutwfc: Wavefunction cutoff in Ry
        **kwargs: Additional parameters
        
    Returns:
        Input file string
    """
    gen = QEInputGenerator.from_structure(structure)
    gen.ecutwfc = ecutwfc
    gen.set_bands_parameters(kpath)
    
    for key, value in kwargs.items():
        if hasattr(gen, key):
            setattr(gen, key, value)
    
    return gen.generate()


def generate_relax_input(
    structure: 'Structure',
    ecutwfc: float = 60.0,
    kgrid: Tuple[int, int, int] = (6, 6, 6),
    variable_cell: bool = False,
    **kwargs,
) -> str:
    """
    Quick relaxation input generation.
    
    Args:
        structure: pymatgen Structure
        ecutwfc: Wavefunction cutoff in Ry
        kgrid: K-point grid
        variable_cell: Whether to optimize cell
        **kwargs: Additional parameters
        
    Returns:
        Input file string
    """
    gen = QEInputGenerator.from_structure(structure)
    gen.ecutwfc = ecutwfc
    gen.kpoints = KPointsGrid(*kgrid, 0, 0, 0)
    gen.set_relaxation_parameters(variable_cell=variable_cell)
    
    for key, value in kwargs.items():
        if hasattr(gen, key):
            setattr(gen, key, value)
    
    return gen.generate()
