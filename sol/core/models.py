"""Shared book data and text projection, independent of interfaces and importers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import unicodedata


@dataclass
class Node:
    """One item in the virtual filesystem; children make a directory."""

    name: str
    title: str
    start_page: int
    children: tuple["Node", ...] = field(default_factory=tuple)
    label: str = ""
    anchor: tuple[int, float] | None = None
    parent: "Node | None" = field(default=None, repr=False, compare=False)

    @property
    def is_directory(self) -> bool:
        return bool(self.children)


@dataclass(frozen=True)
class Passage:
    text: str
    pdf_page: int
    printed_page: int
    node: Node
    path: tuple[str, ...]
    end_pdf_page: int
    end_printed_page: int
    identifier: str
    heading: str = ""
    kind: str = "paragraph"
    random_eligible: bool = True
    transcription_status: str = ""
    facsimile_labels: tuple[str, ...] = ()

    @property
    def needs_source_review(self) -> bool:
        """Transcription quality is independent of quotation eligibility/type."""
        return self.transcription_status in {"needs_review", "needs_visual_review"}


@dataclass
class Book:
    root: Node
    passages: list[Passage]
    redirects: dict[str, str] = field(default_factory=dict)
    canonical_records: dict[str, dict] = field(default_factory=dict, repr=False, compare=False)
    corpus_directory: Path | None = field(default=None, repr=False, compare=False)
    corpus_manifest: dict = field(default_factory=dict, repr=False, compare=False)
    corpus_snapshot: object | None = field(default=None, repr=False, compare=False)

    def selection(self, path: tuple[str, ...]) -> list[Passage]:
        matches = [p for p in self.passages if p.path[:len(path)] == path]
        if not matches:
            raise ValueError("this location has no prose")
        return matches

    def find_passage(self, identifier: str) -> Passage:
        """Resolve an exact ID, retired ID, or unambiguous prefix."""
        identifier = identifier.strip().casefold()
        if not identifier:
            raise ValueError("a passage identifier is required")
        redirects = {key.casefold(): value.casefold() for key, value in self.redirects.items()}
        if identifier not in redirects:
            # The common case, an exact current ID, needs no index of the book.
            for passage in self.passages:
                if passage.identifier.casefold() == identifier:
                    return passage
        by_id = {passage.identifier.casefold(): passage for passage in self.passages}
        if identifier in by_id or identifier in redirects:
            target = identifier
        else:
            candidates = [key for key in (*by_id, *redirects) if key.startswith(identifier)]
            if len(candidates) == 1:
                target = candidates[0]
            elif len(candidates) > 1:
                raise ValueError("ambiguous identifier; use more of the passage ID")
            else:
                raise ValueError(f"no passage with identifier: {identifier}")
        seen: set[str] = set()
        while target in redirects:
            if target in seen:
                raise ValueError("invalid passage redirect cycle")
            seen.add(target)
            target = redirects[target]
        if target not in by_id:
            raise ValueError("this identifier does not refer to a readable Hegel passage")
        return by_id[target]

    def search(self, query: str, path: tuple[str, ...] = (),
               whole_word: bool = False, limit: int = 20) -> list[Passage]:
        """Literal Unicode search in a subtree, preserving book order."""
        if not query.strip():
            raise ValueError("search requires a nonempty query")
        if not 1 <= limit <= 1000:
            raise ValueError("search limit must be between 1 and 1000")
        pattern = re.escape(unicodedata.normalize("NFC", query.strip()).casefold())
        if whole_word:
            pattern = rf"(?<!\w){pattern}(?!\w)"
        expression = re.compile(pattern)
        matches = []
        for passage in self.selection(path):
            text = unicodedata.normalize("NFC", presentation_text(
                passage.text, passage.facsimile_labels)).casefold()
            if expression.search(text):
                matches.append(passage)
                if len(matches) == limit:
                    break
        return matches


def node_path(node: Node) -> tuple[str, ...]:
    parts = []
    while node.parent is not None:
        parts.append(node.name)
        node = node.parent
    return tuple(reversed(parts))


def presentation_text(text: str, facsimile_labels: tuple[str, ...] = ()) -> str:
    """Exclude generated facsimile captions from the terminal prose only."""
    for label in facsimile_labels:
        text = re.sub(r"(?m)^[ \t]*" + re.escape(label) + r"[ \t]*$", "", text)
    return text.strip()
