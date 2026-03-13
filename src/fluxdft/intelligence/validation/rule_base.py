"""
Base classes for validation rules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List, Set
from pathlib import Path

from .validation_result import ValidationResult, Severity


@dataclass
class ValidationContext:
    """
    Context information for validation rules.
    Contains pre-computed data needed by multiple rules.
    """
    
    # System information
    elements: Set[str] = field(default_factory=set)
    n_atoms: int = 0
    n_electrons: int = 0
    
    # Cell information
    cell_params: Optional[tuple] = None  # (a, b, c) in Angstrom
    cell_angles: Optional[tuple] = None  # (alpha, beta, gamma)
    volume: Optional[float] = None
    
    # Pseudopotential information
    pseudo_types: Dict[str, str] = field(default_factory=dict)  # element -> type (NC/US/PAW)
    pseudo_xc: Dict[str, str] = field(default_factory=dict)     # element -> XC
    pseudo_cutoffs: Dict[str, float] = field(default_factory=dict)  # element -> recommended ecutwfc
    
    # Material classification
    is_metal: Optional[bool] = None
    is_magnetic: Optional[bool] = None
    is_2d: bool = False
    
    # Previous calculation data (if available)
    previous_energy: Optional[float] = None
    previous_gap: Optional[float] = None
    
    @classmethod
    def from_input(cls, input_data) -> "ValidationContext":
        """Build context from PWInput object."""
        ctx = cls()
        
        # Extract elements
        if hasattr(input_data, 'atoms') and input_data.atoms:
            ctx.elements = {atom.symbol for atom in input_data.atoms}
            ctx.n_atoms = len(input_data.atoms)
        
        # Extract cell parameters if available
        if hasattr(input_data, 'cell_parameters') and input_data.cell_parameters:
            cell = input_data.cell_parameters
            if hasattr(cell, 'vectors') and cell.vectors:
                # Calculate a, b, c from vectors
                import numpy as np
                v = np.array(cell.vectors)
                ctx.cell_params = tuple(np.linalg.norm(v[i]) for i in range(3))
        
        # Detect 2D system (large c-axis vacuum)
        if ctx.cell_params and len(ctx.cell_params) == 3:
            a, b, c = ctx.cell_params
            if c > 3 * max(a, b):
                ctx.is_2d = True
        
        # Load pseudo info from files (if accessible)
        ctx._load_pseudo_info(input_data)
        
        return ctx
    
    def _load_pseudo_info(self, input_data):
        """Load pseudopotential information from header."""
        # This would parse .UPF files to extract:
        # - Pseudopotential type (NC, US, PAW)
        # - XC functional used
        # - Recommended cutoffs
        # For now, use defaults
        for el in self.elements:
            self.pseudo_types[el] = "US"  # Assume ultrasoft
            self.pseudo_xc[el] = "PBE"    # Assume PBE
            self.pseudo_cutoffs[el] = 40.0  # Default
    
    def get_pseudo_type(self) -> str:
        """Get the dominant pseudopotential type."""
        if not self.pseudo_types:
            return "NC"
        types = list(self.pseudo_types.values())
        if "PAW" in types:
            return "PAW"
        if "US" in types:
            return "US"
        return "NC"
    
    def detect_material_type(self) -> str:
        """Detect if system is metal, insulator, or semiconductor."""
        if self.is_metal is True:
            return "metal"
        if self.is_metal is False:
            if self.previous_gap and self.previous_gap < 2.0:
                return "semiconductor"
            return "insulator"
        # Unknown - use conservative assumption
        return "unknown"


class ValidationRule(ABC):
    """
    Base class for all validation rules.
    
    Each rule checks a specific aspect of the input and returns
    a ValidationResult indicating pass, warning, or error.
    """
    
    # Rule metadata (override in subclasses)
    rule_id: str = "RULE_000"
    category: str = "general"
    name: str = "Unknown Rule"
    description: str = ""
    enabled: bool = True
    
    def __init__(self):
        pass
    
    @abstractmethod
    def validate(self, input_data, context: ValidationContext) -> ValidationResult:
        """
        Execute the validation rule.
        
        Args:
            input_data: PWInput object
            context: Pre-computed validation context
            
        Returns:
            ValidationResult with severity, message, and suggestions
        """
        pass
    
    def is_applicable(self, input_data) -> bool:
        """
        Check if this rule should be applied to this input.
        Override in subclasses for conditional rules.
        """
        return self.enabled
    
    def _pass(self) -> ValidationResult:
        """Create a passing result."""
        return ValidationResult(
            rule_id=self.rule_id,
            severity=Severity.PASS,
            category=self.category,
            message=f"{self.name}: OK",
        )
    
    def _error(
        self, 
        message: str, 
        explanation: str = "",
        fix: str = "",
        param: str = None,
        current: Any = None,
        recommended: Any = None,
    ) -> ValidationResult:
        """Create an error result."""
        return ValidationResult(
            rule_id=self.rule_id,
            severity=Severity.ERROR,
            category=self.category,
            message=message,
            explanation=explanation,
            fix_suggestion=fix,
            parameter=param,
            current_value=current,
            recommended_value=recommended,
        )
    
    def _warning(
        self,
        message: str,
        explanation: str = "",
        fix: str = "",
        param: str = None,
        current: Any = None,
        recommended: Any = None,
    ) -> ValidationResult:
        """Create a warning result."""
        return ValidationResult(
            rule_id=self.rule_id,
            severity=Severity.WARNING,
            category=self.category,
            message=message,
            explanation=explanation,
            fix_suggestion=fix,
            parameter=param,
            current_value=current,
            recommended_value=recommended,
        )
    
    def _info(self, message: str, explanation: str = "") -> ValidationResult:
        """Create an info result."""
        return ValidationResult(
            rule_id=self.rule_id,
            severity=Severity.INFO,
            category=self.category,
            message=message,
            explanation=explanation,
        )
