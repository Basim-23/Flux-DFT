"""
SSH Client for remote job submission to HPC clusters.

Supports SLURM, PBS/Torque, and SGE schedulers.
"""

import os
import re
import time
from pathlib import Path, PurePosixPath
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable
from enum import Enum

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False


class Scheduler(Enum):
    """Supported job schedulers."""
    SLURM = "slurm"
    PBS = "pbs"
    SGE = "sge"


@dataclass
class RemoteJob:
    """Represents a job submitted to a remote cluster."""
    job_id: str
    name: str
    scheduler: Scheduler
    status: str = "unknown"
    queue: str = ""
    nodes: int = 1
    tasks: int = 1
    walltime: str = "01:00:00"
    
    # Paths on the remote server
    remote_work_dir: str = ""
    input_file: str = ""
    output_file: str = ""
    script_file: str = ""


@dataclass
class ServerConfig:
    """Remote server configuration."""
    name: str
    hostname: str
    username: str
    port: int = 22
    key_file: Optional[str] = None
    password: Optional[str] = None
    
    # QE paths on remote server
    qe_path: str = "/usr/local/bin"
    modules: List[str] = field(default_factory=list)  # Modules to load
    
    # Job settings
    scheduler: Scheduler = Scheduler.SLURM
    default_queue: str = "default"
    scratch_dir: str = "/scratch"


