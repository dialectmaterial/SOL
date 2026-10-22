"""Durable semantic positions use invented text and isolated workspaces only."""
from __future__ import annotations

from contextlib import closing
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import sol.reader.app as sol
from sol.being.workspace.catalog import discover_workspaces
from sol.being.workspace.reader import WorkspaceReader
from sol.being.workspace.store import (APPLICATION_ID, Workspace, WorkspaceConflict, WorkspaceError,
                                 _SCHEMA, _ANNOTATION_SCHEMA)
from test_workspace_reader import CORPUS_ID, IDS, invented_book


def make_legacy(path, provenance, version=2):
    with closing(sqlite3.connect(path)) as connection, connection:
        for statement in _SCHEMA + (_ANNOTATION_SCHEMA if version == 2 else ()):
            connection.execute(statement)
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {version}")
        connection.execute("INSERT INTO workspace_metadata VALUES(1,?,?,?,?)",
                           (version, CORPUS_ID, json.dumps(provenance), "2020-01-01T00:00:00Z"))


class ReaderPositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-reader-position-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "reading.sqlite3"
        self.book = invented_book()
        self.provenance = {key: self.book.corpus_manifest[key] for key in ("edition", "source")}
        self.store = self.open(self.path)
        self.session = sol.ReadingSession(self.book)
        self.session.read((), first=True)
        self.session.cursor_offset, self.session.viewport_offset = 0, None
        self.reader = self.adapter(self.store)

    def open(self, path, **options):
        store = Workspace(path, CORPUS_ID, self.provenance, actor="Ada", **options)
        self.addCleanup(store.close)
        return store

    def adapter(self, store):
        return WorkspaceReader(self.book, store, "Ada", sol.resolve_path,
                               sol.display_path, sol.render_passage)

    def saved(self, offset=17, viewport=8):
        self.session.cursor_offset, self.session.viewport_offset = offset, viewport
        self.reader.checkpoint(self.session, (), None)
        return self.store.get_state()

    def restore(self, store=None):
        session = sol.ReadingSession(self.book)
        reader = self.adapter(store or self.store)
        message = reader.restore(session)[3]
        return session, reader, message

    def test_cursor_and_semantic_viewport_roundtrip_same_revision_and_history(self):
        saved = self.saved()
        self.assertEqual(saved["position"]["cursor_offset"], 17)
        self.assertEqual(saved["position"]["viewport_offset"], 8)
        self.assertEqual(saved["position"], self.store.get_history(1)["position"])
        source_bytes = self.path.read_bytes()
        session, _, message = self.restore(self.open(self.path))
        self.assertEqual((session.cursor_offset, session.viewport_offset), (17, 8))
        self.assertEqual(message, "")
        self.assertEqual(source_bytes, self.path.read_bytes())
        self.assertEqual(self.store.get_state()["revision"], 1)

    def test_position_uses_unicode_codepoints_not_encoded_bytes_or_wrapped_rows(self):
        text = "α e\u0301 😀 word."
        self.book.passages[0] = replace(self.book.passages[0], text=text)
        record = self.book.canonical_records[IDS[0]]
        record.update(markdown=text, plain_text=text,
                      content_sha256=hashlib.sha256(text.encode()).hexdigest())
        saved = self.saved(offset=5, viewport=2)
        self.assertEqual(saved["position"]["plain_text_length"], len(text))
        self.assertNotEqual(len(text), len(text.encode()))
        session, _, _ = self.restore()
        self.assertEqual(session.cursor_offset, 5)
        self.assertEqual(session.current().text[session.cursor_offset], "😀")

    def test_dirty_position_writes_once_and_noop_does_not_create_visit(self):
        self.saved()
        self.reader.save_position(self.session, (), None)
        self.assertEqual(self.store.get_state()["revision"], 1)
        self.session.cursor_offset = 18
        self.reader.save_position(self.session, (), None)
        self.assertEqual(self.store.get_state()["revision"], 2)
        self.reader.save_position(self.session, (), None)
        self.assertEqual(self.store.get_state()["revision"], 2)

    def test_cas_conflict_preserves_other_session_and_local_offset(self):
        self.saved()
        other = self.open(self.path)
        other.save_state(other.get_state(), expected_revision=1)
        self.session.cursor_offset = 19
        with self.assertRaises(WorkspaceConflict):
            self.reader.save_position(self.session, (), None)
        self.assertEqual(self.store.get_state()["revision"], 2)
        self.assertEqual(self.store.get_state()["position"]["cursor_offset"], 17)
        self.assertEqual(self.session.cursor_offset, 19)
        self.assertEqual(self.reader.revision, 1)

    def test_noop_does_not_override_concurrent_session(self):
        self.saved()
        other = self.open(self.path)
        state = other.get_state()
        state["position"]["cursor_offset"] = 25
        other.save_state(state, expected_revision=1)
        self.reader.save_position(self.session, (), None)
        self.assertEqual(self.store.get_state()["position"]["cursor_offset"], 25)

    def test_source_generation_change_refuses_dirty_position_write(self):
        before = self.saved()
        self.session.cursor_offset = 18
        with patch.object(self.reader, "ensure_corpus_current", side_effect=WorkspaceError("changed on disk")):
            with self.assertRaisesRegex(WorkspaceError, "changed on disk"):
                self.reader.save_position(self.session, (), None)
        self.assertEqual(self.store.get_state(), before)

    def test_markdown_or_plain_text_change_invalidates_old_offset_without_write(self):
        self.saved()
        self.book.canonical_records[IDS[0]]["content_sha256"] = "a" * 64
        before = self.path.read_bytes()
        session, _, message = self.restore()
        self.assertEqual((session.cursor_offset, session.viewport_offset), (0, None))
        self.assertIn("binding changed", message)
        self.assertEqual(before, self.path.read_bytes())

    def test_plain_text_projection_change_invalidates_even_if_markdown_hash_unchanged(self):
        self.saved()
        self.book.passages[0] = replace(self.book.passages[0], text="A shorter changed projection.")
        session, _, message = self.restore()
        self.assertEqual((session.cursor_offset, session.viewport_offset), (0, None))
        self.assertIn("binding changed", message)

    def test_missing_saved_id_is_not_replaced_by_nearest_text(self):
        self.saved()
        del self.book.canonical_records[IDS[0]]
        before = self.store.get_state()
        with self.assertRaisesRegex(ValueError, "unresolved"):
            self.restore()
        self.assertEqual(self.store.get_state(), before)

    def test_retirement_changes_target_resets_offset_and_preserves_requested_id(self):
        self.saved()
        self.book.canonical_records[IDS[0]] = {
            "id": IDS[0], "type": "retired_record", "redirect_id": IDS[1]}
        self.book.redirects[IDS[0]] = IDS[1]
        self.book.passages.pop(0)
        session, reader, message = self.restore()
        self.assertEqual(session.current().identifier, IDS[1])
        self.assertEqual(session.cursor_offset, 0)
        self.assertIn("binding changed", message)
        reader.checkpoint(session, (), None)
        saved = self.store.get_state()
        self.assertEqual(saved["current_id"], IDS[0])
        self.assertEqual(saved["position"]["target_id"], IDS[1])

    def test_readonly_restore_is_safe_and_dirty_save_refuses(self):
        self.saved()
        readonly = self.open(self.path, read_only=True)
        session, reader, _ = self.restore(readonly)
        self.assertEqual(session.cursor_offset, 17)
        session.cursor_offset = 19
        with self.assertRaisesRegex(WorkspaceError, "read-only"):
            reader.save_position(session, (), None)
        self.assertEqual(self.store.get_state()["revision"], 1)

    def test_historical_restore_retains_position_as_new_visit(self):
        self.saved(offset=12, viewport=4)
        self.session.cursor_offset = 24
        self.reader.save_position(self.session, (), None)
        session = sol.ReadingSession(self.book)
        reader = self.adapter(self.store)
        message = reader.restore(session, historical_revision=1)[3]
        self.assertIn("new revision 3", message)
        self.assertEqual((session.cursor_offset, session.viewport_offset), (12, 4))
        self.assertEqual(self.store.get_state()["position"]["cursor_offset"], 12)

    def test_stale_historical_position_is_not_copied_to_new_visit(self):
        self.saved()
        self.book.canonical_records[IDS[0]]["content_sha256"] = "f" * 64
        session = sol.ReadingSession(self.book)
        reader = self.adapter(self.store)
        reader.restore(session, historical_revision=1)
        self.assertNotIn("position", self.store.get_state())
        self.assertEqual(session.cursor_offset, 0)
        self.assertEqual(self.store.get_history(1)["position"]["cursor_offset"], 17)

    def test_malformed_positions_fail_before_checkpoint_and_preserve_history(self):
        saved = self.saved()
        position = saved["position"]
        invalid = [None, [], {**position, "extra": 0}, {**position, "target_id": "wrong"},
                   {**position, "content_sha256": None}, {**position, "plain_text_sha256": "bad"},
                   {**position, "plain_text_length": True}, {**position, "cursor_offset": True},
                   {**position, "cursor_offset": -1}, {**position, "viewport_offset": -1},
                   {**position, "cursor_offset": position["plain_text_length"] + 1},
                   {**position, "viewport_offset": float("nan")},
                   {**position, "plain_text_length": 2 ** 100}]
        # null deliberately means no semantic position; it is not malformed.
        for value in invalid[1:]:
            with self.subTest(value=value), self.assertRaises(WorkspaceError):
                self.store.save_state({**saved, "position": value}, expected_revision=1)
            self.assertEqual(self.store.get_state(), saved)
            self.assertEqual(len(self.store.list_history()), 1)

    def test_position_audit_entries_are_append_only(self):
        self.saved()
        for statement in ("UPDATE reading_positions SET cursor_offset=19", "DELETE FROM reading_positions"):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                self.store._db().execute(statement)
        self.assertEqual(self.store.get_state()["position"]["cursor_offset"], 17)

    def test_corrupt_position_row_is_rejected_when_reopening(self):
        self.saved()
        self.store.close()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DROP TRIGGER reading_positions_no_update")
            connection.execute("UPDATE reading_positions SET content_sha256='bad'")
            # Restore the exact protection: this tests values, not missing schema.
            from sol.being.workspace.store import _POSITION_SCHEMA
            connection.execute(_POSITION_SCHEMA[1])
        with self.assertRaisesRegex(WorkspaceError, "digest"):
            self.open(self.path)

    def test_legacy_v1_v2_reopen_unchanged_and_upgrade_creates_separate_v3_copy(self):
        for version in (1, 2):
            with self.subTest(version=version):
                path = self.root / f"legacy{version}.sqlite3"
                make_legacy(path, self.provenance, version)
                legacy = self.open(path)
                legacy.save_state({"cwd": "/", "scope": "/", "current_id": IDS[0], "previous_cwd": None})
                if version == 2:
                    note = legacy.add_annotation(IDS[0], "Personal thought.", "a" * 64)
                    legacy.update_annotation(note["id"], "Revised thought.", expected_revision=1)
                before = legacy.export()
                original_bytes = path.read_bytes()
                legacy_session, adapter, message = self.restore(legacy)
                self.assertIn("version-3 copy", message)
                self.assertEqual(legacy_session.cursor_offset, 0)
                legacy_session.cursor_offset = 17
                self.assertIn("not saved", adapter.save_position(legacy_session, (), None))
                self.assertEqual(original_bytes, path.read_bytes())
                upgraded_path = legacy.upgrade_copy(self.root / f"upgraded{version}.sqlite3")
                upgraded = self.open(upgraded_path)
                self.assertEqual(upgraded.schema_version, 3)
                self.assertEqual(original_bytes, path.read_bytes())
                for field in ("state", "history", "bookmarks", "reviews", "comparisons", "relations"):
                    self.assertEqual(upgraded.export()[field], before[field])
                if version == 2:
                    self.assertEqual(upgraded.export()["annotation_history"], before["annotation_history"])
                self.assertNotIn("position", upgraded.get_state())
                upgraded_reader = self.adapter(upgraded)
                upgraded_reader.restore(legacy_session)
                legacy_session.cursor_offset = 17
                upgraded_reader.save_position(legacy_session, (), None)
                self.assertEqual(upgraded.get_state()["position"]["cursor_offset"], 17)
                self.assertEqual(original_bytes, path.read_bytes())
                names = {row["name"]: row for row in discover_workspaces(CORPUS_ID, "0" * 64, self.root)}
                self.assertEqual(names[path.stem]["schema_version"], version)
                self.assertEqual(names[upgraded_path.stem]["schema_version"], 3)

    def test_legacy_store_refuses_position_payload_without_auto_migration(self):
        position = self.saved()["position"]
        path = self.root / "older.sqlite3"
        make_legacy(path, self.provenance)
        legacy = self.open(path)
        before = path.read_bytes()
        with self.assertRaisesRegex(WorkspaceError, "version 3"):
            legacy.save_state({"cwd": "/", "scope": "/", "current_id": IDS[0], "previous_cwd": None,
                               "position": position})
        self.assertEqual(before, path.read_bytes())

    def test_inconsistent_canonical_fingerprint_cannot_be_saved(self):
        before = self.saved()
        self.book.canonical_records[IDS[0]]["content_sha256"] = "f" * 64
        self.session.cursor_offset = 18
        with self.assertRaisesRegex(WorkspaceError, "fingerprint is inconsistent"):
            self.reader.save_position(self.session, (), None)
        self.assertEqual(self.store.get_state(), before)


if __name__ == "__main__":
    unittest.main()
