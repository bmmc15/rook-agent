"""Tests for OpenClaw streamed text merging."""

from pathlib import Path

from rook.adapters.openclaw.client import OpenClawClient
from rook.core.config import Config


def _build_client(tmp_path) -> OpenClawClient:
    config = Config(
        log_file=Path(tmp_path) / "rook.log",
        database_path=Path(tmp_path) / "rook.db",
    )
    return OpenClawClient(config)


def test_merge_text_keeps_word_continuations_together(tmp_path):
    """Streaming continuations should not add spaces inside words."""
    client = _build_client(tmp_path)

    merged = client._merge_text("A casa que mais gostaste foi Avenidas Nov", "as.")

    assert merged == "A casa que mais gostaste foi Avenidas Novas."


def test_merge_text_uses_overlap_without_duplication(tmp_path):
    """Overlapping chunks should collapse into a single readable sentence."""
    client = _build_client(tmp_path)

    merged = client._merge_text("A casa de Avenidas Nov", "Novas está em primeiro lugar.")

    assert merged == "A casa de Avenidas Novas está em primeiro lugar."
