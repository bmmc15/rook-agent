"""Barge-in detection for interrupting TTS playback."""
import numpy as np

from rook.utils.logging import get_logger

logger = get_logger(__name__)


class BargeInDetector:
    """Detects when user speaks during TTS playback."""

    def __init__(self, threshold: float = 0.3):
        """Initialize barge-in detector.

        Args:
            threshold: Audio level threshold (0-1)
        """
        self.threshold = threshold

    def detect(self, audio_data: np.ndarray) -> bool:
        """Check if audio level exceeds threshold.

        Args:
            audio_data: Audio samples

        Returns:
            True if barge-in detected
        """
        try:
            # Calculate RMS level
            rms = np.sqrt(np.mean(audio_data**2))

            # Check against threshold
            return rms > self.threshold

        except Exception as e:
            logger.error(f"Error in barge-in detection: {e}")
            return False
