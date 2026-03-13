"""
Base classes for FluxDFT Workflow System.

Provides status enums, result containers, and base functionality
shared across tasks and workflows.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pathlib import Path
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a task or workflow."""
    PENDING = "pending"          # Not yet started
    WAITING = "waiting"          # Waiting for dependencies
    READY = "ready"              # Ready to run (dependencies satisfied)
    SUBMITTED = "submitted"      # Submitted to queue
    RUNNING = "running"          # Currently executing
    COMPLETED = "completed"      # Finished successfully
    FAILED = "failed"            # Finished with error
    CANCELLED = "cancelled"      # User cancelled
    PAUSED = "paused"            # Paused by user
    
    @property
    def is_terminal(self) -> bool:
        """Check if status is terminal (no further changes expected)."""
        return self in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        )
    
    @property
    def is_active(self) -> bool:
        """Check if task is actively being processed."""
        return self in (
            TaskStatus.SUBMITTED,
            TaskStatus.RUNNING,
        )
    
    @property
    def icon(self) -> str:
        """Status icon for UI display."""
        icons = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.WAITING: "⏸️",
            TaskStatus.READY: "✅",
            TaskStatus.SUBMITTED: "📤",
            TaskStatus.RUNNING: "🔄",
            TaskStatus.COMPLETED: "✔️",
            TaskStatus.FAILED: "❌",
            TaskStatus.CANCELLED: "🚫",
            TaskStatus.PAUSED: "⏸️",
        }
        return icons.get(self, "❓")


class WorkflowStatus(Enum):
    """Status of an entire workflow."""
    CREATED = "created"          # Just created, not started
    RUNNING = "running"          # At least one task active
    COMPLETED = "completed"      # All tasks completed successfully
    FAILED = "failed"            # At least one task failed
    PAUSED = "paused"            # User paused
    CANCELLED = "cancelled"      # User cancelled


@dataclass
class TaskResult:
    """
    Result of a completed task.
    
    Attributes:
        status: Final task status
        workdir: Working directory
        exit_code: Process exit code (0 = success)
        runtime_seconds: Total runtime
        outputs: Dict of output files/data
        errors: List of error messages
        warnings: List of warning messages
        parsed_data: Parsed calculation results
        timestamp: Completion time
    """
    status: TaskStatus
    workdir: Path
    exit_code: int = 0
    runtime_seconds: float = 0.0
    outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    parsed_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def success(self) -> bool:
        return self.status == TaskStatus.COMPLETED and self.exit_code == 0
    
    def to_dict(self) -> Dict:
        return {
            'status': self.status.value,
            'workdir': str(self.workdir),
            'exit_code': self.exit_code,
            'runtime_seconds': self.runtime_seconds,
            'outputs': {k: str(v) if isinstance(v, Path) else v 
                       for k, v in self.outputs.items()},
            'errors': self.errors,
            'warnings': self.warnings,
            'timestamp': self.timestamp.isoformat(),
        }
    
    def save(self, filepath: Union[str, Path]) -> None:
        """Save result to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, filepath: Union[str, Path]) -> 'TaskResult':
        """Load result from JSON file."""
        with open(filepath) as f:
            data = json.load(f)
        
        return cls(
            status=TaskStatus(data['status']),
            workdir=Path(data['workdir']),
            exit_code=data.get('exit_code', 0),
            runtime_seconds=data.get('runtime_seconds', 0),
            outputs=data.get('outputs', {}),
            errors=data.get('errors', []),
            warnings=data.get('warnings', []),
            timestamp=datetime.fromisoformat(data['timestamp']),
        )


@dataclass
class WorkflowResult:
    """
    Result of a completed workflow.
    
    Aggregates results from all tasks.
    """
    status: WorkflowStatus
    workflow_name: str
    workdir: Path
    task_results: Dict[str, TaskResult] = field(default_factory=dict)
    total_runtime_seconds: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def success(self) -> bool:
        return self.status == WorkflowStatus.COMPLETED
    
    @property
    def n_tasks(self) -> int:
        return len(self.task_results)
    
    @property
    def n_completed(self) -> int:
        return sum(1 for r in self.task_results.values() if r.success)
    
    @property
    def n_failed(self) -> int:
        return sum(1 for r in self.task_results.values() 
                   if r.status == TaskStatus.FAILED)
    
    def get_task_result(self, task_name: str) -> Optional[TaskResult]:
        return self.task_results.get(task_name)
    
    def to_dict(self) -> Dict:
        return {
            'status': self.status.value,
            'workflow_name': self.workflow_name,
            'workdir': str(self.workdir),
            'task_results': {k: v.to_dict() for k, v in self.task_results.items()},
            'total_runtime_seconds': self.total_runtime_seconds,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
        }


@dataclass
class Dependency:
    """
    Dependency relationship between tasks.
    
    Attributes:
        source_task: Name of prerequisite task
        target_task: Name of dependent task
        file_transfers: Files to copy from source to target
        data_keys: Data keys to pass from source to target
    """
    source_task: str
    target_task: str
    file_transfers: List[str] = field(default_factory=list)
    data_keys: List[str] = field(default_factory=list)
    
    def describe(self) -> str:
        return f"{self.source_task} → {self.target_task}"


class ConfigurationError(Exception):
    """Error in task/workflow configuration."""
    pass


class ExecutionError(Exception):
    """Error during task/workflow execution."""
    pass


class DependencyError(Exception):
    """Error with task dependencies."""
    pass
