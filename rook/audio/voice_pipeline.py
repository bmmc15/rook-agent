"""Voice pipeline orchestrating STT, agent, and TTS."""
import asyncio
from typing import Optional

from rook.audio.capture import AudioCapture
from rook.audio.playback import AudioPlayback
from rook.audio.barge_in import BargeInDetector
from rook.audio.providers.base import BaseVoiceProvider
from rook.core.events import EventBus, Event, EventType
from rook.core.state_machine import StateMachine, AppState
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class VoicePipeline:
    """Orchestrates the voice interaction flow."""

    def __init__(
        self,
        voice_provider: BaseVoiceProvider,
        audio_capture: AudioCapture,
        audio_playback: AudioPlayback,
        state_machine: StateMachine,
        event_bus: EventBus,
    ):
        """Initialize voice pipeline.

        Args:
            voice_provider: Voice service provider
            audio_capture: Audio capture instance
            audio_playback: Audio playback instance
            state_machine: Application state machine
            event_bus: Event bus
        """
        self.voice_provider = voice_provider
        self.audio_capture = audio_capture
        self.audio_playback = audio_playback
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.barge_in = BargeInDetector()

        self._running = False

    async def start(self) -> None:
        """Start the voice pipeline."""
        if self._running:
            return

        logger.info("Starting voice pipeline...")
        self._running = True

        # Connect to voice provider
        await self.voice_provider.connect()

        logger.info("Voice pipeline started")

    async def stop(self) -> None:
        """Stop the voice pipeline."""
        if not self._running:
            return

        logger.info("Stopping voice pipeline...")
        self._running = False

        # Disconnect from voice provider
        await self.voice_provider.disconnect()

        logger.info("Voice pipeline stopped")

    async def process_voice_input(self) -> None:
        """Process voice input when in LISTENING state."""
        # This would handle the STT → Agent → TTS flow
        # Placeholder for now
        pass
