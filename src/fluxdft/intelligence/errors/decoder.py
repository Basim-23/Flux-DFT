"""
QE Error Decoder for FluxDFT.

Interprets Quantum ESPRESSO runtime errors and provides
actionable diagnostics with fix suggestions.
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class ErrorSolution:
    """A potential fix for a QE error."""
    description: str
    action: str  # "modify_parameter", "delete_files", "restart", "verify"
    parameter: Optional[str] = None
    suggested_value: Optional[Any] = None
    files: Optional[List[str]] = None
    success_rate: float = 0.5


@dataclass
class QEError:
    """Structured QE error information."""
    pattern: str
    error_code: str
    category: str  # "scf", "diag", "io", "parallel", "memory"
    severity: str  # "fatal", "recoverable", "warning"
    title: str
    root_cause: str
    symptoms: List[str] = field(default_factory=list)
    solutions: List[ErrorSolution] = field(default_factory=list)
    related_parameters: List[str] = field(default_factory=list)


@dataclass
class ErrorDiagnosis:
    """Result of error decoding."""
    is_error: bool = False
    recognized: bool = False
    error_code: str = ""
    title: str = ""
    root_cause: str = ""
    solutions: List[ErrorSolution] = field(default_factory=list)
    related_parameters: List[str] = field(default_factory=list)
    all_errors: List[str] = field(default_factory=list)
    raw_output: str = ""
    suggestions: List[str] = field(default_factory=list)


class QEErrorDecoder:
    """
    Interprets QE output and errors to provide actionable diagnostics.
    
    Usage:
        decoder = QEErrorDecoder()
        diagnosis = decoder.decode(output_text, return_code)
        
        if diagnosis.is_error and diagnosis.recognized:
            print(f"Error: {diagnosis.title}")
            print(f"Cause: {diagnosis.root_cause}")
            for sol in diagnosis.solutions:
                print(f"Try: {sol.description}")
    """
    
    # Built-in error database
    ERROR_DATABASE = [
        # SCF Errors
        {
            "pattern": r"Error in routine electrons.*charge is wrong",
            "error_code": "SCF_001",
            "category": "scf",
            "severity": "fatal",
            "title": "Charge Consistency Error",
            "root_cause": "The initial charge density is incompatible with the system. "
                         "Common causes: (1) Wrong number of electrons, (2) Corrupted restart files, "
                         "(3) Incompatible pseudopotentials, (4) tot_charge inconsistent.",
            "solutions": [
                {
                    "description": "Delete old charge density and restart clean",
                    "action": "delete_files",
                    "files": ["*.save/charge-density.dat", "*.wfc*"],
                    "success_rate": 0.7,
                },
                {
                    "description": "Check total electron count (nbnd and pseudopotentials)",
                    "action": "verify",
                    "success_rate": 0.2,
                },
            ],
        },
        {
            "pattern": r"convergence NOT achieved.*scf",
            "error_code": "SCF_002",
            "category": "scf",
            "severity": "fatal",
            "title": "SCF Convergence Failure",
            "root_cause": "Self-consistent field iteration did not converge. "
                         "Often indicates: poorly conditioned system, inappropriate mixing parameters, "
                         "unstable electronic structure, or too few bands.",
            "solutions": [
                {
                    "description": "Reduce mixing strength",
                    "action": "modify_parameter",
                    "parameter": "mixing_beta",
                    "suggested_value": 0.3,
                    "success_rate": 0.5,
                },
                {
                    "description": "Increase maximum SCF iterations",
                    "action": "modify_parameter",
                    "parameter": "electron_maxstep",
                    "suggested_value": 200,
                    "success_rate": 0.4,
                },
                {
                    "description": "Switch diagonalization to CG",
                    "action": "modify_parameter",
                    "parameter": "diagonalization",
                    "suggested_value": "cg",
                    "success_rate": 0.3,
                },
                {
                    "description": "Increase number of bands",
                    "action": "modify_parameter",
                    "parameter": "nbnd",
                    "suggested_value": "increase by 20%",
                    "success_rate": 0.3,
                },
            ],
            "related_parameters": ["mixing_beta", "electron_maxstep", "diagonalization", "nbnd"],
        },
        {
            "pattern": r"too few bands",
            "error_code": "DIAG_001",
            "category": "diag",
            "severity": "fatal",
            "title": "Insufficient Bands",
            "root_cause": "The number of Kohn-Sham states (nbnd) is less than the number "
                         "needed to accommodate all electrons.",
            "solutions": [
                {
                    "description": "Remove nbnd (let QE calculate automatically) or increase it",
                    "action": "modify_parameter",
                    "parameter": "nbnd",
                    "suggested_value": "remove or increase",
                    "success_rate": 0.95,
                },
            ],
        },
        {
            "pattern": r"S matrix not positive definite",
            "error_code": "DIAG_002",
            "category": "diag",
            "severity": "fatal",
            "title": "Overlap Matrix Failure",
            "root_cause": "Atoms are too close together, causing pseudopotential spheres "
                         "to overlap excessively. The overlap matrix becomes singular.",
            "solutions": [
                {
                    "description": "Move atoms apart - check for unrealistic bond lengths",
                    "action": "manual",
                    "success_rate": 0.7,
                },
                {
                    "description": "Check for accidentally duplicated atoms",
                    "action": "verify",
                    "success_rate": 0.2,
                },
            ],
        },
        {
            "pattern": r"negative rho",
            "error_code": "SCF_003",
            "category": "scf",
            "severity": "fatal",
            "title": "Negative Charge Density",
            "root_cause": "Charge density became negative during SCF. Usually indicates "
                         "ecutrho is too low for ultrasoft or PAW pseudopotentials.",
            "solutions": [
                {
                    "description": "Increase density cutoff",
                    "action": "modify_parameter",
                    "parameter": "ecutrho",
                    "suggested_value": "increase to 10× ecutwfc",
                    "success_rate": 0.8,
                },
            ],
        },
        # I/O Errors
        {
            "pattern": r"cannot open.*file",
            "error_code": "IO_001",
            "category": "io",
            "severity": "fatal",
            "title": "File Access Error",
            "root_cause": "QE cannot access a required file. Check paths and permissions.",
            "solutions": [
                {
                    "description": "Verify pseudo_dir and outdir paths exist and are writable",
                    "action": "verify",
                    "success_rate": 0.9,
                },
            ],
        },
        {
            "pattern": r"reading.*xml.*error|xml file not found",
            "error_code": "IO_002",
            "category": "io",
            "severity": "fatal",
            "title": "XML Data File Error",
            "root_cause": "QE cannot read the XML data file. The save directory may be "
                         "corrupted or from an incompatible QE version.",
            "solutions": [
                {
                    "description": "Re-run the previous calculation (SCF) from scratch",
                    "action": "restart",
                    "success_rate": 0.8,
                },
            ],
        },
        # Memory Errors
        {
            "pattern": r"out of memory|cannot allocate",
            "error_code": "MEM_001",
            "category": "memory",
            "severity": "fatal",
            "title": "Out of Memory",
            "root_cause": "Not enough RAM for this calculation. Large systems or many "
                         "k-points require significant memory.",
            "solutions": [
                {
                    "description": "Reduce ecutwfc (if convergence tests allow)",
                    "action": "modify_parameter",
                    "parameter": "ecutwfc",
                    "success_rate": 0.5,
                },
                {
                    "description": "Use more MPI processes (distribute memory)",
                    "action": "manual",
                    "success_rate": 0.7,
                },
                {
                    "description": "Enable disk I/O for wavefunctions (disk_io='low')",
                    "action": "modify_parameter",
                    "parameter": "disk_io",
                    "suggested_value": "low",
                    "success_rate": 0.4,
                },
            ],
        },
        # Parallel Errors
        {
            "pattern": r"mpi|rank.*abort|communicator",
            "error_code": "MPI_001",
            "category": "parallel",
            "severity": "fatal",
            "title": "MPI Communication Error",
            "root_cause": "Parallel communication failed. May be network issues, "
                         "incompatible MPI libraries, or k-point/processor mismatch.",
            "solutions": [
                {
                    "description": "Try running with fewer MPI processes",
                    "action": "manual",
                    "success_rate": 0.5,
                },
                {
                    "description": "Ensure npool divides evenly into k-points",
                    "action": "verify",
                    "success_rate": 0.3,
                },
            ],
        },
        # Relaxation Errors
        {
            "pattern": r"bfgs.*failed|bfgs.*history",
            "error_code": "RELAX_001",
            "category": "relax",
            "severity": "recoverable",
            "title": "BFGS Optimization Problem",
            "root_cause": "Geometry optimizer encountered numerical issues. "
                         "Often happens when forces are very small or erratic.",
            "solutions": [
                {
                    "description": "Restart from current geometry",
                    "action": "restart",
                    "success_rate": 0.6,
                },
                {
                    "description": "Tighten conv_thr for more accurate forces",
                    "action": "modify_parameter",
                    "parameter": "conv_thr",
                    "suggested_value": "1.0d-9",
                    "success_rate": 0.4,
                },
            ],
        },
    ]
    
    def __init__(self, custom_db_path: Optional[Path] = None):
        """
        Initialize the error decoder.
        
        Args:
            custom_db_path: Optional JSON file with additional error patterns
        """
        self.errors: List[QEError] = []
        
        # Load built-in database
        self._load_builtin_db()
        
        # Load custom database if provided
        if custom_db_path and custom_db_path.exists():
            self._load_custom_db(custom_db_path)
        
        # Compile patterns
        self._compile_patterns()
    
    def _load_builtin_db(self):
        """Load the built-in error database."""
        for err_dict in self.ERROR_DATABASE:
            solutions = [
                ErrorSolution(**sol) if isinstance(sol, dict) else sol
                for sol in err_dict.get('solutions', [])
            ]
            
            self.errors.append(QEError(
                pattern=err_dict['pattern'],
                error_code=err_dict['error_code'],
                category=err_dict['category'],
                severity=err_dict['severity'],
                title=err_dict['title'],
                root_cause=err_dict['root_cause'],
                symptoms=err_dict.get('symptoms', []),
                solutions=solutions,
                related_parameters=err_dict.get('related_parameters', []),
            ))
    
    def _load_custom_db(self, path: Path):
        """Load additional errors from JSON file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            for err_dict in data.get('errors', []):
                solutions = [ErrorSolution(**sol) for sol in err_dict.get('solutions', [])]
                self.errors.append(QEError(
                    pattern=err_dict['pattern'],
                    error_code=err_dict['error_code'],
                    category=err_dict['category'],
                    severity=err_dict['severity'],
                    title=err_dict['title'],
                    root_cause=err_dict['root_cause'],
                    solutions=solutions,
                ))
        except Exception as e:
            print(f"Warning: Could not load custom error database: {e}")
    
    def _compile_patterns(self):
        """Compile regex patterns for faster matching."""
        self._compiled = [
            (re.compile(err.pattern, re.IGNORECASE | re.DOTALL), err)
            for err in self.errors
        ]
    
    def decode(self, output: str, return_code: int = 0) -> ErrorDiagnosis:
        """
        Analyze QE output and return structured diagnosis.
        
        Args:
            output: Full text output from QE
            return_code: Exit code from QE process
            
        Returns:
            ErrorDiagnosis with recognized error info and solutions
        """
        # Find all matching error patterns
        matches = []
        for pattern, error in self._compiled:
            if pattern.search(output):
                matches.append(error)
        
        # No matches but non-zero return code
        if not matches and return_code != 0:
            return ErrorDiagnosis(
                is_error=True,
                recognized=False,
                raw_output=self._extract_error_section(output),
                suggestions=[
                    "Check the full output log for details",
                    "Verify input file syntax",
                    "Report unrecognized error to FluxDFT support",
                ],
            )
        
        # No errors
        if not matches:
            return ErrorDiagnosis(is_error=False)
        
        # Prioritize by severity
        severity_order = {'fatal': 0, 'recoverable': 1, 'warning': 2}
        primary_error = min(matches, key=lambda e: severity_order.get(e.severity, 99))
        
        return ErrorDiagnosis(
            is_error=True,
            recognized=True,
            error_code=primary_error.error_code,
            title=primary_error.title,
            root_cause=primary_error.root_cause,
            solutions=primary_error.solutions,
            related_parameters=primary_error.related_parameters,
            all_errors=[e.error_code for e in matches],
        )
    
    def _extract_error_section(self, output: str, context_lines: int = 10) -> str:
        """Extract the relevant error context from full output."""
        lines = output.split('\n')
        
        # Find lines containing error keywords
        error_keywords = ['error', 'crash', 'abort', 'fail', 'stop']
        error_indices = [
            i for i, line in enumerate(lines)
            if any(kw in line.lower() for kw in error_keywords)
        ]
        
        if error_indices:
            # Get context around first error
            start = max(0, error_indices[0] - context_lines)
            end = min(len(lines), error_indices[-1] + context_lines)
            return '\n'.join(lines[start:end])
        
        # No obvious error - return last portion
        return '\n'.join(lines[-30:]) if len(lines) > 30 else output
    
    def get_severity_color(self, severity: str) -> str:
        """Get color for UI display."""
        return {
            'fatal': '#f38ba8',
            'recoverable': '#f9e2af',
            'warning': '#89b4fa',
        }.get(severity, '#cdd6f4')
