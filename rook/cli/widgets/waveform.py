"""Audio waveform visualization widget."""
from typing import List

from rich.align import Align
from rich.console import Group, RenderableType
from rich.text import Text

from rook.cli.themes import Colors, WAVEFORM_BLOCKS


class WaveformWidget:
    """Green audio waveform bars visualization."""

    def __init__(self, bar_count: int = 28):
        """Initialize waveform widget.

        Args:
            bar_count: Number of bars to display
        """
        self._bar_count = bar_count
        self._bar_heights: List[int] = [0] * bar_count
        self._visible = False

    def set_visible(self, visible: bool) -> None:
        """Set waveform visibility.

        Args:
            visible: Whether to show waveform
        """
        self._visible = visible

    def update_bars(self, heights: List[int]) -> None:
        """Update bar heights.

        Args:
            heights: List of heights (0-8) for each bar
        """
        # Pad or trim to match bar_count
        if len(heights) < self._bar_count:
            heights = heights + [0] * (self._bar_count - len(heights))
        elif len(heights) > self._bar_count:
            heights = heights[: self._bar_count]

        self._bar_heights = heights

    def clear(self) -> None:
        """Clear all bars to zero."""
        self._bar_heights = [0] * self._bar_count

    def render(self) -> RenderableType:
        """Render the waveform.

        Returns:
            Rich renderable
        """
        if not self._visible:
            return Text("")

        label = Text("YOU", style=Colors.WAVEFORM)
        text = Text()
        for height in self._bar_heights:
            height = max(0, min(8, height))
            text.append(WAVEFORM_BLOCKS[height] * 2, style=Colors.WAVEFORM)

        return Group(
            Align.center(label),
            Align.center(text),
        )
