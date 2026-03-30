"""Audio capture from microphone using sounddevice."""
import asyncio
from typing import AsyncIterator, Optional
import numpy as np
import sounddevice as sd

from rook.core.config import Config
from rook.utils.exceptions import AudioError
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class AudioCapture:
    """Captures audio from microphone as an async stream."""

    def __init__(self, config: Config):
        """Initialize audio capture.

        Args:
            config: Application configuration
        """
        self.config = config
        self._stream: Optional[sd.InputStream] = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Callback for sounddevice stream.

        Args:
            indata: Input audio data
            frames: Number of frames
            time_info: Time information
            status: Stream status
        """
        if status:
            logger.warning(f"Audio callback status: {status}")

        # Copy data to avoid buffer issues
        data = indata.copy()

        # Put data in queue (non-blocking)
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            logger.warning("Audio queue full, dropping frame")

    async def start(self) -> None:
        """Start capturing audio."""
        if self._running:
            return

        logger.info("Starting audio capture...")

        try:
            self._stream = sd.InputStream(
                samplerate=self.config.audio_sample_rate,
                channels=self.config.audio_channels,
                dtype=np.float32,
                blocksize=self.config.audio_chunk_size,
                device=self.config.audio_device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._running = True
            logger.info("Audio capture started")

        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            raise AudioError(f"Failed to start audio capture: {e}")

    async def stop(self) -> None:
        """Stop capturing audio."""
        if not self._running:
            return

        logger.info("Stopping audio capture...")
        self._running = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        logger.info("Audio capture stopped")

    async def stream(self) -> AsyncIterator[np.ndarray]:
        """Stream audio chunks as they become available.

        Yields:
            Audio data as numpy arrays
        """
        while self._running:
            try:
                # Wait for data with timeout
                data = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                yield data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in audio stream: {e}")
                break

    @property
    def is_running(self) -> bool:
        """Check if capture is running."""
        return self._running
