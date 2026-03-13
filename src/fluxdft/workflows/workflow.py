"""
QE Workflow Container for FluxDFT.

Manages multi-step calculations with dependency resolution,
parallel execution, and checkpoint/restart support.

Inspired by abipy's Flow class and atomate2's workflow patterns.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from pathlib import Path
from datetime import datetime
import json
import pickle
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import (
    TaskStatus, WorkflowStatus, TaskResult, WorkflowResult,
    Dependency, ConfigurationError, DependencyError
)
from .task import QETask

logger = logging.getLogger(__name__)


class QEWorkflow:
    """
    Container for multiple dependent QE tasks.
    
    Manages task dependencies, execution order, and result aggregation.
    Supports checkpointing for crash recovery.
    
    Features:
        - Dependency resolution (DAG-based)
        - Parallel execution of independent tasks
        - Automatic file transfers between tasks
        - Checkpoint/restart support
        - Progress callbacks
        - Visualization (DAG diagram)
    
    Usage:
        >>> workflow = QEWorkflow(name="band_structure", workdir=Path("./calc"))
        >>> workflow.add_task(scf_task)
        >>> workflow.add_task(bands_task, depends_on=['scf'])
        >>> result = workflow.run()
    """
    
    def __init__(
        self,
        name: str,
        workdir: Optional[Path] = None,
        description: str = "",
        max_parallel: int = 1,
        checkpoint_interval: int = 1,
    ):
        """
        Initialize workflow.
        
        Args:
            name: Workflow name.
            workdir: Base working directory.
            description: Human-readable description.
            max_parallel: Maximum parallel tasks.
            checkpoint_interval: Save checkpoint every N tasks.
        """
        self.name = name
        self.workdir = Path(workdir) if workdir else None
        self.description = description
        self.max_parallel = max_parallel
        self.checkpoint_interval = checkpoint_interval
        
        # Tasks and dependencies
        self._tasks: Dict[str, QETask] = {}
        self._dependencies: Dict[str, Set[str]] = {}  # task_name -> set of prereqs
        self._dependents: Dict[str, Set[str]] = {}    # task_name -> set of dependents
        
        # State
        self._status = WorkflowStatus.CREATED
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._completed_tasks: Set[str] = set()
        
        # Callbacks
        self._on_task_complete: Optional[Callable] = None
        self._on_task_error: Optional[Callable] = None
        self._on_progress: Optional[Callable] = None
    
    @property
    def status(self) -> WorkflowStatus:
        return self._status
    
    @property
    def tasks(self) -> List[QETask]:
        return list(self._tasks.values())
    
    @property
    def n_tasks(self) -> int:
        return len(self._tasks)
    
    @property
    def n_completed(self) -> int:
        return len(self._completed_tasks)
    
    @property
    def progress(self) -> float:
        """Progress as fraction (0-1)."""
        if self.n_tasks == 0:
            return 0.0
        return self.n_completed / self.n_tasks
    
    def add_task(
        self,
        task: QETask,
        depends_on: Optional[List[str]] = None,
    ) -> None:
        """
        Add a task to the workflow.
        
        Args:
            task: QETask instance.
            depends_on: List of prerequisite task names.
        """
        if task.name in self._tasks:
            raise ConfigurationError(f"Task '{task.name}' already exists")
        
        self._tasks[task.name] = task
        self._dependencies[task.name] = set(depends_on or [])
        self._dependents[task.name] = set()
        
        # Update reverse dependencies
        for prereq in (depends_on or []):
            if prereq not in self._tasks:
                raise DependencyError(f"Dependency '{prereq}' not found")
            self._dependents.setdefault(prereq, set()).add(task.name)
        
        # Set task workdir
        if self.workdir:
            task.workdir = self.workdir / task.name
        
        logger.debug(f"Added task '{task.name}' with deps: {depends_on}")
    
    def remove_task(self, task_name: str) -> None:
        """Remove a task from the workflow."""
        if task_name not in self._tasks:
            raise ConfigurationError(f"Task '{task_name}' not found")
        
        # Check if other tasks depend on this
        if self._dependents.get(task_name):
            raise DependencyError(
                f"Cannot remove '{task_name}': other tasks depend on it"
            )
        
        del self._tasks[task_name]
        del self._dependencies[task_name]
        
        # Clean up reverse dependencies
        for prereqs in self._dependencies.values():
            prereqs.discard(task_name)
    
    def get_task(self, name: str) -> Optional[QETask]:
        return self._tasks.get(name)
    
    def get_execution_order(self) -> List[str]:
        """
        Get topologically sorted task order.
        
        Returns list of task names in valid execution order.
        """
        visited = set()
        order = []
        
        def visit(name: str, stack: Set[str]):
            if name in stack:
                raise DependencyError(f"Circular dependency detected: {name}")
            if name in visited:
                return
            
            stack.add(name)
            for prereq in self._dependencies.get(name, set()):
                visit(prereq, stack)
            stack.remove(name)
            
            visited.add(name)
            order.append(name)
        
        for task_name in self._tasks:
            visit(task_name, set())
        
        return order
    
    def get_ready_tasks(self) -> List[QETask]:
        """Get tasks that are ready to run (all dependencies satisfied)."""
        ready = []
        for name, task in self._tasks.items():
            if task.status != TaskStatus.PENDING:
                continue
            
            prereqs = self._dependencies.get(name, set())
            if prereqs.issubset(self._completed_tasks):
                ready.append(task)
        
        return ready
    
    def setup(self, workdir: Optional[Path] = None) -> None:
        """Set up workflow for execution."""
        if workdir:
            self.workdir = Path(workdir)
        
        if not self.workdir:
            raise ConfigurationError("No workdir set for workflow")
        
        # Create workflow directory
        self.workdir.mkdir(parents=True, exist_ok=True)
        
        # Validate dependencies
        self.get_execution_order()
        
        # Set up tasks
        for task in self._tasks.values():
            if not task.workdir:
                task.workdir = self.workdir / task.name
        
        # Link dependencies (for file transfers)
        for name, prereqs in self._dependencies.items():
            task = self._tasks[name]
            if prereqs:
                # Use first prereq as prev_task (for simple linear deps)
                first_prereq = list(prereqs)[0]
                task.prev_task = self._tasks[first_prereq]
        
        logger.info(f"Workflow '{self.name}' set up with {self.n_tasks} tasks")
    
    def run(
        self,
        dry_run: bool = False,
        resume: bool = True,
    ) -> WorkflowResult:
        """
        Execute the workflow using ExecutionEngine.
        
        Args:
            dry_run: If True, set up but don't execute.
            resume: If True, skip already completed tasks.
            
        Returns:
            WorkflowResult with all task results.
        """
        # Lazy import to avoid circular dependency
        from .engine import ExecutionEngine, Job, JobStatus
        
        self.setup()
        
        if dry_run:
            logger.info("Dry run: setting up tasks without execution")
            return WorkflowResult(
                status=WorkflowStatus.COMPLETED,
                workflow_name=self.name,
                workdir=self.workdir,
                task_results={},
                total_runtime_seconds=0.0
            )

        self._status = WorkflowStatus.RUNNING
        self._start_time = datetime.now()
        
        if resume:
            self._load_checkpoint()
        
        # Initialize Engine
        engine = ExecutionEngine(
            scheduler='local',
            max_parallel=self.max_parallel,
            checkpoint_file=self.workdir / 'engine_checkpoint.json' if self.workdir else None
        )
        
        # Job ID mapping
        task_job_map = {}
        
        # Helper callbacks
        def make_on_start(t):
            return lambda j: t.setup()
            
        def make_on_complete(t, wf):
            def callback(j):
                if j.result and j.result.is_success:
                    t.status = TaskStatus.COMPLETED
                    # Parse output
                    try:
                        parsed = t._parse_output()
                        t._result = TaskResult(
                            status=TaskStatus.COMPLETED,
                            workdir=t.workdir,
                            exit_code=j.result.exit_code,
                            runtime_seconds=j.result.elapsed_time or 0.0,
                            outputs=t._collect_outputs(),
                            parsed_data=parsed
                        )
                        wf._completed_tasks.add(t.name)
                        if wf._on_task_complete:
                            wf._on_task_complete(t, t._result)
                    except Exception as e:
                        logger.error(f"Error parsing task {t.name}: {e}")
                        t.status = TaskStatus.FAILED
                else:
                    t.status = TaskStatus.FAILED
                    t._result = TaskResult(
                        status=TaskStatus.FAILED,
                        workdir=t.workdir,
                        errors=[j.result.error_message] if j.result else ["Unknown error"]
                    )
                    if wf._on_task_error:
                        wf._on_task_error(t, t._result)
            return callback

        # Create Jobs
        for name in self.get_execution_order():
            if resume and name in self._completed_tasks:
                # Still need to map job_id for dependencies
                # We create a dummy completed job or just track the ID if we supported re-attaching
                # For now, we assume if it's done, dependencies are satisfied implicitly in logic,
                # BUT Engine needs the job definition if pending jobs depend on it.
                # Since Engine checks dependencies in _get_ready_jobs, we should probably add the job 
                # but set its status to COMPLETED if supported, OR just exclude it from dependency list 
                # of children if we are clever.
                # Simpler approach: Add it, but check if output exists. 
                # Actually, if we skip adding it to engine, children will wait forever if they depend on it?
                # No, Engine dependencies must exist in Engine.
                # So we must add completed tasks as "already completed" jobs.
                # Engine doesn't support "add_completed_job" directly.
                # Hack: We don't add it, and we check dependencies in `depends_on`.
                # If a parent is "done" (in _completed_tasks), we don't include it in `depends_on` list sent to Engine.
                # This decouples the Engine dependency graph for skipped nodes.
                continue

            task = self._tasks[name]
            
            # Filter dependencies: only include those that are NOT yet completed
            # If a dependency is already completed (resumed), we don't need to wait for it in Engine.
            active_deps = []
            for dep_name in self._dependencies.get(name, []):
                if dep_name not in self._completed_tasks and dep_name in task_job_map:
                    active_deps.append(task_job_map[dep_name])
            
            # Construct command
            # QETask._build_command returns list. We assume local shell execution.
            cmd_list = task._build_command()
            cmd_str = " ".join(cmd_list)
            # Add redirection
            cmd_str += f" > {task.output_file.name}"
            
            job = Job(
                job_id=name,
                name=name,
                work_dir=task.workdir,
                input_file=task.input_file.name,
                command=cmd_str,
                on_start=make_on_start(task),
                on_complete=make_on_complete(task, self),
                depends_on=active_deps
            )
            
            engine.add_job(job)
            task_job_map[name] = name

        try:
            # Run Engine
            engine.run()
            
            # Determine final status
            failed = any(t.status == TaskStatus.FAILED for t in self._tasks.values())
            self._status = WorkflowStatus.FAILED if failed else WorkflowStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            self._status = WorkflowStatus.FAILED
            
        self._end_time = datetime.now()
        self._save_checkpoint()
        
        # Construct final results
        task_results = {}
        for name, task in self._tasks.items():
            if task.result:
                task_results[name] = task.result
            elif name in self._completed_tasks:
                 # Should have result, but if resumed, maybe load it?
                 # Keep simple for now.
                 pass
                 
        return WorkflowResult(
            status=self._status,
            workflow_name=self.name,
            workdir=self.workdir,
            task_results=task_results,
            total_runtime_seconds=(self._end_time - self._start_time).total_seconds(),
            start_time=self._start_time,
            end_time=self._end_time,
        )

    def _run_sequential(self, dry_run: bool) -> None:
        """Deprecated: Use run()."""
        pass

    def _run_parallel(self, dry_run: bool) -> None:
        """Deprecated: Use run()."""
        pass
    
    def _save_checkpoint(self) -> None:
        """Save workflow state for recovery."""
        if not self.workdir:
            return
        
        checkpoint = {
            'name': self.name,
            'completed_tasks': list(self._completed_tasks),
            'status': self._status.value,
            'start_time': self._start_time.isoformat() if self._start_time else None,
        }
        
        checkpoint_file = self.workdir / 'checkpoint.json'
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def _load_checkpoint(self) -> None:
        """Load workflow state from checkpoint."""
        if not self.workdir:
            return
        
        checkpoint_file = self.workdir / 'checkpoint.json'
        if not checkpoint_file.exists():
            return
        
        with open(checkpoint_file) as f:
            checkpoint = json.load(f)
        
        self._completed_tasks = set(checkpoint.get('completed_tasks', []))
        logger.info(f"Resumed workflow with {len(self._completed_tasks)} completed tasks")
    
    def cancel(self) -> None:
        """Cancel the workflow."""
        self._status = WorkflowStatus.CANCELLED
        for task in self._tasks.values():
            task.cancel()
    
    def on_task_complete(self, callback: Callable) -> None:
        """Set callback for task completion."""
        self._on_task_complete = callback
    
    def on_task_error(self, callback: Callable) -> None:
        """Set callback for task error."""
        self._on_task_error = callback
    
    def on_progress(self, callback: Callable) -> None:
        """Set callback for progress updates."""
        self._on_progress = callback
    
    def visualize(self) -> str:
        """Generate Mermaid diagram of workflow."""
        lines = ["graph TD"]
        
        for name, task in self._tasks.items():
            status_icon = task.status.icon
            lines.append(f'    {name}["{status_icon} {name}"]')
        
        for name, prereqs in self._dependencies.items():
            for prereq in prereqs:
                lines.append(f"    {prereq} --> {name}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        """Serialize workflow configuration."""
        return {
            'name': self.name,
            'description': self.description,
            'workdir': str(self.workdir) if self.workdir else None,
            'tasks': [t.name for t in self._tasks.values()],
            'dependencies': {k: list(v) for k, v in self._dependencies.items()},
            'status': self._status.value,
        }
    
    def save(self, filepath: Path) -> None:
        """Save workflow to pickle file."""
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)
    
    @classmethod
    def load(cls, filepath: Path) -> 'QEWorkflow':
        """Load workflow from pickle file."""
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    
    def __repr__(self) -> str:
        return f"QEWorkflow(name='{self.name}', tasks={self.n_tasks}, status={self._status.value})"
