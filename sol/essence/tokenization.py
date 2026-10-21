"""Shared deterministic word tokens; no corpus, interface or runtime imports.

Offsets address the original Python string, before normalization. Keep this
algorithm stable: word and sentence study artifacts depend on it.
"""
from __future__ import annotations

import unicodedata

TOKENIZATION = "unicode-letter-mark-internal-apostrophe-v1"
NORMALIZATION = "NFC+casefold+curly-apostrophe-to-straight"


def word_tokens(text: str):
    """Yield normalized tokens and untouched, half-open plain-text offsets."""
    position = 0
    while position < len(text):
        if not unicodedata.category(text[position]).startswith("L"):
            position += 1
            continue
        start = position
        position += 1
        while position < len(text):
            category = unicodedata.category(text[position])
            if category.startswith(("L", "M")):
                position += 1
            elif (text[position] in "'’" and position + 1 < len(text)
                  and unicodedata.category(text[position + 1]).startswith("L")):
                position += 2
            else:
                break
        yield unicodedata.normalize("NFC", text[start:position]).casefold().replace("’", "'"), start, position

