"""Isolated continuous proof keeps record identity beneath disposable rows."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from hashlib import sha256
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace
import unittest

from experiments.reader_surfaces.tui import ContinuousProjection, ContinuousView, SourceLocation
from sol.reader.actions import ReaderActions
from test_reader_view import IDS, reader_book


OPTIONAL = bool(importlib.util.find_spec("prompt_toolkit") and
                importlib.util.find_spec("markdown_it"))


def sample_book():
    book = reader_book()
    texts = (
        "Thought remains in its own source paragraph. Determination is not a screen coordinate.",
        "The Idea is not reducible to a classification. A second paragraph remains distinct.",
        "Unicode λογος e\u0301 漢字 keeps every source codepoint.\nAnd a real newline remains real.",
    )
    for index, text in enumerate(texts):
        markdown = text.replace("Thought", "*Thought*").replace("Idea", "**Idea**")
        book.passages[index] = replace(book.passages[index], text=text)
        book.canonical_records[IDS[index]].update(
            plain_text=text, markdown=markdown,
            content_sha256=sha256(markdown.encode()).hexdigest())
    return book


def sample():
    book = sample_book()
    actions = ReaderActions(book)
    actions.open(IDS[0])
    return SimpleNamespace(book=book, actions=actions, passages=tuple(book.passages))


class ContinuousProjectionTests(unittest.TestCase):
    def setUp(self):
        self.book = sample_book()

    def project(self, width=30):
        return ContinuousProjection(self.book.passages, width,
                                    records=self.book.canonical_records)

    def test_import_needs_no_optional_terminal_or_browser_dependency(self):
        result = subprocess.run([sys.executable, "-B", "-c", """
