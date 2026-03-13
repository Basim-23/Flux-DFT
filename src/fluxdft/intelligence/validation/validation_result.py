"""
Validation result types for FluxDFT.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, List
from enum import Enum
from datetime import datetime


class Severity(Enum):
    """Validation result severity levels."""
    ERROR = "error"       # Will not run or produces garbage
    WARNING = "warning"   # Runs but results are questionable
    INFO = "info"         # Suggestion for improvement
    PASS = "pass"         # Validation passed
    
    @property
    def icon(self) -> str:
        """Get icon for UI display."""
        return {
            Severity.ERROR: "❌",
            Severity.WARNING: "⚠️",
            Severity.INFO: "ℹ️",
            Severity.PASS: "✅",
        }[self]
    
    @property
    def color(self) -> str:
        """Get color for UI display."""
        return {
            Severity.ERROR: "#f38ba8",
            Severity.WARNING: "#f9e2af",
            Severity.INFO: "#89b4fa",
            Severity.PASS: "#a6e3a1",
        }[self]


@dataclass
class ValidationResult:
    """Result of a single validation rule."""
    
    rule_id: str = ""
    severity: Severity = Severity.PASS
    category: str = ""
    message: str = ""
    explanation: str = ""
    fix_suggestion: str = ""
    literature_ref: Optional[str] = None
    parameter: Optional[str] = None
    current_value: Any = None
    recommended_value: Any = None
    
    @property
    def is_error(self) -> bool:
        return self.severity == Severity.ERROR
    
    @property
    def is_warning(self) -> bool:
        return self.severity == Severity.WARNING
    
    @property
    def is_pass(self) -> bool:
        return self.severity == Severity.PASS
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "explanation": self.explanation,
            "fix_suggestion": self.fix_suggestion,
            "parameter": self.parameter,
            "current_value": str(self.current_value) if self.current_value else None,
            "recommended_value": str(self.recommended_value) if self.recommended_value else None,
        }


@dataclass
class ValidationReport:
    """Complete validation report from all rules."""
    
    results: List[ValidationResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.ERROR)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.WARNING)
    
    @property
    def info_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.INFO)
    
    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.severity == Severity.PASS)
    
    @property
    def can_proceed(self) -> bool:
        """Check if execution can proceed (no blocking errors)."""
        return self.error_count == 0
    
    @property
    def is_clean(self) -> bool:
        """Check if there are no errors or warnings."""
        return self.error_count == 0 and self.warning_count == 0
    
    def get_errors(self) -> List[ValidationResult]:
        """Get all error results."""
        return [r for r in self.results if r.severity == Severity.ERROR]
    
    def get_warnings(self) -> List[ValidationResult]:
        """Get all warning results."""
        return [r for r in self.results if r.severity == Severity.WARNING]
    
    def get_by_category(self, category: str) -> List[ValidationResult]:
        """Get results for a specific category."""
        return [r for r in self.results if r.category == category]
    
    def summary(self) -> str:
        """Get a one-line summary."""
        if self.is_clean:
            return "✅ All validations passed"
        elif self.can_proceed:
            return f"⚠️ {self.warning_count} warning(s), can proceed"
        else:
            return f"❌ {self.error_count} error(s), cannot proceed"
