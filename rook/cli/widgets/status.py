"""Status bar widget."""
from rich.console import RenderableType
from rich.text import Text

from rook.cli.themes import Colors


class StatusWidget:
    """Bottom status bar with current state and instructions."""

    def __init__(self):
        self._status_text = "Initializing..."
        self._hint_text = "Ctrl+C to quit"

    def set_status(self, text: str) -> None:
        self._status_text = text

    def set_hint(self, text: str) -> None:
        self._hint_text = text

    def render(self) -> RenderableType:
        text = Text()
        text.append(f"  {self._status_text}", style=Colors.STATUS_ACCENT)
        text.append("  ", style="")
        text.append(self._hint_text, style=Colors.STATUS_DIM)
        return text
