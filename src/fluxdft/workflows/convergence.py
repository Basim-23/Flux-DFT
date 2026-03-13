"""
Convergence Testing Module for FluxDFT.

Systematic testing of DFT convergence parameters:
- Energy cutoff (ecutwfc)
- K-point grid
- Smearing parameters
- Cell size

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class ConvergencePoint:
    """A single point in convergence test."""
    parameter_value: float
    total_energy: float  # eV/atom
    cpu_time: float  # seconds
    memory: float  # MB
    forces_max: Optional[float] = None
    stress_max: Optional[float] = None
    scf_iterations: int = 0
    converged: bool = True


@dataclass
class ConvergenceResult:
    """Complete convergence test result."""
    parameter_name: str
    parameter_unit: str
    points: List[ConvergencePoint]
    threshold: float  # meV/atom
    
    # Best value
    converged_value: Optional[float] = None
    convergence_idx: Optional[int] = None
    
    def __post_init__(self):
        if not self.converged_value:
            self._find_convergence()
    
    def _find_convergence(self):
        """Find the converged parameter value."""
        if len(self.points) < 2:
            return
        
        # Sort by parameter value
        sorted_points = sorted(self.points, key=lambda p: p.parameter_value)
        
        # Find first point where energy difference is below threshold
        for i in range(1, len(sorted_points)):
            delta_E = abs(sorted_points[i].total_energy - sorted_points[i-1].total_energy) * 1000  # Convert to meV
            
            if delta_E < self.threshold:
                self.converged_value = sorted_points[i-1].parameter_value
                self.convergence_idx = i - 1
                return
        
        # Not converged, use highest value
        self.converged_value = sorted_points[-1].parameter_value
        self.convergence_idx = len(sorted_points) - 1
    
    @property
    def parameter_values(self) -> np.ndarray:
        """Get parameter values as array."""
        return np.array([p.parameter_value for p in self.points])
    
    @property
    def energies(self) -> np.ndarray:
        """Get energies as array."""
        return np.array([p.total_energy for p in self.points])
    
    @property
    def times(self) -> np.ndarray:
        """Get CPU times as array."""
        return np.array([p.cpu_time for p in self.points])
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'parameter_name': self.parameter_name,
            'parameter_unit': self.parameter_unit,
            'threshold_meV': self.threshold,
            'converged_value': self.converged_value,
            'points': [
                {
                    'value': p.parameter_value,
                    'energy': p.total_energy,
                    'time': p.cpu_time,
                    'scf_iter': p.scf_iterations,
                }
                for p in self.points
            ],
        }
    
    def summarize(self) -> str:
        """Generate summary string."""
        lines = ["=" * 50]
        lines.append(f"Convergence Test: {self.parameter_name}")
        lines.append("=" * 50)
        lines.append(f"Threshold: {self.threshold:.1f} meV/atom")
        lines.append(f"Converged value: {self.converged_value} {self.parameter_unit}")
        lines.append("")
        lines.append(f"{'Value':>10}  {'Energy (eV)':>12}  {'Time (s)':>10}  {'Δ (meV)':>10}")
        lines.append("-" * 50)
        
        sorted_points = sorted(self.points, key=lambda p: p.parameter_value)
        for i, p in enumerate(sorted_points):
            if i > 0:
                delta = abs(p.total_energy - sorted_points[i-1].total_energy) * 1000
            else:
                delta = 0
            converged_marker = " *" if i == self.convergence_idx else ""
            lines.append(
                f"{p.parameter_value:>10.1f}  {p.total_energy:>12.6f}  {p.cpu_time:>10.1f}  {delta:>10.2f}{converged_marker}"
            )
        
        lines.append("=" * 50)
        return "\n".join(lines)
    
    def plot(self, ax=None):
        """Plot convergence curve."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.error("matplotlib required for plotting")
            return
        
        if ax is None:
            fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        else:
            axes = [ax, None]
        
        # Sort data
        sorted_idx = np.argsort(self.parameter_values)
        x = self.parameter_values[sorted_idx]
        y = self.energies[sorted_idx]
        t = self.times[sorted_idx]
        
        # Energy plot
        axes[0].plot(x, y, 'o-', color='#2563eb', markersize=8)
        if self.converged_value:
            axes[0].axvline(self.converged_value, color='green', linestyle='--', 
                          label=f'Converged: {self.converged_value}')
        axes[0].set_xlabel(f'{self.parameter_name} ({self.parameter_unit})')
        axes[0].set_ylabel('Energy (eV/atom)')
        axes[0].legend()
        
        # Time plot
        if axes[1] is not None:
            axes[1].bar(x, t, color='#10b981', alpha=0.7)
            axes[1].set_xlabel(f'{self.parameter_name} ({self.parameter_unit})')
            axes[1].set_ylabel('CPU Time (s)')
        
        plt.tight_layout()
        return axes


