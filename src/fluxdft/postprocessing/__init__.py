"""
Post-processing module for FluxDFT.

Provides automatic plot generation after job completion.
"""

from .manager import PostProcessingManager
from .recipes import PlotRecipe, PlotMetadata

__all__ = ["PostProcessingManager", "PlotRecipe", "PlotMetadata"]
