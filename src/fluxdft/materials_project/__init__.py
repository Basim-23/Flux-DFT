"""
Materials Project Integration for FluxDFT.

IMPORTANT LEGAL NOTES:
- Materials Project data is accessed via their official API
- Data is NOT redistributed; it is fetched on-demand with user's API key
- Users must have their own MP account and agree to MP terms of use
- Attribution: "Data from Materials Project (materialsproject.org)"
- MP API Terms: https://materialsproject.org/terms
"""

from .client import MaterialsProjectClient, MPMaterial
from .comparator import MPComparator, ComparisonResult
from .cache import MPCache

MP_ATTRIBUTION = "Data from Materials Project (materialsproject.org)"
MP_CITATION = "A. Jain et al., APL Mater. 1, 011002 (2013)"

__all__ = [
    "MaterialsProjectClient",
    "MPMaterial",
    "MPComparator",
    "ComparisonResult",
    "MPCache",
    "MP_ATTRIBUTION",
    "MP_CITATION",
]
