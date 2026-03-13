"""
Electronic Structure Analysis Module for FluxDFT.

Comprehensive electronic structure analysis inspired by abipy's ebands.py.
Provides band structure, DOS, Fermi surface, effective mass, optical, and fat bands.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from .band_structure import (
    ElectronicBandStructure,
    BandGapInfo,
    BandEdge,
)

from .dos import (
    ElectronicDOS,
    ProjectedDOS,
    OrbitalProjection,
)

from .fermi_surface import (
    FermiSurface,
    FermiSurfaceSlice,
)

from .effective_mass import (
    EffectiveMass,
    EffectiveMassCalculator,
)

from .advanced_effmass import (
    AdvancedEffMassAnalyzer,
    EffectiveMassResult,
    Segment,
)

from .optical import (
    OpticalPropertiesCalculator,
    DielectricFunction,
)

from .fatbands import (
    FatBandData,
    FatBandParser,
    FatBandPlotter,
    OrbitalWeight,
)

from .analysis import (
    ElectronicStructureAnalyzer,
    CarrierConcentration,
)

__all__ = [
    # Band Structure
    'ElectronicBandStructure',
    'BandGapInfo',
    'BandEdge',
    # DOS
    'ElectronicDOS',
    'ProjectedDOS',
    'OrbitalProjection',
    # Fermi Surface
    'FermiSurface',
    'FermiSurfaceSlice',
    # Effective Mass
    'EffectiveMass',
    'EffectiveMassCalculator',
    'AdvancedEffMassAnalyzer',
    'EffectiveMassResult',
    'Segment',
    # Optical Properties
    'OpticalPropertiesCalculator',
    'DielectricFunction',
    # Fat Bands
    'FatBandData',
    'FatBandParser',
    'FatBandPlotter',
    'OrbitalWeight',
    # Analysis
    'ElectronicStructureAnalyzer',
    'CarrierConcentration',
]


