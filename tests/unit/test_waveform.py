"""Tests for waveform processor."""
import numpy as np
import pytest

from rook.audio.waveform_processor import WaveformProcessor


def test_initialization():
    """Test waveform processor initialization."""
    processor = WaveformProcessor(bar_count=20)
    assert processor.bar_count == 20


def test_process_returns_correct_length():
    """Test process returns correct number of bars."""
    processor = WaveformProcessor(bar_count=15)

    # Generate test audio data
    audio = np.random.randn(1024).astype(np.float32)

    bars = processor.process(audio)
    assert len(bars) == 15


def test_process_returns_valid_range():
    """Test process returns values in 0-8 range."""
    processor = WaveformProcessor(bar_count=20)

    # Generate test audio data
    audio = np.random.randn(1024).astype(np.float32)

    bars = processor.process(audio)

    for bar in bars:
        assert 0 <= bar <= 8


def test_silence_produces_low_bars():
    """Test silence produces low bar heights."""
    processor = WaveformProcessor(bar_count=20)

    # Generate silence
    audio = np.zeros(1024, dtype=np.float32)

    bars = processor.process(audio)

    # Most bars should be 0 or very low
    assert sum(bars) < 10


def test_loud_sound_produces_high_bars():
    """Test loud sound produces high bar heights."""
    processor = WaveformProcessor(bar_count=20, smoothing=0.0)

    # Generate loud signal
    audio = np.ones(1024, dtype=np.float32) * 0.5

    bars = processor.process(audio)

    # Should have some high bars
    assert max(bars) > 3


def test_reset():
    """Test reset clears smoothing state."""
    processor = WaveformProcessor(bar_count=20)

    # Process some audio
    audio = np.random.randn(1024).astype(np.float32)
    processor.process(audio)

    # Reset
    processor.reset()

    # Previous bars should be zero
    assert all(b == 0.0 for b in processor._previous_bars)
