"""
Convergence threshold validation rules for FluxDFT.

Validates SCF and relaxation convergence parameters.
"""

from ..rule_base import ValidationRule, ValidationContext
from ..validation_result import ValidationResult, Severity


class ConvThrRule(ValidationRule):
    """
    Validates SCF convergence threshold (conv_thr).
    
    conv_thr should be tight enough for accurate results but not
    so tight that it wastes computational resources.
    
    Recommended:
    - Energy/property calculations: 1e-8 to 1e-10 Ry
    - Relaxation: 1e-6 to 1e-8 Ry (forces are converged anyway)
    """
    
    rule_id = "CONV_001"
    category = "convergence"
    name = "SCF Convergence"
    description = "Check SCF convergence threshold"
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        conv_thr = getattr(input_data, 'conv_thr', None)
        calculation = getattr(input_data, 'calculation', 'scf')
        
        if conv_thr is None:
            # QE default is 1e-6, which may be too loose
            return self._warning(
                message="conv_thr not specified (QE default: 1e-6 Ry)",
                explanation="Default conv_thr may be too loose for accurate energies. "
                           "Consider setting explicitly.",
                fix="Add conv_thr = 1.0d-8 for production calculations",
                param="conv_thr",
                recommended=1.0e-8,
            )
        
        # Check if too loose
        if calculation in ('scf', 'nscf', 'bands') and conv_thr > 1e-6:
            return self._error(
                message=f"conv_thr ({conv_thr:.0e} Ry) is too loose for {calculation}",
                explanation="Loose SCF convergence leads to unreliable total energies "
                           "and band structures. Energy differences will be noisy.",
                fix="Set conv_thr = 1.0d-8 or tighter",
                param="conv_thr",
                current=conv_thr,
                recommended=1.0e-8,
            )
        
        if calculation in ('scf', 'nscf') and conv_thr > 1e-7:
            return self._warning(
                message=f"conv_thr ({conv_thr:.0e} Ry) may be loose for accurate energies",
                explanation="For publication-quality energy differences, 1e-8 is recommended.",
                fix="Consider conv_thr = 1.0d-8",
                param="conv_thr",
                current=conv_thr,
                recommended=1.0e-8,
            )
        
        # Check if too tight (waste of resources)
        if conv_thr < 1e-12:
            return self._info(
                message=f"conv_thr ({conv_thr:.0e} Ry) is very tight",
                explanation="This level of precision is rarely needed and increases "
                           "computational cost. 1e-10 is sufficient for most purposes.",
            )
        
        return self._pass()


class ForcConvThrRule(ValidationRule):
    """
    Validates force convergence threshold for relaxation.
    
    forc_conv_thr should be:
    - 1e-3 Ry/Bohr for rough optimization
    - 1e-4 Ry/Bohr for standard relaxation
    - 1e-5 Ry/Bohr for tight relaxation (phonons)
    """
    
    rule_id = "CONV_002"
    category = "convergence"
    name = "Force Convergence"
    description = "Check force convergence for relaxation"
    
    def is_applicable(self, input_data) -> bool:
        calculation = getattr(input_data, 'calculation', 'scf')
        return calculation in ('relax', 'vc-relax', 'md', 'vc-md')
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        forc_conv_thr = getattr(input_data, 'forc_conv_thr', None)
        calculation = getattr(input_data, 'calculation', 'relax')
        
        if forc_conv_thr is None:
            # QE default is 1e-3 which is loose
            return self._warning(
                message="forc_conv_thr not specified (QE default: 1e-3 Ry/Bohr)",
                explanation="Default force convergence may be too loose for accurate "
                           "relaxed structures, especially for phonon calculations.",
                fix="Add forc_conv_thr = 1.0d-4 for standard relaxations",
                param="forc_conv_thr",
                recommended=1.0e-4,
            )
        
        if forc_conv_thr > 5e-3:
            return self._error(
                message=f"forc_conv_thr ({forc_conv_thr:.0e} Ry/Bohr) is very loose",
                explanation="Relaxation will stop before structure is properly optimized. "
                           "Residual forces will affect subsequent calculations.",
                fix="Set forc_conv_thr = 1.0d-4 or tighter",
                param="forc_conv_thr",
                current=forc_conv_thr,
                recommended=1.0e-4,
            )
        
        if forc_conv_thr > 1e-3:
            return self._warning(
                message=f"forc_conv_thr ({forc_conv_thr:.0e} Ry/Bohr) is loose",
                explanation="May be acceptable for preliminary calculations but not "
                           "for phonons or accurate property calculations.",
                fix="Consider forc_conv_thr = 1.0d-4",
                param="forc_conv_thr",
                current=forc_conv_thr,
                recommended=1.0e-4,
            )
        
        return self._pass()
