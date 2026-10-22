"""Recoverable removal tests use only invented, disposable local databases."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from sol.being.workspace.lifecycle import delete_workspace, list_workspaces
from sol.being.workspace.store import APPLICATION_ID, Workspace, WorkspaceError, _SCHEMA, fcntl


CORPUS = "dddddddd-0000-4000-8000-000000000004"
OTHER_CORPUS = "eeeeeeee-0000-4000-8000-000000000005"
PASSAGE = "aaaaaaaa-0000-4000-8000-000000000001"
SOURCE = "b" * 64
CREATED = "2025-01-01T00:00:00Z"


class WorkspaceLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-lifecycle-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / "workspaces"
        self.directory.mkdir(mode=0o700)

    def v1(self, name="reading", *, corpus=CORPUS, source=SOURCE):
        path = self.directory / (name + ".sqlite3")
        with closing(sqlite3.connect(path)) as connection:
            with connection:
                for statement in _SCHEMA:
                    connection.execute(statement)
                connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                connection.execute("PRAGMA user_version=1")
                connection.execute("INSERT INTO workspace_metadata VALUES(1,1,?,?,?)",
                                   (corpus, json.dumps({"source_sha256": source}), CREATED))
        return path

    def fingerprint(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def remove(self, name="reading"):
        return delete_workspace(name, self.directory)

    def assert_intact(self, path, digest):
        self.assertTrue(path.is_file())
        self.assertEqual(self.fingerprint(path), digest)

    def test_missing_catalog_does_not_create_any_directory(self):
        missing = self.root / "missing" / "workspaces"
        self.assertEqual(list_workspaces(missing), [])
        self.assertFalse(missing.parent.exists())

    def test_catalog_lists_all_recognized_identities_without_writing(self):
        beta = self.v1("beta", corpus=OTHER_CORPUS, source=None)
        alpha = self.v1("alpha")
        before = {path.name: self.fingerprint(path) for path in (alpha, beta)}
        rows = list_workspaces(self.directory)
        self.assertEqual([row["name"] for row in rows], ["alpha", "beta"])
        self.assertEqual(rows[0], {
            "name": "alpha", "path": str(alpha), "corpus_id": CORPUS,
            "source_sha256": SOURCE, "schema_version": 1, "created_at": CREATED,
        })
        self.assertEqual(rows[1]["corpus_id"], OTHER_CORPUS)
        self.assertIsNone(rows[1]["source_sha256"])
        self.assertEqual({path.name: self.fingerprint(path) for path in (alpha, beta)}, before)
        self.assertEqual(set(self.directory.iterdir()), {alpha, beta})

    def test_default_catalog_uses_xdg_without_inspecting_or_mutating_actors(self):
        target = self.root / "sol" / "workspaces"
        target.parent.mkdir()
        self.directory.rename(target)
        self.directory = target
        self.v1()
        registry = target.parent / "profiles.sqlite3"
        registry.write_bytes(b"invented actor registry, not a workspace")
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root)}):
            self.assertEqual([row["name"] for row in list_workspaces()], ["reading"])
        self.assertEqual(registry.read_bytes(), b"invented actor registry, not a workspace")

    def test_catalog_omits_foreign_corrupt_and_unsafe_names(self):
        good = self.v1("good")
        foreign = self.v1("foreign")
        with closing(sqlite3.connect(foreign)) as connection:
            connection.execute("PRAGMA application_id=1")
        (self.directory / "broken.sqlite3").write_bytes(b"broken")
        self.v1("unsafe name")
        (self.directory / "directory.sqlite3").mkdir()
        self.assertEqual([row["name"] for row in list_workspaces(self.directory)], ["good"])
        self.assertTrue(good.exists())

    def test_catalog_and_removal_reject_symlinked_directory_or_ancestor(self):
        self.v1()
        link = self.root / "linked"
        link.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaisesRegex(WorkspaceError, "symbolic links"):
            list_workspaces(link)
        with self.assertRaisesRegex(WorkspaceError, "symbolic links"):
            delete_workspace("reading", link)
        ancestor = self.root / "ancestor"
        ancestor.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(WorkspaceError, "symbolic links"):
            list_workspaces(ancestor / "workspaces")

    def test_relative_xdg_is_rejected_without_creating_it(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": "relative-location"}):
            with self.assertRaisesRegex(WorkspaceError, "absolute"):
                list_workspaces()

    def test_directory_inspection_errors_are_public_workspace_errors(self):
        path = self.v1()
        digest = self.fingerprint(path)
        for error in (PermissionError("directory denied"), FileNotFoundError("directory changed")):
            for operation in (lambda: list_workspaces(self.directory), lambda: self.remove()):
                with self.subTest(error=type(error).__name__), \
                        patch("sol.being.workspace.lifecycle._root", side_effect=error):
                    with self.assertRaisesRegex(WorkspaceError, "cannot (list|prepare)"):
                        operation()
        self.assert_intact(path, digest)
        self.assertFalse((self.directory / ".trash").exists())

    def test_unreadable_or_racing_file_is_reported_without_modifying_it(self):
        path = self.v1()
        digest = self.fingerprint(path)
        for error in (PermissionError("file denied"), FileNotFoundError("file changed")):
            with self.subTest(error=type(error).__name__), \
                    patch("sol.being.workspace.lifecycle.os.open", side_effect=error):
                with self.assertRaisesRegex(WorkspaceError, "cannot prepare workspace removal"):
                    self.remove()
                # An unreadable candidate remains omitted from the read-only
                # catalog; an explicit deletion must instead explain failure.
                self.assertEqual(list_workspaces(self.directory), [])
        self.assert_intact(path, digest)
        self.assertFalse((self.directory / ".trash").exists())

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_removal_retains_exact_original_bytes_in_private_recovery_directory(self):
        path = self.v1()
        digest = self.fingerprint(path)
        result = self.remove()
        recovery = Path(result["recovery_path"])
        self.assertFalse(path.exists())
        self.assertEqual(result["path"], str(path))
        self.assertEqual(result["corpus_id"], CORPUS)
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(recovery.name, "reading.sqlite3")
        self.assertEqual(recovery.parent.parent, self.directory / ".trash")
        self.assertEqual(self.fingerprint(recovery), digest)
        self.assertEqual(stat.S_IMODE(recovery.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(recovery.parent.parent.stat().st_mode), 0o700)
        self.assertEqual(list_workspaces(self.directory), [])
        # No format migration or note/position rewriting happened while moving.
        with Workspace(recovery, CORPUS, {"source_sha256": SOURCE}, read_only=True) as workspace:
            self.assertEqual(workspace.schema_version, 1)
            self.assertIsNone(workspace.get_state())
        recovery.rename(path)
        self.assertEqual([row["name"] for row in list_workspaces(self.directory)], ["reading"])
        self.assert_intact(path, digest)

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_current_workspace_cursor_notes_and_actor_registry_are_preserved(self):
        path = self.directory / "modern.sqlite3"
        registry = self.root / "profiles.sqlite3"
        registry.write_bytes(b"untouched actor identity")
        with Workspace(path, CORPUS, {"source_sha256": SOURCE}, actor="Researcher") as workspace:
            workspace.save_state({"cwd": "/BEING", "scope": "/BEING", "current_id": PASSAGE})
            note = workspace.add_annotation(PASSAGE, "A personally attributed invented note")
            old_state = workspace.get_state()
        digest = self.fingerprint(path)
        recovery = Path(self.remove("modern")["recovery_path"])
        self.assertEqual(self.fingerprint(recovery), digest)
        with Workspace(recovery, CORPUS, {"source_sha256": SOURCE}, read_only=True) as workspace:
            self.assertEqual(workspace.get_state(), old_state)
            self.assertEqual(workspace.get_annotation(note["id"]), note)
        self.assertEqual(registry.read_bytes(), b"untouched actor identity")

    def test_invalid_names_never_resolve_as_paths(self):
        path = self.v1()
        digest = self.fingerprint(path)
        for name in ("", ".", "..", "../reading", "/reading", "reading.sqlite3", "a/b", "a\\b", "a\n", None):
            with self.subTest(name=name), self.assertRaisesRegex(WorkspaceError, "workspace name"):
                self.remove(name)
        self.assert_intact(path, digest)
        self.assertFalse((self.directory / ".trash").exists())

    def test_missing_workspace_is_not_created(self):
        with self.assertRaisesRegex(WorkspaceError, "does not exist"):
            self.remove("absent")
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_symlink_and_hardlink_targets_are_not_removed(self):
        path = self.v1()
        digest = self.fingerprint(path)
        symlink = self.directory / "alias.sqlite3"
        symlink.symlink_to(path)
        with self.assertRaisesRegex(WorkspaceError, "symbolic or hard link"):
            self.remove("alias")
        hardlink = self.directory / "hard.sqlite3"
        os.link(path, hardlink)
        with self.assertRaisesRegex(WorkspaceError, "symbolic or hard link"):
            self.remove("hard")
        self.assert_intact(path, digest)
        self.assertTrue(symlink.is_symlink())
        self.assertTrue(hardlink.is_file())

    def test_sidecars_including_dangling_links_prevent_inspection_and_removal(self):
        path = self.v1()
        digest = self.fingerprint(path)
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                sidecar = Path(str(path) + suffix)
                sidecar.symlink_to(self.root / "absent")
                with self.assertRaisesRegex(WorkspaceError, "sidecars"):
                    self.remove()
                self.assertEqual(list_workspaces(self.directory), [])
                sidecar.unlink()
        self.assert_intact(path, digest)

    def test_wal_header_is_refused_even_after_sidecars_disappear(self):
        path = self.v1()
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
        digest = self.fingerprint(path)
        with self.assertRaisesRegex(WorkspaceError, "WAL workspace"):
            self.remove()
        self.assertEqual(list_workspaces(self.directory), [])
        self.assert_intact(path, digest)

    def test_corrupt_and_foreign_schema_are_retained(self):
        path = self.v1()
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE foreign_table (value TEXT)")
        digest = self.fingerprint(path)
        with self.assertRaisesRegex(WorkspaceError, "schema.*unrecognized"):
            self.remove()
        self.assertEqual(list_workspaces(self.directory), [])
        self.assert_intact(path, digest)

    def test_foreign_application_id_is_retained(self):
        path = self.v1()
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("PRAGMA application_id=123")
        digest = self.fingerprint(path)
        with self.assertRaisesRegex(WorkspaceError, "not a recognized SOL workspace"):
            self.remove()
        self.assert_intact(path, digest)

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_idle_sol_workspace_is_refused_even_without_proc_detection(self):
        path = self.v1()
        digest = self.fingerprint(path)
        with Workspace(path, CORPUS, {"source_sha256": SOURCE}) as active:
            with patch("sol.being.workspace.lifecycle._refuse_open_inode"):
                with self.assertRaisesRegex(WorkspaceError, "open in SOL"):
                    self.remove()
            self.assertIsNone(active.get_state())
        self.assert_intact(path, digest)
        self.assertFalse((self.directory / ".trash").exists())

    @unittest.skipUnless(Path("/proc/self/fd").is_dir(), "Linux descriptor detection")
    def test_idle_raw_sqlite_connection_is_refused_on_linux(self):
        path = self.v1()
        digest = self.fingerprint(path)
        with closing(sqlite3.connect(path)) as active:
            active.execute("SELECT * FROM workspace_metadata").fetchall()
            with self.assertRaisesRegex(WorkspaceError, "open in a running process"):
                self.remove()
        self.assert_intact(path, digest)

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_external_sqlite_write_transaction_is_refused_without_proc(self):
        path = self.v1()
        digest = self.fingerprint(path)
        with closing(sqlite3.connect(path, isolation_level=None)) as active:
            active.execute("BEGIN IMMEDIATE")
            with patch("sol.being.workspace.lifecycle._refuse_open_inode"):
                with self.assertRaisesRegex(WorkspaceError, "locked"):
                    self.remove()
            active.rollback()
        self.assert_intact(path, digest)

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_new_sol_open_cannot_bypass_exclusive_lifecycle_lease(self):
        path = self.v1()
        descriptor = os.open(path, os.O_RDONLY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(WorkspaceError, "cannot open workspace"):
                Workspace(path, CORPUS, {"source_sha256": SOURCE})
        finally:
            os.close(descriptor)
        with Workspace(path, CORPUS, {"source_sha256": SOURCE}) as workspace:
            self.assertIsNone(workspace.get_state())

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_close_releases_lease_and_is_idempotent(self):
        path = self.v1()
        workspace = Workspace(path, CORPUS, {"source_sha256": SOURCE})
        self.assertIsNotNone(workspace._lease_descriptor)
        workspace.close()
        workspace.close()
        self.assertIsNone(workspace._lease_descriptor)
        self.assertTrue(Path(self.remove()["recovery_path"]).exists())

    def test_unsupported_host_refuses_removal_without_touching_data(self):
        path = self.v1()
        digest = self.fingerprint(path)
        with patch("sol.being.workspace.lifecycle.fcntl", None):
            with self.assertRaisesRegex(WorkspaceError, "POSIX file locking"):
                self.remove()
        self.assert_intact(path, digest)
        self.assertFalse((self.directory / ".trash").exists())

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_unsafe_existing_trash_is_not_followed_or_repermissioned(self):
        path = self.v1()
        digest = self.fingerprint(path)
        trash = self.directory / ".trash"
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        trash.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(WorkspaceError, "private, current-user directory"):
            self.remove()
        self.assertTrue(trash.is_symlink())
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assert_intact(path, digest)
        trash.unlink()
        trash.mkdir(mode=0o755)
        with self.assertRaisesRegex(WorkspaceError, "private, current-user directory"):
            self.remove()
        self.assertEqual(stat.S_IMODE(trash.stat().st_mode), 0o755)
        self.assert_intact(path, digest)

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_archive_name_collision_never_overwrites_existing_recovery(self):
        path = self.v1()
        digest = self.fingerprint(path)
        moment = datetime(2025, 2, 1, tzinfo=timezone.utc)
        identifier = UUID("11111111-1111-4111-8111-111111111111")
        trash = self.directory / ".trash"
        trash.mkdir(mode=0o700)
        occupied = trash / f"reading-20250201T000000000000Z-{identifier.hex}"
        occupied.mkdir(mode=0o700)
        prior = occupied / "reading.sqlite3"
        prior.write_bytes(b"prior recovery must remain")
        with patch("sol.being.workspace.lifecycle.datetime") as clock:
            clock.now.return_value = moment
            with patch("sol.being.workspace.lifecycle.uuid4", return_value=identifier):
                with self.assertRaisesRegex(WorkspaceError, "cannot complete workspace removal"):
                    self.remove()
        self.assertEqual(prior.read_bytes(), b"prior recovery must remain")
        self.assert_intact(path, digest)

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_failed_archive_link_keeps_original_and_removes_only_empty_attempt(self):
        path = self.v1()
        digest = self.fingerprint(path)
        with patch("sol.being.workspace.lifecycle.os.link", side_effect=OSError("injected link failure")):
            with self.assertRaisesRegex(WorkspaceError, "cannot complete workspace removal"):
                self.remove()
        self.assert_intact(path, digest)
        self.assertEqual(list((self.directory / ".trash").iterdir()), [])

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_failed_recovery_flush_retains_both_names_instead_of_removing_data(self):
        path = self.v1()
        digest = self.fingerprint(path)
        with patch("sol.being.workspace.lifecycle._sync_directory", side_effect=OSError("injected fsync failure")):
            with self.assertRaisesRegex(WorkspaceError, "recovery retained at"):
                self.remove()
        self.assert_intact(path, digest)
        recoveries = list((self.directory / ".trash").glob("*/reading.sqlite3"))
        self.assertEqual(len(recoveries), 1)
        self.assertEqual(self.fingerprint(recoveries[0]), digest)

    @unittest.skipIf(fcntl is None, "safe removal requires POSIX file locks")
    def test_lease_remains_exclusive_until_original_name_is_removed(self):
        path = self.v1()
        link = os.link

        def attempt_open_then_link(*arguments, **keywords):
            with self.assertRaisesRegex(WorkspaceError, "cannot open workspace"):
                Workspace(path, CORPUS, {"source_sha256": SOURCE})
            return link(*arguments, **keywords)

        with patch("sol.being.workspace.lifecycle.os.link", side_effect=attempt_open_then_link):
            result = self.remove()
        self.assertFalse(path.exists())
        self.assertTrue(Path(result["recovery_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
