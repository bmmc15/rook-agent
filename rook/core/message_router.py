"""Message routing logic."""
from typing import Optional

from rook.adapters.openclaw.client import OpenClawClient
from rook.core.config import Config
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class MessageRouter:
    """Routes messages to appropriate handlers."""

    def __init__(self, config: Config, openclaw_client: Optional[OpenClawClient] = None):
        """Initialize message router.

        Args:
            config: Application configuration
            openclaw_client: Optional OpenClaw client
        """
        self.config = config
        self.openclaw_client = openclaw_client

    async def route_message(self, content: str) -> str:
        """Route message to appropriate handler.

        Args:
            content: Message content

        Returns:
            Response text
        """
        # Check if this is a coding task request
        if self._is_coding_task(content):
            return await self._handle_coding_task(content)

        # Otherwise, route to chat
        return await self._handle_chat(content)

    def _is_coding_task(self, content: str) -> bool:
        """Check if message is a coding task.

        Args:
            content: Message content

        Returns:
            True if coding task
        """
        # Simple heuristic - check for coding keywords
        coding_keywords = ["code", "implement", "fix", "refactor", "write", "create"]
        content_lower = content.lower()

        return any(keyword in content_lower for keyword in coding_keywords)

    async def _handle_chat(self, content: str) -> str:
        """Handle chat message.

        Args:
            content: Message content

        Returns:
            Response text
        """
        if self.openclaw_client and self.openclaw_client.is_connected:
            # Send to OpenClaw
            request_id = await self.openclaw_client.send_chat(content)
            # Response will come via streaming
            return f"OpenClaw request sent ({request_id[:8]}...)"

        else:
            # No OpenClaw - generate local response
            return f"Echo: {content}"

    async def _handle_coding_task(self, content: str) -> str:
        """Handle coding task request.

        Args:
            content: Task description

        Returns:
            Response text
        """
        if self.openclaw_client and self.openclaw_client.is_connected:
            # Send to OpenClaw as a task
            request_id = await self.openclaw_client.send_task(content)
            return f"OpenClaw task sent ({request_id[:8]}...)"

        else:
            # No OpenClaw - return error
            return "Error: OpenClaw not configured for coding tasks"
