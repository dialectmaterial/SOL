"""A personal workspace references invented UUIDs and never needs a corpus."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from sol_workspace import (
    APPLICATION_ID, SCHEMA_VERSION, Workspace, WorkspaceConflict, WorkspaceError,
)


A = "aaaaaaaa-0000-4000-8000-000000000001"
B = "bbbbbbbb-0000-4000-8000-000000000002"
C = "cccccccc-0000-4000-8000-000000000003"
CORPUS_ID = "dddddddd-0000-4000-8000-000000000004"
OTHER_CORPUS_ID = "eeeeeeee-0000-4000-8000-000000000005"
CONTENT_SHA = "a" * 64
SOURCE_SHA = "b" * 64
PROVENANCE = {
    "edition": {"title": "An invented philosophical book"},
    "source": {"filename": "Synthetic.pdf", "sha256": SOURCE_SHA},
}


def state(current_id=A, cwd="/BEING", scope="/BEING", previous_cwd="/"):
    return {"cwd": cwd, "scope": scope, "current_id": current_id,
            "previous_cwd": previous_cwd}


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="sol-workspace-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "private" / "workspace.sqlite3"
        self.workspace = Workspace(self.path, CORPUS_ID, deepcopy(PROVENANCE), actor="Researcher")
        self.addCleanup(self.workspace.close)

    def reopen(self, actor="Researcher", provenance=None):
        workspace = Workspace(self.path, CORPUS_ID, provenance or deepcopy(PROVENANCE), actor)
        self.addCleanup(workspace.close)
        return workspace

    def test_new_database_has_identity_version_foreign_keys_and_private_permissions(self):
        connection = self.workspace._connection
        self.assertEqual(connection.execute("PRAGMA application_id").fetchone()[0], APPLICATION_ID)
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertIsNone(self.workspace.get_state())
        self.assertEqual(self.workspace.list_history(), [])

    def test_context_manager_closes_and_close_is_idempotent(self):
        with self.reopen() as workspace:
            workspace.set_bookmark("start", A)
        workspace.close()
        with self.assertRaisesRegex(WorkspaceError, "closed"):
            workspace.get_state()

    def test_state_revision_and_reopen_preserve_explicit_selection(self):
        self.assertEqual(self.workspace.save_state(state(), None), 1)
        saved = self.workspace.get_state()
        self.assertEqual(saved, {**state(), "revision": 1})
        saved["cwd"] = "/ESSENCE"
        saved["scope"] = "/BEING"
        saved["current_id"] = B
        self.assertEqual(self.workspace.save_state(saved, 1), 2)
        self.workspace.close()
        self.assertEqual(self.reopen().get_state(), {**saved, "revision": 2})

    def test_state_current_and_previous_directory_may_be_null(self):
        expected = state(None, cwd="/", scope="/", previous_cwd=None)
        self.workspace.save_state(expected, None)
        self.assertEqual(self.workspace.get_state(), {**expected, "revision": 1})

    def test_concurrent_state_update_conflicts_without_losing_newer_data(self):
        self.workspace.save_state(state(), None)
        other = self.reopen(actor="Another reader")
        old = other.get_state()
        self.workspace.save_state(state(B), 1)
        with self.assertRaises(WorkspaceConflict):
            other.save_state({**old, "current_id": C}, old["revision"])
        self.assertEqual(other.get_state()["current_id"], B)
        self.assertEqual([row["revision"] for row in other.list_history()], [2, 1])

    def test_concurrent_first_checkpoint_does_not_overwrite(self):
        other = self.reopen()
        self.workspace.save_state(state(), None)
        with self.assertRaises(WorkspaceConflict):
            other.save_state(state(B), None)
        self.assertEqual(other.get_state()["current_id"], A)
        self.assertEqual(len(other.list_history()), 1)

    def test_state_requires_revision_agreement_and_valid_json_fields(self):
        invalid = [
            ("not an object", None), ({**state(), "unknown": 1}, None),
            ({**state(), "cwd": "BEING"}, None), ({**state(), "scope": None}, None),
            ({**state(), "current_id": "short-prefix"}, None),
            ({**state(), "previous_cwd": "relative"}, None),
            ({**state(), "revision": True}, 1), (state(), True), (state(), 0),
            ({**state(), "revision": 2}, 1),
        ]
        for value, revision in invalid:
            with self.subTest(value=value, revision=revision), self.assertRaises(WorkspaceError):
                self.workspace.save_state(value, revision)
        self.assertIsNone(self.workspace.get_state())
        self.assertEqual(self.workspace.list_history(), [])

    def test_history_keeps_old_references_actor_order_and_full_export(self):
        self.workspace.save_state(state(C), None)
        other = self.reopen(actor="Second reader")
        other.save_state(state(B, cwd="/ESSENCE", scope="/ESSENCE"), 1)
        history = other.list_history(1)
        self.assertEqual(len(history), 1)
        self.assertEqual((history[0]["revision"], history[0]["actor"]), (2, "Second reader"))
        exported = other.export()["history"]
        self.assertEqual([record["current_id"] for record in exported], [B, C])
        self.assertEqual(exported[1]["actor"], "Researcher")
        self.workspace.close()
        self.assertEqual([record["revision"] for record in self.reopen().list_history()], [2, 1])

    def test_history_limit_is_bounded_and_not_a_boolean(self):
        for limit in (0, -1, 1001, True, "2", None):
            with self.subTest(limit=limit), self.assertRaises(WorkspaceError):
                self.workspace.list_history(limit)

    def test_bookmark_creation_replacement_and_deletion(self):
        first = self.workspace.set_bookmark("beginning", A)
        self.assertEqual(first["corpus_id"], CORPUS_ID)
        with self.assertRaisesRegex(WorkspaceError, "already exists"):
            self.workspace.set_bookmark("beginning", B)
        self.assertEqual(self.workspace.get_bookmark("beginning")["target_id"], A)
        second = self.workspace.set_bookmark("beginning", B, replace=True)
        self.assertEqual(second["created_at"], first["created_at"])
        self.assertEqual(self.workspace.list_bookmarks(), [second])
        self.assertTrue(self.workspace.delete_bookmark("beginning"))
        self.assertFalse(self.workspace.delete_bookmark("beginning"))
        self.assertIsNone(self.workspace.get_bookmark("beginning"))

    def test_bookmark_duplicate_protection_is_visible_to_other_sessions(self):
        other = self.reopen()
        self.workspace.set_bookmark("same", A)
        with self.assertRaises(WorkspaceError):
            other.set_bookmark("same", B)
        self.assertEqual(other.get_bookmark("same")["target_id"], A)

    def test_sql_like_names_and_unicode_are_values_not_commands(self):
        name = "α'); DROP TABLE annotations; --"
        self.workspace.set_bookmark(name, A)
        self.assertEqual(self.workspace.get_bookmark(name)["target_id"], A)
        self.assertEqual(self.workspace.list_annotations(), [])

    def test_annotation_has_personal_attribution_and_independent_id(self):
        first = self.workspace.add_annotation(A, "A personal thought.\n\tA second line.", CONTENT_SHA.upper())
        self.assertEqual(str(UUID(first["id"])), first["id"])
        self.assertNotEqual(first["id"], A)
        self.assertEqual(first["attribution"], {"role": "personal_note", "author": "Researcher"})
        self.assertEqual(first["content_sha256"], CONTENT_SHA)
        second = self.workspace.add_annotation(B, "Another thought.")
        self.assertEqual(self.workspace.list_annotations(A), [first])
        self.assertEqual(self.workspace.get_annotation(second["id"]), second)
        updated = self.workspace.update_annotation(first["id"], "A corrected personal thought.")
        self.assertEqual(updated["created_at"], first["created_at"])
        self.assertEqual(updated["actor"], first["actor"])
        self.assertEqual(updated["content_sha256"], CONTENT_SHA)
        self.assertTrue(self.workspace.delete_annotation(first["id"]))
        self.assertIsNone(self.workspace.get_annotation(first["id"]))
        with self.assertRaisesRegex(WorkspaceError, "no such annotation"):
            self.workspace.update_annotation(first["id"], "Missing.")

    def test_comparison_retains_order_duplicates_question_and_attribution(self):
        first = self.workspace.save_comparison("contrast", [B, A, B], "Why this order?\nWhat changes?")
        self.assertEqual(first["target_ids"], [B, A, B])
        self.assertEqual(first["actor"], "Researcher")
        self.assertIn("created_at", first)
        with self.assertRaisesRegex(WorkspaceError, "already exists"):
            self.workspace.save_comparison("contrast", [C])
        second = self.workspace.save_comparison("contrast", [C, A], "New question", replace=True)
        self.assertEqual(second["created_at"], first["created_at"])
        self.assertEqual(self.workspace.list_comparisons(), [second])
        self.assertTrue(self.workspace.delete_comparison("contrast"))
        self.assertIsNone(self.workspace.get_comparison("contrast"))
        self.assertEqual(self.workspace._connection.execute(
            "SELECT COUNT(*) FROM comparison_items").fetchone()[0], 0)

    def test_comparison_update_rolls_back_if_child_insert_fails(self):
        original = self.workspace.save_comparison("contrast", [A], "Original question")
        connection = self.workspace._connection
        connection.execute(
            "CREATE TRIGGER fail_comparison BEFORE INSERT ON comparison_items "
            "WHEN NEW.target_id = '" + B + "' "
            "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
        try:
            with self.assertRaisesRegex(WorkspaceError, "synthetic failure"):
                self.workspace.save_comparison("contrast", [C, B], "Changed question", replace=True)
            self.assertEqual(self.workspace.get_comparison("contrast"), original)
        finally:
            connection.execute("DROP TRIGGER fail_comparison")
        self.assertEqual(self.reopen().get_comparison("contrast"), original)

    def test_checkpoint_and_history_roll_back_together(self):
        self.workspace.save_state(state(), None)
        connection = self.workspace._connection
        connection.execute(
            "CREATE TRIGGER fail_history BEFORE INSERT ON state_history "
            "BEGIN SELECT RAISE(ABORT, 'synthetic history failure'); END")
        try:
            with self.assertRaisesRegex(WorkspaceError, "synthetic history failure"):
                self.workspace.save_state(state(B), 1)
            self.assertEqual(self.workspace.get_state()["revision"], 1)
            self.assertEqual(self.workspace.get_state()["current_id"], A)
            self.assertEqual(len(self.workspace.list_history()), 1)
        finally:
            connection.execute("DROP TRIGGER fail_history")

    def test_review_decisions_are_append_only_and_source_bound(self):
        inspected = self.workspace.add_review(A, "inspected", "Check a symbol.", CONTENT_SHA, SOURCE_SHA)
        verified = self.workspace.add_review(A, "verified", "", CONTENT_SHA, SOURCE_SHA)
        self.assertNotEqual(inspected["id"], verified["id"])
        self.assertEqual(self.workspace.list_reviews(A), [inspected, verified])
        self.assertEqual(self.workspace.list_reviews(B), [])
        for sql in ("UPDATE reviews SET outcome='correction_needed'",
                    "DELETE FROM reviews"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.workspace._connection.execute(sql)
        with self.assertRaises(WorkspaceError):
            self.workspace.add_review(A, "approved")
        with self.assertRaisesRegex(WorkspaceError, "fingerprint"):
            self.workspace.add_review(A, "inspected", source_sha256="c" * 64)
        self.assertEqual(len(self.workspace.list_reviews()), 2)

    def test_checkpoint_history_cannot_be_modified_or_deleted(self):
        self.workspace.save_state(state(), None)
        for sql in ("UPDATE state_history SET current_id=NULL", "DELETE FROM state_history"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.workspace._connection.execute(sql)
        self.assertEqual(self.workspace.list_history()[0]["current_id"], A)

    def test_review_append_order_survives_equal_timestamps_and_uuid_sorting(self):
        with patch("sol_workspace._now", return_value="2026-01-01T00:00:00Z"), \
                patch("sol_workspace.uuid4", side_effect=[UUID(C), UUID(A)]):
            first = self.workspace.add_review(A, "inspected")
            second = self.workspace.add_review(A, "correction_needed")
        self.assertEqual(self.workspace.list_reviews(), [first, second])
        self.assertEqual(self.reopen().export()["reviews"], [first, second])

    def test_directed_typed_relations_have_reader_evidence(self):
        forward = self.workspace.add_relation(A, B, "contrasts", "A reader's interpretation.")
        backward = self.workspace.add_relation(B, A, "develops", "")
        self.assertEqual((forward["source_id"], forward["target_id"]), (A, B))
        self.assertEqual(forward["evidence_origin"], "reader")
        self.assertEqual(self.workspace.get_relation(backward["id"]), backward)
        self.assertEqual(self.workspace.list_relations(A), [forward, backward])
        self.assertEqual(self.workspace.list_relations(C), [])
        self.assertTrue(self.workspace.delete_relation(forward["id"]))
        self.assertIsNone(self.workspace.get_relation(forward["id"]))

    def test_control_characters_and_invalid_hashes_are_rejected_before_writes(self):
        operations = [
            lambda: self.workspace.set_bookmark("line\nbreak", A),
            lambda: self.workspace.add_annotation(A, "escape \x1b[31m"),
            lambda: self.workspace.add_annotation(A, "carriage\rreturn"),
            lambda: self.workspace.add_annotation(A, "reverse\u202etext"),
            lambda: self.workspace.save_comparison("x", [A], "\x07"),
            lambda: self.workspace.add_review(A, "inspected", "\x7f"),
            lambda: self.workspace.add_relation(A, B, "kind\tname"),
            lambda: self.workspace.add_relation(A, B, "supports", "\x1b"),
            lambda: self.workspace.add_annotation(A, "note", "short"),
            lambda: self.workspace.add_review(A, "verified", source_sha256=True),
            lambda: self.workspace.set_bookmark("x", "aaaaaaaa"),
            lambda: self.workspace.save_comparison("x", (A, B)),
            lambda: self.workspace.save_comparison("x", []),
            lambda: self.workspace.save_comparison("x", [A, None]),
            lambda: self.workspace.set_bookmark("x", A, replace=1),
        ]
        for number, operation in enumerate(operations):
            with self.subTest(operation=number), self.assertRaises(WorkspaceError):
                operation()
        for key in ("bookmarks", "annotations", "comparisons", "reviews", "relations"):
            self.assertEqual(self.workspace.export()[key], [])

    def test_invalid_actor_and_non_json_provenance_do_not_create_files(self):
        values = [([], "Reader"), ({"value": float("nan")}, "Reader"),
                  ({"value": (1, 2)}, "Reader"), ({1: "key"}, "Reader"),
                  ({"value": object()}, "Reader"), ({}, "bad\nactor")]
        for index, (provenance, actor) in enumerate(values):
            path = self.root / f"invalid-{index}.sqlite3"
            with self.subTest(index=index), self.assertRaises(WorkspaceError):
                Workspace(path, CORPUS_ID, provenance, actor)
            self.assertFalse(path.exists())

    def test_corpus_identity_requires_a_complete_uuid_before_creation(self):
        for index, identity in enumerate(("arbitrary-label", "dddddddd", "", True, None)):
            path = self.root / f"bad-identity-{index}.sqlite3"
            with self.subTest(identity=identity), self.assertRaises(WorkspaceError):
                Workspace(path, identity, PROVENANCE)
            self.assertFalse(path.exists())

    def test_cross_actor_annotation_edits_cannot_falsify_authorship(self):
        original = self.workspace.add_annotation(A, "A personal thought.", CONTENT_SHA)
        other = self.reopen(actor="Another reader")
        with self.assertRaisesRegex(WorkspaceError, "another actor"):
            other.update_annotation(original["id"], "Another person's prose.")
        self.assertEqual(other.get_annotation(original["id"]), original)

    def test_wrong_corpus_and_changed_source_are_refused_without_writes(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(WorkspaceError, "different corpus"):
            Workspace(self.path, OTHER_CORPUS_ID, PROVENANCE)
        self.assertEqual(self.path.read_bytes(), before)
        changed = deepcopy(PROVENANCE)
        changed["source"]["sha256"] = "c" * 64
        with self.assertRaisesRegex(WorkspaceError, "fingerprint"):
            Workspace(self.path, CORPUS_ID, changed)
        self.assertEqual(self.path.read_bytes(), before)

    def test_reindex_metadata_does_not_replace_original_provenance(self):
        changed = deepcopy(PROVENANCE)
        changed["edition"]["review_status"] = "new metadata"
        reopened = self.reopen(provenance=changed)
        self.assertEqual(reopened.export()["provenance"], PROVENANCE)

    def test_unrecognized_database_and_non_database_are_never_initialized(self):
        database = self.root / "unrelated.sqlite3"
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE unrelated(value TEXT)")
            connection.execute("INSERT INTO unrelated VALUES ('keep me')")
        text = self.root / "not-a-database"
        text.write_bytes(b"An unrelated local file.")
        empty = self.root / "empty.sqlite3"
        empty.touch()
        for path in (database, text, empty):
            before = path.read_bytes()
            with self.subTest(path=path), self.assertRaises(WorkspaceError):
                Workspace(path, CORPUS_ID, PROVENANCE)
            self.assertEqual(path.read_bytes(), before)

    def test_unsupported_schema_is_not_migrated(self):
        self.workspace._connection.execute("PRAGMA user_version = 999")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(WorkspaceError, "no migration"):
            self.reopen()
        self.assertEqual(self.path.read_bytes(), before)

    def test_damaged_tables_or_missing_append_only_protection_are_rejected(self):
        self.workspace._connection.execute("DROP TRIGGER history_no_delete")
        with self.assertRaisesRegex(WorkspaceError, "protections"):
            self.reopen()
        self.workspace._connection.execute("DROP TABLE annotations")
        with self.assertRaisesRegex(WorkspaceError, "schema"):
            self.reopen()

    def test_same_named_no_op_trigger_is_rejected_without_writes(self):
        connection = self.workspace._connection
        connection.execute("DROP TRIGGER reviews_no_update")
        connection.execute(
            "CREATE TRIGGER reviews_no_update BEFORE UPDATE ON reviews BEGIN SELECT 1; END")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(WorkspaceError, "definitions"):
            self.reopen()
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_foreign_key_definition_is_rejected_without_writes(self):
        connection = self.workspace._connection
        connection.execute("DROP TABLE bookmarks")
        connection.execute(
            "CREATE TABLE bookmarks (name TEXT PRIMARY KEY, target_id TEXT NOT NULL, "
            "actor TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "workspace_id INTEGER NOT NULL DEFAULT 1)")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(WorkspaceError, "definitions"):
            self.reopen()
        self.assertEqual(self.path.read_bytes(), before)

    def test_unrecognized_views_and_explicit_indexes_are_rejected_without_writes(self):
        connection = self.workspace._connection
        for sql, removal in (
                ("CREATE VIEW unexpected AS SELECT * FROM bookmarks", "DROP VIEW unexpected"),
                ("CREATE INDEX unexpected ON bookmarks(actor)", "DROP INDEX unexpected")):
            connection.execute(sql)
            before = self.path.read_bytes()
            with self.subTest(sql=sql), self.assertRaisesRegex(WorkspaceError, "schema objects"):
                self.reopen()
            self.assertEqual(self.path.read_bytes(), before)
            connection.execute(removal)

    def test_damaged_persisted_values_are_rejected_on_reopen(self):
        self.workspace._connection.execute(
            "INSERT INTO bookmarks(name,target_id,actor,created_at,updated_at) "
            "VALUES('bad','not-a-uuid','Reader','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
        with self.assertRaisesRegex(WorkspaceError, "UUID"):
            self.reopen()

    def test_export_is_portable_independent_and_contains_no_canonical_text(self):
        self.workspace.save_state(state(), None)
        self.workspace.set_bookmark("start", A)
        self.workspace.add_annotation(A, "My personal note.", CONTENT_SHA)
        self.workspace.save_comparison("question", [A, B], "How do these compare?")
        self.workspace.add_review(A, "correction_needed", "Inspect the original.", CONTENT_SHA, SOURCE_SHA)
        self.workspace.add_relation(A, B, "contrasts", "My interpretation.")
        exported = self.workspace.export()
        self.assertEqual(exported["format"], "sol-workspace")
        self.assertEqual(exported["schema_version"], SCHEMA_VERSION)
        self.assertEqual(exported["corpus_id"], CORPUS_ID)
        encoded = json.dumps(exported, ensure_ascii=False, allow_nan=False)
        self.assertNotIn('"markdown"', encoded)
        self.assertNotIn('"plain_text"', encoded)
        self.assertEqual(json.loads(encoded), exported)
        exported["provenance"]["edition"]["title"] = "Mutated export"
        self.assertEqual(self.workspace.export()["provenance"], PROVENANCE)
        self.workspace.close()
        reopened = self.reopen().export()
        for key in ("state", "history", "bookmarks", "annotations", "comparisons", "reviews", "relations"):
            self.assertEqual(reopened[key], exported[key])

    def test_workspace_does_not_read_or_change_corpus_files(self):
        with patch("sol_workspace.Path.read_text", side_effect=AssertionError("No corpus reads")), \
                patch("sol_workspace.Path.read_bytes", side_effect=AssertionError("No corpus reads")):
            self.workspace.set_bookmark("start", A)
            self.workspace.add_annotation(A, "An independent personal note.")
            self.workspace.save_state(state(), None)
            self.assertEqual(self.workspace.export()["state"]["current_id"], A)


if __name__ == "__main__":
    unittest.main()
