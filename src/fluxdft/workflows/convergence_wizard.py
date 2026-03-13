"""
Convergence Testing Wizard for FluxDFT.

Automates systematic convergence testing for:
- Energy cutoff (ecutwfc)
- K-point grid density
- Smearing parameter (degauss)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import json
import logging
import subprocess

from PyQt6.QtCore import QObject, pyqtSignal, QThread

logger = logging.getLogger(__name__)


@dataclass
class ConvergenceTest:
    """Definition of a convergence test."""
    parameter: str  # 'ecutwfc', 'kpoints', 'degauss'
    values: List[float]  # Values to test
    reference_value: float  # Reference (final) value for convergence check
    threshold: float = 0.001  # Convergence threshold in Ry or appropriate unit


@dataclass
class ConvergenceResult:
    """Result of a single convergence point."""
    parameter_value: float
    total_energy: float
    forces_max: Optional[float] = None
    stress_max: Optional[float] = None
    cpu_time: Optional[float] = None
    converged: bool = True


@dataclass 
class ConvergenceAnalysis:
    """Analysis of convergence test results."""
    parameter: str
    results: List[ConvergenceResult]
    converged_value: float
    convergence_achieved: bool
    recommended_value: float
    energy_vs_parameter: List[Tuple[float, float]]  # (param, energy)


def generate_ecutwfc_values(
    min_cutoff: float = 20.0,
    max_cutoff: float = 100.0,
    step: float = 10.0
) -> List[float]:
    """Generate energy cutoff values for testing."""
    values = []
    current = min_cutoff
    while current <= max_cutoff:
        values.append(current)
        current += step
    return values


def generate_kpoint_values(
    min_k: int = 2,
    max_k: int = 12,
    step: int = 2
) -> List[Tuple[int, int, int]]:
    """Generate k-point grids for testing."""
    values = []
    current = min_k
    while current <= max_k:
        values.append((current, current, current))
        current += step
    return values


def generate_degauss_values(
    min_deg: float = 0.001,
    max_deg: float = 0.05,
    n_points: int = 6
) -> List[float]:
    """Generate smearing values for testing."""
    step = (max_deg - min_deg) / (n_points - 1)
    return [min_deg + i * step for i in range(n_points)]


class ConvergenceRunner(QThread):
    """Background worker that executes convergence tests."""
    progress = pyqtSignal(int, int, str)  # current, total, message
    point_finished = pyqtSignal(str, float, float)  # parameter, value, energy
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            from ..utils.config import AppConfig
            config = AppConfig()
            
            # config.qe_path is a dict on AppConfig: {'pw': 'pw.x', ...}
            if isinstance(config.qe_path, dict):
                qe_cmd = config.qe_path.get('pw', 'pw.x')
            else:
                qe_cmd = str(config.qe_path) + '/pw.x' if config.qe_path else 'pw.x'

            # Count total jobs
            total_jobs = sum(len(inputs) for inputs in self.wizard.generated_inputs.values())
            if total_jobs == 0:
                self.error.emit("No input files generated.")
                return

            current_job = 0

            for param, param_inputs in self.wizard.generated_inputs.items():
                if self._is_cancelled:
                    break
                    
                for value, input_path in param_inputs.items():
                    if self._is_cancelled:
                        break

                    current_job += 1
                    self.progress.emit(current_job, total_jobs, f"Running {param} = {value}")

                    output_path = input_path.with_suffix('.out')
                    
                    # Run pw.x
                    cmd = f'"{qe_cmd}" -in "{input_path.name}" > "{output_path.name}"'
                    process = subprocess.run(
                        cmd,
                        cwd=str(input_path.parent),
                        shell=True,
                        capture_output=True,
                        text=True
                    )

                    if process.returncode != 0:
                        self.error.emit(f"pw.x failed for {input_path.name}:\n{process.stderr}")
                        continue

                    # Parse output
                    result = self.wizard.parse_output(output_path)
                    if result:
                        result.parameter_value = value
                        if param not in self.wizard.results:
                            self.wizard.results[param] = []
                        self.wizard.results[param].append(result)
                        
                        self.point_finished.emit(param, float(value), float(result.total_energy))

            if not self._is_cancelled:
                self.finished.emit()

        except Exception as e:
            self.error.emit(f"Execution error: {str(e)}")


class ConvergenceWizard(QObject):
    """
    Wizard for automated convergence testing.
    
    Usage:
        wizard = ConvergenceWizard(base_input_path="si.scf.in", work_dir="./conv_test")
        
        # Test ecutwfc
        wizard.add_ecutwfc_test(min=20, max=80, step=10)
        
        # Generate all input files
        inputs = wizard.generate_inputs()
        
        # After running calculations...
        analysis = wizard.analyze_results()
    """
    
    def __init__(
        self,
        base_input_path: Optional[Path] = None,
        base_input_text: Optional[str] = None,
        work_dir: Path = Path("./convergence_test")
    ):
        super().__init__()
        """
        Initialize the wizard.
        
        Args:
            base_input_path: Path to base input file
            base_input_text: Or provide input text directly
            work_dir: Directory for convergence test files
        """
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        self.tests: List[ConvergenceTest] = []
        self.generated_inputs: Dict[str, Dict[float, Path]] = {}
        self.results: Dict[str, List[ConvergenceResult]] = {}
        
        # Load base input
        if base_input_path:
            self.base_input = Path(base_input_path).read_text()
        elif base_input_text:
            self.base_input = base_input_text
        else:
            self.base_input = ""
    
    def add_ecutwfc_test(
        self,
        min_cutoff: float = 20.0,
        max_cutoff: float = 100.0,
        step: float = 10.0,
        threshold: float = 0.001  # Ry/atom
    ):
        """Add energy cutoff convergence test."""
        values = generate_ecutwfc_values(min_cutoff, max_cutoff, step)
        self.tests.append(ConvergenceTest(
            parameter='ecutwfc',
            values=values,
            reference_value=max_cutoff,
            threshold=threshold
        ))
    
    def add_kpoint_test(
        self,
        min_k: int = 2,
        max_k: int = 12,
        step: int = 2,
        threshold: float = 0.001
    ):
        """Add k-point convergence test."""
        grids = generate_kpoint_values(min_k, max_k, step)
        # Store as single number (grid size) for simplicity
        values = [g[0] for g in grids]
        self.tests.append(ConvergenceTest(
            parameter='kpoints',
            values=values,
            reference_value=max_k,
            threshold=threshold
        ))
    
    def add_degauss_test(
        self,
        min_deg: float = 0.001,
        max_deg: float = 0.05,
        n_points: int = 6,
        threshold: float = 0.0005
    ):
        """Add smearing convergence test."""
        values = generate_degauss_values(min_deg, max_deg, n_points)
        self.tests.append(ConvergenceTest(
            parameter='degauss',
            values=values,
            reference_value=min_deg,  # Smaller is more accurate
            threshold=threshold
        ))
    
    def generate_inputs(self) -> Dict[str, List[Path]]:
        """
        Generate input files for all tests.
        
        Returns:
            Dict mapping parameter name to list of input file paths.
        """
        all_inputs = {}
        
        for test in self.tests:
            param = test.parameter
            param_dir = self.work_dir / param
            param_dir.mkdir(exist_ok=True)
            
            inputs = []
            param_inputs = {}
            
            for value in test.values:
                # Modify base input
                modified = self._modify_input(self.base_input, param, value)
                
                # Write to file
                filename = f"{param}_{value:.2f}.in" if isinstance(value, float) else f"{param}_{value}.in"
                filepath = param_dir / filename
                filepath.write_text(modified)
                
                inputs.append(filepath)
                param_inputs[value] = filepath
            
            all_inputs[param] = inputs
            self.generated_inputs[param] = param_inputs
        
        return all_inputs
    
    def _modify_input(self, base_input: str, parameter: str, value: float) -> str:
        """Modify a parameter in the input file."""
        lines = base_input.split('\n')
        modified_lines = []
        
        for line in lines:
            stripped = line.strip().lower()
            
            if parameter == 'ecutwfc' and stripped.startswith('ecutwfc'):
                modified_lines.append(f"  ecutwfc = {value}")
            elif parameter == 'ecutrho' and stripped.startswith('ecutrho'):
                modified_lines.append(f"  ecutrho = {value * 8}")  # 8x ecutwfc
            elif parameter == 'degauss' and stripped.startswith('degauss'):
                modified_lines.append(f"  degauss = {value}")
            elif parameter == 'kpoints' and stripped.startswith('k_points'):
                modified_lines.append(line)
                # The next line should be the k-grid
                continue
            else:
                modified_lines.append(line)
        
        # Handle kpoints specially - replace the grid line after K_POINTS
        if parameter == 'kpoints':
            result = []
            i = 0
            while i < len(modified_lines):
                result.append(modified_lines[i])
                if modified_lines[i].strip().lower().startswith('k_points'):
                    # Skip old k-grid and add new one
                    i += 1
                    if i < len(modified_lines):
                        v = int(value)
                        result.append(f"{v} {v} {v}  0 0 0")
                i += 1
            return '\n'.join(result)
        
        return '\n'.join(modified_lines)
    
    def parse_output(self, output_path: Path) -> Optional[ConvergenceResult]:
        """Parse a QE output file for convergence data."""
        if not output_path.exists():
            return None
        
        try:
            content = output_path.read_text()
            
            # Extract total energy
            energy = None
            for line in content.split('\n'):
                if '!' in line and 'total energy' in line.lower():
                    parts = line.split('=')
                    if len(parts) >= 2:
                        energy_str = parts[-1].replace('Ry', '').strip()
                        energy = float(energy_str)
                        break
            
            if energy is None:
                return None
            
            return ConvergenceResult(
                parameter_value=0,  # Will be set by caller
                total_energy=energy,
                converged=True
            )
            
        except Exception as e:
            logger.error(f"Failed to parse {output_path}: {e}")
            return None
    
    def load_results(self, output_dir: Optional[Path] = None):
        """
        Load results from completed calculations.
        
        Looks for .out files in the work_dir or specified output_dir.
        """
        if output_dir is None:
            output_dir = self.work_dir
        
        for test in self.tests:
            param = test.parameter
            results = []
            
            for value in test.values:
                # Try to find output file
                filename = f"{param}_{value:.2f}.out" if isinstance(value, float) else f"{param}_{value}.out"
                output_path = output_dir / param / filename
                
                result = self.parse_output(output_path)
                if result:
                    result.parameter_value = value
                    results.append(result)
            
            self.results[param] = results
    
    def analyze(self, parameter: str) -> Optional[ConvergenceAnalysis]:
        """
        Analyze convergence for a parameter.
        
        Returns ConvergenceAnalysis with recommended value.
        """
        if parameter not in self.results:
            return None
        
        results = self.results[parameter]
        if len(results) < 2:
            return None
        
        # Sort by parameter value
        results = sorted(results, key=lambda r: r.parameter_value)
        
        # Find where convergence is achieved
        test = next((t for t in self.tests if t.parameter == parameter), None)
        if not test:
            return None
        
        threshold = test.threshold
        
        # Reference = last (highest accuracy) value's energy
        ref_energy = results[-1].total_energy
        
        converged_value = None
        for i, result in enumerate(results):
            diff = abs(result.total_energy - ref_energy)
            if diff < threshold:
                converged_value = result.parameter_value
                break
        
        # Energy vs parameter data for plotting
        energy_vs_param = [(r.parameter_value, r.total_energy) for r in results]
        
        return ConvergenceAnalysis(
            parameter=parameter,
            results=results,
            converged_value=converged_value or results[-1].parameter_value,
            convergence_achieved=converged_value is not None,
            recommended_value=converged_value or results[-1].parameter_value,
            energy_vs_parameter=energy_vs_param
        )
    
    def get_plot_data(self, parameter: str) -> Tuple[List[float], List[float]]:
        """
        Get data for convergence plot.
        
        Returns (x_values, y_values) for plotting.
        """
        analysis = self.analyze(parameter)
        if not analysis:
            return [], []
        
        x = [p[0] for p in analysis.energy_vs_parameter]
        y = [p[1] for p in analysis.energy_vs_parameter]
        
        return x, y
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all convergence tests."""
        summary = {}
        
        for test in self.tests:
            analysis = self.analyze(test.parameter)
            if analysis:
                summary[test.parameter] = {
                    'converged': analysis.convergence_achieved,
                    'recommended': analysis.recommended_value,
                    'tested_range': (min(test.values), max(test.values)),
                    'n_points': len(test.values)
                }
        
        return summary
