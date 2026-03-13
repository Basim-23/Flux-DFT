"""
Workflow Specifications for FluxDFT.

These classes define the "What" of a calculation, decoupled from the "How" (Execution Engine).
Users interact with these specs to define their scientific intent.
"""

from typing import Dict, Any, Optional, List, Union, Literal
from pydantic import BaseModel, Field
from pymatgen.core import Structure

class WorkflowSpec(BaseModel):
    """Base class for all workflow specifications."""
    structure: Structure = Field(..., description="The input crystal structure")
    name: str = Field(default="flux_workflow", description="Name of the workflow")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        arbitrary_types_allowed = True


class RelaxationSpec(WorkflowSpec):
    """Specification for a geometry optimization workflow."""
    relax_cell: bool = Field(default=True, description="Whether to relax the unit cell (vc-relax)")
    target_forces: float = Field(default=1.0e-4, description="Target force convergence (Ry/bohr)")
    target_stress: float = Field(default=0.5, description="Target stress convergence (kbar)")
    max_steps: int = Field(default=100, description="Maximum ionic steps")
    
    # "Preset" or "Tier" concept
    precision: Literal["low", "medium", "high", "production"] = "medium"
    
    # Lower-level overrides (careful!)
    qe_params: Dict[str, Any] = Field(default_factory=dict, description="Direct QE namelist overrides")


class BandStructureSpec(WorkflowSpec):
    """Specification for a band structure workflow."""
    line_density: int = Field(default=20, description="K-points per reciprocal angstrom")
    decompose_projections: bool = Field(default=False, description="Calculate orbital projections (projwfc)")
    
    # SCF/Hybrid settings
    functional: Literal["PBE", "HSE06", "SCAN"] = "PBE"
    
    # Restart Source
    parent_scf_dir: Optional[str] = Field(default=None, description="Path to restart from")


class StaticSpec(WorkflowSpec):
    """Specification for a single-point energy/property calculation."""
    property_type: Literal["energy", "dielectric", "polarization"] = "energy"
    
    # Specifics for DFPT
    dielectric_tensor: bool = False
    born_charges: bool = False
