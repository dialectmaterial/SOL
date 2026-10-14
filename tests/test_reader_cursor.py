"""Semantic source offsets survive wrapping, histories, and guarded visits."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import asyncio
import importlib.util
import unittest
from unittest.mock import patch

from sol.reader.actions import ReaderActions, ReadingSession
from sol.reader.navigation import character_cells, source_layout, validate_layout, vertical_offset
from test_reader_actions import IDS, RETIRED, invented_book


class InjectedWorkspace:
    def __init__(self, book):
        self.book = book
        self.resumed_reference = None
        self.checkpoints = []
        self.saved = []

    def checkpoint(self, session, cwd, previous):
        self.checkpoints.append((session.current().identifier, session.cursor_offset,
                                 session.viewport_offset, cwd, previous))

    def save_position(self, session, cwd, previous):
        self.saved.append((session.current().identifier, session.cursor_offset))
        return ""


class ReaderCursorTests(unittest.TestCase):
    def setUp(self):
        self.book = invented_book()
        self.actions = ReaderActions(self.book)

    def replace_text(self, text):
        self.book.passages[0] = replace(self.book.passages[0], text=text)
        self.book.canonical_records[IDS[0]].update(
            plain_text=text, markdown=text, content_sha256=sha256(text.encode()).hexdigest())

    def test_cursor_is_a_canonical_unicode_insertion_boundary(self):
        text = 'α😀 e\u0301\nA line.'
        self.replace_text(text)
        self.actions.open(IDS[0])
        for offset in range(len(text) + 1):
            self.assertEqual(self.actions.set_cursor(offset), offset)
            self.assertEqual(self.actions.snapshot().cursor_offset, offset)
        self.assertEqual(self.actions.move_horizontal(100), len(text))
        self.assertEqual(self.actions.move_horizontal(-100), 0)
        self.assertEqual(self.actions.move_horizontal(2), 2)
        self.assertEqual(text[self.actions.cursor_offset:], ' e\u0301\nA line.')

    def test_invalid_cursor_and_viewport_leave_all_context_unchanged(self):
        self.actions.open(IDS[0])
        self.actions.set_cursor(6)
        self.actions.set_viewport(2)
        previous = self.actions.snapshot(), self.actions._trail
        for offset in (-1, len(self.book.passages[0].text) + 1, True, 0.5, '0', None):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.actions.set_cursor(offset)
            self.assertEqual((self.actions.snapshot(), self.actions._trail), previous)
        for offset in (-1, 1000, True, 0.5, '0'):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.actions.set_viewport(offset)
            self.assertEqual((self.actions.snapshot(), self.actions._trail), previous)
        for delta in (False, 1.5, '1'):
            with self.assertRaises(ValueError):
                self.actions.move_horizontal(delta)

    def test_empty_reader_does_not_claim_a_text_cursor(self):
        self.assertEqual(self.actions.snapshot().cursor_offset, 0)
        for operation in (lambda: self.actions.set_cursor(0), lambda: self.actions.move_up(80),
                          lambda: self.actions.set_viewport(0)):
            with self.assertRaises(ValueError):
                operation()
        self.assertIsNone(self.actions.save_position())

    def test_resize_changes_projection_not_semantic_cursor_or_selection(self):
        self.actions.open(IDS[0])
        self.actions.set_cursor(10)
        selected = self.actions.select_span(2, 10)
        before = self.actions.snapshot()
        wide = source_layout(before.current.text, 80)
        narrow = source_layout(before.current.text, 10)
        self.assertNotEqual(wide[10], narrow[10])
        self.assertEqual(self.actions.snapshot(), before)
        self.assertEqual(self.actions.selection, selected)

    def test_vertical_navigation_uses_supplied_display_cells_not_string_columns(self):
        self.replace_text('A界Bxyz')
        self.actions.open(IDS[0])
        layout = ((0, 0), (0, 1), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3))
        self.actions.set_cursor(2)
        self.assertEqual(self.actions.move_down(layout=layout), 6)
        self.assertEqual(self.actions.move_up(layout=layout), 2)
        self.assertEqual(self.actions.move_up(layout=layout), 2)
        self.assertEqual(self.actions.move_down(layout=layout), 6)

    def test_vertical_preferred_column_survives_shorter_row(self):
        self.replace_text('abcdefghijkl')
        self.actions.open(IDS[0])
        layout = ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
                  (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2), (2, 3), (2, 4))
        self.actions.set_cursor(4)
        self.assertEqual(self.actions.move_down(layout=layout), 7)
        self.assertEqual(self.actions.move_down(layout=layout), 12)
        self.assertEqual(self.actions.move_up(layout=layout), 7)
        self.assertEqual(self.actions.move_up(layout=layout), 4)
        self.actions.move_horizontal(-1)
        self.assertEqual(self.actions.move_down(layout=layout), 7)
        self.assertEqual(self.actions.move_down(layout=layout), 11)

    def test_visual_selection_does_not_discard_vertical_preferred_column(self):
        self.replace_text('abcdefghijkl')
        self.actions.open(IDS[0])
        layout = ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
                  (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2), (2, 3), (2, 4))
        self.actions.set_cursor(4)
        self.assertEqual(self.actions.move_down(layout=layout), 7)
        self.actions.select_span(4, 7)
        self.assertEqual(self.actions.move_down(layout=layout), 12)
        self.actions.select_span(4, 12)
        self.assertEqual(self.actions.move_up(layout=layout), 7)
        self.actions.select_span(4, 7)
        self.assertEqual(self.actions.move_up(layout=layout), 4)

    def test_half_page_moves_wrapped_rows_without_changing_paragraph(self):
        self.replace_text('x' * 100)
        self.actions.open(IDS[0])
        self.actions.set_cursor(3)
        self.assertEqual(self.actions.half_page(1, 10, 10), 53)
        self.assertEqual(self.actions.half_page(-1, 10, 10), 3)
        self.assertEqual(self.actions.snapshot().current.identifier, IDS[0])
        for direction, rows in ((0, 10), (True, 10), (1, 0), (1, True), (1, 1.5)):
            with self.subTest(direction=direction, rows=rows), self.assertRaises(ValueError):
                self.actions.half_page(direction, rows, 10)

    def test_bad_geometry_is_rejected_before_any_cursor_changes(self):
        self.actions.open(IDS[0])
        before = self.actions.snapshot(), self.actions._trail
        for layout in ((), ((0, 0),), None, [False], [(0, -1)] * (len(before[0].current.text) + 1)):
            with self.subTest(layout=layout), self.assertRaises(ValueError):
                self.actions.move_down(layout=layout)
            self.assertEqual((self.actions.snapshot(), self.actions._trail), before)

    def test_transient_navigation_reads_no_source_and_creates_no_checkpoints(self):
        workspace = InjectedWorkspace(self.book)
        actions = ReaderActions(self.book, workspace)
        actions.read(first=True)
        checkpoints, trail = list(workspace.checkpoints), len(actions._trail)
        with patch('builtins.open', side_effect=AssertionError('No source-file I/O')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('No source-file I/O')), \
                patch.object(workspace, 'checkpoint', side_effect=AssertionError('No visit')):
            actions.set_cursor(5)
            actions.move_horizontal(1)
            actions.move_down(20)
            actions.move_up(20)
            actions.half_page(1, 4, 20)
            actions.jump('passage-start')
            actions.set_viewport(0)
        self.assertEqual(workspace.checkpoints, checkpoints)
        self.assertEqual(len(actions._trail), trail)
        actions.set_cursor(10)
        self.assertEqual(actions.save_position(), '')
        self.assertEqual(workspace.saved, [(IDS[0], 10)])

    def test_legacy_injected_workspace_remains_supported(self):
        workspace = InjectedWorkspace(self.book)
        workspace.save_position = None
        actions = ReaderActions(self.book, workspace)
        actions.read(first=True)
        actions.set_cursor(7)
        self.assertIsNone(actions.save_position())
        self.assertEqual(len(workspace.checkpoints), 1)

    def test_history_restores_offset_viewport_and_backward_selection_direction(self):
        self.actions.open(IDS[0])
        selected = self.actions.select_span(2, 15)
        self.actions.set_cursor(2)
        self.actions.set_viewport(1)
        self.actions.open(IDS[1])
        self.assertEqual(self.actions.cursor_offset, 0)
        self.assertIsNone(self.actions.snapshot().viewport_offset)
        self.actions.set_cursor(9)
        self.actions.history_back()
        self.assertEqual(self.actions.cursor_offset, selected.start)
        self.assertEqual(self.actions.snapshot().viewport_offset, 1)
        self.assertEqual(self.actions.selection, selected)
        self.actions.history_forward()
        self.assertEqual(self.actions.cursor_offset, 9)
        self.assertIsNone(self.actions.selection)

    def test_programmatic_selection_sets_active_end_but_keeps_explicit_direction(self):
        self.actions.open(IDS[0])
        self.actions.select_span(2, 15)
        self.assertEqual(self.actions.cursor_offset, 15)
        self.actions.set_cursor(2)
        self.actions.select_span(2, 15)
        self.assertEqual(self.actions.cursor_offset, 2)
        self.actions.set_cursor(20)
        self.actions.select_span(2, 15)
        self.assertEqual(self.actions.cursor_offset, 15)

    def test_alias_visit_preserves_canonical_offset(self):
        self.book.canonical_records[RETIRED] = {
            'id': RETIRED, 'type': 'retired_record', 'redirect_id': IDS[0]}
        self.actions.open(IDS[0])
        self.actions.set_cursor(12)
        self.actions.open(RETIRED)
        self.assertEqual(self.actions.cursor_offset, 12)
        self.assertEqual(self.actions.snapshot().requested_id, RETIRED)
        self.actions.set_cursor(3)
        self.actions.history_back()
        self.assertEqual(self.actions.cursor_offset, 12)
        self.assertEqual(self.actions.snapshot().requested_id, IDS[0])

    def test_failed_guarded_navigation_rolls_back_cursor_viewport_and_trail(self):
        workspace = InjectedWorkspace(self.book)
        actions = ReaderActions(self.book, workspace)
        actions.read(first=True)
        actions.select_span(2, 12)
        actions.set_cursor(2)
        actions.set_viewport(1)
        before = actions.snapshot(), actions._trail, actions._preferred_column
        with patch.object(workspace, 'checkpoint', side_effect=RuntimeError('CAS conflict')):
            for operation in (lambda: actions.move_paragraph(1), lambda: actions.jump('scope-end')):
                with self.assertRaisesRegex(RuntimeError, 'CAS conflict'):
                    operation()
                self.assertEqual((actions.snapshot(), actions._trail, actions._preferred_column), before)

    def test_paragraph_motion_and_scope_jumps_are_semantic_visits(self):
        self.actions.read(('BEING',), first=True)
        self.actions.set_cursor(8)
        self.assertEqual(self.actions.move_paragraph(1).identifier, IDS[1])
        self.assertEqual(self.actions.cursor_offset, 0)
        self.actions.set_cursor(7)
        self.assertEqual(self.actions.move_paragraph(-1).identifier, IDS[0])
        self.assertEqual(self.actions.cursor_offset, 0)
        self.assertEqual(self.actions.jump('scope-end').identifier, IDS[1])
        self.assertEqual(self.actions.cursor_offset, len(self.book.passages[1].text))
        self.assertEqual(self.actions.session.path, ('BEING',))
        self.assertEqual(self.actions.jump('scope-start').identifier, IDS[0])
        self.assertEqual(self.actions.cursor_offset, 0)
        self.actions.jump('passage-end')
        self.assertEqual(self.actions.cursor_offset, len(self.book.passages[0].text))
        self.actions.jump('passage-start')
        self.assertEqual(self.actions.cursor_offset, 0)

    def test_same_passage_scope_jump_amends_history_with_new_source_offset(self):
        self.actions.open(IDS[0])
        self.actions.jump('scope-start')
        self.actions.open(IDS[1])
        self.actions.jump('scope-end')
        offset = self.actions.cursor_offset
        self.actions.history_back()
        self.assertEqual(self.actions.cursor_offset, 0)
        self.actions.history_forward()
        self.assertEqual(self.actions.cursor_offset, offset)

    def test_search_navigation_wraps_latest_results_in_both_directions(self):
        self.actions.read((), first=True)
        self.actions.search('invented', ())
        for identifier in (IDS[1], IDS[2], IDS[0]):
            self.assertEqual(self.actions.search_next().identifier, identifier)
            self.assertEqual(self.actions.cursor_offset, self.actions.snapshot().current.text.index('invented'))
        self.assertEqual(self.actions.search_next(reverse=True).identifier, IDS[2])
        self.assertEqual(self.actions.session.path, ())
        self.actions.search('absent word', ())
        previous = self.actions.snapshot()
        with self.assertRaisesRegex(ValueError, 'no search results'):
            self.actions.search_next()
        self.assertEqual(self.actions.snapshot(), previous)

    def test_snapshot_detects_corrupt_source_offsets(self):
        self.actions.open(IDS[0])
        for value in (-1, len(self.book.passages[0].text) + 1, True):
            self.actions.session.cursor_offset = value
            with self.assertRaisesRegex(ValueError, 'outside its source text'):
                self.actions.snapshot()
        self.actions.session.cursor_offset = 0
        self.actions.session.viewport_offset = 1000
        with self.assertRaisesRegex(ValueError, 'viewport anchor'):
            self.actions.snapshot()


class SourceLayoutTests(unittest.TestCase):
    def test_layout_covers_all_source_boundaries_not_display_characters(self):
        text = 'A界e\u0301\x1b\u202eZ'
        positions = source_layout(text, 20)
        self.assertEqual(len(positions), len(text) + 1)
        self.assertEqual(positions[:5], ((0, 0), (0, 1), (0, 3), (0, 4), (0, 4)))
        self.assertEqual(positions[5], (0, 8))
        self.assertEqual(positions[6], (0, 14))
        self.assertEqual(validate_layout(positions, len(text)), positions)

    def test_wide_characters_do_not_start_in_last_single_cell(self):
        self.assertEqual(source_layout('ab界Z', 3), ((0, 0), (0, 1), (1, 0), (1, 2), (1, 3)))

    def test_newlines_after_full_row_do_not_add_an_extra_wrapped_row(self):
        self.assertEqual(source_layout('abc\nx', 3), ((0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1)))

    def test_custom_cell_widths_use_source_offsets_and_no_optional_library(self):
        self.assertEqual(source_layout('ABC', 10, cell_width=lambda char: 3),
                         ((0, 0), (0, 3), (0, 6), (0, 9)))
        for width in (0, -1, True, 1.5, None):
            with self.subTest(width=width), self.assertRaises(ValueError):
                source_layout('A', width)
        with self.assertRaises(ValueError):
            source_layout('A', 10, cell_width=lambda char: -1)

    def test_escaped_source_character_can_cross_multiple_visual_rows(self):
        positions = source_layout('\u202eX', 2)
        self.assertEqual(len(positions), 3)
        offset, preferred = vertical_offset(positions, 0, 1)
        self.assertEqual(offset, 1)
        self.assertEqual(preferred, 0)
        self.assertEqual(vertical_offset(positions, offset, -1)[0], 0)

    def test_character_width_includes_unicode_combining_and_safety_escapes(self):
        for character, cells in (('界', 2), ('\u0301', 0), ('A', 1), ('\t', 2),
                                 ('\x1b', 4), ('\u202e', 6), ('\U000e0001', 10)):
            self.assertEqual(character_cells(character), cells)

    def test_invalid_renderer_coordinates_are_not_trusted(self):
        for layout in (((0, 0), (-1, 0)), ((1, 0), (0, 2)), ((0, 2), (0, 1)),
                       ((0, 0), (0, True)), ((0, 0), (0, 1, 2)), (False,)):
            with self.subTest(layout=layout), self.assertRaises(ValueError):
                validate_layout(layout, 1)


@unittest.skipUnless(importlib.util.find_spec('prompt_toolkit') is not None
                     and importlib.util.find_spec('markdown_it') is not None,
                     'optional reader dependencies are absent')
class ToolkitSourceGeometryTests(unittest.IsolatedAsyncioTestCase):
    async def assert_live_geometry(self, text):
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        from sol.terminal.reader import ReaderView, _character_display
        book = invented_book()
        book.passages[0] = replace(book.passages[0], text=text)
        book.canonical_records[IDS[0]].update(
            plain_text=text, markdown=text, content_sha256=sha256(text.encode()).hexdigest())
        actions = ReaderActions(book)
        actions.read(first=True)
        with create_pipe_input() as pipe:
            view = ReaderView(actions, input=pipe, output=DummyOutput(), width=20)
            task = asyncio.create_task(view.application.run_async())
            try:
                for _ in range(200):
                    if view.body.window.render_info is not None:
                        break
                    await asyncio.sleep(0.005)
                info = view.body.window.render_info
                self.assertIsNotNone(info)
                positions = view._source_positions()
                self.assertEqual(len(positions), len(text) + 1)
                offset = 0
                for line_number, line in enumerate(view.body.buffer.document.lines):
                    display_column = 0
                    for source_column in range(len(line) + 1):
                        coordinate = info._rowcol_to_yx.get((line_number, display_column))
                        if coordinate is not None:
                            row, column = coordinate
                            self.assertEqual(positions[offset],
                                             (row - info._y_offset, column - info._x_offset),
                                             (text, offset, positions))
                        offset += 1
                        if source_column < len(line):
                            display_column += len(_character_display(line[source_column]))
                return positions
            finally:
                pipe.send_text('\x03')
                await asyncio.wait_for(task, 2)

    async def test_wide_character_boundary_is_after_actual_pre_wrap(self):
        positions = await self.assert_live_geometry('a' * 19 + '界Z')
        self.assertEqual(positions[19], (1, 0))
        self.assertEqual(positions[20], (1, 2))

    async def test_exact_width_newline_includes_toolkit_cursor_space(self):
        positions = await self.assert_live_geometry('a' * 20 + '\nx')
        self.assertEqual(positions[20], (1, 0))
        self.assertEqual(positions[21], (2, 0))

    async def test_combining_and_escaped_source_coordinates_match_live_renderer(self):
        for text in ('a' * 19 + 'e\u0301Z', 'a' * 18 + '\x1bZ', 'a' * 18 + '\u202e界'):
            with self.subTest(text=text):
                await self.assert_live_geometry(text)


if __name__ == '__main__':
    unittest.main()
