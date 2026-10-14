"""Reader state and actions, without a command loop or terminal dependency.

This is BEING's application boundary, not another corpus or persistence layer.
The caller supplies a loaded book and, optionally, its existing WorkspaceReader.
Actions return domain objects; prompts, parsing, rendering, and panes belong to
the interface. No database, actor profile, or PDF is opened implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
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
    cursor_offset: int = 0
    viewport_offset: int | None = None

    def _position(self, path, index, passage):
        previous = None if self.cursor is None else self.current().identifier
        self.path, self.cursor = path, index
        if previous != passage.identifier:
            self.cursor_offset, self.viewport_offset = 0, None
        return passage

    def current(self) -> Passage:
        if self.cursor is None:
            raise ValueError("no current paragraph; use first, read, or open")
        return self.book.selection(self.path)[self.cursor]

    def open(self, identifier: str) -> Passage:
        passage = self.book.find_passage(identifier)
        path = passage.path if self.cursor is None or passage.path[:len(self.path)] != self.path else self.path
        matches = self.book.selection(path)
        index = next(index for index, item in enumerate(matches)
                     if item.identifier == passage.identifier)
        return self._position(path, index, passage)

    def read(self, path: tuple[str, ...], first: bool = False) -> Passage:
        matches = self.book.selection(path)
        if first:
            return self._position(path, 0, matches[0])
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
        return self._position(path, index, matches[index])

    def move(self, offset: int) -> Passage:
        if self.cursor is None and offset < 0:
            raise ValueError("no current paragraph; use first or read")
        matches = self.book.selection(self.path)
        index = 0 if self.cursor is None else self.cursor + offset
        if index < 0:
            raise ValueError("already at the beginning of this selection")
        if index >= len(matches):
            raise ValueError("already at the end of this selection")
        return self._position(self.path, index, matches[index])


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
class TextSelection:
    """A transient span in exact canonical plain text, using codepoint offsets."""
    requested_id: str
    target_id: str
    start: int
    end: int
    text: str
    content_sha256: str
    plain_text_sha256: str


@dataclass(frozen=True)
class ReaderState:
    """The reader context an interface can inspect without writing a visit."""
    current: Passage | None
    cwd: tuple[str, ...]
    scope: tuple[str, ...]
    requested_id: str | None
    selection: TextSelection | None
    can_go_back: bool
    can_go_forward: bool
    search_query: str | None
    results: tuple[Passage, ...]
    cursor_offset: int = 0
    viewport_offset: int | None = None


@dataclass(frozen=True)
class _ReadingContext:
    cwd: tuple[str, ...]
    previous_cwd: tuple[str, ...] | None
    scope: tuple[str, ...]
    current_id: str | None
    requested_id: str | None
    selection: TextSelection | None
    search_query: str | None
    result_ids: tuple[str, ...]
    cursor_offset: int
    viewport_offset: int | None


@dataclass(frozen=True)
class _LocalState:
    cwd: tuple[str, ...]
    previous_cwd: tuple[str, ...] | None
    path: tuple[str, ...]
    cursor: int | None
    resumed_reference: object | None
    requested_id: str | None
    requested_target: str | None
    selection: TextSelection | None
    search_query: str | None
    results: tuple[Passage, ...]
    trail: tuple[_ReadingContext, ...]
    history_index: int
    cursor_offset: int
    viewport_offset: int | None
    preferred_column: int | None
    preferred_layout: tuple | None


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
        self.search_query: str | None = None
        self._requested_id: str | None = None
        self._requested_target: str | None = None
        self._selection: TextSelection | None = None
        self._preferred_column: int | None = None
        self._preferred_layout: tuple | None = None
        self._trail = (self._context(),)
        self._history_index = 0

    def _current(self):
        return None if self.session.cursor is None else self.session.current()

    def _context(self):
        current = self._current()
        return _ReadingContext(
            self.cwd, self.previous_cwd, self.session.path,
            current.identifier if current is not None else None,
            self.current_reference_id() if current is not None else None,
            self._selection, self.search_query,
            tuple(passage.identifier for passage in self.results),
            self.session.cursor_offset, self.session.viewport_offset)

    def _amend_context(self):
        context = self._context()
        self._trail = (self._trail[:self._history_index] + (context,)
                       + self._trail[self._history_index + 1:])

    def _append_context(self, context):
        trail = self._trail[:self._history_index + 1] + (context,)
        self._trail = trail[-100:]
        self._history_index = len(self._trail) - 1

    @staticmethod
    def _navigation_key(context):
        return (context.cwd, context.previous_cwd, context.scope,
                context.current_id, context.requested_id)

    def _capture(self):
        reference = (self.workspace_reader.resumed_reference
                     if self.workspace_reader is not None else None)
        return _LocalState(self.cwd, self.previous_cwd, self.session.path,
                           self.session.cursor, reference, self._requested_id, self._requested_target,
                           self._selection, self.search_query, tuple(self.results),
                           self._trail, self._history_index, self.session.cursor_offset,
                           self.session.viewport_offset, self._preferred_column, self._preferred_layout)

    def _rollback(self, state):
        self.cwd, self.previous_cwd = state.cwd, state.previous_cwd
        self.session.path, self.session.cursor = state.path, state.cursor
        self._requested_id, self._requested_target = state.requested_id, state.requested_target
        self._selection, self.search_query = state.selection, state.search_query
        self.results = list(state.results)
        self._trail, self._history_index = state.trail, state.history_index
        self.session.cursor_offset, self.session.viewport_offset = state.cursor_offset, state.viewport_offset
        self._preferred_column = state.preferred_column
        self._preferred_layout = state.preferred_layout
        if self.workspace_reader is not None:
            self.workspace_reader.resumed_reference = state.resumed_reference

    def _transition(self, operation, *, checkpoint=True, history=True):
        before = self._capture()
        origin = self._context()
        try:
            result = operation()
            current = self._current()
            if self._selection is not None:
                if current is None or current.identifier != self._selection.target_id:
                    self._selection = None
                else:
                    self._selection = replace(self._selection, requested_id=self.current_reference_id())
                    self._validate_selection(self._selection)
            destination = self._context()
            changed = self._navigation_key(origin) != self._navigation_key(destination)
            if origin.current_id != destination.current_id:
                self._preferred_column = None
            if checkpoint and self.workspace_reader is not None:
                self.workspace_reader.checkpoint(self.session, self.cwd, self.previous_cwd)
            if history and changed:
                self._append_context(destination)
            elif history:
                self._amend_context()
            return result
        except (ValueError, RuntimeError):
            self._rollback(before)
            raise

    def _selection_source(self, requested_id, target_id):
        """Validate the explicit loaded generation, without reading source files."""
        if not self.book.canonical_records:
            raise ValueError("text selection requires canonical Book records")
        from sol.core.references import resolve_reference
        try:
            reference = resolve_reference(self.book, requested_id)
            record = reference.record
            plain_text, markdown = record["plain_text"], record["markdown"]
            digest = record["content_sha256"]
            sources = record["sources"]
            first, last = sources[0], sources[-1]
            passage = self.book.find_passage(target_id)
            valid = (
                reference.target_id == target_id and record["id"] == target_id
                and record["type"] in {"paragraph", "list_item", "quotation", "formula"}
                and isinstance(plain_text, str) and isinstance(markdown, str)
                and digest == sha256(markdown.encode("utf-8")).hexdigest()
                and passage.identifier == target_id and passage.text == plain_text
                and passage.kind == record["type"]
                and display_path(passage.path) == record["reader_path"]
                and (passage.pdf_page, passage.printed_page,
                     passage.end_pdf_page, passage.end_printed_page)
                == (first["pdf_page"], int(first["printed_page"]),
                    last["pdf_page"], int(last["printed_page"])))
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise ValueError("The canonical selection source is corrupted; reopen SOL") from error
        if not valid:
            raise ValueError("The reader projection or canonical selection source disagrees; reopen SOL")
        return plain_text, digest, sha256(plain_text.encode("utf-8")).hexdigest()

    def _validate_selection(self, selection):
        current = self._current()
        if (current is None or current.identifier != selection.target_id
                or self.current_reference_id() != selection.requested_id):
            raise ValueError("The selected span no longer belongs to the current passage")
        plain_text, content_digest, plain_digest = self._selection_source(
            selection.requested_id, selection.target_id)
        if (content_digest != selection.content_sha256
                or plain_digest != selection.plain_text_sha256
                or not 0 <= selection.start < selection.end <= len(plain_text)
                or plain_text[selection.start:selection.end] != selection.text):
            raise ValueError("The selected span's source text changed; select it again after reopening SOL")
        return selection

    @property
    def selection(self):
        return None if self._selection is None else self._validate_selection(self._selection)

    def select_span(self, start, end):
        """Select a nonempty half-open span; selection creates no personal object."""
        if type(start) is not int or type(end) is not int:
            raise ValueError("selection offsets must be integer codepoint positions")
        current = self.session.current()
        expected_id = self._trail[self._history_index].current_id
        if expected_id is not None and current.identifier != expected_id:
            raise ValueError("The current reader projection disagrees with its reading context; reopen SOL")
        requested_id = self.current_reference_id()
        plain_text, content_digest, plain_digest = self._selection_source(requested_id, current.identifier)
        if not 0 <= start < end <= len(plain_text):
            raise ValueError("selection requires a nonempty span within the canonical plain text")
        selected = TextSelection(requested_id, current.identifier, start, end,
                                 plain_text[start:end], content_digest, plain_digest)
        self._selection = selected
        if self.session.cursor_offset not in {start, end}:
            self.session.cursor_offset = end
            self._preferred_column = None
        self._amend_context()
        return selected

    def clear_selection(self):
        self._selection = None
        self._amend_context()

    @property
    def cursor_offset(self):
        """Insertion boundary in canonical plain text, never a display column."""
        return self.session.cursor_offset

    def set_cursor(self, offset):
        """Move the transient source cursor without a checkpoint or new visit."""
        current = self.snapshot().current
        if current is None:
            raise ValueError("no current paragraph; use first, read, or open")
        if type(offset) is not int or not 0 <= offset <= len(current.text):
            raise ValueError("cursor offset must be an integer boundary within the source text")
        self.session.cursor_offset = offset
        self._preferred_column = None
        self._amend_context()
        return offset

    def set_viewport(self, offset):
        """Remember a source boundary at the viewport top, without persisting."""
        current = self.snapshot().current
        if current is None:
            raise ValueError("no current paragraph; use first, read, or open")
        if offset is not None and (type(offset) is not int or not 0 <= offset <= len(current.text)):
            raise ValueError("viewport offset must be a source boundary or None")
        self.session.viewport_offset = offset
        self._amend_context()
        return offset

    def move_horizontal(self, delta):
        if type(delta) is not int:
            raise ValueError("cursor movement must be an integer")
        current = self.session.current()
        return self.set_cursor(max(0, min(len(current.text), self.cursor_offset + delta)))

    def _move_vertical(self, rows, width=None, *, layout=None):
        from sol.reader.navigation import source_layout, validate_layout, vertical_offset
        if type(rows) is not int:
            raise ValueError("cursor row movement must be an integer")
        current = self.snapshot().current
        if current is None:
            raise ValueError("no current paragraph; use first, read, or open")
        positions = (source_layout(current.text, width) if layout is None
                     else validate_layout(layout, len(current.text)))
        if positions != self._preferred_layout:
            self._preferred_column = None
            self._preferred_layout = positions
        offset, preferred = vertical_offset(positions, self.cursor_offset, rows, self._preferred_column)
        self.session.cursor_offset, self._preferred_column = offset, preferred
        self._amend_context()
        return offset

    def move_up(self, width=None, *, layout=None):
        return self._move_vertical(-1, width, layout=layout)

    def move_down(self, width=None, *, layout=None):
        return self._move_vertical(1, width, layout=layout)

    def half_page(self, direction, rows, width=None, *, layout=None):
        if type(direction) is not int or direction not in {-1, 1}:
            raise ValueError("half-page direction must be -1 or 1")
        if type(rows) is not int or rows < 1:
            raise ValueError("visible row count must be a positive integer")
        return self._move_vertical(direction * max(1, rows // 2), width, layout=layout)

    def move_paragraph(self, offset):
        """Visit a neighboring semantic paragraph at its beginning."""
        if type(offset) is not int:
            raise ValueError("paragraph movement must be an integer")
        def change():
            passage = self.session.move(offset)
            if self._requested_target != passage.identifier:
                self._requested_id = self._requested_target = None
            self.session.cursor_offset, self.session.viewport_offset = 0, None
            self._preferred_column = None
            return passage
        return self._transition(change)

    def jump(self, where):
        """Jump to a source boundary or the beginning/end of the reading scope."""
        if where in {"passage-start", "passage-end"}:
            current = self.session.current()
            return self.set_cursor(0 if where == "passage-start" else len(current.text))
        if where not in {"scope-start", "scope-end"}:
            raise ValueError("jump needs passage-start/end or scope-start/end")
        scope = self.session.path
        matches = self.book.selection(scope)
        index = 0 if where == "scope-start" else len(matches) - 1
        def change():
            passage = self.session._position(scope, index, matches[index])
            if self._requested_target != passage.identifier:
                self._requested_id = self._requested_target = None
            self.session.cursor_offset = 0 if where == "scope-start" else len(passage.text)
            self.session.viewport_offset = None
            self._preferred_column = None
            return passage
        return self._transition(change)

    def search_next(self, reverse=False):
        """Visit the next/previous passage in the latest literal search, wrapping."""
        if type(reverse) is not bool:
            raise ValueError("reverse search direction must be a boolean")
        if not self.results:
            raise ValueError("no search results; search the book first")
        current = self._current()
        index = next((index for index, passage in enumerate(self.results)
                      if current is not None and passage.identifier == current.identifier), None)
        target = ((index + (-1 if reverse else 1)) % len(self.results) if index is not None
                  else len(self.results) - 1 if reverse else 0)
        return self.open_result(target + 1)

    def save_position(self):
        """Save a changed semantic position explicitly using existing CAS guards.

        Returns a legacy-schema warning or an empty success value. Temporary readers and older
        injected workspace adapters have no position-saving side effects.
        """
        if self._current() is None or self.workspace_reader is None:
            return None
        save = getattr(self.workspace_reader, "save_position", None)
        if save is None:
            return None
        return self._transition(lambda: save(self.session, self.cwd, self.previous_cwd),
                                checkpoint=False, history=False)

    def _history_target(self, direction):
        index = self._history_index + direction
        while 0 <= index < len(self._trail):
            if self._trail[index].current_id is not None:
                return index
            index += direction
        return None

    def _history_move(self, direction):
        index = self._history_target(direction)
        if index is None:
            raise ValueError("no previous reading context" if direction < 0 else "no next reading context")
        context = self._trail[index]

        def change():
            # Resolve IDs and scope before touching the active reader context.
            passage = self.book.find_passage(context.current_id)
            reference = None
            if self.book.canonical_records:
                from sol.core.references import resolve_reference
                reference = resolve_reference(self.book, context.requested_id)
                if reference.target_id != context.current_id:
                    raise ValueError("The historical reading reference changed; reopen SOL")
            matches = self.book.selection(context.scope)
            cursor = next((i for i, row in enumerate(matches)
                           if row.identifier == context.current_id), None)
            if cursor is None:
                raise ValueError("The passage is no longer in its historical reading scope")
            results = [self.book.find_passage(identifier) for identifier in context.result_ids]
            self.cwd, self.previous_cwd = context.cwd, context.previous_cwd
            self.session.path, self.session.cursor = context.scope, cursor
            if not 0 <= context.cursor_offset <= len(passage.text):
                raise ValueError("The historical cursor is no longer within its source text")
            self.session.cursor_offset = context.cursor_offset
            self.session.viewport_offset = context.viewport_offset
            self._preferred_column = None
            self._requested_id, self._requested_target = context.requested_id, context.current_id
            if self.workspace_reader is not None:
                self.workspace_reader.resumed_reference = reference
            self._selection, self.search_query, self.results = context.selection, context.search_query, results
            self._history_index = index
            return passage

        return self._transition(change, history=False)

    def history_back(self):
        """Restore a prior complete reading context through normal checkpoint guards."""
        return self._history_move(-1)

    def history_forward(self):
        return self._history_move(1)

    def snapshot(self):
        current = self._current()
        expected_id = self._trail[self._history_index].current_id
        if (None if current is None else current.identifier) != expected_id:
            raise ValueError("The current reader projection disagrees with its reading context; reopen SOL")
        if (type(self.session.cursor_offset) is not int or self.session.cursor_offset < 0
                or self.session.cursor_offset > (0 if current is None else len(current.text))):
            raise ValueError("The reader cursor is outside its source text; reopen SOL")
        viewport = self.session.viewport_offset
        if viewport is not None and (type(viewport) is not int or current is None
                                     or not 0 <= viewport <= len(current.text)):
            raise ValueError("The reader viewport anchor is outside its source text; reopen SOL")
        return ReaderState(current, self.cwd, self.session.path,
                           self.current_reference_id() if current is not None else None,
                           self.selection, self._history_target(-1) is not None,
                           self._history_target(1) is not None, self.search_query,
                           tuple(self.results), self.session.cursor_offset,
                           self.session.viewport_offset)

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
                self.session.cursor_offset, self.session.viewport_offset = 0, None
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
        self.search_query = query
        self._amend_context()
        return list(matches)

    def context(self, radius=1):
        return context_passages(self.book, self.session.current(), radius)

    def restore(self, revision=None):
        if self.workspace_reader is None:
            raise ValueError("resume requires starting SOL with --workspace NAME")

        def change():
            cwd, previous, passage, message = self.workspace_reader.restore(self.session, revision)
            self.cwd, self.previous_cwd = cwd, previous
            self._requested_id = self._requested_target = None
            self._selection, self.search_query, self.results = None, None, []
            return passage, message

        result = self._transition(change, checkpoint=False, history=revision is not None)
        if revision is None:
            self._trail, self._history_index = (self._context(),), 0
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
