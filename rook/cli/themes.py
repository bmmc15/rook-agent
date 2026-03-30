"""Theme and color definitions for the UI."""
from rich.style import Style
from rich.theme import Theme


# Define color palette
class Colors:
    """Color constants matching the HALIST aesthetic."""

    BORDER = "magenta"
    WAVEFORM = "green"
    ORB = "red"
    ORB_DIM = "rgb(139,69,19)"  # Dark brown/red for orb shading
    STATUS_TEXT = "white"
    STATUS_DIM = "bright_black"
    ERROR = "bright_red"
    SUCCESS = "bright_green"
    INFO = "bright_cyan"
    WARNING = "bright_yellow"


# Create Rich theme
rook_theme = Theme(
    {
        "border": Style(color=Colors.BORDER, bold=True),
        "orb": Style(color=Colors.ORB, bold=True),
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


# Block characters for waveform visualization (in order of height)
WAVEFORM_BLOCKS = " ▁▂▃▄▅▆▇█"


# Orb animation frames (6 frames for smooth animation)
ORB_FRAMES = [
    [
        "         ░▒▓██▓▒░         ",
        "      ░▒▓████████▓▒░      ",
        "     ░▒▓██████████▓▒░     ",
        "      ░▒▓████████▓▒░      ",
        "         ░▒▓██▓▒░         ",
    ],
    [
        "        ░▒▓████▓▒░        ",
        "     ░▒▓██████████▓▒░     ",
        "    ░▒▓████████████▓▒░    ",
        "     ░▒▓██████████▓▒░     ",
        "        ░▒▓████▓▒░        ",
    ],
    [
        "       ░▒▓██████▓▒░       ",
        "    ░▒▓████████████▓▒░    ",
        "   ░▒▓██████████████▓▒░   ",
        "    ░▒▓████████████▓▒░    ",
        "       ░▒▓██████▓▒░       ",
    ],
    [
        "      ░▒▓████████▓▒░      ",
        "   ░▒▓██████████████▓▒░   ",
        "  ░▒▓████████████████▓▒░  ",
        "   ░▒▓██████████████▓▒░   ",
        "      ░▒▓████████▓▒░      ",
    ],
    [
        "       ░▒▓██████▓▒░       ",
        "    ░▒▓████████████▓▒░    ",
        "   ░▒▓██████████████▓▒░   ",
        "    ░▒▓████████████▓▒░    ",
        "       ░▒▓██████▓▒░       ",
    ],
    [
        "        ░▒▓████▓▒░        ",
        "     ░▒▓██████████▓▒░     ",
        "    ░▒▓████████████▓▒░    ",
        "     ░▒▓██████████▓▒░     ",
        "        ░▒▓████▓▒░        ",
    ],
]