import sys
import experiments.reader_surfaces.tui
assert not any(name == 'prompt_toolkit' or name.startswith('prompt_toolkit.') for name in sys.modules)
assert not any(name == 'markdown_it' or name.startswith('markdown_it.') for name in sys.modules)
"""], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_boundary_has_existing_id_and_exact_codepoint(self):
        projected = self.project()
        for passage in self.book.passages:
            self.assertEqual(len(projected.positions[passage.identifier]), len(passage.text) + 1)
            for offset in range(len(passage.text) + 1):
                location = SourceLocation(passage.identifier, offset)
                row, column = projected.position(location)
                self.assertIn((column, location), projected.row_sources[row])
        self.assertEqual(set(projected.positions), set(IDS))

    def test_records_stay_separate_and_adjacent_with_neutral_separator(self):
        projected = self.project()
        first_end = projected.position(SourceLocation(IDS[0], len(self.book.passages[0].text)))[0]
        second_start = projected.position(SourceLocation(IDS[1], 0))[0]
        self.assertGreaterEqual(second_start, first_end + 2)
        self.assertEqual(projected.rows[first_end + 1], ())
        self.assertEqual(projected.row_sources[first_end + 1], ())
        self.assertEqual(self.book.passages[0].text, sample_book().passages[0].text)

    def test_section_changes_are_labeled_once_without_repeating_the_first_header(self):
        self.book.passages[1] = replace(self.book.passages[1], heading="Ground and existence")
        self.book.passages[2] = replace(self.book.passages[2], heading="Ground and existence")
        projected = self.project(30)
        labels = "".join(glyph.text for row in projected.rows for glyph in row
                         if glyph.style == "class:section-heading")
        self.assertEqual(labels, "Ground and existence")
        first_end = projected.position(SourceLocation(IDS[0], len(self.book.passages[0].text)))[0]
        second_start = projected.position(SourceLocation(IDS[1], 0))[0]
        self.assertEqual(projected.rows[first_end + 1], ())
        self.assertEqual("".join(g.text for g in projected.rows[first_end + 2]),
                         "Ground and existence")
        self.assertEqual(second_start, first_end + 3)

    def test_node_title_fallback_and_returning_sections_have_their_own_labels(self):
        from sol.core.models import Node
        node = Node("ground.txt", "Ground", 1)
        self.book.passages[1] = replace(self.book.passages[1], heading="", node=node)
        projected = self.project()
        labels = ["".join(g.text for g in row if g.style == "class:section-heading")
                  for row in projected.rows]
        self.assertEqual([label for label in labels if label], ["Ground", "Quality"])

    def test_section_labels_and_review_warnings_remain_neutral_and_motion_skips_them(self):
        self.book.passages[1] = replace(self.book.passages[1], heading="Ground",
                                        transcription_status="needs_review")
        projected = self.project(20)
        second_start = projected.position(SourceLocation(IDS[1], 0))[0]
        heading_row = next(index for index, row in enumerate(projected.rows)
                           if any(g.style == "class:section-heading" for g in row))
        warning_row = next(index for index, row in enumerate(projected.rows)
                           if any(g.style == "class:warning" for g in row))
        self.assertLess(heading_row, warning_row)
        self.assertLess(warning_row, second_start)
        for index in range(heading_row, second_start):
            self.assertFalse(projected.row_sources[index])
            self.assertTrue(all(g.source is None for g in projected.rows[index]))
        selected = SimpleNamespace(target_id=IDS[1], start=0, end=len(self.book.passages[1].text))
        self.assertTrue(all("section-heading" not in style and "warning" not in style
                            for style, _ in projected.fragments(selected)
                            if "selected-text" in style))
        first_end = SourceLocation(IDS[0], len(self.book.passages[0].text))
        self.assertEqual(projected.vertical(first_end, 1, 0)[0], SourceLocation(IDS[1], 0))
        preceding, _ = projected.vertical(SourceLocation(IDS[1], 0), -1, 0)
        self.assertEqual(preceding.target_id, IDS[0])
        self.assertEqual(projected.position(preceding)[0], projected.position(first_end)[0])

    def test_section_label_words_reflow_without_changing_any_source_boundary(self):
        heading = "The essential determination of reflection"
        self.book.passages[1] = replace(self.book.passages[1], heading=heading)
        for width in (10, 20, 72):
            with self.subTest(width=width):
                projected = self.project(width)
                label_rows = ["".join(g.text for g in row).strip() for row in projected.rows
                              if any(g.style == "class:section-heading" for g in row)]
                # The third record returns to Quality; check only this heading.
                label_rows = label_rows[:label_rows.index("Quality")]
                self.assertEqual("".join("".join(label_rows).split()), "".join(heading.split()))
                for word in heading.split():
                    if len(word) <= width:
                        self.assertTrue(any(word in row for row in label_rows), word)
                for passage in self.book.passages:
                    self.assertEqual(len(projected.positions[passage.identifier]), len(passage.text) + 1)
                    for offset in range(len(passage.text) + 1):
                        location = SourceLocation(passage.identifier, offset)
                        row, column = projected.position(location)
                        self.assertIn((column, location), projected.row_sources[row])

    def test_section_metadata_controls_are_escaped_before_layout(self):
        self.book.passages[1] = replace(self.book.passages[1], heading="Ground\x1b[31m\u202e\n")
        projected = self.project(30)
        label = "".join(g.text for row in projected.rows for g in row
                        if g.style == "class:section-heading")
        self.assertNotIn("\x1b", label)
        self.assertNotIn("\u202e", label)
        self.assertIn("\\x1b", label)
        self.assertIn("\\u202e", label)

    def test_full_width_section_label_has_no_extra_end_cursor_row(self):
        self.book.passages[1] = replace(self.book.passages[1], heading="A" * 20)
        projected = self.project(20)
        heading_row = next(index for index, row in enumerate(projected.rows)
                           if any(g.style == "class:section-heading" for g in row))
        self.assertEqual("".join(g.text for g in projected.rows[heading_row]), "A" * 20)
        self.assertEqual(projected.position(SourceLocation(IDS[1], 0))[0], heading_row + 1)

    def test_words_never_split_when_they_fit_the_available_measure(self):
        for width in (8, 20, 30, 72):
            projected = self.project(width)
            for passage in self.book.passages[:2]:
                positions = projected.positions[passage.identifier]
                for match in re.finditer(r"\S+", passage.text):
                    if len(match.group()) <= width:
                        self.assertEqual(len({positions[i][0] for i in range(match.start(), match.end())}), 1)

    def test_resize_changes_only_visual_geometry(self):
        narrow, wide = self.project(20), self.project(72)
        location = SourceLocation(IDS[0], 50)
        self.assertNotEqual(narrow.position(location), wide.position(location))
        self.assertEqual(narrow.positions.keys(), wide.positions.keys())
        self.assertEqual(self.book.passages[0].text[13:40], sample_book().passages[0].text[13:40])

    def test_vertical_motion_skips_non_source_separators_in_both_directions(self):
        projected = self.project()
        end = SourceLocation(IDS[0], len(self.book.passages[0].text))
        following, _ = projected.vertical(end, 1, 0)
        self.assertEqual(following, SourceLocation(IDS[1], 0))
        preceding, _ = projected.vertical(following, -1, 0)
        self.assertEqual(preceding.target_id, IDS[0])
        self.assertEqual(projected.position(preceding)[0], projected.position(end)[0])

    def test_unicode_combining_wide_and_newline_boundaries_remain_source_offsets(self):
        projected = self.project(20)
        text = self.book.passages[2].text
        for needle in ("λ", "\u0301", "漢", "\n"):
            offset = text.index(needle)
            location = SourceLocation(IDS[2], offset)
            row, col = projected.position(location)
            self.assertIn((col, location), projected.row_sources[row])
        newline = text.index("\n")
        self.assertGreater(projected.position(SourceLocation(IDS[2], newline + 1))[0],
                           projected.position(SourceLocation(IDS[2], newline))[0])

    def test_terminal_controls_are_visible_literals_not_escape_instructions(self):
        passage = replace(self.book.passages[0], text="one\x1b[31m\u202e two")
        projected = ContinuousProjection((passage,), 20)
        text = "".join(part for _, part in projected.fragments())
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\u202e", text)
        self.assertIn("\\x1b", text)
        self.assertIn("\\u202e", text)
        location = SourceLocation(IDS[0], 3)
        self.assertTrue(any(g.source == location for row in projected.rows for g in row))

    @unittest.skipUnless(importlib.util.find_spec("markdown_it"), "optional CommonMark parser absent")
    def test_semantic_styles_and_selection_share_source_offsets_not_padding(self):
        projected = self.project(20)
        selected = SimpleNamespace(target_id=IDS[0], start=0, end=7)
        fragments = projected.fragments(selected)
        styled = "".join(text for style, text in fragments if "source.emphasis" in style)
        self.assertEqual(styled, "Thought")
        selected_text = "".join(text for style, text in fragments if "selected-text" in style)
        self.assertEqual(selected_text, "Thought")
        self.assertTrue(any("source.strong" in g.style for row in projected.rows for g in row))
        for row in projected.rows:
            for glyph in row:
                if glyph.source is None:
                    self.assertIn(glyph.style, ("", "class:warning", "class:section-heading"))

    def test_inactive_review_warning_is_visible_and_has_no_source_coordinates(self):
        self.book.passages[1] = replace(self.book.passages[1], transcription_status="needs_review")
        projected = self.project()
        second_start = projected.position(SourceLocation(IDS[1], 0))[0]
        warning_rows = [index for index in range(second_start)
                        if any(glyph.style == "class:warning" for glyph in projected.rows[index])]
        warning_text = "".join(glyph.text for index in warning_rows for glyph in projected.rows[index])
        self.assertIn("[source review]", warning_text)
        for index in warning_rows:
            self.assertFalse(projected.row_sources[index])
            self.assertTrue(all(glyph.source is None for glyph in projected.rows[index]))
        first_end = SourceLocation(IDS[0], len(self.book.passages[0].text))
        self.assertEqual(projected.vertical(first_end, 1, 0)[0], SourceLocation(IDS[1], 0))
        for passage in self.book.passages:
            self.assertEqual(len(projected.positions[passage.identifier]), len(passage.text) + 1)

    def test_typography_fallback_label_is_neutral_not_selectable_source(self):
        from unittest.mock import patch
        from sol.reader.typography import Typography
        with patch("experiments.reader_surfaces.tui.map_typography", return_value=Typography(
                degraded=True, reason="Invented parser disagreement")):
            projected = self.project(20)
        label = "".join(glyph.text for row in projected.rows for glyph in row
                        if glyph.style == "class:warning")
        self.assertIn("[plain typography fallback]", label)
        self.assertTrue(all(glyph.source is None for row in projected.rows for glyph in row
                            if glyph.style == "class:warning"))

    def test_invalid_locations_width_and_duplicate_records_refused(self):
        for width in (0, -1, True, "30"):
            with self.assertRaises(ValueError):
                self.project(width)
        for passages in ((), (self.book.passages[0],) * 2):
            with self.assertRaises(ValueError):
                ContinuousProjection(passages, 20)
        projected = self.project()
        for location in (SourceLocation("missing", 0), SourceLocation(IDS[0], -1),
                         SourceLocation(IDS[0], True), SourceLocation(IDS[0], 10000)):
            with self.assertRaises(ValueError):
                projected.position(location)


@unittest.skipUnless(OPTIONAL, "optional continuous terminal dependencies absent")
class ContinuousViewTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, condition):
        deadline = asyncio.get_running_loop().time() + 2
        while not condition():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail("continuous proof did not reach expected state")
            await asyncio.sleep(.01)

    @asynccontextmanager
    async def view(self, selection=None):
        from prompt_toolkit.data_structures import Size
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput

        class ResizableOutput(DummyOutput):
            columns, rows = 100, 24
            def get_size(self):
                return Size(rows=self.rows, columns=self.columns)

        selection = selection or sample()
        output = ResizableOutput()
        with create_pipe_input() as pipe:
            view = ContinuousView(selection, input=pipe, output=output, width=40)
            view.application.ttimeoutlen = .01
            view.application.timeoutlen = .03
            task = asyncio.create_task(view.application.run_async())
            await self.wait_for(lambda: view.body_window.render_info is not None)
            try:
                yield view, pipe, selection, output
            finally:
                if not task.done():
                    pipe.send_text("q")
                self.assertEqual(await asyncio.wait_for(task, 2), 0)

    async def test_adjacent_records_appear_in_one_continuous_body(self):
        async with self.view() as (view, pipe, selection, output):
            text = "".join(part for _, part in view._body_text())
            self.assertIn("Thought remains", text)
            self.assertIn("The Idea", text)
            self.assertIn("Unicode", text)
            self.assertEqual(view.body_window.render_info.window_width, 40)
            self.assertEqual(view.heading_window.render_info._x_offset,
                             view.body_window.render_info._x_offset)
            self.assertEqual(view.body_window.render_info._y_offset,
                             view.heading_window.render_info._y_offset + 3)

    async def test_j_k_cross_existing_record_boundaries_without_new_ids(self):
        async with self.view() as (view, pipe, selection, output):
            selection.actions.set_cursor(len(selection.passages[0].text))
            view.application.invalidate()
            pipe.send_text("j")
            await self.wait_for(lambda: view.location.target_id == IDS[1])
            pipe.send_text("k")
            await self.wait_for(lambda: view.location.target_id == IDS[0])
            self.assertEqual(set(view.projection().positions), set(IDS))

    async def test_visible_section_transition_keeps_source_cursor_motion_and_selection(self):
        selection = sample()
        selection.book.passages[1] = replace(selection.book.passages[1], heading="Ground and existence")
        selection.book.passages[2] = replace(selection.book.passages[2], heading="Ground and existence")
        selection.passages = tuple(selection.book.passages)
        async with self.view(selection) as (view, pipe, selection, output):
            self.assertIn("Ground and existence", "".join(part for _, part in view._body_text()))
            selection.actions.set_cursor(len(selection.passages[0].text))
            expected, _ = view.projection().vertical(view.location, 1)
            view.application.invalidate()
            pipe.send_text("j")
            await self.wait_for(lambda: view.location == expected)
            self.assertEqual(view.location.target_id, IDS[1])
            self.assertTrue("".join(part for _, part in view._heading()).startswith("Ground and existence"))
            selection.actions.set_cursor(0)
            pipe.send_text("vlllllll")
            await self.wait_for(lambda: selection.actions.selection is not None and
                                selection.actions.selection.end == 7)
            selected = selection.actions.selection
            self.assertEqual(selected.text, selection.passages[1].text[:7])
            self.assertTrue(all("section-heading" not in style for style, _ in view._body_text()
                                if "selected-text" in style))
            output.columns = 20
            view.application.invalidate()
            await self.wait_for(lambda: view.body_window.render_info.window_width == 20)
            self.assertEqual(selection.actions.selection, selected)
            self.assertEqual(view.location, SourceLocation(IDS[1], 7))
            pipe.send_text("\x1b")
            await self.wait_for(lambda: view.anchor is None)
            selection.actions.set_cursor(0)
            pipe.send_text("k")
            await self.wait_for(lambda: view.location.target_id == IDS[0])

    async def test_h_l_keep_unicode_codepoint_semantics(self):
        async with self.view() as (view, pipe, selection, output):
            view.move_passage(1)
            view.move_passage(1)
            index = selection.passages[2].text.index("\u0301")
            selection.actions.set_cursor(index)
            pipe.send_text("l")
            await self.wait_for(lambda: view.location.offset == index + 1)
            pipe.send_text("h")
            await self.wait_for(lambda: view.location.offset == index)

    async def test_selection_uses_existing_span_and_cross_record_is_refused(self):
        async with self.view() as (view, pipe, selection, output):
            pipe.send_text("vlllllll")
            await self.wait_for(lambda: selection.actions.selection is not None and
                                selection.actions.selection.end == 7)
            selected = selection.actions.selection
            self.assertEqual(selected.text, "Thought")
            self.assertEqual(selected.target_id, IDS[0])
            self.assertTrue(any("source.emphasis" in style and "selected-text" in style
                                for style, _ in view._body_text()))
            pipe.send_text("n")
            await self.wait_for(lambda: "Selection stops" in view.status)
            self.assertEqual(view.location.target_id, IDS[0])
            self.assertEqual(selection.actions.selection, selected)
            pipe.send_text("\x1bn")
            await self.wait_for(lambda: view.location.target_id == IDS[1])
            self.assertIsNone(selection.actions.selection)

    async def test_empty_visual_anchor_also_refuses_crossing(self):
        async with self.view() as (view, pipe, selection, output):
            selection.actions.set_cursor(len(selection.passages[0].text))
            pipe.send_text("vj")
            await self.wait_for(lambda: "Selection stops" in view.status)
            self.assertEqual(view.location.target_id, IDS[0])
            self.assertIsNone(selection.actions.selection)
            self.assertIsNotNone(view.anchor)

    async def test_resize_keeps_current_source_and_selection_exact(self):
        async with self.view() as (view, pipe, selection, output):
            pipe.send_text("v" + "l" * 35)
            await self.wait_for(lambda: view.location.offset == 35)
            old = view.projection().position(view.location)
            selected = selection.actions.selection
            output.columns = 20
            view.application.invalidate()
            await self.wait_for(lambda: view.body_window.render_info.window_width == 20)
            self.assertEqual(view.location, SourceLocation(IDS[0], 35))
            self.assertEqual(selection.actions.selection, selected)
            self.assertNotEqual(view.projection().position(view.location), old)
            output.columns = 100
            view.application.invalidate()
            await self.wait_for(lambda: view.body_window.render_info.window_width == 40)
            self.assertEqual(view.projection().position(view.location), old)

    async def test_half_screen_and_passage_navigation_have_bounded_scope(self):
        async with self.view() as (view, pipe, selection, output):
            pipe.send_text("\x04")
            await self.wait_for(lambda: view.location != SourceLocation(IDS[0], 0))
            pipe.send_text("\x15")
            await self.wait_for(lambda: view.location.target_id == IDS[0])
            selection.actions.open(IDS[0])
            selection.actions.set_cursor(0)
            pipe.send_text("b")
            await self.wait_for(lambda: "End of this bounded sample" in view.status)
            self.assertEqual(view.location, SourceLocation(IDS[0], 0))
            pipe.send_text("n")
            await self.wait_for(lambda: view.location == SourceLocation(IDS[1], 0))

    async def test_context_reveals_existing_identity_and_not_view_rows(self):
        async with self.view() as (view, pipe, selection, output):
            pipe.send_text("c")
            await self.wait_for(lambda: view.context_visible)
            heading = "".join(part for _, part in view._heading())
            self.assertIn(IDS[0], heading)
            self.assertIn("codepoint 0", heading)

    async def test_long_paragraph_scrolls_naturally_into_its_existing_neighbor(self):
        selection = sample()
        text = ("An adjacent *thought* retains its own canonical source. " * 80).strip()
        plain = text.replace("*", "")
        selection.book.passages[0] = replace(selection.book.passages[0], text=plain)
        selection.book.canonical_records[IDS[0]].update(
            plain_text=plain, markdown=text, content_sha256=sha256(text.encode()).hexdigest())
        selection.passages = tuple(selection.book.passages)
        async with self.view(selection) as (view, pipe, selection, output):
            selection.actions.set_cursor(len(plain))
            view.application.invalidate()
            await self.wait_for(lambda: view.body_window.vertical_scroll > 0)
            pipe.send_text("j")
            await self.wait_for(lambda: view.location.target_id == IDS[1])
            position = view.body_window.render_info.cursor_position
            self.assertGreaterEqual(position.y, 0)
            self.assertLess(position.y, view.body_window.render_info.window_height)
            pipe.send_text("k")
            await self.wait_for(lambda: view.location.target_id == IDS[0])
            self.assertEqual(selection.actions.snapshot().current.text, plain)

    async def test_source_review_is_not_hidden_by_secondary_metadata(self):
        selection = sample()
        selection.book.passages[0] = replace(selection.book.passages[0], transcription_status="needs_review")
        selection.passages = tuple(selection.book.passages)
        async with self.view(selection) as (view, pipe, selection, output):
            label = "".join(text for _, text in view._heading()).split("\n")[1]
            self.assertTrue(label.startswith("[source review]"))

    async def test_non_active_visible_record_shows_its_own_review_warning(self):
        selection = sample()
        selection.book.passages[1] = replace(selection.book.passages[1], transcription_status="needs_review")
        selection.passages = tuple(selection.book.passages)
        async with self.view(selection) as (view, pipe, selection, output):
            self.assertEqual(view.location.target_id, IDS[0])
            screen = view.application.renderer._last_screen
            text = "\n".join("".join(cell.char for _, cell in sorted(row.items()))
                             for _, row in sorted(screen.data_buffer.items()))
            self.assertIn("[source review]", text)
            self.assertIn("The Idea", text)
            self.assertNotIn("[source review]", "".join(t for _, t in view._heading()))

    def test_workspace_binding_is_refused_before_optional_view_creation(self):
        selection = sample()
        selection.actions.workspace_reader = object()
        with self.assertRaisesRegex(ValueError, "refuses personal workspace"):
            ContinuousView(selection)

