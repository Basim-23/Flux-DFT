"""
Cutoff validation rules for FluxDFT.

Validates ecutwfc and ecutrho parameters based on:
- Element-specific requirements
- Pseudopotential type (NC/US/PAW)
- Literature recommendations
"""

from ..rule_base import ValidationRule, ValidationContext
from ..validation_result import ValidationResult, Severity


class EcutwfcMinimumRule(ValidationRule):
    """
    Validates that ecutwfc meets minimum requirements for each element.
    
    Based on:
    - SSSP library recommendations
    - Lejaeghere et al., Science 351 (2016) - Delta test
    - Standard pseudopotential testing
    """
    
    rule_id = "CUTOFF_001"
    category = "cutoff"
    name = "Wavefunction Cutoff"
    description = "Check plane-wave cutoff against element requirements"
    
    # Element-specific minimum ecutwfc (Ry)
    # Conservative values based on SSSP efficiency library
    ELEMENT_MINIMUMS = {
        # First row
        "H": 30, "He": 30,
        # Second row
        "Li": 40, "Be": 40, "B": 40, "C": 40, "N": 50, "O": 50, "F": 50, "Ne": 50,
        # Third row
        "Na": 40, "Mg": 40, "Al": 35, "Si": 30, "P": 35, "S": 40, "Cl": 45, "Ar": 45,
        # Transition metals (3d)
        "Sc": 50, "Ti": 50, "V": 55, "Cr": 55, "Mn": 55, "Fe": 60, 
        "Co": 55, "Ni": 60, "Cu": 50, "Zn": 70,
        # Post-transition
        "Ga": 50, "Ge": 45, "As": 40, "Se": 45, "Br": 45, "Kr": 45,
        # 4d transition metals
        "Y": 45, "Zr": 45, "Nb": 50, "Mo": 50, "Tc": 50, "Ru": 50,
        "Rh": 50, "Pd": 50, "Ag": 45, "Cd": 60,
        # 5d transition metals
        "Hf": 45, "Ta": 50, "W": 50, "Re": 50, "Os": 50, "Ir": 50,
        "Pt": 45, "Au": 45, "Hg": 60,
        # Lanthanides (need high cutoffs due to f-electrons)
        "La": 50, "Ce": 55, "Pr": 55, "Nd": 55, "Pm": 55, "Sm": 55,
        "Eu": 55, "Gd": 55, "Tb": 55, "Dy": 55, "Ho": 55, "Er": 55,
        "Tm": 55, "Yb": 55, "Lu": 55,
        # Actinides
        "Ac": 55, "Th": 55, "Pa": 55, "U": 55, "Np": 55, "Pu": 55,
    }
    
    # Default for elements not in table
    DEFAULT_MINIMUM = 40.0
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        ecutwfc = getattr(input_data, 'ecutwfc', None)
        
        if ecutwfc is None:
            return self._error(
                message="ecutwfc not specified",
                explanation="Plane-wave cutoff (ecutwfc) is required for all calculations.",
                fix="Add ecutwfc to SYSTEM namelist",
                param="ecutwfc",
            )
        
        # Get required cutoff for all elements
        elements = context.elements
        if not elements:
            return self._warning(
                message="No elements detected, cannot validate ecutwfc",
            )
        
        requirements = {
            el: self.ELEMENT_MINIMUMS.get(el, self.DEFAULT_MINIMUM)
            for el in elements
        }
        
        max_required = max(requirements.values())
        limiting_element = max(requirements, key=requirements.get)
        
        # Check against thresholds
        if ecutwfc < max_required * 0.7:
            # Severe: below 70% of minimum
            return self._error(
                message=f"ecutwfc ({ecutwfc} Ry) is dangerously low",
                explanation=f"For {limiting_element}, minimum {max_required} Ry is recommended. "
                           f"Current value ({ecutwfc} Ry) is only {ecutwfc/max_required*100:.0f}% "
                           "of this. Wavefunctions will be severely truncated, leading to "
                           "incorrect energies, forces, and properties.",
                fix=f"Increase ecutwfc to at least {max_required} Ry",
                param="ecutwfc",
                current=ecutwfc,
                recommended=max_required,
            )
        
        elif ecutwfc < max_required:
            # Below minimum but not severely
            return self._warning(
                message=f"ecutwfc ({ecutwfc} Ry) is below recommended value",
                explanation=f"For {limiting_element}, at least {max_required} Ry is recommended. "
                           "Results may have ~1-5 meV/atom errors.",
                fix=f"Consider increasing ecutwfc to {max_required} Ry for production calculations",
                param="ecutwfc",
                current=ecutwfc,
                recommended=max_required,
            )
        
        elif ecutwfc < max_required * 1.2:
            # Acceptable but could be higher for publications
            return self._info(
                message=f"ecutwfc ({ecutwfc} Ry) is acceptable",
                explanation=f"Consider running a convergence test to verify this is sufficient.",
            )
        
        return self._pass()


class EcutrhoRatioRule(ValidationRule):
    """
    Validates ecutrho/ecutwfc ratio based on pseudopotential type.
    
    Requirements:
    - Norm-conserving: ecutrho = 4 * ecutwfc (minimum)
    - Ultrasoft: ecutrho = 8-12 * ecutwfc
    - PAW: ecutrho = 8-12 * ecutwfc
    """
    
    rule_id = "CUTOFF_002"
    category = "cutoff"
    name = "Density Cutoff Ratio"
    description = "Check ecutrho/ecutwfc ratio for pseudopotential type"
    
    # Minimum ratio by pseudo type
    RATIO_REQUIREMENTS = {
        "NC": 4.0,
        "US": 8.0,
        "PAW": 8.0,
    }
    
    RATIO_OPTIMAL = {
        "NC": 4.0,
        "US": 10.0,
        "PAW": 10.0,
    }
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        ecutwfc = getattr(input_data, 'ecutwfc', None)
        ecutrho = getattr(input_data, 'ecutrho', None)
        
        if ecutwfc is None:
            return self._pass()  # Will be caught by other rule
        
        if ecutrho is None:
            # QE uses default of 4*ecutwfc if not specified
            ecutrho = 4.0 * ecutwfc
        
        ratio = ecutrho / ecutwfc
        pseudo_type = context.get_pseudo_type()
        min_ratio = self.RATIO_REQUIREMENTS.get(pseudo_type, 4.0)
        optimal_ratio = self.RATIO_OPTIMAL.get(pseudo_type, 4.0)
        
        if ratio < min_ratio * 0.9:
            return self._error(
                message=f"ecutrho/ecutwfc ratio ({ratio:.1f}) too low for {pseudo_type} pseudopotentials",
                explanation=f"Ultrasoft and PAW pseudopotentials have augmentation charges that "
                           f"require fine real-space grids. A ratio of at least {min_ratio} is "
                           "required for accurate integration.",
                fix=f"Set ecutrho = {int(ecutwfc * optimal_ratio)} Ry ({optimal_ratio}× ecutwfc)",
                param="ecutrho",
                current=ecutrho,
                recommended=int(ecutwfc * optimal_ratio),
            )
        
        elif ratio < min_ratio:
            return self._warning(
                message=f"ecutrho/ecutwfc ratio ({ratio:.1f}) is marginal for {pseudo_type}",
                explanation="Consider increasing for better accuracy.",
                fix=f"Set ecutrho = {int(ecutwfc * optimal_ratio)} Ry",
                param="ecutrho",
                current=ecutrho,
                recommended=int(ecutwfc * optimal_ratio),
            )
        
        return self._pass()
