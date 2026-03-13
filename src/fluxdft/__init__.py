"""
FluxDFT — Professional GUI for Quantum ESPRESSO

Copyright (c) 2026 Basim Nasser. MIT License.

FluxDFT provides:
- Core: Structure loading, input building, output parsing, job management
- Electronic: Band structure, DOS, Fermi surface, effective mass, optical
- Plotting: Publication-quality band structure, DOS, fat band visualizations
- Workflows: Task/workflow management with Slurm/PBS integration
- Intelligence: Validation, error detection, fix suggestions
- Phonon: Phonon band structure, DOS, thermodynamics
- Analysis: Bader charges, bonding analysis
- Symmetry: K-path generation, space group analysis
- Materials Project: Reference data integration
- I/O: QE input/output parsing and generation
- Reporting: HTML/LaTeX/Markdown report generation
- UI: Professional PyQt6 interface with real-time monitoring

Modules:
    fluxdft.core - Core structure handling
    fluxdft.electronic - Electronic structure analysis
    fluxdft.phonon - Phonon analysis
    fluxdft.plotting - Publication plotting
    fluxdft.workflows - Workflow management
    fluxdft.intelligence - Validation & error handling
    fluxdft.symmetry - K-path & symmetry
    fluxdft.analysis - Charge & bonding analysis
    fluxdft.io - Input/output parsing
    fluxdft.reporting - Report generation
    fluxdft.materials_project - MP integration
    fluxdft.ui - User interface
"""

__version__ = "2.0.0"
__author__ = "Basim Nasser"
__product__ = "FluxDFT"
__copyright__ = "Copyright (c) 2026 Basim Nasser. MIT License."

# Convenience imports for common use cases
from .core import StructureModel, StructureLoader

# Version info
def get_version_info():
    """Get detailed version information."""
    return {
        'version': __version__,
        'product': __product__,
        'author': __author__,
        'modules': [
            'core',
            'electronic',
            'phonon',
            'plotting',
            'workflows',
            'intelligence',
            'symmetry',
            'analysis',
            'io',
            'reporting',
            'materials_project',
            'ui',
        ]
    }

__all__ = [
    # Version
    "__version__",
    "__product__",
    "__author__",
    "get_version_info",
    # Core
    "StructureModel",
    "StructureLoader",
]



