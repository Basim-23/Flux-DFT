"""
Workflow Execution Engine.

This module handles the actual running of workflows, acting as the 
interface between the user's specs and the underlying JobFlow/Atomate machinery.
"""

import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Union
import logging

# Check integration availability
try:
    from jobflow.managers.local import run_locally
    JOBFLOW_AVAILABLE = True
except ImportError:
    JOBFLOW_AVAILABLE = False

from ..workflows.spec import WorkflowSpec
from ..integrations.atomate.adapter import to_atomate_flow

logger = logging.getLogger(__name__)

class WorkflowEngine:
    """
    Main execution engine for FluxDFT workflows.
    
    Handles:
    - Spec validation
    - Translation to JobFlow
    - Local execution management
    - Result harvesting
    """
    
    def __init__(self, run_dir_root: Union[str, Path] = "./flux_runs"):
        self.run_dir_root = Path(run_dir_root)
        self.run_dir_root.mkdir(parents=True, exist_ok=True)
        
        if not JOBFLOW_AVAILABLE:
            logger.warning("JobFlow not found. Execution will fail.")

    def submit(self, spec: WorkflowSpec) -> str:
        """
        Submit a workflow for execution.
        
        Args:
            spec: The WorkflowSpec defining the calculation.
            
        Returns:
            str: A run_id for tracking.
        """
        if not JOBFLOW_AVAILABLE:
            raise RuntimeError("JobFlow integration missing.")

        # 1. Translate Spec to Flow
        logger.info(f"Translating spec '{spec.name}' to Atomate Flow...")
        flow = to_atomate_flow(spec)
        
        # 2. Setup Run Directory
        run_id = str(uuid.uuid4())[:8]
        unique_name = f"{spec.name}_{run_id}"
        run_dir = self.run_dir_root / unique_name
        run_dir.mkdir(exist_ok=True)
        
        logger.info(f"Starting execution in {run_dir}")
        
        # 3. Execute Locally (Blocking for MVP, Async later)
        # uses jobflow's local runner which handles dependency resolution
        try:
            responses = run_locally(
                flow, 
                root_dir=str(run_dir), 
                ensure_success=True,
                store=None # Uses ephemeral memory store by default
            )
            
            # 4. Check status
            # run_locally returns a dict of {uuid: Response}
            failures = [
                r for r in responses.values() 
                if r.response and not r.response.output.get("success", False)
            ]
            
            if failures:
                logger.error("Workflow failed.")
                return f"{run_id}_FAILED"
                
            logger.info("Workflow completed successfully.")
            return f"{run_id}_SUCCESS"
            
        except Exception as e:
            logger.exception("Workflow execution crashed.")
            return f"{run_id}_CRASHED"
            
    def get_status(self, run_id: str) -> str:
        """Get status of a run (MVP stub)."""
        # In a real DB-backed system, query the JobStore
        return "UNKNOWN"
