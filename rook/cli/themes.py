"""Theme and color definitions for the UI."""
from rich.style import Style
from rich.theme import Theme


class Colors:
    """Color constants — original red / green / magenta HALIST-style palette."""

    BORDER = "magenta"
    WAVEFORM = "green"
    ORB = "red"
    ORB_MID = "red"
    ORB_DIM = "rgb(139,69,19)"
    ORB_ACTIVE = "bright_red"

    USER_LABEL = "bold green"
    AGENT_LABEL = "bold red"
    TRANSCRIPT_BAR = "bright_black"

    STATUS_TEXT = "white"
    STATUS_DIM = "bright_black"
    STATUS_ACCENT = "white"

    SEPARATOR = "bright_black"

    ERROR = "bright_red"
    SUCCESS = "bright_green"
    INFO = "bright_cyan"
    WARNING = "bright_yellow"


rook_theme = Theme(
    {
        "border": Style(color=Colors.BORDER, bold=True),
        "orb": Style(color=Colors.ORB, bold=True),
        "orb_mid": Style(color=Colors.ORB_MID),
        "orb_dim": Style(color=Colors.ORB_DIM),
        "waveform": Style(color=Colors.WAVEFORM, bold=True),
        "status": Style(color=Colors.STATUS_TEXT),
        "status_dim": Style(color=Colors.STATUS_DIM, italic=True),
        "error": Style(color=Colors.ERROR, bold=True),
        "success": Style(color=Colors.SUCCESS, bold=True),
        "info": Style(color=Colors.INFO),
        "warning": Style(color=Colors.WARNING),
    }
)


WAVEFORM_BLOCKS = " ▁▂▃▄▅▆▇█"


ORB_FRAMES = [
    [
        "          ▓██▓          ",
        "       ▒▓██████▓▒       ",
        "      ▒▓████████▓▒      ",
        "       ▒▓██████▓▒       ",
        "          ▓██▓          ",
    ],
    [
        "         ▓████▓         ",
        "      ▒▓████████▓▒      ",
        "     ▒▓██████████▓▒     ",
        "      ▒▓████████▓▒      ",
        "         ▓████▓         ",
    ],
    [
        "        ▓██████▓        ",
        "     ▒▓██████████▓▒     ",
        "    ▒▓████████████▓▒    ",
        "     ▒▓██████████▓▒     ",
        "        ▓██████▓        ",
    ],
    [
        "       ▓████████▓       ",
        "    ▒▓████████████▓▒    ",
        "   ▒▓██████████████▓▒   ",
        "    ▒▓████████████▓▒    ",
        "       ▓████████▓       ",
    ],
    [
        "        ▓██████▓        ",
        "     ▒▓██████████▓▒     ",
        "    ▒▓████████████▓▒    ",
        "     ▒▓██████████▓▒     ",
        "        ▓██████▓        ",
    ],
    [
        "         ▓████▓         ",
        "      ▒▓████████▓▒      ",
        "     ▒▓██████████▓▒     ",
        "      ▒▓████████▓▒      ",
        "         ▓████▓         ",
    ],
]
