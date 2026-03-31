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
    if not _looks_like_safe_followup(remainder):
        return "", normalized
    return lead, remainder


def _looks_like_safe_followup(text: str) -> bool:
    """Return True when remainder looks like a fresh sentence, not a broken continuation."""
    if not text:
        return False

    first = text[0]
    if first.isupper() or first.isdigit():
        return True

    return first in {'"', "'", "“", "(", "["}


def trim_spoken_prefix(full_text: str, spoken_prefix: str) -> str:
    """Remove the already-spoken prefix from the final text reply."""
    normalized_full = _normalize_whitespace(full_text)
    normalized_prefix = _normalize_whitespace(spoken_prefix)

    if not normalized_prefix:
        return normalized_full

    shared_length = 0
    max_length = min(len(normalized_full), len(normalized_prefix))
    while shared_length < max_length and normalized_full[shared_length] == normalized_prefix[shared_length]:
        shared_length += 1

    if shared_length == 0:
        return normalized_full

    mismatch_inside_word = (
        shared_length < len(normalized_full)
        and normalized_full[shared_length - 1].isalnum()
        and normalized_full[shared_length].isalnum()
    )
    if mismatch_inside_word:
        while shared_length > 0 and normalized_full[shared_length - 1].isalnum():
            shared_length -= 1

    while shared_length > 0:
        prev_char = normalized_full[shared_length - 1]
        next_char = normalized_full[shared_length] if shared_length < len(normalized_full) else ""
        if not (prev_char.isalnum() and next_char.isalnum()):
            break
        shared_length -= 1

    if shared_length <= 0:
        return normalized_full

    return normalized_full[shared_length:].strip()
