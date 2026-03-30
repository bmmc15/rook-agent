"""Animated orb widget."""
import time

from rich.align import Align
from rich.console import RenderableType
from rich.text import Text

from rook.cli.themes import Colors, ORB_FRAMES


class OrbWidget:
    """Animated orb using the original smooth frame set plus live activity."""

    def __init__(self):
        """Initialize orb widget."""
        self._frame_index = 0
        self._last_update = time.time()
        self._speed = 0.5  # Default speed (seconds per frame)
        self._activity = 0.0
        self._target_activity = 0.0

    def set_speed(self, speed: float) -> None:
        """Set animation speed.

        Args:
            speed: Delay between frames in seconds
        """
        self._speed = speed

    def set_activity(self, level: float) -> None:
        """Set orb animation intensity based on agent speech energy."""
        self._target_activity = max(0.0, min(1.0, level))

    def update(self) -> None:
        """Update animation frame if enough time has passed."""
        now = time.time()
        delta = max(0.0, now - self._last_update)

        decay = 0.88 if self._speed <= 0 else 0.94
        self._activity = max(self._target_activity, self._activity * decay)
        self._target_activity *= 0.6

        if self._speed > 0:
            cadence = self._speed / max(0.45, 1.0 + self._activity * 2.2)
            if delta >= cadence:
                self._frame_index = (self._frame_index + 1) % len(ORB_FRAMES)
                self._last_update = now
        else:
            self._last_update = now

    def render(self) -> RenderableType:
        """Render the current orb frame.

        Returns:
            Rich renderable
        """
        frame = ORB_FRAMES[self._frame_index]
        lines = []

        for row_index, line in enumerate(frame):
            text = Text()
            for char in line:
                if char == " ":
                    text.append(char)
                elif char in {"░", "▒"}:
                    text.append(char, style=Colors.ORB_DIM)
                else:
                    style = Colors.ORB if self._activity > 0.18 or row_index == 1 else Colors.ORB_DIM
                    text.append(char, style=style)
            lines.append(text)

        # Join lines with newlines
        result = Text("\n").join(lines)

        # Center the orb
        return Align.center(result)

    def reset(self) -> None:
        """Reset animation to first frame."""
        self._frame_index = 0
        self._last_update = time.time()
        self._activity = 0.0
        self._target_activity = 0.0
