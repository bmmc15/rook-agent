"""Streaming message handler for OpenClaw gateway events."""
from __future__ import annotations

import asyncio

from rook.adapters.openclaw.client import OpenClawClient
from rook.adapters.openclaw.models import GatewayEnvelope
from rook.core.events import EventBus, Event, EventType
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class OpenClawStreamingHandler:
    """Consumes streamed `chat` and `agent` gateway events."""

    def __init__(self, client: OpenClawClient, event_bus: EventBus):
        self.client = client
        self.event_bus = event_bus
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._stream_messages())
        logger.info("Started OpenClaw gateway event streaming")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        logger.info("Stopped OpenClaw gateway event streaming")

    async def _stream_messages(self) -> None:
        while self._running:
            message = await self.client.receive_message()
            if message is None:
                await asyncio.sleep(0.1)
                continue
            await self._handle_message(message)

    async def _handle_message(self, message: GatewayEnvelope) -> None:
        kind = message.kind
        payload = message.payload()

        if kind.startswith("chat"):
            content = self._extract_text(payload)
            if content:
                await self.event_bus.publish(
                    Event(
                        type=EventType.AGENT_MESSAGE_RECEIVED,
                        data={
                            "content": content,
                            "state": payload.get("state"),
                            "run_id": payload.get("runId"),
                            "session_key": payload.get("sessionKey"),
                        },
                    )
                )
            return

        if kind.startswith("agent"):
            content = self._extract_text(payload)
            if content:
                await self.event_bus.publish(
                    Event(
                        type=EventType.AGENT_MESSAGE_RECEIVED,
                        data={
                            "content": content,
                            "state": payload.get("state"),
                            "run_id": payload.get("runId"),
                            "session_key": payload.get("sessionKey"),
                        },
                    )
                )
            phase = None
            data = payload.get("data")
            if isinstance(data, dict):
                phase = data.get("phase")
            await self.event_bus.publish(
                Event(
                    type=EventType.TASK_PROGRESS,
                    data={
                        "task_id": payload.get("taskId") or payload.get("id"),
                        "progress": payload.get("progress", 0.0),
                        "message": payload.get("message") or payload.get("status") or phase or kind,
                        "phase": phase,
                        "run_id": payload.get("runId"),
                        "session_key": payload.get("sessionKey"),
                    },
                )
            )
            return

        if message.error:
            await self.event_bus.publish(
                Event(type=EventType.SYSTEM_ERROR, data={"error": message.error})
            )

    def _extract_text(self, payload: dict) -> str:
        """Flatten the common chat/agent payload shapes into plain text."""
        direct_text = payload.get("content") or payload.get("text") or payload.get("delta")
        if isinstance(direct_text, str):
            return direct_text

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("text", "delta", "message"):
                value = data.get(key)
                if isinstance(value, str):
                    return value

        message = payload.get("message")
        if isinstance(message, str):
            return message
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                chunks: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str):
                            chunks.append(text)
                return " ".join(chunk.strip() for chunk in chunks if chunk.strip())

        return ""
