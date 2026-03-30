"""Transcript widget for the latest user and agent messages."""
from rich.console import Group, RenderableType
from rich.text import Text

from rook.cli.themes import Colors


class TranscriptWidget:
    """Displays the latest user and assistant transcripts with sidebar quote bars."""

    def __init__(self):
        self._user_text = ""
        self._agent_text = ""
        self._user_pending = False
        self._agent_pending = False

    def set_user_text(self, text: str, *, pending: bool = False) -> None:
        self._user_text = text
        self._user_pending = pending

    def set_agent_text(self, text: str, *, pending: bool = False) -> None:
        self._agent_text = text
        self._agent_pending = pending

    def clear(self) -> None:
        self._user_text = ""
        self._agent_text = ""
        self._user_pending = False
        self._agent_pending = False

    def render(self) -> RenderableType:
        lines: list[Text] = []

        if self._user_text:
            label = Text()
            label.append("  ▎ ", style=Colors.USER_LABEL)
            label.append("You", style=Colors.USER_LABEL)
            lines.append(label)

            body = Text()
            body.append("  ▎ ", style=Colors.TRANSCRIPT_BAR)
            body.append(
                self._user_text,
                style=Colors.STATUS_DIM if self._user_pending else Colors.STATUS_TEXT,
            )
            lines.append(body)

        if self._agent_text:
            if self._user_text:
                lines.append(Text(""))

            label = Text()
            label.append("  ▎ ", style=Colors.AGENT_LABEL)
            label.append("Rook", style=Colors.AGENT_LABEL)
            lines.append(label)

            body = Text()
            body.append("  ▎ ", style=Colors.TRANSCRIPT_BAR)
            body.append(
                self._agent_text,
                style=Colors.STATUS_DIM if self._agent_pending else Colors.STATUS_TEXT,
            )
            lines.append(body)

        if not lines:
            return Text("")

        return Group(*lines)
