"""Tests for orb widget."""
import time
import pytest

from rook.cli.widgets.orb import OrbWidget


def test_initialization():
    """Test orb widget initialization."""
    orb = OrbWidget()
    assert orb._frame_index == 0
    assert orb._speed == 0.5


def test_set_speed():
    """Test setting animation speed."""
    orb = OrbWidget()
    orb.set_speed(0.1)
    assert orb._speed == 0.1


def test_update_advances_frame():
    """Test update advances frame after enough time."""
    orb = OrbWidget()
    orb.set_speed(0.01)  # Very fast

    initial_frame = orb._frame_index
    time.sleep(0.02)
    orb.update()

    # Frame should have advanced
    assert orb._frame_index != initial_frame


def test_update_wraps_frame():
    """Test frame index wraps around."""
    orb = OrbWidget()
    orb.set_speed(0.001)  # Very fast

    # Advance many times
    for _ in range(20):
        time.sleep(0.002)
        orb.update()

    # Frame should still be in valid range
    assert 0 <= orb._frame_index < 6


def test_reset():
    """Test reset returns to first frame."""
    orb = OrbWidget()
    orb._frame_index = 3

    orb.reset()
    assert orb._frame_index == 0


def test_render_returns_content():
    """Test render returns renderable content."""
    orb = OrbWidget()
    content = orb.render()
    assert content is not None
