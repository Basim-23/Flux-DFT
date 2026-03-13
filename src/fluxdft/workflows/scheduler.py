"""
Workflow Schedulers for FluxDFT.

Provides adapters for different execution environments:
- Local (direct execution)
- Slurm (HPC clusters)
- PBS/Torque
- SGE

Inspired by abipy's qadapters.py

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
from abc import ABC, abstractmethod
import subprocess
import os
import re
import time
import logging

from .base import TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class JobInfo:
    """
    Information about a submitted job.
    
    Attributes:
        job_id: Queue system job ID
        name: Job name
        status: Current status
        queue: Queue/partition name
        nodes: Number of nodes
        walltime: Requested walltime
        submit_time: Submission timestamp
    """
    job_id: str
    name: str
    status: str = "unknown"
    queue: Optional[str] = None
    nodes: int = 1
    walltime: Optional[str] = None
    submit_time: Optional[str] = None
    
    @property
    def is_running(self) -> bool:
        return self.status.lower() in ('running', 'r')
    
    @property
    def is_pending(self) -> bool:
        return self.status.lower() in ('pending', 'pd', 'q', 'queued')
    
    @property
    def is_complete(self) -> bool:
        return self.status.lower() in ('completed', 'done', 'cd')


class WorkflowScheduler(ABC):
    """
    Abstract base class for job schedulers.
    
    Schedulers submit and monitor jobs on different platforms.
    """
    
    name: str = "base"
    
    @abstractmethod
    def submit(
        self,
        script_path: Path,
        workdir: Path,
    ) -> str:
        """
        Submit a job.
        
        Args:
            script_path: Path to job script.
            workdir: Working directory.
            
        Returns:
            Job ID.
        """
        pass
    
    @abstractmethod
    def cancel(self, job_id: str) -> bool:
        """Cancel a job."""
        pass
    
    @abstractmethod
    def get_status(self, job_id: str) -> JobInfo:
        """Get job status."""
        pass
    
    @abstractmethod
    def generate_script(
        self,
        command: str,
        job_name: str,
        workdir: Path,
        **resources,
    ) -> str:
        """Generate job script."""
        pass
    
    def wait_for_completion(
        self,
        job_id: str,
        poll_interval: int = 30,
        timeout: Optional[int] = None,
    ) -> JobInfo:
        """Wait for job to complete."""
        start_time = time.time()
        
        while True:
            info = self.get_status(job_id)
            
            if not info.is_running and not info.is_pending:
                return info
            
            if timeout and (time.time() - start_time) > timeout:
                logger.warning(f"Job {job_id} timed out")
                self.cancel(job_id)
                info.status = "timeout"
                return info
            
            time.sleep(poll_interval)


class LocalScheduler(WorkflowScheduler):
    """
    Execute jobs locally (no queue system).
    
    Useful for testing and small calculations.
    """
    
    name: str = "local"
    
    def __init__(self, max_parallel: int = 1):
        self.max_parallel = max_parallel
        self._jobs: Dict[str, subprocess.Popen] = {}
        self._job_counter = 0
    
    def submit(
        self,
        script_path: Path,
        workdir: Path,
    ) -> str:
        """Submit job by executing script."""
        self._job_counter += 1
        job_id = f"local_{self._job_counter}"
        
        # Execute script
        process = subprocess.Popen(
            ['bash', str(script_path)],
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        self._jobs[job_id] = process
        logger.info(f"Submitted local job {job_id}")
        
        return job_id
    
    def cancel(self, job_id: str) -> bool:
        """Cancel local job."""
        if job_id in self._jobs:
            self._jobs[job_id].terminate()
            return True
        return False
    
    def get_status(self, job_id: str) -> JobInfo:
        """Get local job status."""
        if job_id not in self._jobs:
            return JobInfo(job_id=job_id, name="", status="unknown")
        
        process = self._jobs[job_id]
        poll = process.poll()
        
        if poll is None:
            status = "running"
        elif poll == 0:
            status = "completed"
        else:
            status = "failed"
        
        return JobInfo(
            job_id=job_id,
            name="local_job",
            status=status,
        )
    
    def generate_script(
        self,
        command: str,
        job_name: str,
        workdir: Path,
        **resources,
    ) -> str:
        """Generate simple bash script."""
        lines = [
            "#!/bin/bash",
            f"# Local job: {job_name}",
            f"cd {workdir}",
            "",
            command,
        ]
        return "\n".join(lines)


@dataclass
class SlurmScheduler(WorkflowScheduler):
    """
    Slurm workload manager scheduler.
    
    Attributes:
        partition: Default partition/queue
        account: Default account
        qos: Quality of service
    """
    
    name: str = "slurm"
    partition: str = "standard"
    account: Optional[str] = None
    qos: Optional[str] = None
    
    def submit(
        self,
        script_path: Path,
        workdir: Path,
    ) -> str:
        """Submit job with sbatch."""
        result = subprocess.run(
            ['sbatch', str(script_path)],
            cwd=workdir,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"sbatch failed: {result.stderr}")
        
        # Parse job ID from "Submitted batch job 12345"
        match = re.search(r'(\d+)', result.stdout)
        if match:
            job_id = match.group(1)
            logger.info(f"Submitted Slurm job {job_id}")
            return job_id
        
        raise RuntimeError(f"Could not parse job ID from: {result.stdout}")
    
    def cancel(self, job_id: str) -> bool:
        """Cancel job with scancel."""
        result = subprocess.run(
            ['scancel', job_id],
            capture_output=True,
        )
        return result.returncode == 0
    
    def get_status(self, job_id: str) -> JobInfo:
        """Get job status with squeue/sacct."""
        # Try squeue first (for pending/running)
        result = subprocess.run(
            ['squeue', '-j', job_id, '-o', '%T', '--noheader'],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0 and result.stdout.strip():
            status = result.stdout.strip()
            return JobInfo(job_id=job_id, name="", status=status)
        
        # Try sacct for completed jobs
        result = subprocess.run(
            ['sacct', '-j', job_id, '-o', 'State', '--noheader', '-n', '-X'],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0 and result.stdout.strip():
            status = result.stdout.strip().split('\n')[0].strip()
            return JobInfo(job_id=job_id, name="", status=status)
        
        return JobInfo(job_id=job_id, name="", status="unknown")
    
    def generate_script(
        self,
        command: str,
        job_name: str,
        workdir: Path,
        nodes: int = 1,
        ntasks: int = 1,
        cpus_per_task: int = 1,
        time: str = "24:00:00",
        memory: str = "4G",
        **kwargs,
    ) -> str:
        """Generate Slurm job script."""
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={job_name}",
            f"#SBATCH --output={job_name}.out",
            f"#SBATCH --error={job_name}.err",
            f"#SBATCH --nodes={nodes}",
            f"#SBATCH --ntasks={ntasks}",
            f"#SBATCH --cpus-per-task={cpus_per_task}",
            f"#SBATCH --time={time}",
            f"#SBATCH --mem={memory}",
            f"#SBATCH --partition={self.partition}",
        ]
        
        if self.account:
            lines.append(f"#SBATCH --account={self.account}")
        if self.qos:
            lines.append(f"#SBATCH --qos={self.qos}")
        
        lines.extend([
            "",
            f"cd {workdir}",
            "",
            command,
        ])
        
        return "\n".join(lines)


@dataclass
class PBSScheduler(WorkflowScheduler):
    """
    PBS/Torque scheduler.
    """
    
    name: str = "pbs"
    queue: str = "default"
    
    def submit(
        self,
        script_path: Path,
        workdir: Path,
    ) -> str:
        """Submit job with qsub."""
        result = subprocess.run(
            ['qsub', str(script_path)],
            cwd=workdir,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"qsub failed: {result.stderr}")
        
        job_id = result.stdout.strip()
        logger.info(f"Submitted PBS job {job_id}")
        return job_id
    
    def cancel(self, job_id: str) -> bool:
        """Cancel job with qdel."""
        result = subprocess.run(
            ['qdel', job_id],
            capture_output=True,
        )
        return result.returncode == 0
    
    def get_status(self, job_id: str) -> JobInfo:
        """Get job status with qstat."""
        result = subprocess.run(
            ['qstat', '-f', job_id],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            return JobInfo(job_id=job_id, name="", status="completed")
        
        # Parse job_state
        match = re.search(r'job_state = (\w+)', result.stdout)
        status = match.group(1) if match else "unknown"
        
        return JobInfo(job_id=job_id, name="", status=status)
    
    def generate_script(
        self,
        command: str,
        job_name: str,
        workdir: Path,
        nodes: int = 1,
        ppn: int = 1,
        walltime: str = "24:00:00",
        memory: str = "4gb",
        **kwargs,
    ) -> str:
        """Generate PBS job script."""
        lines = [
            "#!/bin/bash",
            f"#PBS -N {job_name}",
            f"#PBS -o {job_name}.out",
            f"#PBS -e {job_name}.err",
            f"#PBS -l nodes={nodes}:ppn={ppn}",
            f"#PBS -l walltime={walltime}",
            f"#PBS -l mem={memory}",
            f"#PBS -q {self.queue}",
            "",
            f"cd {workdir}",
            "",
            command,
        ]
        
        return "\n".join(lines)


def get_scheduler(scheduler_type: str, **kwargs) -> WorkflowScheduler:
    """
    Factory function for schedulers.
    
    Args:
        scheduler_type: 'local', 'slurm', or 'pbs'
        **kwargs: Scheduler-specific options
        
    Returns:
        Configured scheduler instance.
    """
    schedulers = {
        'local': LocalScheduler,
        'slurm': SlurmScheduler,
        'pbs': PBSScheduler,
    }
    
    if scheduler_type not in schedulers:
        raise ValueError(f"Unknown scheduler: {scheduler_type}")
    
    return schedulers[scheduler_type](**kwargs)
