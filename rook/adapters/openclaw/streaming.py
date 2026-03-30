"""Streaming message handler for OpenClaw."""
import asyncio
from typing import AsyncIterator

from rook.adapters.openclaw.client import OpenClawClient
from rook.adapters.openclaw.models import OpenClawMessage
from rook.core.events import EventBus, Event, EventType
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class OpenClawStreamingHandler:
    """Handles streaming messages from OpenClaw."""

    def __init__(self, client: OpenClawClient, event_bus: EventBus):
        """Initialize streaming handler.

        Args:
            client: OpenClaw client
            event_bus: Event bus for publishing events
        """
        self.client = client
        self.event_bus = event_bus
        self._running = False

    async def start(self) -> None:
        """Start message streaming."""
        if self._running:
            return

        self._running = True
        logger.info("Starting OpenClaw message streaming...")

        # Start streaming task
        asyncio.create_task(self._stream_messages())

    async def stop(self) -> None:
        """Stop message streaming."""
        self._running = False
        logger.info("Stopped OpenClaw message streaming")

    async def _stream_messages(self) -> None:
        """Stream messages from OpenClaw."""
        while self._running:
            try:
                message = await self.client.receive_message()

                if message:
                    await self._handle_message(message)

            except Exception as e:
                logger.error(f"Error in message stream: {e}")
                await asyncio.sleep(1)  # Backoff on error

    async def _handle_message(self, message: OpenClawMessage) -> None:
        """Handle received message.

        Args:
            message: Received message
        """
        # Publish appropriate event based on message type
        if message.type == "chat_response":
            await self.event_bus.publish(
                Event(
                    type=EventType.AGENT_MESSAGE_RECEIVED,
                    data={"content": message.content},
                )
            )

        elif message.type == "task_response":
            await self.event_bus.publish(
                Event(
                    type=EventType.TASK_CREATED,
                    data={"task_id": message.task_id, "status": message.status},
                )
            )

        elif message.type == "task_progress":
            await self.event_bus.publish(
                Event(
                    type=EventType.TASK_PROGRESS,
                    data={
                        "task_id": message.task_id,
                        "progress": message.progress,
                        "message": message.message,
                    },
                )
            )

        elif message.type == "error":
            await self.event_bus.publish(
                Event(type=EventType.SYSTEM_ERROR, data={"error": message.error})
            )
