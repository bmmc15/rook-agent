"""Renderer replacement that streams runtime updates to the macOS shell."""
import asyncio
from typing import Any, Awaitable, Callable, Optional

from rook.core.events import Event, EventBus, EventType
from rook.core.state_machine import StateMachine


EmitEvent = Callable[[dict[str, Any]], Awaitable[None]]


class BridgeRenderer:
    """Mirror runtime state and transcript updates to an external UI shell."""

    def __init__(
        self,
        *,
        state_machine: Optional[StateMachine],
        event_bus: Optional[EventBus],
        emit_event: EmitEvent,
    ):
        self._state_machine = state_machine
        self._event_bus = event_bus
        self._emit_event = emit_event
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False

    def configure_runtime(self, *, state_machine: StateMachine, event_bus: EventBus) -> None:
        """Attach the runtime objects after the app is created."""
        self._state_machine = state_machine
        self._event_bus = event_bus

    async def start(self) -> None:
        """Subscribe to runtime events."""
        if self._running:
            return

        if self._state_machine is None or self._event_bus is None:
            raise RuntimeError("BridgeRenderer requires a state machine and event bus before start()")

        self._running = True
        self._loop = asyncio.get_running_loop()
        self._event_bus.subscribe(EventType.STATE_CHANGED, self._on_state_changed)
        self._event_bus.subscribe(EventType.AUDIO_LEVEL_UPDATED, self._on_audio_level)
        self._event_bus.subscribe(EventType.AGENT_CONNECTED, self._on_openclaw_connected)
        self._event_bus.subscribe(EventType.AGENT_DISCONNECTED, self._on_openclaw_disconnected)

    async def stop(self) -> None:
        """Unsubscribe from runtime events."""
        if not self._running:
            return

        self._running = False
        self._event_bus.unsubscribe(EventType.STATE_CHANGED, self._on_state_changed)
        self._event_bus.unsubscribe(EventType.AUDIO_LEVEL_UPDATED, self._on_audio_level)
        self._event_bus.unsubscribe(EventType.AGENT_CONNECTED, self._on_openclaw_connected)
        self._event_bus.unsubscribe(EventType.AGENT_DISCONNECTED, self._on_openclaw_disconnected)
        self._loop = None

    async def _on_state_changed(self, event: Event) -> None:
        """Forward state transitions."""
        await self._emit_event(
            {
                "type": "state",
                "state": self._state_machine.current_state.name.lower(),
                "status": self._state_machine.get_status_text(),
            }
        )

    async def _on_audio_level(self, event: Event) -> None:
        """Forward listening audio activity."""
        bars = [float(value) for value in event.data.get("bar_heights", [])]
        level = max(bars, default=0.0)
        await self._emit_event(
            {
                "type": "audio_level",
                "bars": bars,
                "level": level,
            }
        )

    async def _on_openclaw_connected(self, event: Event) -> None:
        """Forward OpenClaw connectivity."""
        await self._emit_event(
            {
                "type": "connection",
                "target": "openclaw",
                "status": "connected",
            }
        )

    async def _on_openclaw_disconnected(self, event: Event) -> None:
        """Forward OpenClaw connectivity."""
        await self._emit_event(
            {
                "type": "connection",
                "target": "openclaw",
                "status": "disconnected",
            }
        )

    def update_status(self, text: str) -> None:
        """Forward status banner updates."""
        self._schedule_emit({"type": "status", "text": text})

    def update_hint(self, text: str) -> None:
        """Forward hint updates."""
        self._schedule_emit({"type": "hint", "text": text})

    def update_user_transcript(self, text: str, *, pending: bool = False) -> None:
        """Forward the latest user transcript."""
        self._schedule_emit(
            {
                "type": "transcript",
                "role": "user",
                "text": text,
                "pending": pending,
            }
        )

    def update_agent_transcript(self, text: str, *, pending: bool = False) -> None:
        """Forward the latest assistant transcript."""
        self._schedule_emit(
            {
                "type": "transcript",
                "role": "assistant",
                "text": text,
                "pending": pending,
            }
        )

    def clear_transcripts(self) -> None:
        """Tell the native shell to clear the active transcript turn."""
        self._schedule_emit({"type": "transcript_clear"})

    def update_orb_activity(self, level: float) -> None:
        """Forward speaking activity for the animated orb."""
        self._schedule_emit({"type": "speaking_level", "level": float(level)})

    def _schedule_emit(self, payload: dict[str, Any]) -> None:
        """Schedule a JSON payload from sync code paths."""
        if not self._running or self._loop is None or self._loop.is_closed():
            return

        async def _emit() -> None:
            await self._emit_event(payload)

        self._loop.call_soon_threadsafe(lambda: asyncio.create_task(_emit()))
