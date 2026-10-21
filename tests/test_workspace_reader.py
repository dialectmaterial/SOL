"""Persistent philosophical workflows using only invented, public test text."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr, nullcontext
from dataclasses import replace
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sol.reader.app as sol
from sol.workspace.store import Workspace, WorkspaceConflict
from sol.workspace.reader import WorkspaceReader, resolve_reference, safe_output, workspace_path


CORPUS_ID = 'dddddddd-0000-4000-8000-000000000001'
IDS = [f'aaaaaaaa-0000-4000-8000-{i:012d}' for i in range(1, 5)]


def invented_book():
    root = sol.Node('', 'Invented book', 7)
    being = sol.Node('BEING', 'Being', 7, parent=root)
    leaf = sol.Node('01-quality.txt', 'Quality', 7, parent=being)
    essence = sol.Node('ESSENCE', 'Essence', 12, parent=root)
    other = sol.Node('01-ground.txt', 'Ground', 12, parent=essence)
    concept = sol.Node('CONCEPT', 'Concept', 15, parent=root)
    root.children = (being, essence, concept)
    being.children, essence.children = (leaf,), (other,)
    bodies = ['An *invented* paragraph provides a durable first reading position for this test.',
              'A second invented paragraph gives this test a place to continue its reading.',
              'An invented passage in another doctrine supports comparison and deliberate navigation.']
    passages, records = [], {}
    for i, body in enumerate(bodies):
        node, page = (leaf, 7 + i) if i < 2 else (other, 12)
        path = sol.node_path(node)
        passages.append(sol.Passage(body.replace('*', ''), page + 73, page, node, path, page + 73,
                                    page, IDS[i], node.title))
        records[IDS[i]] = {'id': IDS[i], 'type': 'paragraph', 'parent_id': None, 'order': i,
                          'reader_path': sol.display_path(path), 'reader_title': node.title,
                          'sources': [{'pdf_page': page + 73, 'printed_page': str(page)}],
                          'markdown': body, 'plain_text': body.replace('*', ''), 'document': 'sample.md',
                          'attribution': {'author': 'G. W. F. Hegel', 'role': 'main_text', 'status': 'confirmed'},
                          'content_sha256': hashlib.sha256(body.encode()).hexdigest()}
    records[IDS[3]] = {**records[IDS[0]], 'id': IDS[3], 'type': 'note',
                      'attribution': {'author': 'Invented editor', 'role': 'editorial_note', 'status': 'confirmed'}}
    return sol.Book(root, passages, {}, records, Path('/invented/corpus'),
                    {'corpus_id': CORPUS_ID, 'edition': {'title': 'Invented edition'},
                     'source': {'sha256': '0' * 64, 'filename': 'absent.pdf'}})


class WorkspaceReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sol-reader-workspace-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.book = invented_book()
        self.path = self.directory / 'reading.sqlite3'
        self.provenance = {key: self.book.corpus_manifest[key] for key in ('edition', 'source')}
        self.store = Workspace(self.path, CORPUS_ID, self.provenance, actor='Ada')
        self.addCleanup(self.store.close)
        self.session = sol.ReadingSession(self.book)
        self.reader = self.make_reader()

    def make_reader(self, store=None, actor='Ada'):
        return WorkspaceReader(self.book, store or self.store, actor, sol.resolve_path,
                               sol.display_path, sol.render_passage)

    def shell(self, commands, reader=None):
        stdout = StringIO()
        with redirect_stdout(stdout), patch('builtins.input', side_effect=commands), \
                patch('sol.reader.shell.install_completion', return_value=lambda: None):
            status = sol.run_shell(self.book, 80, workspace_reader=reader or self.reader)
        return status, stdout.getvalue()

    def main(self, arguments):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
                patch('sol.reader.app.discover_corpus', return_value=Path('/invented/corpus')), \
                patch('sol.reader.app.load_corpus_book', return_value=self.book), \
                nullcontext():
            status = sol.main(arguments)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_reordering_recomputes_cursor_by_uuid_not_numeric_position(self):
        self.session.read(('BEING',), first=True)
        self.session.move(1)
        self.reader.checkpoint(self.session, (), None)
        self.book.passages[:2] = list(reversed(self.book.passages[:2]))
        session = sol.ReadingSession(self.book)
        self.make_reader().restore(session)
        self.assertEqual(session.current().identifier, IDS[1])
        self.assertEqual(session.cursor, 0)

    def test_retired_reference_discloses_chain_and_preserves_requested_id(self):
        retired = 'eeeeeeee-0000-4000-8000-000000000001'
        self.book.canonical_records[retired] = {'id': retired, 'type': 'retired_record', 'redirect_id': IDS[0]}
        self.book.redirects[retired] = IDS[0]
        self.store.save_state({'cwd': '/', 'scope': '/BEING', 'current_id': retired, 'previous_cwd': None}, None)
        reader = self.make_reader()
        _, _, _, message = reader.restore(self.session)
        self.assertIn(retired + ' -> ' + IDS[0], message)
        reader.checkpoint(self.session, (), None)
        self.assertEqual(self.store.get_state()['current_id'], retired)

    def test_conflicting_session_does_not_silently_overwrite_saved_position(self):
        self.session.read((), first=True)
        self.reader.checkpoint(self.session, (), None)
        with Workspace(self.path, CORPUS_ID, self.provenance, actor='Other') as other:
            reader = self.make_reader(other)
            session = sol.ReadingSession(self.book)
            reader.restore(session)
            reader.checkpoint(session, (), None)
        self.session.move(1)
        with self.assertRaises(WorkspaceConflict):
            self.reader.checkpoint(self.session, (), None)
        self.assertEqual(self.store.get_state()['current_id'], IDS[0])

    def test_plain_resume_json_and_portable_export_work_without_pdf(self):
        args = ['--workspace', 'reading', '--workspace-dir', str(self.directory)]
        status, output, stderr = self.main(args + ['--first', '/being', '--json'])
        self.assertEqual(status, 0, stderr)
        data = json.loads(output)
        self.assertEqual(data['id'], IDS[0])
        self.assertEqual(data['corpus']['id'], CORPUS_ID)
        self.assertEqual(data['corpus']['source']['sha256'], '0' * 64)
        status, output, stderr = self.main(args + ['--resume', '--plain'])
        self.assertEqual(status, 0, stderr)
        self.assertNotIn(IDS[0], output)
        status, output, stderr = self.main(args + ['--resume', '--json'])
        self.assertEqual(status, 0, stderr)
        self.assertEqual(json.loads(output)['workspace']['corpus_id'], CORPUS_ID)
        status, output, stderr = self.main(args + ['--workspace-export'])
        self.assertEqual(status, 0, stderr)
        exported = json.loads(output)
        self.assertEqual(exported['state']['current_id'], IDS[0])
        self.assertNotIn('invented', json.dumps(exported))

    def test_workspace_requires_initialized_identity_and_does_not_create_db_on_error(self):
        del self.book.corpus_manifest['corpus_id']
        status, _, stderr = self.main(['--workspace', 'uninitialized', '--workspace-dir', str(self.directory), '--first', '/being'])
        self.assertEqual(status, 2)
        self.assertIn('--initialize-identity', stderr)
        self.assertFalse((self.directory / 'uninitialized.sqlite3').exists())

    def test_incompatible_options_fail_before_loading_or_creating_workspace(self):
        for args in [['--resume'], ['--actor', 'Ada'], ['--workspace-dir', str(self.directory)],
                     ['--workspace', 'x', '--structure'], ['--workspace', 'x', '--search', 'ground']]:
            with self.subTest(args=args):
                status, _, stderr = self.main(args)
                self.assertEqual(status, 2, stderr)
        self.assertFalse((self.directory / 'x.sqlite3').exists())

    def test_workspace_names_and_environment_do_not_allow_path_traversal(self):
        for name in ('../escape', '/absolute', '', 'x/y', 'a' * 65):
            with self.subTest(name=name), self.assertRaises(ValueError):
                workspace_path(name, self.directory)
        with patch.dict('os.environ', {'XDG_DATA_HOME': 'relative'}), self.assertRaises(ValueError):
            workspace_path('study')

    def test_terminal_controls_are_displayed_as_literal_escapes(self):
        self.assertEqual(safe_output('safe\x1b[31m\ntext'), 'safe\\x1b[31m\ntext')
        self.assertEqual(safe_output('a\u202eb'), 'a\\u202eb')

    def test_failed_resume_does_not_adopt_another_sessions_unresolved_revision(self):
        self.session.read((), first=True)
        self.reader.checkpoint(self.session, (), None)
        revision = self.reader.revision
        with Workspace(self.path, CORPUS_ID, self.provenance) as other:
            state = other.get_state()
            state['current_id'] = 'ffffffff-0000-4000-8000-000000000001'
            other.save_state(state, state['revision'])
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            self.reader.restore(self.session)
        self.assertEqual(self.reader.revision, revision)
        with self.assertRaises(WorkspaceConflict):
            self.reader.checkpoint(self.session, (), None)

    def test_historical_resume_creates_a_new_checkpoint_without_erasing_history(self):
        self.session.read((), first=True)
        self.reader.checkpoint(self.session, (), None)
        self.session.move(1)
        self.reader.checkpoint(self.session, ('ESSENCE',), ())
        _, _, passage, message = self.reader.restore(self.session, 1)
        self.assertEqual(passage.identifier, IDS[0])
        self.assertEqual(self.store.get_state()['revision'], 3)
        self.assertEqual(self.store.get_history(2)['current_id'], IDS[1])
        self.assertIn('new revision 3', message)
        self.assertEqual(len(self.store.list_history()), 3)

    def test_bad_historical_resume_preserves_live_session_and_database(self):
        self.session.read((), first=True)
        self.reader.checkpoint(self.session, (), None)
        before = (self.session.path, self.session.cursor, self.reader.revision)
        for value in (0, -1, 99, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.reader.restore(self.session, value)
            self.assertEqual((self.session.path, self.session.cursor, self.reader.revision), before)
            self.assertEqual(self.store.get_state()['revision'], 1)

    def test_historical_resume_conflict_does_not_mutate_live_cursor(self):
        self.session.read((), first=True)
        self.reader.checkpoint(self.session, (), None)
        self.session.move(1)
        self.reader.checkpoint(self.session, (), None)
        with Workspace(self.path, CORPUS_ID, self.provenance) as other:
            original = self.store.save_state
            def contested(state, expected_revision):
                newer = other.get_state()
                newer['current_id'] = IDS[2]
                other.save_state(newer, newer['revision'])
                return original(state, expected_revision)
            with patch.object(self.store, 'save_state', side_effect=contested), self.assertRaises(WorkspaceConflict):
                self.reader.restore(self.session, 1)
        self.assertEqual(self.session.current().identifier, IDS[1])
        self.assertEqual(self.reader.revision, 2)
        self.assertEqual(self.store.get_state()['current_id'], IDS[2])

    def test_cli_health_queue_backup_and_historical_resume_are_machine_readable(self):
        args = ['--workspace', 'reading', '--workspace-dir', str(self.directory)]
        for identifier in (IDS[0], IDS[1]):
            status, _, error = self.main(args + ['--passage', identifier])
            self.assertEqual(status, 0, error)
        status, output, error = self.main(args + ['--resume', '--resume-revision', '1', '--json'])
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)['id'], IDS[0])
        self.assertEqual(json.loads(output)['workspace']['revision'], 3)
        status, output, error = self.main(args + ['--workspace-check', '--json'])
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)['format'], 'sol-workspace-health')
        self.book.canonical_records[IDS[0]]['transcription_status'] = 'needs_review'
        status, output, error = self.main(args + ['--review-queue', '--within', '/being', '--limit', '1', '--json'])
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)[0]['id'], IDS[0])
        destination = self.directory / 'backup.sqlite3'
        status, output, error = self.main(args + ['--workspace-backup', str(destination), '--json'])
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)['backup'], str(destination))
        with Workspace(destination, CORPUS_ID, self.provenance) as backup:
            self.assertEqual(backup.get_state()['revision'], 3)


if __name__ == '__main__':
    unittest.main()
