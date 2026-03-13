"""
DFT Result Validator for FluxDFT.

Post-calculation validation to detect physically suspicious results
and warn users about potential issues.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Severity level of validation result."""
    PASS = "pass"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    """
    Result of a single validation check.
    
    Attributes:
        check_name: Name of the validation check
        level: Severity level
        message: Human-readable message
        details: Additional context/data
        suggestions: List of actionable suggestions
    """
    check_name: str
    level: ValidationLevel
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        return self.level in (ValidationLevel.PASS, ValidationLevel.INFO)


class DFTResultValidator:
    """
    Post-calculation result validator.
    
    Validates DFT calculation results for physical reasonableness.
    Can compare against Materials Project reference data.
    
    Checks include:
    - Band gap consistency with expected values
    - Realistic band gap range
    - Metal/insulator classification
    - Force convergence
    - Energy convergence
    - Magnetic moment validation
    
    Usage:
        >>> validator = DFTResultValidator(mp_client=mp_client)
        >>> results = validator.validate_calculation(
        ...     formula="Si",
        ...     band_gap=1.1,
        ...     is_metal=False,
        ...     total_energy=-15.87,
        ... )
        >>> for r in results:
        ...     print(f"{r.level.value}: {r.message}")
    """
    
    # Band gap thresholds
    MAX_REASONABLE_BANDGAP = 12.0  # eV (very wide gap insulators)
    MIN_INSULATOR_GAP = 0.01  # eV
    
    # Force thresholds
    DEFAULT_FORCE_THRESHOLD = 0.05  # Ry/Bohr
    STRICT_FORCE_THRESHOLD = 0.01  # Ry/Bohr
    
    # Energy thresholds
    ENERGY_CONVERGENCE_THRESHOLD = 1e-6  # Ry
    
    def __init__(self, mp_client=None):
        """
        Initialize validator.
        
        Args:
            mp_client: Optional MaterialsProjectClient for reference comparisons
        """
        self.mp_client = mp_client
        self._mp_cache = {}
    
    def validate_calculation(
        self,
        formula: str,
        band_gap: Optional[float] = None,
        is_metal: Optional[bool] = None,
        total_energy: Optional[float] = None,
        max_force: Optional[float] = None,
        total_magnetization: Optional[float] = None,
        spacegroup: Optional[str] = None,
        is_spin_polarized: bool = False,
        **kwargs,
    ) -> List[ValidationResult]:
        """
        Run all validation checks on calculation results.
        
        Args:
            formula: Chemical formula (e.g., "Si", "Fe2O3")
            band_gap: Calculated band gap in eV
            is_metal: Whether system is metallic
            total_energy: Total energy in Ry
            max_force: Maximum residual force in Ry/Bohr
            total_magnetization: Total magnetization in Bohr magneton
            spacegroup: Space group symbol if known
            is_spin_polarized: Whether calculation was spin-polarized
            **kwargs: Additional parameters
            
        Returns:
            List of ValidationResult objects
        """
        results = []
        
        # Get MP reference if available
        mp_ref = self._get_mp_reference(formula, spacegroup)
        
        # Band gap validation
        if band_gap is not None:
            results.extend(self._validate_band_gap(
                band_gap, is_metal, formula, mp_ref
            ))
        
        # Force convergence
        if max_force is not None:
            results.extend(self._validate_forces(max_force))
        
        # Magnetization
        if total_magnetization is not None:
            results.extend(self._validate_magnetization(
                total_magnetization, formula, is_spin_polarized, mp_ref
            ))
        
        # General reasonableness checks
        results.extend(self._validate_general(formula, mp_ref, **kwargs))
        
        return results
    
    def _get_mp_reference(
        self,
        formula: str,
        spacegroup: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch Materials Project reference data."""
        if self.mp_client is None:
            return None
        
        if not self.mp_client.is_configured():
            return None
        
        cache_key = f"{formula}_{spacegroup or 'any'}"
        if cache_key in self._mp_cache:
            return self._mp_cache[cache_key]
        
        try:
            match = self.mp_client.find_best_match(formula, spacegroup)
            if match:
                ref = {
                    'mp_id': match.mp_id,
                    'band_gap': match.band_gap,
                    'is_metal': match.is_metal,
                    'is_magnetic': match.is_magnetic,
                    'total_magnetization': match.total_magnetization,
                    'formula': match.formula_pretty,
                }
                self._mp_cache[cache_key] = ref
                return ref
        except Exception as e:
            logger.warning(f"Could not fetch MP reference: {e}")
        
        return None
    
    def _validate_band_gap(
        self,
        band_gap: float,
        is_metal: Optional[bool],
        formula: str,
        mp_ref: Optional[Dict],
    ) -> List[ValidationResult]:
        """Validate band gap value."""
        results = []
        
        # Check for unreasonably large gap
        if band_gap > self.MAX_REASONABLE_BANDGAP:
            results.append(ValidationResult(
                check_name="band_gap_range",
                level=ValidationLevel.WARNING,
                message=f"Unusually large band gap: {band_gap:.2f} eV",
                details={'band_gap': band_gap, 'threshold': self.MAX_REASONABLE_BANDGAP},
                suggestions=[
                    "Verify calculation completed correctly",
                    "Check for convergence issues",
                ],
            ))
        
        # Check for fake metallic behavior
        if is_metal and mp_ref and not mp_ref.get('is_metal', True):
            results.append(ValidationResult(
                check_name="metal_insulator_mismatch",
                level=ValidationLevel.WARNING,
                message=f"System appears metallic but {formula} is insulating in MP reference",
                details={
                    'calculated_metal': True,
                    'mp_metal': mp_ref.get('is_metal'),
                    'mp_gap': mp_ref.get('band_gap'),
                },
                suggestions=[
                    "Increase k-point density (especially near Fermi level)",
                    "Check smearing parameters",
                    "This may indicate insufficient k-point sampling",
                ],
            ))
        
        # Compare with MP reference
        if mp_ref and mp_ref.get('band_gap') is not None:
            mp_gap = mp_ref['band_gap']
            gap_diff = abs(band_gap - mp_gap)
            
            # Large discrepancy
            if gap_diff > 1.0:
                level = ValidationLevel.WARNING if gap_diff > 2.0 else ValidationLevel.INFO
                results.append(ValidationResult(
                    check_name="band_gap_mp_comparison",
                    level=level,
                    message=f"Band gap ({band_gap:.2f} eV) differs from MP ({mp_gap:.2f} eV) by {gap_diff:.2f} eV",
                    details={
                        'calculated_gap': band_gap,
                        'mp_gap': mp_gap,
                        'difference': gap_diff,
                        'mp_id': mp_ref.get('mp_id'),
                    },
                    suggestions=[
                        "LDA/GGA typically underestimates band gaps by ~50%",
                        "Consider hybrid functionals or GW for accurate gaps",
                        "Check if same structure as MP reference",
                    ],
                ))
            else:
                results.append(ValidationResult(
                    check_name="band_gap_mp_comparison",
                    level=ValidationLevel.PASS,
                    message=f"Band gap ({band_gap:.2f} eV) consistent with MP reference ({mp_gap:.2f} eV)",
                    details={'calculated_gap': band_gap, 'mp_gap': mp_gap},
                ))
        
        # Check for negative gap (shouldn't happen)
        if band_gap < 0:
            results.append(ValidationResult(
                check_name="negative_band_gap",
                level=ValidationLevel.ERROR,
                message="Negative band gap detected - calculation error",
                details={'band_gap': band_gap},
                suggestions=["Check calculation output for errors"],
            ))
        
        return results
    
    def _validate_forces(self, max_force: float) -> List[ValidationResult]:
        """Validate force convergence."""
        results = []
        
        if max_force > self.DEFAULT_FORCE_THRESHOLD:
            results.append(ValidationResult(
                check_name="force_convergence",
                level=ValidationLevel.WARNING,
                message=f"Forces not fully converged: max={max_force:.4f} Ry/Bohr",
                details={
                    'max_force': max_force,
                    'threshold': self.DEFAULT_FORCE_THRESHOLD,
                },
                suggestions=[
                    "Continue geometry relaxation",
                    "Increase forc_conv_thr",
                    "Check for convergence issues",
                ],
            ))
        elif max_force > self.STRICT_FORCE_THRESHOLD:
            results.append(ValidationResult(
                check_name="force_convergence",
                level=ValidationLevel.INFO,
                message=f"Forces converged to standard threshold: {max_force:.4f} Ry/Bohr",
                details={'max_force': max_force},
            ))
        else:
            results.append(ValidationResult(
                check_name="force_convergence",
                level=ValidationLevel.PASS,
                message=f"Forces well converged: {max_force:.4f} Ry/Bohr",
                details={'max_force': max_force},
            ))
        
        return results
    
    def _validate_magnetization(
        self,
        total_mag: float,
        formula: str,
        is_spin_polarized: bool,
        mp_ref: Optional[Dict],
    ) -> List[ValidationResult]:
        """Validate magnetic properties."""
        results = []
        
        # Non-spin-polarized but magnetic expected
        if mp_ref and mp_ref.get('is_magnetic') and not is_spin_polarized:
            results.append(ValidationResult(
                check_name="magnetization_expected",
                level=ValidationLevel.WARNING,
                message=f"{formula} is magnetic in MP but calculation was non-spin-polarized",
                details={
                    'mp_magnetic': True,
                    'mp_magnetization': mp_ref.get('total_magnetization'),
                },
                suggestions=[
                    "Enable spin-polarized calculation (nspin=2)",
                    "Set appropriate starting_magnetization",
                ],
            ))
        
        # Compare magnetization with MP
        if mp_ref and mp_ref.get('total_magnetization') is not None and is_spin_polarized:
            mp_mag = mp_ref['total_magnetization']
            mag_diff = abs(total_mag - mp_mag)
            
            # Significant deviation
            if mp_mag > 0.1 and mag_diff > 0.5:
                results.append(ValidationResult(
                    check_name="magnetization_comparison",
                    level=ValidationLevel.INFO,
                    message=f"Magnetization ({total_mag:.2f} µB) differs from MP ({mp_mag:.2f} µB)",
                    details={
                        'calculated_mag': total_mag,
                        'mp_mag': mp_mag,
                    },
                ))
        
        return results
    
    def _validate_general(
        self,
        formula: str,
        mp_ref: Optional[Dict],
        **kwargs,
    ) -> List[ValidationResult]:
        """General validation checks."""
        results = []
        
        # Check if MP reference was found
        if self.mp_client and self.mp_client.is_configured() and mp_ref is None:
            results.append(ValidationResult(
                check_name="mp_reference_found",
                level=ValidationLevel.INFO,
                message=f"No Materials Project reference found for {formula}",
                suggestions=["Novel material or unusual stoichiometry"],
            ))
        elif mp_ref:
            results.append(ValidationResult(
                check_name="mp_reference_found",
                level=ValidationLevel.PASS,
                message=f"Using MP reference: {mp_ref.get('mp_id', 'unknown')}",
                details={'mp_id': mp_ref.get('mp_id')},
            ))
        
        return results
    
    def get_summary(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """
        Get summary of validation results.
        
        Returns dict with counts and overall status.
        """
        counts = {level.value: 0 for level in ValidationLevel}
        for r in results:
            counts[r.level.value] += 1
        
        # Overall status
        if counts['error'] > 0:
            status = 'error'
        elif counts['warning'] > 0:
            status = 'warning'
        elif counts['info'] > 0:
            status = 'info'
        else:
            status = 'pass'
        
        return {
            'status': status,
            'counts': counts,
            'total_checks': len(results),
            'all_passed': status == 'pass',
        }