class SSHClient:
    """
    SSH client for remote job submission and file transfer.
    
    Usage:
        config = ServerConfig(
            name="cluster",
            hostname="cluster.example.com",
            username="user",
            key_file="~/.ssh/id_rsa"
        )
        
        client = SSHClient(config)
        client.connect()
        
        # Upload files
        client.upload_file("input.in", "/scratch/user/job1/input.in")
        
        # Submit job
        job_id = client.submit_job(script_content, "/scratch/user/job1")
        
        # Check status
        status = client.get_job_status(job_id)
        
        client.disconnect()
    """
    
    def __init__(self, config: ServerConfig):
        if not HAS_PARAMIKO:
            raise ImportError("paramiko is required for SSH support. Install with: pip install paramiko")
        
        self.config = config
        self.ssh: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
    
    def connect(self) -> None:
        """Establish SSH connection."""
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_kwargs = {
            "hostname": self.config.hostname,
            "port": self.config.port,
            "username": self.config.username,
        }
        
        if self.config.key_file:
            key_path = os.path.expanduser(self.config.key_file)
            connect_kwargs["key_filename"] = key_path
        elif self.config.password:
            connect_kwargs["password"] = self.config.password
        
        self.ssh.connect(**connect_kwargs)
        self.sftp = self.ssh.open_sftp()
    
    def disconnect(self) -> None:
        """Close SSH connection."""
        if self.sftp:
            self.sftp.close()
        if self.ssh:
            self.ssh.close()
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
    
    def execute(self, command: str) -> tuple[str, str, int]:
        """Execute a command on the remote server."""
        if not self.ssh:
            raise RuntimeError("Not connected")
        
        stdin, stdout, stderr = self.ssh.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        
        return stdout.read().decode(), stderr.read().decode(), exit_code
    
    def upload_file(self, local_path: str | Path, remote_path: str) -> None:
        """Upload a file to the remote server."""
        if not self.sftp:
            raise RuntimeError("Not connected")
        
        local_path = Path(local_path)
        self.sftp.put(str(local_path), remote_path)
    
    def download_file(self, remote_path: str, local_path: str | Path) -> None:
        """Download a file from the remote server."""
        if not self.sftp:
            raise RuntimeError("Not connected")
        
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.sftp.get(remote_path, str(local_path))
    
    def mkdir(self, remote_path: str) -> None:
        """Create a directory on the remote server."""
        self.execute(f"mkdir -p {remote_path}")
    
    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists on the remote server."""
        try:
            self.sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
    
    def generate_job_script(
        self,
        job_name: str,
        executable: str,
        input_file: str,
        output_file: str,
        work_dir: str,
        nodes: int = 1,
        tasks_per_node: int = 1,
        walltime: str = "01:00:00",
        queue: Optional[str] = None,
    ) -> str:
        """Generate a job submission script."""
        queue = queue or self.config.default_queue
        total_tasks = nodes * tasks_per_node
        
        if self.config.scheduler == Scheduler.SLURM:
            return self._generate_slurm_script(
                job_name, executable, input_file, output_file,
                work_dir, nodes, tasks_per_node, walltime, queue
            )
        elif self.config.scheduler == Scheduler.PBS:
            return self._generate_pbs_script(
                job_name, executable, input_file, output_file,
                work_dir, nodes, tasks_per_node, walltime, queue
            )
        elif self.config.scheduler == Scheduler.SGE:
            return self._generate_sge_script(
                job_name, executable, input_file, output_file,
                work_dir, total_tasks, walltime, queue
            )
        else:
            raise ValueError(f"Unknown scheduler: {self.config.scheduler}")
    
    def _generate_slurm_script(
        self, job_name, executable, input_file, output_file,
        work_dir, nodes, tasks_per_node, walltime, queue
    ) -> str:
        """Generate a SLURM job script."""
        modules_cmd = ""
        if self.config.modules:
            modules_cmd = "\n".join(f"module load {m}" for m in self.config.modules)
        
        exe_path = f"{self.config.qe_path}/{executable}"
        
        return f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={output_file}
#SBATCH --error={output_file}.err
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={tasks_per_node}
#SBATCH --time={walltime}
#SBATCH --partition={queue}

cd {work_dir}

{modules_cmd}

srun {exe_path} < {input_file}
"""
    
    def _generate_pbs_script(
        self, job_name, executable, input_file, output_file,
        work_dir, nodes, tasks_per_node, walltime, queue
    ) -> str:
        """Generate a PBS/Torque job script."""
        modules_cmd = ""
        if self.config.modules:
            modules_cmd = "\n".join(f"module load {m}" for m in self.config.modules)
        
        exe_path = f"{self.config.qe_path}/{executable}"
        total_tasks = nodes * tasks_per_node
        
        return f"""#!/bin/bash
#PBS -N {job_name}
#PBS -o {output_file}
#PBS -e {output_file}.err
#PBS -l nodes={nodes}:ppn={tasks_per_node}
#PBS -l walltime={walltime}
#PBS -q {queue}

cd {work_dir}

{modules_cmd}

mpirun -np {total_tasks} {exe_path} < {input_file}
"""
    
    def _generate_sge_script(
        self, job_name, executable, input_file, output_file,
        work_dir, total_tasks, walltime, queue
    ) -> str:
        """Generate an SGE job script."""
        modules_cmd = ""
        if self.config.modules:
            modules_cmd = "\n".join(f"module load {m}" for m in self.config.modules)
        
        exe_path = f"{self.config.qe_path}/{executable}"
        
        # Convert HH:MM:SS to seconds for SGE
        h, m, s = map(int, walltime.split(":"))
        walltime_secs = h * 3600 + m * 60 + s
        
        return f"""#!/bin/bash
#$ -N {job_name}
#$ -o {output_file}
#$ -e {output_file}.err
#$ -pe mpi {total_tasks}
#$ -l h_rt={walltime_secs}
#$ -q {queue}
#$ -cwd

cd {work_dir}

{modules_cmd}

mpirun -np {total_tasks} {exe_path} < {input_file}
"""
    
    def submit_job(self, script_content: str, work_dir: str) -> str:
        """Submit a job and return the job ID."""
        # Write script to remote
        script_path = f"{work_dir}/job.sh"
        
        # Create temp local file and upload
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(script_content)
            temp_path = f.name
        
        try:
            self.upload_file(temp_path, script_path)
        finally:
            os.unlink(temp_path)
        
        # Submit based on scheduler
        if self.config.scheduler == Scheduler.SLURM:
            stdout, stderr, code = self.execute(f"sbatch {script_path}")
            # Parse job ID from "Submitted batch job 12345"
            match = re.search(r"Submitted batch job (\d+)", stdout)
            if match:
                return match.group(1)
        
        elif self.config.scheduler == Scheduler.PBS:
            stdout, stderr, code = self.execute(f"qsub {script_path}")
            # PBS returns job ID directly
            return stdout.strip()
        
        elif self.config.scheduler == Scheduler.SGE:
            stdout, stderr, code = self.execute(f"qsub {script_path}")
            # Parse "Your job 12345 has been submitted"
            match = re.search(r"Your job (\d+)", stdout)
            if match:
                return match.group(1)
        
        raise RuntimeError(f"Failed to submit job: {stderr}")
    
    def get_job_status(self, job_id: str) -> str:
        """Get the status of a job."""
        if self.config.scheduler == Scheduler.SLURM:
            stdout, _, _ = self.execute(f"squeue -j {job_id} -h -o %T")
            return stdout.strip() or "COMPLETED"
        
        elif self.config.scheduler == Scheduler.PBS:
            stdout, _, code = self.execute(f"qstat -f {job_id}")
            if code != 0:
                return "COMPLETED"
            match = re.search(r"job_state = (\w+)", stdout)
            if match:
                state = match.group(1)
                return {"Q": "PENDING", "R": "RUNNING", "C": "COMPLETED"}.get(state, state)
        
        elif self.config.scheduler == Scheduler.SGE:
            stdout, _, code = self.execute(f"qstat -j {job_id}")
            if code != 0:
                return "COMPLETED"
            return "RUNNING"
        
        return "UNKNOWN"
    
    def cancel_job(self, job_id: str) -> None:
        """Cancel a job."""
        if self.config.scheduler == Scheduler.SLURM:
            self.execute(f"scancel {job_id}")
        elif self.config.scheduler == Scheduler.PBS:
            self.execute(f"qdel {job_id}")
        elif self.config.scheduler == Scheduler.SGE:
            self.execute(f"qdel {job_id}")
    
    def wait_for_job(
        self,
        job_id: str,
        poll_interval: int = 30,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Wait for a job to complete, polling periodically."""
        while True:
            status = self.get_job_status(job_id)
            
            if on_status:
                on_status(status)
            
            if status in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"):
                return status
            
            time.sleep(poll_interval)
