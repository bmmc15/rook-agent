"""Task manager for tracking coding tasks."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from rook.core.events import EventBus, Event, EventType
from rook.tasks.states import Task, TaskState
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class TaskManager:
    """Manages coding tasks."""

    def __init__(self, event_bus: EventBus):
        """Initialize task manager.

        Args:
            event_bus: Event bus
        """
        self.event_bus = event_bus
        self._tasks: Dict[str, Task] = {}

    def create_task(self, description: str) -> Task:
        """Create a new task.

        Args:
            description: Task description

        Returns:
            Created task
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()

        task = Task(
            id=task_id,
            description=description,
            state=TaskState.PENDING,
            created_at=now,
            updated_at=now,
        )

        self._tasks[task_id] = task
        logger.info(f"Created task {task_id}: {description[:50]}...")

        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None
        """
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[Task]:
        """List all tasks.

        Returns:
            List of tasks
        """
        return list(self._tasks.values())

    def update_task_state(
        self, task_id: str, state: TaskState, error: Optional[str] = None
    ) -> Optional[Task]:
        """Update task state.

        Args:
            task_id: Task ID
            state: New state
            error: Optional error message

        Returns:
            Updated task or None
        """
        task = self._tasks.get(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            return None

        task.state = state
        task.updated_at = datetime.now()

        if error:
            task.error = error

        logger.info(f"Task {task_id} state updated to {state.name}")
        return task

    def update_task_progress(
        self, task_id: str, progress: float, message: Optional[str] = None
    ) -> Optional[Task]:
        """Update task progress.

        Args:
            task_id: Task ID
            progress: Progress value (0-1)
            message: Optional progress message

        Returns:
            Updated task or None
        """
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.progress = progress
        task.updated_at = datetime.now()

        logger.debug(f"Task {task_id} progress: {progress * 100:.1f}%")
        return task

    def cancel_task(self, task_id: str) -> Optional[Task]:
        """Cancel a task.

        Args:
            task_id: Task ID

        Returns:
            Updated task or None
        """
        return self.update_task_state(task_id, TaskState.CANCELLED)

    def cancel_all_tasks(self) -> None:
        """Cancel all pending and running tasks."""
        for task in self._tasks.values():
            if task.state in (TaskState.PENDING, TaskState.RUNNING):
                task.state = TaskState.CANCELLED
                task.updated_at = datetime.now()

        logger.info("Cancelled all tasks")
