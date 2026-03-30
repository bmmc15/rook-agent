"""Main panel widget that composes all UI elements."""
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from rook.cli.themes import Colors
from rook.cli.widgets.orb import OrbWidget
from rook.cli.widgets.status import StatusWidget
from rook.cli.widgets.transcript import TranscriptWidget
from rook.cli.widgets.waveform import WaveformWidget


class MainPanel:
    """Main UI panel that composes orb, waveform, and status."""

    def __init__(self):
        """Initialize main panel."""
        self.orb = OrbWidget()
        self.waveform = WaveformWidget(bar_count=20)
        self.transcript = TranscriptWidget()
        self.status = StatusWidget()

    def render(self) -> RenderableType:
        """Render the complete panel.

        Returns:
            Rich Panel containing all widgets
        """
        # Create spacing
        spacer = Text("")

        # Compose all widgets vertically
        content = Group(
            spacer,
            self.orb.render(),
            spacer,
            spacer,
            self.waveform.render(),
            spacer,
            self.transcript.render(),
            spacer,
            self.status.render(),
        )

        # Wrap in bordered panel
        return Panel(
            content,
            title="[bold]ROOK[/bold]",
            border_style=Colors.BORDER,
            padding=(1, 2),
        )
