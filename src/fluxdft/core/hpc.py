"""
HPC Script Generator for FluxDFT.

Generates submission scripts for various schedulers (SLURM, PBS).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import textwrap

@dataclass
class HpcConfig:
    """Configuration for HPC job submission."""
    scheduler: str = "SLURM"  # SLURM or PBS
    job_name: str = "flux_calc"
    nodes: int = 1
    ntasks_per_node: int = 40
    cpus_per_task: int = 1
    walltime: str = "24:00:00"
    partition: str = "standard"
    email: str = ""
    modules: List[str] = field(default_factory=lambda: ["qe/7.0", "openmpi/4.0"])
    pre_commands: List[str] = field(default_factory=list)
    executable: str = "pw.x"
    input_file: str = "pw.in"
    output_file: str = "pw.out"

class HpcScriptGenerator:
    """Generates HPC submission scripts."""
    
    @staticmethod
    def generate_slurm(config: HpcConfig) -> str:
        """Generate SLURM submission script."""
        
        # Header
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={config.job_name}",
            f"#SBATCH --nodes={config.nodes}",
            f"#SBATCH --ntasks-per-node={config.ntasks_per_node}",
            f"#SBATCH --cpus-per-task={config.cpus_per_task}",
            f"#SBATCH --time={config.walltime}",
            f"#SBATCH --partition={config.partition}",
            f"#SBATCH --output={config.job_name}.%j.out",
            f"#SBATCH --error={config.job_name}.%j.err",
        ]
        
        if config.email:
            lines.append(f"#SBATCH --mail-user={config.email}")
            lines.append("#SBATCH --mail-type=ALL")
            
        lines.append("")
        lines.append("# Environment Setup")
        lines.append("module purge")
        for mod in config.modules:
            lines.append(f"module load {mod}")
            
        if config.pre_commands:
            lines.append("")
            lines.append("# Pre-processing")
            lines.extend(config.pre_commands)
            
        lines.append("")
        lines.append("# Execution")
        
        # MPI Command construction
        total_tasks = config.nodes * config.ntasks_per_node
        mpirun = f"mpirun -np {total_tasks} {config.executable}"
        
        lines.append(f"{mpirun} -in {config.input_file} > {config.output_file}")
        
        return "\n".join(lines)

    @staticmethod
    def generate_pbs(config: HpcConfig) -> str:
        """Generate PBS submission script."""
        
        lines = [
            "#!/bin/bash",
            f"#PBS -N {config.job_name}",
            f"#PBS -l select={config.nodes}:ncpus={config.ntasks_per_node}:mpiprocs={config.ntasks_per_node}",
            f"#PBS -l walltime={config.walltime}",
            f"#PBS -q {config.partition}",
            f"#PBS -o {config.job_name}.out",
            f"#PBS -e {config.job_name}.err",
        ]

        if config.email:
             lines.append(f"#PBS -M {config.email}")
             lines.append("#PBS -m abe")

        lines.append("")
        lines.append("cd $PBS_O_WORKDIR")
        lines.append("")
        lines.append("# Environment Setup")
        lines.append("module purge")
        for mod in config.modules:
            lines.append(f"module load {mod}")

        if config.pre_commands:
            lines.append("")
            lines.append("# Pre-processing")
            lines.extend(config.pre_commands)

        lines.append("")
        lines.append("# Execution")
        # PBS often uses mpiexec or mpirun
        lines.append(f"mpirun {config.executable} -in {config.input_file} > {config.output_file}")

        return "\n".join(lines)
