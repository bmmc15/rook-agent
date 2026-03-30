"""Rich Live renderer for the terminal UI."""
import asyncio
from typing import Optional

from rich.console import Console
from rich.live import Live

from rook.cli.themes import rook_theme
from rook.cli.widgets.panel import MainPanel
from rook.core.state_machine import StateMachine, AppState
from rook.core.events import EventBus, Event, EventType


class Renderer:
    """Manages the Rich Live display loop."""

    def __init__(
        self,
        console: Console,
        state_machine: StateMachine,
        event_bus: EventBus,
        refresh_rate: int = 30,
    ):
        """Initialize renderer.

        Args:
            console: Rich console instance
            state_machine: Application state machine
            event_bus: Event bus for updates
            refresh_rate: Refresh rate in FPS
        """
        self._console = console
        self._state_machine = state_machine
        self._event_bus = event_bus
        self._refresh_rate = refresh_rate
        self._panel = MainPanel()
        self._live: Optional[Live] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the rendering loop."""
        if self._running:
            return

        self._running = True

        # Subscribe to events
        self._event_bus.subscribe(EventType.STATE_CHANGED, self._on_state_changed)
        self._event_bus.subscribe(EventType.AUDIO_LEVEL_UPDATED, self._on_audio_level)

        # Create Live display
        self._live = Live(
            self._panel.render(),
            console=self._console,
            refresh_per_second=self._refresh_rate,
            transient=False,
        )

        # Start Live display
        self._live.start()

        # Start render loop
        self._task = asyncio.create_task(self._render_loop())

    async def stop(self) -> None:
        """Stop the rendering loop."""
        if not self._running:
            return

        self._running = False

        # Stop render loop
        if self._task:
            await self._task
            self._task = None

        # Stop Live display
        if self._live:
            self._live.stop()
            self._live = None

        # Unsubscribe from events
        self._event_bus.unsubscribe(EventType.STATE_CHANGED, self._on_state_changed)
        self._event_bus.unsubscribe(EventType.AUDIO_LEVEL_UPDATED, self._on_audio_level)

    async def _render_loop(self) -> None:
        """Main rendering loop."""
        frame_time = 1.0 / self._refresh_rate

        while self._running:
            try:
                # Update animations
                self._panel.orb.update()

                # Update display
                if self._live:
                    self._live.update(self._panel.render())

                # Wait for next frame
                await asyncio.sleep(frame_time)

            except Exception as e:
                # Don't crash the render loop
                pass

    async def _on_state_changed(self, event: Event) -> None:
        """Handle state change events.

        Args:
            event: State change event
        """
        state = self._state_machine.current_state

        # Update orb speed based on state
        orb_speed = self._state_machine.get_orb_speed()
        self._panel.orb.set_speed(orb_speed)

        # Update status text
        status_text = self._state_machine.get_status_text()
        self._panel.status.set_status(status_text)

        # Show/hide waveform
        show_waveform = self._state_machine.should_show_waveform()
        self._panel.waveform.set_visible(show_waveform)

        if not show_waveform:
            self._panel.waveform.clear()

    async def _on_audio_level(self, event: Event) -> None:
        """Handle audio level updates.

        Args:
            event: Audio level event with bar heights
        """
        bar_heights = event.data.get("bar_heights", [])
        self._panel.waveform.update_bars(bar_heights)

    def update_status(self, text: str) -> None:
        """Manually update status text.

        Args:
            text: Status message
        """
        self._panel.status.set_status(text)

    def update_hint(self, text: str) -> None:
        """Manually update hint text.

        Args:
            text: Hint message
        """
        self._panel.status.set_hint(text)

    def update_user_transcript(self, text: str, *, pending: bool = False) -> None:
        """Update the latest user transcript shown in the panel."""
        self._panel.transcript.set_user_text(text, pending=pending)

    def update_agent_transcript(self, text: str, *, pending: bool = False) -> None:
        """Update the latest assistant transcript shown in the panel."""
        self._panel.transcript.set_agent_text(text, pending=pending)

    def clear_transcripts(self) -> None:
        """Clear the transcript area."""
        self._panel.transcript.clear()

    def update_orb_activity(self, level: float) -> None:
        """Drive the orb with live speaking energy."""
        self._panel.orb.set_activity(level)
