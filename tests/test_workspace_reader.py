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
                patch('sol.reader.app.install_completion', return_value=lambda: None):
            status = sol.run_shell(self.book, 80, workspace_reader=reader or self.reader)
        return status, stdout.getvalue()

    def main(self, arguments):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
                patch('sol.reader.app.discover_corpus', return_value=Path('/invented/corpus')), \
                patch('sol.reader.app.load_corpus_book', return_value=self.book), \
                patch('sol.reader.app.load_book', side_effect=AssertionError('PDF extraction forbidden')):
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
        output = self.reader.execute('review', ['list'], self.session).text
        self.assertIn('same text/PDF fingerprints; PDF hash is manifest-declared', output)
        self.assertIn('record metadata is not bound', output)
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
        with patch('sol.workspace.store.Workspace', side_effect=AssertionError('No database for ordinary shell')), \
                patch('builtins.input', side_effect=['first /being', 'exit']), \
                patch('sol.reader.app.install_completion', return_value=lambda: None):
            status, _, stderr = self.main(['-n'])
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
                    patch('sol.reader.app.ReadingSession', return_value=self.session), \
                    patch('sol.reader.app.install_completion', return_value=lambda: None):
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

    def test_nullable_history_is_displayed_without_a_crash(self):
        self.store.save_state({'cwd': '/', 'scope': '/', 'current_id': None, 'previous_cwd': None})
        output = self.reader.execute('workspace', ['history', '--limit', '1'], self.session).text
        self.assertIn('[no saved passage]', output)

    def test_health_report_is_readonly_and_separates_pending_flags_from_testimony(self):
        self.session.read((), first=True)
        self.reader.checkpoint(self.session, (), None)
        self.book.canonical_records[IDS[0]]['transcription_status'] = 'needs_visual_review'
        self.reader.execute('review', ['record', 'verified', '--issue', 'Reader testimony only'], self.session)
        before = self.store.get_state()
        report = self.reader.health()
        self.assertEqual(report['counts']['pending_source_review'], 1)
        self.assertEqual(report['review_provenance_binding'], 'text_and_pdf_fingerprint_only')
        self.assertEqual(self.store.get_state(), before)
        self.book.canonical_records.pop(IDS[0])
        report = self.reader.health()
        self.assertGreater(report['counts']['unresolved_references'], 0)
        self.assertEqual(report['status'], 'attention_required')

    def test_review_queue_can_include_editorial_material_and_filter_by_virtual_path(self):
        self.book.canonical_records[IDS[0]]['transcription_status'] = 'needs_visual_review'
        self.book.canonical_records[IDS[3]]['transcription_status'] = 'needs_review'
        rows = self.reader.queue()
        self.assertEqual({row['id'] for row in rows}, {IDS[0], IDS[3]})
        self.assertEqual(self.reader.queue(('ESSENCE',)), [])
        output = self.reader.execute('review', ['queue', '--within', '/being', '--limit', '1'], self.session).text
        self.assertIn(IDS[0], output)
        self.assertNotIn(IDS[3], output)

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

    def test_queue_without_workspace_uses_no_database_and_backup_never_overwrites(self):
        self.book.canonical_records[IDS[0]]['transcription_status'] = 'needs_review'
        with patch('sol.workspace.store.Workspace', side_effect=AssertionError('No workspace database')):
            status, output, error = self.main(['--review-queue', '--json'])
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)[0]['id'], IDS[0])
        destination = self.directory / 'existing.sqlite3'
        destination.write_bytes(b'A file to preserve')
        before = self.store.get_state()
        with self.assertRaises(ValueError):
            self.reader.execute('workspace', ['backup', str(destination)], self.session)
        self.assertEqual(destination.read_bytes(), b'A file to preserve')
        self.assertEqual(self.store.get_state(), before)

    def test_workspace_commands_reject_options_in_the_wrong_context(self):
        for arguments in [['check', '--limit', '1'], ['backup'], ['history', '/tmp/extra'], ['export', '--limit', '1']]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.reader.execute('workspace', arguments, self.session)
        for args in [['--resume-revision', '1'], ['--workspace-backup', str(self.directory / 'b.sqlite3')],
                     ['--workspace-check'], ['--word', '--review-queue']]:
            with self.subTest(args=args):
                status, _, _ = self.main(args)
                self.assertEqual(status, 2)

    def test_injected_input_output_uses_same_commands_and_no_readline_or_ui_import(self):
        commands = iter(['first /being', 'note add "An adapter note."', 'where', 'exit'])
        stdout = StringIO()
        prompts = []
        def read_command(prompt):
            prompts.append(prompt)
            return next(commands)
        def emit(*values, **options):
            print(*values, file=stdout, **options)
        with patch('sol.reader.app.install_completion', side_effect=AssertionError('Custom adapter owns completion')):
            status = sol.run_shell(self.book, 80, workspace_reader=self.reader,
                                   read_command=read_command, write_output=emit)
        self.assertEqual(status, 0)
        self.assertEqual(len(prompts), 4)
        self.assertIn('Position 1 of 2', stdout.getvalue())
        self.assertEqual(self.store.list_annotations()[0]['body'], 'An adapter note.')
        self.assertEqual(self.store.get_state()['current_id'], IDS[0])

    def test_injected_input_interrupt_and_eof_preserve_workspace(self):
        commands = iter([KeyboardInterrupt(), EOFError()])
        def read_command(prompt):
            raise next(commands)
        stdout = StringIO()
        with redirect_stdout(stdout):
            status = sol.run_shell(self.book, 80, workspace_reader=self.reader, read_command=read_command)
        self.assertEqual(status, 0)
        self.assertIn("Type 'exit' to leave", stdout.getvalue())
        self.assertIsNone(self.store.get_state())

    def test_invalid_adapter_result_does_not_fall_back_to_host_input(self):
        commands = iter([None, 'exit'])
        stdout = StringIO()
        with redirect_stdout(stdout), patch('builtins.input', side_effect=AssertionError('No host-input fallback')):
            status = sol.run_shell(self.book, 80, read_command=lambda prompt: next(commands))
        self.assertEqual(status, 0)
        self.assertIn('command input must be text', stdout.getvalue())

    def test_annotation_draft_stores_raw_multiline_text_once_without_changing_checkpoint(self):
        body = '--flaglike text with "quotes"\n\n*An interpretation of α.*'
        commands = iter(['first /being', 'note draft', 'exit'])
        stdout = StringIO()
        with redirect_stdout(stdout):
            status = sol.run_shell(self.book, 80, workspace_reader=self.reader,
                                   read_command=lambda prompt: next(commands), draft_reader=lambda prompt: body)
        self.assertEqual(status, 0)
        records = self.store.list_annotations()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['body'], body)
        self.assertEqual(records[0]['actor'], 'Ada')
        self.assertEqual(records[0]['target_id'], IDS[0])
        self.assertEqual(self.store.get_state()['revision'], 1)

    def test_cancelled_or_empty_draft_preserves_annotations_and_checkpoint(self):
        for result in (KeyboardInterrupt(), EOFError(), ''):
            with self.subTest(result=result):
                commands = iter(['first /being', 'note draft', 'exit'])
                def draft(prompt):
                    if isinstance(result, BaseException):
                        raise result
                    return result
                stdout = StringIO()
                with redirect_stdout(stdout):
                    status = sol.run_shell(self.book, 80, workspace_reader=self.make_reader(),
                                           read_command=lambda prompt: next(commands), draft_reader=draft)
                self.assertEqual(status, 0)
                self.assertEqual(self.store.list_annotations(), [])
        self.assertEqual(len(self.store.list_history()), 3)

    def test_draft_actor_or_target_changes_refuse_commit(self):
        for change in ('actor', 'store_actor', 'target'):
            with self.subTest(change=change):
                reader = self.make_reader()
                self.store.actor = 'Ada'
                commands = iter(['first /being', 'note draft', 'exit'])
                def draft(prompt):
                    if change == 'actor':
                        reader.actor = 'Other'
                    elif change == 'store_actor':
                        self.store.actor = 'Other'
                    else:
                        self.book.canonical_records[IDS[0]]['content_sha256'] = '1' * 64
                    return 'A draft that must not be misattributed or moved.'
                with redirect_stdout(StringIO()):
                    status = sol.run_shell(self.book, 80, workspace_reader=reader,
                                           read_command=lambda prompt: next(commands), draft_reader=draft)
                self.assertEqual(status, 0)
                self.assertEqual(self.store.list_annotations(), [])

    def test_draft_requires_actor_and_enhanced_input_before_opening_editor(self):
        commands = iter(['first /being', 'note draft', 'exit'])
        with redirect_stdout(StringIO()):
            self.assertEqual(sol.run_shell(self.book, 80, workspace_reader=self.reader,
                                          read_command=lambda prompt: next(commands)), 0)
        self.assertEqual(self.store.list_annotations(), [])
        commands = iter(['note draft', 'exit'])
        with redirect_stdout(StringIO()):
            self.assertEqual(sol.run_shell(self.book, 80, workspace_reader=self.make_reader(actor=None),
                                          read_command=lambda prompt: next(commands),
                                          draft_reader=lambda prompt: self.fail('No draft without actor')), 0)

    def test_changed_canonical_generation_refuses_writes_without_reading_pdf(self):
        import sol.corpus.contract as contract
        from test_packaging import write_runtime_corpus
        corpus = self.directory / 'actual-corpus'
        write_runtime_corpus(corpus)
        contract.initialize_corpus_identity(corpus)
        book = sol.load_corpus_book(corpus)
        with Workspace(self.directory / 'guarded.sqlite3', book.corpus_manifest['corpus_id'],
                       {'source': book.corpus_manifest['source']}, actor='Ada') as store:
            reader = WorkspaceReader(book, store, 'Ada', sol.resolve_path, sol.display_path, sol.render_passage)
            session = sol.ReadingSession(book)
            session.read((), first=True)
            reader.checkpoint(session, (), None)
            self.assertEqual(reader.corpus_freshness()['state'], 'current')
            document = corpus / 'sample.md'
            document.write_text(document.read_text(encoding='utf-8') + '\n', encoding='utf-8')
            with patch('sol.reader.app.load_book', side_effect=AssertionError('Never read the PDF')):
                with self.assertRaisesRegex(ValueError, 'loaded corpus changed'):
                    reader.execute('note', ['add', 'Preserve against stale generation'], session)
                with self.assertRaisesRegex(ValueError, 'loaded corpus changed'):
                    reader.checkpoint(session, (), None)
            self.assertEqual(store.list_annotations(), [])
            self.assertEqual(store.get_state()['revision'], 1)
            report = reader.health()
            self.assertEqual(report['corpus_freshness']['state'], 'changed')
            self.assertEqual(report['status'], 'attention_required')

    def test_source_changed_during_draft_refuses_one_insert_and_preserves_checkpoint(self):
        import sol.corpus.contract as contract
        from test_packaging import write_runtime_corpus
        corpus = self.directory / 'draft-corpus'
        write_runtime_corpus(corpus)
        contract.initialize_corpus_identity(corpus)
        book = sol.load_corpus_book(corpus)
        with Workspace(self.directory / 'draft-guarded.sqlite3', book.corpus_manifest['corpus_id'],
                       {'source': book.corpus_manifest['source']}, actor='Ada') as store:
            reader = WorkspaceReader(book, store, 'Ada', sol.resolve_path, sol.display_path, sol.render_passage)
            commands = iter(['first /being', 'note draft', 'exit'])
            def draft(prompt):
                document = corpus / 'sample.md'
                document.write_text(document.read_text(encoding='utf-8') + '\n', encoding='utf-8')
                return 'An annotation based on a now-stale source.'
            stdout = StringIO()
            with redirect_stdout(stdout), patch('sol.reader.app.load_book', side_effect=AssertionError('Never read the PDF')):
                self.assertEqual(sol.run_shell(book, 80, workspace_reader=reader,
                                              read_command=lambda prompt: next(commands), draft_reader=draft), 0)
            self.assertIn('loaded corpus changed', stdout.getvalue())
            self.assertEqual(store.list_annotations(), [])
            self.assertEqual(store.get_state()['revision'], 1)


if __name__ == '__main__':
    unittest.main()
