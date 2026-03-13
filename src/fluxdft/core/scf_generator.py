"""
Scientific SCF Input Generator for Quantum ESPRESSO.

Publication-grade, material-agnostic SCF input generation with:
- Automatic DFT+U for d/f orbital elements
- Magnetism detection and initialization
- Adaptive SCF stabilizers
- Metal/insulator smearing logic
- Energy cutoff validation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# ELEMENT CLASSIFICATION
# =============================================================================

# 3d transition metals (need DFT+U for localized d orbitals)
ELEMENTS_3D = {'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn'}

# 4d transition metals (usually don't need U, more delocalized)
ELEMENTS_4D = {'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd'}

# 5d transition metals (usually don't need U, even more delocalized)
ELEMENTS_5D = {'La', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg'}

# 4f lanthanides (definitely need DFT+U)
ELEMENTS_4F = {'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu'}

# 5f actinides (definitely need DFT+U)
ELEMENTS_5F = {'Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr'}

# Metals (simple metals that are definitely metallic)
SIMPLE_METALS = {'Li', 'Na', 'K', 'Rb', 'Cs', 'Be', 'Mg', 'Ca', 'Sr', 'Ba', 'Al', 'Ga', 'In', 'Tl', 'Sn', 'Pb', 'Bi'}

# Noble gases and clear insulators
INSULATORS = {'He', 'Ne', 'Ar', 'Kr', 'Xe', 'F', 'Cl', 'Br', 'I'}

# Default Hubbard U values (eV) from literature
# Conservative values suitable for most calculations
DEFAULT_HUBBARD_U: Dict[str, float] = {
    # 3d transition metals
    'Ti': 3.0, 'V': 3.0, 'Cr': 3.5, 'Mn': 4.0, 'Fe': 4.0, 'Co': 3.5, 'Ni': 5.0, 'Cu': 4.0,
    # 4f lanthanides
    'Ce': 4.5, 'Pr': 5.0, 'Nd': 5.0, 'Sm': 5.0, 'Eu': 6.0, 'Gd': 6.0, 'Tb': 5.5, 'Dy': 5.5,
    # 5f actinides
    'U': 4.0, 'Np': 4.0, 'Pu': 4.0,
}

# Starting magnetization values for magnetic elements
DEFAULT_MAGNETIZATION: Dict[str, float] = {
    'Cr': 0.3, 'Mn': 0.4, 'Fe': 0.5, 'Co': 0.4, 'Ni': 0.3,
    'Ce': 0.2, 'Pr': 0.2, 'Nd': 0.3, 'Sm': 0.3, 'Eu': 0.5, 'Gd': 0.5,
    'U': 0.3, 'Np': 0.3, 'Pu': 0.3,
}


def classify_element(symbol: str) -> str:
    """
    Classify element by orbital type.
    
    Returns:
        '3d', '4d', '5d', '4f', '5f', 'metal', 'insulator', or 'other'
    """
    if symbol in ELEMENTS_3D:
        return '3d'
    elif symbol in ELEMENTS_4D:
        return '4d'
    elif symbol in ELEMENTS_5D:
        return '5d'
    elif symbol in ELEMENTS_4F:
        return '4f'
    elif symbol in ELEMENTS_5F:
        return '5f'
    elif symbol in SIMPLE_METALS:
        return 'metal'
    elif symbol in INSULATORS:
        return 'insulator'
    return 'other'


def needs_hubbard_u(elements: List[str]) -> List[str]:
    """
    Determine which elements need DFT+U treatment.
    
    Only 3d and 4f/5f elements get Hubbard U.
    4d/5d elements are too delocalized and don't need U by default.
    """
    u_elements = []
    for el in elements:
        el_type = classify_element(el)
        if el_type in ('3d', '4f', '5f'):
            u_elements.append(el)
    return u_elements


def get_hubbard_u_values(elements: List[str], user_overrides: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """
    Get Hubbard U values for all elements.
    
    Returns a dict mapping element symbol to U value.
    Elements not needing U get 0.0.
    """
    user_overrides = user_overrides or {}
    u_values = {}
    
    for el in elements:
        if el in user_overrides:
            u_values[el] = user_overrides[el]
        elif el in DEFAULT_HUBBARD_U:
            u_values[el] = DEFAULT_HUBBARD_U[el]
        else:
            # Non-DFT+U elements get 0.0 (they won't appear in output if lda_plus_u is off anyway)
            u_values[el] = 0.0
    
    return u_values


def is_magnetic_system(elements: List[str]) -> bool:
    """
    Detect if system likely has magnetic ordering.
    
    Returns True if any element has partially filled d or f shells
    that could lead to magnetic moments.
    """
    magnetic_elements = set(DEFAULT_MAGNETIZATION.keys())
    return any(el in magnetic_elements for el in elements)


def get_starting_magnetization(
    elements: List[str], 
    user_overrides: Optional[Dict[str, float]] = None,
    mode: str = 'ferromagnetic'
) -> Dict[str, float]:
    """
    Get starting magnetization values for spin-polarized calculation.
    
    Args:
        elements: List of element symbols
        user_overrides: User-provided values
        mode: 'ferromagnetic' (all positive) or 'antiferromagnetic' (alternating)
    
    Returns:
        Dict mapping element symbol to starting_magnetization value
    """
    user_overrides = user_overrides or {}
    mag_values = {}
    
    afm_sign = 1
    for el in elements:
        if el in user_overrides:
            mag_values[el] = user_overrides[el]
        elif el in DEFAULT_MAGNETIZATION:
            val = DEFAULT_MAGNETIZATION[el]
            if mode == 'antiferromagnetic':
                val *= afm_sign
                afm_sign *= -1  # Alternate signs
            mag_values[el] = val
        # Non-magnetic elements don't need starting_magnetization
    
    return mag_values


def is_metallic_heuristic(elements: List[str]) -> bool:
    """
    Heuristic to detect if system is likely metallic.
    
    Returns True if:
    - Contains simple metals (alkali, alkaline earth, Al, etc.)
    - Contains transition metals (likely metallic unless oxide)
    - Does NOT contain only clear insulators
    """
    has_metal = any(el in SIMPLE_METALS for el in elements)
    has_transition = any(el in (ELEMENTS_3D | ELEMENTS_4D | ELEMENTS_5D) for el in elements)
    all_insulator = all(el in INSULATORS for el in elements)
    
    # If it has metals or transition metals and isn't purely insulating
    if all_insulator:
        return False
    
    # More nuanced: oxides of transition metals are often insulators
    has_oxygen = 'O' in elements
    has_only_tm_and_o = all(el in (ELEMENTS_3D | ELEMENTS_4D | ELEMENTS_5D | {'O'}) for el in elements)
    if has_only_tm_and_o and has_oxygen:
        # Transition metal oxide - likely insulator or small gap
        return False
    
    return has_metal or has_transition


def get_adaptive_mixing(n_atoms: int, has_correlated: bool) -> float:
    """
    Get adaptive mixing_beta based on system size and correlation.
    
    Small systems: 0.4 (faster convergence)
    Large systems: 0.2 (more stable)
    Correlated (DFT+U): reduce by 0.1
    """
    if n_atoms < 10:
        beta = 0.4
    elif n_atoms < 50:
        beta = 0.3
    else:
        beta = 0.2
    
    if has_correlated:
        beta = max(0.1, beta - 0.1)
    
    return beta


def get_adaptive_conv_thr(n_atoms: int, is_magnetic: bool) -> float:
    """
    Get adaptive convergence threshold.
    
    Base: 1.0e-8 per atom
    Magnetic systems: tighter (1.0e-9)
    """
    base = 1.0e-8
    
    if is_magnetic:
        base = 1.0e-9
    
    # Scale with number of atoms
    return base * max(1, n_atoms // 10)


@dataclass
class SCFConfig:
    """Configuration for SCF calculation with all parameters."""
    
    # Energy cutoffs
    ecutwfc: float = 50.0
    ecutrho: float = 400.0  # Will be enforced as 8x ecutwfc
    
    # SCF convergence
    conv_thr: float = 1.0e-8
    mixing_beta: float = 0.3
    electron_maxstep: int = 150
    
    # Occupations
    occupations: str = 'smearing'  # 'smearing' or 'fixed'
    smearing: str = 'cold'  # 'cold', 'gaussian', 'mp', 'mv', 'fd'
    degauss: float = 0.01  # Ry
    
    # Spin polarization
    nspin: int = 1  # 1 = unpolarized, 2 = spin-polarized
    starting_magnetization: Dict[str, float] = field(default_factory=dict)
    
    # DFT+U
    lda_plus_u: bool = False
    lda_plus_u_kind: int = 0  # 0 = Dudarev (simplified)
    hubbard_u: Dict[str, float] = field(default_factory=dict)
    
    # Validation
    warnings: List[str] = field(default_factory=list)


def generate_scf_config(
    elements: List[str],
    n_atoms: int,
    ecutwfc: float = 50.0,
    user_overrides: Optional[Dict[str, Any]] = None
) -> SCFConfig:
    """
    Generate publication-grade SCF configuration for any material.
    
    Args:
        elements: List of unique element symbols in the structure
        n_atoms: Total number of atoms
        ecutwfc: Wavefunction cutoff (Ry)
        user_overrides: Dict of user-provided parameter overrides
    
    Returns:
        SCFConfig with all parameters set
    """
    user_overrides = user_overrides or {}
    config = SCFConfig()
    warnings = []
    
    # === Energy Cutoffs ===
    config.ecutwfc = user_overrides.get('ecutwfc', ecutwfc)
    config.ecutrho = max(8 * config.ecutwfc, user_overrides.get('ecutrho', 8 * config.ecutwfc))
    
    if 'ecutrho' in user_overrides and user_overrides['ecutrho'] < 8 * config.ecutwfc:
        warnings.append(f"⚠️ ecutrho ({user_overrides['ecutrho']}) < 8×ecutwfc ({8*config.ecutwfc}) - auto-corrected")
    
    # === DFT+U ===
    u_elements = needs_hubbard_u(elements)
    if u_elements:
        config.lda_plus_u = True
        config.lda_plus_u_kind = 0  # Dudarev
        config.hubbard_u = get_hubbard_u_values(elements, user_overrides.get('hubbard_u'))
        logger.info(f"DFT+U enabled for: {u_elements}")
    
    # === Magnetism ===
    if is_magnetic_system(elements):
        config.nspin = 2
        config.starting_magnetization = get_starting_magnetization(
            elements, 
            user_overrides.get('starting_magnetization'),
            mode=user_overrides.get('magnetic_mode', 'ferromagnetic')
        )
        logger.info(f"Spin-polarized calculation enabled (nspin=2)")
    
    # === Smearing ===
    if is_metallic_heuristic(elements):
        config.occupations = 'smearing'
        config.smearing = 'cold'  # Marzari-Vanderbilt cold smearing
        config.degauss = 0.01
    else:
        # Insulator - use fixed occupations or small smearing for stability
        config.occupations = 'smearing'
        config.smearing = 'gaussian'
        config.degauss = 0.005  # Very small smearing
    
    # === Adaptive SCF Stabilizers ===
    has_correlated = len(u_elements) > 0
    config.mixing_beta = get_adaptive_mixing(n_atoms, has_correlated)
    config.conv_thr = get_adaptive_conv_thr(n_atoms, config.nspin == 2)
    config.electron_maxstep = 150 if n_atoms < 100 else 200
    
    # === Apply user overrides ===
    for key in ['conv_thr', 'mixing_beta', 'electron_maxstep', 'occupations', 'smearing', 'degauss', 'nspin']:
        if key in user_overrides:
            setattr(config, key, user_overrides[key])
    
    config.warnings = warnings
    return config


def generate_scf_input_text(
    structure_data: Dict[str, Any],
    config: SCFConfig,
    calculation: str = 'scf',
    prefix: str = 'pwscf',
    pseudo_dir: str = './pseudo',
    outdir: str = './tmp'
) -> str:
    """
    Generate complete QE input file text from structure data and config.
    
    Args:
        structure_data: Dict with 'atomic_species', 'atomic_positions', 'cell_parameters', 'system_params'
        config: SCFConfig object
        calculation: 'scf', 'relax', 'vc-relax', etc.
        prefix: Job prefix
        pseudo_dir: Pseudopotential directory
        outdir: Output directory
    
    Returns:
        Complete QE input file as string
    """
    nat = structure_data['system_params']['nat']
    ntyp = structure_data['system_params']['ntyp']
    
    lines = []
    
    # === CONTROL ===
    lines.append("&CONTROL")
    lines.append(f"  calculation = '{calculation}'")
    lines.append(f"  prefix = '{prefix}'")
    lines.append(f"  pseudo_dir = '{pseudo_dir}'")
    lines.append(f"  outdir = '{outdir}'")
    lines.append(f"  verbosity = 'high'")
    if calculation in ('relax', 'vc-relax'):
        lines.append(f"  tprnfor = .true.")
        lines.append(f"  tstress = .true.")
    lines.append("/")
    lines.append("")
    
    # === SYSTEM ===
    lines.append("&SYSTEM")
    lines.append(f"  ibrav = 0")
    lines.append(f"  nat = {nat}")
    lines.append(f"  ntyp = {ntyp}")
    lines.append(f"  ecutwfc = {config.ecutwfc}")
    lines.append(f"  ecutrho = {config.ecutrho}")
    
    # Spin polarization
    if config.nspin == 2:
        lines.append(f"  nspin = 2")
        for i, (el, mag) in enumerate(config.starting_magnetization.items(), 1):
            if mag != 0:
                lines.append(f"  starting_magnetization({i}) = {mag}")
    
    # Occupations & Smearing
    lines.append(f"  occupations = '{config.occupations}'")
    if config.occupations == 'smearing':
        lines.append(f"  smearing = '{config.smearing}'")
        lines.append(f"  degauss = {config.degauss}")
    
    # DFT+U
    if config.lda_plus_u:
        lines.append(f"  lda_plus_u = .true.")
        lines.append(f"  lda_plus_u_kind = {config.lda_plus_u_kind}")
        for i, (el, u) in enumerate(config.hubbard_u.items(), 1):
            if u > 0:
                lines.append(f"  Hubbard_U({i}) = {u}")
    
    lines.append("/")
    lines.append("")
    
    # === ELECTRONS ===
    lines.append("&ELECTRONS")
    lines.append(f"  conv_thr = {config.conv_thr:.1e}")
    lines.append(f"  mixing_beta = {config.mixing_beta}")
    lines.append(f"  electron_maxstep = {config.electron_maxstep}")
    lines.append("/")
    lines.append("")
    
    # === IONS (for relax) ===
    if calculation in ('relax', 'vc-relax'):
        lines.append("&IONS")
        lines.append("  ion_dynamics = 'bfgs'")
        lines.append("/")
        lines.append("")
    
    # === CELL (for vc-relax) ===
    if calculation == 'vc-relax':
        lines.append("&CELL")
        lines.append("  cell_dynamics = 'bfgs'")
        lines.append("/")
        lines.append("")
    
    # === Cards ===
    lines.append(structure_data['atomic_species'])
    lines.append("")
    lines.append(structure_data['atomic_positions'])
    lines.append("")
    lines.append(structure_data['cell_parameters'])
    lines.append("")
    lines.append("K_POINTS automatic")
    lines.append("4 4 4  0 0 0")
    
    return "\n".join(lines)


def analyze_structure_for_scf(elements: List[str], n_atoms: int) -> Dict[str, Any]:
    """
    Analyze structure and return analysis summary for UI display.
    
    Returns dict with:
    - requires_dft_u: bool
    - dft_u_elements: list
    - is_magnetic: bool
    - magnetic_elements: list
    - is_metallic: bool
    - recommended_ecutwfc: float
    - warnings: list
    """
    u_elements = needs_hubbard_u(elements)
    magnetic = is_magnetic_system(elements)
    metallic = is_metallic_heuristic(elements)
    
    # Recommend ecutwfc based on elements
    recommended_ecut = 50.0
    if any(el in ELEMENTS_3D for el in elements):
        recommended_ecut = 60.0  # TM need higher cutoff
    if any(el in (ELEMENTS_4F | ELEMENTS_5F) for el in elements):
        recommended_ecut = 80.0  # f-elements need even higher
    
    return {
        'requires_dft_u': len(u_elements) > 0,
        'dft_u_elements': u_elements,
        'hubbard_u_values': get_hubbard_u_values(elements),
        'is_magnetic': magnetic,
        'magnetic_elements': [el for el in elements if el in DEFAULT_MAGNETIZATION],
        'is_metallic': metallic,
        'recommended_ecutwfc': recommended_ecut,
        'element_types': {el: classify_element(el) for el in elements},
        'n_atoms': n_atoms,
        'warnings': [],
    }
