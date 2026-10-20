"""Search visits land on source matches without changing ordinary-open semantics."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.core.paths import display_path, resolve_path
from sol.core.references import resolve_reference
from sol.reader.actions import ReaderActions
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace, WorkspaceConflict, WorkspaceError
from test_reader_actions import CORPUS_ID, IDS, RETIRED, invented_book


class RecordingWorkspace:
    """Observe the position supplied to the one checkpoint, not a later save."""
    def __init__(self, book):
        self.book = book
        self.resumed_reference = None
        self.positions = []

    def current_reference(self, session, identifier):
        return resolve_reference(self.book, identifier)

    def checkpoint(self, session, cwd, previous):
        self.positions.append((session.current().identifier, session.cursor_offset,
                               session.viewport_offset, cwd, previous))


class ReaderSearchActionsTests(unittest.TestCase):
    def setUp(self):
        self.book = invented_book()
        self.actions = ReaderActions(self.book)
        self.actions.read((), first=True)

    def state(self):
        return (self.actions.snapshot(), self.actions._trail, self.actions._history_index,
                self.actions._preferred_column, self.actions._preferred_layout)

    def replace_text(self, text):
        self.book.passages[0] = replace(self.book.passages[0], text=text)
        self.book.canonical_records[IDS[0]].update(
            plain_text=text, markdown=text,
            content_sha256=sha256(text.encode()).hexdigest())

    def test_search_open_lands_on_first_source_match_not_passage_start(self):
        self.actions.search('invented', ())
        second = self.actions.open_result(2)
        self.assertEqual(second.identifier, IDS[1])
        self.assertEqual(self.actions.cursor_offset, second.text.index('invented'))
        self.assertIsNone(self.actions.session.viewport_offset)

    def test_search_open_same_passage_preserves_selected_origin_in_history(self):
        selected = self.actions.select_span(2, 15)
        self.actions.set_viewport(3)
        self.actions.search('ground', (), whole_word=True)
        origin = self.actions.snapshot()
        trail_length = len(self.actions._trail)
        self.actions.open_result(1)
        self.assertEqual(self.actions.cursor_offset, origin.current.text.index('ground'))
        self.assertIsNone(self.actions.selection)
        self.assertIsNone(self.actions.session.viewport_offset)
        self.assertEqual(len(self.actions._trail), trail_length + 1)
        self.actions.history_back()
        restored = self.actions.snapshot()
        self.assertEqual((restored.current, restored.cursor_offset, restored.viewport_offset,
                          restored.selection, restored.search_query,
                          restored.search_whole_word, restored.results),
                         (origin.current, origin.cursor_offset, origin.viewport_offset,
                          selected, origin.search_query, True, origin.results))
        self.actions.history_forward()
        self.assertEqual(self.actions.cursor_offset, origin.current.text.index('ground'))
        self.assertIsNone(self.actions.selection)

    def test_selection_only_change_on_same_match_is_a_returnable_search_visit(self):
        match = self.book.passages[0].text.index('ground')
        selected = self.actions.select_span(match, match + 6)
        self.actions.set_cursor(match)
        self.actions.search('ground', ())
        trail_length = len(self.actions._trail)
        self.actions.open_result(1)
        self.assertEqual(self.actions.cursor_offset, match)
        self.assertIsNone(self.actions.selection)
        self.assertEqual(len(self.actions._trail), trail_length + 1)
        self.actions.history_back()
        self.assertEqual(self.actions.selection, selected)
        self.assertEqual(self.actions.cursor_offset, match)

    def test_same_match_keeps_viewport_without_manufacturing_history(self):
        match = self.book.passages[0].text.index('ground')
        self.actions.set_cursor(match)
        self.actions.set_viewport(3)
        self.actions.search('ground', ())
        trail_length = len(self.actions._trail)
        self.actions.open_result(1)
        self.assertEqual(len(self.actions._trail), trail_length)
        self.assertEqual(self.actions.cursor_offset, match)
        self.assertEqual(self.actions.session.viewport_offset, 3)

    def test_exact_repeated_search_destination_does_not_grow_transient_history(self):
        self.actions.search('ground', ())
        self.actions.open_result(1)
        before = self.state()
        self.actions.open_result(1)
        self.assertEqual(self.state(), before)

    def test_ordinary_repeat_open_still_preserves_selection_position_and_trail(self):
        selected = self.actions.select_span(2, 15)
        self.actions.set_viewport(3)
        self.actions.search('ground', (), whole_word=True)
        before = self.state()
        self.actions.open(IDS[0])
        self.assertEqual(self.state(), before)
        self.assertEqual(self.actions.selection, selected)

    def test_character_motion_after_search_does_not_create_navigation_entries(self):
        self.actions.search('ground', ())
        self.actions.open_result(1)
        size = len(self.actions._trail)
        for _ in range(5):
            self.actions.move_horizontal(1)
        self.assertEqual(len(self.actions._trail), size)

    def test_latest_whole_word_mode_survives_history_in_both_directions(self):
        self.actions.search('ground', (), whole_word=True)
        self.actions.open_result(2)
        self.assertTrue(self.actions.snapshot().search_whole_word)
        self.actions.search('invented', (), whole_word=False)
        self.actions.open_result(2)
        self.actions.history_back()
        self.assertEqual(self.actions.search_query, 'invented')
        self.assertFalse(self.actions.snapshot().search_whole_word)
        self.actions.history_back()
        self.assertEqual(self.actions.search_query, 'ground')
        self.assertTrue(self.actions.snapshot().search_whole_word)
        self.actions.history_forward()
        self.assertFalse(self.actions.snapshot().search_whole_word)

    def test_whole_word_search_does_not_open_embedded_grounding(self):
        results = self.actions.search('ground', (), whole_word=True)
        self.assertEqual([p.identifier for p in results], [IDS[0], IDS[2]])
        target = self.actions.open_result(2)
        self.assertEqual(target.identifier, IDS[2])
        self.assertEqual(self.actions.cursor_offset, target.text.index('ground'))
        self.actions.search_next(reverse=True)
        self.assertEqual(self.actions.snapshot().current.identifier, IDS[0])
        self.assertTrue(self.actions.snapshot().search_whole_word)

    def test_casefold_expansion_lands_on_original_source_boundary(self):
        text = 'Before Straße, after the road.'
        self.replace_text(text)
        self.actions.search('STRASSE', ())
        self.actions.open_result(1)
        self.assertEqual(self.actions.cursor_offset, text.index('Straße'))
        self.assertEqual(self.actions.snapshot().current.text, text)

    def test_decomposed_emphasis_search_uses_source_not_normalized_offsets(self):
        text = 'Before e\u0301lan, the source remains decomposed.'
        self.replace_text(text)
        self.actions.search('ÉLAN', ())
        self.actions.open_result(1)
        self.assertEqual(self.actions.cursor_offset, text.index('e\u0301lan'))
        self.assertEqual(self.actions.snapshot().current.text, text)

    def test_failed_search_keeps_query_mode_results_and_origin(self):
        self.actions.search('ground', (), whole_word=True)
        before = self.state()
        for query, limit in (('', 20), ('invented', 0), ('invented', 1001)):
            with self.subTest(query=query, limit=limit), self.assertRaises(ValueError):
                self.actions.search(query, (), whole_word=False, limit=limit)
            self.assertEqual(self.state(), before)

    def test_invalid_result_number_does_not_change_semantic_context(self):
        self.actions.search('ground', (), whole_word=True)
        selected = self.actions.select_span(0, 3)
        before = self.state()
        for number in (0, 3, -1, True, 1.0, '1', None):
            with self.subTest(number=number), self.assertRaises(ValueError):
                self.actions.open_result(number)
            self.assertEqual(self.state(), before)
            self.assertEqual(self.actions.selection, selected)

    def test_invalid_search_mode_keeps_previous_query_and_mode(self):
        self.actions.search('ground', (), whole_word=True)
        before = self.state()
        for mode in (None, 0, 1, 'word'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.actions.search('invented', (), whole_word=mode)
            self.assertEqual(self.state(), before)

    def test_search_next_wraps_passages_but_enters_matching_source_offsets(self):
        self.actions.search('invented', ())
        for identifier in (IDS[0], IDS[1], IDS[2], IDS[0]):
            target = self.actions.search_next()
            self.assertEqual(target.identifier, identifier)
            self.assertEqual(self.actions.cursor_offset, target.text.index('invented'))
        target = self.actions.search_next(reverse=True)
        self.assertEqual(target.identifier, IDS[2])
        self.assertEqual(self.actions.cursor_offset, target.text.index('invented'))

    def test_every_occurrence_is_counted_and_reachable_in_both_directions(self):
        self.replace_text('Ground, ground, GROUND.')
        self.actions.search('ground', (), whole_word=True, limit=None)
        self.actions.open_result(1)
        expected = [(IDS[0], 0), (IDS[0], 8), (IDS[0], 16),
                    (IDS[2], self.book.passages[2].text.index('ground'))]
        for index, (identifier, offset) in enumerate(expected, 1):
            self.assertEqual((self.actions.snapshot().current.identifier, self.actions.cursor_offset),
                             (identifier, offset))
            self.assertEqual(self.actions.search_position(), (index, 4))
            self.actions.search_next()
        self.assertEqual(self.actions.search_position(), (1, 4))
        for index in (4, 3, 2, 1):
            self.actions.search_next(reverse=True)
            self.assertEqual(self.actions.search_position(), (index, 4))

    def test_complete_search_has_neither_twenty_nor_thousand_passage_ceiling(self):
        original = self.book.passages[0]
        self.book.canonical_records = {}
        self.book.passages = [replace(original, identifier=f'passage-{i}', text='the and the')
                              for i in range(1005)]
        self.actions = ReaderActions(self.book)
        self.actions.read((), first=True)
        self.assertEqual(len(self.actions.search('the', (), limit=None)), 1005)
        self.actions.open_result(1005)
        self.assertEqual(self.actions.search_position(), (2009, 2010))
        self.actions.search_next()
        self.assertEqual(self.actions.search_position(), (2010, 2010))
        self.actions.search_next()
        self.assertEqual(self.actions.search_position(), (1, 2010))
        self.actions.search_next(reverse=True)
        self.assertEqual(self.actions.search_position(), (2010, 2010))

    def test_partial_unicode_matches_keep_their_ordinal_without_guessed_spans(self):
        self.replace_text('ß s')
        self.actions.search('s', (), whole_word=False, limit=1)
        self.actions.open_result(1)
        self.assertEqual(self.actions.search_position(), (1, 3))
        self.assertEqual(self.actions.cursor_offset, 0)
        self.actions.search_next()
        self.assertEqual(self.actions.search_position(), (2, 3))
        self.assertEqual(self.actions.cursor_offset, 0)
        self.actions.history_back()
        self.assertEqual(self.actions.search_position(), (1, 3))
        self.actions.history_forward()
        self.assertEqual(self.actions.search_position(), (2, 3))
        self.actions.search_next()
        self.assertEqual(self.actions.search_position(), (3, 3))
        self.assertEqual(self.actions.cursor_offset, 2)
        self.assertEqual(self.actions.search_highlights().spans, ((2, 3),))

    def test_refused_same_passage_occurrence_restores_index_and_retry(self):
        self.replace_text('ground ground')
        self.actions.search('ground', (), limit=None)
        self.actions.open_result(1)
        with self.assertRaises(ValueError):
            with self.actions.staged():
                self.actions.search_next()
                raise ValueError('view refused')
        self.assertEqual(self.actions.search_position(), (1, 4))
        self.actions.search_next()
        self.assertEqual(self.actions.search_position(), (2, 4))

    def test_cached_occurrences_are_reused_but_text_replacement_invalidates(self):
        from sol.reader.search import search_projection
        self.actions.search('ground', (), limit=None)
        self.actions.search_occurrences()
        with patch('sol.reader.search.search_projection', wraps=search_projection) as project:
            self.actions.search_position()
            self.actions.search_occurrences()
            self.assertEqual(project.call_count, 0)
            self.replace_text('ground ground')
            self.assertEqual(self.actions.search_position()[1], 4)
            self.assertGreater(project.call_count, 0)

    def test_motion_between_matches_steps_from_live_source_cursor(self):
        self.replace_text('ground then ground')
        self.actions.search('ground', (), whole_word=True, limit=1)
        self.actions.set_cursor(7)
        self.actions.search_next()
        self.assertEqual(self.actions.cursor_offset, 12)
        self.actions.set_cursor(7)
        self.actions.search_next(reverse=True)
        self.assertEqual(self.actions.cursor_offset, 0)

    def test_search_mode_defaults_to_substring_in_snapshot(self):
        self.assertFalse(self.actions.snapshot().search_whole_word)
        self.actions.search('ground', (), whole_word=True)
        self.actions.search('ground', ())
        self.assertFalse(self.actions.snapshot().search_whole_word)
        self.assertEqual(len(self.actions.results), 3)

    def test_checkpoint_observes_match_position_before_any_later_cursor_save(self):
        workspace = RecordingWorkspace(self.book)
        actions = ReaderActions(self.book, workspace)
        actions.read((), first=True)
        actions.search('invented', ())
        workspace.positions.clear()
        target = actions.open_result(2)
        self.assertEqual(workspace.positions,
                         [(target.identifier, target.text.index('invented'), None, (), None)])

    def test_storage_failure_rolls_back_same_passage_selection_and_location(self):
        workspace = RecordingWorkspace(self.book)
        actions = ReaderActions(self.book, workspace)
        actions.read((), first=True)
        actions.select_span(2, 15)
        actions.set_viewport(3)
        actions.search('ground', (), whole_word=True)
        actions.move_down(20)
        before = (actions.snapshot(), actions._trail, actions._history_index,
                  actions._preferred_column, actions._preferred_layout,
                  workspace.resumed_reference)
        with patch.object(workspace, 'checkpoint', side_effect=OSError('Unavailable workspace')):
            with self.assertRaisesRegex(OSError, 'Unavailable workspace'):
                actions.open_result(1)
        self.assertEqual((actions.snapshot(), actions._trail, actions._history_index,
                          actions._preferred_column, actions._preferred_layout,
                          workspace.resumed_reference), before)


class WorkspaceReaderSearchActionsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sol-search-actions-')
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'workspace.sqlite3'
        self.book = invented_book()
        self.provenance = {key: self.book.corpus_manifest[key] for key in ('edition', 'source')}
        self.store = Workspace(self.path, CORPUS_ID, self.provenance, actor='Ada')
        self.addCleanup(self.store.close)
        self.reader = WorkspaceReader(self.book, self.store, 'Ada', resolve_path, display_path,
                                      lambda *args, **kwargs: self.fail('Actions do not render'))
        self.actions = ReaderActions(self.book, self.reader)
        self.actions.read((), first=True)

    def state(self):
        return (self.actions.snapshot(), self.actions._trail, self.actions._history_index,
                self.actions._preferred_column, self.actions._preferred_layout,
                self.reader.resumed_reference, self.reader.revision)

    def test_search_open_commits_one_source_position_checkpoint(self):
        self.actions.search('invented', ())
        revision = self.store.get_state()['revision']
        visits = len(self.store.list_history())
        with patch.object(self.reader, 'checkpoint', wraps=self.reader.checkpoint) as checkpoint:
            target = self.actions.open_result(2)
        self.assertEqual(checkpoint.call_count, 1)
        saved = self.store.get_state()
        self.assertEqual(saved['current_id'], target.identifier)
        self.assertEqual(saved['position']['cursor_offset'], target.text.index('invented'))
        self.assertEqual(saved['revision'], revision + 1)
        self.assertEqual(len(self.store.list_history()), visits + 1)

    def test_same_passage_search_return_and_resume_retain_source_positions(self):
        self.actions.select_span(2, 15)
        self.actions.set_viewport(3)
        self.actions.search('ground', (), whole_word=True)
        original = self.actions.snapshot()
        self.actions.open_result(1)
        matched = self.actions.cursor_offset
        self.assertEqual(self.store.get_state()['position']['cursor_offset'], matched)
        self.actions.history_back()
        self.assertEqual(self.actions.selection, original.selection)
        self.assertEqual(self.store.get_state()['position']['cursor_offset'], original.cursor_offset)
        self.actions.history_forward()
        self.assertEqual(self.store.get_state()['position']['cursor_offset'], matched)
        reopened = ReaderActions(self.book, self.reader)
        reopened.restore()
        self.assertEqual(reopened.cursor_offset, matched)
        self.assertIsNone(reopened.selection)
        self.assertIsNone(reopened.search_query)
        self.assertFalse(reopened.snapshot().search_whole_word)

    def test_failed_search_visit_preserves_retired_origin_and_forward_branch(self):
        self.book.canonical_records[RETIRED] = {
            'id': RETIRED, 'type': 'retired_record', 'redirect_id': IDS[0]}
        self.actions.open(RETIRED)
        self.actions.select_span(2, 15)
        self.actions.open(IDS[1])
        self.actions.history_back()
        self.actions.search('ground', (), whole_word=True)
        before, saved = self.state(), self.store.get_state()
        with patch.object(self.reader, 'checkpoint', side_effect=OSError('No storage')):
            with self.assertRaisesRegex(OSError, 'No storage'):
                self.actions.open_result(1)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.actions.snapshot().requested_id, RETIRED)
        self.assertTrue(self.actions.snapshot().can_go_forward)
        self.assertEqual(self.store.get_state(), saved)

    def test_concurrent_checkpoint_restores_complete_search_origin(self):
        self.actions.select_span(2, 15)
        self.actions.set_viewport(3)
        self.actions.search('ground', (), whole_word=True)
        before = self.state()
        with Workspace(self.path, CORPUS_ID, self.provenance, actor='Other') as other:
            newer = other.get_state()
            newer['current_id'] = IDS[2]
            other.save_state(newer, newer['revision'])
            with self.assertRaises(WorkspaceConflict):
                self.actions.open_result(1)
            self.assertEqual(self.state(), before)
            self.assertEqual(other.get_state()['current_id'], IDS[2])

    def test_generation_change_blocks_match_navigation_without_partial_state(self):
        self.actions.select_span(2, 15)
        self.actions.search('invented', (), whole_word=True)
        before, saved = self.state(), self.store.get_state()
        with patch.object(self.reader, 'corpus_freshness', return_value={
                'state': 'changed', 'reason': 'Invented generation change'}):
            with self.assertRaises(WorkspaceError):
                self.actions.open_result(2)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.store.get_state(), saved)

    def test_failed_history_return_rolls_back_search_mode_as_well_as_location(self):
        self.actions.search('ground', (), whole_word=True)
        self.actions.open_result(2)
        self.actions.search('invented', (), whole_word=False)
        self.actions.open_result(2)
        self.actions.history_back()
        self.assertFalse(self.actions.snapshot().search_whole_word)
        self.actions.select_span(2, 9)
        self.actions.set_viewport(1)
        before, saved = self.state(), self.store.get_state()
        with patch.object(self.reader, 'checkpoint', side_effect=OSError('No storage')):
            with self.assertRaisesRegex(OSError, 'No storage'):
                self.actions.history_back()
        self.assertEqual(self.state(), before)
        self.assertEqual(self.store.get_state(), saved)
        self.assertFalse(self.actions.snapshot().search_whole_word)


if __name__ == '__main__':
    unittest.main()
