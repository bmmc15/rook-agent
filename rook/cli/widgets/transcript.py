"""Transcript widget for the latest user and agent messages."""
from rich.console import Group, RenderableType
from rich.text import Text

from rook.cli.themes import Colors


class TranscriptWidget:
    """Displays the latest user and assistant transcripts."""

    def __init__(self):
        self._user_text = ""
        self._agent_text = ""

    def set_user_text(self, text: str) -> None:
        self._user_text = text.strip()

    def set_agent_text(self, text: str) -> None:
        self._agent_text = text.strip()

    def clear(self) -> None:
        self._user_text = ""
        self._agent_text = ""

    def render(self) -> RenderableType:
        lines = []

        if self._user_text:
            line = Text()
            line.append("You: ", style=Colors.WAVEFORM)
            line.append(self._user_text, style=Colors.STATUS_TEXT)
            lines.append(line)

        if self._agent_text:
            line = Text()
            line.append("Rook: ", style=Colors.ORB)
            line.append(self._agent_text, style=Colors.STATUS_TEXT)
            lines.append(line)

        if not lines:
            return Text("")

        return Group(*lines)
