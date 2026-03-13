"""
Job Runner for Quantum ESPRESSO.

Handles local and remote execution of QE calculations.
"""

import os
import subprocess
import threading
import queue
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict
from datetime import datetime
from enum import Enum
import shutil


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a QE calculation job."""
    id: str
    name: str
    executable: str  # e.g., "pw.x", "bands.x"
    input_file: Path
    output_file: Path
    work_dir: Path
    
    status: JobStatus = JobStatus.PENDING
    process: Optional[subprocess.Popen] = None
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results
    return_code: Optional[int] = None
    error_message: Optional[str] = None
    
    # Parallelization
    n_procs: int = 1
    n_threads: int = 1
    
    # Callbacks
    on_output: Optional[Callable[[str], None]] = None
    on_complete: Optional[Callable[["Job"], None]] = None


class JobRunner:
    """
    Runs QE calculations locally.
    
    Usage:
        runner = JobRunner(qe_path="/usr/local/bin")
        
        job = runner.create_job(
            name="Silicon SCF",
            executable="pw.x",
            input_file="si.scf.in",
            work_dir="./si_scf"
        )
        
        runner.run_job(job, on_output=print)
    """
    
    def __init__(
        self,
        qe_path: str | Path = "/usr/local/bin",
        mpi_command: str = "mpirun",
    ):
        self.qe_path = Path(qe_path)
        self.mpi_command = mpi_command
        self.jobs: Dict[str, Job] = {}
        self._job_counter = 0
        self._output_queues: Dict[str, queue.Queue] = {}
    
    def _generate_job_id(self) -> str:
        """Generate a unique job ID."""
        self._job_counter += 1
        return f"job_{self._job_counter:06d}"
    
    def find_executable(self, name: str) -> Optional[Path]:
        """Find a QE executable."""
        # Try QE path first
        exe_path = self.qe_path / name
        if exe_path.exists():
            return exe_path
        
        # Try system PATH
        exe = shutil.which(name)
        if exe:
            return Path(exe)
        
        return None
    
    def create_job(
        self,
        name: str,
        executable: str,
        input_file: str | Path,
        work_dir: str | Path,
        output_file: Optional[str | Path] = None,
        n_procs: int = 1,
        n_threads: int = 1,
    ) -> Job:
        """Create a new job."""
        job_id = self._generate_job_id()
        work_dir = Path(work_dir)
        input_file = Path(input_file)
        
        if output_file is None:
            output_file = work_dir / f"{input_file.stem}.out"
        else:
            output_file = Path(output_file)
        
        job = Job(
            id=job_id,
            name=name,
            executable=executable,
            input_file=input_file,
            output_file=output_file,
            work_dir=work_dir,
            n_procs=n_procs,
            n_threads=n_threads,
        )
        
        self.jobs[job_id] = job
        return job
    
    def run_job(
        self,
        job: Job,
        on_output: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[Job], None]] = None,
        blocking: bool = False,
    ) -> None:
        """
        Run a job.
        
        Args:
            job: The job to run
            on_output: Callback for each line of output
            on_complete: Callback when job completes
            blocking: If True, wait for job to complete
        """
        job.on_output = on_output
        job.on_complete = on_complete
        
        if blocking:
            self._run_job_blocking(job)
        else:
            thread = threading.Thread(target=self._run_job_blocking, args=(job,))
            thread.daemon = True
            thread.start()
    
    def _run_job_blocking(self, job: Job) -> None:
        """Run a job and wait for completion."""
        try:
            # Find executable
            exe_path = self.find_executable(job.executable)
            if exe_path is None:
                job.status = JobStatus.FAILED
                job.error_message = f"Executable not found: {job.executable}"
                if job.on_complete:
                    job.on_complete(job)
                return
            
            # Ensure work directory exists
            job.work_dir.mkdir(parents=True, exist_ok=True)
            
            # Build command
            cmd = []
            
            if job.n_procs > 1:
                cmd.extend([self.mpi_command, "-np", str(job.n_procs)])
            
            cmd.append(str(exe_path))
            
            # Set up environment
            env = os.environ.copy()
            env["OMP_NUM_THREADS"] = str(job.n_threads)
            
            # Start process
            job.started_at = datetime.now()
            job.status = JobStatus.RUNNING
            
            with open(job.input_file, "r") as stdin_file:
                with open(job.output_file, "w") as stdout_file:
                    job.process = subprocess.Popen(
                        cmd,
                        stdin=stdin_file,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        cwd=job.work_dir,
                        env=env,
                        text=True,
                        bufsize=1,
                    )
                    
                    # Stream output
                    for line in job.process.stdout:
                        stdout_file.write(line)
                        stdout_file.flush()
                        if job.on_output:
                            job.on_output(line.rstrip())
                    
                    # Wait for completion
                    job.return_code = job.process.wait()
            
            job.completed_at = datetime.now()
            
            if job.return_code == 0:
                job.status = JobStatus.COMPLETED
            else:
                job.status = JobStatus.FAILED
                job.error_message = f"Process exited with code {job.return_code}"
        
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()
        
        finally:
            if job.on_complete:
                job.on_complete(job)
    
    def cancel_job(self, job: Job) -> None:
        """Cancel a running job."""
        if job.status == JobStatus.RUNNING and job.process:
            job.process.terminate()
            try:
                job.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                job.process.kill()
            
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self.jobs.get(job_id)
    
    def list_jobs(self, status: Optional[JobStatus] = None) -> List[Job]:
        """List jobs, optionally filtered by status."""
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs
    
    def get_job_duration(self, job: Job) -> Optional[float]:
        """Get job duration in seconds."""
        if job.started_at is None:
            return None
        
        end_time = job.completed_at or datetime.now()
        return (end_time - job.started_at).total_seconds()


class WorkflowRunner:
    """
    Runs multi-step QE workflows.
    
    Example: Band structure workflow
    1. SCF calculation (pw.x)
    2. NSCF calculation with k-path (pw.x)
    3. Band post-processing (bands.x)
    """
    
    def __init__(self, job_runner: JobRunner):
        self.runner = job_runner
        self.workflows: Dict[str, List[Job]] = {}
    
    def create_band_structure_workflow(
        self,
        name: str,
        work_dir: str | Path,
        scf_input: str,
        nscf_input: str,
        bands_input: str,
        n_procs: int = 1,
    ) -> List[Job]:
        """Create a band structure workflow."""
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        
        jobs = []
        
        # SCF
        scf_job = self.runner.create_job(
            name=f"{name} - SCF",
            executable="pw.x",
            input_file=work_dir / scf_input,
            work_dir=work_dir,
            n_procs=n_procs,
        )
        jobs.append(scf_job)
        
        # NSCF with band path
        nscf_job = self.runner.create_job(
            name=f"{name} - NSCF",
            executable="pw.x",
            input_file=work_dir / nscf_input,
            work_dir=work_dir,
            n_procs=n_procs,
        )
        jobs.append(nscf_job)
        
        # bands.x
        bands_job = self.runner.create_job(
            name=f"{name} - Bands",
            executable="bands.x",
            input_file=work_dir / bands_input,
            work_dir=work_dir,
            n_procs=1,  # bands.x usually runs serial
        )
        jobs.append(bands_job)
        
        self.workflows[name] = jobs
        return jobs
    
    def run_workflow(
        self,
        name: str,
        on_step_complete: Optional[Callable[[Job, int], None]] = None,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Run a workflow sequentially.
        
        Returns True if all steps completed successfully.
        """
        if name not in self.workflows:
            raise ValueError(f"Workflow not found: {name}")
        
        jobs = self.workflows[name]
        
        for i, job in enumerate(jobs):
            self.runner.run_job(
                job,
                on_output=on_output,
                blocking=True,
            )
            
            if on_step_complete:
                on_step_complete(job, i)
            
            if job.status != JobStatus.COMPLETED:
                return False
        
        return True
