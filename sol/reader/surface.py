"""Read-only surface projections over verified CORE records and source offsets.

The projection is detached from personal state. Installed and research frontends
share this validation; only ReaderActions may accept a position into a workspace.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
from hashlib import sha256
import json

from sol.corpus.contract import CorpusSnapshot, verify_snapshot_current
from sol.core.models import Book, Passage
from sol.core.protocol import capture_reference, capture_references, check_reference, decode_reference, encode_reference
from sol.core.references import resolve_record_reference, resolve_reference
from sol.reader.actions import ReaderActions, TextSelection


@dataclass(frozen=True)
class Sample:
    book: Book
    passages: tuple[Passage, ...]
    actions: ReaderActions


def note_paragraph_ids(book: Book) -> dict[str, list[str]]:
    """Map each note to its body records, in reading order.

    A converted footnote is a ``note`` record holding only its heading
    ("Note 12"); the text lives in ``note_paragraph`` children.
    """
    bodies = {}
    for record in book.canonical_records.values():
        if record.get("type") == "note_paragraph":
            bodies.setdefault(record.get("parent_id"), []).append(record)
    return {parent: [row["id"] for row in sorted(rows, key=lambda row: row["order"])]
            for parent, rows in bodies.items()}


FOOTNOTE_DEPTH = 8
FOOTNOTE_PARAGRAPHS = 64
FOOTNOTE_LINKS = 128


def footnote_links(records) -> list[str]:
    """Canonical links, including those on body paragraphs, in source order."""
    return list(dict.fromkeys(identifier for record in records for identifier in record.get("note_ids", [])))


def footnote_scope(book: Book, passage_id: str, trail: list[str]) -> tuple[str, ...]:
    """Fence a disposable note path to the shown passage and bound its work.

    This chooses records for a checked CaptureExport, never accepts a reading
    position or invents identities. The caller still captures and finishes the
    export, so a detached graph or a changed corpus cannot supply panel text.
    """
    if (not isinstance(trail, list) or not 1 <= len(trail) <= FOOTNOTE_DEPTH
            or any(not isinstance(identifier, str) for identifier in trail)):
        raise ValueError(f"a footnote path needs 1–{FOOTNOTE_DEPTH} canonical note IDs")
    bodies = note_paragraph_ids(book)
    current = book.canonical_records.get(passage_id)
    if current is None:
        raise ValueError("the footnote's passage is unavailable")
    parts, identifiers, seen = [current], [passage_id], set()
    for identifier in trail:
        if identifier in seen:
            raise ValueError("footnote cycle: that note is already open in this path")
        if identifier not in footnote_links(parts):
            raise ValueError("that footnote is not linked from the shown passage or note")
        note = book.canonical_records.get(identifier)
        if note is None or note.get("type") != "note":
            raise ValueError("unresolved canonical footnote; source text was not substituted")
        body_ids = bodies.get(identifier, [])
        if len(body_ids) > FOOTNOTE_PARAGRAPHS:
            raise ValueError(f"footnote view is limited to {FOOTNOTE_PARAGRAPHS} body paragraphs; source is unchanged")
        parts = [note, *(book.canonical_records[body] for body in body_ids)]
        identifiers.extend(part["id"] for part in parts)
        seen.add(identifier)
    return tuple(dict.fromkeys(identifiers))


def sample_from_book(book: Book, start: str | None = None, count: int = 24) -> Sample:
    """Choose a bounded sequential view, never a new canonical combined record."""
    if type(count) is not int or not 1 <= count <= 64:
        raise ValueError("sample count must be between 1 and 64")
    if not book.passages:
        raise ValueError("the verified book has no readable passages")
    first = book.find_passage(start) if start is not None else book.passages[0]
    index = next(i for i, passage in enumerate(book.passages) if passage.identifier == first.identifier)
    passages = tuple(book.passages[index:index + count])
    actions = ReaderActions(book)
    # Match the normal temporary reader's whole-work scope before positioning
    # the sample. Opening from an empty session would silently choose one leaf.
    actions.read(path=(), first=True)
    actions.open(first.identifier)
    return Sample(book, passages, actions)


class CaptureExport:
    """One short-lived export over an owned graph, with no shared trust cache.

    A declared sample captures its references together through CORE's bounded
    batch API. Imported packets still use the unchanged full check_reference.
    Copies prevent callers from changing what was checked while it is rendered.
    """

    def __init__(self, book: Book, *, identifiers=None):
        if not isinstance(book.corpus_snapshot, CorpusSnapshot):
            raise ValueError("surface export requires a verified corpus snapshot with explicit corpus identity")
        self.book = book
        self.snapshot = deepcopy(book.corpus_snapshot)
        self.records = {row["id"]: row for row in self.snapshot.records}
        self._cache = {}
        self._reader_ids = set()
        self.manifest = deepcopy(self.snapshot.manifest)
        self._closed = False
        self._packets = None if identifiers is None else {
            packet["reference"]["requested_id"]: packet
            for packet in capture_references(self.snapshot, tuple(dict.fromkeys(identifiers)))
        }

    @classmethod
    def for_sample(cls, sample, requested_ids=None):
        requested_ids = requested_ids or {}
        identifiers, bodies = [], note_paragraph_ids(sample.book)
        for passage in sample.passages:
            identifiers.append(requested_ids.get(passage.identifier, passage.identifier))
            for note in sample.book.canonical_records[passage.identifier].get("note_ids", []):
                identifiers += [note, *bodies.get(note, [])]
        return cls(sample.book, identifiers=identifiers)

    def capture(self, identifier):
        if self._closed:
            raise ValueError("export capture is closed; start a new checked export")
        if not isinstance(identifier, str):
            raise ValueError("a canonical record identifier is required")
        requested = resolve_record_reference(self.records, identifier)
        key = requested.requested_id
        if key not in self._cache:
            # Serialization validates the existing protocol's shape, not a new
            # export format. CORE remains the producer of every reference.
            if self._packets is None:
                packet = capture_reference(self.snapshot, identifier)
            else:
                if key not in self._packets:
                    raise ValueError("record was not included in this checked export batch")
                packet = self._packets[key]
            payload = decode_reference(encode_reference(packet))
            reference = resolve_record_reference(self.records, payload["reference"]["requested_id"])
            row = reference.record
            edition = json.dumps(self.snapshot.manifest["edition"], ensure_ascii=False,
                                 sort_keys=True, separators=(",", ":"), allow_nan=False)
            expected_corpus = {"id": self.snapshot.corpus_id,
                               "edition_sha256": sha256(edition.encode("utf-8")).hexdigest(),
                               "source": {name: self.manifest["source"][name] for name in ("sha256", "pdf_pages")}}
            expected_binding = {"requested_id": reference.requested_id, "target_id": reference.target_id,
                                "chain": list(reference.chain), "content_sha256": row["content_sha256"],
                                "type": row["type"],
                                "sources": [{name: value for name, value in source.items()
                                             if name in {"pdf_page", "printed_page", "bbox"}} for source in row["sources"]],
                                "attribution": {name: row["attribution"][name] for name in ("author", "status", "role")}}
            if (payload["corpus"] != expected_corpus
                    or payload["generation"] != {"manifest_sha256": self.snapshot.manifest_sha256,
                                                  "index_sha256": self.snapshot.index_sha256}
                    or payload["reference"] != expected_binding
                    or row["content_sha256"] != sha256(row["markdown"].encode("utf-8")).hexdigest()):
                raise ValueError("captured CORE reference disagrees with its owned source snapshot")
            if requested != reference:
                raise ValueError("captured CORE reference changed the requested object")
            self._cache[key] = payload, reference
        payload, reference = self._cache[key]
        if reference.record != self.book.canonical_records.get(reference.target_id):
            raise ValueError("loaded record disagrees with its verified CORE source")
        loaded = resolve_reference(self.book, reference.requested_id)
        if (loaded.target_id, loaded.chain) != (reference.target_id, reference.chain):
            raise ValueError("loaded reader retirement chain disagrees with CORE")
        if reference.record["type"] in {"paragraph", "list_item", "quotation", "formula"}:
            _agree_with_core(self.book, reference)
            self._reader_ids.add(reference.requested_id)
        return deepcopy(payload), deepcopy(reference)

    def finish(self):
        """Refuse final-render edits before any output file is created."""
        if self._closed:
            raise ValueError("export capture is closed; start a new checked export")
        try:
            if (self.book.corpus_snapshot != self.snapshot
                    or self.book.corpus_manifest != self.snapshot.manifest
                    or self.book.canonical_records != self.records):
                raise ValueError("the loaded corpus graph changed during export; reopen and retry")
            for identifier in self._reader_ids:
                _agree_with_core(self.book, resolve_record_reference(self.records, identifier))
            verify_snapshot_current(self.snapshot)
        finally:
            self._cache.clear()
            self._closed = True


def record_payload(sample: Sample, passage: Passage, *, capture: CaptureExport | None = None,
                   requested_id=None) -> dict:
    """Capture the existing reference protocol, not a renderer-specific identity."""
    if sample.actions.workspace_reader is not None:
        raise ValueError("reader experiments do not accept a personal workspace")
    owned = capture is None
    capture = CaptureExport(sample.book) if owned else capture
    if capture.book is not sample.book:
        raise ValueError("export capture belongs to another book")
    reference, checked = capture.capture(requested_id or passage.identifier)
    if checked.target_id != passage.identifier:
        raise ValueError("requested reference does not identify the displayed passage")
    if sample.book.find_passage(passage.identifier) is not passage:
        raise ValueError("sample must use the book's existing passage objects")
    payload = {"id": passage.identifier, "plain_text": checked.record["plain_text"],
               "plain_text_sha256": sha256(checked.record["plain_text"].encode("utf-8")).hexdigest(),
               "reference": reference}
    if owned:
        capture.finish()
    return payload


def _agree_with_core(book, reference):
    """A detached caller-owned graph must not override the verified snapshot."""
    record = book.canonical_records.get(reference.target_id)
    loaded = resolve_reference(book, reference.requested_id)
    if (loaded.target_id, loaded.chain) != (reference.target_id, reference.chain):
        raise ValueError("loaded reader retirement chain disagrees with CORE")
    if record != reference.record or book.find_passage(reference.target_id).text != reference.record["plain_text"]:
        raise ValueError("loaded reader text/record disagrees with the verified CORE source")
    # Reuse the reader's existing projection/provenance guard rather than
    # accepting independently changed page/path/kind data in a display sample.
    if record["plain_text"]:
        reader = ReaderActions(book)
        reader.open(reference.requested_id)
        reader.select_span(0, len(record["plain_text"]))
    return record


def selection_packet(book: Book, identifier: str, start: int, end: int) -> dict:
    """Research bridge wrapper over CORE and TextSelection, not a new protocol."""
    if book.corpus_snapshot is None:
        raise ValueError("a verified corpus snapshot is required")
    reference = capture_reference(book.corpus_snapshot, identifier)
    _agree_with_core(book, check_reference(book.corpus_snapshot, reference))
    actions = ReaderActions(book)
    actions.open(identifier)
    selected = actions.select_span(start, end)
    return {"reference": reference,
            "selection": asdict(selected), "cursor_offset": actions.cursor_offset}


def validate_packet(book: Book, packet: dict) -> TextSelection | None:
    """Refuse stale/mismatched exported positions; never write a workspace.

    The file carries no corpus path, command, actor, or write authority. The caller
    supplies its own locally verified corpus. Exact generation checks intentionally
    make these disposable research exports stricter than future ordinary reading.
    """
    if not isinstance(packet, dict) or set(packet) != {"reference", "selection", "cursor_offset"}:
        raise ValueError("a research packet requires reference, selection, and cursor_offset only")
    if book.corpus_snapshot is None:
        raise ValueError("a verified corpus snapshot is required")
    reference = check_reference(book.corpus_snapshot, packet["reference"])
    _agree_with_core(book, reference)
    actions = ReaderActions(book)
    actions.open(reference.requested_id)
    actions.set_cursor(packet["cursor_offset"])
    selected = packet["selection"]
    if selected is None:
        return None
    fields = {"requested_id", "target_id", "start", "end", "text", "content_sha256", "plain_text_sha256"}
    if not isinstance(selected, dict) or set(selected) != fields:
        raise ValueError("selection must use the existing TextSelection fields")
    actual = actions.select_span(selected["start"], selected["end"])
    if asdict(actual) != selected:
        raise ValueError("selection identity, exact text, or source digest disagrees with the local corpus")
    if packet["cursor_offset"] not in {actual.start, actual.end}:
        raise ValueError("selected-span cursor must be one of its source boundaries")
    return actual
