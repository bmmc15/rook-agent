"""Tests for streamed-text speech chunking helpers."""

from rook.utils.streaming_text import (
    find_tts_segment_boundary,
    split_tts_lead_segment,
    trim_spoken_prefix,
)


def test_find_tts_segment_boundary_on_sentence():
    text = "Rook found the issue in the websocket client. I can patch it next."

    boundary = find_tts_segment_boundary(text)

    assert boundary is not None
    assert text[:boundary].strip() == "Rook found the issue in the websocket client."


def test_find_tts_segment_boundary_uses_clause_for_long_reply():
    text = (
        "I checked the hot path through transcription and playback, and the largest delay is "
        "waiting for the full OpenClaw reply before speech begins while the rest of the answer "
        "keeps streaming behind it"
    )

    boundary = find_tts_segment_boundary(text)

    assert boundary is not None
    assert text[:boundary].strip().endswith(",")


def test_split_tts_lead_segment_returns_remainder():
    lead, remainder = split_tts_lead_segment(
        "The first sentence is ready to speak. The second sentence should wait."
    )

    assert lead == "The first sentence is ready to speak."
    assert remainder == "The second sentence should wait."


def test_trim_spoken_prefix_removes_lead_segment():
    remaining = trim_spoken_prefix(
        "The first sentence is ready to speak. The second sentence should wait.",
        "The first sentence is ready to speak.",
    )

    assert remaining == "The second sentence should wait."
