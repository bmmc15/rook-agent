"""Audio waveform visualization widget."""
from typing import List

from rich.align import Align
from rich.console import RenderableType
from rich.text import Text

from rook.cli.themes import Colors, WAVEFORM_BLOCKS


class WaveformWidget:
    """Audio waveform bars visualization."""

    def __init__(self, bar_count: int = 28):
        self._bar_count = bar_count
        self._bar_heights: List[int] = [0] * bar_count
        self._visible = False

    def set_visible(self, visible: bool) -> None:
        self._visible = visible

    def update_bars(self, heights: List[int]) -> None:
        if len(heights) < self._bar_count:
            heights = heights + [0] * (self._bar_count - len(heights))
        elif len(heights) > self._bar_count:
            heights = heights[: self._bar_count]

        self._bar_heights = heights

    def clear(self) -> None:
        self._bar_heights = [0] * self._bar_count

    def render(self) -> RenderableType:
        if not self._visible:
            return Text("")

        text = Text()
        for height in self._bar_heights:
            height = max(0, min(8, height))
            text.append(WAVEFORM_BLOCKS[height] * 2, style=Colors.WAVEFORM)

        return Align.center(text)
