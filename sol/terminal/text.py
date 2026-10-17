"""Display policies for terminal text; canonical strings are never modified."""
from __future__ import annotations

import sys
import unicodedata


_BIDI = {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}


def safe_output(value: object) -> str:
    """Escape source controls while retaining prose newlines and tabs."""
    result = []
    for character in str(value):
        code = ord(character)
        if unicodedata.bidirectional(character) in _BIDI or unicodedata.category(character) == "Cs":
            result.append(f"\\u{code:04x}")
        elif character not in "\n\t" and (code < 32 or 127 <= code <= 159):
            result.append(f"\\x{code:02x}")
        else:
            result.append(character)
    return "".join(result)


def safe_label(value: object) -> str:
    """Escape controls in a single-line label, including newlines and tabs."""
    return "".join(f"\\u{ord(c):04x}" if unicodedata.category(c) in {"Cc", "Cs"}
                   or unicodedata.bidirectional(c) in _BIDI else c for c in str(value))


def display_text(value: object, stream=None) -> str:
    """Protect a terminal; retain exact text for pipes and explicit exports."""
    stream = sys.stdout if stream is None else stream
    return safe_output(value) if getattr(stream, "isatty", lambda: False)() else str(value)
