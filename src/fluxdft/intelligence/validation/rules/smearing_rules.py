"""
Smearing validation rules for FluxDFT.

Validates smearing parameters based on:
- Material type (metal vs insulator)
- Smearing type appropriateness
- degauss value
"""

from ..rule_base import ValidationRule, ValidationContext
from ..validation_result import ValidationResult, Severity


class MetalSmearingRule(ValidationRule):
    """
    Detects metals and validates that appropriate smearing is used.
    
    Metals MUST use smearing to avoid SCF oscillations due to
    level crossings near the Fermi energy.
    
    Based on:
    - Standard DFT practice
    - QE documentation
    """
    
    rule_id = "SMEARING_001"
    category = "smearing"
    name = "Metal Smearing"
    description = "Check smearing settings for metallic systems"
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        occupations = getattr(input_data, 'occupations', 'fixed')
        
        # Check if system is metallic
        is_metal = context.is_metal
        
        # If we know it's a metal and using fixed occupations
        if is_metal and occupations == 'fixed':
            return self._error(
                message="Metal detected but occupations='fixed'",
                explanation="Fixed occupations cause SCF oscillation in metals "
                           "due to level crossings near the Fermi energy. "
                           "This typically leads to convergence failure.",
                fix="Set occupations='smearing' with smearing='m-v' (cold) "
                   "or smearing='m-p' and degauss=0.02",
                param="occupations",
                current="fixed",
                recommended="smearing",
            )
        
        # Check for known metallic elements without smearing
        metallic_elements = {
            'Li', 'Na', 'K', 'Rb', 'Cs',  # Alkali metals
            'Be', 'Mg', 'Ca', 'Sr', 'Ba',  # Alkaline earth
            'Al', 'Ga', 'In', 'Tl', 'Sn', 'Pb', 'Bi',  # Post-transition
            'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',  # 3d
            'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',  # 4d
            'La', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',  # 5d
        }
        
        has_metal = bool(context.elements & metallic_elements)
        
        if has_metal and occupations == 'fixed':
            return self._warning(
                message="Possible metal with fixed occupations",
                explanation=f"System contains elements ({context.elements & metallic_elements}) "
                           "that are often metallic. If this is a metal, smearing is needed.",
                fix="If metallic, use occupations='smearing' with degauss=0.02 Ry",
                param="occupations",
                current="fixed",
            )
        
        return self._pass()


class DegaussValueRule(ValidationRule):
    """
    Validates degauss (smearing width) value.
    
    Rules:
    - Too small: may cause SCF instability
    - Too large: electronic entropy affects total energy
    - Typical range: 0.005 - 0.03 Ry
    """
    
    rule_id = "SMEARING_002"
    category = "smearing"
    name = "Smearing Width"
    description = "Check degauss value is appropriate"
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        occupations = getattr(input_data, 'occupations', 'fixed')
        
        if occupations != 'smearing':
            return self._pass()
        
        degauss = getattr(input_data, 'degauss', None)
        smearing = getattr(input_data, 'smearing', 'gaussian')
        
        if degauss is None:
            return self._error(
                message="occupations='smearing' but degauss not specified",
                explanation="Smearing width (degauss) is required when using smearing.",
                fix="Add degauss = 0.02 (typical starting value in Ry)",
                param="degauss",
                recommended=0.02,
            )
        
        # Check for too large degauss
        if degauss > 0.05:
            return self._error(
                message=f"degauss ({degauss} Ry) is too large",
                explanation="Large smearing width introduces significant electronic "
                           "entropy term. Total energy loses physical meaning and "
                           "forces become unreliable.",
                fix="Reduce degauss to 0.02 Ry or less after convergence test",
                param="degauss",
                current=degauss,
                recommended=0.02,
            )
        
        if degauss > 0.03:
            return self._warning(
                message=f"degauss ({degauss} Ry) may be too large",
                explanation="Consider reducing after initial convergence. "
                           "Electronic entropy corrections may be significant.",
                fix="Try degauss = 0.01-0.02 Ry for production",
                param="degauss",
                current=degauss,
                recommended=0.02,
            )
        
        if degauss < 0.001:
            return self._warning(
                message=f"degauss ({degauss} Ry) may be too small",
                explanation="Very small smearing can cause SCF instabilities "
                           "especially for metals with flat Fermi surfaces.",
                fix="Use degauss >= 0.005 Ry",
                param="degauss",
                current=degauss,
                recommended=0.01,
            )
        
        # Check smearing type
        if smearing in ('gaussian', 'gauss') and degauss > 0.02:
            return self._info(
                message="Consider cold smearing for better energy accuracy",
                explanation="Marzari-Vanderbilt cold smearing ('m-v') gives "
                           "better extrapolation to zero smearing than Gaussian.",
            )
        
        return self._pass()
