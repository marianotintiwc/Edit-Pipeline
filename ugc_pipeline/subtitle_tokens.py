"""Subtitle text token normalizations (no heavy transcription deps)."""

import re


def normalize_subtitle_tokens(text: str) -> str:
    """Normalize common spoken phrases for on-screen subtitles (e.g. Chile Spanish).
    Output is always exactly 'altiro' (lowercase) for the 'al tiro' phrase."""
    if not text:
        return text
    # Whisper often transcribes "al tiro" (two words); style guide: single token "altiro"
    text = re.sub(r"\bal\s+tiro\b", "altiro", text, flags=re.IGNORECASE)
    # Karaoke segments: "[al] tiro" or "al [tiro]" → "[altiro]"
    text = re.sub(r"\[al\]\s+tiro\b", "[altiro]", text, flags=re.IGNORECASE)
    text = re.sub(r"\bal\s+\[tiro\]", "[altiro]", text, flags=re.IGNORECASE)
    return text
