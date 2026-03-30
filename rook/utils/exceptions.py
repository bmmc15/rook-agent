"""Custom exceptions for the application."""


class RookError(Exception):
    """Base exception for all Rook errors."""

    pass


class ConfigurationError(RookError):
    """Raised when configuration is invalid or missing."""

    pass


class AudioError(RookError):
    """Raised when audio operations fail."""

    pass


class VoiceProviderError(RookError):
    """Raised when voice provider operations fail."""

    pass


class OpenClawError(RookError):
    """Raised when OpenClaw operations fail."""

    pass


class ConnectionError(OpenClawError):
    """Raised when connection to OpenClaw fails."""

    pass


class TaskError(RookError):
    """Raised when task operations fail."""

    pass


class StorageError(RookError):
    """Raised when storage operations fail."""

    pass


class CommandError(RookError):
    """Raised when command execution fails."""

    pass
