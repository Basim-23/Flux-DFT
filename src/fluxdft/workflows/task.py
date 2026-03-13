"""
QE Task Classes for FluxDFT Workflow System.

Defines individual calculation tasks (SCF, NSCF, bands, DOS, relax, etc.)
that can be composed into workflows.

Inspired by abipy's Task classes and atomate2's Maker pattern.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Literal, Callable
from pathlib import Path
from abc import ABC, abstractmethod
import subprocess
import shutil
import time
import os
import logging

from .base import TaskStatus, TaskResult, ConfigurationError, ExecutionError

logger = logging.getLogger(__name__)


@dataclass
class QEInput:
    """
    Quantum ESPRESSO input configuration.
    
    Wraps all input parameters for a QE calculation.
    """
    calculation: str = 'scf'
    prefix: str = 'pwscf'
    pseudo_dir: Optional[Path] = None
    outdir: Optional[Path] = None
    
    # Control namelist
    control: Dict[str, Any] = field(default_factory=dict)
    
    # System namelist
    system: Dict[str, Any] = field(default_factory=dict)
    
    # Electrons namelist
    electrons: Dict[str, Any] = field(default_factory=dict)
    
    # Ions namelist (for relax/md)
    ions: Dict[str, Any] = field(default_factory=dict)
    
    # Cell namelist (for vc-relax)
    cell: Dict[str, Any] = field(default_factory=dict)
    
    # K-points
    kpoints: Dict[str, Any] = field(default_factory=dict)
    
    # Structure (ATOMIC_POSITIONS, CELL_PARAMETERS)
    structure: Optional['Structure'] = None
    
    # Additional cards
    additional_cards: Dict[str, str] = field(default_factory=dict)
    
    def to_input_string(self) -> str:
        """Generate QE input file content."""
        lines = []
        
        # CONTROL
        lines.append("&CONTROL")
        lines.append(f"  calculation = '{self.calculation}'")
        lines.append(f"  prefix = '{self.prefix}'")
        if self.pseudo_dir:
            lines.append(f"  pseudo_dir = '{self.pseudo_dir}'")
        if self.outdir:
            lines.append(f"  outdir = '{self.outdir}'")
        for key, val in self.control.items():
            lines.append(f"  {key} = {self._format_value(val)}")
        lines.append("/\n")
        
        # SYSTEM
        lines.append("&SYSTEM")
        for key, val in self.system.items():
            lines.append(f"  {key} = {self._format_value(val)}")
        lines.append("/\n")
        
        # ELECTRONS
        lines.append("&ELECTRONS")
        for key, val in self.electrons.items():
            lines.append(f"  {key} = {self._format_value(val)}")
        lines.append("/\n")
        
        # IONS (if needed)
        if self.calculation in ('relax', 'md', 'vc-relax'):
            lines.append("&IONS")
            for key, val in self.ions.items():
                lines.append(f"  {key} = {self._format_value(val)}")
            lines.append("/\n")
        
        # CELL (if needed)
        if self.calculation == 'vc-relax':
            lines.append("&CELL")
            for key, val in self.cell.items():
                lines.append(f"  {key} = {self._format_value(val)}")
            lines.append("/\n")
        
        # Cards (ATOMIC_SPECIES, ATOMIC_POSITIONS, etc.)
        for card_name, card_content in self.additional_cards.items():
            lines.append(card_content)
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_value(self, val: Any) -> str:
        """Format value for Fortran namelist."""
        if isinstance(val, bool):
            return ".true." if val else ".false."
        elif isinstance(val, str):
            return f"'{val}'"
        elif isinstance(val, (int, float)):
            return str(val)
        else:
            return str(val)
    
    def write(self, filepath: Path) -> None:
        """Write input file."""
        with open(filepath, 'w') as f:
            f.write(self.to_input_string())


class QETask(ABC):
    """
    Base class for Quantum ESPRESSO tasks.
    
    A task represents a single QE calculation (pw.x, bands.x, dos.x, etc.).
    Tasks can be combined into workflows with dependencies.
    
    Lifecycle:
        1. Created (PENDING)
        2. Dependencies checked (WAITING → READY)
        3. Input written (READY)
        4. Submitted/executed (SUBMITTED → RUNNING)
        5. Output parsed (COMPLETED or FAILED)
    
    Usage:
        >>> task = ScfTask(name="scf", input_data=input_config)
        >>> task.setup(workdir=Path("./calc"))
        >>> result = task.run()
    """
    
    # QE executable for this task type
    executable: str = "pw.x"
    
    # Files to copy from previous task
    files_from_prev: List[str] = []
    
    # Files produced by this task
    output_files: List[str] = []
    
    def __init__(
        self,
        name: str,
        input_data: Optional[QEInput] = None,
        workdir: Optional[Path] = None,
        prev_task: Optional['QETask'] = None,
        parallelization: Optional[Dict[str, int]] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        """
        Initialize task.
        
        Args:
            name: Unique task name.
            input_data: QE input configuration.
            workdir: Working directory.
            prev_task: Previous task for file dependencies.
            parallelization: MPI/OMP settings (nprocs, npool, etc.).
            on_complete: Callback on successful completion.
            on_error: Callback on error.
        """
        self.name = name
        self.input_data = input_data
        self._workdir = workdir
        self.prev_task = prev_task
        self.parallelization = parallelization or {}
        self.on_complete = on_complete
        self.on_error = on_error
        
        # State
        self._status = TaskStatus.PENDING
        self._result: Optional[TaskResult] = None
        self._process: Optional[subprocess.Popen] = None
        self._start_time: Optional[float] = None
    
    @property
    def status(self) -> TaskStatus:
        return self._status
    
    @status.setter
    def status(self, value: TaskStatus):
        logger.debug(f"Task {self.name}: {self._status.value} → {value.value}")
        self._status = value
    
    @property
    def workdir(self) -> Optional[Path]:
        return self._workdir
    
    @workdir.setter
    def workdir(self, path: Path):
        self._workdir = Path(path)
    
    @property
    def input_file(self) -> Path:
        """Path to input file."""
        return self.workdir / f"{self.name}.in"
    
    @property
    def output_file(self) -> Path:
        """Path to output file."""
        return self.workdir / f"{self.name}.out"
    
    @property
    def result(self) -> Optional[TaskResult]:
        return self._result
    
    def setup(self, workdir: Optional[Path] = None) -> None:
        """
        Set up task for execution.
        
        Creates working directory, copies files from previous task,
        and writes input file.
        """
        if workdir:
            self.workdir = workdir
        
        if not self.workdir:
            raise ConfigurationError(f"No workdir set for task {self.name}")
        
        # Create working directory
        self.workdir.mkdir(parents=True, exist_ok=True)
        
        # Copy files from previous task
        if self.prev_task and self.files_from_prev:
            self._copy_from_previous()
        
        # Write input file
        if self.input_data:
            self.input_data.write(self.input_file)
        
        self.status = TaskStatus.READY
        logger.info(f"Task {self.name} set up in {self.workdir}")
    
    def _copy_from_previous(self) -> None:
        """Copy required files from previous task."""
        if not self.prev_task or not self.prev_task.workdir:
            return
        
        for filename in self.files_from_prev:
            src = self.prev_task.workdir / filename
            dst = self.workdir / filename
            
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            elif src.is_file():
                shutil.copy2(src, dst)
            else:
                logger.warning(f"File not found: {src}")
    
    def run(self, dry_run: bool = False) -> TaskResult:
        """
        Execute the task.
        
        Args:
            dry_run: If True, don't actually run, just prepare.
            
        Returns:
            TaskResult with execution outcome.
        """
        if self.status != TaskStatus.READY:
            self.setup()
        
        self.status = TaskStatus.RUNNING
        self._start_time = time.time()
        
        if dry_run:
            self.status = TaskStatus.COMPLETED
            return TaskResult(
                status=TaskStatus.COMPLETED,
                workdir=self.workdir,
                exit_code=0,
            )
        
        try:
            # Build command
            cmd = self._build_command()
            logger.info(f"Running: {' '.join(cmd)}")
            
            # Execute
            with open(self.output_file, 'w') as outfile:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=outfile,
                    stderr=subprocess.STDOUT,
                    cwd=self.workdir,
                )
                exit_code = self._process.wait()
            
            runtime = time.time() - self._start_time
            
            # Parse results
            if exit_code == 0:
                self.status = TaskStatus.COMPLETED
                parsed = self._parse_output()
                
                self._result = TaskResult(
                    status=TaskStatus.COMPLETED,
                    workdir=self.workdir,
                    exit_code=exit_code,
                    runtime_seconds=runtime,
                    outputs=self._collect_outputs(),
                    parsed_data=parsed,
                )
                
                if self.on_complete:
                    self.on_complete(self._result)
            else:
                self.status = TaskStatus.FAILED
                errors = self._extract_errors()
                
                self._result = TaskResult(
                    status=TaskStatus.FAILED,
                    workdir=self.workdir,
                    exit_code=exit_code,
                    runtime_seconds=runtime,
                    errors=errors,
                )
                
                if self.on_error:
                    self.on_error(self._result)
        
        except Exception as e:
            self.status = TaskStatus.FAILED
            self._result = TaskResult(
                status=TaskStatus.FAILED,
                workdir=self.workdir,
                errors=[str(e)],
            )
            
            if self.on_error:
                self.on_error(self._result)
        
        return self._result
    
    def _build_command(self) -> List[str]:
        """Build execution command with parallelization."""
        cmd = []
        
        # MPI
        nprocs = self.parallelization.get('nprocs', 1)
        if nprocs > 1:
            mpirun = self.parallelization.get('mpirun', 'mpirun')
            cmd.extend([mpirun, '-np', str(nprocs)])
        
        # Executable
        cmd.append(self.executable)
        
        # Parallelization flags
        if 'npool' in self.parallelization:
            cmd.extend(['-npool', str(self.parallelization['npool'])])
        if 'ndiag' in self.parallelization:
            cmd.extend(['-ndiag', str(self.parallelization['ndiag'])])
        
        # Input/output
        cmd.extend(['-in', str(self.input_file)])
        
        return cmd
    
    def _collect_outputs(self) -> Dict[str, Path]:
        """Collect paths to output files."""
        outputs = {}
        for filename in self.output_files:
            path = self.workdir / filename
            if path.exists():
                outputs[filename] = path
        return outputs
    
    @abstractmethod
    def _parse_output(self) -> Dict[str, Any]:
        """Parse task-specific output. Override in subclasses."""
        pass
    
    def _extract_errors(self) -> List[str]:
        """Extract error messages from output file."""
        errors = []
        if self.output_file.exists():
            content = self.output_file.read_text()
            for line in content.split('\n'):
                if 'error' in line.lower() or 'crash' in line.lower():
                    errors.append(line.strip())
        return errors
    
    def cancel(self) -> None:
        """Cancel running task."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self.status = TaskStatus.CANCELLED
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', status={self.status.value})"


