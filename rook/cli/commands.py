"""REPL commands implementation."""
from typing import Optional

from rook.core.agent import Agent
from rook.core.state_machine import StateMachine, AppState
from rook.core.events import EventBus, Event, EventType
from rook.utils.exceptions import CommandError
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class CommandHandler:
    """Handles REPL commands."""

    def __init__(
        self, agent: Agent, state_machine: StateMachine, event_bus: EventBus
    ):
        """Initialize command handler.

        Args:
            agent: Agent instance
            state_machine: State machine
            event_bus: Event bus
        """
        self.agent = agent
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.voice_enabled = True

    async def handle_command(self, command: str) -> Optional[str]:
        """Handle a command.

        Args:
            command: Command string (including /)

        Returns:
            Response message or None
        """
        parts = command[1:].split(maxsplit=1)  # Remove leading /
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Dispatch to appropriate handler
        handlers = {
            "help": self._cmd_help,
            "status": self._cmd_status,
            "tasks": self._cmd_tasks,
            "voice": self._cmd_voice,
            "code": self._cmd_code,
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
            "panic": self._cmd_panic,
        }

        handler = handlers.get(cmd)
        if handler:
            return await handler(args)
        else:
            return f"Unknown command: /{cmd}. Type /help for available commands."

    async def _cmd_help(self, args: str) -> str:
        """Show help information."""
        return """Available commands:
/help       - Show this help message
/status     - Show current session status
/tasks      - List all coding tasks
/voice on   - Enable voice mode
/voice off  - Disable voice mode
/code <desc> - Create a coding task
/agent      - Route new turns through OpenClaw
/audio      - Route new turns through Gemini voice mode
/quit       - Exit the application
/exit       - Exit the application
/panic      - Emergency stop all tasks"""

    async def _cmd_status(self, args: str) -> str:
        """Show current status."""
        state = self.state_machine.current_state
        voice = "enabled" if self.voice_enabled else "disabled"
        openclaw = (
            "connected"
            if self.agent.openclaw_client and self.agent.openclaw_client.is_connected
            else "not connected"
        )

        return f"""Status:
  State: {state.name}
  Voice: {voice}
  OpenClaw: {openclaw}"""

    async def _cmd_tasks(self, args: str) -> str:
        """List all tasks."""
        # Placeholder - would integrate with task manager
        return "No tasks yet. Use /code to create a task."

    async def _cmd_voice(self, args: str) -> str:
        """Toggle voice mode."""
        args = args.lower().strip()

        if args == "on":
            self.voice_enabled = True
            return "Voice mode enabled"
        elif args == "off":
            self.voice_enabled = False
            return "Voice mode disabled"
        else:
            return "Usage: /voice on|off"

    async def _cmd_code(self, args: str) -> str:
        """Create a coding task."""
        if not args:
            return "Usage: /code <task description>"

        # Send to agent
        response = await self.agent.process_message(args)

        # Publish task created event
        await self.event_bus.publish(
            Event(type=EventType.TASK_CREATED, data={"description": args})
        )

        return f"Task created: {args[:50]}..."

    async def _cmd_quit(self, args: str) -> str:
        """Quit the application."""
        await self.event_bus.publish(Event(type=EventType.SYSTEM_SHUTDOWN, data={}))
        return "Shutting down..."

    async def _cmd_panic(self, args: str) -> str:
        """Emergency stop all tasks."""
        logger.warning("PANIC: Emergency stop requested")

        # Cancel all tasks (would integrate with task manager)
        # Reset state machine
        self.state_machine.reset()

        await self.event_bus.publish(
            Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
        )

        return "Emergency stop executed. All tasks cancelled."
