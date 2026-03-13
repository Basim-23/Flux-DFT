"""
Pseudopotential validation rules for FluxDFT.

Validates pseudopotential usage:
- XC functional consistency
- File existence
- Type compatibility
"""

from pathlib import Path
from ..rule_base import ValidationRule, ValidationContext
from ..validation_result import ValidationResult, Severity


class PseudoXCConsistencyRule(ValidationRule):
    """
    Ensures pseudopotential XC matches input_dft.
    
    CRITICAL: Mixing LDA pseudo with GGA functional (or vice versa)
    produces scientifically invalid results.
    
    Based on:
    - Fundamental DFT theory
    - QE documentation warnings
    """
    
    rule_id = "PSEUDO_001"
    category = "pseudo"
    name = "XC Consistency"
    description = "Check pseudopotential XC matches calculation XC"
    
    # XC families that are compatible
    XC_FAMILIES = {
        'lda': {'lda', 'pz', 'vwn', 'pw'},
        'pbe': {'pbe', 'gga', 'pbesol', 'revpbe', 'pw91'},
        'pbesol': {'pbesol', 'pbe', 'gga'},
    }
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        input_dft = getattr(input_data, 'input_dft', None)
        
        if not input_dft:
            # QE defaults to XC from pseudopotential
            return self._pass()
        
        input_xc = input_dft.lower()
        
        # Check each species
        for el, pseudo_xc in context.pseudo_xc.items():
            if not pseudo_xc:
                continue
                
            pseudo_xc = pseudo_xc.lower()
            
            # Check compatibility
            if not self._xc_compatible(input_xc, pseudo_xc):
                return self._error(
                    message=f"XC mismatch: input_dft='{input_dft}' but {el} pseudo uses '{pseudo_xc}'",
                    explanation="Pseudopotentials are generated for specific XC functionals. "
                               "Using a different XC introduces systematic errors in core-valence "
                               "interaction. Results will be unreliable.",
                    fix=f"Either change input_dft to '{pseudo_xc}' or download a "
                       f"'{input_dft}' pseudopotential for {el}",
                    param="input_dft",
                    current=input_dft,
                    recommended=pseudo_xc,
                )
        
        return self._pass()
    
    def _xc_compatible(self, xc1: str, xc2: str) -> bool:
        """Check if two XC functionals are compatible."""
        xc1, xc2 = xc1.lower(), xc2.lower()
        
        if xc1 == xc2:
            return True
        
        # Check family membership
        for family, members in self.XC_FAMILIES.items():
            if xc1 in members and xc2 in members:
                return True
        
        return False


class PseudoExistsRule(ValidationRule):
    """
    Validates that pseudopotential files exist.
    """
    
    rule_id = "PSEUDO_002"
    category = "pseudo"
    name = "Pseudopotential Files"
    description = "Check that pseudopotential files are accessible"
    
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        pseudo_dir = getattr(input_data, 'pseudo_dir', None)
        species = getattr(input_data, 'species', [])
        
        if not species:
            return self._warning(
                message="No atomic species defined",
                explanation="ATOMIC_SPECIES card is required.",
            )
        
        missing = []
        for sp in species:
            pp_file = getattr(sp, 'pseudopotential', None)
            if not pp_file:
                missing.append(sp.symbol if hasattr(sp, 'symbol') else str(sp))
                continue
            
            # Check if file exists (if we know pseudo_dir)
            if pseudo_dir:
                full_path = Path(pseudo_dir) / pp_file
                if not full_path.exists():
                    missing.append(f"{sp.symbol}: {pp_file}")
        
        if missing:
            return self._error(
                message=f"Missing pseudopotential files: {', '.join(missing)}",
                explanation="Calculation will fail without pseudopotential files.",
                fix="Download required pseudopotentials or check pseudo_dir path",
                param="pseudo_dir",
                current=pseudo_dir,
            )
        
        return self._pass()
