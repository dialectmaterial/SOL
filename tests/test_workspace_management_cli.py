"""Local workspace lifecycle needs neither a book nor an interactive reader."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from sol.reader import app
from sol.workspace.launch import read_launch_preferences, remember_launch
from sol.workspace.profiles import profile_path, register_actor
from sol.workspace.store import Workspace


CORPUS = "aaaaaaaa-0000-4000-8000-000000000001"
SOURCE = "a" * 64


class WorkspaceManagementCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-workspace-management-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.environment = patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root / "data"),
                                                   "XDG_CONFIG_HOME": str(self.root / "config")})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.directory = self.root / "data" / "sol" / "workspaces"

    def call(self, *arguments):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error), \
                patch.object(app, "discover_corpus", side_effect=AssertionError("No corpus discovery")), \
                patch.object(app, "shell_identity", side_effect=AssertionError("No onboarding")), \
                patch("sol.terminal.neovim.validate_environment", side_effect=AssertionError("No terminal needed")):
            status = app.main(list(arguments))
        return status, output.getvalue(), error.getvalue()

    def workspace(self, name="reading"):
        path = self.directory / (name + ".sqlite3")
        with Workspace(path, CORPUS, {"source_sha256": SOURCE}, actor="Invented actor"):
            pass
        return path

    def test_missing_directory_listing_does_not_create_personal_storage(self):
        status, output, error = self.call("--workspace-list", "--json")
        self.assertEqual((status, json.loads(output), error), (0, [], ""))
        self.assertFalse((self.root / "data").exists())
        self.assertFalse((self.root / "config").exists())

    def test_listing_reports_exact_local_names_without_opening_or_changing_them(self):
        path = self.workspace()
        before = path.read_bytes()
        status, output, error = self.call("--workspace-list", "--json")
        self.assertEqual((status, error), (0, ""))
        rows = json.loads(output)
        self.assertEqual([(row["name"], row["path"]) for row in rows], [("reading", str(path))])
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(profile_path().exists())

    def test_removal_is_recoverable_and_forgets_only_the_removed_launch_choice(self):
        path = self.workspace()
        other = self.workspace("other")
        register_actor("Invented actor")
        register_actor("Another actor")
        remember_launch("Invented actor", path, CORPUS, SOURCE)
        remember_launch("Another actor", other, CORPUS, SOURCE)
        profiles_before = profile_path().read_bytes()
        database_before = path.read_bytes()
        status, output, error = self.call("--workspace-delete", "reading", "--json")
        self.assertEqual((status, error), (0, ""))
        removed = json.loads(output)
        self.assertFalse(path.exists())
        self.assertEqual(Path(removed["recovery_path"]).read_bytes(), database_before)
        preferences = read_launch_preferences()
        self.assertEqual(preferences["last_actor"], "Another actor")
        self.assertEqual([choice["workspace"] for choice in preferences["selections"]], [str(other)])
        self.assertEqual(profile_path().read_bytes(), profiles_before)
        self.assertEqual(json.loads(self.call("--workspace-list", "--json")[1])[0]["name"], "other")

    def test_plain_removal_reports_recovery_location_and_preserved_authority(self):
        self.workspace()
        status, output, error = self.call("--workspace-delete", "reading")
        self.assertEqual((status, error), (0, ""))
        self.assertIn("Removed workspace: reading", output)
        self.assertIn("Recoverable database:", output)
        self.assertIn("canonical corpus were not changed", output)

    def test_missing_or_unsafe_names_fail_without_creation(self):
        for name in ("missing", "../elsewhere", "/absolute", ".", "a.sqlite3"):
            with self.subTest(name=name):
                status, output, error = self.call("--workspace-delete", name)
                self.assertEqual(status, 2)
                self.assertFalse(output)
                self.assertTrue(error)
        self.assertFalse((self.root / "data").exists())

    def test_management_rejects_unrelated_flags_before_storage_access(self):
        for flag in (("being",), ("-n",), ("--actor", "Somebody"),
                     ("--workspace", "reading"), ("--width", "0"),
                     ("--corpus", "missing"), ("--plain",), ("--depth", "1")):
            with self.subTest(flag=flag), \
                    patch("sol.workspace.lifecycle.list_workspaces", side_effect=AssertionError("No storage")):
                status, output, error = self.call("--workspace-list", *flag)
                self.assertEqual(status, 2)
                self.assertFalse(output)
                self.assertIn("workspace listing/removal", error)

    def test_custom_directory_is_exact_and_does_not_touch_the_default(self):
        path = self.workspace()
        custom = self.root / "custom"
        with Workspace(custom / "separate.sqlite3", CORPUS, {"source_sha256": SOURCE}):
            pass
        before = path.read_bytes()
        status, output, error = self.call("--workspace-delete", "separate", "--workspace-dir", str(custom), "--json")
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(Path(json.loads(output)["recovery_path"]).parent.parent, custom / ".trash")
        self.assertEqual(path.read_bytes(), before)

    def test_removed_workspace_recovery_is_reported_even_if_preferences_are_damaged(self):
        path = self.workspace()
        with patch("sol.workspace.launch.forget_workspace", side_effect=ValueError("Invented damaged preference")):
            status, output, error = self.call("--workspace-delete", "reading", "--json")
        self.assertEqual(status, 0)
        self.assertFalse(path.exists())
        result = json.loads(output)
        self.assertTrue(Path(result["recovery_path"]).exists())
        self.assertIn("preferences_warning", result)
        self.assertIn("workspace removed", error)


if __name__ == "__main__":
    unittest.main()
