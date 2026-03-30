"""WebSocket client for OpenClaw connection."""
import asyncio
import json
from typing import Optional
import websockets
from websockets.client import WebSocketClientProtocol

from rook.adapters.openclaw.models import (
    OpenClawMessage,
    ChatRequest,
    ChatResponse,
    TaskRequest,
    TaskResponse,
    ErrorResponse,
)
from rook.core.config import Config
from rook.utils.exceptions import OpenClawError, ConnectionError as RookConnectionError
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class OpenClawClient:
    """WebSocket client for OpenClaw agent."""

    def __init__(self, config: Config):
        """Initialize OpenClaw client.

        Args:
            config: Application configuration
        """
        self.config = config
        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3

    async def connect(self) -> None:
        """Connect to OpenClaw WebSocket."""
        if not self.config.has_openclaw_config:
            raise RookConnectionError("OpenClaw not configured")

        logger.info(f"Connecting to OpenClaw at {self.config.openclaw_ws_url}...")

        try:
            # Connect with authentication
            extra_headers = {"Authorization": f"Bearer {self.config.openclaw_api_key}"}

            self._ws = await websockets.connect(
                self.config.openclaw_ws_url, extra_headers=extra_headers
            )

            self._connected = True
            self._reconnect_attempts = 0
            logger.info("Connected to OpenClaw")

        except Exception as e:
            logger.error(f"Failed to connect to OpenClaw: {e}")
            raise RookConnectionError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """Disconnect from OpenClaw."""
        if self._ws:
            await self._ws.close()
            self._ws = None

        self._connected = False
        logger.info("Disconnected from OpenClaw")

    async def send_message(self, message: OpenClawMessage) -> None:
        """Send message to OpenClaw.

        Args:
            message: Message to send
        """
        if not self._connected or not self._ws:
            raise OpenClawError("Not connected")

        try:
            data = message.model_dump_json()
            await self._ws.send(data)
            logger.debug(f"Sent message: {message.type}")

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise OpenClawError(f"Send failed: {e}")

    async def receive_message(self) -> Optional[OpenClawMessage]:
        """Receive message from OpenClaw.

        Returns:
            Parsed message or None
        """
        if not self._connected or not self._ws:
            return None

        try:
            data = await self._ws.recv()
            message_dict = json.loads(data)

            # Parse based on type
            msg_type = message_dict.get("type")

            if msg_type == "chat_response":
                return ChatResponse(**message_dict)
            elif msg_type == "task_response":
                return TaskResponse(**message_dict)
            elif msg_type == "error":
                return ErrorResponse(**message_dict)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                return None

        except Exception as e:
            logger.error(f"Failed to receive message: {e}")
            return None

    async def send_chat(self, content: str, session_id: Optional[str] = None) -> None:
        """Send a chat message.

        Args:
            content: Message content
            session_id: Optional session ID
        """
        message = ChatRequest(content=content, session_id=session_id)
        await self.send_message(message)

    async def send_task(
        self, description: str, session_id: Optional[str] = None
    ) -> None:
        """Send a coding task request.

        Args:
            description: Task description
            session_id: Optional session ID
        """
        message = TaskRequest(description=description, session_id=session_id)
        await self.send_message(message)

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
