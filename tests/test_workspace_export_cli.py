"""BEING export routing uses invented data, never personal storage or source PDFs."""
import builtins
from contextlib import redirect_stderr, redirect_stdout, nullcontext
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sol.reader.app as sol
from sol.workspace.store import Workspace
from sol.workspace.reader import WorkspaceReader
from test_workspace_reader import invented_book, CORPUS_ID, IDS


class WorkspaceExportRoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sol-markdown-export-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.book = invented_book()
        self.provenance = {key: self.book.corpus_manifest[key] for key in ('edition', 'source')}
        self.store = Workspace(self.directory / 'study.sqlite3', CORPUS_ID, self.provenance, actor='Ada')
        self.addCleanup(self.store.close)
        self.reader = WorkspaceReader(self.book, self.store, None, sol.resolve_path, sol.display_path,
                                      sol.render_passage)
        self.session = sol.ReadingSession(self.book)
        self.session.read(('BEING',), first=True)
        self.reader.checkpoint(self.session, (), None)
        self.note = self.store.add_annotation(IDS[0], 'A *personal* question, not Hegel’s prose.',
                                              self.book.canonical_records[IDS[0]]['content_sha256'])
        self.arguments = ['--workspace', 'study', '--workspace-dir', str(self.directory), '--workspace-export']

    def invoke(self, arguments):
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors), \
                patch('sol.reader.app.discover_corpus', return_value=self.book.corpus_directory), \
                patch('sol.reader.app.load_corpus_book', return_value=self.book), \
                nullcontext(), \
                patch('sol.reader.app.shell_identity', side_effect=AssertionError('No onboarding')), \
                patch('builtins.input', side_effect=AssertionError('No prompts')):
            status = sol.main(arguments)
        return status, output.getvalue(), errors.getvalue()

    def test_json_default_and_explicit_json_are_unchanged(self):
        with patch('sol.workspace.store._now', return_value='2026-10-12T00:00:00Z'):
            expected = self.store.export()
            for options in ([], ['--export-format', 'json'], ['--json']):
                with self.subTest(options=options):
                    status, output, error = self.invoke(self.arguments + options)
                    self.assertEqual(status, 0, error)
                    self.assertEqual(json.loads(output), expected)

    def test_actor_free_markdown_export_has_no_writes_or_optional_source_imports(self):
        before = self.store.path.read_bytes()
        original_import = builtins.__import__
        def guard(name, *arguments, **options):
            if (name.split('.')[0] in {'pypdf', 'pdfplumber', 'markdown_it'}
                    or name == 'sol.terminal.source'):
                raise AssertionError('Export must not import ' + name)
            return original_import(name, *arguments, **options)
        with patch('builtins.__import__', side_effect=guard):
            status, output, error = self.invoke(self.arguments + ['--export-format', 'markdown'])
        self.assertEqual(status, 0, error)
        self.assertTrue(output.startswith('# '))
        self.assertIn(self.note['body'], output)
        self.assertIn(IDS[0], output)
        self.assertNotIn(self.book.canonical_records[IDS[0]]['markdown'], output)
        self.assertNotIn('\x1b', output)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_invalid_cli_combinations_refuse_before_prompt_or_workspace_creation(self):
        cases = [(['-r', '--export-format', 'markdown'], '--export-format'),
                 (['-n', '--include-passages'], '--include-passages'),
                 (self.arguments + ['--include-passages'], '--include-passages'),
                 (self.arguments + ['--export-format', 'markdown', '--json'], '--json'),
                 (self.arguments + ['--export-format', 'markdown', '--plain'], '--plain'),
                 (['--workspace-export', '--export-format', 'markdown'], '--workspace NAME')]
        before = self.store.path.read_bytes()
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                status, _, error = self.invoke(arguments)
                self.assertEqual(status, 2, error)
                self.assertIn(expected, error)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_missing_workspace_markdown_export_does_not_create_it(self):
        arguments = ['--workspace', 'missing', '--workspace-dir', str(self.directory),
                     '--workspace-export', '--export-format', 'markdown']
        status, _, error = self.invoke(arguments)
        self.assertEqual(status, 2)
        self.assertIn('does not exist', error)
        self.assertFalse((self.directory / 'missing.sqlite3').exists())

    def test_changed_loaded_generation_is_labelled_and_does_not_prevent_export_recovery(self):
        with patch.object(self.reader, 'corpus_freshness', return_value={
                'state': 'changed', 'reason': 'The source Markdown changed on disk.'}):
            text = self.reader.export_text('markdown', include_passages=True)
        self.assertIn('changed', text)
        self.assertIn('The source Markdown changed on disk.', text)
        self.assertIn(self.book.canonical_records[IDS[0]]['markdown'], text)
        self.assertEqual(self.store.get_state()['revision'], 1)


if __name__ == '__main__':
    unittest.main()
