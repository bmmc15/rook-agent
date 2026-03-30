"""Audio playback using sounddevice."""
import asyncio
import queue
import re
from typing import Callable, Optional
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
        self._stream_queue: queue.Queue[bytes | None] | None = None
        self._stream_task: asyncio.Task | None = None

    async def play(
        self,
        audio_data: bytes,
        mime_type: str = "audio/pcm;rate=24000",
        on_start: Optional[Callable[[], None]] = None,
        on_chunk: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        """Play audio data.

        Args:
            audio_data: Audio bytes to play
            mime_type: MIME type for the audio payload
        """
        try:
            audio_bytes, sample_rate = self._decode_audio(audio_data, mime_type)
            self._playing = True
            self._stop_requested = False
            await asyncio.to_thread(
                self._play_blocking,
                audio_bytes,
                sample_rate,
                on_start,
                on_chunk,
            )

        except Exception as e:
            logger.error(f"Failed to play audio: {e}")
            raise AudioError(f"Playback failed: {e}")
        finally:
            self._playing = False

    async def stop(self) -> None:
        """Stop current playback."""
        self._stop_requested = True
        if self._stream_queue is not None:
            try:
                self._stream_queue.put_nowait(None)
            except queue.Full:
                pass
        sd.stop()
        if self._stream_task:
            await asyncio.gather(self._stream_task, return_exceptions=True)
            self._stream_task = None
        self._stream_queue = None
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

    async def start_stream(
        self,
        mime_type: str = "audio/pcm;rate=24000",
        on_start: Optional[Callable[[], None]] = None,
        on_chunk: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        """Start a streaming playback session fed chunk by chunk."""
        if self._stream_task and not self._stream_task.done():
            raise AudioError("Playback stream already active")

        _, sample_rate = self._decode_audio(b"", mime_type)
        self._stop_requested = False
        self._playing = True
        self._stream_queue = queue.Queue()
        self._stream_task = asyncio.create_task(
            asyncio.to_thread(
                self._play_streaming_blocking,
                sample_rate,
                on_start,
                on_chunk,
            )
        )

    async def write_chunk(self, chunk: bytes) -> None:
        """Queue one PCM16 chunk for streaming playback."""
        if not chunk:
            return
        if self._stream_queue is None:
            raise AudioError("Playback stream is not active")
        self._stream_queue.put_nowait(chunk)

    async def finish_stream(self) -> None:
        """Finish the current streaming playback session."""
        if self._stream_queue is not None:
            self._stream_queue.put_nowait(None)
        if self._stream_task is not None:
            await asyncio.gather(self._stream_task, return_exceptions=True)
        self._stream_queue = None
        self._stream_task = None
        self._playing = False

    def _play_blocking(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        on_start: Optional[Callable[[], None]] = None,
        on_chunk: Optional[Callable[[bytes], None]] = None,
    ) -> None:
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
            started = False
            for start in range(0, len(audio_bytes), chunk_bytes):
                if self._stop_requested:
                    break
                chunk = audio_bytes[start : start + chunk_bytes]
                if not started:
                    started = True
                    if on_start is not None:
                        on_start()
                if on_chunk is not None:
                    on_chunk(chunk)
                stream.write(chunk)
        finally:
            try:
                stream.stop()
            except Exception:
                pass
            stream.close()
            self._stream = None

    def _play_streaming_blocking(
        self,
        sample_rate: int,
        on_start: Optional[Callable[[], None]] = None,
        on_chunk: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        """Play queued PCM16 chunks as soon as they arrive."""
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
            started = False
            while not self._stop_requested:
                if self._stream_queue is None:
                    break
                chunk = self._stream_queue.get()
                if chunk is None:
                    break
                if not started:
                    started = True
                    if on_start is not None:
                        on_start()
                if on_chunk is not None:
                    on_chunk(chunk)
                stream.write(chunk)
        finally:
            try:
                stream.stop()
            except Exception:
                pass
            stream.close()
            self._stream = None
