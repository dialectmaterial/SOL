"""Opt-in continuous terminal proof, not a replacement SOL reader.

Rows are a disposable presentation of separate canonical records. No combined
passage, new identifier, saved position, or personal workspace is created here.
The only semantic cursor/selection belongs to the supplied ReaderActions.
"""
from __future__ import annotations

from dataclasses import dataclass

from sol.reader.navigation import character_cells
from sol.reader.typography import map_typography
from experiments.reader_surfaces.baseline import (
    _character_display, _load_toolkit, emphasis_style, safe_reader_text,
)
from experiments.reader_surfaces.reading_layout import line_layout


@dataclass(frozen=True)
class SourceLocation:
    """Existing paragraph identity and canonical Unicode-codepoint boundary."""

    target_id: str
    offset: int


@dataclass(frozen=True)
class Glyph:
    style: str
    text: str
    source: SourceLocation | None = None


class ContinuousProjection:
    """Word-aware rows with a reversible, per-record source boundary map.

    The terminal's own cell-width function can be supplied by the view. Pure
    tests use the reader's standard Unicode width fallback. Section labels,
    warning labels, padding and blank separators have no source location and
    can never become selected text.
    """

    def __init__(self, passages, width, *, records=None, cell_width=character_cells):
        if type(width) is not int or width < 1:
            raise ValueError("continuous reading width must be a positive integer")
        self.passages = tuple(passages)
        if not self.passages or len({p.identifier for p in self.passages}) != len(self.passages):
            raise ValueError("continuous proof needs nonempty, distinct canonical records")
        if any(not isinstance(p.identifier, str) or not p.identifier for p in self.passages):
            raise ValueError("every continuous proof record needs its existing identifier")
        self.width = width
        self.positions = {}
        self.rows = []
        self.row_sources = []
        self.degraded = []
        records = records or {}

        previous_heading = None
        for index, passage in enumerate(self.passages):
            heading = passage.heading or passage.node.title
            # The first section is already named by the view's document header.
            # Later changes must remain visible beside their own prose, even
            # while a different record owns the semantic reading cursor.
            if index and heading != previous_heading:
                self._append_label(heading, "class:section-heading", cell_width)
            previous_heading = heading
            typography = map_typography(records.get(passage.identifier, {}).get("markdown"), passage.text)
            if typography.degraded:
                self.degraded.append((passage.identifier, typography.reason))
            warnings = []
            if passage.needs_source_review:
                warnings.append("[source review]")
            if typography.degraded:
                warnings.append("[plain typography fallback]")
            if warnings:
                # Visible neighboring prose must not acquire a false appearance
                # of source approval just because its cursor isn't active yet.
                # These neutral labels are presentation, never source offsets.
                self._append_label(" ".join(warnings), "class:warning", cell_width)
            source_positions = []
            source_offset = 0
            for line in passage.text.split("\n"):
                layout = line_layout(line, width, display_character=_character_display,
                                     cell_width=cell_width)
                start_row = len(self.rows)
                physical_rows = [[] for _ in range(layout.row_count)]
                row, column = 0, 0

                def emit(character, style="", source=None):
                    nonlocal row, column
                    cells = cell_width(character)
                    if column + cells > width:
                        row, column = row + 1, 0
                    physical_rows[row].append(Glyph(style, character, source))
                    column += cells

                for index, displayed in enumerate(layout.displayed):
                    absolute = source_offset + index
                    styles = {style for span in typography.spans
                              if span.start <= absolute < span.end for style in span.styles}
                    style = " ".join("class:source." + value for value in sorted(styles))
                    for _ in range(layout.padding[index]):
                        emit(" ")
                    source = SourceLocation(passage.identifier, absolute)
                    for character in displayed:
                        emit(character, style, source)
                self.rows.extend(tuple(value) for value in physical_rows)
                self.row_sources.extend([] for _ in physical_rows)
                # Includes the boundary before each real source newline. The
                # next line starts after it, so no boundary is dropped/created.
                for index, (line_row, col) in enumerate(layout.positions):
                    position = (start_row + line_row, col)
                    source_positions.append(position)
                    self.row_sources[position[0]].append(
                        (col, SourceLocation(passage.identifier, source_offset + index)))
                source_offset += len(line) + 1
            self.positions[passage.identifier] = tuple(source_positions)
            # A visual separator, not an extra canonical newline or paragraph.
            self.rows.append(())
            self.row_sources.append([])
        self.rows = tuple(self.rows)
        self.row_sources = tuple(tuple(row) for row in self.row_sources)
        self.degraded = tuple(self.degraded)

    def _append_label(self, text, style, cell_width):
        """Word-wrap safe presentation metadata, never source coordinates."""
        label = safe_reader_text(text)
        layout = line_layout(label, self.width, display_character=lambda value: value,
                             cell_width=cell_width)
        rows = [[] for _ in range(layout.row_count)]
        row, column = 0, 0

        def emit(character, character_style):
            nonlocal row, column
            cells = cell_width(character)
            if column + cells > self.width:
                row, column = row + 1, 0
            rows[row].append(Glyph(character_style, character))
            column += cells

        for index, displayed in enumerate(layout.displayed):
            for _ in range(layout.padding[index]):
                emit(" ", "")
            for character in displayed:
                emit(character, style)
        # Metadata has no end-insertion cursor; unlike canonical prose it does
        # not need the planner's extra cursor row after a full-width last line.
        while rows and not rows[-1]:
            rows.pop()
        self.rows.extend(tuple(value) for value in rows)
        self.row_sources.extend([] for _ in rows)

    def position(self, location):
        try:
            positions = self.positions[location.target_id]
            if type(location.offset) is not int or not 0 <= location.offset < len(positions):
                raise ValueError("continuous source boundary is outside its record")
            return positions[location.offset]
        except KeyError as error:
            raise ValueError("record is outside this continuous reading sample") from error

    def vertical(self, location, delta, preferred_column=None):
        """Choose an existing source boundary, skipping non-source separator rows."""
        if type(delta) is not int:
            raise ValueError("continuous row motion must be an integer")
        row, column = self.position(location)
        preferred = column if preferred_column is None else preferred_column
        if not delta:
            return location, preferred
        last = max(points[-1][0] for points in self.positions.values())
        target = max(0, min(last, row + delta))
        step = 1 if delta > 0 else -1
        while not self.row_sources[target] and 0 <= target + step <= last:
            target += step
        candidates = self.row_sources[target]
        if not candidates:
            return location, preferred
        _, selected = min(candidates, key=lambda item: (
            abs(item[0] - preferred), item[0] > preferred, -item[1].offset))
        return selected, preferred

    def fragments(self, selection=None):
        """Only presentation strings; neutral padding never acquires selection."""
        fragments = []
        for index, row in enumerate(self.rows):
            for glyph in row:
                style = glyph.style
                if (selection is not None and glyph.source is not None
                        and glyph.source.target_id == selection.target_id
                        and selection.start <= glyph.source.offset < selection.end):
                    style += " class:selected-text"
                fragments.append((style.strip(), glyph.text))
            if index + 1 < len(self.rows):
                fragments.append(("", "\n"))
        return fragments


