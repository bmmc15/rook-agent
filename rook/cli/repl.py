"""REPL (Read-Eval-Print Loop) for text commands."""
import asyncio
from typing import Optional

from rook.cli.commands import CommandHandler
from rook.core.agent import Agent
from rook.core.events import EventBus, Event, EventType
from rook.core.state_machine import StateMachine
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class REPL:
    """Read-Eval-Print Loop for text interaction."""

    def __init__(
        self, agent: Agent, state_machine: StateMachine, event_bus: EventBus
    ):
        """Initialize REPL.

        Args:
            agent: Agent instance
            state_machine: State machine
            event_bus: Event bus
        """
        self.agent = agent
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.command_handler = CommandHandler(agent, state_machine, event_bus)
        self._running = False

    async def start(self) -> None:
        """Start the REPL."""
        if self._running:
            return

        self._running = True
        logger.info("REPL started")

    async def stop(self) -> None:
        """Stop the REPL."""
        self._running = False
        logger.info("REPL stopped")

    async def process_input(self, text: str) -> Optional[str]:
        """Process user input.

        Args:
            text: Input text

        Returns:
            Response message or None
        """
        text = text.strip()

        if not text:
            return None

        # Check if it's a command (starts with /)
        if text.startswith("/"):
            return await self.command_handler.handle_command(text)

        # Otherwise, treat as chat message
        return await self.agent.process_message(text)

    def is_command(self, text: str) -> bool:
        """Check if input is a command.

        Args:
            text: Input text

        Returns:
            True if command
        """
        return text.strip().startswith("/")
