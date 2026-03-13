"""
Constants and configuration values for FluxDFT.
"""

from pathlib import Path

# Application info
APP_NAME = "FluxDFT"
APP_VERSION = "2.0.0"
APP_AUTHOR = "Basim Nasser"
APP_COPYRIGHT = "© 2026 Basim Nasser. MIT License."
APP_WEBSITE = "https://github.com/Basim-23/Flux-DFT"
APP_SUPPORT_EMAIL = ""

# Default paths
DEFAULT_QE_PATH = Path("/usr/local/bin")
DEFAULT_PSEUDO_PATH = Path.home() / "espresso" / "pseudo"
DEFAULT_WORK_DIR = Path.home() / "FluxDFT" / "projects"

# Supported Quantum ESPRESSO executables
QE_EXECUTABLES = {
    "pw.x": "Plane-wave self-consistent field (SCF, bands, relax, MD)",
    "ph.x": "Phonon calculations",
    "bands.x": "Band structure post-processing",
    "dos.x": "Density of states",
    "projwfc.x": "Projected density of states (PDOS)",
    "pp.x": "Post-processing (charge density, potentials)",
    "plotband.x": "Band structure plotting",
    "matdyn.x": "Phonon interpolation",
    "q2r.x": "Fourier transform of dynamical matrices",
    "dynmat.x": "Dynamical matrix analysis",
}

# Calculation types for pw.x
CALCULATION_TYPES = {
    "scf": "Self-consistent field calculation",
    "nscf": "Non-self-consistent field calculation",
    "bands": "Band structure calculation",
    "relax": "Atomic position relaxation",
    "vc-relax": "Variable-cell relaxation",
    "md": "Molecular dynamics",
    "vc-md": "Variable-cell molecular dynamics",
}

# Bravais lattice types
BRAVAIS_LATTICES = {
    0: "Free (user-specified)",
    1: "Cubic P (simple cubic)",
    2: "Cubic F (face-centered cubic)",
    3: "Cubic I (body-centered cubic)",
    4: "Hexagonal",
    5: "Trigonal R (3-fold axis c)",
    6: "Tetragonal P",
    7: "Tetragonal I",
    8: "Orthorhombic P",
    9: "Orthorhombic base-centered",
    10: "Orthorhombic face-centered",
    11: "Orthorhombic body-centered",
    12: "Monoclinic P (unique axis c)",
    13: "Monoclinic base-centered",
    14: "Triclinic",
}

# K-points options
KPOINTS_OPTIONS = {
    "automatic": "Monkhorst-Pack grid",
    "gamma": "Gamma point only",
    "crystal": "Explicit k-points (crystal coordinates)",
    "crystal_b": "Band structure path (crystal coordinates)",
    "tpiba_b": "Band structure path (2π/a units)",
}

# Atomic positions units
ATOMIC_POSITIONS_UNITS = {
    "alat": "Units of lattice parameter a",
    "bohr": "Bohr radii (atomic units)",
    "angstrom": "Angstroms",
    "crystal": "Crystal coordinates",
}

# Occupations types
OCCUPATIONS_TYPES = {
    "fixed": "Fixed occupations (insulators)",
    "smearing": "Smearing (metals)",
    "tetrahedra": "Tetrahedron method",
    "tetrahedra_lin": "Linear tetrahedron method",
    "tetrahedra_opt": "Optimized tetrahedron method",
}

# Smearing types
SMEARING_TYPES = {
    "gaussian": "Gaussian smearing",
    "gauss": "Gaussian smearing (alias)",
    "methfessel-paxton": "Methfessel-Paxton (order 1)",
    "m-p": "Methfessel-Paxton (alias)",
    "marzari-vanderbilt": "Cold smearing (Marzari-Vanderbilt)",
    "m-v": "Cold smearing (alias)",
    "fermi-dirac": "Fermi-Dirac smearing",
    "f-d": "Fermi-Dirac (alias)",
}

# High-symmetry points for common lattices
HIGH_SYMMETRY_POINTS = {
    "fcc": {
        "Γ": [0.0, 0.0, 0.0],
        "X": [0.5, 0.0, 0.5],
        "W": [0.5, 0.25, 0.75],
        "K": [0.375, 0.375, 0.75],
        "L": [0.5, 0.5, 0.5],
        "U": [0.625, 0.25, 0.625],
    },
    "bcc": {
        "Γ": [0.0, 0.0, 0.0],
        "H": [0.5, -0.5, 0.5],
        "N": [0.0, 0.0, 0.5],
        "P": [0.25, 0.25, 0.25],
    },
    "hexagonal": {
        "Γ": [0.0, 0.0, 0.0],
        "M": [0.5, 0.0, 0.0],
        "K": [1/3, 1/3, 0.0],
        "A": [0.0, 0.0, 0.5],
        "L": [0.5, 0.0, 0.5],
        "H": [1/3, 1/3, 0.5],
    },
    "simple_cubic": {
        "Γ": [0.0, 0.0, 0.0],
        "X": [0.5, 0.0, 0.0],
        "M": [0.5, 0.5, 0.0],
        "R": [0.5, 0.5, 0.5],
    },
}

# Common band paths
BAND_PATHS = {
    "fcc": "Γ-X-W-K-Γ-L-U-W-L-K",
    "bcc": "Γ-H-N-Γ-P-H",
    "hexagonal": "Γ-M-K-Γ-A-L-H-A",
    "simple_cubic": "Γ-X-M-Γ-R-X",
}

# Default convergence thresholds
DEFAULT_CONV_THR = 1.0e-8  # Ry
DEFAULT_FORC_CONV_THR = 1.0e-4  # Ry/Bohr
DEFAULT_ETOT_CONV_THR = 1.0e-5  # Ry

# Unit conversions
RY_TO_EV = 13.605693122994
BOHR_TO_ANGSTROM = 0.529177210903
HA_TO_EV = 27.211386245988
