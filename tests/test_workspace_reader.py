"""Persistent philosophical workflows using only invented, public test text."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sol
from sol_workspace import Workspace, WorkspaceConflict
from sol_workspace_reader import WorkspaceReader, resolve_reference, safe_output, workspace_path


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
                patch('sol.install_completion', return_value=lambda: None):
            status = sol.run_shell(self.book, 80, workspace_reader=reader or self.reader)
        return status, stdout.getvalue()

    def main(self, arguments):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
                patch('sol.discover_corpus', return_value=Path('/invented/corpus')), \
                patch('sol.load_corpus_book', return_value=self.book), \
                patch('sol.load_book', side_effect=AssertionError('PDF extraction forbidden')):
            status = sol.main(arguments)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_shell_reopens_same_uuid_and_independent_browsing_directory(self):
        status, output = self.shell(['cd /being', 'first', 'next', 'cd /essence', 'where', 'exit'])
        self.assertEqual(status, 0)
        self.assertNotIn('sol: ', output)
        self.assertIn('Position 2 of 2 in /BEING', output)
        state = self.store.get_state()
        self.assertEqual(state['current_id'], IDS[1])
        self.assertEqual(state['cwd'], '/ESSENCE')
        self.assertEqual(state['scope'], '/BEING')
        reopened = self.make_reader()
        _, output = self.shell(['where', 'pwd', 'exit'], reopened)
        self.assertIn(IDS[1], output)
        self.assertIn('Position 2 of 2 in /BEING', output)
        self.assertTrue(output.endswith('/ESSENCE\n'))

    def test_reordering_recomputes_cursor_by_uuid_not_numeric_position(self):
        self.session.read(('BEING',), first=True)
        self.session.move(1)
        self.reader.checkpoint(self.session, (), None)
        self.book.passages[:2] = list(reversed(self.book.passages[:2]))
        session = sol.ReadingSession(self.book)
        self.make_reader().restore(session)
        self.assertEqual(session.current().identifier, IDS[1])
        self.assertEqual(session.cursor, 0)

    def test_readonly_commands_and_failed_navigation_do_not_write_checkpoints(self):
        self.shell(['first /being', 'exit'])
        before = self.store.export()
        before.pop('exported_at')
        _, output = self.shell(['search invented', 'context 1', 'review show', 'note list',
                                'bookmark list', 'compare list', 'relate list', 'workspace history',
                                'previous', 'exit'], self.make_reader())
        self.assertIn('already at the beginning', output)
        after = self.store.export()
        after.pop('exported_at')
        self.assertEqual(after, before)

    def test_bookmark_roundtrip_duplicate_protection_and_explicit_replacement(self):
        self.session.read(('BEING',), first=True)
        self.reader.execute('bookmark', ['add', 'start'], self.session)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.reader.execute('bookmark', ['add', 'start', IDS[1]], self.session)
        self.reader.execute('bookmark', ['set', 'start', IDS[1]], self.session)
        result = self.make_reader().execute('bookmark', ['open', 'start'], self.session)
        self.assertEqual(result.open_id, IDS[1])

    def test_explicit_actor_is_required_for_each_kind_of_authored_write(self):
        reader = self.make_reader(actor=None)
        self.session.read((), first=True)
        commands = [('note', ['add', 'A note']),
                    ('compare', ['save', 'pair', IDS[0], IDS[1], '--question', 'Why?']),
                    ('review', ['record', 'inspected', '--issue', 'Checked']),
                    ('relate', ['add', IDS[0], 'compares-with', IDS[1], '--reason', 'Why'])]
        for verb, arguments in commands:
            with self.subTest(verb=verb), self.assertRaisesRegex(ValueError, '--actor'):
                reader.execute(verb, arguments, self.session)
        self.assertEqual(self.store.list_annotations(), [])
        self.assertEqual(self.store.list_comparisons(), [])
        self.assertEqual(self.store.list_reviews(), [])
        self.assertEqual(self.store.list_relations(), [])

    def test_annotation_keeps_unicode_markdown_author_and_target_digest(self):
        self.session.read((), first=True)
        body = 'An *interpretation* of α, not Hegel’s own prose.'
        self.reader.execute('note', ['add', body], self.session)
        note = self.store.list_annotations()[0]
        self.assertEqual(note['body'], body)
        self.assertEqual(note['attribution']['author'], 'Ada')
        self.assertEqual(note['content_sha256'], self.book.canonical_records[IDS[0]]['content_sha256'])
        self.book.canonical_records[IDS[0]]['content_sha256'] = '1' * 64
        self.assertIn('target text changed', self.reader.execute('note', ['list'], self.session).text)

    def test_comparison_is_ordered_attributed_and_does_not_move_cursor(self):
        self.session.read((), first=True)
        before = (self.session.path, self.session.cursor)
        self.reader.execute('compare', ['save', 'pair', IDS[2], IDS[0], '--question', 'What returns?'], self.session)
        output = self.reader.execute('compare', ['show', 'pair'], self.session).text
        self.assertIn('By Ada', output)
        self.assertIn('What returns?', output)
        self.assertLess(output.index(IDS[2]), output.index(IDS[0]))
        self.assertEqual((self.session.path, self.session.cursor), before)

    def test_review_is_readonly_and_decisions_become_stale_after_correction(self):
        self.session.read((), first=True)
        original = json.dumps(self.book.canonical_records, sort_keys=True)
        output = self.reader.execute('review', ['show'], self.session).text
        self.assertIn('*invented*', output)
        self.assertIn('PDF transcription', output)
        self.reader.execute('review', ['record', 'verified', '--issue', 'Reader testimony only'], self.session)
        self.assertEqual(json.dumps(self.book.canonical_records, sort_keys=True), original)
        self.assertIn('current inspected version', self.reader.execute('review', ['list'], self.session).text)
        self.book.canonical_records[IDS[0]]['content_sha256'] = '2' * 64
        self.assertIn('STALE', self.reader.execute('review', ['list'], self.session).text)

    def test_notes_and_editorial_records_can_be_inspected_without_main_text_misattribution(self):
        output = self.reader.execute('review', ['show', IDS[3]], self.session).text
        self.assertIn('Invented editor | editorial_note', output)
        self.reader.execute('note', ['add', 'Editorial inquiry', '--on', IDS[3]], self.session)
        self.assertEqual(self.store.list_annotations()[0]['target_id'], IDS[3])

    def test_relation_is_directed_reader_assertion_and_tree_is_unchanged(self):
        before = json.dumps(self.book.canonical_records, sort_keys=True)
        self.reader.execute('relate', ['add', IDS[0], 'presupposes', IDS[2], '--reason', 'A hypothesis to argue'], self.session)
        relation = self.store.list_relations()[0]
        self.assertEqual((relation['source_id'], relation['target_id']), (IDS[0], IDS[2]))
        self.assertEqual(relation['evidence_origin'], 'reader')
        self.assertEqual(json.dumps(self.book.canonical_records, sort_keys=True), before)

    def test_missing_saved_reference_remains_visible_in_checkpoint_and_history(self):
        self.session.read((), first=True)
        self.reader.checkpoint(self.session, (), None)
        del self.book.canonical_records[IDS[0]]
        self.book.passages.pop(0)
        _, output = self.shell(['workspace history', 'first /essence', 'exit'], self.make_reader())
        self.assertIn('saved position not restored', output)
        self.assertIn('unresolved', output)
        history = self.store.list_history()
        self.assertTrue(any(row['current_id'] == IDS[0] for row in history))
        self.assertEqual(self.store.get_state()['current_id'], IDS[2])

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
                     ['--workspace', 'x', '--pdf', 'absent.pdf'],
                     ['--workspace', 'x', '--structure'], ['--workspace', 'x', '--search', 'ground']]:
            with self.subTest(args=args):
                status, _, stderr = self.main(args)
                self.assertEqual(status, 2, stderr)
        self.assertFalse((self.directory / 'x.sqlite3').exists())

    def test_standard_shell_never_opens_workspace_storage(self):
        with patch('sol_workspace.Workspace', side_effect=AssertionError('No database for ordinary shell')), \
                patch('builtins.input', side_effect=['first /being', 'exit']), \
                patch('sol.install_completion', return_value=lambda: None):
            status, _, stderr = self.main(['--shell'])
        self.assertEqual(status, 0, stderr)

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

    def test_shell_rolls_back_local_navigation_on_concurrent_checkpoint_conflict(self):
        self.session.read((), first=True)
        self.reader.checkpoint(self.session, (), None)
        with Workspace(self.path, CORPUS_ID, self.provenance, actor='Other') as other:
            commands = iter(['next', 'where', 'resume', 'where', 'exit'])
            def entered(prompt):
                command = next(commands)
                if command == 'next':
                    state = other.get_state()
                    state['current_id'] = IDS[2]
                    other.save_state(state, state['revision'])
                return command
            stdout = StringIO()
            with redirect_stdout(stdout), patch('builtins.input', side_effect=entered), \
                    patch('sol.ReadingSession', return_value=self.session), \
                    patch('sol.install_completion', return_value=lambda: None):
                self.assertEqual(sol.run_shell(self.book, 80, workspace_reader=self.reader), 0)
        output = stdout.getvalue()
        self.assertIn('sol: ', output)
        self.assertIn('Position 1 of 3 in /', output)
        self.assertIn('Position 3 of 3 in /', output)
        self.assertEqual(self.session.current().identifier, IDS[2])

    def test_retirement_requires_reconsidering_review_even_if_text_is_unchanged(self):
        self.session.read((), first=True)
        self.reader.execute('review', ['record', 'verified', '--issue', 'Checked original'], self.session)
        self.book.canonical_records[IDS[0]] = {'id': IDS[0], 'type': 'retired_record', 'redirect_id': IDS[1]}
        self.book.canonical_records[IDS[1]]['content_sha256'] = self.store.list_reviews()[0]['content_sha256']
        self.assertIn('STALE', self.reader.execute('review', ['list'], self.session).text)

    def test_authored_assertions_require_explicit_nonempty_explanation(self):
        self.session.read((), first=True)
        commands = [('compare', ['save', 'pair', IDS[0], IDS[1], '--question', '']),
                    ('review', ['record', 'verified', '--issue', '']),
                    ('relate', ['add', IDS[0], 'sublates', IDS[1], '--reason', ''])]
        for verb, arguments in commands:
            with self.subTest(verb=verb), self.assertRaisesRegex(ValueError, 'nonempty'):
                self.reader.execute(verb, arguments, self.session)

    def test_explicitly_empty_names_and_identifiers_are_not_treated_as_defaults(self):
        self.session.read((), first=True)
        status, _, _ = self.main(['--workspace', ''])
        self.assertEqual(status, 2)
        status, _, _ = self.main(['--workspace', 'reading', '--actor', '', '--workspace-dir', str(self.directory)])
        self.assertEqual(status, 2)
        for verb, arguments in [('note', ['add', 'Text', '--on', '']), ('note', ['list', '--on', '']),
                                ('review', ['show', '']), ('review', ['list', '--on', '']),
                                ('relate', ['list', '--on', ''])]:
            with self.subTest(verb=verb, arguments=arguments), self.assertRaises(ValueError):
                self.reader.execute(verb, arguments, self.session)


if __name__ == '__main__':
    unittest.main()
