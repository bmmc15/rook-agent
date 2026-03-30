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
        self._queue: asyncio.Queue[Optional[np.ndarray]] = asyncio.Queue(maxsize=32)
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

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

        if not self._running or self._loop is None:
            return

        # Copy data to avoid buffer issues
        data = indata.copy()

        # Hand the audio off to the event loop thread safely.
        try:
            self._loop.call_soon_threadsafe(self._enqueue_audio_frame, data)
        except RuntimeError:
            return

    def _enqueue_audio_frame(self, data: np.ndarray) -> None:
        """Push a captured frame into the async queue from the loop thread."""
        if not self._running:
            return

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
            self._loop = asyncio.get_running_loop()
            while not self._queue.empty():
                self._queue.get_nowait()

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

        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        await self._queue.put(None)
        self._loop = None
        logger.info("Audio capture stopped")

    async def stream(self) -> AsyncIterator[np.ndarray]:
        """Stream audio chunks as they become available.

        Yields:
            Audio data as numpy arrays
        """
        while True:
            try:
                data = await self._queue.get()
                if data is None:
                    break
                yield data
            except Exception as e:
                logger.error(f"Error in audio stream: {e}")
                break

    @property
    def is_running(self) -> bool:
        """Check if capture is running."""
        return self._running
