"""
K-points validation rules for FluxDFT.

Validates k-point sampling based on:
- Cell dimensions (k*a product)
- Material type (metal vs insulator)
- Calculation type (SCF vs bands)
"""

from ..rule_base import ValidationRule, ValidationContext
from ..validation_result import ValidationResult, Severity


class KPointDensityRule(ValidationRule):
    """
    Validates k-point density based on cell size.
    
    Heuristic: k_i * a_i >= threshold (in Å)
    - Metals: 40-60 Å needed for accurate Fermi surface
    - Insulators/semiconductors: 20-30 Å acceptable
    
    Based on:
    - Common practice in DFT literature
    - Sholl & Steckel textbook recommendations
    """
    
    rule_id = "KPOINTS_001"
    category = "kpoints"
    name = "K-point Density"
    description = "Check k-point sampling against cell dimensions"
    
    THRESHOLDS = {
        "metal": 45,
        "semiconductor": 30,
        "insulator": 25,
        "unknown": 35,  # Conservative for unknown systems
    }
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        kpoints = getattr(input_data, 'kpoints', None)
        
        if kpoints is None:
            return self._error(
                message="K_POINTS not specified",
                explanation="K-point sampling is required for periodic calculations.",
                fix="Add K_POINTS card with automatic grid or explicit points",
            )
        
        # Only check for automatic grids
        mode = getattr(kpoints, 'mode', 'automatic')
        if mode == 'gamma':
            # Gamma-only is fine for molecules or very large cells
            if context.n_atoms and context.n_atoms < 50:
                return self._warning(
                    message="Gamma-only k-point for small system",
                    explanation="Gamma-only sampling is usually only accurate for "
                               "molecules or very large supercells (>50 atoms).",
                    fix="Use at least a 2×2×2 grid for better accuracy",
                )
            return self._pass()
        
        if mode not in ('automatic', 'auto'):
            return self._pass()  # Explicit k-points, assume user knows what they're doing
        
        grid = getattr(kpoints, 'grid', None)
        if not grid or len(grid) < 3:
            return self._warning(
                message="Could not determine k-point grid",
            )
        
        # Check cell parameters
        if not context.cell_params:
            return self._info(
                message="Cannot validate k-point density without cell parameters",
            )
        
        a, b, c = context.cell_params
        k1, k2, k3 = grid[0], grid[1], grid[2]
        
        # Calculate k*a products
        ka_products = [k1 * a, k2 * b, k3 * c]
        min_ka = min(ka_products)
        min_direction = ['a', 'b', 'c'][ka_products.index(min_ka)]
        
        # Adjust for 2D systems (ignore vacuum direction)
        if context.is_2d:
            # Ignore c-direction for 2D
            ka_products_2d = [k1 * a, k2 * b]
            min_ka = min(ka_products_2d)
            min_direction = ['a', 'b'][ka_products_2d.index(min_ka)]
        
        material_type = context.detect_material_type()
        threshold = self.THRESHOLDS.get(material_type, 35)
        
        # Suggest appropriate grid
        def suggest_grid(threshold, params):
            return tuple(max(1, int(threshold / p) + 1) for p in params[:3])
        
        if min_ka < threshold * 0.5:
            return self._error(
                message=f"K-point density severely insufficient (k×a = {min_ka:.1f} Å)",
                explanation=f"For {material_type}s, k×a should be at least {threshold} Å. "
                           f"Direction {min_direction} is limiting with only {min_ka:.1f} Å. "
                           "This will cause large sampling errors in total energy.",
                fix=f"Increase k-grid to at least {suggest_grid(threshold, context.cell_params)}",
                param="K_POINTS",
                current=grid,
                recommended=suggest_grid(threshold, context.cell_params),
            )
        
        elif min_ka < threshold:
            return self._warning(
                message=f"K-point density marginal (k×a = {min_ka:.1f} Å in {min_direction})",
                explanation=f"For publication-quality results, consider {threshold} Å minimum.",
                fix=f"Consider k-grid {suggest_grid(threshold, context.cell_params)}",
                param="K_POINTS",
                current=grid,
                recommended=suggest_grid(threshold, context.cell_params),
            )
        
        return self._pass()


class KPointShiftRule(ValidationRule):
    """
    Validates k-point grid shifts.
    
    Rules:
    - Odd grids should NOT be shifted (includes Gamma)
    - Even grids should be shifted for better sampling
    - Special cases: magnetic, spin-orbit
    """
    
    rule_id = "KPOINTS_002"
    category = "kpoints"
    name = "K-point Shift"
    description = "Check k-point shift for grid type"
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        kpoints = getattr(input_data, 'kpoints', None)
        
        if not kpoints or getattr(kpoints, 'mode', '') not in ('automatic', 'auto'):
            return self._pass()
        
        grid = getattr(kpoints, 'grid', None)
        shift = getattr(kpoints, 'shift', (0, 0, 0))
        
        if not grid:
            return self._pass()
        
        # Check for even grids without shift
        even_directions = [i for i, k in enumerate(grid[:3]) if k % 2 == 0]
        
        if even_directions and shift == (0, 0, 0):
            return self._info(
                message="Even k-grid without shift",
                explanation="For even k-grids, a (1,1,1) shift often improves sampling "
                           "by avoiding high-symmetry points. However, this depends on "
                           "the specific system and property being computed.",
            )
        
        # Check for odd grids with shift (less optimal)
        odd_with_shift = any(
            grid[i] % 2 == 1 and shift[i] == 1 
            for i in range(min(3, len(grid), len(shift)))
        )
        
        if odd_with_shift:
            return self._info(
                message="Odd k-grid with shift",
                explanation="Odd k-grids typically don't benefit from shifting and "
                           "naturally include the Gamma point. Consider removing shift.",
            )
        
        return self._pass()
