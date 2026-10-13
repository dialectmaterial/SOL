"""Workspace suggestions inspect invented databases without creating anything."""
from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from sol.workspace.store import APPLICATION_ID, Workspace, WorkspaceError, _ANNOTATION_SCHEMA, _SCHEMA
from sol.workspace.catalog import discover_workspaces


CORPUS = "dddddddd-0000-4000-8000-000000000004"
OTHER_CORPUS = "eeeeeeee-0000-4000-8000-000000000005"
PASSAGE = "aaaaaaaa-0000-4000-8000-000000000001"
SOURCE = "b" * 64
CREATED = "2025-01-01T00:00:00Z"


@contextmanager
def database(path):
    with closing(sqlite3.connect(path)) as connection:
        with connection:
            yield connection


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-catalog-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / "workspaces"
        self.directory.mkdir()

    def v1(self, name="reading", *, corpus=CORPUS, source=SOURCE, created=CREATED):
        """Build the exact frozen version-one format without a migration."""
        path = self.directory / (name + ".sqlite3")
        with database(path) as connection:
            for statement in _SCHEMA:
                connection.execute(statement)
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute("PRAGMA user_version=1")
            provenance = json.dumps({"source": {"sha256": source}})
            connection.execute("INSERT INTO workspace_metadata VALUES(1,1,?,?,?)",
                               (corpus, provenance, created))
        return path

    def checkpoint(self, path, *, timestamp=CREATED, actor="Reader", scope="/BEING"):
        with database(path) as connection:
            connection.execute("INSERT INTO reading_state VALUES(1,?,?,?,NULL,1)",
                               (scope, scope, PASSAGE))
            connection.execute("INSERT INTO state_history VALUES(1,?,?,?,NULL,?,?,1)",
                               (scope, scope, PASSAGE, actor, timestamp))

    def discover(self, **options):
        return discover_workspaces(CORPUS, SOURCE, self.directory, **options)

    def fingerprints(self):
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.directory.iterdir() if path.is_file()}

    def test_missing_directory_is_empty_and_not_created(self):
        missing = self.root / "not-created" / "workspaces"
        self.assertEqual(discover_workspaces(CORPUS, SOURCE, missing), [])
        self.assertFalse(missing.parent.exists())

    def test_default_directory_is_xdg_local_without_reading_actor_registry(self):
        target = self.root / "sol" / "workspaces"
        target.parent.mkdir()
        self.directory.rename(target)
        self.directory = target
        self.v1()
        registry = target.parent / "profiles.sqlite3"
        registry.write_bytes(b"not-an-actor-registry")
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root)}):
            found = discover_workspaces(CORPUS, SOURCE)
        self.assertEqual([row["name"] for row in found], ["reading"])
        self.assertEqual(registry.read_bytes(), b"not-an-actor-registry")

    def test_v1_empty_workspace_has_truthful_null_context_and_no_writes(self):
        path = self.v1()
        before = self.fingerprints()
        self.assertEqual(self.discover(), [{
            "name": "reading", "schema_version": 1,
            "last_activity": "2025-01-01T00:00:00Z",
            "current_id": None, "scope": None, "last_actor": None,
        }])
        self.assertEqual(self.fingerprints(), before)
        with database(path) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_v2_workspace_is_recognized_without_mutation(self):
        path = self.directory / "modern.sqlite3"
        with patch("sol.workspace.store._now", return_value=CREATED):
            with Workspace(path, CORPUS, {"source_sha256": SOURCE}, actor="Dima") as workspace:
                workspace.save_state({"cwd": "/BEING", "scope": "/BEING", "current_id": PASSAGE}, None)
                workspace.add_annotation(PASSAGE, "Invented note")
        before = self.fingerprints()
        found = self.discover()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["schema_version"], 2)
        self.assertEqual(found[0]["current_id"], PASSAGE)
        self.assertEqual(found[0]["scope"], "/BEING")
        self.assertEqual(found[0]["last_actor"], "Dima")
        self.assertEqual(self.fingerprints(), before)

    def test_identity_and_source_must_both_match(self):
        self.v1("good")
        self.v1("other-corpus", corpus=OTHER_CORPUS)
        self.v1("other-source", source="c" * 64)
        self.v1("missing-source", source=None)
        before = self.fingerprints()
        self.assertEqual([row["name"] for row in self.discover()], ["good"])
        self.assertEqual(self.fingerprints(), before)

    def test_null_source_is_an_exact_identity_not_a_wildcard(self):
        self.v1("unspecified", source=None)
        self.v1("fingerprinted")
        found = discover_workspaces(CORPUS, None, self.directory)
        self.assertEqual([row["name"] for row in found], ["unspecified"])

    def test_actual_saved_activity_not_file_mtime_controls_recent_order(self):
        old = self.v1("old")
        newer = self.v1("newer")
        self.checkpoint(old, timestamp="2025-02-01T00:00:00Z")
        self.checkpoint(newer, timestamp="2025-03-01T00:00:00Z", actor="Later reader")
        os.utime(old, (2_000_000_000, 2_000_000_000))
        os.utime(newer, (1, 1))
        before = self.fingerprints()
        found = self.discover()
        self.assertEqual([row["name"] for row in found], ["newer", "old"])
        self.assertEqual(found[0]["last_activity"], "2025-03-01T00:00:00Z")
        self.assertEqual(found[0]["last_actor"], "Later reader")
        self.assertEqual(self.fingerprints(), before)

    def test_latest_saved_annotation_or_bookmark_counts_as_activity(self):
        path = self.v1()
        self.checkpoint(path, timestamp="2025-02-01T00:00:00Z")
        with database(path) as connection:
            connection.execute("INSERT INTO bookmarks VALUES(?,?,?,?,?,1)",
                               ("start", PASSAGE, "Annotator", CREATED, "2025-04-01T00:00:00Z"))
        found = self.discover()[0]
        self.assertEqual(found["last_activity"], "2025-04-01T00:00:00Z")
        self.assertEqual(found["last_actor"], "Annotator")
        self.assertEqual(found["current_id"], PASSAGE)

    def test_v2_note_revisions_are_recognized_saved_activity(self):
        path = self.directory / "notes.sqlite3"
        with patch("sol.workspace.store._now", return_value=CREATED):
            with Workspace(path, CORPUS, {"source_sha256": SOURCE}, actor="Dima") as workspace:
                note = workspace.add_annotation(PASSAGE, "First interpretation")
                with patch("sol.workspace.store._now", return_value="2025-06-01T00:00:00Z"):
                    workspace.update_annotation(note["id"], "Second interpretation", expected_revision=1)
        before = self.fingerprints()
        found = self.discover()[0]
        self.assertEqual(found["last_activity"], "2025-06-01T00:00:00Z")
        self.assertEqual(found["last_actor"], "Dima")
        self.assertEqual(self.fingerprints(), before)

    def test_legacy_copy_upgrade_date_does_not_invent_an_editor(self):
        path = self.v1("legacy")
        with Workspace(path, CORPUS, {"source_sha256": SOURCE}, actor="Original author") as workspace:
            with patch("sol.workspace.store._now", return_value=CREATED):
                workspace.add_annotation(PASSAGE, "A retained legacy note")
            with patch("sol.workspace.store._now", return_value="2025-06-01T00:00:00Z"):
                workspace.upgrade_copy(self.directory / "upgraded.sqlite3")
        before = self.fingerprints()
        found = self.discover()[0]
        self.assertEqual(found["name"], "upgraded")
        self.assertEqual(found["schema_version"], 2)
        self.assertEqual(found["last_activity"], "2025-06-01T00:00:00Z")
        self.assertIsNone(found["last_actor"])
        self.assertEqual(self.fingerprints(), before)

    def test_compatibility_is_revalidated_in_the_snapshot_being_displayed(self):
        path = self.v1()

        def identity_changed_after_open(*arguments, **options):
            workspace = Workspace(*arguments, **options)
            with database(path) as connection:
                connection.execute("UPDATE workspace_metadata SET corpus_id=?", (OTHER_CORPUS,))
            return workspace

        with patch("sol.workspace.catalog.Workspace", side_effect=identity_changed_after_open):
            self.assertEqual(self.discover(), [])

    def test_v2_damaged_audit_metadata_is_not_used_as_activity(self):
        path = self.directory / "damaged-history.sqlite3"
        with patch("sol.workspace.store._now", return_value=CREATED):
            with Workspace(path, CORPUS, {"source_sha256": SOURCE}, actor="Dima") as workspace:
                workspace.add_annotation(PASSAGE, "An invented note")
        with database(path) as connection:
            connection.execute("DROP TRIGGER annotation_history_no_update")
            connection.execute("UPDATE annotation_history SET recorded_at='not-a-date'")
            connection.execute(_ANNOTATION_SCHEMA[1])
        before = self.fingerprints()
        self.assertEqual(self.discover(), [])
        self.assertEqual(self.fingerprints(), before)

    def test_dates_sort_by_utc_instant_not_iso_text_and_ties_by_name(self):
        alpha = self.v1("alpha", created="2025-01-01T00:00:00Z")
        beta = self.v1("beta", created="2025-01-01T00:00:00.1+00:00")
        gamma = self.v1("gamma", created="2025-01-01T00:00:00.100000Z")
        self.assertEqual([row["name"] for row in self.discover()], ["beta", "gamma", "alpha"])
        self.assertEqual(self.discover()[0]["last_activity"], "2025-01-01T00:00:00.100000Z")
        self.assertTrue(all(path.exists() for path in (alpha, beta, gamma)))

    def test_limit_is_bounded_and_boolean_is_not_an_integer_limit(self):
        self.v1("alpha")
        self.v1("beta")
        self.assertEqual(len(self.discover(limit=1)), 1)
        for limit in (0, -1, 21, True, None, "10", 1.0):
            with self.subTest(limit=limit), self.assertRaises(WorkspaceError):
                self.discover(limit=limit)

    def test_invalid_caller_identity_and_relative_xdg_are_actionable(self):
        for corpus, source in (("not-a-uuid", SOURCE), (CORPUS, "not-a-sha")):
            with self.subTest(corpus=corpus, source=source), self.assertRaises(WorkspaceError):
                discover_workspaces(corpus, source, self.directory)
        with patch.dict(os.environ, {"XDG_DATA_HOME": "relative"}):
            with self.assertRaisesRegex(WorkspaceError, "absolute"):
                discover_workspaces(CORPUS, SOURCE)

    def test_symlinks_nonregular_files_bad_names_and_non_databases_are_ignored(self):
        good = self.v1("good")
        good.with_name("alias.sqlite3").symlink_to(good)
        self.v1("unsafe name")
        self.v1("_starts-with-underscore")
        self.v1("a" * 65)
        (self.directory / "folder.sqlite3").mkdir()
        (self.directory / "corrupt.sqlite3").write_bytes(b"Not SQLite")
        (self.directory / "ignored.db").write_bytes(b"Not SQLite")
        if hasattr(os, "mkfifo"):
            os.mkfifo(self.directory / "pipe.sqlite3")
        before = self.fingerprints()
        self.assertEqual([row["name"] for row in self.discover()], ["good"])
        self.assertEqual(self.fingerprints(), before)

    def test_symlink_catalog_directory_is_not_followed(self):
        self.v1()
        link = self.root / "linked-directory"
        link.symlink_to(self.directory, target_is_directory=True)
        self.assertEqual(discover_workspaces(CORPUS, SOURCE, link), [])

    def test_unsupported_versions_and_unrecognized_schema_are_not_reinterpreted(self):
        future = self.v1("future")
        extra = self.v1("extra")
        broken = self.v1("broken")
        with database(future) as connection:
            connection.execute("PRAGMA user_version=99")
            connection.execute("UPDATE workspace_metadata SET schema_version=99")
        with database(extra) as connection:
            connection.execute("CREATE TABLE private_extra(value TEXT)")
        with database(broken) as connection:
            connection.execute("DROP TRIGGER history_no_delete")
        self.v1("good")
        before = self.fingerprints()
        self.assertEqual([row["name"] for row in self.discover()], ["good"])
        self.assertEqual(self.fingerprints(), before)

    def test_unsafe_display_metadata_bad_timestamps_and_uuid_are_omitted(self):
        actors = self.v1("actor")
        times = self.v1("time")
        passage = self.v1("passage")
        self.checkpoint(actors, actor="Reader\x1b[31m")
        self.checkpoint(times, timestamp="2025-02-01T00:00:00+01:00")
        self.checkpoint(passage)
        with database(passage) as connection:
            connection.execute("DROP TRIGGER history_no_update")
            connection.execute("UPDATE reading_state SET current_id='bad-uuid'")
            connection.execute("UPDATE state_history SET current_id='bad-uuid'")
            connection.execute(_SCHEMA[-2])
        self.v1("good")
        before = self.fingerprints()
        self.assertEqual([row["name"] for row in self.discover()], ["good"])
        self.assertEqual(self.fingerprints(), before)

    def test_conflicting_source_provenance_and_state_history_disagreement_are_omitted(self):
        conflict = self.v1("conflict")
        disagreement = self.v1("disagreement")
        with database(conflict) as connection:
            connection.execute("UPDATE workspace_metadata SET provenance=?", (json.dumps({
                "source_sha256": SOURCE, "source": {"sha256": "c" * 64}}),))
        self.checkpoint(disagreement)
        with database(disagreement) as connection:
            connection.execute("UPDATE reading_state SET scope='/ESSENCE'")
        self.assertEqual(self.discover(), [])

    def test_wal_database_and_sidecar_candidates_are_omitted_without_new_files(self):
        wal = self.v1("wal")
        with database(wal) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        sidecar = self.v1("sidecar")
        Path(str(sidecar) + "-wal").write_bytes(b"do-not-touch")
        good = self.v1("good")
        before = self.fingerprints()
        before_names = {path.name for path in self.directory.iterdir()}
        self.assertEqual([row["name"] for row in self.discover()], ["good"])
        self.assertEqual(self.fingerprints(), before)
        self.assertEqual({path.name for path in self.directory.iterdir()}, before_names)

    def test_unavailable_directory_returns_no_suggestions(self):
        with patch.object(Path, "iterdir", side_effect=PermissionError("blocked")):
            self.assertEqual(self.discover(), [])


if __name__ == "__main__":
    unittest.main()
