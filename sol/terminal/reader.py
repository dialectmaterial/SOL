"""Optional full-screen reading view over the ordinary ReaderActions boundary.

Importing this module uses only the standard library. The source buffer retains
exact source characters; rendering alone escapes controls and invisible marks.
Selection is session-local, and this prototype does not author span notes.
"""
from __future__ import annotations

import os
import sys
import unicodedata


def _character_display(character: str) -> str:
    """One raw character becomes visible text, never a terminal instruction."""
    code = ord(character)
    if (unicodedata.category(character) in {"Cc", "Cf", "Cs", "Zl", "Zp"}
            or (character.isspace() and character != " ")
            or code in {0x034f, 0x115f, 0x1160, 0x17b4, 0x17b5, 0x2800, 0x3164, 0xffa0}
            or 0x180b <= code <= 0x180f or 0x2060 <= code <= 0x206f
            or 0xfe00 <= code <= 0xfe0f or 0xfff0 <= code <= 0xfff8
            or 0xe0000 <= code <= 0xeffff):
        if character == "\t":
            return "\\t"
        if code <= 0xff:
            return f"\\x{code:02x}"
        return f"\\u{code:04x}" if code <= 0xffff else f"\\U{code:08x}"
    return character


def safe_reader_text(value: str) -> str:
    """Escape untrusted metadata for single-line labels and result snippets."""
    return "".join(_character_display(character) for character in str(value))


def _load_toolkit():
    from prompt_toolkit.application import Application
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.document import Document
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.history import DummyHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.layout.processors import Processor, Transformation
    from prompt_toolkit.selection import SelectionState, SelectionType
    from prompt_toolkit.styles import Style
    from prompt_toolkit.utils import get_cwidth
    from prompt_toolkit.widgets import TextArea
    return locals()


def validate_reader_environment() -> None:
    """Fail before loading data or onboarding when fullscreen cannot be used."""
    if (not getattr(sys.stdin, "isatty", lambda: False)()
            or not getattr(sys.stdout, "isatty", lambda: False)()
            or os.environ.get("TERM") == "dumb"):
        raise ValueError("--reader needs an interactive terminal for both input and output "
                         "with TERM other than dumb; use the ordinary SOL command view instead")
    try:
        _load_toolkit()
    except ImportError as error:
        raise ValueError("--reader needs the optional prompt_toolkit dependency; "
                         "from the SOL project run pipx install --force '.[shell]' "
                         "to install or refresh SOL with its shell extra") from error


def _source_processor(toolkit):
    class EscapeSource(toolkit["Processor"]):
        """Preserve source offsets while displaying every unsafe character."""

        def apply_transformation(self, transformation_input):
            fragments = []
            boundaries = [0]
            reverse = []
            for fragment in transformation_input.fragments:
                style, text = fragment[:2]
                for character in text:
                    displayed = _character_display(character)
                    source_index = len(boundaries) - 1
                    fragments.append((style, displayed))
                    reverse.extend([source_index] * len(displayed))
                    boundaries.append(boundaries[-1] + len(displayed))
            reverse.append(len(boundaries) - 1)

            def source_to_display(index):
                return boundaries[max(0, min(index, len(boundaries) - 1))]

            def display_to_source(index):
                return reverse[max(0, min(index, len(reverse) - 1))]

            return toolkit["Transformation"](fragments, source_to_display, display_to_source)

    return EscapeSource()


