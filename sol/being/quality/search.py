"""Literal search matches projected onto unchanged canonical codepoints.

Book search uses a presentation-only NFC/casefold projection. Those operations
can compose, reorder, or expand Unicode characters; a normalized index is never
a source offset. This helper exposes only boundaries whose alignment is proved
by independently normalizing both sides. Unrepresentable partial matches are
reported explicitly, not expanded into a guessed selection.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class SearchProjection:
    """Exact half-open source spans, with an honest partial-projection fallback."""

    spans: tuple[tuple[int, int], ...] = ()
    degraded: bool = False
    reason: str | None = None
    # One entry per normalized match, including explicit unmappable visits.
    occurrences: tuple[tuple[int, int] | None, ...] = ()


# Verification of internal boundaries is quadratic in one normalization
# segment, never in the passage. Pathological combining sequences fall back
# explicitly rather than consuming an unbounded amount of reader work.
_MAX_VERIFIED_SEGMENT = 128


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def _presentation(text: str, labels: tuple[str, ...]) -> tuple[str, tuple[int, ...]]:
    """Mirror core.presentation_text while retaining every surviving index."""
    indices = list(range(len(text)))
    for label in labels:
        expression = re.compile(r"(?m)^[ \t]*" + re.escape(label) + r"[ \t]*$")
        kept: list[int] = []
        cursor = 0
        for match in expression.finditer(text):
            kept.extend(indices[cursor:match.start()])
            cursor = match.end()
        kept.extend(indices[cursor:])
        indices = kept
        text = expression.sub("", text)
    left = len(text) - len(text.lstrip())
    right = len(text.rstrip())
    return text[left:right], tuple(indices[left:right])


def _segments(text: str):
    """Split at verified NFC boundaries, including class-zero compositions.

    Combining marks remain with their starter. Testing the next class-zero
    character also handles Hangul Jamo and other compositions that a simplistic
    'split at every starter' algorithm would miss. Joining all segment
    projections is independently verified by the caller.
    """
    start = 0
    for index in range(1, len(text)):
        if unicodedata.combining(text[index]):
            continue
        current = text[start:index]
        following = text[index]
        if unicodedata.normalize("NFC", current + following) == (
                unicodedata.normalize("NFC", current) +
                unicodedata.normalize("NFC", following)):
            yield start, index
            start = index
    if text:
        yield start, len(text)


def search_projection(text: str, query: str, whole_word: bool = False,
                      facsimile_labels: tuple[str, ...] = ()) -> SearchProjection:
    """Match Book.search semantics and return precisely mappable source spans.

    Captions and surrounding whitespace are excluded from matching, not deleted
    from the canonical source. A match across an excluded caption cannot be
    represented by one contiguous source span and therefore degrades visibly.
    Unicode expansion fragments (for example one ``s`` inside ``ß``) similarly
    remain valid search results but have no exact source span.
    """
    if not isinstance(text, str) or not isinstance(query, str):
        raise TypeError("search text and query must be strings")
    if not isinstance(whole_word, bool):
        raise TypeError("whole_word must be a boolean")
    if not isinstance(facsimile_labels, tuple) or any(
            not isinstance(label, str) for label in facsimile_labels):
        raise TypeError("facsimile_labels must be a tuple of strings")
    if not query.strip():
        raise ValueError("search requires a nonempty query")

    presented, source_indices = _presentation(text, facsimile_labels)
    normalized = _fold(presented)
    pattern = re.escape(_fold(query.strip()))
    if whole_word:
        pattern = rf"(?<!\w){pattern}(?!\w)"
    matches = tuple(re.finditer(pattern, normalized))
    if not matches:
        return SearchProjection()

    # Most prose needs no boundary proof per character: if independent folds
    # reproduce the whole normalization with one codepoint each, indices align.
    direct = presented.isascii()
    if not direct and not any(map(unicodedata.combining, presented)):
        folded_characters = tuple(_fold(char) for char in presented)
        direct = (all(len(char) == 1 for char in folded_characters)
                  and "".join(folded_characters) == normalized)
    boundaries, oversized = (None, False) if direct else _verified_boundaries(presented, normalized)
    if not direct and boundaries is None:
        return SearchProjection(degraded=True, reason=(
            "Search found this passage, but Unicode normalization could not "
            "be aligned safely with its source characters."), occurrences=(None,) * len(matches))

    spans: list[tuple[int, int]] = []
    occurrences = []
    ambiguous = False
    for match in matches:
        start = match.start() if direct else boundaries.get(match.start())
        end = match.end() if direct else boundaries.get(match.end())
        if start is None or end is None or start == end:
            ambiguous = True
            occurrences.append(None)
            continue
        original_start = source_indices[start]
        original_end = source_indices[end - 1] + 1
        if original_end - original_start != end - start or (
                _fold(presented[start:end]) != match.group()):
            ambiguous = True
            occurrences.append(None)
            continue
        spans.append((original_start, original_end))
        occurrences.append((original_start, original_end))
    if ambiguous:
        reason = (
            "Some search matches have no exact contiguous source span; "
            "only verified matches are highlighted."
        )
        if oversized:
            reason = (
                "An unusually long Unicode combining sequence prevented "
                "safe alignment of some matches; only verified matches "
                "are highlighted."
            )
        return SearchProjection(tuple(spans), degraded=True, reason=reason,
                                occurrences=tuple(occurrences))
    return SearchProjection(tuple(spans), occurrences=tuple(occurrences))


def _verified_boundaries(presented, normalized):
    boundaries: dict[int, int] = {0: 0}
    projected_parts: list[str] = []
    projected_offset = 0
    oversized = False
    for start, end in _segments(presented):
        segment = presented[start:end]
        folded = _fold(segment)
        projected_parts.append(folded)
        boundaries[projected_offset] = start
        boundaries[projected_offset + len(folded)] = end
        if len(segment) <= _MAX_VERIFIED_SEGMENT:
            for local in range(1, len(segment)):
                prefix = _fold(segment[:local])
                if prefix + _fold(segment[local:]) == folded:
                    boundaries[projected_offset + len(prefix)] = start + local
        else:
            oversized = True
        projected_offset += len(folded)
    if "".join(projected_parts) != normalized:
        return None, oversized
    return boundaries, oversized
