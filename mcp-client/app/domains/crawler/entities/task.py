"""Task entity for crawler domain"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum

class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessingMode(str, Enum):
    """Processing mode enumeration"""
    BASIC = "basic"
    AUTO = "auto"

@dataclass
class Task:
    """Task entity representing a crawling task"""
    id: str
    url: str
    mode: ProcessingMode
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def mark_as_running(self) -> None:
        """Mark task as running"""
        self.status = TaskStatus.RUNNING
    
    def mark_as_completed(self) -> None:
        """Mark task as completed"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
    
    def mark_as_failed(self, error: str) -> None:
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()
    
    @property
    def is_finished(self) -> bool:
        """Check if task is finished (completed or failed)"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
