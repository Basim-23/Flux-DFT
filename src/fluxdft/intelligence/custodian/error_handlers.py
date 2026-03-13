"""
DFT Error Handlers for FluxDFT.

Inspired by custodian's ErrorHandler pattern, provides QE-specific
error detection and correction strategies.

Each handler:
1. Checks if a specific error occurred in output files
2. Provides a correction action with parameter modifications

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ErrorAction:
    """
    Action to resolve a detected error.
    
    Attributes:
        action_type: Type of action ('modify_input', 'restart', 'skip', 'fatal')
        modifications: Dict of parameter changes to apply
        description: Human-readable description of the fix
        priority: Priority level (lower = more urgent)
    """
    action_type: str
    modifications: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    priority: int = 1
    
    def __post_init__(self):
        valid_types = {'modify_input', 'restart', 'skip', 'fatal', 'reduce_parallelism'}
        if self.action_type not in valid_types:
            raise ValueError(f"action_type must be one of {valid_types}")


class QEErrorHandler(ABC):
    """
    Abstract base class for Quantum ESPRESSO error handling.
    
    Based on custodian.custodian.ErrorHandler pattern.
    
    Subclasses must implement:
        - check(): Detect if error occurred
        - correct(): Provide correction action
    """
    
    # Whether this handler runs during job execution (monitoring)
    is_monitor: bool = False
    
    # Error patterns (regex) this handler recognizes
    error_patterns: List[str] = []
    
    # Human-readable name
    name: str = "Base Handler"
    
    def __init__(self):
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.error_patterns
        ]
    
    @abstractmethod
    def check(self, output_path: Path) -> bool:
        """
        Check if this error occurred.
        
        Args:
            output_path: Path to QE output file
            
        Returns:
            True if error detected, False otherwise
        """
        pass
    
    @abstractmethod
    def correct(self, output_path: Path) -> Optional[ErrorAction]:
        """
        Return correction action for detected error.
        
        Args:
            output_path: Path to QE output file
            
        Returns:
            ErrorAction with fix, or None if cannot fix
        """
        pass
    
    def _read_file(self, path: Path) -> str:
        """Safely read file content."""
        try:
            return path.read_text(errors='ignore')
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
            return ""
    
    def _search_patterns(self, content: str) -> List[re.Match]:
        """Search for all error patterns in content."""
        matches = []
        for pattern in self._compiled_patterns:
            match = pattern.search(content)
            if match:
                matches.append(match)
        return matches


class ConvergenceErrorHandler(QEErrorHandler):
    """
    Handle SCF convergence failures.
    
    Common causes:
    - mixing_beta too high for difficult systems
    - Too few iterations
    - Bad initial guess
    """
    
    name = "SCF Convergence"
    error_patterns = [
        r'convergence\s+NOT\s+achieved',
        r'scf\s+convergence\s+NOT\s+reached',
        r'too\s+many\s+bands',
    ]
    
    def check(self, output_path: Path) -> bool:
        content = self._read_file(output_path)
        return bool(self._search_patterns(content))
    
    def correct(self, output_path: Path) -> Optional[ErrorAction]:
        content = self._read_file(output_path)
        
        # Determine appropriate fix based on context
        modifications = {}
        description = []
        
        # Check current mixing_beta
        mix_match = re.search(r'mixing\s*beta\s*=\s*([\d.]+)', content)
        current_beta = float(mix_match.group(1)) if mix_match else 0.7
        
        if current_beta > 0.2:
            modifications['mixing_beta'] = max(0.1, current_beta - 0.2)
            description.append(f"Reduce mixing_beta from {current_beta:.2f} to {modifications['mixing_beta']:.2f}")
        
        # Increase max iterations
        iter_match = re.search(r'electron_maxstep\s*=\s*(\d+)', content)
        current_max = int(iter_match.group(1)) if iter_match else 100
        
        if current_max < 300:
            modifications['electron_maxstep'] = min(300, current_max + 100)
            description.append(f"Increase electron_maxstep to {modifications['electron_maxstep']}")
        
        # Try different mixing mode
        if 'local-TF' not in content:
            modifications['mixing_mode'] = 'local-TF'
            description.append("Use local-TF mixing mode")
        
        if not modifications:
            return None
        
        return ErrorAction(
            action_type='modify_input',
            modifications=modifications,
            description='; '.join(description),
        )


class WallclockTimeHandler(QEErrorHandler):
    """Handle wallclock time exceeded errors."""
    
    name = "Wallclock Time"
    error_patterns = [
        r'Maximum CPU time exceeded',
        r'wall.*time.*limit',
        r'SIGTERM',
    ]
    
    def check(self, output_path: Path) -> bool:
        content = self._read_file(output_path)
        return bool(self._search_patterns(content))
    
    def correct(self, output_path: Path) -> Optional[ErrorAction]:
        return ErrorAction(
            action_type='restart',
            modifications={
                'startingwfc': 'file',
                'startingpot': 'file',
            },
            description='Restart from checkpoint with extended walltime',
        )


class MemoryErrorHandler(QEErrorHandler):
    """Handle out-of-memory errors."""
    
    name = "Memory Error"
    error_patterns = [
        r'insufficient\s+virtual\s+memory',
        r'out\s+of\s+memory',
        r'cannot\s+allocate\s+memory',
        r'oom',
        r'memory\s+allocation\s+failed',
    ]
    
    def check(self, output_path: Path) -> bool:
        content = self._read_file(output_path)
        return any(p.search(content) for p in self._compiled_patterns)
    
    def correct(self, output_path: Path) -> Optional[ErrorAction]:
        content = self._read_file(output_path)
        
        # Check current parallelization
        npool_match = re.search(r'-npool\s+(\d+)', content)
        current_npool = int(npool_match.group(1)) if npool_match else 1
        
        if current_npool < 4:
            return ErrorAction(
                action_type='reduce_parallelism',
                modifications={'npool': current_npool * 2},
                description=f'Increase k-point parallelization (npool: {current_npool} → {current_npool * 2})',
            )
        
        # Fallback: reduce ecut slightly
        return ErrorAction(
            action_type='modify_input',
            modifications={'ecutwfc_reduction': 5},  # Reduce by 5 Ry
            description='Reduce ecutwfc by 5 Ry to fit in memory',
        )


class DielectricSingularityHandler(QEErrorHandler):
    """
    Handle dielectric matrix singularity (metals without smearing).
    
    Occurs when treating a metal as an insulator without proper
    smearing scheme.
    """
    
    name = "Dielectric Singularity"
    error_patterns = [
        r'dielectric\s+matrix.*singular',
        r'metal.*detected.*without.*smearing',
        r'partial\s+occupations.*tetrahedra',
    ]
    
    def check(self, output_path: Path) -> bool:
        content = self._read_file(output_path)
        return bool(self._search_patterns(content))
    
    def correct(self, output_path: Path) -> Optional[ErrorAction]:
        return ErrorAction(
            action_type='modify_input',
            modifications={
                'occupations': 'smearing',
                'smearing': 'mv',  # Marzari-Vanderbilt cold smearing
                'degauss': 0.02,
            },
            description='Enable Marzari-Vanderbilt cold smearing for metallic system',
        )


class BroadenerErrorHandler(QEErrorHandler):
    """
    Handle DOS broadening issues.
    
    Occurs when degauss is too small or too large for the system.
    """
    
    name = "Broadening Error"
    error_patterns = [
        r'degauss.*too.*small',
        r'degauss.*too.*large',
        r'eigenvalue.*too.*close.*to.*Fermi',
    ]
    
    def check(self, output_path: Path) -> bool:
        content = self._read_file(output_path)
        return bool(self._search_patterns(content))
    
    def correct(self, output_path: Path) -> Optional[ErrorAction]:
        content = self._read_file(output_path)
        
        # Determine if degauss is too small or large
        if 'too small' in content.lower():
            return ErrorAction(
                action_type='modify_input',
                modifications={'degauss': 0.02},
                description='Increase degauss to 0.02 Ry',
            )
        elif 'too large' in content.lower():
            return ErrorAction(
                action_type='modify_input',
                modifications={'degauss': 0.005},
                description='Decrease degauss to 0.005 Ry',
            )
        
        return None


class SymmetryErrorHandler(QEErrorHandler):
    """
    Handle symmetry-related errors.
    
    Can occur with complex structures or magnetic systems.
    """
    
    name = "Symmetry Error"
    error_patterns = [
        r'symmetry.*error',
        r'inconsistent.*symmetry',
        r'symmetry\s+operation.*not\s+found',
        r'wrong.*atomic.*positions',
    ]
    
    def check(self, output_path: Path) -> bool:
        content = self._read_file(output_path)
        return bool(self._search_patterns(content))
    
    def correct(self, output_path: Path) -> Optional[ErrorAction]:
        return ErrorAction(
            action_type='modify_input',
            modifications={
                'nosym': True,
                'noinv': True,
            },
            description='Disable symmetry operations',
            priority=2,  # Try other fixes first
        )


class FFTGridHandler(QEErrorHandler):
    """Handle FFT grid errors."""
    
    name = "FFT Grid Error"
    error_patterns = [
        r'FFT\s+grid.*incompatible',
        r'reduce\s+ecutrho',
        r'FFT.*nr[123].*too.*small',
    ]
    
    def check(self, output_path: Path) -> bool:
        content = self._read_file(output_path)
        return bool(self._search_patterns(content))
    
    def correct(self, output_path: Path) -> Optional[ErrorAction]:
        return ErrorAction(
            action_type='modify_input',
            modifications={
                'ecutrho_multiplier': 4,  # Set ecutrho = 4 * ecutwfc
            },
            description='Adjust ecutrho to 4x ecutwfc for proper FFT grid',
        )


# Handler Registry: All available handlers
HANDLER_REGISTRY = [
    ConvergenceErrorHandler,
    WallclockTimeHandler,
    MemoryErrorHandler,
    DielectricSingularityHandler,
    BroadenerErrorHandler,
    SymmetryErrorHandler,
    FFTGridHandler,
]


def get_all_handlers() -> List[QEErrorHandler]:
    """Instantiate all available error handlers."""
    return [handler_class() for handler_class in HANDLER_REGISTRY]


def check_for_errors(output_path: Path) -> List[Dict]:
    """
    Check output file for all known errors.
    
    Returns list of dicts with:
        - handler_name
        - detected: bool
        - action: ErrorAction or None
    """
    handlers = get_all_handlers()
    results = []
    
    for handler in handlers:
        detected = handler.check(output_path)
        action = handler.correct(output_path) if detected else None
        
        results.append({
            'handler_name': handler.name,
            'detected': detected,
            'action': action,
        })
    
    return results
