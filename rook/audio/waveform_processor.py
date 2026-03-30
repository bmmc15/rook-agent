"""Waveform processor for FFT-based visualization."""
from typing import List
import numpy as np

from rook.utils.logging import get_logger

logger = get_logger(__name__)


class WaveformProcessor:
    """Processes audio data into waveform bar heights using FFT."""

    def __init__(self, bar_count: int = 20, smoothing: float = 0.3):
        """Initialize waveform processor.

        Args:
            bar_count: Number of frequency bars
            smoothing: Smoothing factor (0-1, higher = more smoothing)
        """
        self.bar_count = bar_count
        self.smoothing = smoothing
        self._previous_bars: List[float] = [0.0] * bar_count

    def process(self, audio_data: np.ndarray) -> List[int]:
        """Process audio data into bar heights.

        Args:
            audio_data: Audio samples (float32, mono)

        Returns:
            List of bar heights (0-8)
        """
        try:
            # Ensure we have a 1D array
            if audio_data.ndim > 1:
                audio_data = audio_data.flatten()

            # Apply FFT
            fft_data = np.fft.rfft(audio_data)
            magnitudes = np.abs(fft_data)

            # Split into frequency bands
            bars = self._split_into_bars(magnitudes)

            # Normalize to 0-8 range
            bars = self._normalize_bars(bars)

            # Apply smoothing
            bars = self._smooth_bars(bars)

            # Convert to integers
            bar_heights = [int(round(bar)) for bar in bars]

            # Clamp to 0-8
            bar_heights = [max(0, min(8, h)) for h in bar_heights]

            return bar_heights

        except Exception as e:
            logger.error(f"Error processing waveform: {e}")
            return [0] * self.bar_count

    def _split_into_bars(self, magnitudes: np.ndarray) -> List[float]:
        """Split FFT magnitudes into frequency bars.

        Args:
            magnitudes: FFT magnitude array

        Returns:
            List of bar values
        """
        # Use logarithmic frequency bands (more bars for lower frequencies)
        n = len(magnitudes)
        bars = []

        for i in range(self.bar_count):
            # Calculate frequency band range (logarithmic)
            start_idx = int(n * (2 ** (i / self.bar_count) - 1))
            end_idx = int(n * (2 ** ((i + 1) / self.bar_count) - 1))

            # Ensure valid range
            start_idx = max(0, min(start_idx, n - 1))
            end_idx = max(start_idx + 1, min(end_idx, n))

            # Average magnitude in this band
            band_magnitude = np.mean(magnitudes[start_idx:end_idx])
            bars.append(band_magnitude)

        return bars

    def _normalize_bars(self, bars: List[float]) -> List[float]:
        """Normalize bars to 0-8 range.

        Args:
            bars: Raw bar values

        Returns:
            Normalized bars
        """
        if not bars:
            return []

        # Apply logarithmic scaling for better visualization
        bars = [np.log1p(bar) for bar in bars]

        # Find max value
        max_val = max(bars) if bars else 1.0
        if max_val <= 0:
            return [0.0] * len(bars)

        # Scale to 0-8
        normalized = [(bar / max_val) * 8.0 for bar in bars]
        return normalized

    def _smooth_bars(self, bars: List[float]) -> List[float]:
        """Apply smoothing to bars.

        Args:
            bars: Current bar values

        Returns:
            Smoothed bars
        """
        smoothed = []
        for i, bar in enumerate(bars):
            # Exponential moving average
            smoothed_val = (
                self.smoothing * self._previous_bars[i] + (1 - self.smoothing) * bar
            )
            smoothed.append(smoothed_val)

        # Update previous bars
        self._previous_bars = smoothed
        return smoothed

    def reset(self) -> None:
        """Reset smoothing state."""
        self._previous_bars = [0.0] * self.bar_count
