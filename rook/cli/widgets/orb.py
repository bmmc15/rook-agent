"""Animated orb widget."""
import time

from rich.align import Align
from rich.console import RenderableType
from rich.text import Text

from rook.cli.themes import Colors, ORB_FRAMES


class OrbWidget:
    """Animated orb with a smooth pulsing effect and live activity glow."""

    def __init__(self):
        self._frame_index = 0
        self._last_update = time.time()
        self._speed = 0.5
        self._activity = 0.0
        self._target_activity = 0.0

    def set_speed(self, speed: float) -> None:
        self._speed = speed

    def set_activity(self, level: float) -> None:
        self._target_activity = max(0.0, min(1.0, level))

    def update(self) -> None:
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
        frame = ORB_FRAMES[self._frame_index]
        lines = []
        center_row = len(frame) // 2
        is_active = self._activity > 0.14

        for row_index, line in enumerate(frame):
            text = Text()
            for char in line:
                if char == " ":
                    text.append(char)
                elif char == "▒":
                    text.append(char, style=Colors.ORB_DIM)
                elif char == "▓":
                    style = Colors.ORB_MID if is_active else Colors.ORB_DIM
                    text.append(char, style=style)
                else:
                    is_core_row = abs(row_index - center_row) <= 1
                    if is_active:
                        style = Colors.ORB_ACTIVE
                    elif is_core_row:
                        style = Colors.ORB
                    else:
                        style = Colors.ORB_MID
                    text.append(char, style=style)
            lines.append(text)

        result = Text("\n").join(lines)
        return Align.center(result)

    def reset(self) -> None:
        self._frame_index = 0
        self._last_update = time.time()
        self._activity = 0.0
        self._target_activity = 0.0
