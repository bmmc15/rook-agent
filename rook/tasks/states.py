"""Task states and models."""
from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class TaskState(Enum):
    """Task states."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class Task:
    """Coding task model."""

    id: str
    description: str
    state: TaskState
    created_at: datetime
    updated_at: datetime
    progress: float = 0.0
    result: Optional[str] = None
    error: Optional[str] = None
