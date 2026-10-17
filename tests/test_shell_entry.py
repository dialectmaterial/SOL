"""The beginner entry points are tested without a real TTY or personal data."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sol.reader.app as sol
import sol.workspace.profiles as sol_profiles
from sol.workspace.store import Workspace
from test_workspace_reader import invented_book, CORPUS_ID, IDS


class ShellEntryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sol-entry-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        environment = patch.dict('os.environ', {'XDG_DATA_HOME': str(self.directory), 'TERM': 'dumb'})
        environment.start()
        self.addCleanup(environment.stop)
        self.book = invented_book()
        self.reader_launches = []

    def launch_reader(self, book, workspace_reader=None, **options):
        self.reader_launches.append((book, workspace_reader, options))
        if workspace_reader is not None:
            actions = sol.ReaderActions(book, workspace_reader, session=sol.ReadingSession(book))
            if workspace_reader.store.get_state() is None:
                actions.read(('BEING',), first=True)
            else:
                actions.restore()
        return 0

    def main(self, arguments, commands=(), interactive=True):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
                patch('sol.reader.app.discover_corpus', return_value=Path('/invented/corpus')), \
                patch('sol.reader.app.load_corpus_book', return_value=self.book), \
                patch('sol.reader.app.load_book', side_effect=AssertionError('PDF extraction forbidden')), \
                patch('sol.reader.launch.interactive_input_available', return_value=interactive), \
                patch('sol.terminal.neovim.validate_environment'), \
                patch('sol.reader.app.run_reader', side_effect=self.launch_reader), \
                patch('sol.reader.shell.install_completion', return_value=lambda: None), \
                patch('builtins.input', side_effect=commands):
            status = sol.main(arguments)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_default_asks_creates_workspace_and_actor_and_remembers_reading(self):
        status, output, error = self.main([], ['Ada', 'study'])
        self.assertEqual(status, 0, error)
        self.assertEqual(self.reader_launches[-1][1].actor, 'Ada')
        profile = sol_profiles.list_actors()[0]
        self.assertEqual(profile['name'], 'Ada')
        path = self.directory / 'sol' / 'workspaces' / 'study.sqlite3'
        provenance = {key: self.book.corpus_manifest[key] for key in ('edition', 'source')}
        with Workspace(path, CORPUS_ID, provenance) as workspace:
            self.assertEqual(workspace.get_state()['current_id'], IDS[0])
        status, output, error = self.main([], interactive=False)
        self.assertEqual(status, 0, error)
        self.assertEqual(self.reader_launches[-1][1].store.path, path)
        self.assertEqual(self.reader_launches[-1][1].actor, 'Ada')
        self.assertEqual(sol_profiles.list_actors()[0]['id'], profile['id'])

    def test_none_skips_workspace_profiles_and_prompts(self):
        with patch('sol.workspace.profiles.list_actors', side_effect=AssertionError('No actor registry')), \
                patch('sol.workspace.profiles.register_actor', side_effect=AssertionError('No actor registry')), \
                patch('sol.workspace.store.Workspace', side_effect=AssertionError('No workspace')):
            status, output, error = self.main(['-n'], interactive=False)
        self.assertEqual(status, 0, error)
        self.assertIsNone(self.reader_launches[-1][1])
        self.assertFalse((self.directory / 'sol').exists())

    def test_random_is_one_shot_and_does_not_use_input_or_registry(self):
        status, output, error = self.main(['-r', '--json'], interactive=False)
        self.assertEqual(status, 0, error)
        self.assertIn(json.loads(output)['id'], IDS[:3])
        self.assertFalse((self.directory / 'sol').exists())

    def test_explicit_temporary_shell_remains_available_without_identity(self):
        status, output, error = self.main(['--shell', '-n', '--ui', 'basic'],
                                          ['first /being', 'exit'], interactive=False)
        self.assertEqual(status, 0, error)
        self.assertIn(IDS[0], output)
        self.assertEqual(self.reader_launches, [])
        self.assertFalse((self.directory / 'sol').exists())

    def test_roles_from_flags_skip_only_supplied_prompts(self):
        for arguments, commands in [(['--workspace', 'study'], ['Ada']),
                                    (['--actor', 'Ada'], []),
                                    (['--workspace', 'study', '--actor', 'Ada'], [])]:
            with self.subTest(arguments=arguments):
                status, _, error = self.main(arguments, commands)
                self.assertEqual(status, 0, error)

    def test_fully_explicit_workspace_shell_supports_scripted_input(self):
        status, _, error = self.main(['--shell', '--workspace', 'script', '--actor', 'Ada', '--ui', 'basic'],
                                    ['exit'], interactive=False)
        self.assertEqual(status, 0, error)
        self.assertTrue((self.directory / 'sol' / 'profiles.sqlite3').exists())

    def test_redirected_missing_roles_fail_without_consuming_command_stream(self):
        status, _, error = self.main([], interactive=False)
        self.assertEqual(status, 2)
        self.assertIn('sol -n', error)
        self.assertFalse((self.directory / 'sol').exists())

    def test_setup_cancel_does_not_create_workspace_or_actor(self):
        status, _, error = self.main([], ['Ada', EOFError()])
        self.assertEqual(status, 0, error)
        self.assertIn('setup cancelled', error)
        self.assertFalse((self.directory / 'sol').exists())

    def test_invalid_prompt_labels_retry_before_creation(self):
        status, output, error = self.main([], ['', 'Ada', '../bad', 'study'])
        self.assertEqual(status, 0, error)
        self.assertIn('workspace name', output)
        self.assertIn('actor name', output)
        self.assertEqual([profile['name'] for profile in sol_profiles.list_actors()], ['Ada'])

    def test_incompatible_modes_and_implicit_json_fail_before_creation(self):
        for arguments in [['-n', '--actor', 'Ada'], ['-n', '--workspace', 'study'],
                          ['-r', '--ui', 'prompt'], ['--json'], ['--actor', '', '--workspace', 'x']]:
            with self.subTest(arguments=arguments):
                status, _, error = self.main(arguments)
                self.assertEqual(status, 2, error)
        self.assertFalse((self.directory / 'sol').exists())

    def test_one_shot_actions_do_not_create_profiles_or_start_shell(self):
        for arguments in [['--guide'], ['guide'], ['--structure'], ['--first', '/being']]:
            with self.subTest(arguments=arguments):
                status, output, error = self.main(arguments, interactive=False)
                self.assertEqual(status, 0, error)
                self.assertNotIn('Known actors:', output)
        self.assertFalse((self.directory / 'sol').exists())

    def test_picker_displays_recent_compatible_workspaces_and_selects_number(self):
        for name, timestamp in [('older', '2026-10-10T00:00:00Z'), ('newer', '2026-10-12T00:00:00Z')]:
            with patch('sol.workspace.store._now', return_value=timestamp):
                status, _, error = self.main(['--shell', '--workspace', name, '--actor', 'Ada'], ['first /being', 'exit'])
                self.assertEqual(status, 0, error)
        status, output, error = self.main(['--shell', '--actor', 'Bob'], ['2', 'where', 'exit'])
        self.assertEqual(status, 0, error)
        self.assertIn('1. newer', output)
        self.assertIn('2. older', output)
        self.assertIn('Workspace: older', output)
        self.assertIn(IDS[0], output)

    def test_blank_choice_keeps_numeric_workspace_default_as_name(self):
        self.assertEqual(self.main(['--workspace', '42', '--actor', 'Ada'])[0], 0)
        status, output, error = self.main(['--shell'], ['exit'])
        self.assertEqual(status, 0, error)
        self.assertIn('Workspace: 42', output)

    def test_picker_retries_unknown_number_and_explicit_flags_bypass_catalog(self):
        self.assertEqual(self.main(['--workspace', 'study', '--actor', 'Ada'])[0], 0)
        status, output, error = self.main(['--shell', '--actor', 'Bob'], ['9' * 5000, '5', '1', 'exit'])
        self.assertEqual(status, 0, error)
        self.assertIn('choose a displayed workspace number', output)
        with patch('sol.workspace.catalog.discover_workspaces', side_effect=AssertionError('No picker')):
            self.assertEqual(self.main(['--workspace', 'study', '--actor', 'Ada'])[0], 0)
            self.assertEqual(self.main(['-n'], interactive=False)[0], 0)
            self.assertEqual(self.main(['-r'], interactive=False)[0], 0)

    def test_incompatible_options_include_upgrade_without_named_workspace(self):
        status, _, error = self.main(['--workspace-upgrade', str(self.directory / 'copy.sqlite3')])
        self.assertEqual(status, 2, error)
        self.assertIn('--workspace NAME', error)
        self.assertFalse((self.directory / 'sol').exists())

    def test_legacy_pdf_default_is_refused_before_slow_extraction(self):
        for arguments in [['--pdf', 'unused.pdf'], ['--shell', '--pdf', 'unused.pdf']]:
            with self.subTest(arguments=arguments):
                status, _, error = self.main(arguments, interactive=False)
                self.assertEqual(status, 2, error)
                self.assertIn('sol -r --pdf PATH', error)
        self.assertFalse((self.directory / 'sol').exists())


class ActorProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sol-profiles-')
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'nested' / 'profiles.sqlite3'

    def test_readonly_list_creates_nothing(self):
        self.assertEqual(sol_profiles.list_actors(self.path), [])
        self.assertFalse(self.path.parent.exists())

    def test_explicit_registration_is_private_and_idempotent(self):
        first = sol_profiles.register_actor('Ada', self.path)
        self.assertEqual(sol_profiles.register_actor('Ada', self.path), first)
        self.assertEqual(sol_profiles.list_actors(self.path), [first])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        other = sol_profiles.register_actor('Díma', self.path)
        self.assertNotEqual(other['id'], first['id'])

    def test_labels_reject_controls_or_empty_names(self):
        for name in ['', ' ', 'x\x1b[31m', 'x\n', '\u202e', 'x' * 129]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                sol_profiles.register_actor(name, self.path)
        self.assertFalse(self.path.exists())

    def test_unknown_database_is_not_overwritten(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b'A file to preserve')
        for operation in (lambda: sol_profiles.list_actors(self.path),
                          lambda: sol_profiles.register_actor('Ada', self.path)):
            with self.assertRaises(ValueError):
                operation()
        self.assertEqual(self.path.read_bytes(), b'A file to preserve')

    def test_registry_symlinks_are_refused_without_replacing_target(self):
        self.path.parent.mkdir()
        target = self.path.parent / 'target'
        target.write_bytes(b'Untouched')
        self.path.symlink_to(target)
        with self.assertRaises(ValueError):
            sol_profiles.register_actor('Ada', self.path)
        self.assertEqual(target.read_bytes(), b'Untouched')


if __name__ == '__main__':
    unittest.main()
