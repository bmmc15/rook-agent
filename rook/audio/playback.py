"""Audio playback using sounddevice."""
import asyncio
import re
import time
import numpy as np
import sounddevice as sd

from rook.core.config import Config
from rook.utils.exceptions import AudioError
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class AudioPlayback:
    """Plays audio through speakers."""

    def __init__(self, config: Config):
        """Initialize audio playback.

        Args:
            config: Application configuration
        """
        self.config = config
        self._stream: sd.OutputStream | None = None
        self._playing = False
        self._stop_requested = False

    async def play(self, audio_data: bytes, mime_type: str = "audio/pcm;rate=24000") -> None:
        """Play audio data.

        Args:
            audio_data: Audio bytes to play
            mime_type: MIME type for the audio payload
        """
        try:
            audio_array, sample_rate = self._decode_audio(audio_data, mime_type)
            self._playing = True
            self._stop_requested = False
            await asyncio.to_thread(
                self._play_blocking,
                audio_array,
                sample_rate,
            )

        except Exception as e:
            logger.error(f"Failed to play audio: {e}")
            raise AudioError(f"Playback failed: {e}")
        finally:
            self._playing = False

    async def stop(self) -> None:
        """Stop current playback."""
        self._stop_requested = True
        sd.stop()
        self._playing = False

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self._playing

    def _decode_audio(self, audio_data: bytes, mime_type: str) -> tuple[np.ndarray, int]:
        """Decode PCM audio bytes into an int16 numpy array."""
        if not mime_type.startswith("audio/pcm"):
            raise AudioError(f"Unsupported audio format: {mime_type}")

        sample_rate = self.config.tts_sample_rate
        match = re.search(r"rate=(\d+)", mime_type)
        if match:
            sample_rate = int(match.group(1))

        audio_array = np.frombuffer(audio_data, dtype=np.int16).copy()
        return audio_array, sample_rate

    def _play_blocking(self, audio_array: np.ndarray, sample_rate: int) -> None:
        """Play audio synchronously in a worker thread."""
        sd.play(
            audio_array,
            samplerate=sample_rate,
            device=self.config.audio_device_index,
        )
        while sd.get_stream().active:
            if self._stop_requested:
                sd.stop()
                break
            time.sleep(0.05)
