"""Task executor for running coding tasks."""
from typing import Optional

from rook.adapters.openclaw.client import OpenClawClient
from rook.core.events import EventBus
from rook.tasks.manager import TaskManager
from rook.tasks.states import TaskState
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class TaskExecutor:
    """Executes coding tasks via OpenClaw."""

    def __init__(
        self,
        task_manager: TaskManager,
        openclaw_client: Optional[OpenClawClient],
        event_bus: EventBus,
    ):
        """Initialize task executor.

        Args:
            task_manager: Task manager
            openclaw_client: OpenClaw client (optional)
            event_bus: Event bus
        """
        self.task_manager = task_manager
        self.openclaw_client = openclaw_client
        self.event_bus = event_bus

    async def execute_task(self, task_id: str) -> None:
        """Execute a task.

        Args:
            task_id: Task ID
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            logger.error(f"Task not found: {task_id}")
            return

        # Update state to running
        self.task_manager.update_task_state(task_id, TaskState.RUNNING)

        try:
            # Execute via OpenClaw if available
            if self.openclaw_client and self.openclaw_client.is_connected:
                await self.openclaw_client.send_task(task.description)
                logger.info(f"Task {task_id} sent to OpenClaw")

            else:
                # No OpenClaw - mark as failed
                self.task_manager.update_task_state(
                    task_id, TaskState.FAILED, error="OpenClaw not available"
                )
                logger.warning(f"Cannot execute task {task_id}: OpenClaw not available")

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            self.task_manager.update_task_state(task_id, TaskState.FAILED, error=str(e))
