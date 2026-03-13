"""
Workflow Execution Engine for FluxDFT.

Manages the execution of DFT calculation workflows with:
- Job queuing and dependency resolution
- Status monitoring and callbacks
- Error handling and recovery
- Checkpointing and restart

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from datetime import datetime
import threading
import time
import json
import logging

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Status of a calculation job."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class JobResult:
    """Result of a completed job."""
    status: JobStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    output_dir: Optional[Path] = None
    output_files: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    exit_code: int = 0
    
    @property
    def elapsed_time(self) -> Optional[float]:
        """Elapsed time in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def is_success(self) -> bool:
        return self.status == JobStatus.COMPLETED


@dataclass
class Job:
    """
    A single calculation job.
    """
    job_id: str
    name: str
    work_dir: Path
    input_file: str
    command: str
    
    # Status
    status: JobStatus = JobStatus.PENDING
    result: Optional[JobResult] = None
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    
    # Callbacks
    on_start: Optional[Callable] = None
    on_complete: Optional[Callable] = None
    on_error: Optional[Callable] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Serialize job to dictionary."""
        return {
            'job_id': self.job_id,
            'name': self.name,
            'work_dir': str(self.work_dir),
            'input_file': self.input_file,
            'command': self.command,
            'status': self.status.value,
            'depends_on': self.depends_on,
            'created_at': self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Job':
        """Deserialize job from dictionary."""
        return cls(
            job_id=data['job_id'],
            name=data['name'],
            work_dir=Path(data['work_dir']),
            input_file=data['input_file'],
            command=data['command'],
            status=JobStatus(data.get('status', 'pending')),
            depends_on=data.get('depends_on', []),
            created_at=datetime.fromisoformat(data['created_at']),
        )


class ExecutionEngine:
    """
    Workflow execution engine.
    
    Manages job submission, monitoring, and completion handling.
    
    Features:
        - DAG-based dependency resolution
        - Parallel job execution
        - Real-time status monitoring
        - Checkpoint/restart capability
        - Multiple scheduler backends
    
    Usage:
        >>> engine = ExecutionEngine(scheduler='local')
        >>> 
        >>> # Add jobs
        >>> engine.add_job(scf_job)
        >>> engine.add_job(bands_job, depends_on=['scf'])
        >>> 
        >>> # Run workflow
        >>> engine.run()
        >>> 
        >>> # Check status
        >>> print(engine.get_status())
    """
    
    def __init__(
        self,
        scheduler: str = 'local',
        max_parallel: int = 4,
        checkpoint_file: Optional[Path] = None,
    ):
        """
        Initialize engine.
        
        Args:
            scheduler: Scheduler type ('local', 'slurm', 'pbs')
            max_parallel: Maximum parallel jobs
            checkpoint_file: File for checkpointing
        """
        self.scheduler = scheduler
        self.max_parallel = max_parallel
        self.checkpoint_file = checkpoint_file
        
        self.jobs: Dict[str, Job] = {}
        self.job_order: List[str] = []
        self.running_jobs: Dict[str, threading.Thread] = {}
        
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # Callbacks
        self.on_job_start: Optional[Callable] = None
        self.on_job_complete: Optional[Callable] = None
        self.on_workflow_complete: Optional[Callable] = None
    
    def add_job(
        self,
        job: Job,
        depends_on: Optional[List[str]] = None,
    ) -> str:
        """
        Add a job to the workflow.
        
        Args:
            job: Job to add
            depends_on: Job IDs this job depends on
            
        Returns:
            Job ID
        """
        with self._lock:
            if depends_on:
                job.depends_on = depends_on
            
            self.jobs[job.job_id] = job
            self.job_order.append(job.job_id)
        
        return job.job_id
    
    def _get_ready_jobs(self) -> List[str]:
        """Get jobs that are ready to run (dependencies met)."""
        ready = []
        
        for job_id, job in self.jobs.items():
            if job.status != JobStatus.PENDING:
                continue
            
            # Check dependencies
            deps_met = True
            for dep_id in job.depends_on:
                if dep_id not in self.jobs:
                    logger.warning(f"Unknown dependency: {dep_id}")
                    continue
                
                dep_job = self.jobs[dep_id]
                if dep_job.status != JobStatus.COMPLETED:
                    deps_met = False
                    break
            
            if deps_met:
                ready.append(job_id)
        
        return ready
    
    def _run_job(self, job: Job):
        """Run a single job."""
        import subprocess
        
        job.status = JobStatus.RUNNING
        job.result = JobResult(status=JobStatus.RUNNING)
        job.result.start_time = datetime.now()
        
        if job.on_start:
            job.on_start(job)
        if self.on_job_start:
            self.on_job_start(job)
        
        logger.info(f"Starting job: {job.name}")
        
        try:
            # Run the command
            process = subprocess.run(
                job.command,
                shell=True,
                cwd=job.work_dir,
                capture_output=True,
                text=True,
            )
            
            job.result.end_time = datetime.now()
            job.result.exit_code = process.returncode
            
            if process.returncode == 0:
                job.status = JobStatus.COMPLETED
                job.result.status = JobStatus.COMPLETED
                
                # Find output files
                job.result.output_dir = job.work_dir
                job.result.output_files = [
                    f.name for f in job.work_dir.iterdir() if f.is_file()
                ]
                
                logger.info(f"Job completed: {job.name}")
                
            else:
                job.status = JobStatus.FAILED
                job.result.status = JobStatus.FAILED
                job.result.error_message = process.stderr
                
                logger.error(f"Job failed: {job.name}\n{process.stderr}")
                
                if job.on_error:
                    job.on_error(job, process.stderr)
        
        except Exception as e:
            job.status = JobStatus.FAILED
            job.result.status = JobStatus.FAILED
            job.result.error_message = str(e)
            job.result.end_time = datetime.now()
            
            logger.exception(f"Job exception: {job.name}")
            
            if job.on_error:
                job.on_error(job, str(e))
        
        finally:
            if job.on_complete:
                job.on_complete(job)
            if self.on_job_complete:
                self.on_job_complete(job)
            
            # Remove from running jobs
            with self._lock:
                if job.job_id in self.running_jobs:
                    del self.running_jobs[job.job_id]
            
            # Checkpoint
            self._save_checkpoint()
    
    def run(self, blocking: bool = True):
        """
        Run the workflow.
        
        Args:
            blocking: Wait for completion
        """
        logger.info("Starting workflow execution")
        
        if blocking:
            self._run_loop()
        else:
            thread = threading.Thread(target=self._run_loop)
            thread.start()
    
    def _run_loop(self):
        """Main execution loop."""
        while not self._stop_event.is_set():
            # Check if all jobs are done
            all_done = all(
                job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
                for job in self.jobs.values()
            )
            
            if all_done:
                break
            
            # Get ready jobs
            ready = self._get_ready_jobs()
            
            # Submit jobs up to max_parallel
            with self._lock:
                while ready and len(self.running_jobs) < self.max_parallel:
                    job_id = ready.pop(0)
                    job = self.jobs[job_id]
                    
                    job.status = JobStatus.QUEUED
                    job.submitted_at = datetime.now()
                    
                    thread = threading.Thread(target=self._run_job, args=(job,))
                    self.running_jobs[job_id] = thread
                    thread.start()
            
            # Wait a bit before checking again
            time.sleep(1)
        
        # Wait for running jobs
        for thread in list(self.running_jobs.values()):
            thread.join()
        
        logger.info("Workflow execution completed")
        
        if self.on_workflow_complete:
            self.on_workflow_complete(self)
    
    def stop(self):
        """Stop workflow execution."""
        self._stop_event.set()
    
    def get_status(self) -> Dict[str, Any]:
        """Get workflow status summary."""
        status_counts = {s.value: 0 for s in JobStatus}
        
        for job in self.jobs.values():
            status_counts[job.status.value] += 1
        
        return {
            'total_jobs': len(self.jobs),
            'status_counts': status_counts,
            'running': list(self.running_jobs.keys()),
            'completed': [j.job_id for j in self.jobs.values() if j.status == JobStatus.COMPLETED],
            'failed': [j.job_id for j in self.jobs.values() if j.status == JobStatus.FAILED],
        }
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self.jobs.get(job_id)
    
    def _save_checkpoint(self):
        """Save checkpoint to file."""
        if not self.checkpoint_file:
            return
        
        data = {
            'jobs': {jid: job.to_dict() for jid, job in self.jobs.items()},
            'job_order': self.job_order,
            'timestamp': datetime.now().isoformat(),
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_checkpoint(self, checkpoint_file: Path) -> bool:
        """
        Load workflow state from checkpoint.
        
        Args:
            checkpoint_file: Checkpoint file path
            
        Returns:
            True if successful
        """
        if not checkpoint_file.exists():
            return False
        
        with open(checkpoint_file, 'r') as f:
            data = json.load(f)
        
        self.jobs = {
            jid: Job.from_dict(jdata) for jid, jdata in data['jobs'].items()
        }
        self.job_order = data['job_order']
        
        logger.info(f"Loaded checkpoint with {len(self.jobs)} jobs")
        return True
    
    def reset_failed_jobs(self):
        """Reset failed jobs to pending."""
        for job in self.jobs.values():
            if job.status == JobStatus.FAILED:
                job.status = JobStatus.PENDING
                job.result = None


class WorkflowRunner:
    """
    High-level workflow runner.
    
    Provides simple interface for common DFT workflows.
    
    Usage:
        >>> runner = WorkflowRunner(work_dir="./calculations")
        >>> runner.run_scf(structure, ecutwfc=60, kgrid=(8, 8, 8))
        >>> runner.run_bands(kpath)
        >>> runner.wait()
    """
    
    def __init__(
        self,
        work_dir: Union[str, Path],
        pw_command: str = "mpirun -np 4 pw.x",
        pp_command: str = "mpirun -np 4 pp.x",
        bands_command: str = "mpirun -np 4 bands.x",
    ):
        """
        Initialize runner.
        
        Args:
            work_dir: Working directory
            pw_command: Command for pw.x
            pp_command: Command for pp.x
            bands_command: Command for bands.x
        """
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        self.pw_command = pw_command
        self.pp_command = pp_command
        self.bands_command = bands_command
        
        self.engine = ExecutionEngine(checkpoint_file=self.work_dir / "checkpoint.json")
        self._job_counter = 0
    
    def _next_job_id(self, prefix: str = "job") -> str:
        """Generate next job ID."""
        self._job_counter += 1
        return f"{prefix}_{self._job_counter:03d}"
    
    def run_scf(
        self,
        input_content: str,
        name: str = "scf",
    ) -> str:
        """
        Run SCF calculation.
        
        Args:
            input_content: QE input file content
            name: Job name
            
        Returns:
            Job ID
        """
        job_dir = self.work_dir / name
        job_dir.mkdir(exist_ok=True)
        
        input_file = job_dir / f"{name}.in"
        with open(input_file, 'w') as f:
            f.write(input_content)
        
        job = Job(
            job_id=self._next_job_id("scf"),
            name=name,
            work_dir=job_dir,
            input_file=f"{name}.in",
            command=f"{self.pw_command} < {name}.in > {name}.out 2>&1",
        )
        
        return self.engine.add_job(job)
    
    def run_bands(
        self,
        input_content: str,
        scf_job_id: str,
        name: str = "bands",
    ) -> str:
        """
        Run bands calculation.
        
        Args:
            input_content: QE input file content
            scf_job_id: SCF job this depends on
            name: Job name
            
        Returns:
            Job ID
        """
        job_dir = self.work_dir / name
        job_dir.mkdir(exist_ok=True)
        
        input_file = job_dir / f"{name}.in"
        with open(input_file, 'w') as f:
            f.write(input_content)
        
        job = Job(
            job_id=self._next_job_id("bands"),
            name=name,
            work_dir=job_dir,
            input_file=f"{name}.in",
            command=f"{self.pw_command} < {name}.in > {name}.out 2>&1",
        )
        
        return self.engine.add_job(job, depends_on=[scf_job_id])
    
    def run(self):
        """Start workflow execution."""
        self.engine.run(blocking=False)
    
    def wait(self):
        """Wait for workflow completion."""
        self.engine.run(blocking=True)
    
    def get_status(self) -> Dict:
        """Get workflow status."""
        return self.engine.get_status()