class ScfTask(QETask):
    """Self-consistent field calculation."""
    
    executable = "pw.x"
    output_files = ["pwscf.save", "pwscf.xml"]
    
    def __init__(self, name: str = "scf", **kwargs):
        super().__init__(name=name, **kwargs)
        if self.input_data:
            self.input_data.calculation = 'scf'
    
    def _parse_output(self) -> Dict[str, Any]:
        """Parse SCF output."""
        data = {}
        if self.output_file.exists():
            content = self.output_file.read_text()
            
            # Total energy
            for line in content.split('\n'):
                if '!    total energy' in line:
                    try:
                        data['total_energy'] = float(line.split()[-2])
                    except (ValueError, IndexError):
                        pass
                elif 'the Fermi energy is' in line:
                    try:
                        data['fermi_energy'] = float(line.split()[-2])
                    except (ValueError, IndexError):
                        pass
                elif 'convergence has been achieved' in line:
                    data['converged'] = True
        
        return data


class NscfTask(QETask):
    """Non-self-consistent field calculation."""
    
    executable = "pw.x"
    files_from_prev = ["pwscf.save"]
    output_files = ["pwscf.save"]
    
    def __init__(self, name: str = "nscf", **kwargs):
        super().__init__(name=name, **kwargs)
        if self.input_data:
            self.input_data.calculation = 'nscf'
    
    def _parse_output(self) -> Dict[str, Any]:
        return {}  # NSCF is intermediate step


