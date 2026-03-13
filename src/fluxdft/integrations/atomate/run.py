"""
Execution Logic for Quantum ESPRESSO Jobs.

This module defines the actual jobflow Jobs that run QE calculations.
"""

import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import subprocess

# Atomate2 / Jobflow Imports
from jobflow import job, Response
from pymatgen.core import Structure
from pymatgen.io.pwscf import PWInput

# FluxDFT Imports
from ...io.qe_output import QEOutputParser

@job
def run_qe_calculation(
    structure: Structure,
    input_set: PWInput,
    command: str = "pw.x < pw.in > pw.out",
    prev_dir: Optional[str] = None,
) -> Any:
    """
    Run a Quantum ESPRESSO calculation.
    
    Args:
        structure: Input structure.
        input_set: The PWInput object defining the calc.
        command: The shell command to run.
        prev_dir: Directory to copy restart files from.
        
    Returns:
        Jobflow Response containing results.
    """
    # 1. Setup Working Directory
    # Jobflow manages the dir, we just write to current
    
    # 2. Copy Previous Files (if chaining)
    if prev_dir:
        prev_path = Path(prev_dir)
        for f in ["prefix.save", "prefix.wfc", "charge-density"]: # Example list
            src = prev_path / f
            if src.exists():
                if src.is_dir():
                    shutil.copytree(src, Path.cwd() / f)
                else:
                    shutil.copy2(src, Path.cwd())
                    
    # 3. Write Input
    input_set.write_file("pw.in")
    
    # 4. Execute with Custodian
    try:
        from custodian.custodian import Custodian
        from ...integrations.custodian.handlers import QESCFErrorHandler
        
        # Define Handlers
        handlers = [QESCFErrorHandler()]
        
        # Define Job
        # Custodian expects a list of jobs. We can define a simplified Job class or use subprocess
        # Basic subprocess wrapper:
        from custodian.utils import run_command
        
        # We need a tailored Custodian Job class for QE if we want fine control
        # For MVP, we can treat the command as the job
        # Custodian(handlers, jobs=[command], ...)
        
        # However, Custodian jobs usually need a 'run' method.
        # Let's create a minimal inner class or use a generic one if available.
        # We'll use a simple list of commands for now if Custodian supports it (it requires objects usually)
        
        class SimpleJob:
            def __init__(self, cmd):
                self.cmd = cmd
                self.name = "pw.x"
            def setup(self): pass
            def run(self):
                # run_command(self.cmd) # Custodian util
                try:
                    subprocess.run(self.cmd, shell=True, check=True)
                except subprocess.CalledProcessError as e:
                    return e.returncode
                return 0
            def postprocess(self): pass
            
        c = Custodian(handlers, [SimpleJob(command)], max_errors=3)
        c.run()
        success = True # If run() finishes without exception
        
    except ImportError:
        # Fallback if Custodian missing
        try:
            subprocess.run(command, shell=True, check=True)
            success = True
        except subprocess.CalledProcessError:
            success = False
    except Exception as e:
        success = False
        # Log e

            
    # 5. Parse Output
    # Use our new parser
    parser = QEOutputParser()
    try:
        data = parser.parse("pw.out")
        success = True # TODO check data.convergence
    except Exception:
        success = False
        data = None
        
    # 6. Return Response
    result_doc = {
        "formula": structure.formula,
        "energy": data.total_energy if data else None,
        "success": success,
        "dir_name": str(Path.cwd())
    }
    
    return Response(output=result_doc, stop_children=not success)
