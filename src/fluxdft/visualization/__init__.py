"""
FluxDFT Visualization Module.

Provides 3D visualization for:
- Crystal structures
- Isosurfaces (charge density, spin density)
- Fermi surfaces
- Phonon modes

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from .structure_viewer import (
    StructureViewer,
    StructureScene,
    AtomStyle,
    ColorScheme,
    AtomRenderInfo,
    BondRenderInfo,
    JMOL_COLORS,
    COVALENT_RADII,
    view_structure,
)

__all__ = [
    'StructureViewer',
    'StructureScene',
    'AtomStyle',
    'ColorScheme',
    'AtomRenderInfo',
    'BondRenderInfo',
    'JMOL_COLORS',
    'COVALENT_RADII',
    'view_structure',
]