class BandsTask(QETask):
    """Band structure calculation."""
    
    executable = "pw.x"
    files_from_prev = ["pwscf.save"]
    output_files = ["pwscf.save", "bands.dat"]
    
    def __init__(self, name: str = "bands", **kwargs):
        super().__init__(name=name, **kwargs)
        if self.input_data:
            self.input_data.calculation = 'bands'
    
    def _parse_output(self) -> Dict[str, Any]:
        data = {'bands_file': self.workdir / 'bands.dat'}
        return data


class DosTask(QETask):
    """Density of states calculation (using dos.x)."""
    
    executable = "dos.x"
    files_from_prev = ["pwscf.save"]
    output_files = ["pwscf.dos"]
    
    def __init__(self, name: str = "dos", **kwargs):
        super().__init__(name=name, **kwargs)
    
    def _parse_output(self) -> Dict[str, Any]:
        data = {'dos_file': self.workdir / 'pwscf.dos'}
        return data


class RelaxTask(QETask):
    """Atomic relaxation calculation."""
    
    executable = "pw.x"
    output_files = ["pwscf.save", "pwscf.xml"]
    
    def __init__(self, name: str = "relax", **kwargs):
        super().__init__(name=name, **kwargs)
        if self.input_data:
            self.input_data.calculation = 'relax'
    
    def _parse_output(self) -> Dict[str, Any]:
        data = {}
        if self.output_file.exists():
            content = self.output_file.read_text()
            
            # Check if converged
            if 'Final energy' in content or 'bfgs converged' in content.lower():
                data['converged'] = True
            
            # Final energy
            for line in reversed(content.split('\n')):
                if '!    total energy' in line:
                    try:
                        data['final_energy'] = float(line.split()[-2])
                    except (ValueError, IndexError):
                        pass
                    break
        
        return data


class VCRelaxTask(QETask):
    """Variable-cell relaxation calculation."""
    
    executable = "pw.x"
    output_files = ["pwscf.save", "pwscf.xml"]
    
    def __init__(self, name: str = "vc-relax", **kwargs):
        super().__init__(name=name, **kwargs)
        if self.input_data:
            self.input_data.calculation = 'vc-relax'
    
    def _parse_output(self) -> Dict[str, Any]:
        data = {}
        if self.output_file.exists():
            content = self.output_file.read_text()
            
            if 'Final energy' in content or 'bfgs converged' in content.lower():
                data['converged'] = True
            
            # Parse final cell
            # TODO: Extract final cell parameters
        
        return data


class PhononTask(QETask):
    """Phonon calculation (using ph.x)."""
    
    executable = "ph.x"
    files_from_prev = ["pwscf.save"]
    output_files = ["phonon.dyn"]
    
    def __init__(self, name: str = "phonon", **kwargs):
        super().__init__(name=name, **kwargs)
    
    def _parse_output(self) -> Dict[str, Any]:
        return {}  # TODO: Parse phonon output
