"""Native-shell launch contracts without opening a desktop window."""
from __future__ import annotations

from contextlib import ExitStack
import io
import os
from pathlib import Path
import shlex
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from sol.terminal import kitty


class NativeLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="native-launch-")
        self.addCleanup(self.temporary.cleanup)
        self.corpus = Path(self.temporary.name) / "corpus 'quoted' $(literal) `name`"
        self.corpus.mkdir()
        contexts = ExitStack()
        self.addCleanup(contexts.close)
        self.which = contexts.enter_context(patch("sol.terminal.kitty.shutil.which",
            side_effect=lambda value: {"kitty": "/usr/bin/kitty", "zsh": "/usr/bin/zsh",
                                       "sol": "/opt/sol commands/sol"}.get(value)))
        self.discover = contexts.enter_context(patch("sol.core.config.discover_corpus", return_value=self.corpus))
        self.load = contexts.enter_context(patch("sol.core.corpus.load_corpus_book"))
        self.run = contexts.enter_context(patch("sol.terminal.kitty.subprocess.run",
                                          return_value=SimpleNamespace(returncode=0)))

    def test_launch_uses_real_zsh_private_profile_and_literal_paths(self):
        captured = {}

        def inspect(command, **options):
            profile = Path(command[command.index("--config") + 1])
            session = Path(command[command.index("--session") + 1])
            captured.update(profile=profile, session=session)
            self.assertEqual(profile.stat().st_mode & 0o777, 0o600)
            self.assertEqual(session.stat().st_mode & 0o777, 0o600)
            self.assertEqual(profile.read_text(), kitty.KITTY_PROFILE)
            lines = session.read_text().splitlines()
            self.assertEqual(lines[0], "layout splits")
            self.assertEqual(shlex.split(lines[1]), ["launch", "--title=SOL zsh",
                "--env=SOL_CORPUS=" + str(self.corpus), "/usr/bin/zsh", "-i"])
            self.assertNotIn("--allow-remote-control", lines[1])
            self.assertNotIn("shell", options)
            self.assertEqual(options["cwd"], str(self.corpus))
            self.assertFalse(options["check"])
            environment = options["env"]
            self.assertEqual(environment["SOL_CORPUS"], str(self.corpus))
            self.assertEqual(environment["PATH"], "/opt/sol commands:/usr/bin:/custom")
            self.assertEqual(environment["ZDOTDIR"], "/user shell files")
            for key in ("KITTY_RC_PASSWORD", "KITTY_LISTEN_ON", "SOL_KITTY_SESSION"):
                self.assertNotIn(key, environment)
            return SimpleNamespace(returncode=17)

        self.run.side_effect = inspect
        with patch.dict(os.environ, {"PATH": "/usr/bin:/custom", "ZDOTDIR": "/user shell files",
            "KITTY_RC_PASSWORD": "ambient", "KITTY_LISTEN_ON": "fd:9", "SOL_KITTY_SESSION": "1"}):
            self.assertEqual(kitty.main(["--zsh"]), 17)
        self.load.assert_called_once_with(self.corpus)
        self.assertFalse(captured["profile"].exists())
        self.assertFalse(captured["session"].exists())

    def test_explicit_corpus_and_start_directory(self):
        self.assertEqual(kitty.main(["--zsh", "--corpus", str(self.corpus),
                                     "--directory", self.temporary.name]), 0)
        self.discover.assert_called_once_with(self.corpus)
        self.assertEqual(self.run.call_args.kwargs["cwd"], self.temporary.name)

    def test_invalid_or_reader_options_are_errors_before_launch(self):
        for arguments in (["--workspace", "reading"], ["--actor", "Ada"], ["--directory"], ["--unknown"]):
            with self.subTest(arguments=arguments), patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(kitty.main(["--zsh", *arguments]), 1)
        self.run.assert_not_called()

    def test_no_corpus_fails_without_launch(self):
        self.discover.return_value = None
        with patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(kitty.main(["--zsh"]), 1)
        self.assertIn("--corpus", output.getvalue())
        self.load.assert_not_called()
        self.run.assert_not_called()

    def test_invalid_corpus_fails_without_launch(self):
        self.load.side_effect = ValueError("corpus hash mismatch")
        with patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(kitty.main(["--zsh"]), 1)
        self.assertIn("hash mismatch", output.getvalue())
        self.run.assert_not_called()

    def test_missing_zsh_is_actionable(self):
        self.which.side_effect = lambda value: None if value == "zsh" else "/usr/bin/" + value
        with patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(kitty.main(["--zsh"]), 1)
        self.assertIn("zsh", output.getvalue())
        self.run.assert_not_called()

    def test_missing_start_directory_fails(self):
        with patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(kitty.main(["--zsh", "--directory", str(self.corpus / "absent")]), 1)
        self.assertIn("Shell directory not found", output.getvalue())
        self.run.assert_not_called()

    def test_session_injection_is_rejected_in_argument_and_discovered_path(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(kitty.main(["--zsh", "--corpus", "path\nlaunch injected"]), 1)
            bad = self.corpus / "bad\nlaunch injected"
            bad.mkdir()
            self.discover.return_value = bad
            self.assertEqual(kitty.main(["--zsh"]), 1)
        self.run.assert_not_called()

    def test_help_needs_no_corpus_or_desktop(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(kitty.main(["--zsh", "--help"]), 0)
        self.assertIn("--directory", output.getvalue())
        self.discover.assert_not_called()
        self.load.assert_not_called()
        self.run.assert_not_called()

    def test_desktop_launch_failure_cleans_private_files(self):
        captured = []

        def fail(command, **options):
            captured.append(Path(command[command.index("--session") + 1]))
            raise OSError("desktop unavailable")

        self.run.side_effect = fail
        with patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(kitty.main(["--zsh"]), 1)
        self.assertIn("desktop unavailable", output.getvalue())
        self.assertFalse(captured[0].exists())


if __name__ == "__main__":
    unittest.main()
