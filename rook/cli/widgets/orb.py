"""Animated orb widget."""
import time
from typing import List

from rich.align import Align
from rich.console import RenderableType
from rich.text import Text

from rook.cli.themes import ORB_FRAMES, Colors


class OrbWidget:
    """Animated pulsating orb that changes speed based on state."""

    def __init__(self):
        """Initialize orb widget."""
        self._frame_index = 0
        self._last_update = time.time()
        self._speed = 0.5  # Default speed (seconds per frame)

    def set_speed(self, speed: float) -> None:
        """Set animation speed.

        Args:
            speed: Delay between frames in seconds
        """
        self._speed = speed

    def update(self) -> None:
        """Update animation frame if enough time has passed."""
        if self._speed <= 0:
            return

        now = time.time()
        if now - self._last_update >= self._speed:
            self._frame_index = (self._frame_index + 1) % len(ORB_FRAMES)
            self._last_update = now

    def render(self) -> RenderableType:
        """Render the current orb frame.

        Returns:
            Rich renderable
        """
        frame = ORB_FRAMES[self._frame_index]
        lines = []

        for line in frame:
            text = Text()
            text.append(line, style=Colors.ORB)
            lines.append(text)

        # Join lines with newlines
        result = Text("\n").join(lines)

        # Center the orb
        return Align.center(result)

    def reset(self) -> None:
        """Reset animation to first frame."""
        self._frame_index = 0
        self._last_update = time.time()