class ReaderView:
    """A small reading surface; all domain mutations go through supplied actions."""

    def __init__(self, actions, *, input=None, output=None):
        self.actions = actions
        self._toolkit = toolkit = _load_toolkit()
        self._state = actions.snapshot()
        self.status = ""
        self._searching = False
        self._results_visible = bool(self._state.results)
        self._result_index = 0
        self._help_visible = False
        self._projecting = False
        self._preferred_column = None
        self.source_processor = _source_processor(toolkit)
        self.body = toolkit["TextArea"](
            text="", read_only=True, wrap_lines=True, scrollbar=True,
            width=toolkit["Dimension"](max=88),
            input_processors=[self.source_processor], name="sol-reader-source",
        )
        self.search_input = toolkit["TextArea"](
            multiline=False, prompt="Search book: ", history=toolkit["DummyHistory"](),
            input_processors=[self.source_processor], name="sol-reader-query",
        )
        self.results = toolkit["FormattedTextControl"](
            text=self._result_text, focusable=True,
            get_cursor_position=lambda: toolkit["Point"](x=0, y=self._result_index + 1),
        )
        self.results_window = toolkit["Window"](
            self.results, height=lambda: toolkit["Dimension"](
                min=1, max=6, preferred=min(6, len(self._state.results) + 1)),
            wrap_lines=False, style="class:results",
        )
        container = toolkit["HSplit"]([
            toolkit["Window"](toolkit["FormattedTextControl"](self._header),
                              height=3, style="class:header"),
            self.body,
            toolkit["ConditionalContainer"](
                self.search_input, toolkit["Condition"](lambda: self._searching)),
            toolkit["ConditionalContainer"](
                self.results_window, toolkit["Condition"](lambda: self._results_visible)),
            toolkit["ConditionalContainer"](
                toolkit["Window"](toolkit["FormattedTextControl"](
                    "Arrows: source cursor/scroll | Shift-arrows: select characters\n"
                    "Alt-Left/Right: reading history | Tab: source/results\n"
                    "Selection is session-local; durable span notes are deferred."), height=3),
                toolkit["Condition"](lambda: self._help_visible)),
            toolkit["Window"](toolkit["FormattedTextControl"](self._status_text),
                              height=2, style="class:status"),
            toolkit["Window"](toolkit["FormattedTextControl"](
                "PgDn/n next  PgUp/p previous  / search  Esc clear  ? help  Ctrl-Q quit"),
                height=1, style="class:footer"),
        ])
        bindings = toolkit["KeyBindings"]()
        body_focus = toolkit["Condition"](lambda: self.application.layout.has_focus(self.body))
        result_focus = toolkit["Condition"](lambda: self.application.layout.has_focus(self.results))
        query_focus = toolkit["Condition"](lambda: self.application.layout.has_focus(self.search_input))

        @bindings.add("c-q", eager=True)
        @bindings.add("c-c", eager=True)
        def quit_reader(event):
            event.app.exit(result=0)

        @bindings.add("n", filter=~query_focus)
        @bindings.add("pagedown", filter=~query_focus)
        def next_passage(event):
            self._act(lambda: self.actions.move(1))

        @bindings.add("p", filter=~query_focus)
        @bindings.add("pageup", filter=~query_focus)
        def previous_passage(event):
            self._act(lambda: self.actions.move(-1))

        @bindings.add("escape", "left", filter=~query_focus)
        def history_back(event):
            self._act(self.actions.history_back)

        @bindings.add("escape", "right", filter=~query_focus)
        def history_forward(event):
            self._act(self.actions.history_forward)

        @bindings.add("/", filter=~query_focus)
        def start_search(event):
            self._searching = True
            self.search_input.buffer.set_document(toolkit["Document"](self._state.search_query or ""))
            self.search_input.buffer.cursor_position = len(self.search_input.text)
            event.app.layout.focus(self.search_input)

        @bindings.add("enter", filter=query_focus)
        def search(event):
            if self._act(lambda: self.actions.search(self.search_input.text, (), limit=20), project=False):
                self._result_index = 0
                self._results_visible = True
                self._searching = False
                event.app.layout.focus(self.results)
                if not self._state.results:
                    self.status = "No matching passages. Press / to search again."

        @bindings.add("up", filter=result_focus)
        def result_up(event):
            self._result_index = max(0, self._result_index - 1)

        @bindings.add("down", filter=result_focus)
        def result_down(event):
            self._result_index = min(max(0, len(self._state.results) - 1), self._result_index + 1)

        @bindings.add("enter", filter=result_focus)
        def open_result(event):
            self._act(lambda: self.actions.open_result(self._result_index + 1))

        @bindings.add("tab", filter=~query_focus)
        @bindings.add("s-tab", filter=~query_focus)
        def change_focus(event):
            target = self.results if self._results_visible and body_focus() else self.body
            event.app.layout.focus(target)

        @bindings.add("escape")
        def clear_or_cancel(event):
            if self._searching:
                self._searching = False
                event.app.layout.focus(self.body)
            else:
                if self._act(self.actions.clear_selection, project=False):
                    self.body.buffer.exit_selection()
                self._help_visible = False

        @bindings.add("?", filter=~query_focus)
        def toggle_help(event):
            self._help_visible = not self._help_visible

        # Override shifted/unshifted arrows so selection is always a character
        # span, regardless of the toolkit's editable-buffer shift mode.
        for key, direction in (("left", -1), ("right", 1), ("up", -1), ("down", 1)):
            def cursor(event, key=key, direction=direction):
                self.body.buffer.exit_selection()
                self._move_cursor(key, direction)
            bindings.add(key, filter=body_focus)(cursor)

            def select(event, key=key, direction=direction):
                if self.body.buffer.selection_state is None:
                    self.body.buffer.start_selection(toolkit["SelectionType"].CHARACTERS)
                self._move_cursor(key, direction)
            bindings.add("s-" + key, filter=body_focus)(select)

        self.application = toolkit["Application"](
            layout=toolkit["Layout"](container, focused_element=self.body),
            key_bindings=bindings, full_screen=True, editing_mode=toolkit["EditingMode"].EMACS,
            input=input, output=output, mouse_support=False,
            style=toolkit["Style"].from_dict({
                "header": "bold", "footer": "reverse", "status": "",
                "results": "", "result.selected": "reverse", "selected-text": "reverse",
            }),
        )
        self.application.key_processor.after_key_press += self._sync_selection
        self._project_body()

    def _move_cursor(self, key, direction):
        buffer = self.body.buffer
        if key in {"left", "right"}:
            self._preferred_column = None
            buffer.cursor_position += direction
        else:
            self._move_vertical(direction)

    def _move_vertical(self, direction):
        """Move between visually wrapped rows without changing source offsets."""
        buffer = self.body.buffer
        info = self.body.window.render_info
        width = max(1, info.window_width if info is not None else 80)
        row, column = 0, 0
        positions = [(row, column)]
        for character in buffer.text:
            if character == "\n":
                row, column = row + 1, 0
            else:
                for displayed in _character_display(character):
                    cells = self._toolkit["get_cwidth"](displayed)
                    if column + cells > width:
                        row, column = row + 1, 0
                    column += cells
                if column >= width:
                    row, column = row + 1, 0
            positions.append((row, column))
        current_row, current_column = positions[buffer.cursor_position]
        if self._preferred_column is None:
            self._preferred_column = current_column
        rows = {row for row, _ in positions if (row - current_row) * direction > 0}
        if not rows:
            return
        target_row = min(rows) if direction > 0 else max(rows)
        candidates = [index for index, (row, column) in enumerate(positions) if row == target_row]
        buffer.cursor_position = min(candidates, key=lambda index: (
            abs(positions[index][1] - self._preferred_column), abs(index - buffer.cursor_position)))

    def _project_body(self):
        current, selection = self._state.current, self._state.selection
        text = "" if current is None else current.text
        self._projecting = True
        self._preferred_column = None
        try:
            cursor = selection.end if selection is not None else 0
            self.body.buffer.set_document(self._toolkit["Document"](text, cursor), bypass_readonly=True)
            self.body.buffer.selection_state = (
                self._toolkit["SelectionState"](selection.start,
                    self._toolkit["SelectionType"].CHARACTERS) if selection is not None else None)
        finally:
            self._projecting = False

    def _sync_selection(self, sender=None):
        if self._projecting or self._state.current is None:
            return
        ranges = list(self.body.buffer.document.selection_ranges())
        span = ranges[0] if ranges and ranges[0][0] != ranges[0][1] else None
        old = self._state.selection
        if span == (None if old is None else (old.start, old.end)):
            return
        operation = self.actions.clear_selection if span is None else lambda: self.actions.select_span(*span)
        if not self._act(operation, project=False):
            self._project_body()

    def _act(self, operation, *, project=True):
        try:
            operation()
            state = self.actions.snapshot()
        except (ValueError, RuntimeError, OSError) as error:
            self.status = safe_reader_text(str(error))
            return False
        self._state = state
        self._result_index = min(self._result_index, max(0, len(state.results) - 1))
        self.status = ""
        if project:
            self._results_visible = bool(state.results or state.search_query)
            self._project_body()
            self.application.layout.focus(self.body)
        return True

    def _header(self):
        passage = self._state.current
        if passage is None:
            return "SOL reader\nNo active passage.\nPgDn/n begins reading; / searches."
        title = passage.heading or passage.node.title or self.actions.book.root.title
        path = "/" + "/".join(passage.path)
        printed = str(passage.printed_page)
        pdf = str(passage.pdf_page)
        if passage.end_printed_page != passage.printed_page:
            printed += f"-{passage.end_printed_page}"
        if passage.end_pdf_page != passage.pdf_page:
            pdf += f"-{passage.end_pdf_page}"
        return safe_reader_text(title) + "\n" + safe_reader_text(path) + f"\nPrinted {printed} | PDF {pdf}"

    def _status_text(self):
        passage = self._state.current
        position = "No position"
        if passage is not None:
            matches = self.actions.book.selection(self._state.scope)
            index = next((i for i, item in enumerate(matches) if item.identifier == passage.identifier), 0)
            position = f"Passage {index + 1}/{len(matches)}"
            if passage.needs_source_review:
                position += " [source review]"
        history = ("back" if self._state.can_go_back else "-") + "/" + (
            "forward" if self._state.can_go_forward else "-")
        selected = 0 if self._state.selection is None else self._state.selection.end - self._state.selection.start
        return (f"{position} | history {history} | {selected} selected characters (session-local)\n"
                + safe_reader_text(self.status))

    def _result_text(self):
        rows = [("class:header", f"Search results: {len(self._state.results)} (Enter opens; Tab returns to source)\n")]
        for index, passage in enumerate(self._state.results):
            marker = ">" if index == self._result_index else " "
            title = passage.heading or passage.node.title
            snippet = passage.text.replace("\n", " ")[:100]
            text = safe_reader_text(f"{marker} {index + 1}. {title} | p. {passage.printed_page} | {snippet}")
            rows.append(("class:result.selected" if index == self._result_index else "", text + "\n"))
        return rows

    def run(self) -> int:
        """The toolkit owns raw-mode/alternate-screen cleanup, including errors."""
        try:
            return int(self.application.run() or 0)
        except (EOFError, KeyboardInterrupt):
            return 0


def run_reader(book, workspace_reader=None) -> int:
    """Restore normal reading state; a refused restore never writes a new visit."""
    validate_reader_environment()
    from sol.reader.actions import ReaderActions
    actions = ReaderActions(book, workspace_reader)
    message = ""
    try:
        if workspace_reader is not None and workspace_reader.store.get_state() is not None:
            _, message = actions.restore()
        else:
            actions.read(first=True)
    except (ValueError, RuntimeError, OSError) as error:
        message = str(error)
    view = ReaderView(actions)
    view.status = message
    return view.run()
