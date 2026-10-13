"""Invented notes exercise audited edits without touching a real workspace."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch

from sol.workspace.store import (APPLICATION_ID, Workspace, WorkspaceConflict, WorkspaceError,
                           _SCHEMA, _ANNOTATION_SCHEMA)
from test_workspace import A, B, C, CORPUS_ID, CONTENT_SHA, PROVENANCE, state, stable_export


LEGACY_TIME = "2020-01-01T00:00:00Z"
LEGACY_UPDATE = "2021-02-03T04:05:06Z"
UPGRADE_TIME = "2026-10-12T12:00:00Z"


def make_legacy(path: Path, *, annotation=True) -> None:
    """Build the genuine frozen v1 schema, not a downgraded v2 database."""
    connection = sqlite3.connect(path)
    try:
        for statement in _SCHEMA:
            connection.execute(statement)
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute("PRAGMA user_version = 1")
        import json
        connection.execute("INSERT INTO workspace_metadata VALUES(1,1,?,?,?)",
                           (CORPUS_ID, json.dumps(PROVENANCE), LEGACY_TIME))
        if annotation:
            connection.execute("INSERT INTO annotations VALUES(?,?,?,?,?,?,?,1)",
                               (C, A, "Legacy surviving body.", "Researcher", LEGACY_TIME,
                                LEGACY_UPDATE, CONTENT_SHA))
        connection.commit()
    finally:
        connection.close()


class AnnotationRevisionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="sol-annotation-revision-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "workspace.sqlite3"
        self.workspace = self.open(self.path)

    def open(self, path, actor="Researcher", **options):
        workspace = Workspace(path, CORPUS_ID, deepcopy(PROVENANCE), actor, **options)
        self.addCleanup(workspace.close)
        return workspace

    def legacy(self, annotation=True):
        path = self.root / "legacy.sqlite3"
        make_legacy(path, annotation=annotation)
        return self.open(path)

    def test_created_note_has_truthful_first_snapshot(self):
        self.assertEqual(self.workspace.schema_version, 2)
        note = self.workspace.add_annotation(A, "Personal note.", CONTENT_SHA)
        self.assertEqual(note["revision"], 1)
        history = self.workspace.list_annotation_history(note["id"])
        self.assertEqual(len(history), 1)
        snapshot = history[0]
        for field in ("target_id", "actor", "created_at", "updated_at", "body", "content_sha256"):
            self.assertEqual(snapshot[field], note[field])
        self.assertEqual(snapshot["annotation_id"], note["id"])
        self.assertEqual(snapshot["editor"], "Researcher")
        self.assertEqual(snapshot["kind"], "created")
        self.assertEqual(snapshot["recorded_at"], note["created_at"])
        self.assertEqual(snapshot["corpus_id"], CORPUS_ID)
        self.assertEqual(self.open(self.path).get_annotation(note["id"]), note)

    def test_edit_appends_snapshots_freezes_original_provenance_and_checkpoint(self):
        self.workspace.save_state(state(B))
        note = self.workspace.add_annotation(A, "Original thought.", CONTENT_SHA)
        reading_before = self.workspace.get_state()
        updated = self.workspace.update_annotation(note["id"], "Revised thought.\n\tSecond line.",
                                                   expected_revision=1)
        self.assertEqual(updated["revision"], 2)
        for field in ("id", "target_id", "actor", "created_at", "content_sha256", "attribution"):
            self.assertEqual(updated[field], note[field])
        snapshots = self.workspace.list_annotation_history(note["id"])
        self.assertEqual([row["body"] for row in snapshots],
                         ["Original thought.", "Revised thought.\n\tSecond line."])
        self.assertEqual([row["kind"] for row in snapshots], ["created", "edited"])
        self.assertEqual(snapshots[1]["recorded_at"], updated["updated_at"])
        self.assertEqual(self.workspace.get_state(), reading_before)
        self.assertEqual(len(self.workspace.list_history()), 1)
        self.open(self.path)

    def test_edits_require_positive_explicit_nonboolean_expected_revision(self):
        note = self.workspace.add_annotation(A, "Original.")
        before = stable_export(self.workspace)
        for revision in (None, True, False, 0, -1, "1", 1.0):
            with self.subTest(revision=revision), self.assertRaisesRegex(WorkspaceError, "explicit positive"):
                self.workspace.update_annotation(note["id"], "Changed.", expected_revision=revision)
        with self.assertRaisesRegex(WorkspaceError, "explicit positive"):
            self.workspace.update_annotation(note["id"], "Changed.")
        self.assertEqual(stable_export(self.workspace), before)

    def test_same_body_is_noop_but_stale_revision_still_conflicts(self):
        note = self.workspace.add_annotation(A, "Original.", CONTENT_SHA)
        before = stable_export(self.workspace)
        with patch("sol.workspace.store._now", side_effect=AssertionError("no timestamp needed")):
            same = self.workspace.update_annotation(note["id"], note["body"], CONTENT_SHA,
                                                    expected_revision=1)
        self.assertEqual(same, note)
        self.assertEqual(stable_export(self.workspace), before)
        updated = self.workspace.update_annotation(note["id"], "Changed.", expected_revision=1)
        with self.assertRaises(WorkspaceConflict):
            self.workspace.update_annotation(note["id"], updated["body"], expected_revision=1)
        self.assertEqual(len(self.workspace.list_annotation_history(note["id"])), 2)

    def test_two_connections_cannot_overwrite_another_editor_revision(self):
        note = self.workspace.add_annotation(A, "Original.")
        other = self.open(self.path)
        stale = other.get_annotation(note["id"])
        updated = self.workspace.update_annotation(note["id"], "First edit.", expected_revision=1)
        with self.assertRaisesRegex(WorkspaceConflict, "another session"):
            other.update_annotation(note["id"], "Lost edit.", expected_revision=stale["revision"])
        self.assertEqual(other.get_annotation(note["id"]), updated)
        latest = other.update_annotation(note["id"], "Second edit.", expected_revision=2)
        self.assertEqual(latest["revision"], 3)
        self.assertEqual([row["revision"] for row in self.workspace.list_annotation_history(note["id"])],
                         [1, 2, 3])

    def test_actor_match_digest_immutability_and_safe_body_are_required(self):
        note = self.workspace.add_annotation(A, "Original.", CONTENT_SHA)
        other = self.open(self.path, actor="Another reader")
        before = stable_export(self.workspace)
        with self.assertRaisesRegex(WorkspaceError, "another actor"):
            other.update_annotation(note["id"], "Changed.", expected_revision=1)
        with self.assertRaisesRegex(WorkspaceError, "immutable"):
            self.workspace.update_annotation(note["id"], "Changed.", "f" * 64, expected_revision=1)
        for body in ("", " \n\t", "bad\x00", "bad\x1b", "bad\r", "bad\u202e", "bad\ud800"):
            with self.subTest(body=repr(body)), self.assertRaises(WorkspaceError):
                self.workspace.update_annotation(note["id"], body, expected_revision=1)
        self.assertEqual(stable_export(self.workspace), before)

    def test_null_original_digest_cannot_be_rebound_during_edit(self):
        note = self.workspace.add_annotation(A, "Original.")
        with self.assertRaisesRegex(WorkspaceError, "immutable"):
            self.workspace.update_annotation(note["id"], "Changed.", CONTENT_SHA, expected_revision=1)
        updated = self.workspace.update_annotation(note["id"], "Changed.", expected_revision=1)
        self.assertIsNone(updated["content_sha256"])

    def test_sql_cannot_modify_history_delete_note_or_mutate_provenance(self):
        note = self.workspace.add_annotation(A, "Original.", CONTENT_SHA)
        connection = self.workspace._connection
        attempts = [
            ("UPDATE annotation_history SET body='forged'", ()),
            ("DELETE FROM annotation_history", ()),
            ("DELETE FROM annotations", ()),
            ("UPDATE annotations SET target_id=?", (B,)),
            ("UPDATE annotations SET actor='Other'", ()),
            ("UPDATE annotations SET id=?", (C,)),
            ("UPDATE annotations SET created_at=?", (LEGACY_TIME,)),
            ("UPDATE annotations SET content_sha256=?", ("f" * 64,)),
            ("UPDATE annotations SET body='unlogged'", ()),
        ]
        for sql, arguments in attempts:
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                connection.execute(sql, arguments)
        with self.assertRaisesRegex(WorkspaceError, "cannot be deleted"):
            self.workspace.delete_annotation(note["id"])
        self.assertEqual(self.workspace.get_annotation(note["id"]), note)
        self.open(self.path)

    def test_failed_projection_update_rolls_back_inserted_audit(self):
        note = self.workspace.add_annotation(A, "Original.")
        connection = self.workspace._connection
        connection.execute("CREATE TRIGGER synthetic_fail BEFORE UPDATE ON annotations "
                           "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        try:
            with self.assertRaisesRegex(WorkspaceError, "synthetic failure"):
                self.workspace.update_annotation(note["id"], "Changed.", expected_revision=1)
        finally:
            connection.execute("DROP TRIGGER synthetic_fail")
        self.assertEqual(self.workspace.get_annotation(note["id"]), note)
        self.assertEqual(len(self.workspace.list_annotation_history(note["id"])), 1)
        self.open(self.path)

    def test_clock_rollback_refuses_edit_before_any_saved_changes(self):
        self.workspace.save_state(state())
        with patch("sol.workspace.store._now", return_value="2026-10-12T12:00:00Z"):
            note = self.workspace.add_annotation(A, "Original.")
        before = stable_export(self.workspace)
        source_bytes = self.path.read_bytes()
        with patch("sol.workspace.store._now", return_value="2026-10-12T11:59:59Z"):
            with self.assertRaisesRegex(WorkspaceError, "system clock precedes"):
                self.workspace.update_annotation(note["id"], "Changed.", expected_revision=1)
        self.assertEqual(stable_export(self.workspace), before)
        self.assertEqual(self.path.read_bytes(), source_bytes)
        self.assertFalse(self.workspace._connection.in_transaction)
        self.open(self.path)

    def test_long_lived_editor_refuses_malformed_concurrent_audit_head(self):
        note = self.workspace.add_annotation(A, "Original.")
        other = self.open(self.path)
        connection = other._connection
        connection.execute("DROP TRIGGER annotation_history_no_update")
        connection.execute("UPDATE annotation_history SET body='forged body'")
        connection.execute(next(sql for sql in _ANNOTATION_SCHEMA
                                if sql.startswith("CREATE TRIGGER annotation_history_no_update")))
        before = stable_export(self.workspace)
        with self.assertRaisesRegex(WorkspaceError, "projection and latest history"):
            self.workspace.update_annotation(note["id"], "Changed.", expected_revision=1)
        self.assertEqual(stable_export(self.workspace), before)
        self.assertEqual(self.workspace.get_annotation(note["id"])["revision"], 1)
        self.assertFalse(self.workspace._connection.in_transaction)

    def test_missing_annotation_or_history_has_documented_behavior(self):
        self.assertIsNone(self.workspace.get_annotation(C))
        self.assertEqual(self.workspace.list_annotation_history(C), [])
        with self.assertRaisesRegex(WorkspaceError, "no such annotation"):
            self.workspace.update_annotation(C, "Changed.", expected_revision=1)
        with self.assertRaises(WorkspaceError):
            self.workspace.list_annotation_history("prefix")

    def test_validator_detects_mutated_audit_snapshot_even_after_trigger_restored(self):
        for alteration, parameters in (
            ("body = 'forged'", ()), ("target_id = ?", (B,)),
            ("editor = 'Other'", ()), ("recorded_at = 'not a time'", ()),
            ("kind = 'edited'", ()), ("revision = 2", ()),
        ):
            with self.subTest(alteration=alteration):
                path = self.root / ("tamper-" + str(len(list(self.root.iterdir()))) + ".sqlite3")
                workspace = self.open(path)
                workspace.add_annotation(A, "Original.")
                connection = workspace._connection
                connection.execute("DROP TRIGGER annotation_history_no_update")
                connection.execute("UPDATE annotation_history SET " + alteration, parameters)
                connection.execute(next(sql for sql in _ANNOTATION_SCHEMA
                                        if sql.startswith("CREATE TRIGGER annotation_history_no_update")))
                workspace.close()
                with self.assertRaises(WorkspaceError):
                    self.open(path)

    def test_validator_detects_missing_history_and_missing_protection(self):
        note = self.workspace.add_annotation(A, "Original.")
        connection = self.workspace._connection
        connection.execute("DROP TRIGGER annotation_history_no_delete")
        connection.execute("DELETE FROM annotation_history")
        connection.execute(next(sql for sql in _ANNOTATION_SCHEMA
                                if sql.startswith("CREATE TRIGGER annotation_history_no_delete")))
        with self.assertRaisesRegex(WorkspaceError, "audited revision"):
            self.open(self.path)
        connection.execute("DROP TRIGGER annotations_no_delete")
        with self.assertRaisesRegex(WorkspaceError, "protections"):
            self.open(self.path)

    def test_validator_refuses_latest_projection_changed_outside_audit(self):
        self.workspace.add_annotation(A, "Original.")
        connection = self.workspace._connection
        connection.execute("DROP TRIGGER annotations_audited_update")
        connection.execute("UPDATE annotations SET body='unlogged change'")
        connection.execute(next(sql for sql in _ANNOTATION_SCHEMA
                                if sql.startswith("CREATE TRIGGER annotations_audited_update")))
        with self.assertRaisesRegex(WorkspaceError, "projection and latest history"):
            self.open(self.path)

    def test_export_history_is_independent_and_in_revision_order(self):
        note = self.workspace.add_annotation(A, "Original.")
        self.workspace.update_annotation(note["id"], "Changed.", expected_revision=1)
        exported = self.workspace.export()
        self.assertEqual(exported["schema_version"], 2)
        self.assertEqual([row["revision"] for row in exported["annotation_history"]], [1, 2])
        exported["annotation_history"][0]["body"] = "change to exported value only"
        exported["annotations"][0]["body"] = "also independent"
        self.assertEqual(self.workspace.list_annotation_history(note["id"])[0]["body"], "Original.")
        self.assertEqual(self.workspace.get_annotation(note["id"])["body"], "Changed.")

    def test_genuine_v1_opens_unchanged_and_still_reads_and_adds_notes(self):
        legacy = self.legacy()
        before = legacy.path.read_bytes()
        self.assertEqual(legacy.schema_version, 1)
        self.assertIsNone(legacy.get_annotation(C)["revision"])
        self.assertEqual(legacy.list_annotation_history(C), [])
        self.assertEqual(legacy.path.read_bytes(), before)
        with self.assertRaisesRegex(WorkspaceError, "copy-upgrade"):
            legacy.update_annotation(C, "Changed.", expected_revision=1)
        with self.assertRaisesRegex(WorkspaceError, "copy-upgrade"):
            legacy.update_annotation(C, "Changed.")
        self.assertEqual(legacy.path.read_bytes(), before)
        legacy.save_state(state())
        new = legacy.add_annotation(B, "An ordinary new legacy note.", CONTENT_SHA)
        self.assertIsNone(new["revision"])
        exported = legacy.export()
        self.assertEqual(exported["schema_version"], 1)
        self.assertNotIn("annotation_history", exported)
        self.assertTrue(legacy.delete_annotation(new["id"]))
        self.open(legacy.path)

    def test_explicit_upgrade_copy_preserves_source_and_truthful_legacy_baseline(self):
        legacy = self.legacy()
        legacy.save_state(state())
        legacy.set_bookmark("start", A)
        legacy.add_relation(A, B, "contrast", "A reader's relation.")
        before = stable_export(legacy)
        source_bytes = legacy.path.read_bytes()
        target = self.root / "upgraded.sqlite3"
        with patch("sol.workspace.store._now", return_value=UPGRADE_TIME):
            self.assertEqual(legacy.upgrade_copy(target), target)
        upgraded = self.open(target)
        self.assertEqual(legacy.path.read_bytes(), source_bytes)
        self.assertEqual(stable_export(legacy), before)
        self.assertEqual(legacy.schema_version, 1)
        self.assertEqual(upgraded.schema_version, 2)
        old, new = legacy.get_annotation(C), upgraded.get_annotation(C)
        self.assertEqual({k: v for k, v in new.items() if k != "revision"},
                         {k: v for k, v in old.items() if k != "revision"})
        snapshot = upgraded.list_annotation_history(C)[0]
        self.assertEqual(snapshot["kind"], "legacy_baseline")
        self.assertIsNone(snapshot["editor"])
        self.assertEqual(snapshot["recorded_at"], UPGRADE_TIME)
        self.assertEqual(snapshot["created_at"], LEGACY_TIME)
        self.assertEqual(snapshot["updated_at"], LEGACY_UPDATE)
        self.assertEqual(snapshot["actor"], "Researcher")
        for key in ("state", "history", "bookmarks", "comparisons", "reviews", "relations"):
            self.assertEqual(upgraded.export()[key], before[key])
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        updated = upgraded.update_annotation(C, "First known edit after upgrade.", expected_revision=1)
        self.assertEqual(updated["revision"], 2)
        self.open(target)

    def test_empty_v1_can_be_copy_upgraded_and_new_notes_are_created_not_baselines(self):
        legacy = self.legacy(annotation=False)
        target = legacy.upgrade_copy(self.root / "empty-upgraded.sqlite3")
        upgraded = self.open(target)
        self.assertEqual(upgraded.export()["annotation_history"], [])
        note = upgraded.add_annotation(A, "New after upgrade.")
        self.assertEqual(upgraded.list_annotation_history(note["id"])[0]["kind"], "created")

    def test_backup_preserves_actual_format_for_v1_and_v2(self):
        self.workspace.add_annotation(A, "A v2 note.")
        for workspace in (self.workspace, self.legacy()):
            target = self.root / f"backup-v{workspace.schema_version}.sqlite3"
            workspace.backup(target)
            copy = self.open(target)
            self.assertEqual(copy.schema_version, workspace.schema_version)
            self.assertEqual(stable_export(copy), stable_export(workspace))
            if workspace.schema_version == 2:
                self.assertIn("annotation_history", copy.export())

    def test_copy_upgrade_refuses_v2_existing_self_symlink_and_missing_parent(self):
        with self.assertRaisesRegex(WorkspaceError, "already schema 2"):
            self.workspace.upgrade_copy(self.root / "bad.sqlite3")
        legacy = self.legacy()
        target = self.root / "existing.sqlite3"
        target.write_bytes(b"preserve this unrelated file")
        symlink = self.root / "symlink.sqlite3"
        symlink.symlink_to(target)
        attempts = (target, symlink, legacy.path, self.root / "absent" / "new.sqlite3",
                    self.root / "not-a-database.txt")
        for destination in attempts:
            with self.subTest(destination=destination), self.assertRaises(WorkspaceError):
                legacy.upgrade_copy(destination)
        self.assertEqual(target.read_bytes(), b"preserve this unrelated file")
        self.assertTrue(symlink.is_symlink())
        self.assertFalse((self.root / "absent").exists())
        self.assertFalse(list(self.root.glob(".sol-backup-*")))

    def test_migration_failure_publishes_nothing_and_preserves_original(self):
        legacy = self.legacy()
        source_bytes = legacy.path.read_bytes()
        target = self.root / "failed.sqlite3"
        original = Workspace._append_annotation_snapshot

        def fail_after_insert(workspace, *arguments):
            original(workspace, *arguments)
            raise WorkspaceError("synthetic migration failure")

        with patch.object(Workspace, "_append_annotation_snapshot", fail_after_insert):
            with self.assertRaisesRegex(WorkspaceError, "synthetic migration failure"):
                legacy.upgrade_copy(target)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob(".sol-backup-*")))
        self.assertEqual(legacy.path.read_bytes(), source_bytes)
        self.assertEqual(self.open(legacy.path).schema_version, 1)

    def test_copy_upgrade_publish_failure_after_migration_cleans_only_private_stage(self):
        legacy = self.legacy()
        source_bytes = legacy.path.read_bytes()
        target = self.root / "publish-failed.sqlite3"
        with patch("sol.workspace.store.os.link", side_effect=OSError("synthetic publish failure")):
            with self.assertRaisesRegex(WorkspaceError, "synthetic publish failure"):
                legacy.upgrade_copy(target)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob(".sol-backup-*")))
        self.assertEqual(legacy.path.read_bytes(), source_bytes)

    def test_copy_upgrade_racing_existing_destination_is_preserved(self):
        legacy = self.legacy()
        source_bytes = legacy.path.read_bytes()
        target = self.root / "racing.sqlite3"
        original_link = __import__("os").link

        def another_process_wins(staged, destination):
            Path(destination).write_bytes(b"unrelated winner")
            original_link(staged, destination)

        with patch("sol.workspace.store.os.link", side_effect=another_process_wins):
            with self.assertRaisesRegex(WorkspaceError, "already exists"):
                legacy.upgrade_copy(target)
        self.assertEqual(target.read_bytes(), b"unrelated winner")
        self.assertEqual(legacy.path.read_bytes(), source_bytes)
        self.assertFalse(list(self.root.glob(".sol-backup-*")))

    def test_readonly_validation_creates_nothing_and_refuses_writes(self):
        note = self.workspace.add_annotation(A, "A v2 note.")
        before_files = {path.name for path in self.root.iterdir()}
        before = self.path.read_bytes()
        readonly = self.open(self.path, read_only=True)
        self.assertTrue(readonly.read_only)
        self.assertEqual(readonly.get_annotation(note["id"]), note)
        self.assertEqual(stable_export(readonly), stable_export(self.workspace))
        with self.assertRaisesRegex(WorkspaceError, "read-only"):
            readonly.add_annotation(A, "Cannot write.")
        self.assertEqual(before_files, {path.name for path in self.root.iterdir()})
        self.assertEqual(self.path.read_bytes(), before)
        missing = self.root / "missing" / "workspace.sqlite3"
        with self.assertRaisesRegex(WorkspaceError, "already exist"):
            self.open(missing, read_only=True)
        self.assertFalse(missing.parent.exists())

    def test_readonly_inspection_fails_closed_for_wal_before_connecting(self):
        self.workspace._connection.execute("PRAGMA journal_mode = WAL")
        self.workspace.add_annotation(A, "A committed WAL note.")
        before = {path.name for path in self.root.iterdir()}
        with patch("sol.workspace.store.sqlite3.connect", side_effect=AssertionError("must not connect")):
            with self.assertRaisesRegex(WorkspaceError, "does not open WAL"):
                self.open(self.path, read_only=True)
        self.assertEqual(before, {path.name for path in self.root.iterdir()})


if __name__ == "__main__":
    unittest.main()
