"""Reader actions exercised directly with invented text and injected workspaces."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.core.models import Book, Node, Passage, node_path
from sol.core.paths import display_path, resolve_path
from sol.being.actions import ReaderActions, ReadingSession, context_passages
from sol.being.workspace.reader import WorkspaceReader
from sol.being.workspace.store import Workspace, WorkspaceConflict, WorkspaceError


CORPUS_ID = 'dddddddd-0000-4000-8000-000000000001'
IDS = [f'aaaaaaaa-0000-4000-8000-{number:012d}' for number in range(1, 4)]
RETIRED = 'eeeeeeee-0000-4000-8000-000000000001'


def invented_book():
    root = Node('', 'Invented action book', 1)
    being = Node('BEING', 'Being', 1, parent=root)
    leaf = Node('01-quality.txt', 'Quality', 1, parent=being)
    essence = Node('ESSENCE', 'Essence', 3, parent=root)
    other = Node('01-ground.txt', 'Ground', 3, parent=essence)
    root.children = (being, essence)
    being.children, essence.children = (leaf,), (other,)
    bodies = [
        'A common ground supports this invented first paragraph for deliberate reading.',
        'Grounding gives this invented second paragraph a distinct search word and position.',
        'Another ground connects this invented passage to a separate browsing directory.',
    ]
    passages, records = [], {}
    for index, body in enumerate(bodies):
        node = leaf if index < 2 else other
        page = index + 1
        path = node_path(node)
        passages.append(Passage(body, page, page, node, path, page, page,
                                IDS[index], node.title))
        records[IDS[index]] = {
            'id': IDS[index], 'type': 'paragraph', 'parent_id': None, 'order': index,
            'reader_path': display_path(path), 'reader_title': node.title,
            'plain_text': body, 'markdown': body, 'document': 'invented.md',
            'sources': [{'pdf_page': page, 'printed_page': str(page)}],
            'attribution': {'author': 'Invented writer', 'role': 'main_text', 'status': 'confirmed'},
            'content_sha256': hashlib.sha256(body.encode()).hexdigest(),
        }
    return Book(root, passages, canonical_records=records,
                corpus_manifest={'corpus_id': CORPUS_ID,
                                 'edition': {'title': 'Invented edition'},
                                 'source': {'sha256': '0' * 64, 'filename': 'absent.pdf'}})


class ReaderActionsTests(unittest.TestCase):
    def setUp(self):
        self.book = invented_book()
        self.session = ReadingSession(self.book)
        self.actions = ReaderActions(self.book, session=self.session)

    def test_actions_return_book_data_without_prompting_or_rendering(self):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
                patch('builtins.input', side_effect=AssertionError('No prompt in actions')):
            node, path = self.actions.locate('/being')
            self.actions.browse(path)
            first = self.actions.read(first=True)
            second = self.actions.move(1)
            context = self.actions.context(1)
        self.assertIs(self.actions.session, self.session)
        self.assertIs(node, self.book.root.children[0])
        self.assertIs(first, self.book.passages[0])
        self.assertIs(second, self.book.passages[1])
        self.assertEqual(context, self.book.passages)
        self.assertEqual((stdout.getvalue(), stderr.getvalue()), ('', ''))

    def test_changed_browsing_directory_resets_unpersisted_reading_scope(self):
        self.actions.browse(('BEING',))
        self.actions.read(first=True)
        self.actions.move(1)
        self.actions.browse(('ESSENCE',))
        self.assertEqual((self.actions.cwd, self.actions.previous_cwd),
                         (('ESSENCE',), ('BEING',)))
        self.assertEqual((self.session.path, self.session.cursor), (('ESSENCE',), None))
        self.assertIs(self.actions.read(first=True), self.book.passages[2])
        self.actions.back()
        self.assertEqual(self.actions.cwd, ('BEING',))
        self.actions.up()
        self.assertEqual(self.actions.cwd, ())

    def test_same_directory_browse_preserves_cursor_and_latest_search(self):
        self.actions.browse(('BEING',))
        self.actions.read(first=True)
        matches = self.actions.search('ground', whole_word=True)
        self.actions.browse(self.actions.locate('.')[1])
        self.actions.browse(self.actions.locate('/BEING')[1])
        self.assertEqual(self.session.cursor, 0)
        self.assertEqual(self.actions.results, matches)
        self.assertIs(self.actions.open_result(1), self.book.passages[0])

    def test_search_is_readonly_and_failed_search_keeps_latest_results(self):
        self.actions.read(('BEING',), first=True)
        before = (self.actions.cwd, self.actions.previous_cwd, self.session.path, self.session.cursor)
        matches = self.actions.search('ground', ('BEING',), whole_word=True)
        self.assertEqual(matches, [self.book.passages[0]])
        self.assertEqual(before, (self.actions.cwd, self.actions.previous_cwd,
                                  self.session.path, self.session.cursor))
        with self.assertRaises(ValueError):
            self.actions.search('', ('BEING',))
        self.assertEqual(self.actions.results, matches)
        for number in (0, 2):
            with self.subTest(number=number), self.assertRaises(ValueError):
                self.actions.open_result(number)
        self.assertEqual(self.session.cursor, 0)

    def test_invalid_navigation_and_context_preserve_current_selection(self):
        self.actions.read(('BEING',), first=True)
        before = (self.actions.cwd, self.actions.previous_cwd, self.session.path, self.session.cursor)
        for operation in (lambda: self.actions.move(-1),
                          lambda: self.actions.browse(self.book.passages[0].path),
                          lambda: self.actions.open('missing'),
                          lambda: self.actions.context(11)):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()
            self.assertEqual(before, (self.actions.cwd, self.actions.previous_cwd,
                                      self.session.path, self.session.cursor))

    def test_fast_lookups_answer_exactly_as_the_full_scans(self):
        def find_by_full_index(book, identifier):
            # The algorithm before 19 October 2026, kept as the reference.
            identifier = identifier.strip().casefold()
            if not identifier:
                raise ValueError("a passage identifier is required")
            by_id = {passage.identifier.casefold(): passage for passage in book.passages}
            redirects = {key.casefold(): value.casefold() for key, value in book.redirects.items()}
            if identifier in by_id or identifier in redirects:
                target = identifier
            else:
                candidates = [key for key in (*by_id, *redirects) if key.startswith(identifier)]
                if len(candidates) != 1:
                    raise ValueError("ambiguous or unknown")
                target = candidates[0]
            seen = set()
            while target in redirects:
                if target in seen:
                    raise ValueError("cycle")
                seen.add(target)
                target = redirects[target]
            if target not in by_id:
                raise ValueError("not readable")
            return by_id[target]

        self.book.redirects[RETIRED] = IDS[1]
        # A current ID that is also listed as retired follows its redirect.
        self.book.redirects[IDS[2]] = IDS[0]
        for identifier in (*IDS, RETIRED, RETIRED.upper(), " " + IDS[0], "aaaaaaaa", "eeee", "",
                           "ffffffff-0000-4000-8000-000000000009"):
            with self.subTest(identifier=identifier):
                try:
                    expected = find_by_full_index(self.book, identifier)
                except ValueError:
                    with self.assertRaises(ValueError):
                        self.book.find_passage(identifier)
                else:
                    self.assertIs(self.book.find_passage(identifier), expected)
        for path in ((), ("BEING",)):
            session = ReadingSession(self.book, path=path)
            for cursor in range(len(self.book.selection(path))):
                session.cursor = cursor
                self.assertIs(session.current(), self.book.selection(path)[cursor])

    def test_legacy_application_symbols_remain_reexports(self):
        from sol.app import main as app
        self.assertIs(app.ReadingSession, ReadingSession)
        self.assertIs(app.context_passages, context_passages)

    def test_cross_book_session_or_workspace_binding_is_rejected(self):
        other = invented_book()
        with self.assertRaisesRegex(ValueError, 'session must belong'):
            ReaderActions(self.book, session=ReadingSession(other))
        from types import SimpleNamespace
        with self.assertRaisesRegex(ValueError, 'workspace reader must belong'):
            ReaderActions(self.book, workspace_reader=SimpleNamespace(book=other))

    def test_plain_actions_import_no_application_workspace_or_optional_interface(self):
        statement = '''
import json, sys
from sol.core.models import Book, Node, Passage
from sol.being.actions import ReaderActions
root = Node('', 'Invented', 1)
leaf = Node('sample.txt', 'Sample', 1, parent=root)
root.children = (leaf,)
passage = Passage('Invented ground for a reader action.', 1, 1, leaf,
                  ('sample.txt',), 1, 1, 'sample')
actions = ReaderActions(Book(root, [passage]))
actions.locate('/sample.txt')
actions.read(('sample.txt',), first=True)
actions.search('ground')
actions.open_result(1)
actions.context()
actions.browse(())
print(json.dumps(sorted(sys.modules)))
'''
        result = subprocess.run([sys.executable, '-B', '-c', statement],
                                cwd=Path(__file__).resolve().parents[1],
                                text=True, capture_output=True, check=True)
        modules = set(json.loads(result.stdout))
        for prefix in ('sol.app.main', 'sol.being.workspace', 'sol.being.neovim', 'sol.presentation', 'sol.corpus',
                       'prompt_toolkit', 'markdown_it', 'openai'):
            with self.subTest(prefix=prefix):
                self.assertFalse(any(name == prefix or name.startswith(prefix + '.')
                                     for name in modules))


class WorkspaceReaderActionsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sol-actions-')
        self.addCleanup(self.temporary.cleanup)
        self.book = invented_book()
        self.path = Path(self.temporary.name) / 'reading.sqlite3'
        self.provenance = {key: self.book.corpus_manifest[key] for key in ('edition', 'source')}
        self.store = Workspace(self.path, CORPUS_ID, self.provenance, actor='Ada')
        self.addCleanup(self.store.close)
        self.reader = WorkspaceReader(self.book, self.store, 'Ada', resolve_path, display_path,
                                      lambda *args, **kwargs: self.fail('Actions do not render'))
        self.actions = ReaderActions(self.book, self.reader)

    def state(self):
        return (self.actions.cwd, self.actions.previous_cwd, self.actions.session.path,
                self.actions.session.cursor, self.reader.resumed_reference,
                tuple(self.actions.results))

    def retire_first(self):
        self.book.canonical_records[RETIRED] = {
            'id': RETIRED, 'type': 'retired_record', 'redirect_id': IDS[0]}
        self.book.redirects[RETIRED] = IDS[0]

    def test_workspace_browse_preserves_reading_scope_and_noop_does_not_checkpoint(self):
        self.actions.browse(('BEING',))
        self.assertIsNone(self.store.get_state())
        self.actions.read(first=True)
        self.actions.move(1)
        self.actions.browse(('ESSENCE',))
        self.assertEqual(self.actions.cwd, ('ESSENCE',))
        self.assertEqual((self.actions.session.path, self.actions.session.cursor), (('BEING',), 1))
        state = self.store.get_state()
        self.assertEqual((state['cwd'], state['scope'], state['current_id']),
                         ('/ESSENCE', '/BEING', IDS[1]))
        self.actions.browse(('ESSENCE',))
        self.actions.search('ground', whole_word=True)
        self.actions.context()
        self.actions.locate()
        self.assertEqual(self.store.get_state(), state)
        self.assertEqual(len(self.store.list_history()), 3)

    def test_open_retired_reference_keeps_requested_id_in_checkpoint(self):
        self.retire_first()
        passage = self.actions.open(RETIRED)
        self.assertIs(passage, self.book.passages[0])
        self.assertEqual(self.reader.resumed_reference.requested_id, RETIRED)
        self.assertEqual(self.store.get_state()['current_id'], RETIRED)
        self.actions.browse(('ESSENCE',))
        self.assertEqual(self.store.get_state()['current_id'], RETIRED)
        self.actions.move(1)
        self.assertEqual(self.store.get_state()['current_id'], IDS[1])
        self.assertIsNone(self.reader.resumed_reference)

    def test_workspace_open_resolves_canonical_graph_not_projected_redirect_cache(self):
        self.retire_first()
        self.book.redirects.clear()
        passage = self.actions.open(RETIRED)
        self.assertIs(passage, self.book.passages[0])
        self.assertEqual(self.reader.resumed_reference.requested_id, RETIRED)
        self.assertEqual(self.reader.resumed_reference.target_id, IDS[0])
        self.assertEqual(self.store.get_state()['current_id'], RETIRED)

    def test_concurrent_checkpoint_rolls_back_all_local_navigation(self):
        self.retire_first()
        self.actions.open(RETIRED)
        self.actions.search('ground')
        before = self.state()
        with Workspace(self.path, CORPUS_ID, self.provenance, actor='Other') as other:
            newer = other.get_state()
            newer['current_id'] = IDS[2]
            other.save_state(newer, newer['revision'])
            for operation in (lambda: self.actions.browse(('ESSENCE',)),
                              lambda: self.actions.read(('ESSENCE',), first=True),
                              lambda: self.actions.move(1),
                              lambda: self.actions.open(IDS[2]),
                              lambda: self.actions.open_result(3)):
                with self.subTest(operation=operation), self.assertRaises(WorkspaceConflict):
                    operation()
                self.assertEqual(self.state(), before)
            self.assertEqual(other.get_state()['current_id'], IDS[2])

    def test_stale_corpus_checkpoint_rolls_back_navigation(self):
        self.actions.read(('BEING',), first=True)
        before = self.state()
        saved = self.store.get_state()
        with patch.object(self.reader, 'corpus_freshness',
                          return_value={'state': 'changed', 'reason': 'Invented generation change'}):
            for operation in (lambda: self.actions.browse(('ESSENCE',)),
                              lambda: self.actions.move(1),
                              lambda: self.actions.open(IDS[2])):
                with self.subTest(operation=operation), self.assertRaises(WorkspaceError):
                    operation()
                self.assertEqual(self.state(), before)
        self.assertEqual(self.store.get_state(), saved)

    def test_staged_moves_save_once_and_only_after_the_block_completes(self):
        self.actions.read(('BEING',), first=True)
        visits = len(self.store.list_history())
        with self.actions.staged():
            self.actions.move(1)
            self.actions.open(IDS[2])
            self.assertEqual(len(self.store.list_history()), visits)
            with self.assertRaises(RuntimeError):
                with self.actions.staged():
                    pass
        self.assertEqual(self.store.get_state()['current_id'], IDS[2])
        self.assertEqual(len(self.store.list_history()), visits + 1)
        self.actions.history_back()
        self.assertEqual(self.actions.session.current().identifier, IDS[1])

    def test_failed_staged_block_restores_local_state_and_saves_nothing(self):
        self.actions.read(('BEING',), first=True)
        self.actions.search('ground')
        before, saved, trail = self.state(), self.store.get_state(), self.actions.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'invented view failure'):
            with self.actions.staged():
                self.actions.move(1)
                raise RuntimeError('invented view failure')
        self.assertEqual((self.state(), self.store.get_state(), self.actions.snapshot()), (before, saved, trail))
        # A conflict at the single save is a failure of the block, too.
        with Workspace(self.path, CORPUS_ID, self.provenance, actor='Other') as other:
            newer = other.get_state()
            newer['current_id'] = IDS[2]
            other.save_state(newer, newer['revision'])
            with self.assertRaises(WorkspaceConflict):
                with self.actions.staged():
                    self.actions.move(1)
            self.assertEqual(self.state(), before)
            self.assertEqual(other.get_state()['current_id'], IDS[2])
        # Staging leaves no trace: the next ordinary move saves at once.
        self.reader.revision = self.store.get_state()['revision']
        self.actions.move(1)
        self.assertEqual(self.store.get_state()['current_id'], IDS[1])

    def test_reference_or_runtime_failure_restores_existing_cursor_and_reference(self):
        self.retire_first()
        self.actions.open(RETIRED)
        before = self.state()
        saved = self.store.get_state()
        with patch.object(self.reader, 'current_reference', side_effect=ValueError('Invalid reference')):
            with self.assertRaisesRegex(ValueError, 'Invalid reference'):
                self.actions.open(IDS[2])
        self.assertEqual(self.state(), before)
        with patch.object(self.reader, 'checkpoint', side_effect=RuntimeError('Unavailable workspace')):
            with self.assertRaisesRegex(RuntimeError, 'Unavailable workspace'):
                self.actions.move(1)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.store.get_state(), saved)

    def test_restore_latest_clears_results_without_creating_another_visit(self):
        self.actions.browse(('BEING',))
        self.actions.read(first=True)
        self.actions.move(1)
        self.actions.browse(('ESSENCE',))
        saved = self.store.get_state()
        restored = ReaderActions(self.book, self.reader)
        restored.search('ground')
        passage, message = restored.restore()
        self.assertIs(passage, self.book.passages[1])
        self.assertEqual(message, '')
        self.assertEqual((restored.cwd, restored.previous_cwd), (('ESSENCE',), ('BEING',)))
        self.assertEqual((restored.session.path, restored.session.cursor), (('BEING',), 1))
        self.assertEqual(restored.results, [])
        self.assertEqual(self.store.get_state(), saved)
        self.assertEqual(len(self.store.list_history()), 3)

    def test_historical_restore_is_one_new_visit_and_failed_restore_keeps_results(self):
        self.actions.read(('BEING',), first=True)
        self.actions.move(1)
        self.actions.search('ground')
        before = self.state()
        with self.assertRaises(ValueError):
            self.actions.restore(99)
        self.assertEqual(self.state(), before)
        passage, message = self.actions.restore(1)
        self.assertIs(passage, self.book.passages[0])
        self.assertIn('new revision 3', message)
        self.assertEqual(self.actions.results, [])
        self.assertEqual(self.store.get_history(2)['current_id'], IDS[1])
        self.assertEqual(self.store.get_state()['revision'], 3)
        self.assertEqual(len(self.store.list_history()), 3)

