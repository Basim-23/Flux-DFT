"""
FluxDFT Custodian Module.

DFT error detection and auto-fixing system inspired by the custodian project.
"""

from .error_handlers import (
    QEErrorHandler,
    ErrorAction,
    ConvergenceErrorHandler,
    WallclockTimeHandler,
    MemoryErrorHandler,
    DielectricSingularityHandler,
    BroadenerErrorHandler,
    SymmetryErrorHandler,
)

from .result_validator import (
    DFTResultValidator,
    ValidationResult,
    ValidationLevel,
)

from .fix_engine import (
    FixSuggestionEngine,
    FixSuggestion,
)

__all__ = [
    # Error Handlers
    'QEErrorHandler',
    'ErrorAction',
    'ConvergenceErrorHandler',
    'WallclockTimeHandler',
    'MemoryErrorHandler',
    'DielectricSingularityHandler',
    'BroadenerErrorHandler',
    'SymmetryErrorHandler',
    # Validators
    'DFTResultValidator',
    'ValidationResult',
    'ValidationLevel',
    # Fix Engine
    'FixSuggestionEngine',
    'FixSuggestion',
]
