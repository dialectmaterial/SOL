"""Optional full-screen reading view over the ordinary ReaderActions boundary.

Importing this module uses only the standard library. The source buffer retains
exact source characters; rendering alone escapes controls and invisible marks.
Selection is session-local. Semantic reading positions reuse workspace checkpoints;
this adapter does not author span notes or turn screen rows into source identity.
"""
from __future__ import annotations

from bisect import bisect_right
import os
import sys
import unicodedata

from sol.reader.options import DEFAULT_READER_WIDTH


def emphasis_style(mode="auto"):
    """Unknown terminals use visible underlining; capabilities aren't assumed."""
    if mode not in {"auto", "italic", "underline"}:
        raise ValueError("reader emphasis must be auto, italic or underline")
    if mode != "auto":
        return mode
    term = os.environ.get("TERM", "").lower()
    return "italic" if term.startswith(("alacritty", "xterm", "screen", "tmux", "foot", "wezterm")) else "underline"


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
    from markdown_it import MarkdownIt
    from prompt_toolkit.application import Application
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.document import Document
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.history import DummyHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import ConditionalContainer, HSplit, HorizontalAlign, Layout, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.layout.processors import Processor, Transformation
    from prompt_toolkit.lexers import Lexer
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
        raise ValueError("the SOL reader needs an interactive terminal for both input and output "
                         "with TERM other than dumb; use sol -r for one-shot output "
                         "or sol --shell for the command interface")
    try:
        _load_toolkit()
    except ImportError as error:
        raise ValueError("the SOL reader needs prompt_toolkit and CommonMark; "
                         "from the SOL project run pipx install --force . "
                         "to install or refresh its reader dependencies") from error


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


def _reading_processor(toolkit, plan_line):
    class ReadingProjection(toolkit["Processor"]):
        """Soft-wrap source prose without editing Buffer's text or positions."""
        def apply_transformation(self, transformation_input):
            source = transformation_input.document.lines[transformation_input.lineno]
            plan = plan_line(source, max(1, transformation_input.width))
            return toolkit["Transformation"](
                plan.styled_fragments(transformation_input.fragments),
                plan.source_to_display, plan.display_to_source)
    return ReadingProjection()


def _typography_lexer(toolkit, typography, search_spans=lambda: ()):
    class SourceTypography(toolkit["Lexer"]):
        def invalidation_hash(self):
            # BufferControl caches lexed lines even when the source is unchanged.
            # Include presentation ranges so same-passage queries, dismissals,
            # and semantic style changes cannot reuse stale character styles.
            return typography().spans, search_spans()

        def lex_document(self, document):
            offsets = [0]
            for line in document.lines:
                offsets.append(offsets[-1] + len(line) + 1)
            spans = typography().spans
            matches = search_spans()
            match_starts = tuple(left for left, _ in matches)

            def get_line(number):
                line = document.lines[number]
                start = offsets[number]
                fragments = []
                for index, character in enumerate(line, start):
                    styles = {style for span in spans if span.start <= index < span.end
                              for style in span.styles}
                    match = bisect_right(match_starts, index) - 1
                    if match >= 0 and index < matches[match][1]:
                        styles.add("search")
                    fragments.append((" ".join("class:source." + style for style in sorted(styles)), character))
                return fragments
            return get_line
    return SourceTypography()


