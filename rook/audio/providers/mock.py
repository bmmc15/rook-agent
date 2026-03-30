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

    async def receive_turn(self) -> AsyncIterator[VoiceEvent]:
        """Generate one mock response turn.

        Yields:
            VoiceEvent instances
        """
        if not self._connected:
            return

        await asyncio.sleep(0.2)
        yield VoiceEvent(
            type=VoiceEventType.TRANSCRIPT_FINAL,
            data={"source": "output", "text": "Mock response", "finished": True},
        )
        yield VoiceEvent(
            type=VoiceEventType.AUDIO_DATA,
            data={"audio": b"\x00\x00" * 1024, "mime_type": "audio/pcm;rate=24000"},
        )
        yield VoiceEvent(type=VoiceEventType.TURN_COMPLETE, data={})

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
