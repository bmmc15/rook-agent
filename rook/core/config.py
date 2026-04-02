"""Configuration management using Pydantic Settings."""
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Gemini API Configuration
    gemini_api_key: str = Field(
        default="",
        description="Gemini API key for voice services",
    )
    gemini_live_model: str = Field(
        default="gemini-3.1-flash-live-preview",
        description="Gemini Live model for audio conversations",
    )
    gemini_session_prompt_path: Path = Field(
        default=Path("./prompts/gemini_session.md"),
        description="Markdown file with persistent Gemini session instructions",
    )
    gemini_voice_name: str = Field(
        default="Kore",
        description="Prebuilt Gemini voice name used for assistant speech",
    )

    # OpenClaw Configuration
    openclaw_ws_url: str = Field(
        default="",
        description="WebSocket URL for OpenClaw connection",
    )
    openclaw_api_key: str = Field(
        default="",
        description="Bearer token for OpenClaw authentication",
    )
    openclaw_agent_name: str = Field(
        default="Rook",
        description="Name of the OpenClaw agent",
    )
    openclaw_reply_timeout_seconds: int = Field(
        default=75,
        gt=0,
        description="Maximum time to wait for a final OpenClaw reply before aborting the turn",
    )
    openclaw_primary_demo_note_path: str = Field(
        default="demo-vault/Rook Agent docs.md",
        description="Primary Obsidian note that OpenClaw is allowed to rely on during the demo",
    )
    openclaw_allowed_demo_vault_path: str = Field(
        default="demo-vault",
        description="Only vault subtree that OpenClaw may consult for supporting demo context",
    )

    # Audio Configuration
    audio_sample_rate: int = Field(
        default=16000,
        description="Audio sample rate in Hz",
    )
    audio_channels: int = Field(
        default=1,
        description="Number of audio channels (1=mono, 2=stereo)",
    )
    audio_chunk_size: int = Field(
        default=1024,
        description="Audio buffer chunk size",
    )
    audio_device_index: Optional[int] = Field(
        default=None,
        description="Audio device index (None=default device)",
    )

    # Database Configuration
    database_path: Path = Field(
        default=Path("./data/rook.db"),
        description="Path to SQLite database file",
    )

    # UI Configuration
    ui_refresh_rate: int = Field(
        default=30,
        description="UI refresh rate in FPS",
    )
    ui_border_color: str = Field(
        default="magenta",
        description="Border color for main panel",
    )
    ui_waveform_color: str = Field(
        default="green",
        description="Waveform visualization color",
    )
    ui_orb_color: str = Field(
        default="red",
        description="Orb animation color",
    )

    # Voice Configuration
    voice_activation_key: str = Field(
        default="space",
        description="Key to activate voice input",
    )
    barge_in_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Audio level threshold for barge-in detection",
    )
    voice_timeout_seconds: int = Field(
        default=5,
        gt=0,
        description="Timeout for voice input in seconds",
    )
    tts_sample_rate: int = Field(
        default=24000,
        gt=0,
        description="Sample rate for Gemini audio output in Hz",
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    log_file: Path = Field(
        default=Path("./data/rook.log"),
        description="Path to log file",
    )

    @property
    def has_openclaw_config(self) -> bool:
        """Check if OpenClaw is configured."""
        return bool(self.openclaw_ws_url and self.openclaw_api_key)

    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
        _config.ensure_directories()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment."""
    global _config
    _config = Config()
    _config.ensure_directories()
    return _config