class ReaderView:
    """A small reading surface; all domain mutations go through supplied actions."""

    def __init__(self, actions, *, input=None, output=None, width=DEFAULT_READER_WIDTH, emphasis="auto"):
        if type(width) is not int or not 20 <= width <= 240:
            raise ValueError("reader width must be between 20 and 240 columns")
        self.actions = actions
        self.reading_width = width
        self.emphasis = emphasis_style(emphasis)
        self._toolkit = toolkit = _load_toolkit()
        self._state = actions.snapshot()
        self.status = ""
        self._searching = False
        self._search_marks_visible = True
        self._results_visible = bool(self._state.results)
        self._result_index = 0
        self._help_visible = False
        self._context_visible = False
        self._focus_mode = False
        self._exit_notice = ""
        self._saved_on_exit = False
        self._projecting = False
        self._geometry_cache = None
        self._line_plans = {}
        from sol.reader.typography import Typography
        self.typography = Typography(())
        self.source_processor = _source_processor(toolkit)
        self.reading_processor = _reading_processor(toolkit, self._plan_line)
        self.body = toolkit["TextArea"](
            text="", read_only=True, wrap_lines=True, scrollbar=False,
            width=toolkit["Dimension"](min=1, preferred=width, max=width),
            lexer=_typography_lexer(toolkit, lambda: self.typography, self._search_spans),
            input_processors=[self.reading_processor], name="sol-reader-source",
        )
        # TextArea's DynamicLexer keys its cache by lexer identity alone. This
        # reader never switches lexers; use ours directly so changing semantic
        # ranges invalidates the cache without changing canonical source text.
        self.body.control.lexer = self.body.lexer
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
        measure = toolkit["Dimension"](min=1, preferred=width, max=width)
        self.heading_window = toolkit["Window"](
            toolkit["FormattedTextControl"](self._document_heading), height=2,
            style="class:document-context", wrap_lines=False)
        self.context_window = toolkit["Window"](
            toolkit["FormattedTextControl"](self._header),
            height=toolkit["Dimension"](min=1, max=6, preferred=4),
            style="class:context", wrap_lines=True)
        self.top_gap = toolkit["Window"](height=lambda: self._gap_height(0))
        self.body_gap = toolkit["Window"](height=lambda: self._gap_height(1))
        column = toolkit["HSplit"]([
            self.top_gap,
            toolkit["ConditionalContainer"](
                self.heading_window, toolkit["Condition"](lambda: not self._focus_mode)),
            toolkit["ConditionalContainer"](
                self.context_window,
                toolkit["Condition"](lambda: self._context_visible)),
            self.body_gap,
            self.body,
        ], width=measure)
        container = toolkit["HSplit"]([
            toolkit["VSplit"]([column], align=toolkit["HorizontalAlign"].CENTER),
            toolkit["ConditionalContainer"](
                self.search_input, toolkit["Condition"](lambda: self._searching)),
            toolkit["ConditionalContainer"](
                self.results_window, toolkit["Condition"](lambda: self._results_visible)),
            toolkit["ConditionalContainer"](
                toolkit["Window"](toolkit["FormattedTextControl"](
                    "j/k or arrows: reading rows, continuing at edges  h/l: characters\n"
                    "Ctrl-D/U: half page  gg/G: scope ends  b/n: passages  v: select\n"
                    "/: search  Ctrl-P/N: previous/next result  Alt-Left/Right: history\n"
                    "c: context  f: focus  Esc: clear/close  Ctrl-Q: save & quit\n"
                    "Selections are session-local; Ctrl-C quits without saving the cursor."), height=5),
                toolkit["Condition"](lambda: self._help_visible)),
            toolkit["ConditionalContainer"](
                toolkit["Window"](toolkit["FormattedTextControl"](self._status_text),
                                  height=self._status_height, wrap_lines=True,
                                  style=lambda: "class:status class:warning" if (
                                      self.status or self._needs_review() or self.typography.degraded
                                      or self._search_degraded()) else "class:status"),
                toolkit["Condition"](lambda: not self._focus_mode or bool(self.status)
                                      or self._needs_review() or self.typography.degraded
                                      or self._search_degraded())),
            toolkit["ConditionalContainer"](
                toolkit["Window"](toolkit["FormattedTextControl"](self._footer_text),
                    height=1, style="class:footer"),
                toolkit["Condition"](lambda: not self._focus_mode)),
        ])
        bindings = toolkit["KeyBindings"]()
        body_focus = toolkit["Condition"](lambda: self.application.layout.has_focus(self.body))
        result_focus = toolkit["Condition"](lambda: self.application.layout.has_focus(self.results))
        query_focus = toolkit["Condition"](lambda: self.application.layout.has_focus(self.search_input))

        @bindings.add("c-q", eager=True)
        def quit_reader(event):
            if self._act(self._save_position, project=False):
                self._saved_on_exit = True
                event.app.exit(result=0)

        @bindings.add("c-c", eager=True)
        def discard_cursor(event):
            self._saved_on_exit = True
            event.app.exit(result=0)

        @bindings.add("}", filter=body_focus)
        @bindings.add("n", filter=body_focus)
        @bindings.add("pagedown", filter=~query_focus)
        def next_passage(event):
            self._act(lambda: self.actions.move_paragraph(1))

        @bindings.add("p", filter=~query_focus)
        @bindings.add("{", filter=body_focus)
        @bindings.add("b", filter=body_focus)
        @bindings.add("pageup", filter=~query_focus)
        def previous_passage(event):
            self._act(lambda: self.actions.move_paragraph(-1))

        @bindings.add("c-n", filter=body_focus)
        @bindings.add("c-p", filter=body_focus)
        def repeat_search(event):
            self._search_marks_visible = True
            self._act(lambda: self.actions.search_next(reverse=event.key_sequence[-1].key == "c-p"))
            if self._state.current is not None:
                self._results_visible = False

        @bindings.add("g", "g", filter=body_focus)
        def scope_start(event):
            self._act(lambda: self.actions.jump("scope-start"))

        @bindings.add("G", filter=body_focus)
        def scope_end(event):
            self._act(lambda: self.actions.jump("scope-end"))

        @bindings.add("c-d", filter=body_focus)
        @bindings.add("c-u", filter=body_focus)
        def half_page(event):
            direction = -1 if event.key_sequence[-1].key == "c-u" else 1
            rows = self.body.window.render_info.window_height if self.body.window.render_info else 20
            self._advance_reading(direction * max(1, rows // 2))

        @bindings.add("v", filter=body_focus)
        def visual_selection(event):
            if self.body.buffer.selection_state is None:
                self.body.buffer.start_selection(toolkit["SelectionType"].CHARACTERS)
            else:
                self.body.buffer.exit_selection()

        @bindings.add("c", filter=body_focus)
        def context(event):
            self._context_visible = not self._context_visible

        @bindings.add("f", filter=body_focus)
        def focus(event):
            self._focus_mode = not self._focus_mode
            if self._focus_mode:
                self._context_visible = self._help_visible = self._results_visible = False

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
                self._search_marks_visible = True
                self._results_visible = True
                self._searching = False
                event.app.layout.focus(self.results)
                if not self._state.results:
                    self.status = "No matching passages. Press / to search again."

        @bindings.add("up", filter=result_focus)
        @bindings.add("k", filter=result_focus)
        def result_up(event):
            self._result_index = max(0, self._result_index - 1)

        @bindings.add("down", filter=result_focus)
        @bindings.add("j", filter=result_focus)
        def result_down(event):
            self._result_index = min(max(0, len(self._state.results) - 1), self._result_index + 1)

        @bindings.add("enter", filter=result_focus)
        def open_result(event):
            if self._act(lambda: self.actions.open_result(self._result_index + 1)):
                self._results_visible = False

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
                self._context_visible = False
                self._results_visible = False
                self._search_marks_visible = False
                event.app.layout.focus(self.body)

        @bindings.add("?", filter=~query_focus)
        def toggle_help(event):
            self._help_visible = not self._help_visible

        # Override shifted/unshifted arrows so selection is always a character
        # span, regardless of the toolkit's editable-buffer shift mode.
        for key, direction, vim in (("left", -1, "h"), ("right", 1, "l"), ("up", -1, "k"), ("down", 1, "j")):
            def cursor(event, key=key, direction=direction):
                self._move_cursor(key, direction)
            bindings.add(key, filter=body_focus)(cursor)
            bindings.add(vim, filter=body_focus)(cursor)

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
                "header": "", "document-context": "", "document-title": "bold",
                "document-pages": "fg:ansibrightblack", "context": "fg:ansibrightblack",
                "footer": "fg:ansibrightblack", "status": "fg:ansibrightblack",
                "warning": "bold",
                "results": "", "result.selected": "reverse", "selected-text": "reverse",
                "source.emphasis": self.emphasis, "source.strong": "bold",
                "source.code": "underline", "source.quotation": "",
                "source.search": "underline bg:ansiyellow fg:ansiblack",
                "source.heading": "bold",
            }),
        )
        self.application.key_processor.after_key_press += self._sync_selection
        self.application.after_render += self._sync_viewport
        self._project_body()

    def _move_cursor(self, key, direction):
        if key in {"left", "right"}:
            self._cursor_action(lambda: self.actions.move_horizontal(direction))
        else:
            self._move_vertical(direction)

    def _cursor_action(self, operation):
        before = self._state.current
        if self._act(operation, project=False):
            current = self._state.current
            if (None if before is None else before.identifier) != (
                    None if current is None else current.identifier):
                self._results_visible = False
                self._project_body()
                self.application.layout.focus(self.body)
                return
            self._projecting = True
            try:
                self.body.buffer.cursor_position = self._state.cursor_offset
            finally:
                self._projecting = False

    def _source_positions(self):
        """Use the SAME presentation plan as rendering for semantic movement."""
        buffer = self.body.buffer
        info = self.body.window.render_info
        width = max(1, info.window_width if info is not None else min(
            self.reading_width, self.application.output.get_size().columns))
        key = (buffer.text, width)
        if self._geometry_cache is not None and self._geometry_cache[0] == key:
            return self._geometry_cache[1]
        row, positions = 0, []
        for line in buffer.document.lines:
            plan = self._plan_line(line, width)
            positions.extend((row + y, x) for y, x in plan.positions)
            row += plan.row_count
        self._geometry_cache = key, tuple(positions)
        return self._geometry_cache[1]

    def _plan_line(self, source, width):
        from sol.terminal.reading_layout import line_layout
        key = (source, width)
        if key not in self._line_plans:
            if len(self._line_plans) >= 64:
                self._line_plans.clear()
            self._line_plans[key] = line_layout(source, width,
                display_character=_character_display, cell_width=self._toolkit["get_cwidth"])
        return self._line_plans[key]

    def _move_vertical(self, direction):
        """Read visual rows, continuing from edges with passage-bound offsets."""
        self._advance_reading(direction)

    def _advance_reading(self, rows):
        self._cursor_action(lambda: self.actions.advance_reading(
            rows, layout=self._source_positions(),
            selecting=self.body.buffer.selection_state is not None))

    def _project_body(self):
        current, selection = self._state.current, self._state.selection
        text = "" if current is None else current.text
        self._projecting = True
        from sol.reader.typography import map_typography
        record = self.actions.book.canonical_records.get(current.identifier) if current is not None else None
        self.typography = map_typography(record["markdown"], text) if record is not None else map_typography(text, text)
        try:
            cursor = self._state.cursor_offset
            self.body.buffer.set_document(self._toolkit["Document"](text, cursor), bypass_readonly=True)
            anchor = selection.start if selection is not None and cursor == selection.end else (
                selection.end if selection is not None else None)
            self.body.buffer.selection_state = (
                self._toolkit["SelectionState"](anchor,
                    self._toolkit["SelectionType"].CHARACTERS) if selection is not None else None)
            viewport = self._state.viewport_offset
            self.body.window.vertical_scroll = 0
            self.body.window.vertical_scroll_2 = 0
            if viewport is not None and text:
                line, _ = self.body.buffer.document.translate_index_to_position(viewport)
                self.body.window.vertical_scroll = line
                positions = self._source_positions()
                start = self.body.buffer.document.translate_row_col_to_index(line, 0)
                self.body.window.vertical_scroll_2 = max(0, positions[viewport][0] - positions[start][0])
        finally:
            self._projecting = False

    def _sync_selection(self, sender=None):
        if self._projecting or self._state.current is None:
            return
        if self.body.buffer.cursor_position != self._state.cursor_offset:
            if not self._act(lambda: self.actions.set_cursor(self.body.buffer.cursor_position), project=False):
                self._project_body()
                return
        ranges = list(self.body.buffer.document.selection_ranges())
        span = ranges[0] if ranges and ranges[0][0] != ranges[0][1] else None
        old = self._state.selection
        if span == (None if old is None else (old.start, old.end)):
            return
        operation = self.actions.clear_selection if span is None else lambda: self.actions.select_span(*span)
        if not self._act(operation, project=False):
            self._project_body()

    def _sync_viewport(self, sender=None):
        """Retain a source anchor for approximate scroll restoration on resize."""
        info = self.body.window.render_info
        if self._projecting or self._state.current is None or info is None:
            return
        location = info.visible_line_to_row_col.get(0)
        if location is None:
            return
        line_number, _ = location
        document = self.body.buffer.document
        if not 0 <= line_number < len(document.lines):
            return
        positions = self._source_positions()
        start = document.translate_row_col_to_index(line_number, 0)
        top_row = positions[start][0] + info.window.vertical_scroll_2
        offset = next((index for index in range(start, len(positions))
                       if positions[index][0] >= top_row), len(document.text))
        if self._state.viewport_offset != offset:
            try:
                self.actions.set_viewport(offset)
                self._state = self.actions.snapshot()
            except (ValueError, RuntimeError) as error:
                self.status = safe_reader_text(str(error))

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
            # Results remain semantic context, not permanent reading chrome.
            # Opening/returning to prose never resurrects a dismissed pane.
            self._results_visible = False
            self._project_body()
            self.application.layout.focus(self.body)
        return True

    def _header(self):
        passage = self._state.current
        if passage is None:
            return "SOL reader\nNo active passage.\n} begins reading; / searches."
        title = passage.heading or passage.node.title or self.actions.book.root.title
        path = "/" + "/".join(passage.path)
        printed = str(passage.printed_page)
        pdf = str(passage.pdf_page)
        if passage.end_printed_page != passage.printed_page:
            printed += f"-{passage.end_printed_page}"
        if passage.end_pdf_page != passage.pdf_page:
            pdf += f"-{passage.end_pdf_page}"
        workspace = self.actions.workspace_reader
        label = "temporary" if workspace is None else "workspace " + str(
            getattr(getattr(getattr(workspace, "store", None), "path", None), "stem", "active"))
        return ((safe_reader_text(title) + "\n" if self._focus_mode else "")
                + safe_reader_text(path)
                + f"\nPrinted {printed} | PDF {pdf} | " + safe_reader_text(label)
                + "\nScope: " + safe_reader_text(self._scope_label())
                + (" | " + safe_reader_text(self.typography.reason) if self.typography.degraded else "")
                + (" | " + safe_reader_text(self.actions.search_highlights().reason)
                   if self._search_degraded() else ""))

    def _scope_label(self):
        return "work" if not self._state.scope else "/" + "/".join(self._state.scope)

    def _document_heading(self):
        passage = self._state.current
        if passage is None:
            return [("class:document-title", "SOL reader\n"), ("class:document-pages", "No active passage; / searches")]
        title = passage.heading or passage.node.title or self.actions.book.root.title
        printed = str(passage.printed_page)
        if passage.end_printed_page != passage.printed_page:
            printed += f"–{passage.end_printed_page}"
        label = "Quotation · " if passage.kind == "quotation" or any(
            "quotation" in span.styles for span in self.typography.spans) else ""
        return [("class:document-title", safe_reader_text(title) + "\n"),
                ("class:document-pages", label + f"p. {printed}")]

    def _needs_review(self):
        return self._state.current is not None and self._state.current.needs_source_review

    def _search_spans(self):
        return self.actions.search_highlights().spans if self._search_marks_visible else ()

    def _search_degraded(self):
        return self._search_marks_visible and self.actions.search_highlights().degraded

    def _status_text(self):
        passage = self._state.current
        position = "No position"
        if passage is not None:
            matches = self.actions.book.selection(self._state.scope)
            index = next((i for i, item in enumerate(matches) if item.identifier == passage.identifier), 0)
            position = f"Passage {index + 1}/{len(matches)}"
        selected = 0 if self._state.selection is None else self._state.selection.end - self._state.selection.start
        selection = "" if not selected else f" | {selected} selected"
        warnings = (["[source review]"] if self._needs_review() else [])
        if self.typography.degraded:
            warnings.append("Typography fallback (c for context)")
        if self._search_degraded():
            warnings.append("Search highlight fallback (c for context)")
        if self.status:
            warnings.append(safe_reader_text(self.status))
        return " | ".join(warnings + [position + selection])

    def _status_height(self):
        width = max(1, self.application.output.get_size().columns)
        rows = (self._toolkit["get_cwidth"](self._status_text()) + width - 1) // width
        needed = min(3, max(1, rows))
        return self._toolkit["Dimension"](min=1, max=needed, preferred=needed)

    def _reading_gaps(self):
        """Quiet top/lead space, relinquished before reading room gets cramped."""
        rows = self.application.output.get_size().rows
        desired = min(3, max(0, (rows - 12) // 6))
        chrome = 0 if self._focus_mode else 3  # Two heading rows and footer.
        if (not self._focus_mode or self.status or self._needs_review() or self.typography.degraded
                or self._search_degraded()):
            chrome += self._status_height().preferred
        # Context may grow beyond its preferred height for long source paths.
        chrome += (6 if self._context_visible else 0) + (5 if self._help_visible else 0)
        chrome += int(self._searching)
        if self._results_visible:
            chrome += min(6, len(self._state.results) + 1)
        budget = max(0, rows - chrome - 8)
        lead = int(not self._focus_mode and desired > 0 and budget > desired)
        return min(desired, max(0, budget - lead)), lead

    def _gap_height(self, index):
        gap = self._reading_gaps()[index]
        return self._toolkit["Dimension"](min=0, max=gap, preferred=gap)

    def _footer_text(self):
        columns = self.application.output.get_size().columns
        if columns < 28:
            return "j/k b/n / ? help"
        if columns < 60:
            return "j/k  b/n  / search  ? help"
        return "j/k read  b/n passages  / search  v select  c context  ? help"

    def _save_position(self):
        self._exit_notice = self.actions.save_position() or ""

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
        status = 0
        try:
            status = int(self.application.run() or 0)
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            if not self._saved_on_exit:
                try:
                    self._save_position()
                except (ValueError, RuntimeError, OSError) as error:
                    self._exit_notice = "Reading cursor not saved: " + str(error)
                    status = 1
            if self._exit_notice:
                print("sol: " + safe_reader_text(self._exit_notice), file=sys.stderr)
        return status


def run_reader(book, workspace_reader=None, *, width=DEFAULT_READER_WIDTH, emphasis="auto") -> int:
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
    view = ReaderView(actions, **({"width": width, "emphasis": emphasis}
                                 if width != DEFAULT_READER_WIDTH or emphasis != "auto" else {}))
    view.status = message
    return view.run()
