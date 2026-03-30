"""Task progress tracking."""
from rook.core.events import EventBus, Event, EventType
from rook.tasks.manager import TaskManager
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class ProgressTracker:
    """Tracks and publishes task progress."""

    def __init__(self, task_manager: TaskManager, event_bus: EventBus):
        """Initialize progress tracker.

        Args:
            task_manager: Task manager
            event_bus: Event bus
        """
        self.task_manager = task_manager
        self.event_bus = event_bus

        # Subscribe to task progress events
        self.event_bus.subscribe(EventType.TASK_PROGRESS, self._handle_progress)

    async def _handle_progress(self, event: Event) -> None:
        """Handle task progress event.

        Args:
            event: Progress event
        """
        task_id = event.data.get("task_id")
        progress = event.data.get("progress", 0.0)
        message = event.data.get("message", "")

        # Update task
        self.task_manager.update_task_progress(task_id, progress, message)

        logger.debug(f"Task {task_id} progress: {progress * 100:.1f}% - {message}")
