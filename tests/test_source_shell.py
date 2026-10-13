"""Source inspection must not change the scholarly reading state."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import sol.reader.app as sol
from sol.terminal.prompt import CompletionCatalog
from sol.workspace.store import Workspace
from sol.workspace.reader import WorkspaceReader
from test_workspace_reader import invented_book, CORPUS_ID, IDS


class SourceShellTests(unittest.TestCase):
    def setUp(self):
        self.book = invented_book()
        self.request = {'target_id': IDS[2], 'sources': [{'pdf_page': 12, 'printed_page': 'xii'}]}
        self.service = Mock()
        self.service.capture.return_value = self.request
        self.service.set_pdf.return_value = Path('/invented/evidence.pdf')
        self.service.inspect_info.return_value = {'source_sha256': 'f' * 64}
        self.pane = Mock()

    def run_shell(self, commands, reader=None, **kwargs):
        output = StringIO()
        with patch('sol.terminal.source.SourceService', return_value=self.service), \
                redirect_stdout(output), patch('sol.reader.app.install_completion', return_value=lambda: None):
            iterator = iter(commands)
            status = sol.run_shell(self.book, 80, workspace_reader=reader,
                                   read_command=lambda prompt: next(iterator),
                                   source_pane=self.pane, **kwargs)
        return status, output.getvalue()

    def test_show_other_record_close_and_info_leave_checkpoint_unchanged(self):
        with tempfile.TemporaryDirectory(prefix='sol-source-shell-') as temporary:
            provenance = {key: self.book.corpus_manifest[key] for key in ('edition', 'source')}
            with Workspace(Path(temporary) / 'reading.sqlite3', CORPUS_ID, provenance, actor='Ada') as store:
                reader = WorkspaceReader(self.book, store, 'Ada', sol.resolve_path,
                                         sol.display_path, sol.render_passage)
                status, output = self.run_shell([
                    'first /being', f'source show {IDS[2]}', 'source info', 'source close', 'where', 'exit'
                ], reader)
                self.assertEqual(status, 0)
                self.assertEqual(store.get_state()['current_id'], IDS[0])
                self.assertEqual(len(store.export()['history']), 1)
                self.assertIn(f'ID {IDS[0]}', output)
                self.service.capture.assert_called_once_with(IDS[2])
                self.pane.show.assert_called_once_with(self.request)
                self.pane.close.assert_called_once()
                self.pane.cleanup.assert_called_once()

    def test_default_source_uses_current_passage_without_advancing(self):
        status, output = self.run_shell(['first /being', 'source show', 'where', 'exit'])
        self.assertEqual(status, 0)
        self.service.capture.assert_called_once_with(IDS[0])
        self.assertIn('Position 1 of', output)

    def test_failed_or_cancelled_capture_returns_to_same_reading_position(self):
        for failure in (ValueError('PDF fingerprint mismatch'), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                self.service.capture.side_effect = failure
                status, output = self.run_shell(['first /being', 'source show', 'where', 'next', 'where', 'exit'])
                self.assertEqual(status, 0)
                self.assertIn(f'ID {IDS[0]}', output)
                self.assertIn(f'ID {IDS[1]}', output)
                self.assertIn('Command cancelled.' if isinstance(failure, KeyboardInterrupt)
                              else 'PDF fingerprint mismatch', output)
        self.pane.show.assert_not_called()

    def test_set_pdf_does_not_need_a_current_passage(self):
        status, output = self.run_shell(['source set-pdf "/invented/pdf with spaces.pdf"', 'exit'])
        self.assertEqual(status, 0)
        self.service.set_pdf.assert_called_once_with(Path('/invented/pdf with spaces.pdf'))
        self.service.capture.assert_not_called()
        self.pane.show.assert_not_called()
        self.assertIn('Verified source PDF remembered', output)

    def test_invalid_source_actions_do_not_launch_or_capture(self):
        status, output = self.run_shell(['source bad', 'source show a b', 'source close x',
                                         'source set-pdf', 'exit'])
        self.assertEqual(status, 0)
        self.service.capture.assert_not_called()
        self.pane.show.assert_not_called()
        self.assertIn('requires a local PDF path', output)

    def test_source_flag_requires_canonical_shell(self):
        for flags in [['-r', '--source-pdf', 'a.pdf'],
                      ['-n', '--pdf', 'a.pdf', '--source-pdf', 'a.pdf']]:
            with self.subTest(flags=flags):
                args = sol.build_parser().parse_args(flags)
                with self.assertRaisesRegex(ValueError, '--source-pdf'):
                    sol.validate_options(args)

    def test_source_completion_is_available_without_workspace(self):
        catalog = CompletionCatalog(self.book, False)
        self.assertIn(('source', -3), catalog.suggestions('sou'))
        self.assertIn(('show', 0), catalog.suggestions('source '))
        self.assertIn((IDS[0], 0), catalog.suggestions('source show '))

    def test_auto_width_updates_subsequent_and_workspace_rendering(self):
        with patch('sol.reader.app.sensible_width', side_effect=[28, 60, 60]), \
                patch('sol.reader.app.render_passage', wraps=sol.render_passage) as render:
            self.run_shell(['first /being', 'next', 'exit'], auto_width=True)
        self.assertEqual([call.args[1] for call in render.call_args_list], [28, 60])

    def test_opening_source_rerenders_current_at_changed_width_without_moving(self):
        with patch('sol.reader.app.sensible_width', side_effect=[80, 80, 40, 40]), \
                patch('sol.reader.app.render_passage', wraps=sol.render_passage) as render:
            self.run_shell(['first /being', 'source show', 'exit'], auto_width=True)
        self.assertEqual([call.args[1] for call in render.call_args_list], [80, 40])
        self.assertEqual([call.args[0].identifier for call in render.call_args_list], [IDS[0], IDS[0]])


if __name__ == '__main__':
    unittest.main()
