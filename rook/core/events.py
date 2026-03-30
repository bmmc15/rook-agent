"""Event bus for async publish-subscribe communication."""
import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    """Base event class."""

    type: str
    data: Any
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Async event bus for publish-subscribe pattern."""

    def __init__(self):
        """Initialize event bus."""
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Type of event to listen for
            handler: Async function to handle events
        """
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: Type of event
            handler: Handler to remove
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Event to publish
        """
        await self._event_queue.put(event)

    async def _process_events(self) -> None:
        """Process events from the queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            handlers = self._subscribers.get(event.type, [])
            if handlers:
                # Run all handlers concurrently
                await asyncio.gather(
                    *[handler(event) for handler in handlers],
                    return_exceptions=True,
                )

    async def start(self) -> None:
        """Start processing events."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        """Stop processing events and wait for completion."""
        if not self._running:
            return

        self._running = False
        if self._task:
            await self._task
            self._task = None

    def clear(self) -> None:
        """Clear all subscribers."""
        self._subscribers.clear()

    def get_subscriber_count(self, event_type: Optional[str] = None) -> int:
        """Get number of subscribers.

        Args:
            event_type: Specific event type, or None for total

        Returns:
            Number of subscribers
        """
        if event_type is not None:
            return len(self._subscribers.get(event_type, []))
        return sum(len(handlers) for handlers in self._subscribers.values())


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Common event types
class EventType:
    """Common event type constants."""

    # State changes
    STATE_CHANGED = "state.changed"

    # Audio events
    AUDIO_INPUT_STARTED = "audio.input.started"
    AUDIO_INPUT_STOPPED = "audio.input.stopped"
    AUDIO_OUTPUT_STARTED = "audio.output.started"
    AUDIO_OUTPUT_STOPPED = "audio.output.stopped"
    AUDIO_LEVEL_UPDATED = "audio.level.updated"
    BARGE_IN_DETECTED = "audio.barge_in.detected"

    # Voice events
    VOICE_TRANSCRIPT_PARTIAL = "voice.transcript.partial"
    VOICE_TRANSCRIPT_FINAL = "voice.transcript.final"
    VOICE_RESPONSE_STARTED = "voice.response.started"
    VOICE_RESPONSE_COMPLETED = "voice.response.completed"

    # Task events
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"

    # Agent events
    AGENT_MESSAGE_SENT = "agent.message.sent"
    AGENT_MESSAGE_RECEIVED = "agent.message.received"
    AGENT_CONNECTED = "agent.connected"
    AGENT_DISCONNECTED = "agent.disconnected"

    # UI events
    UI_COMMAND_ENTERED = "ui.command.entered"
    UI_REFRESH = "ui.refresh"

    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_SHUTDOWN = "system.shutdown"
