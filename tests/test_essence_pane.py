"""ESSENCE launch confinement and reader-owned window/transport boundaries."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sol.terminal import kitty


SESSION = {"SOL_KITTY_SESSION": "1", "KITTY_RC_PASSWORD": "private-token", "KITTY_WINDOW_ID": "19"}


class EssencePaneTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, SESSION)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.which = patch("sol.terminal.kitty.shutil.which", return_value="/usr/bin/kitten")
        self.which.start()
        self.addCleanup(self.which.stop)
        self.temporary = tempfile.TemporaryDirectory(prefix="sol-essence-pane-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.corpus = self.root / "Corpus ' with ; $(words)"
        self.directory = self.root / "Handoff ' with ; $(words)"
        self.corpus.mkdir()
        self.directory.mkdir()
        self.transport = self.directory / "outgoing.json"
        self.transport.write_text('{"reader": "owns this transport"}\n', encoding="utf-8")
        self.pane = kitty.EssencePane()
        self.addCleanup(self.pane._forget)

    def inventory(self, identifier=43):
        return json.dumps([{"tabs": [{"windows": [{"id": identifier}]}]}])

    def assert_transport_intact(self):
        self.assertEqual(self.transport.read_text(encoding="utf-8"), '{"reader": "owns this transport"}\n')
        self.assertEqual(list(self.directory.iterdir()), [self.transport])

    def test_launch_has_exact_arguments_pinned_corpus_and_no_child_remote_permissions(self):
        package_root = str(Path(kitty.__file__).resolve().parents[2])
        with patch.dict(os.environ, {"PYTHONPATH": "/ambient modules",
                                     "SOL_CORPUS": "/ambient wrong corpus", "SOL_HANDOFF_DIR": "/wrong handoff",
                                     "KITTY_LISTEN_ON": "fd:37"}), \
                patch.object(self.pane, "_remote", return_value="43\n") as remote:
            self.assertEqual(self.pane.show(self.directory, self.corpus), 43)
        self.assertEqual(remote.call_args.args, (
            "launch", "--match", "window_id:19", "--source-window", "id:19", "--next-to", "id:19",
            "--location", "vsplit", "--dont-take-focus", "--title", "SOL ESSENCE",
            "--cwd", str(self.corpus),
            "--env=KITTY_LISTEN_ON", "--env=KITTY_RC_PASSWORD", "--env=SOL_KITTY_SESSION",
            "--env=SOL_CORPUS=" + str(self.corpus), "--env=SOL_HANDOFF_DIR=" + str(self.directory),
            sys.executable, "-I", "-B", "-c",
            "import sys; sys.path.insert(0, sys.argv.pop(1)); import runpy; "
            "runpy.run_module('sol.terminal.essence', run_name='__main__')",
            package_root, "--handoff-dir", str(self.directory),
            "--corpus", str(self.corpus),
        ))
        self.assertNotIn("--allow-remote-control", remote.call_args.args)
        self.assertFalse(any(value.startswith("--remote-control-password") for value in remote.call_args.args))
        self.assertFalse(any(value.startswith("--copy-env") for value in remote.call_args.args))
        self.assertIsNone(self.pane.mailbox)
        self.assertIsNone(self.pane._temporary)
        self.assert_transport_intact()

    def test_relative_directories_become_absolute_and_metacharacters_stay_arguments(self):
        directory = Path(os.path.relpath(self.directory))
        corpus = Path(os.path.relpath(self.corpus))
        with patch.object(self.pane, "_remote", return_value="43") as remote:
            self.pane.show(directory, corpus)
        command = remote.call_args.args
        self.assertEqual(command[command.index("--handoff-dir") + 1], str(self.directory))
        self.assertEqual(command[command.index("--corpus") + 1], str(self.corpus))
        self.assertEqual(command[command.index("--cwd") + 1], str(self.corpus))
        self.assertNotIn("sh", command)
        self.assertIn("-I", command)
        self.assertEqual(command[command.index("-c") - 3], sys.executable)
        self.assert_transport_intact()

    def test_inherited_remote_uses_argument_list_without_shell_and_credentials_only_for_kitten(self):
        with patch.dict(os.environ, {"KITTY_LISTEN_ON": "fd:37"}), \
                patch("sol.terminal.kitty.subprocess.run", return_value=SimpleNamespace(
                    returncode=0, stdout="43", stderr="")) as run:
            self.assertEqual(self.pane.show(self.directory, self.corpus), 43)
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["kitten", "@", "--password-env=KITTY_RC_PASSWORD", "--use-password=always"])
        self.assertEqual(run.call_args.kwargs["pass_fds"], (37,))
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertIn("--env=KITTY_RC_PASSWORD", command)
        self.assertIn("--env=KITTY_LISTEN_ON", command)
        self.assertIn("--env=SOL_KITTY_SESSION", command)
        self.assertNotIn("--allow-remote-control", command)

    def test_actual_isolated_bootstrap_ignores_corpus_and_pythonpath_package_shadowing(self):
        ambient = self.root / "ambient Python modules"
        ambient.mkdir()
        for directory in (self.corpus, ambient):
            package = directory / "sol"
            package.mkdir()
            (package / "__init__.py").write_text(
                'raise RuntimeError("Untrusted corpus or ambient package executed")\n', encoding="utf-8")
        with patch.object(self.pane, "_remote", return_value="43") as remote:
            self.pane.show(self.directory, self.corpus)
        launch = remote.call_args.args
        command = [*launch[launch.index(sys.executable):], "--help"]
        environment = dict(os.environ, PYTHONPATH=str(ambient))
        result = subprocess.run(command, cwd=self.corpus, env=environment,
                                text=True, capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Open ESSENCE's native shell", result.stdout)
        self.assertNotIn("Untrusted", result.stderr)
        self.assert_transport_intact()

    def test_no_source_mailbox_lifecycle_or_transport_deletion_on_close(self):
        with patch.object(kitty.SourcePane, "show", side_effect=AssertionError("source mailbox lifecycle")), \
                patch.object(kitty.SourcePane, "_forget", side_effect=AssertionError("source mailbox cleanup")), \
                patch("sol.terminal.kitty.tempfile.TemporaryDirectory", side_effect=AssertionError("pane-owned transport")), \
                patch.object(self.pane, "_remote", side_effect=["43", ""]) as remote:
            self.pane.show(self.directory, self.corpus)
            self.pane.close()
        self.assertEqual(remote.call_args.args, ("close-window", "--match", "id:43", "--ignore-no-match"))
        self.assertIsNone(self.pane.window_id)
        self.assert_transport_intact()

    def test_an_open_handoff_refuses_replacement_without_launch_or_transport_mutation(self):
        other = self.root / "replacement handoff"
        other.mkdir()
        with patch.object(self.pane, "_remote", side_effect=["43", self.inventory()]) as remote:
            self.pane.show(self.directory, self.corpus)
            with self.assertRaisesRegex(kitty.KittyError, "already open"):
                self.pane.show(other, self.corpus)
        self.assertEqual(remote.call_count, 2)
        self.assertEqual(remote.call_args.args, ("ls", "--match", "id:43"))
        self.assertEqual(self.pane.window_id, 43)
        self.assertEqual(list(other.iterdir()), [])
        self.assert_transport_intact()

    def test_a_manually_closed_pane_allows_fresh_launch_and_only_new_owned_id_closes(self):
        other = self.root / "new handoff"
        other.mkdir()
        with patch.object(self.pane, "_remote", side_effect=["43", "[]", "44", ""]) as remote:
            self.pane.show(self.directory, self.corpus)
            self.assertEqual(self.pane.show(other, self.corpus), 44)
            self.pane.close()
        self.assertEqual(remote.call_args_list[1].args, ("ls", "--match", "id:43"))
        self.assertEqual(remote.call_args.args, ("close-window", "--match", "id:44", "--ignore-no-match"))
        self.assert_transport_intact()
        self.assertTrue(other.is_dir())

    def test_invalid_launch_responses_cannot_claim_a_reader_or_arbitrary_window(self):
        for answer in ("19", "0", "-1", "all", "title:reader", "４３", "43\nclose-window", None):
            with self.subTest(answer=answer), patch.object(self.pane, "_remote", return_value=answer) as remote:
                with self.assertRaises(kitty.KittyError):
                    self.pane.show(self.directory, self.corpus)
                self.assertIsNone(self.pane.window_id)
                self.pane.cleanup()
                self.assertEqual(remote.call_count, 1)
                self.assert_transport_intact()

    def test_launch_errors_leave_transport_available_to_parent(self):
        with patch.object(self.pane, "_remote", side_effect=kitty.KittyError("denied")):
            with self.assertRaisesRegex(kitty.KittyError, "denied"):
                self.pane.show(self.directory, self.corpus)
            self.pane.cleanup()
        self.assertIsNone(self.pane.window_id)
        self.assert_transport_intact()

    def test_remote_launch_timeout_is_reported_without_transport_cleanup(self):
        with patch("sol.terminal.kitty.subprocess.run", side_effect=subprocess.TimeoutExpired("kitten", 10)):
            with self.assertRaisesRegex(kitty.KittyError, "Cannot reach"):
                self.pane.show(self.directory, self.corpus)
        self.assertIsNone(self.pane.window_id)
        self.assert_transport_intact()

    def test_close_error_remains_retryable_and_cleanup_is_best_effort(self):
        with patch.object(self.pane, "_remote", return_value="43"):
            self.pane.show(self.directory, self.corpus)
        with patch.object(self.pane, "_remote", side_effect=kitty.KittyError("denied")) as remote:
            with self.assertRaisesRegex(kitty.KittyError, "denied"):
                self.pane.close()
            self.assertEqual(self.pane.window_id, 43)
            self.pane.cleanup()
            self.assertEqual(remote.call_count, 2)
        self.assertIsNone(self.pane.window_id)
        self.assert_transport_intact()

    def test_corrupted_inventory_keeps_owned_window_available_for_explicit_close(self):
        with patch.object(self.pane, "_remote", side_effect=["43", "invalid inventory", ""]):
            self.pane.show(self.directory, self.corpus)
            with self.assertRaisesRegex(kitty.KittyError, "invalid essence pane inventory"):
                self.pane.show(self.directory, self.corpus)
            self.assertEqual(self.pane.window_id, 43)
            self.pane.close()
        self.assert_transport_intact()

    def test_close_refuses_window_ids_that_were_not_returned_by_its_launch(self):
        for identifier in (19, 77, "all", "43", True, -1):
            with self.subTest(identifier=identifier):
                pane = kitty.EssencePane()
                with patch.object(pane, "_remote", return_value="43"):
                    pane.show(self.directory, self.corpus)
                pane.window_id = identifier
                with patch.object(pane, "_remote") as remote:
                    with self.assertRaisesRegex(kitty.KittyError, "unowned"):
                        pane.close()
                    pane.cleanup()
                    remote.assert_not_called()
                self.assertIsNone(pane.window_id)
                self.assert_transport_intact()

    def test_session_reader_is_pinned_for_launch_and_close(self):
        with patch.object(self.pane, "_remote", return_value="43"):
            self.pane.show(self.directory, self.corpus)
        with patch.dict(os.environ, {"KITTY_WINDOW_ID": "20"}), patch.object(self.pane, "_remote") as remote:
            with self.assertRaisesRegex(kitty.KittyError, "different reader window"):
                self.pane.show(self.directory, self.corpus)
            with self.assertRaisesRegex(kitty.KittyError, "different reader window"):
                self.pane.close()
            remote.assert_not_called()
        self.assertEqual(self.pane.reader_id, 19)
        self.assertEqual(self.pane.window_id, 43)
        self.assert_transport_intact()

    def test_ordinary_terminal_cannot_control_a_pane(self):
        with patch.dict(os.environ, {"SOL_KITTY_SESSION": "0"}), patch.object(self.pane, "_remote") as remote:
            with self.assertRaisesRegex(kitty.KittyError, "sol-kitty"):
                self.pane.show(self.directory, self.corpus)
            remote.assert_not_called()
        self.assert_transport_intact()

    def test_control_characters_missing_files_and_symbolic_link_directories_are_rejected(self):
        file = self.root / "file"
        file.write_text("not a directory", encoding="utf-8")
        linked = self.root / "linked"
        linked.symlink_to(self.directory, target_is_directory=True)
        nested = self.directory / "nested"
        nested.mkdir()
        bad_paths = [self.root / "missing", file, linked, linked / "nested"]
        for character in ("\r", "\n", "\0"):
            bad_paths.append(self.root / ("bad" + character + "directory"))
        for bad in bad_paths:
            for side in ("handoff", "corpus"):
                with self.subTest(path=str(bad), side=side), patch.object(self.pane, "_remote") as remote:
                    arguments = (bad, self.corpus) if side == "handoff" else (self.directory, bad)
                    with self.assertRaises(kitty.KittyError):
                        self.pane.show(*arguments)
                    remote.assert_not_called()
        self.assertTrue(self.transport.exists())
        self.assertTrue(nested.is_dir())

if __name__ == "__main__":
    unittest.main()