class ConvergenceTestRunner:
    """
    Automatic convergence testing.
    
    Runs systematic tests for cutoff and k-points.
    
    Usage:
        >>> from fluxdft.io import QEInputGenerator
        >>> 
        >>> runner = ConvergenceTestRunner(
        ...     base_generator=gen,
        ...     work_dir="./convergence",
        ... )
        >>> 
        >>> # Test ecutwfc
        >>> result = runner.test_ecutwfc(
        ...     values=[30, 40, 50, 60, 70, 80],
        ...     threshold=1.0,  # meV/atom
        ... )
        >>> print(result.converged_value)
    """
    
    def __init__(
        self,
        base_generator: 'QEInputGenerator',
        work_dir: Union[str, Path],
        pw_command: str = "pw.x",
        natoms: int = 1,
    ):
        """
        Initialize runner.
        
        Args:
            base_generator: Base input generator
            work_dir: Working directory
            pw_command: Command for pw.x
            natoms: Number of atoms for per-atom energy
        """
        self.base_generator = base_generator
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.pw_command = pw_command
        self.natoms = natoms
    
    def test_ecutwfc(
        self,
        values: List[float],
        threshold: float = 1.0,  # meV/atom
        ecutrho_factor: float = 8.0,
    ) -> ConvergenceResult:
        """
        Test energy cutoff convergence.
        
        Args:
            values: List of ecutwfc values to test (Ry)
            threshold: Convergence threshold in meV/atom
            ecutrho_factor: ecutrho = ecutwfc * factor
            
        Returns:
            ConvergenceResult
        """
        points = []
        
        for ecutwfc in values:
            logger.info(f"Testing ecutwfc = {ecutwfc} Ry")
            
            # Create input
            gen = self._copy_generator()
            gen.ecutwfc = ecutwfc
            gen.ecutrho = ecutwfc * ecutrho_factor
            
            # Run calculation
            result = self._run_calculation(f"ecutwfc_{int(ecutwfc)}", gen)
            
            if result:
                points.append(ConvergencePoint(
                    parameter_value=ecutwfc,
                    total_energy=result['energy'] / self.natoms,
                    cpu_time=result['time'],
                    memory=result.get('memory', 0),
                    scf_iterations=result.get('scf_iter', 0),
                ))
        
        return ConvergenceResult(
            parameter_name='ecutwfc',
            parameter_unit='Ry',
            points=points,
            threshold=threshold,
        )
    
    def test_kpoints(
        self,
        grids: List[Tuple[int, int, int]],
        threshold: float = 1.0,
    ) -> ConvergenceResult:
        """
        Test k-point grid convergence.
        
        Args:
            grids: List of k-point grids to test
            threshold: Convergence threshold in meV/atom
            
        Returns:
            ConvergenceResult
        """
        from ..io.qe_input import KPointsGrid
        
        points = []
        
        for kgrid in grids:
            k_density = kgrid[0]  # Use first value as proxy
            logger.info(f"Testing kgrid = {kgrid}")
            
            gen = self._copy_generator()
            gen.kpoints = KPointsGrid(*kgrid, 1, 1, 1)
            
            result = self._run_calculation(f"kpts_{kgrid[0]}x{kgrid[1]}x{kgrid[2]}", gen)
            
            if result:
                points.append(ConvergencePoint(
                    parameter_value=k_density,
                    total_energy=result['energy'] / self.natoms,
                    cpu_time=result['time'],
                    memory=result.get('memory', 0),
                    scf_iterations=result.get('scf_iter', 0),
                ))
        
        return ConvergenceResult(
            parameter_name='k-points',
            parameter_unit='per axis',
            points=points,
            threshold=threshold,
        )
    
    def test_smearing(
        self,
        values: List[float],
        threshold: float = 1.0,
    ) -> ConvergenceResult:
        """
        Test smearing parameter convergence.
        
        Args:
            values: List of degauss values (Ry)
            threshold: Convergence threshold in meV/atom
            
        Returns:
            ConvergenceResult
        """
        points = []
        
        for degauss in values:
            logger.info(f"Testing degauss = {degauss} Ry")
            
            gen = self._copy_generator()
            gen.degauss = degauss
            
            result = self._run_calculation(f"smear_{degauss:.4f}", gen)
            
            if result:
                points.append(ConvergencePoint(
                    parameter_value=degauss * 1000,  # Convert to mRy for display
                    total_energy=result['energy'] / self.natoms,
                    cpu_time=result['time'],
                    memory=result.get('memory', 0),
                ))
        
        return ConvergenceResult(
            parameter_name='degauss',
            parameter_unit='mRy',
            points=points,
            threshold=threshold,
        )
    
    def _copy_generator(self) -> 'QEInputGenerator':
        """Create a copy of the base generator."""
        import copy
        return copy.deepcopy(self.base_generator)
    
    def _run_calculation(
        self,
        name: str,
        generator: 'QEInputGenerator',
    ) -> Optional[Dict]:
        """
        Run a single calculation.
        
        Returns:
            Dictionary with energy, time, etc. or None if failed
        """
        import subprocess
        import time
        
        calc_dir = self.work_dir / name
        calc_dir.mkdir(exist_ok=True)
        
        # Write input
        input_file = calc_dir / "scf.in"
        generator.write(input_file)
        
        # Run calculation
        start_time = time.time()
        
        try:
            process = subprocess.run(
                f"{self.pw_command} < scf.in > scf.out 2>&1",
                shell=True,
                cwd=calc_dir,
                capture_output=True,
            )
            
            elapsed = time.time() - start_time
            
            # Parse output
            output_file = calc_dir / "scf.out"
            if output_file.exists():
                from ..io import QEOutputParser
                parser = QEOutputParser()
                parsed = parser.parse(output_file)
                
                if parsed.job_done:
                    return {
                        'energy': parsed.total_energy_ev,
                        'time': elapsed,
                        'scf_iter': len(parsed.scf_iterations),
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Calculation failed: {e}")
            return None
    
    def run_all(
        self,
        ecutwfc_values: Optional[List[float]] = None,
        kpoint_grids: Optional[List[Tuple[int, int, int]]] = None,
        threshold: float = 1.0,
    ) -> Dict[str, ConvergenceResult]:
        """
        Run all convergence tests.
        
        Args:
            ecutwfc_values: Cutoff values to test
            kpoint_grids: K-point grids to test
            threshold: Convergence threshold
            
        Returns:
            Dictionary of results
        """
        results = {}
        
        if ecutwfc_values is None:
            ecutwfc_values = [30, 40, 50, 60, 70, 80, 90, 100]
        
        if kpoint_grids is None:
            kpoint_grids = [
                (4, 4, 4), (6, 6, 6), (8, 8, 8),
                (10, 10, 10), (12, 12, 12), (14, 14, 14),
            ]
        
        # Test ecutwfc first
        results['ecutwfc'] = self.test_ecutwfc(ecutwfc_values, threshold)
        
        # Update base generator with converged ecutwfc
        if results['ecutwfc'].converged_value:
            self.base_generator.ecutwfc = results['ecutwfc'].converged_value
        
        # Test k-points
        results['kpoints'] = self.test_kpoints(kpoint_grids, threshold)
        
        return results
    
    def generate_report(
        self,
        results: Dict[str, ConvergenceResult],
        output_file: Optional[Path] = None,
    ) -> str:
        """
        Generate convergence test report.
        
        Args:
            results: Dictionary of results
            output_file: Optional output file
            
        Returns:
            Report string
        """
        lines = ["=" * 60]
        lines.append("         CONVERGENCE TEST REPORT")
        lines.append("=" * 60)
        lines.append("")
        
        for name, result in results.items():
            lines.append(result.summarize())
            lines.append("")
        
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 60)
        
        for name, result in results.items():
            lines.append(f"  {name}: {result.converged_value} {result.parameter_unit}")
        
        lines.append("")
        lines.append("=" * 60)
        
        report = "\n".join(lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
        
        return report
