"""Central agent coordinator."""
from typing import Optional

from rook.adapters.openclaw.client import OpenClawClient
from rook.adapters.openclaw.streaming import OpenClawStreamingHandler
from rook.core.config import Config
from rook.core.events import EventBus, Event, EventType
from rook.core.message_router import MessageRouter
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class Agent:
    """Central agent that coordinates all interactions."""

    def __init__(self, config: Config, event_bus: EventBus):
        """Initialize agent.

        Args:
            config: Application configuration
            event_bus: Event bus
        """
        self.config = config
        self.event_bus = event_bus

        # Initialize OpenClaw client if configured
        self.openclaw_client: Optional[OpenClawClient] = None
        self.openclaw_streaming: Optional[OpenClawStreamingHandler] = None

        if config.has_openclaw_config:
            self.openclaw_client = OpenClawClient(config)
            self.openclaw_streaming = OpenClawStreamingHandler(
                self.openclaw_client, event_bus
            )

        # Initialize message router
        self.router = MessageRouter(config, self.openclaw_client)

        self._running = False

    async def start(self) -> None:
        """Start the agent."""
        if self._running:
            return

        logger.info("Starting agent...")

        # Connect to OpenClaw if available
        await self.ensure_openclaw_connected()

        self._running = True
        logger.info("Agent started")

    async def stop(self) -> None:
        """Stop the agent."""
        if not self._running:
            return

        logger.info("Stopping agent...")

        # Disconnect from OpenClaw
        if self.openclaw_streaming:
            await self.openclaw_streaming.stop()

        if self.openclaw_client:
            await self.openclaw_client.disconnect()
            await self.event_bus.publish(
                Event(type=EventType.AGENT_DISCONNECTED, data={})
            )

        self._running = False
        logger.info("Agent stopped")

    async def ensure_openclaw_connected(self) -> bool:
        """Ensure OpenClaw is connected, retrying on demand when needed."""
        if not self.openclaw_client:
            return False

        if self.openclaw_client.is_connected:
            return True

        try:
            await self.openclaw_client.connect()
            if self.openclaw_streaming:
                await self.openclaw_streaming.start()

            await self.event_bus.publish(
                Event(type=EventType.AGENT_CONNECTED, data={})
            )
            return True
        except Exception as e:
            logger.warning(f"Could not connect to OpenClaw: {e}")
            return False

    async def process_message(self, content: str) -> str:
        """Process a user message.

        Args:
            content: Message content

        Returns:
            Response text
        """
        logger.info(f"Processing message: {content[:50]}...")

        # Publish event
        await self.event_bus.publish(
            Event(type=EventType.AGENT_MESSAGE_SENT, data={"content": content})
        )

        # Route message
        response = await self.router.route_message(content)

        return response
