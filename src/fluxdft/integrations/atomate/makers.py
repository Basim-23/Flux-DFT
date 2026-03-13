"""
Makers for Quantum ESPRESSO Workflows.

These classes configure and orchestrate the execution of QE jobs.
"""

from dataclasses import dataclass, field
from typing import Optional, Union, List

from jobflow import Job, Flow, Maker
from pymatgen.core import Structure

from .generators import FluxQEInputGenerator, RelaxSetGenerator, BandsSetGenerator
from .run import run_qe_calculation

@dataclass
class BaseQEMaker(Maker):
    """
    Base maker for QE calculations.
    """
    name: str = "base"
    input_set_generator: FluxQEInputGenerator = field(default_factory=FluxQEInputGenerator)
    
    def make(self, structure: Structure, prev_dir: Optional[str] = None) -> Job:
        """
        Create the QE job.
        
        Args:
            structure: Input structure.
            prev_dir: Previous directory for chaining.
        """
        # 1. Generate Input Set
        input_set = self.input_set_generator.get_input_set(structure, prev_dir=prev_dir)
        
        # 2. Add FluxDFT metadata/provenance?
        
        # 3. Create the Job
        # We pass the input_set object to the job, which serializes it
        return run_qe_calculation(
            structure=structure,
            input_set=input_set,
            command="pw.x < pw.in > pw.out", # Default command
            prev_dir=prev_dir 
        )


@dataclass
class RelaxQEMaker(BaseQEMaker):
    """
    Maker for Geometry Optimization (Relax/VC-Relax).
    """
    name: str = "relax"
    input_set_generator: RelaxSetGenerator = field(default_factory=RelaxSetGenerator)


@dataclass
class BandsQEMaker(BaseQEMaker):
    """
    Maker for Band Structure calculations.
    """
    name: str = "bands"
    input_set_generator: BandsSetGenerator = field(default_factory=BandsSetGenerator)

    def make(self, structure: Structure, prev_dir: Optional[str] = None) -> Flow:
        """
        Bands usually require SCF then Bands.
        This maker can return a Flow of [SCF -> Bands].
        """
        # MVP: Assuming prev_dir provides the charge density (Hybrid flow)
        # If no prev_dir, we should construct an SCF job first
        
        jobs = []
        
        if prev_dir is None:
            # Create SCF step
            scf_maker = BaseQEMaker(name=f"{self.name} scf")
            # We'd need an SCF generator here. Re-using RelaxSetGenerator with relax_cell=False as generic SCF for now
            scf_maker.input_set_generator = RelaxSetGenerator(relax_cell=False, precision="medium")
            scf_job = scf_maker.make(structure)
            jobs.append(scf_job)
            prev_dir = scf_job.output["dir_name"] # Dependencies in jobflow are handled via output references
        
        # Bands Step
        # The 'prev_dir' here implies runtime dependency if passed from a Job output
        bands_job = super().make(structure, prev_dir=prev_dir)
        jobs.append(bands_job)
        
        return Flow(jobs, output=bands_job.output)
