"""Plot recipes for automatic post-processing."""

from .base import PlotRecipe, PlotMetadata, PlotStyle
from .bands import BandStructureRecipe
from .dos import DOSRecipe
from .pdos import PDOSRecipe
from .composite import CompositeBandsDOSRecipe
from .convergence import ConvergenceRecipe

__all__ = [
    "PlotRecipe",
    "PlotMetadata",
    "PlotStyle",
    "BandStructureRecipe",
    "DOSRecipe",
    "PDOSRecipe",
    "CompositeBandsDOSRecipe",
    "ConvergenceRecipe",
]
