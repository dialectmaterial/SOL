"""Reader-first context stays transient, canonical, and independent of a UI."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.core.paths import display_path, resolve_path
from sol.being.actions import ReaderActions, ReaderState, TextSelection
from sol.being.workspace.reader import WorkspaceReader
from sol.being.workspace.store import Workspace, WorkspaceConflict, WorkspaceError
from test_reader_actions import CORPUS_ID, IDS, RETIRED, invented_book


class ReaderContextTests(unittest.TestCase):
    def setUp(self):
        self.book = invented_book()
        self.actions = ReaderActions(self.book)

    def retire_first(self):
        self.book.canonical_records[RETIRED] = {
            'id': RETIRED, 'type': 'retired_record', 'redirect_id': IDS[0]}
        # Identity comes from the canonical graph, even without this cache.
        self.book.redirects.clear()

    def internal_state(self):
        return (self.actions.snapshot(), self.actions.previous_cwd,
                self.actions._trail, self.actions._history_index)

    def test_empty_snapshot_and_history_boundaries(self):
        self.assertEqual(self.actions.snapshot(), ReaderState(
            None, (), (), None, None, False, False, None, ()))
        for operation in (self.actions.history_back, self.actions.history_forward,
                          lambda: self.actions.select_span(0, 1)):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()
        self.actions.clear_selection()
        self.actions.open(IDS[0])
        self.assertFalse(self.actions.snapshot().can_go_back)
        self.assertFalse(self.actions.snapshot().can_go_forward)

    def test_selection_search_and_reading_history_restore_complete_context(self):
        self.actions.browse(('BEING',))
        first = self.actions.read(first=True)
        selected = self.actions.select_span(2, 15)
        results = self.actions.search('invented', ())
        original = self.actions.snapshot()
        second = self.actions.open_result(2)
        self.assertEqual((first.identifier, second.identifier), tuple(IDS[:2]))
        self.assertIsNone(self.actions.selection)
        self.assertEqual(self.actions.history_back(), first)
        restored = self.actions.snapshot()
        self.assertEqual((restored.current, restored.cwd, restored.scope,
                          restored.requested_id, restored.selection,
                          restored.search_query, restored.results),
                         (original.current, original.cwd, original.scope,
                          original.requested_id, selected, 'invented', tuple(results)))
        self.assertTrue(restored.can_go_forward)
        self.assertEqual(self.actions.history_forward(), second)
        self.assertIsNone(self.actions.selection)
        self.assertEqual(self.actions.search_query, 'invented')

    def test_selection_and_search_amend_context_without_creating_navigation(self):
        self.actions.open(IDS[0])
        trail_length = len(self.actions._trail)
        self.actions.select_span(0, 1)
        self.actions.search('ground')
        self.actions.select_span(2, 8)
        self.actions.clear_selection()
        self.assertEqual(len(self.actions._trail), trail_length)
        self.assertFalse(self.actions.snapshot().can_go_back)
        before = self.internal_state()
        with self.assertRaises(ValueError):
            self.actions.search('')
        self.assertEqual(self.internal_state(), before)

    def test_branch_is_cut_only_after_successful_new_navigation(self):
        for identifier in IDS[:2]:
            self.actions.open(identifier)
        self.actions.history_back()
        selected = self.actions.select_span(0, 8)
        before = self.internal_state()
        with self.assertRaises(ValueError):
            self.actions.open('missing')
        self.assertEqual(self.internal_state(), before)
        self.actions.open(IDS[0])
        self.actions.move(0)
        self.assertEqual(self.internal_state(), before)
        self.assertEqual(self.actions.selection, selected)
        self.assertTrue(self.actions.snapshot().can_go_forward)
        self.actions.open(IDS[2])
        self.assertFalse(self.actions.snapshot().can_go_forward)
        self.assertEqual(self.actions.history_back().identifier, IDS[0])
        self.assertEqual(self.actions.selection, selected)
        self.assertEqual(self.actions.history_forward().identifier, IDS[2])

    def test_directory_back_keeps_its_existing_semantics(self):
        self.actions.browse(('BEING',))
        first = self.actions.read(first=True)
        selected = self.actions.select_span(0, 8)
        self.actions.browse(('ESSENCE',))
        self.assertIsNone(self.actions.snapshot().current)
        self.assertIsNone(self.actions.selection)
        self.assertEqual(self.actions.history_back(), first)
        self.assertEqual(self.actions.cwd, ('BEING',))
        self.assertEqual(self.actions.selection, selected)
        self.actions.browse(('ESSENCE',))
        self.actions.back()
        self.assertEqual(self.actions.cwd, ('BEING',))
        self.assertIsNone(self.actions.snapshot().current)

    def test_requested_retirement_identity_is_preserved_without_new_ids(self):
        self.retire_first()
        with patch('uuid.uuid4', side_effect=AssertionError('No new identity')):
            self.actions.open(RETIRED[:8])
            selected = self.actions.select_span(0, 8)
            self.actions.open(IDS[1])
            self.actions.history_back()
        self.assertEqual((selected.requested_id, selected.target_id), (RETIRED, IDS[0]))
        self.assertEqual(self.actions.snapshot().requested_id, RETIRED)
        self.assertEqual(self.actions.selection, selected)
        self.assertEqual(set(self.book.canonical_records), {*IDS, RETIRED})

    def test_same_target_alias_change_keeps_span_with_current_requested_identity(self):
        self.retire_first()
        self.actions.open(IDS[0])
        selected = self.actions.select_span(0, 8)
        self.actions.open(RETIRED)
        self.assertEqual(self.actions.selection, replace(selected, requested_id=RETIRED))
        self.actions.history_back()
        self.assertEqual(self.actions.selection, selected)

    def test_offsets_are_half_open_unicode_codepoints_of_exact_plain_text(self):
        text = 'α😀 e\u0301\nA line.'
        record = self.book.canonical_records[IDS[0]]
        record.update(plain_text=text, markdown=text, content_sha256=sha256(text.encode()).hexdigest())
        self.book.passages[0] = replace(self.book.passages[0], text=text)
        self.actions.open(IDS[0])
        selected = self.actions.select_span(1, 6)
        self.assertIsInstance(selected, TextSelection)
        self.assertEqual((selected.start, selected.end, selected.text), (1, 6, '😀 e\u0301\n'))
        self.assertEqual(selected.plain_text_sha256, sha256(text.encode()).hexdigest())
        self.assertEqual(self.actions.select_span(0, len(text)).text, text)
        self.assertEqual(self.actions.select_span(len(text) - 1, len(text)).text, '.')
        with self.assertRaises(FrozenInstanceError):
            selected.start = 0
        with self.assertRaises(FrozenInstanceError):
            self.actions.snapshot().search_query = 'another query'

    def test_invalid_spans_do_not_change_selection_or_history(self):
        self.actions.open(IDS[0])
        self.actions.select_span(0, 8)
        before = self.internal_state()
        length = len(self.book.passages[0].text)
        for start, end in ((False, 3), (0, True), (0.0, 3), (0, 3.0), ('0', 3),
                           (None, 3), (-1, 3), (3, 3), (4, 3), (0, length + 1),
                           (length, length + 1)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.actions.select_span(start, end)
            self.assertEqual(self.internal_state(), before)

    def test_legacy_book_can_read_but_cannot_claim_a_canonical_selection(self):
        self.book.canonical_records = {}
        self.actions.open(IDS[0])
        with self.assertRaisesRegex(ValueError, 'canonical Book records'):
            self.actions.select_span(0, 8)
        self.assertIsNone(self.actions.snapshot().selection)

    def test_corrupted_record_or_projection_is_rejected_before_selection(self):
        original = self.book.passages[0]
        self.actions.open(IDS[0])
        for changes in ({'text': 'Wrong text'}, {'kind': 'formula'}, {'pdf_page': 4},
                        {'printed_page': 7}, {'path': ('ESSENCE', 'wrong.txt')}):
            with self.subTest(changes=changes):
                self.book.passages[0] = replace(original, **changes)
                with self.assertRaisesRegex(ValueError, 'disagrees'):
                    self.actions.select_span(0, 8)
                self.assertIsNone(self.actions._selection)
        self.book.passages[0] = original
        record = self.book.canonical_records[IDS[0]]
        for field, value in (('content_sha256', '0' * 64), ('plain_text', 'Wrong canonical text'),
                             ('markdown', 'Changed Markdown'), ('id', IDS[1]), ('sources', [])):
            previous = record[field]
            with self.subTest(field=field):
                record[field] = value
                with self.assertRaises(ValueError):
                    self.actions.select_span(0, 8)
                self.assertIsNone(self.actions._selection)
            record[field] = previous

    def test_scope_drift_cannot_silently_change_the_current_passage_in_a_snapshot(self):
        self.actions.read(('BEING',), first=True)
        before = self.actions.snapshot()
        original = self.book.passages[0]
        self.book.passages[0] = replace(original, path=('ESSENCE', 'wrong.txt'))
        with self.assertRaisesRegex(ValueError, 'reading context'):
            self.actions.snapshot()
        self.book.passages[0] = original
        self.assertEqual(self.actions.snapshot(), before)

    def test_selected_source_changes_are_detected_on_property_and_snapshot(self):
        self.actions.open(IDS[0])
        self.actions.select_span(0, 8)
        record = self.book.canonical_records[IDS[0]]
        changed = record['plain_text'] + ' Changed text.'
        record.update(plain_text=changed, markdown=changed,
                      content_sha256=sha256(changed.encode()).hexdigest())
        self.book.passages[0] = replace(self.book.passages[0], text=changed)
        for operation in (lambda: self.actions.selection, self.actions.snapshot):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'source text changed'):
                operation()
        self.actions.clear_selection()
        self.assertIsNone(self.actions.snapshot().selection)

    def test_history_revalidates_span_and_rolls_back_if_source_changed(self):
        self.actions.open(IDS[0])
        selected = self.actions.select_span(0, 8)
        self.actions.open(IDS[1])
        before = self.internal_state()
        record = self.book.canonical_records[IDS[0]]
        markdown = '**' + record['markdown'] + '**'
        record.update(markdown=markdown, content_sha256=sha256(markdown.encode()).hexdigest())
        with self.assertRaisesRegex(ValueError, 'source text changed'):
            self.actions.history_back()
        self.assertEqual(self.internal_state(), before)
        self.assertEqual(self.actions._trail[self.actions._history_index - 1].selection, selected)

    def test_history_rejects_a_changed_retirement_target(self):
        self.retire_first()
        self.actions.open(RETIRED)
        self.actions.select_span(0, 8)
        self.actions.open(IDS[1])
        before = self.internal_state()
        self.book.canonical_records[RETIRED]['redirect_id'] = IDS[2]
        with self.assertRaisesRegex(ValueError, 'historical reading reference changed'):
            self.actions.history_back()
        self.assertEqual(self.internal_state(), before)

    def test_history_uses_live_passages_and_stable_result_ids(self):
        self.actions.open(IDS[0])
        self.actions.search('invented')
        self.actions.open_result(2)
        replacement = replace(self.book.passages[0], heading='Current heading')
        self.book.passages[0] = replacement
        self.assertIs(self.actions.history_back(), replacement)
        self.assertIs(self.actions.snapshot().results[0], replacement)
        self.assertEqual(self.actions._trail[self.actions._history_index].result_ids, tuple(IDS))

    def test_session_history_is_bounded(self):
        for index in range(140):
            self.actions.open(IDS[index % 2])
        self.assertEqual(len(self.actions._trail), 100)
        for _ in range(99):
            self.actions.history_back()
        self.assertFalse(self.actions.snapshot().can_go_back)
        with self.assertRaises(ValueError):
            self.actions.history_back()


class WorkspaceReaderContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sol-reader-context-test-')
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'workspace.sqlite3'
        self.book = invented_book()
        self.provenance = {key: self.book.corpus_manifest[key] for key in ('edition', 'source')}
        self.store = Workspace(self.path, CORPUS_ID, self.provenance, actor='Ada')
        self.addCleanup(self.store.close)
        self.reader = WorkspaceReader(self.book, self.store, 'Ada', resolve_path, display_path,
                                      lambda *args, **kwargs: self.fail('Reader context does not render'))
        self.actions = ReaderActions(self.book, self.reader)

    def state(self):
        return (self.actions.snapshot(), self.actions.previous_cwd, self.reader.resumed_reference,
                self.reader.revision, self.actions._trail, self.actions._history_index)

    def test_selection_snapshot_search_and_same_directory_create_no_checkpoint(self):
        self.actions.open(IDS[0])
        saved = self.store.get_state()
        with patch.object(self.reader, 'checkpoint', side_effect=AssertionError('No visit')):
            self.actions.select_span(0, 8)
            self.actions.snapshot()
            self.actions.search('invented')
            self.actions.browse(self.actions.cwd)
            self.actions.clear_selection()
        self.assertEqual(self.store.get_state(), saved)
        self.assertEqual(len(self.store.list_history()), 1)
        exported = self.store.export()
        self.assertEqual(exported['annotations'], [])

    def test_explicit_repeat_visits_keep_span_and_trail_but_retain_checkpoint_guards(self):
        self.actions.open(IDS[0])
        self.actions.select_span(0, 8)
        before = self.actions.snapshot()
        trail = self.actions._trail
        with patch.object(self.reader, 'checkpoint', wraps=self.reader.checkpoint) as checkpoint:
            self.actions.open(IDS[0])
            self.actions.move(0)
        self.assertEqual(checkpoint.call_count, 2)
        self.assertEqual(len(self.store.list_history()), 3)
        self.assertEqual(self.actions.snapshot(), before)
        self.assertEqual(self.actions._trail, trail)
        with Workspace(self.path, CORPUS_ID, self.provenance, actor='Other') as other:
            newer = other.get_state()
            newer['current_id'] = IDS[2]
            other.save_state(newer, newer['revision'])
            with self.assertRaises(WorkspaceConflict):
                self.actions.open(IDS[0])
            self.assertEqual(self.actions.snapshot(), before)
            self.assertEqual(self.actions._trail, trail)
            self.assertEqual(other.get_state()['current_id'], IDS[2])

    def test_workspace_history_restores_scope_browsing_and_requested_id(self):
        self.book.canonical_records[RETIRED] = {
            'id': RETIRED, 'type': 'retired_record', 'redirect_id': IDS[0]}
        self.actions.browse(('BEING',))
        self.actions.open(RETIRED)
        self.actions.select_span(0, 8)
        self.actions.search('invented', ())
        original = self.actions.snapshot()
        self.actions.browse(('ESSENCE',))
        self.actions.open_result(3)
        self.actions.history_back()
        self.assertEqual((self.actions.cwd, self.actions.session.path), (('ESSENCE',), original.scope))
        self.assertEqual(self.actions.selection, original.selection)
        self.actions.history_back()
        restored = self.actions.snapshot()
        self.assertEqual((restored.current, restored.cwd, restored.scope, restored.requested_id,
                          restored.selection, restored.search_query, restored.results),
                         (original.current, original.cwd, original.scope, original.requested_id,
                          original.selection, original.search_query, original.results))
        self.assertEqual(self.store.get_state()['current_id'], RETIRED)
        self.assertEqual(len(self.store.list_history()), 5)

    def test_concurrent_checkpoint_restores_selection_trail_cursor_and_search(self):
        self.actions.open(IDS[0])
        self.actions.select_span(0, 8)
        self.actions.search('invented')
        self.actions.open_result(2)
        self.actions.search('ground')
        self.actions.select_span(0, 9)
        before = self.state()
        with Workspace(self.path, CORPUS_ID, self.provenance, actor='Other') as other:
            state = other.get_state()
            state['current_id'] = IDS[2]
            other.save_state(state, state['revision'])
            for operation in (self.actions.history_back, lambda: self.actions.open(IDS[2]),
                              lambda: self.actions.browse(('ESSENCE',))):
                with self.subTest(operation=operation), self.assertRaises(WorkspaceConflict):
                    operation()
                self.assertEqual(self.state(), before)
            self.assertEqual(other.get_state()['current_id'], IDS[2])

    def test_failed_forward_and_branch_leave_remaining_trail_intact(self):
        self.actions.open(IDS[0])
        self.actions.select_span(0, 8)
        self.actions.search('invented')
        self.actions.open_result(2)
        self.actions.history_back()
        before = self.state()
        with patch.object(self.reader, 'checkpoint', side_effect=RuntimeError('Unavailable workspace')):
            for operation in (self.actions.history_forward, lambda: self.actions.open(IDS[2])):
                with self.subTest(operation=operation), self.assertRaisesRegex(RuntimeError, 'Unavailable'):
                    operation()
                self.assertEqual(self.state(), before)
        self.assertTrue(self.actions.snapshot().can_go_forward)

    def test_existing_generation_guard_also_protects_history_moves(self):
        self.actions.open(IDS[0])
        self.actions.select_span(0, 8)
        self.actions.open(IDS[1])
        before, saved = self.state(), self.store.get_state()
        with patch.object(self.reader, 'corpus_freshness', return_value={
                'state': 'changed', 'reason': 'Invented generation change'}):
            with self.assertRaises(WorkspaceError):
                self.actions.history_back()
        self.assertEqual(self.state(), before)
        self.assertEqual(self.store.get_state(), saved)

    def test_latest_restore_seeds_history_and_historical_restore_remains_a_new_visit(self):
        self.actions.open(IDS[0])
        self.actions.select_span(0, 8)
        self.actions.open(IDS[1])
        restored = ReaderActions(self.book, self.reader)
        saved = self.store.get_state()
        restored.restore()
        self.assertFalse(restored.snapshot().can_go_back)
        self.assertFalse(restored.snapshot().can_go_forward)
        self.assertIsNone(restored.selection)
        self.assertEqual(len(restored._trail), 1)
        self.assertEqual(self.store.get_state(), saved)
        restored.restore(1)
        self.assertEqual(restored.session.current().identifier, IDS[0])
        self.assertEqual(len(self.store.list_history()), 3)
        self.assertEqual(restored.history_back().identifier, IDS[1])
        self.assertEqual(len(self.store.list_history()), 4)

    def test_snapshot_and_selection_do_not_read_disk_or_check_generation(self):
        self.actions.open(IDS[0])
        with patch('builtins.open', side_effect=AssertionError('No source-file I/O')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('No source-file I/O')), \
                patch.object(self.reader, 'corpus_freshness', side_effect=AssertionError('No rehash')):
            self.actions.select_span(0, 8)
            self.actions.snapshot()


class ReaderContextImportTests(unittest.TestCase):
    def test_plain_context_imports_no_ui_workspace_optional_parser_or_database(self):
        script = '''
import hashlib
import sys
from sol.core.models import Book, Node, Passage
from sol.being.actions import ReaderActions, ReaderState, TextSelection
root = Node('', 'Invented', 1)
leaf = Node('invented.txt', 'Invented', 1, parent=root)
root.children = (leaf,)
identifier = 'aaaaaaaa-0000-4000-8000-000000000001'
text = 'Invented exact canonical text.'
passage = Passage(text, 1, 1, leaf, ('invented.txt',), 1, 1, identifier)
record = {'id': identifier, 'type': 'paragraph', 'plain_text': text, 'markdown': text,
          'reader_path': '/invented.txt', 'sources': [{'pdf_page': 1, 'printed_page': '1'}],
          'content_sha256': hashlib.sha256(text.encode()).hexdigest()}
def guard(event, args):
    if event == 'sqlite3.connect':
        raise AssertionError('No database')
    if event == 'open' and len(args) > 2 and args[2] & 3:
        raise AssertionError('No file writes')
sys.addaudithook(guard)
actions = ReaderActions(Book(root, [passage], canonical_records={identifier: record}))
actions.open(identifier)
actions.select_span(0, 8)
assert actions.snapshot().selection.text == 'Invented'
actions.search('text')
actions.clear_selection()
for name in ('sol.reader.app', 'sol.reader.view', 'sol.being.workspace', 'sqlite3',
             'prompt_toolkit', 'markdown_it', 'fitz', 'sol.corpus.contract'):
    assert name not in sys.modules, name
'''
        result = subprocess.run([sys.executable, '-B', '-c', script],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
