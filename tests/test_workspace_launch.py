"""Launch choices are explicit preferences, never inferred attribution."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from sol.reader import app
from sol.being.workspace.launch import (forget_workspace, launch_path, read_launch_preferences,
                                  remember_launch)
from sol.being.workspace.profiles import list_actors, register_actor
from sol.being.workspace.store import Workspace
from test_workspace_reader import CORPUS_ID, invented_book


class LaunchPreferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-launch-preferences-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root / "data")})
        environment.start()
        self.addCleanup(environment.stop)
        self.workspace = self.root / "workspaces" / "reading.sqlite3"

    def test_read_and_forget_absent_preferences_create_nothing(self):
        self.assertEqual(read_launch_preferences(), {"last_actor": None, "selections": []})
        forget_workspace(self.workspace)
        self.assertFalse((self.root / "data").exists())

    def test_remembers_last_explicit_actor_and_one_workspace_per_actor_and_source(self):
        remember_launch("Ada", self.workspace, CORPUS_ID, "0" * 64)
        other = self.workspace.with_name("other.sqlite3")
        remember_launch("Bob", other, CORPUS_ID, "0" * 64)
        remember_launch("Ada", other, CORPUS_ID, "1" * 64)
        result = read_launch_preferences()
        self.assertEqual(result["last_actor"], "Ada")
        self.assertEqual(len(result["selections"]), 3)
        remember_launch("Ada", other, CORPUS_ID, "0" * 64)
        choices = read_launch_preferences()["selections"]
        self.assertEqual(len(choices), 3)
        self.assertEqual(next(choice for choice in choices if choice["actor"] == "Ada" and
                              choice["source_sha256"] == "0" * 64)["workspace"], str(other))
        self.assertEqual(launch_path().stat().st_mode & 0o777, 0o600)

    def test_forgetting_a_workspace_retains_other_choices_and_last_actor(self):
        other = self.workspace.with_name("other.sqlite3")
        remember_launch("Ada", self.workspace, CORPUS_ID, "0" * 64)
        remember_launch("Bob", self.workspace, CORPUS_ID, "0" * 64)
        remember_launch("Ada", other, CORPUS_ID, "1" * 64)
        forget_workspace(self.workspace)
        result = read_launch_preferences()
        self.assertEqual(result["last_actor"], "Ada")
        self.assertEqual([choice["workspace"] for choice in result["selections"]], [str(other)])

    def test_unrecognized_files_and_symlinks_are_not_changed(self):
        path = launch_path()
        path.parent.mkdir(parents=True)
        path.write_bytes(b"preserve this unrelated file")
        for operation in (read_launch_preferences,
                          lambda: remember_launch("Ada", self.workspace, CORPUS_ID, "0" * 64),
                          lambda: forget_workspace(self.workspace)):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()
            self.assertEqual(path.read_bytes(), b"preserve this unrelated file")
        target = self.root / "target"
        path.rename(target)
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            read_launch_preferences()
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            remember_launch("Ada", self.workspace, CORPUS_ID, "0" * 64)
        self.assertEqual(target.read_bytes(), b"preserve this unrelated file")

    def test_invalid_labels_fingerprints_and_paths_do_not_create_preferences(self):
        for actor, workspace, identity, source in (
                ("", self.workspace, CORPUS_ID, "0" * 64),
                ("Ada", Path("relative.sqlite3"), CORPUS_ID, "0" * 64),
                ("Ada", self.workspace.with_name("not a named workspace.sqlite3"), CORPUS_ID, "0" * 64),
                ("Ada", self.workspace, "not-a-uuid", "0" * 64),
                ("Ada", self.workspace, CORPUS_ID, "invalid")):
            with self.subTest(actor=actor, workspace=workspace, identity=identity, source=source), \
                    self.assertRaises(ValueError):
                remember_launch(actor, workspace, identity, source)
        self.assertFalse(launch_path().exists())

    def test_schema_and_row_tampering_are_rejected_without_repair(self):
        remember_launch("Ada", self.workspace, CORPUS_ID, "0" * 64)
        connection = sqlite3.connect(launch_path())
        connection.execute("UPDATE selections SET source_sha256='invalid'")
        connection.commit()
        connection.close()
        before = launch_path().read_bytes()
        with self.assertRaises(ValueError):
            read_launch_preferences()
        with self.assertRaises(ValueError):
            remember_launch("Bob", self.workspace, CORPUS_ID, "0" * 64)
        self.assertEqual(launch_path().read_bytes(), before)

    def test_readonly_lookup_refuses_wal_without_creating_shared_memory(self):
        remember_launch("Ada", self.workspace, CORPUS_ID, "0" * 64)
        connection = sqlite3.connect(launch_path())
        self.assertEqual(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        connection.close()
        before = {item.name: item.read_bytes() for item in launch_path().parent.iterdir()}
        with self.assertRaisesRegex(ValueError, "WAL"):
            read_launch_preferences()
        self.assertEqual({item.name: item.read_bytes() for item in launch_path().parent.iterdir()}, before)


class ReaderStartupMemoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-reader-launch-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root / "data"), "TERM": "dumb"})
        environment.start()
        self.addCleanup(environment.stop)
        self.book = invented_book()
        self.directory = self.root / "workspaces"
        self.provenance = {key: self.book.corpus_manifest[key] for key in ("edition", "source")}
        self.launches = []

    def prepare(self, actor="Ada", name="reading", *, remember=True, directory=None):
        path = (directory or self.directory) / f"{name}.sqlite3"
        register_actor(actor)
        with Workspace(path, CORPUS_ID, self.provenance, actor=actor):
            pass
        if remember:
            remember_launch(actor, path, CORPUS_ID, "0" * 64)
        return path

    def call(self, arguments, responses=(), interactive=True):
        output, errors = StringIO(), StringIO()
        def launch(book, reader=None, **options):
            self.launches.append((None if reader is None else reader.actor,
                                  None if reader is None else reader.store.path, options))
            return 0
        with redirect_stdout(output), redirect_stderr(errors), \
                patch.object(app, "discover_corpus", return_value=Path("/invented/corpus")), \
                patch.object(app, "load_corpus_book", return_value=self.book), \
                patch("sol.reader.launch.interactive_input_available", return_value=interactive), \
                patch("sol.being.neovim.host.validate_environment"), \
                patch.object(app, "run_reader", side_effect=launch), \
                patch("builtins.input", side_effect=responses) as prompt:
            status = app.main(arguments)
        return status, output.getvalue(), errors.getvalue(), prompt.call_count

    def test_last_actor_is_launch_choice_not_newest_profile_or_catalog_activity(self):
        path = self.prepare("Ada", "reading")
        self.prepare("Bob", "later-profile", remember=False)
        result = self.call([], interactive=False)
        self.assertEqual(result[0], 0, result[2])
        self.assertEqual(result[3], 0)
        self.assertEqual(self.launches[-1][:2], ("Ada", path))

    def test_explicit_actor_gets_own_last_workspace_and_changes_next_default(self):
        ada = self.prepare("Ada", "ada-reading")
        bob = self.prepare("Bob", "bob-reading")
        self.assertEqual(self.call(["--actor", "Ada"], interactive=False)[0], 0)
        self.assertEqual(self.launches[-1][:2], ("Ada", ada))
        self.assertEqual(self.call([], interactive=False)[0], 0)
        self.assertEqual(self.launches[-1][:2], ("Ada", ada))
        self.assertEqual(self.call(["--actor", "Bob"], interactive=False)[0], 0)
        self.assertEqual(self.launches[-1][:2], ("Bob", bob))

    def test_explicit_workspace_and_directory_override_memory(self):
        self.prepare()
        chosen = self.root / "explicit" / "chosen.sqlite3"
        result = self.call(["--workspace", "chosen", "--workspace-dir", str(chosen.parent)], interactive=False)
        self.assertEqual(result[0], 0, result[2])
        self.assertEqual(self.launches[-1][:2], ("Ada", chosen))
        self.assertEqual(self.call([], interactive=False)[0], 0)
        self.assertEqual(self.launches[-1][:2], ("Ada", chosen))

    def test_directory_override_does_not_reopen_remembered_other_directory(self):
        self.prepare()
        other = self.root / "other"
        result = self.call(["--workspace-dir", str(other)], ["new-reading"])
        self.assertEqual(result[0], 0, result[2])
        self.assertEqual(result[3], 1)
        self.assertEqual(self.launches[-1][:2], ("Ada", other / "new-reading.sqlite3"))

    def test_new_actor_is_asked_to_create_workspace_instead_of_inheriting_another_actor(self):
        self.prepare()
        result = self.call(["--actor", "Bob", "--workspace-dir", str(self.directory)], ["bob-reading"])
        self.assertEqual(result[0], 0, result[2])
        self.assertEqual(result[3], 1)
        self.assertEqual(self.launches[-1][:2], ("Bob", self.directory / "bob-reading.sqlite3"))

    def test_missing_remembered_workspace_prompts_instead_of_recreating_silently(self):
        path = self.root / "missing" / "reading.sqlite3"
        register_actor("Ada")
        remember_launch("Ada", path, CORPUS_ID, "0" * 64)
        result = self.call([], [EOFError()])
        self.assertEqual(result[0], 0, result[2])
        self.assertEqual(result[3], 1)
        self.assertFalse(path.exists())
        self.assertEqual(self.launches, [])

    def test_no_last_actor_is_inferred_from_existing_profiles(self):
        self.prepare(remember=False)
        result = self.call([], interactive=False)
        self.assertEqual(result[0], 2)
        self.assertIn("actor setup", result[2])
        self.assertEqual(result[3], 0)
        self.assertFalse(launch_path().exists())

    def test_missing_registered_last_actor_requires_an_explicit_label(self):
        remember_launch("Ada", self.directory / "reading.sqlite3", CORPUS_ID, "0" * 64)
        result = self.call([], ["Bob", "bob-reading"])
        self.assertEqual(result[0], 0, result[2])
        self.assertEqual(result[3], 2)
        self.assertEqual(self.launches[-1][0], "Bob")
        self.assertEqual([profile["name"] for profile in list_actors()], ["Bob"])

    def test_failed_workspace_validation_does_not_replace_remembered_session(self):
        self.prepare()
        before = read_launch_preferences()
        invalid = self.directory / "broken.sqlite3"
        invalid.write_bytes(b"preserve invalid workspace")
        result = self.call(["--actor", "Bob", "--workspace", "broken", "--workspace-dir", str(self.directory)])
        self.assertEqual(result[0], 2)
        self.assertEqual(read_launch_preferences(), before)
        self.assertEqual([profile["name"] for profile in list_actors()], ["Ada"])
        self.assertEqual(invalid.read_bytes(), b"preserve invalid workspace")

    def test_temporary_random_and_inspection_leave_last_session_unchanged(self):
        self.prepare()
        before = launch_path().read_bytes()
        for arguments in (["-n"], ["-r"], ["--structure"], ["--workspace", "reading", "--actor", "Bob",
                                                            "--workspace-dir", str(self.directory), "--first", "/being"]):
            with self.subTest(arguments=arguments):
                result = self.call(arguments, interactive=False)
                self.assertEqual(result[0], 0, result[2])
                self.assertEqual(launch_path().read_bytes(), before)
        self.assertEqual([profile["name"] for profile in list_actors()], ["Ada"])


if __name__ == "__main__":
    unittest.main()
