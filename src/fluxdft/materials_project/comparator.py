"""
Comparator for user results vs Materials Project references.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any

from .client import MaterialsProjectClient, MPMaterial


@dataclass
class ComparisonResult:
    """Result of comparing a property to MP reference."""
    property_name: str
    user_value: float
    reference_value: float
    difference: float
    percent_error: float
    status: str  # "good", "warning", "error"
    message: str
    mp_id: str = ""
    
    @property
    def is_good(self) -> bool:
        return self.status == "good"
    
    @property
    def is_warning(self) -> bool:
        return self.status == "warning"
    
    @property
    def is_error(self) -> bool:
        return self.status == "error"
    
    @property
    def color(self) -> str:
        return {
            "good": "#a6e3a1",
            "warning": "#f9e2af",
            "error": "#f38ba8",
        }.get(self.status, "#cdd6f4")


class MPComparator:
    """
    Compares user calculation results to Materials Project references.
    
    Provides:
    - Pre-calculation expectations
    - Post-calculation validation
    - Deviation warnings
    
    Usage:
        client = MaterialsProjectClient(api_key)
        comparator = MPComparator(client)
        
        results = comparator.compare("Si", {"band_gap": 0.58})
        for r in results:
            print(f"{r.property_name}: {r.message}")
    """
    
    # Tolerance thresholds
    BAND_GAP_TOLERANCE = 0.3        # eV (PBE typically underestimates by ~0.5 eV)
    BAND_GAP_PERCENT_TOL = 25       # % difference allowed
    VOLUME_TOLERANCE = 5            # % difference
    MAGNETIZATION_TOLERANCE = 0.5   # μB/f.u.
    
    def __init__(self, client: MaterialsProjectClient):
        """
        Initialize the comparator.
        
        Args:
            client: Configured MaterialsProjectClient
        """
        self.client = client
    
    def compare(
        self,
        formula: str,
        user_results: Dict[str, float],
        spacegroup: Optional[str] = None,
    ) -> List[ComparisonResult]:
        """
        Compare user results to MP reference.
        
        Args:
            formula: Chemical formula
            user_results: Dict with keys like "band_gap", "volume", "magnetization"
            spacegroup: Optional spacegroup for better matching
            
        Returns:
            List of comparison results
        """
        ref = self.client.find_best_match(formula, spacegroup)
        if not ref:
            return []
        
        comparisons = []
        
        # Band gap comparison
        if "band_gap" in user_results:
            comparison = self._compare_band_gap(
                user_results["band_gap"],
                ref,
            )
            if comparison:
                comparisons.append(comparison)
        
        # Metal/insulator consistency
        if "band_gap" in user_results:
            comparison = self._check_metal_consistency(
                user_results["band_gap"],
                ref,
            )
            if comparison:
                comparisons.append(comparison)
        
        # Volume comparison
        if "volume" in user_results and ref.volume:
            comparison = self._compare_volume(
                user_results["volume"],
                ref,
            )
            if comparison:
                comparisons.append(comparison)
        
        # Magnetization comparison
        if "magnetization" in user_results:
            comparison = self._compare_magnetization(
                user_results["magnetization"],
                ref,
            )
            if comparison:
                comparisons.append(comparison)
        
        return comparisons
    
    def _compare_band_gap(
        self,
        user_gap: float,
        ref: MPMaterial,
    ) -> Optional[ComparisonResult]:
        """Compare band gap values."""
        if ref.band_gap is None:
            return None
        
        ref_gap = ref.band_gap
        diff = user_gap - ref_gap
        
        # Calculate percent error (handle zero reference)
        if ref_gap > 0.01:
            pct = abs(diff / ref_gap) * 100
        else:
            pct = 100 if user_gap > 0.1 else 0
        
        # Determine status
        if abs(diff) < self.BAND_GAP_TOLERANCE and pct < self.BAND_GAP_PERCENT_TOL:
            status = "good"
            msg = f"Band gap ({user_gap:.2f} eV) matches MP reference ({ref_gap:.2f} eV)"
        elif abs(diff) < self.BAND_GAP_TOLERANCE * 2:
            status = "warning"
            msg = f"Band gap differs from MP by {diff:+.2f} eV ({pct:.0f}%)"
        else:
            status = "error"
            msg = f"Band gap significantly differs from MP ({diff:+.2f} eV, {pct:.0f}%)"
        
        return ComparisonResult(
            property_name="Band Gap",
            user_value=user_gap,
            reference_value=ref_gap,
            difference=diff,
            percent_error=pct,
            status=status,
            message=msg,
            mp_id=ref.mp_id,
        )
    
    def _check_metal_consistency(
        self,
        user_gap: float,
        ref: MPMaterial,
    ) -> Optional[ComparisonResult]:
        """Check metal/insulator consistency."""
        user_is_metal = user_gap < 0.01
        
        if user_is_metal == ref.is_metal:
            return None  # Consistent, no issue
        
        return ComparisonResult(
            property_name="Metal/Insulator",
            user_value=0 if user_is_metal else 1,
            reference_value=0 if ref.is_metal else 1,
            difference=1,
            percent_error=100,
            status="error",
            message=f"Calculated {'metal' if user_is_metal else 'insulator'} "
                   f"but MP shows {'metal' if ref.is_metal else 'insulator'} ({ref.mp_id})",
            mp_id=ref.mp_id,
        )
    
    def _compare_volume(
        self,
        user_volume: float,
        ref: MPMaterial,
    ) -> Optional[ComparisonResult]:
        """Compare unit cell volume."""
        if not ref.volume:
            return None
        
        diff = user_volume - ref.volume
        pct = abs(diff / ref.volume) * 100
        
        if pct < self.VOLUME_TOLERANCE:
            status = "good"
            msg = f"Volume ({user_volume:.1f} Å³) matches MP"
        elif pct < self.VOLUME_TOLERANCE * 2:
            status = "warning"
            msg = f"Volume differs from MP by {pct:.1f}%"
        else:
            status = "error"
            msg = f"Volume significantly differs from MP ({pct:.1f}%)"
        
        return ComparisonResult(
            property_name="Volume",
            user_value=user_volume,
            reference_value=ref.volume,
            difference=diff,
            percent_error=pct,
            status=status,
            message=msg,
            mp_id=ref.mp_id,
        )
    
    def _compare_magnetization(
        self,
        user_mag: float,
        ref: MPMaterial,
    ) -> Optional[ComparisonResult]:
        """Compare magnetization values."""
        ref_mag = ref.total_magnetization or 0
        diff = abs(user_mag) - abs(ref_mag)
        
        # Check magnetic state consistency
        user_is_magnetic = abs(user_mag) > 0.1
        
        if user_is_magnetic != ref.is_magnetic:
            return ComparisonResult(
                property_name="Magnetic State",
                user_value=user_mag,
                reference_value=ref_mag,
                difference=diff,
                percent_error=100,
                status="error",
                message=f"{'Magnetic' if user_is_magnetic else 'Non-magnetic'} "
                       f"but MP shows {'magnetic' if ref.is_magnetic else 'non-magnetic'}",
                mp_id=ref.mp_id,
            )
        
        if abs(diff) < self.MAGNETIZATION_TOLERANCE:
            status = "good"
            msg = f"Magnetization ({user_mag:.2f} μB) matches MP"
        else:
            status = "warning"
            msg = f"Magnetization differs from MP by {diff:.2f} μB"
        
        return ComparisonResult(
            property_name="Magnetization",
            user_value=user_mag,
            reference_value=ref_mag,
            difference=diff,
            percent_error=abs(diff / ref_mag * 100) if ref_mag else 0,
            status=status,
            message=msg,
            mp_id=ref.mp_id,
        )
    
    def get_summary(self, comparisons: List[ComparisonResult]) -> str:
        """Get a summary of comparison results."""
        if not comparisons:
            return "No MP comparison available"
        
        errors = [c for c in comparisons if c.is_error]
        warnings = [c for c in comparisons if c.is_warning]
        
        if errors:
            return f"❌ {len(errors)} significant deviation(s) from MP reference"
        elif warnings:
            return f"⚠️ {len(warnings)} minor deviation(s) from MP reference"
        else:
            return "✅ Results consistent with Materials Project reference"
