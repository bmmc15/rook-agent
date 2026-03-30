"""Keyboard input handler for voice activation."""
import asyncio
import sys
import select
import termios
import time
import tty
from typing import Awaitable, Callable, Optional

from rook.core.events import EventBus, Event, EventType
from rook.core.state_machine import StateMachine, AppState
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class InputHandler:
    """Handles keyboard input for voice activation."""

    def __init__(
        self,
        state_machine: StateMachine,
        event_bus: EventBus,
        on_text_submit: Optional[Callable[[str], Awaitable[None]]] = None,
        on_buffer_change: Optional[Callable[[str], None]] = None,
    ):
        """Initialize input handler.

        Args:
            state_machine: Application state machine
            event_bus: Event bus
        """
        self.state_machine = state_machine
        self.event_bus = event_bus
        self._running = False
        self._listening = False
        self._on_text_submit = on_text_submit
        self._on_buffer_change = on_buffer_change
        self._fd: Optional[int] = None
        self._original_terminal_settings = None
        self._last_space_press = 0.0
        self._command_buffer = ""

    async def start(self) -> None:
        """Start input handling."""
        if self._running:
            return

        self._running = True
        self._configure_terminal()
        logger.info("Input handler started (space = listen when text buffer is empty)")

    async def stop(self) -> None:
        """Stop input handling."""
        self._running = False
        self._restore_terminal()
        logger.info("Input handler stopped")

    async def handle_input_loop(self) -> bool:
        """Handle input in a non-blocking way.

        Returns:
            False if should quit, True otherwise
        """
        # Simple input handling for testing
        # In production, this should use proper terminal input handling
        # For now, we'll just check stdin availability

        # Check if input is available (non-blocking)
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            char = sys.stdin.read(1)
            if char:
                char = char.lower()

                if char == "\x03":
                    logger.info("Ctrl+C requested")
                    return False

                if char in ("\r", "\n"):
                    command = self._command_buffer.strip().lower()
                    raw_command = self._command_buffer.strip()
                    self._command_buffer = ""
                    self._notify_buffer_change()
                    if command in {"quit", "exit"}:
                        logger.info("Quit command requested: %s", command)
                        return False
                    if raw_command and self._on_text_submit is not None:
                        await self._on_text_submit(raw_command)
                    return True

                if char == "\x1b":
                    self._command_buffer = ""
                    self._notify_buffer_change()
                    return True

                if char in ("\x7f", "\b"):
                    self._command_buffer = self._command_buffer[:-1]
                    self._notify_buffer_change()
                    return True

                if char == " ":
                    if self._command_buffer:
                        self._command_buffer += char
                        self._notify_buffer_change()
                        return True
                    now = time.monotonic()
                    if now - self._last_space_press < 0.35:
                        return True
                    self._last_space_press = now
                    await self._toggle_listening()
                    return True

                if char.isprintable():
                    self._command_buffer += char
                    self._notify_buffer_change()

        return True

    def _notify_buffer_change(self) -> None:
        """Push the current text buffer to the UI preview callback."""
        if self._on_buffer_change is not None:
            self._on_buffer_change(self._command_buffer)

    def _configure_terminal(self) -> None:
        """Enable cbreak mode so key presses are available immediately."""
        if not sys.stdin.isatty():
            return

        self._fd = sys.stdin.fileno()
        self._original_terminal_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)

    def _restore_terminal(self) -> None:
        """Restore terminal settings when input handling stops."""
        if self._fd is None or self._original_terminal_settings is None:
            return

        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._original_terminal_settings)
        self._fd = None
        self._original_terminal_settings = None

    async def _toggle_listening(self) -> None:
        """Toggle between IDLE and LISTENING states."""
        current = self.state_machine.current_state

        if current == AppState.IDLE:
            # Start listening
            try:
                self.state_machine.transition_to(AppState.LISTENING)
                await self.event_bus.publish(
                    Event(type=EventType.STATE_CHANGED, data={"state": AppState.LISTENING})
                )
                await self.event_bus.publish(
                    Event(type=EventType.AUDIO_INPUT_STARTED, data={})
                )
                self._listening = True
                logger.info("Started listening")
            except Exception as e:
                logger.error(f"Failed to start listening: {e}")

        elif current == AppState.LISTENING:
            # Stop listening
            try:
                self.state_machine.transition_to(AppState.IDLE)
                await self.event_bus.publish(
                    Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
                )
                await self.event_bus.publish(
                    Event(type=EventType.AUDIO_INPUT_STOPPED, data={})
                )
                self._listening = False
                logger.info("Stopped listening")
            except Exception as e:
                logger.error(f"Failed to stop listening: {e}")
