"""Reader and input boundaries for audited personal notes; all data invented."""
from contextlib import closing, redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import sol.reader.app as sol
from sol.workspace.store import APPLICATION_ID, Workspace, _SCHEMA
from sol.workspace.reader import WorkspaceReader
from test_workspace_reader import invented_book, CORPUS_ID, IDS


def legacy_workspace(path, provenance):
    with closing(sqlite3.connect(path)) as connection, connection:
        for statement in _SCHEMA:
            connection.execute(statement)
        connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
        connection.execute('PRAGMA user_version=1')
        connection.execute('INSERT INTO workspace_metadata VALUES(1,1,?,?,?)',
                           (CORPUS_ID, json.dumps(provenance), '2026-10-12T00:00:00Z'))


class AnnotationEditingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sol-editing-test-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.book = invented_book()
        self.provenance = {key: self.book.corpus_manifest[key] for key in ('edition', 'source')}
        self.store = Workspace(self.directory / 'study.sqlite3', CORPUS_ID, self.provenance, actor='Ada')
        self.addCleanup(self.store.close)
        self.reader = self.make_reader()
        self.session = sol.ReadingSession(self.book)
        self.session.read(('BEING',), first=True)
        self.reader.checkpoint(self.session, (), None)
        self.note = self.store.add_annotation(IDS[0], 'An original interpretation.',
                                              self.book.canonical_records[IDS[0]]['content_sha256'])

    def make_reader(self, store=None, actor='Ada'):
        return WorkspaceReader(self.book, store or self.store, actor, sol.resolve_path,
                               sol.display_path, sol.render_passage)

    def shell(self, commands, draft_reader=None, reader=None):
        commands = iter(commands)
        output = StringIO()
        with redirect_stdout(output):
            status = sol.run_shell(self.book, 80, workspace_reader=reader or self.reader,
                                   read_command=lambda prompt: next(commands), draft_reader=draft_reader)
        return status, output.getvalue()

    def test_basic_edit_requires_shown_revision_and_keeps_source_and_position(self):
        with self.assertRaisesRegex(ValueError, '--expect-revision'):
            self.reader.execute('note', ['edit', self.note['id'], 'Replacement without revision'], self.session)
        self.assertEqual(len(self.store.list_annotation_history(self.note['id'])), 1)
        state = self.store.get_state()
        outcome = self.reader.execute('note', ['edit', self.note['id'], 'A reconsidered interpretation.',
                                              '--expect-revision', '1'], self.session)
        self.assertIn('revision 2', outcome.text)
        current = self.store.get_annotation(self.note['id'])
        for field in ('id', 'actor', 'created_at', 'target_id', 'content_sha256'):
            self.assertEqual(current[field], self.note[field])
        self.assertEqual(self.store.get_state(), state)
        shown = self.reader.execute('note', ['show', self.note['id']], self.session).text
        self.assertIn('revision 2', shown)
        history = self.reader.execute('note', ['history', self.note['id']], self.session).text
        self.assertIn('An original interpretation.', history)
        self.assertIn('A reconsidered interpretation.', history)

    def test_enhanced_editor_receives_original_body_and_commits_raw_multiline_once(self):
        calls = []
        body = '--flaglike literal prose.\n\n*Another interpretation of α.*'
        def editor(prompt, default):
            calls.append((prompt, default))
            return body
        state = self.store.get_state()
        status, output = self.shell([f'note edit {self.note["id"]}', 'exit'], editor)
        self.assertEqual(status, 0)
        self.assertIn('revised', output)
        self.assertEqual(calls, [('Edit personal note: ', self.note['body'])])
        self.assertEqual(self.store.get_annotation(self.note['id'])['body'], body)
        self.assertEqual(len(self.store.list_annotation_history(self.note['id'])), 2)
        self.assertEqual(self.store.get_state(), state)

    def test_cancel_empty_and_unchanged_edits_do_not_append_revisions(self):
        for result in (KeyboardInterrupt(), EOFError(), '', self.note['body']):
            with self.subTest(result=result):
                def editor(prompt, default):
                    if isinstance(result, BaseException):
                        raise result
                    return result
                state = self.store.get_state()
                status, _ = self.shell([f'note edit {self.note["id"]}', 'exit'], editor)
                self.assertEqual(status, 0)
                self.assertEqual(self.store.get_annotation(self.note['id'])['revision'], 1)
                self.assertEqual(self.store.get_state(), state)

    def test_competing_editor_save_is_detected_after_drafting(self):
        other = Workspace(self.store.path, CORPUS_ID, self.provenance, actor='Ada')
        self.addCleanup(other.close)
        def editor(prompt, default):
            other.update_annotation(self.note['id'], 'The competing saved interpretation.', expected_revision=1)
            return 'The stale editor must not overwrite this.'
        status, output = self.shell([f'note edit {self.note["id"]}', 'exit'], editor)
        self.assertEqual(status, 0)
        self.assertIn('sol:', output)
        self.assertEqual(self.store.get_annotation(self.note['id'])['body'], 'The competing saved interpretation.')
        self.assertEqual(len(self.store.list_annotation_history(self.note['id'])), 2)

    def test_actor_or_canonical_target_changes_refuse_edit(self):
        for change in ('actor', 'store_actor', 'digest'):
            with self.subTest(change=change):
                original_digest = self.book.canonical_records[IDS[0]]['content_sha256']
                reader = self.make_reader()
                self.store.actor = 'Ada'
                def editor(prompt, default):
                    if change == 'actor':
                        reader.actor = 'Other'
                    elif change == 'store_actor':
                        self.store.actor = 'Other'
                    else:
                        self.book.canonical_records[IDS[0]]['content_sha256'] = '1' * 64
                    return 'A misbound edit that must not be saved.'
                status, output = self.shell([f'note edit {self.note["id"]}', 'exit'], editor, reader)
                self.assertEqual(status, 0)
                self.assertIn('nothing was saved', output)
                self.assertEqual(self.store.get_annotation(self.note['id'])['revision'], 1)
                self.book.canonical_records[IDS[0]]['content_sha256'] = original_digest
        self.store.actor = 'Ada'

    def test_editing_does_not_turn_stale_note_binding_into_new_source_evidence(self):
        self.book.canonical_records[IDS[0]]['content_sha256'] = '1' * 64
        self.reader.execute('note', ['edit', self.note['id'], 'Rewording a historical interpretation.',
                                    '--expect-revision', '1'], self.session)
        current = self.store.get_annotation(self.note['id'])
        self.assertEqual(current['content_sha256'], self.note['content_sha256'])
        self.assertIn('target text changed', self.reader.execute('note', ['show', self.note['id']], self.session).text)

    def test_foreign_actor_cannot_open_editor(self):
        status, output = self.shell([f'note edit {self.note["id"]}', 'exit'],
                                   lambda *a, **k: self.fail('No editor before author validation'),
                                   self.make_reader(actor='Other'))
        self.assertEqual(status, 0)
        self.assertIn('another actor', output)
        self.assertEqual(self.store.get_annotation(self.note['id'])['revision'], 1)

    def test_legacy_workspace_upgrade_command_is_copy_only_and_does_not_switch(self):
        source = self.directory / 'legacy.sqlite3'
        legacy_workspace(source, self.provenance)
        with Workspace(source, CORPUS_ID, self.provenance, actor='Ada') as legacy:
            note = legacy.add_annotation(IDS[0], 'An old workspace interpretation.')
            reader = self.make_reader(legacy)
            before = source.read_bytes()
            with self.assertRaisesRegex(ValueError, 'upgrade'):
                reader.execute('note', ['edit', note['id'], 'Replacement', '--expect-revision', '1'], self.session)
            history = reader.execute('note', ['history', note['id']], self.session).text
            self.assertIn('no annotation revision audit', history)
            target = self.directory / 'legacy-v2.sqlite3'
            result = reader.execute('workspace', ['upgrade', str(target)], self.session).text
            self.assertIn('session still uses the original', result)
            self.assertEqual(legacy.schema_version, 1)
            self.assertEqual(source.read_bytes(), before)
        with Workspace(target, CORPUS_ID, self.provenance, actor='Ada') as upgraded:
            rows = upgraded.list_annotation_history(note['id'])
            self.assertEqual(rows[0]['kind'], 'legacy_baseline')
            self.assertIsNone(rows[0]['editor'])
            shown = self.make_reader(upgraded).execute('note', ['history', note['id']], self.session).text
            self.assertIn('earlier edits and editor are unknown', shown)

    def test_changed_disk_generation_during_edit_refuses_commit(self):
        import sol.corpus.contract as contract
        from test_packaging import write_runtime_corpus
        corpus = self.directory / 'edit-corpus'
        write_runtime_corpus(corpus)
        contract.initialize_corpus_identity(corpus)
        book = sol.load_corpus_book(corpus)
        with Workspace(self.directory / 'guarded.sqlite3', book.corpus_manifest['corpus_id'],
                       {'source': book.corpus_manifest['source']}, actor='Ada') as store:
            record = book.passages[0]
            note = store.add_annotation(record.identifier, 'Original from a captured generation.',
                                        book.canonical_records[record.identifier]['content_sha256'])
            reader = WorkspaceReader(book, store, 'Ada', sol.resolve_path, sol.display_path, sol.render_passage)
            commands = iter([f'note edit {note["id"]}', 'exit'])
            def editor(prompt, default):
                document = corpus / 'sample.md'
                document.write_text(document.read_text(encoding='utf-8') + '\n', encoding='utf-8')
                return 'Stale generation edit.'
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(sol.run_shell(book, 80, workspace_reader=reader,
                                              read_command=lambda prompt: next(commands), draft_reader=editor), 0)
            self.assertIn('loaded corpus changed', output.getvalue())
            self.assertEqual(store.get_annotation(note['id'])['revision'], 1)

    def test_upgrade_reopen_name_cannot_silently_select_different_file(self):
        source = self.directory / 'legacy.sqlite3'
        legacy_workspace(source, self.provenance)
        target = self.directory / 'upgraded.SQLITE3'
        with Workspace(source, CORPUS_ID, self.provenance, actor='Ada') as legacy:
            reader = self.make_reader(legacy)
            with self.assertRaisesRegex(ValueError, 'lowercase .sqlite3'):
                reader.execute('workspace', ['upgrade', str(target)], self.session)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as error, \
                patch('sol.reader.app.discover_corpus', return_value=self.book.corpus_directory), \
                patch('sol.reader.app.load_corpus_book', return_value=self.book):
            status = sol.main(['--workspace', 'legacy', '--workspace-dir', str(self.directory),
                               '--workspace-upgrade', str(target)])
        self.assertEqual(status, 2)
        self.assertIn('lowercase .sqlite3', error.getvalue())
        self.assertFalse(target.exists())
        self.assertFalse((self.directory / 'upgraded.sqlite3').exists())


if __name__ == '__main__':
    unittest.main()
