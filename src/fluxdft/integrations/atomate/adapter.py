"""
FluxDFT -> Atomate2 Adapter.

This module bridges the high-level FluxDFT WorkflowSpecs to the internal
Atomate2 Makers and Flows.
"""

from typing import Union

from jobflow import Flow, Job
from pymatgen.core import Structure

from ...workflows.spec import WorkflowSpec, RelaxationSpec, BandStructureSpec
from .makers import RelaxQEMaker, BandsQEMaker
from .generators import RelaxSetGenerator, BandsSetGenerator

def to_atomate_flow(spec: WorkflowSpec) -> Union[Flow, Job]:
    """
    Convert a FluxDFT WorkflowSpec into an executable Atomate2 Flow/Job.
    
    Args:
        spec: The high-level workflow specification.
        
    Returns:
        A jobflow Flow or Job ready for execution.
    """
    if isinstance(spec, RelaxationSpec):
        # Translate Spec -> Generator Settings
        generator = RelaxSetGenerator(
            relax_cell=spec.relax_cell,
            precision=spec.precision,
            user_settings=spec.qe_params
        )
        
        maker = RelaxQEMaker(
            name=spec.name,
            input_set_generator=generator
        )
        
        return maker.make(spec.structure)
        
    elif isinstance(spec, BandStructureSpec):
        generator = BandsSetGenerator(
            base_settings={"user_override": "true"} # Placeholder
        )
        
        maker = BandsQEMaker(
            name=spec.name,
            input_set_generator=generator
        )
        
        # parent_scf_dir handling would happen here 
        # (resolving the path/dependency)
        
        return maker.make(spec.structure, prev_dir=spec.parent_scf_dir)
        
    else:
        raise NotImplementedError(f"Spec type {type(spec)} not supported by Atomate adapter yet.")
