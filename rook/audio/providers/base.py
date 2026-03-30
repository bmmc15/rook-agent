"""Base voice provider interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, Optional


class VoiceEventType(Enum):
    """Types of voice events."""

    TRANSCRIPT_PARTIAL = "transcript_partial"
    TRANSCRIPT_FINAL = "transcript_final"
    AUDIO_DATA = "audio_data"
    TURN_COMPLETE = "turn_complete"
    ERROR = "error"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass
class VoiceEvent:
    """Voice provider event."""

    type: VoiceEventType
    data: dict


class BaseVoiceProvider(ABC):
    """Abstract base class for voice providers."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to voice service."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from voice service."""
        pass

    @abstractmethod
    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio data to the service.

        Args:
            audio_data: Audio bytes to send
        """
        pass

    @abstractmethod
    async def receive(self) -> AsyncIterator[VoiceEvent]:
        """Receive events from the service.

        Yields:
            VoiceEvent instances
        """
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to service."""
        pass
