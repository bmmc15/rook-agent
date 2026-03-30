"""Transcript widget for the latest user and agent messages."""
from rich.console import Group, RenderableType
from rich.text import Text

from rook.cli.themes import Colors


class TranscriptWidget:
    """Displays the latest user and assistant transcripts."""

    def __init__(self):
        self._user_text = ""
        self._agent_text = ""
        self._user_pending = False
        self._agent_pending = False

    def set_user_text(self, text: str, *, pending: bool = False) -> None:
        self._user_text = text.strip()
        self._user_pending = pending

    def set_agent_text(self, text: str, *, pending: bool = False) -> None:
        self._agent_text = text.strip()
        self._agent_pending = pending

    def clear(self) -> None:
        self._user_text = ""
        self._agent_text = ""
        self._user_pending = False
        self._agent_pending = False

    def render(self) -> RenderableType:
        lines = []

        if self._user_text:
            line = Text()
            line.append("You: ", style=Colors.WAVEFORM)
            line.append(
                self._user_text,
                style=Colors.STATUS_DIM if self._user_pending else Colors.STATUS_TEXT,
            )
            lines.append(line)

        if self._agent_text:
            line = Text()
            line.append("Rook: ", style=Colors.ORB)
            line.append(
                self._agent_text,
                style=Colors.STATUS_DIM if self._agent_pending else Colors.STATUS_TEXT,
            )
            lines.append(line)

        if not lines:
            return Text("")

        return Group(*lines)
