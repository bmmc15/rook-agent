"""Audio playback using sounddevice."""
import asyncio
import re
import time
import wave
from pathlib import Path
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
            audio_bytes, sample_rate = self._decode_audio(audio_data, mime_type)
            self._write_debug_wav(audio_bytes, sample_rate)
            self._playing = True
            self._stop_requested = False
            await asyncio.to_thread(
                self._play_blocking,
                audio_bytes,
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

    def _decode_audio(self, audio_data: bytes, mime_type: str) -> tuple[bytes, int]:
        """Validate PCM audio bytes and extract the sample rate."""
        if not mime_type.startswith("audio/pcm"):
            raise AudioError(f"Unsupported audio format: {mime_type}")

        sample_rate = self.config.tts_sample_rate
        match = re.search(r"rate=(\d+)", mime_type)
        if match:
            sample_rate = int(match.group(1))

        # Keep the raw PCM16 byte stream intact for playback.
        return bytes(audio_data), sample_rate

    def _play_blocking(self, audio_bytes: bytes, sample_rate: int) -> None:
        """Play audio synchronously in a worker thread using raw PCM writes."""
        chunk_bytes = 4096
        stream = sd.RawOutputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            device=self.config.audio_device_index,
            blocksize=chunk_bytes // 2,
        )
        self._stream = stream
        try:
            stream.start()
            for start in range(0, len(audio_bytes), chunk_bytes):
                if self._stop_requested:
                    break
                stream.write(audio_bytes[start : start + chunk_bytes])
        finally:
            try:
                stream.stop()
            except Exception:
                pass
            stream.close()
            self._stream = None

    def _write_debug_wav(self, audio_bytes: bytes, sample_rate: int) -> None:
        """Persist the latest assistant reply for audio debugging."""
        debug_path = Path("data/latest_reply.wav")
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(debug_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)
