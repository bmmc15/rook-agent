"""Mock voice provider for testing."""
import asyncio
from typing import AsyncIterator

from rook.audio.providers.base import BaseVoiceProvider, VoiceEvent, VoiceEventType
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class MockVoiceProvider(BaseVoiceProvider):
    """Mock voice provider that echoes input."""

    def __init__(self):
        """Initialize mock provider."""
        self._connected = False
        self._audio_queue: asyncio.Queue = asyncio.Queue()

    async def connect(self) -> None:
        """Establish mock connection."""
        logger.info("Mock voice provider connecting...")
        await asyncio.sleep(0.1)  # Simulate connection delay
        self._connected = True
        logger.info("Mock voice provider connected")

    async def disconnect(self) -> None:
        """Disconnect mock connection."""
        logger.info("Mock voice provider disconnecting...")
        self._connected = False
        logger.info("Mock voice provider disconnected")

    async def send_audio(self, audio_data: bytes) -> None:
        """Accept audio data (does nothing in mock).

        Args:
            audio_data: Audio bytes
        """
        # In mock mode, just log
        logger.debug(f"Mock received {len(audio_data)} bytes of audio")

    async def receive(self) -> AsyncIterator[VoiceEvent]:
        """Generate mock responses.

        Yields:
            VoiceEvent instances
        """
        # Simulate connection event
        yield VoiceEvent(type=VoiceEventType.CONNECTED, data={})

        # Simulate periodic responses
        counter = 0
        while self._connected:
            await asyncio.sleep(2.0)

            # Send mock transcript
            counter += 1
            yield VoiceEvent(
                type=VoiceEventType.TRANSCRIPT_FINAL,
                data={"text": f"Mock response {counter}"},
            )

            # Send mock audio
            yield VoiceEvent(
                type=VoiceEventType.AUDIO_DATA, data={"audio": b"mock_audio_data"}
            )

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
