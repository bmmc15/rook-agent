"""Main panel widget that composes all UI elements."""
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from rook.cli.themes import Colors
from rook.cli.widgets.orb import OrbWidget
from rook.cli.widgets.status import StatusWidget
from rook.cli.widgets.transcript import TranscriptWidget
from rook.cli.widgets.waveform import WaveformWidget


class MainPanel:
    """Main UI panel that composes orb, waveform, transcript, and status."""

    def __init__(self):
        self.orb = OrbWidget()
        self.waveform = WaveformWidget(bar_count=28)
        self.transcript = TranscriptWidget()
        self.status = StatusWidget()

    def render(self) -> RenderableType:
        content = Group(
            Text(""),
            self.orb.render(),
            Text(""),
            self.waveform.render(),
            Text(""),
            self.transcript.render(),
            Text(""),
            Rule(style=Colors.SEPARATOR),
            self.status.render(),
        )

        return Panel(
            content,
            title="[bold]ROOK[/bold]",
            border_style=Colors.BORDER,
            padding=(1, 2),
        )
