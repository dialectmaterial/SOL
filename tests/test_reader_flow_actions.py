"""Bounded reading flow keeps passage identity and guarded visits explicit."""
from dataclasses import replace
from hashlib import sha256
import unittest
from unittest.mock import patch

from sol.reader.actions import ReaderActions
from sol.reader.navigation import source_layout
from sol.core.references import resolve_reference
from test_reader_actions import IDS, RETIRED, invented_book
from test_reader_cursor import InjectedWorkspace


class ReaderFlowActionsTests(unittest.TestCase):
    def setUp(self):
        self.book = invented_book()
        self.workspace = InjectedWorkspace(self.book)
        self.actions = ReaderActions(self.book, self.workspace)
        self.actions.read((), first=True)

    def replace_text(self, index, text):
        self.book.passages[index] = replace(self.book.passages[index], text=text)
        self.book.canonical_records[IDS[index]].update(
            plain_text=text, markdown=text,
            content_sha256=sha256(text.encode("utf-8")).hexdigest())

    def geometry(self, width=20):
        return source_layout(self.actions.snapshot().current.text, width)

    def outer_row_offset(self, direction, width=20):
        layout = self.geometry(width)
        row = layout[-1 if direction > 0 else 0][0]
        # Use an interior offset within the row when one exists: flow is
        # based on visual rows, not a requirement to reach len(text) or zero.
        offsets = [index for index, point in enumerate(layout) if point[0] == row]
        return offsets[min(1, len(offsets) - 1)]

    def local_state(self):
        return (self.actions.snapshot(), self.actions._trail,
                self.actions._history_index, self.actions._preferred_column,
                self.actions._preferred_layout, self.workspace.resumed_reference,
                tuple(self.workspace.checkpoints))

    def test_forward_outer_row_visits_next_passage_at_zero_in_one_checkpoint(self):
        self.replace_text(0, "abcdefghijklmno")
        layout = self.geometry(10)
        self.actions.set_cursor(11)
        self.actions.set_viewport(7)
        before = len(self.workspace.checkpoints)
        self.actions.advance_reading(1, layout=layout)
        state = self.actions.snapshot()
        self.assertEqual(state.current.identifier, IDS[1])
        self.assertEqual(state.cursor_offset, 0)
        self.assertIsNone(state.viewport_offset)
        self.assertEqual(state.scope, ())
        self.assertEqual(len(self.workspace.checkpoints), before + 1)
        self.assertEqual(self.workspace.checkpoints[-1], (IDS[1], 0, None, (), None))

    def test_backward_outer_row_visits_previous_tail_before_checkpoint(self):
        self.replace_text(0, "A long previous passage " * 80)
        self.actions.move_paragraph(1)
        self.actions.set_cursor(4)
        self.actions.set_viewport(2)
        previous_text = self.book.passages[0].text
        before = len(self.workspace.checkpoints)
        self.actions.advance_reading(-1, layout=self.geometry())
        state = self.actions.snapshot()
        self.assertEqual((state.current.identifier, state.cursor_offset),
                         (IDS[0], len(previous_text)))
        self.assertIsNone(state.viewport_offset)
        self.assertEqual(len(self.workspace.checkpoints), before + 1)
        self.assertEqual(self.workspace.checkpoints[-1],
                         (IDS[0], len(previous_text), None, (), None))

    def test_large_row_request_reaches_current_tail_before_crossing_one_passage(self):
        self.replace_text(0, "abcdefghij" * 20)
        layout = self.geometry(10)
        self.actions.set_cursor(21)
        before = len(self.workspace.checkpoints)
        self.actions.advance_reading(100, layout=layout)
        self.assertEqual(self.actions.snapshot().current.identifier, IDS[0])
        self.assertEqual(layout[self.actions.cursor_offset][0], layout[-1][0])
        self.assertEqual(len(self.workspace.checkpoints), before)
        self.actions.advance_reading(100, layout=layout)
        self.assertEqual(self.actions.snapshot().current.identifier, IDS[1])
        self.assertEqual(self.actions.cursor_offset, 0)
        self.assertEqual(len(self.workspace.checkpoints), before + 1)

    def test_in_passage_flow_uses_actual_supplied_geometry_and_creates_no_visit(self):
        self.replace_text(0, "A界Bxyz")
        layout = ((0, 0), (0, 1), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3))
        self.actions.set_cursor(2)
        before = len(self.workspace.checkpoints), len(self.actions._trail)
        self.actions.advance_reading(1, layout=layout)
        self.assertEqual(self.actions.cursor_offset, 6)
        self.actions.advance_reading(-1, layout=layout)
        self.assertEqual(self.actions.cursor_offset, 2)
        self.assertEqual((len(self.workspace.checkpoints), len(self.actions._trail)), before)

    def test_empty_visual_anchor_blocks_crossing_even_without_semantic_selection(self):
        self.actions.move_paragraph(1)
        self.actions.set_cursor(3)
        before = self.local_state()
        self.actions.advance_reading(-1, layout=self.geometry(), selecting=True)
        self.assertEqual(self.actions.snapshot().current.identifier, IDS[1])
        self.assertEqual(self.actions.cursor_offset, 3)
        self.assertIsNone(self.actions.selection)
        self.assertEqual(tuple(self.workspace.checkpoints), before[-1])

    def test_semantic_selection_blocks_crossing_and_remains_bound_to_source_uuid(self):
        self.actions.move_paragraph(1)
        self.actions.select_span(2, 7)
        selected = self.actions.selection
        before = len(self.workspace.checkpoints)
        self.actions.advance_reading(-1, layout=self.geometry())
        self.assertEqual(self.actions.snapshot().current.identifier, IDS[1])
        self.assertEqual(self.actions.selection, selected)
        self.assertEqual(self.actions.selection.text, self.book.passages[1].text[2:7])
        self.assertEqual(len(self.workspace.checkpoints), before)

    def test_selecting_mode_still_allows_local_visual_motion(self):
        self.replace_text(0, "abcdefghijklmnop")
        self.actions.set_cursor(2)
        before = len(self.workspace.checkpoints)
        self.actions.advance_reading(1, 10, selecting=True)
        self.assertEqual((self.actions.snapshot().current.identifier, self.actions.cursor_offset),
                         (IDS[0], 12))
        self.assertEqual(len(self.workspace.checkpoints), before)

    def test_scope_edges_are_quiet_and_do_not_escape_or_write_checkpoints(self):
        self.actions.read(("BEING",), first=True)
        self.actions.set_cursor(4)
        before = self.actions.snapshot(), tuple(self.workspace.checkpoints), self.actions._trail
        self.actions.advance_reading(-1, layout=self.geometry())
        self.assertEqual((self.actions.snapshot(), tuple(self.workspace.checkpoints),
                          self.actions._trail), before)
        self.actions.move_paragraph(1)
        self.actions.set_cursor(self.outer_row_offset(1))
        before = self.actions.snapshot(), tuple(self.workspace.checkpoints), self.actions._trail
        self.actions.advance_reading(10, layout=self.geometry())
        self.assertEqual((self.actions.snapshot(), tuple(self.workspace.checkpoints),
                          self.actions._trail), before)
        self.assertEqual(self.actions.snapshot().scope, ("BEING",))

    def test_retired_alias_and_search_history_restore_meaningful_origin(self):
        self.book.canonical_records[RETIRED] = {
            "id": RETIRED, "type": "retired_record", "redirect_id": IDS[0]}
        self.workspace.current_reference = lambda session, identifier: resolve_reference(
            self.book, identifier)
        self.actions.open(RETIRED)
        self.actions.search("invented", ())
        self.actions.set_cursor(self.outer_row_offset(1))
        self.actions.set_viewport(10)
        origin = self.actions.snapshot()
        self.actions.advance_reading(1, layout=self.geometry())
        destination = self.actions.snapshot()
        self.assertEqual(destination.requested_id, IDS[1])
        self.assertEqual(destination.search_query, origin.search_query)
        self.assertEqual(destination.results, origin.results)
        self.assertIsNone(self.actions._preferred_column)
        self.assertIsNone(self.actions._preferred_layout)
        self.actions.history_back()
        restored = self.actions.snapshot()
        self.assertEqual((restored.current, restored.requested_id, restored.cursor_offset,
                          restored.viewport_offset, restored.scope, restored.search_query,
                          restored.results),
                         (origin.current, RETIRED, origin.cursor_offset, 10,
                          origin.scope, origin.search_query, origin.results))
        self.actions.history_forward()
        self.assertEqual((self.actions.snapshot().current.identifier,
                          self.actions.cursor_offset), (IDS[1], 0))

    def test_failed_boundary_checkpoint_rolls_back_entire_local_context(self):
        self.actions.search("invented", ())
        self.actions.set_cursor(self.outer_row_offset(1))
        self.actions.set_viewport(10)
        self.actions._preferred_column = 3
        self.actions._preferred_layout = self.geometry()
        before = self.local_state()
        for error in (RuntimeError("CAS conflict"), OSError("storage unavailable")):
            with self.subTest(error=error), \
                    patch.object(self.workspace, "checkpoint", side_effect=error):
                with self.assertRaises(type(error)):
                    self.actions.advance_reading(1, layout=self.geometry())
            self.assertEqual(self.local_state(), before)

    def test_zero_rows_and_invalid_arguments_do_not_mutate_context(self):
        before = self.local_state()
        self.actions.advance_reading(0, layout=self.geometry())
        self.assertEqual(self.local_state(), before)
        for options in ({"rows": True}, {"rows": 1.5}, {"rows": "1"},
                        {"rows": 1, "selecting": 1}, {"rows": 1, "selecting": None},
                        {"rows": 1, "layout": ()}, {"rows": 1, "layout": ((0, 0),)},
                        {"rows": 1, "width": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.actions.advance_reading(**options)
            self.assertEqual(self.local_state(), before)

    def test_one_visible_row_request_is_valid_and_crosses_at_most_one_identity(self):
        self.replace_text(0, "Short.")
        self.actions.set_cursor(3)
        before = len(self.workspace.checkpoints)
        self.actions.advance_reading(1, 72)
        self.assertEqual((self.actions.snapshot().current.identifier, self.actions.cursor_offset),
                         (IDS[1], 0))
        self.assertEqual(len(self.workspace.checkpoints), before + 1)

    def test_identical_prose_does_not_collapse_distinct_passage_identities(self):
        self.replace_text(0, "The same invented prose.")
        self.replace_text(1, "The same invented prose.")
        self.actions.set_cursor(5)
        before = len(self.workspace.checkpoints)
        self.actions.advance_reading(1, 72)
        self.assertEqual(self.actions.snapshot().current.identifier, IDS[1])
        self.assertEqual(self.actions.snapshot().requested_id, IDS[1])
        self.assertEqual(self.actions.cursor_offset, 0)
        self.assertEqual(self.workspace.checkpoints[-1][0], IDS[1])
        self.assertEqual(len(self.workspace.checkpoints), before + 1)

    def test_existing_vertical_actions_remain_local_at_an_outer_reading_edge(self):
        self.replace_text(0, "Short invented source.")
        self.actions.set_cursor(5)
        before = self.local_state()
        self.actions.move_down(72)
        self.actions.move_up(72)
        self.actions.half_page(1, 1, 72)
        self.assertEqual(self.actions.snapshot().current.identifier, IDS[0])
        self.assertEqual(self.actions.cursor_offset, 5)
        self.assertEqual(tuple(self.workspace.checkpoints), before[-1])

    def test_empty_reader_rejects_flow_without_creating_a_position(self):
        actions = ReaderActions(self.book)
        before = actions.snapshot()
        with self.assertRaisesRegex(ValueError, "no current paragraph"):
            actions.advance_reading(1, 72)
        self.assertEqual(actions.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
