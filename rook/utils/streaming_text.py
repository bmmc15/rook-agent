"""Helpers for turning streamed model text into speakable chunks."""
from __future__ import annotations

import re


def _normalize_whitespace(text: str) -> str:
    """Collapse whitespace while preserving the text content."""
    return " ".join(text.split()).strip()


def _is_speakable_segment(text: str, *, min_chars: int = 24, min_words: int = 4) -> bool:
    """Return True when a chunk is long enough to sound natural on TTS."""
    normalized = _normalize_whitespace(text)
    if len(normalized) < min_chars:
        return False
    return len(normalized.split()) >= min_words


def find_tts_segment_boundary(text: str) -> int | None:
    """Find a safe boundary for starting speech before the full reply is done."""
    normalized = _normalize_whitespace(text)
    if not normalized:
        return None

    for match in re.finditer(r"[.!?](?=(?:\s|$))", normalized):
        candidate = normalized[: match.end()]
        if _is_speakable_segment(candidate):
            return match.end()

    # If the reply is getting long, fall back to a clause break instead of
    # making the user wait for a full sentence.
    if len(normalized) < 120:
        return None

    candidates: list[int] = []
    for match in re.finditer(r"[,;:](?=\s)", normalized):
        candidate = normalized[: match.end()]
        if _is_speakable_segment(candidate, min_chars=60, min_words=8):
            candidates.append(match.end())

    if candidates:
        return candidates[-1]

    return None


def split_tts_lead_segment(text: str) -> tuple[str, str]:
    """Split the first speakable segment from the remainder of the reply."""
    normalized = _normalize_whitespace(text)
    boundary = find_tts_segment_boundary(normalized)
    if boundary is None:
        return "", normalized

    lead = normalized[:boundary].strip()
    remainder = normalized[boundary:].strip()
    return lead, remainder


def trim_spoken_prefix(full_text: str, spoken_prefix: str) -> str:
    """Remove the already-spoken prefix from the final text reply."""
    normalized_full = _normalize_whitespace(full_text)
    normalized_prefix = _normalize_whitespace(spoken_prefix)

    if not normalized_prefix:
        return normalized_full

    if normalized_full.startswith(normalized_prefix):
        return normalized_full[len(normalized_prefix) :].strip()

    if normalized_prefix in normalized_full:
        return normalized_full.split(normalized_prefix, 1)[1].strip()

    return normalized_full
