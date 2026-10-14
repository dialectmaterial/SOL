"""Reader state and actions, without a command loop or terminal dependency.

This is BEING's application boundary, not another corpus or persistence layer.
The caller supplies a loaded book and, optionally, its existing WorkspaceReader.
Actions return domain objects; prompts, parsing, rendering, and panes belong to
the interface. No database, actor profile, or PDF is opened implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
import re

from sol.core.models import Book, Passage
from sol.core.paths import display_path, resolve_path


@dataclass
class ReadingSession:
    """A cursor within an explicit selection; random reads also set the cursor."""
    book: Book
    path: tuple[str, ...] = ()
    cursor: int | None = None

    def current(self) -> Passage:
        if self.cursor is None:
            raise ValueError("no current paragraph; use first, read, or open")
        return self.book.selection(self.path)[self.cursor]

    def open(self, identifier: str) -> Passage:
        passage = self.book.find_passage(identifier)
        if self.cursor is None or passage.path[:len(self.path)] != self.path:
            self.path = passage.path
        matches = self.book.selection(self.path)
        self.cursor = next(index for index, item in enumerate(matches)
                           if item.identifier == passage.identifier)
        return passage

    def read(self, path: tuple[str, ...], first: bool = False) -> Passage:
        matches = self.book.selection(path)
        if first:
            self.path, self.cursor = path, 0
            return matches[0]
        candidates = [index for index, p in enumerate(matches)
                      if p.kind != "formula" and p.random_eligible
                      and len(re.findall(r"[A-Za-z]{2,}", p.text)) >= 8]
        if not candidates:
            candidates = [index for index, p in enumerate(matches)
                          if p.kind != "formula" and p.random_eligible
                          and len(re.findall(r"[A-Za-z]{2,}", p.text)) >= 3]
        if not candidates:
            raise ValueError("this file has no suitable random prose paragraph; use cat")
        index = random.choice(candidates)
        self.path, self.cursor = path, index
        return matches[index]

    def move(self, offset: int) -> Passage:
        if self.cursor is None and offset < 0:
            raise ValueError("no current paragraph; use first or read")
        matches = self.book.selection(self.path)
        index = 0 if self.cursor is None else self.cursor + offset
        if index < 0:
            raise ValueError("already at the beginning of this selection")
        if index >= len(matches):
            raise ValueError("already at the end of this selection")
        self.cursor = index
        return matches[index]


def context_passages(book: Book, passage: Passage, radius: int) -> list[Passage]:
    """Inspect neighboring reader passages without moving or checkpointing."""
    if not 0 <= radius <= 10:
        raise ValueError("context must be between 0 and 10 paragraphs on each side")
    index = next((i for i, item in enumerate(book.passages)
                  if item.identifier == passage.identifier), None)
    if index is None:
        raise ValueError("this passage is not in the book")
    return book.passages[max(0, index - radius):index + radius + 1]


@dataclass(frozen=True)
class _LocalState:
    cwd: tuple[str, ...]
    previous_cwd: tuple[str, ...] | None
    path: tuple[str, ...]
    cursor: int | None
    resumed_reference: object | None
    requested_id: str | None
    requested_target: str | None


class ReaderActions:
    """One source of reader state shared by command-driven and future interfaces.

    A workspace binding reuses its existing checkpoint/freshness rules. Failures
    restore local navigation and reference state; this is not a transaction over
    arbitrary external effects. Search and inspection never write checkpoints.
    """
    def __init__(self, book: Book, workspace_reader=None, *, session=None):
        self.book = book
        self.session = ReadingSession(book) if session is None else session
        if self.session.book is not book:
            raise ValueError("the reading session must belong to this book")
        if workspace_reader is not None and getattr(workspace_reader, "book", None) is not book:
            raise ValueError("the workspace reader must belong to this book")
        self.workspace_reader = workspace_reader
        self.cwd: tuple[str, ...] = ()
        self.previous_cwd: tuple[str, ...] | None = None
        self.results: list[Passage] = []
        self._requested_id: str | None = None
        self._requested_target: str | None = None

    def _capture(self):
        reference = (self.workspace_reader.resumed_reference
                     if self.workspace_reader is not None else None)
        return _LocalState(self.cwd, self.previous_cwd, self.session.path,
                           self.session.cursor, reference, self._requested_id, self._requested_target)

    def _rollback(self, state):
        self.cwd, self.previous_cwd = state.cwd, state.previous_cwd
        self.session.path, self.session.cursor = state.path, state.cursor
        self._requested_id, self._requested_target = state.requested_id, state.requested_target
        if self.workspace_reader is not None:
            self.workspace_reader.resumed_reference = state.resumed_reference

    def _transition(self, operation, *, checkpoint=True):
        before = self._capture()
        try:
            result = operation()
            if checkpoint and self.workspace_reader is not None:
                self.workspace_reader.checkpoint(self.session, self.cwd, self.previous_cwd)
            return result
        except (ValueError, RuntimeError):
            self._rollback(before)
            raise

    def locate(self, value=None):
        """Resolve a book location; virtual aliases remain a compatibility view."""
        return resolve_path(value, self.cwd, self.book.root)

    def browse(self, path: tuple[str, ...]):
        node, path = resolve_path(display_path(path), (), self.book.root)
        if not node.is_directory:
            raise ValueError("not a directory")
        if path == self.cwd:
            return node

        def change():
            self.previous_cwd, self.cwd = self.cwd, path
            if self.workspace_reader is None:
                self.session.path, self.session.cursor = path, None
                self._requested_id = self._requested_target = None
            return node

        return self._transition(change)

    def up(self):
        return self.browse(self.cwd[:-1])

    def back(self):
        if self.previous_cwd is None:
            raise ValueError("no previous directory")
        return self.browse(self.previous_cwd)

    def read(self, path: tuple[str, ...] | None = None, first=False):
        scope = self.cwd if path is None else path
        def change():
            passage = self.session.read(scope, first)
            self._requested_id = self._requested_target = None
            return passage
        return self._transition(change)

    def open(self, identifier: str):
        def change():
            if self.workspace_reader is not None:
                # Durable work uses the canonical graph, not a projection cache
                # or prefix match limited to readable main-text passages.
                reference = self.workspace_reader.current_reference(self.session, identifier)
                passage = self.session.open(reference.target_id)
                self.workspace_reader.resumed_reference = reference
                self._requested_id, self._requested_target = reference.requested_id, reference.target_id
            elif self.book.canonical_records:
                from sol.core.references import resolve_reference
                reference = resolve_reference(self.book, identifier)
                passage = self.session.open(reference.target_id)
                self._requested_id, self._requested_target = reference.requested_id, reference.target_id
            else:
                passage = self.session.open(identifier)
                self._requested_id = self._requested_target = None
            return passage

        return self._transition(change)

    def open_result(self, number: int):
        if type(number) is not int or not 1 <= number <= len(self.results):
            raise ValueError("no such result in the latest search")
        return self.open(self.results[number - 1].identifier)

    def move(self, offset: int):
        def change():
            passage = self.session.move(offset)
            if self._requested_target != passage.identifier:
                self._requested_id = self._requested_target = None
            return passage
        return self._transition(change)

    def search(self, query: str, path: tuple[str, ...] | None = None,
               whole_word=False, limit=20):
        matches = self.book.search(query, self.cwd if path is None else path, whole_word, limit)
        self.results = list(matches)
        return list(matches)

    def context(self, radius=1):
        return context_passages(self.book, self.session.current(), radius)

    def restore(self, revision=None):
        if self.workspace_reader is None:
            raise ValueError("resume requires starting SOL with --workspace NAME")

        def change():
            cwd, previous, passage, message = self.workspace_reader.restore(self.session, revision)
            self.cwd, self.previous_cwd = cwd, previous
            return passage, message

        result = self._transition(change, checkpoint=False)
        self._requested_id = self._requested_target = None
        self.results = []
        return result

    def current_reference_id(self):
        """Retain a requested retirement ID without a workspace or second UUID system."""
        current = self.session.current()
        if self.workspace_reader is not None:
            restored = self.workspace_reader.resumed_reference
            if restored is not None and restored.target_id == current.identifier:
                return restored.requested_id
        if self._requested_target == current.identifier and self._requested_id is not None:
            return self._requested_id
        return current.identifier

    def _reference_snapshot(self):
        if self.book.corpus_snapshot is None:
            raise ValueError("ESSENCE handoffs require the verified canonical corpus, not legacy PDF reading")
        return self.book.corpus_snapshot

    def capture_active_reference(self):
        """Capture active identity without a visit, pane, actor, or workspace write."""
        from sol.core import capture_reference
        packet = capture_reference(self._reference_snapshot(), self.current_reference_id())
        if packet["reference"]["target_id"] != self.session.current().identifier:
            raise ValueError("The active reader reference disagrees with canonical data; reopen SOL")
        self.check_return_reference(packet)
        return packet

    def check_return_reference(self, packet):
        """Inspect a return; validation never navigates or checkpoints."""
        from sol.core import check_reference, resolve_reference
        reference = check_reference(self._reference_snapshot(), packet)
        projected = resolve_reference(self.book, reference.requested_id)
        passage = self.book.find_passage(reference.target_id)
        record = reference.record
        first, last = record["sources"][0], record["sources"][-1]
        if (projected.target_id != reference.target_id or projected.chain != reference.chain
                or passage.text != record["plain_text"] or passage.kind != record["type"]
                or display_path(passage.path) != record["reader_path"]
                or (passage.pdf_page, passage.printed_page, passage.end_pdf_page, passage.end_printed_page)
                != (first["pdf_page"], int(first["printed_page"]), last["pdf_page"], int(last["printed_page"]))):
            raise ValueError("The reader projection disagrees with canonical data; reopen SOL")
        return reference

    def accept_return_reference(self, packet):
        """Explicit navigation uses the same guarded checkpoint path as ordinary open."""
        reference = self.check_return_reference(packet)
        return self.open(reference.requested_id)
