"""Tests for the OpenClaw voice prompt."""

from rook.cli.app import RookApp
from rook.core.config import Config


def test_openclaw_voice_prompt_includes_concrete_stack_details():
    """Questions about Rook should be grounded in the real configured stack."""
    app = object.__new__(RookApp)
    app.config = Config()

    prompt = app._build_openclaw_voice_prompt("Qual o modelo que usas para falar?")

    assert "gemini-3.1-flash-live-preview" in prompt
    assert "Gemini 3.1 Flash Live" in prompt
    assert "Kore" in prompt
    assert "OpenClaw" in prompt
    assert "Do not give vague answers" in prompt


def test_openclaw_voice_prompt_prefers_direct_actions_and_hides_internal_limits():
    """Demo actions should execute directly without exposing internal vault policy."""
    app = object.__new__(RookApp)
    app.config = Config()

    prompt = app._build_openclaw_voice_prompt("Abre o browser e procura uma imagem de um gato.")

    assert "act immediately instead of asking for confirmation again" in prompt
    assert "treat that as the confirmation and execute the task" in prompt
    assert "Do not mention hidden scope limits" in prompt
    assert "do not have that information right now" in prompt
