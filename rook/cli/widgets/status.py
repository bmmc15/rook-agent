"""Status bar widget."""
from rich.console import RenderableType
from rich.text import Text

from rook.cli.themes import Colors


class StatusWidget:
    """Bottom status bar with current state and instructions."""

    def __init__(self):
        """Initialize status widget."""
        self._status_text = "Initializing..."
        self._hint_text = "Ctrl+C to quit"

    def set_status(self, text: str) -> None:
        """Set status text.

        Args:
            text: Status message
        """
        self._status_text = text

    def set_hint(self, text: str) -> None:
        """Set hint text.

        Args:
            text: Hint message
        """
        self._hint_text = text

    def render(self) -> RenderableType:
        """Render the status bar.

        Returns:
            Rich renderable
        """
        text = Text()
        text.append(self._status_text, style=Colors.STATUS_TEXT)
        text.append("  ", style="")
        text.append(self._hint_text, style=Colors.STATUS_DIM)
        return text
