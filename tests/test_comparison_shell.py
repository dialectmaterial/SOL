"""Opening a desk is inspection, not another durable reading session."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from sol.reader import app
from sol.terminal.prompt import CompletionCatalog
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace
from test_workspace_reader import invented_book, CORPUS_ID, IDS


class ComparisonShellTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sol-comparison-shell-')
        self.addCleanup(self.temporary.cleanup)
        self.book = invented_book()
        provenance = {key: self.book.corpus_manifest[key] for key in ('edition', 'source')}
        self.store = Workspace(Path(self.temporary.name) / 'study.sqlite3', CORPUS_ID, provenance, actor='Ada')
        self.addCleanup(self.store.close)
        self.store.save_comparison('ground inquiry', [IDS[0], IDS[2]], 'How do these passages differ?')
        self.note = self.store.add_annotation(IDS[0], 'A personal question to keep visible.',
                                             self.book.canonical_records[IDS[0]]['content_sha256'])
        self.reader = WorkspaceReader(self.book, self.store, None, app.resolve_path,
                                      app.display_path, app.render_passage)
        self.pane = Mock()

    def shell(self, commands, reader=True, **options):
        output = StringIO()
        with redirect_stdout(output), patch('sol.reader.shell.install_completion', return_value=lambda: None):
            iterator = iter(commands)
            status = app.run_shell(self.book, 80, workspace_reader=self.reader if reader else None,
                                   read_command=lambda prompt: next(iterator), comparison_pane=self.pane,
                                   **options)
        return status, output.getvalue()

    def test_open_refresh_and_close_preserve_checkpoint_notes_and_actor(self):
        before = self.store.export()
        status, output = self.shell(['first /being', 'compare open "ground inquiry"',
                                    'compare open "ground inquiry"', 'compare close', 'where', 'exit'])
        after = self.store.export()
        self.assertEqual(status, 0)
        self.assertEqual(after['state']['current_id'], IDS[0])
        self.assertEqual(len(after['history']), 1)
        for field in ('annotations', 'annotation_history', 'comparisons', 'reviews', 'relations'):
            self.assertEqual(after[field], before[field])
        self.assertIn(f'ID {IDS[0]}', output)
        self.assertEqual(self.pane.show.call_count, 2)
        snapshot = self.pane.show.call_args.args[0]
        self.assertEqual([card['requested_id'] for card in snapshot['records']], [IDS[0], IDS[2]])
        self.assertEqual(snapshot['records'][0]['notes'][0]['body'], self.note['body'])
        self.pane.close.assert_called_once()
        self.pane.cleanup.assert_called_once()

    def test_capture_failures_and_cancellation_return_to_reader(self):
        for failure in (ValueError('comparison is missing'), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__), \
                    patch('sol.workspace.comparison.capture_comparison', side_effect=failure):
                status, output = self.shell(['first /being', 'compare open missing', 'where', 'exit'])
                self.assertEqual(status, 0)
                self.assertIn(f'ID {IDS[0]}', output)
                self.assertIn('Command cancelled.' if isinstance(failure, KeyboardInterrupt)
                              else 'comparison is missing', output)
        self.pane.show.assert_not_called()

    def test_interrupting_real_snapshot_read_leaves_workspace_usable(self):
        with patch.object(self.store, 'list_annotations', side_effect=KeyboardInterrupt()):
            status, output = self.shell(['compare open "ground inquiry"', 'exit'])
        self.assertEqual(status, 0)
        self.assertIn('Command cancelled.', output)
        self.assertFalse(self.store._db().in_transaction)
        self.assertEqual(len(self.store.export()['annotations']), 1)
        record = self.store.add_annotation(IDS[2], 'A subsequent write still works.')
        self.assertEqual(record['target_id'], IDS[2])
        self.pane.show.assert_not_called()

    def test_pane_failure_does_not_change_reading_or_search_results(self):
        self.pane.show.side_effect = RuntimeError('kitty unavailable')
        status, output = self.shell(['first /being', 'search "another" /',
                                    'compare open "ground inquiry"', 'where', 'open 1', 'where', 'exit'])
        self.assertEqual(status, 0)
        self.assertIn('kitty unavailable', output)
        self.assertIn(f'ID {IDS[0]}', output)
        self.assertIn(f'ID {IDS[2]}', output)
        self.assertEqual(len(self.store.export()['history']), 2)

    def test_saved_open_requires_workspace_and_missing_selection_is_explained(self):
        status, output = self.shell(['compare open test', 'compare close', 'exit'], reader=False)
        self.assertEqual(status, 0)
        self.assertIn('requires a reading workspace', output)
        self.pane.show.assert_not_called()
        status, output = self.shell(['compare open', 'compare open a b', 'compare close named', 'exit'])
        self.assertEqual(status, 0)
        self.assertIn('Choose two paths: compare PATH_A PATH_B', output)
        self.assertIn('does not take a name', output)

    def test_split_change_reflows_without_creating_another_checkpoint(self):
        with patch('sol.reader.shell.sensible_width', side_effect=[80, 80, 40, 40]), \
                patch('sol.reader.shell.render_passage', wraps=app.render_passage) as render:
            self.shell(['first /being', 'compare open "ground inquiry"', 'exit'], auto_width=True)
        self.assertEqual([call.args[1] for call in render.call_args_list], [80, 40])
        self.assertEqual(len(self.store.export()['history']), 1)

    def test_both_optional_panes_clean_up_and_have_independent_ownership(self):
        source = Mock()
        self.shell(['compare open "ground inquiry"', 'compare close', 'exit'], source_pane=source)
        self.pane.close.assert_called_once()
        self.pane.cleanup.assert_called_once()
        source.close.assert_not_called()
        source.cleanup.assert_called_once()

    def test_completion_offers_desk_and_quoted_saved_names(self):
        catalog = CompletionCatalog(self.book, True)
        catalog.comparisons = ('ground inquiry',)
        self.assertIn(('open', 0), catalog.suggestions('compare '))
        self.assertIn(('close', 0), catalog.suggestions('compare '))
        self.assertIn(("'ground inquiry'", 0), catalog.suggestions('compare open '))


if __name__ == '__main__':
    unittest.main()