class ContinuousView:
    """Small read-only proof using an in-memory, workspace-free ReaderActions."""

    def __init__(self, sample, *, input=None, output=None, width=72):
        if sample.actions.workspace_reader is not None:
            raise ValueError("continuous proof refuses personal workspace bindings")
        if type(width) is not int or not 20 <= width <= 240:
            raise ValueError("continuous proof width must be between 20 and 240 columns")
        self.sample, self.actions = sample, sample.actions
        self.passages = tuple(sample.passages)
        if not self.passages:
            raise ValueError("continuous proof needs at least one canonical record")
        if any(self.actions.book.find_passage(p.identifier) != p for p in self.passages):
            raise ValueError("continuous sample differs from its ReaderActions source")
        state = self.actions.snapshot()
        if state.current is None:
            self.actions.open(self.passages[0].identifier)
            state = self.actions.snapshot()
        if state.current.identifier not in {p.identifier for p in self.passages}:
            raise ValueError("current source is outside the continuous reading sample")
        self.reading_width = width
        self.status = "Experiment: no saved position or workspace writes."
        self.context_visible = False
        self.anchor = None
        if state.selection is not None:
            selected = state.selection
            other = selected.start if state.cursor_offset == selected.end else selected.end
            self.anchor = SourceLocation(selected.target_id, other)
        self.preferred_column = None
        self._cached_projection = None
        self.toolkit = toolkit = _load_toolkit()
        self.body = toolkit["FormattedTextControl"](
            self._body_text, focusable=True, get_cursor_position=self._cursor_point)
        self.body_window = toolkit["Window"](
            self.body, wrap_lines=False, always_hide_cursor=False)
        measure = toolkit["Dimension"](min=1, preferred=width, max=width)
        self.heading_window = toolkit["Window"](
            toolkit["FormattedTextControl"](self._heading), height=2, wrap_lines=False)
        self.body_gap = toolkit["Window"](
            height=lambda: 1 if self.application.output.get_size().rows >= 20 else 0)
        column = toolkit["HSplit"]([
            toolkit["Window"](height=lambda: 2 if self.application.output.get_size().rows >= 20 else 0),
            self.heading_window, self.body_gap, self.body_window,
        ], width=measure)
        root = toolkit["HSplit"]([
            toolkit["VSplit"]([column], align=toolkit["HorizontalAlign"].CENTER),
            toolkit["Window"](toolkit["FormattedTextControl"](lambda: safe_reader_text(self.status)),
                              height=1, wrap_lines=False, style="class:status"),
            toolkit["Window"](toolkit["FormattedTextControl"](
                "q: quit  j/k: rows  b/n: passages  v: select  Esc: clear  c: context  "
                "Ctrl-D/U: half screen  h/l: source characters"), height=1, wrap_lines=False,
                style="class:status"),
        ])
        keys = toolkit["KeyBindings"]()

        @keys.add("q")
        @keys.add("c-c")
        @keys.add("c-q")
        def quit_view(event):
            event.app.exit(result=0)

        @keys.add("j")
        @keys.add("down")
        def down(event):
            self.move_rows(1)

        @keys.add("k")
        @keys.add("up")
        def up(event):
            self.move_rows(-1)

        @keys.add("h")
        @keys.add("left")
        def left(event):
            self.move_characters(-1)

        @keys.add("l")
        @keys.add("right")
        def right(event):
            self.move_characters(1)

        @keys.add("c-d")
        @keys.add("c-u")
        def half_screen(event):
            info = self.body_window.render_info
            rows = max(1, (info.window_height if info else 10) // 2)
            self.move_rows(rows if event.key_sequence[-1].key == "c-d" else -rows)

        @keys.add("b")
        @keys.add("n")
        def passage(event):
            self.move_passage(-1 if event.key_sequence[-1].key == "b" else 1)

        @keys.add("v")
        def select(event):
            if self.anchor is None:
                self.anchor = self.location
                self.status = "Selection is source-bound and limited to one paragraph."
            else:
                self.clear_selection()

        @keys.add("escape", eager=True)
        def clear(event):
            self.clear_selection()

        @keys.add("c")
        def context(event):
            self.context_visible = not self.context_visible

        self.application = toolkit["Application"](
            layout=toolkit["Layout"](root, focused_element=self.body),
            key_bindings=keys, full_screen=True, input=input, output=output,
            style=toolkit["Style"].from_dict({
                "source.emphasis": emphasis_style(), "source.strong": "bold",
                "source.code": "underline", "source.quotation": emphasis_style(),
                "source.heading": "bold", "selected-text": "reverse",
                "status": "dim", "warning": "bold underline", "section-heading": "bold",
            }))

    @property
    def location(self):
        state = self.actions.snapshot()
        return SourceLocation(state.current.identifier, state.cursor_offset)

    def projection(self):
        width = min(self.reading_width, self.application.output.get_size().columns)
        width = max(1, width)
        if self._cached_projection is None or self._cached_projection.width != width:
            self._cached_projection = ContinuousProjection(
                self.passages, width, records=self.actions.book.canonical_records,
                cell_width=self.toolkit["get_cwidth"])
            self.preferred_column = None
        return self._cached_projection

    def _body_text(self):
        return self.projection().fragments(self.actions.selection)

    def _cursor_point(self):
        row, column = self.projection().position(self.location)
        return self.toolkit["Point"](x=column, y=row)

    def _heading(self):
        state = self.actions.snapshot()
        passage = state.current
        first = safe_reader_text(passage.heading or passage.node.title)
        if self.context_visible:
            second = f"{passage.identifier}  codepoint {state.cursor_offset}  /{'/'.join(passage.path)}"
        else:
            index = next(i for i, item in enumerate(self.passages) if item.identifier == passage.identifier)
            second = f"Printed {passage.printed_page} | PDF {passage.pdf_page}  ·  sample {index + 1}/{len(self.passages)}"
        warnings = []
        if passage.needs_source_review:
            warnings.append("[source review]")
        if any(item[0] == passage.identifier for item in self.projection().degraded):
            warnings.append("[plain typography fallback]")
        if warnings:
            second = " ".join(warnings) + "  " + second
        return [("bold", first), ("", "\n" + safe_reader_text(second))]

    def clear_selection(self):
        self.anchor = None
        self.actions.clear_selection()
        self.status = "Selection cleared."

    def _move_to(self, location):
        self.projection().position(location)
        if self.anchor is not None and self.anchor.target_id != location.target_id:
            self.status = "Selection stops at its paragraph; Esc clears it before crossing."
            return False
        if self.location.target_id != location.target_id:
            self.actions.open(location.target_id)
        self.actions.set_cursor(location.offset)
        if self.anchor is not None:
            start, end = sorted((self.anchor.offset, location.offset))
            if start != end:
                self.actions.select_span(start, end)
            else:
                self.actions.clear_selection()
        self.status = "Source selection: one paragraph only." if self.anchor is not None else ""
        return True

    def move_rows(self, delta):
        target, preferred = self.projection().vertical(self.location, delta, self.preferred_column)
        if self._move_to(target):
            self.preferred_column = preferred

    def move_characters(self, delta):
        if type(delta) is not int:
            raise ValueError("continuous character motion must be an integer")
        self.preferred_column = None
        passage = self.actions.snapshot().current
        offset = max(0, min(len(passage.text), self.location.offset + delta))
        return self._move_to(SourceLocation(passage.identifier, offset))

    def move_passage(self, delta):
        if type(delta) is not int or delta not in {-1, 1}:
            raise ValueError("continuous passage motion must be previous or next")
        self.preferred_column = None
        index = next(i for i, item in enumerate(self.passages) if item.identifier == self.location.target_id)
        target = index + delta
        if not 0 <= target < len(self.passages):
            self.status = "End of this bounded sample; no source was changed."
            return False
        return self._move_to(SourceLocation(self.passages[target].identifier, 0))

    def run(self):
        return self.application.run()


def run(sample, *, input=None, output=None, width=72):
    """Run explicitly from the source-tree experiment harness, never by default."""
    return ContinuousView(sample, input=input, output=output, width=width).run()
