"""Pinned comparison snapshots over an invented corpus and disposable workspace."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from sol.corpus.contract import load_snapshot, render_record
from sol.workspace.comparison import ComparisonError, capture_comparison
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace, WorkspaceError


ROOT = "aaaaaaaa-0000-4000-8000-000000000001"
FIRST = "bbbbbbbb-0000-4000-8000-000000000002"
EDITORIAL = "cccccccc-0000-4000-8000-000000000003"
RETIRED = "dddddddd-0000-4000-8000-000000000004"
OTHER = "eeeeeeee-0000-4000-8000-000000000005"
MISSING = "ffffffff-0000-4000-8000-000000000006"
CORPUS = "aaaaaaaa-0000-4000-8000-000000000007"
SOURCE = "0123456789abcdef" * 4


def stable_export(store):
    exported = store.export()
    exported.pop("exported_at")
    return exported


class ComparisonCaptureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-comparison-capture-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.corpus = self.directory / "corpus"
        self.corpus.mkdir()
        self.records = []
        bodies = [
            (ROOT, "section", "# Invented corpus", 1),
            (FIRST, "paragraph", "A *synthetic* argument preserves α and its complete final sentence.", 2),
            (EDITORIAL, "note", "An editorial *note* has a distinct author.\n\nIts full second paragraph stays visible.", 3),
            (RETIRED, "retired_record", "Editorial history redirects an older permanent reference.", 4),
            (OTHER, "paragraph", "UNRELATED CANONICAL BODY MUST NOT ENTER THE COMPARISON", 2),
        ]
        for order, (identifier, kind, body, page) in enumerate(bodies):
            metadata = {"id": identifier, "parent_id": None if identifier == ROOT else ROOT,
                        "type": kind, "order": order,
                        "title": "Editorial note" if identifier == EDITORIAL else "Invented argument",
                        "path": "/editorial" if identifier == EDITORIAL else "/invented",
                        "sources": [{"pdf_page": page, "printed_page": "i" if page == 1 else str(page - 1)}],
                        "attribution": {"author": "Synthetic editor" if identifier == EDITORIAL else "Synthetic philosopher",
                                        "role": "editorial_note" if identifier == EDITORIAL else "main_text",
                                        "status": "confirmed"}}
            if identifier == FIRST:
                metadata["sources"] = [{"pdf_page": 2, "printed_page": "1", "bbox": [1, 2, 30, 40]},
                                       {"pdf_page": 4, "printed_page": "3"}]
                metadata["transcription_status"] = "needs_visual_review"
            if identifier == RETIRED:
                metadata["redirect_id"] = FIRST
            self.records.append({**metadata, "markdown": body, "plain_text": body.replace("*", "").lstrip("# "),
                                 "document": "invented.md", "context": [],
                                 "content_sha256": hashlib.sha256(body.encode()).hexdigest()})
        self.write_generation()
        snapshot = load_snapshot(self.corpus)
        self.book = SimpleNamespace(corpus_directory=self.corpus, corpus_snapshot=snapshot,
                                    corpus_manifest=snapshot.manifest,
                                    canonical_records={r["id"]: r for r in snapshot.records})
        provenance = {key: self.book.corpus_manifest[key] for key in ("edition", "source")}
        self.store = Workspace(self.directory / "inquiry.sqlite3", CORPUS, provenance, actor="Ada")
        self.addCleanup(self.store.close)
        digest = self.book.canonical_records[FIRST]["content_sha256"]
        self.matching = self.store.add_annotation(FIRST, "My *personal* note α, with a full final sentence.", digest)
        self.stale = self.store.add_annotation(FIRST, "Earlier text binding stays visibly stale.", "f" * 64)
        self.legacy = self.store.add_annotation(FIRST, "Legacy unbound personal note.", None)
        self.retired = self.store.add_annotation(RETIRED, "A note on the original retired UUID.", digest)
        self.unresolved = self.store.add_annotation(MISSING, "A note on an unresolved canonical reference.", "e" * 64)
        self.store.add_annotation(OTHER, "UNRELATED PERSONAL NOTE MUST NOT ENTER THE COMPARISON", digest)
        self.targets = [EDITORIAL, RETIRED, FIRST, FIRST, MISSING]
        self.store.save_comparison("inquiry", self.targets, "How do these invented determinations differ?")
        self.store.save_state({"cwd": "/", "scope": "/invented", "current_id": FIRST, "previous_cwd": None})
        self.reader = WorkspaceReader(self.book, self.store, None, None, None, None)

    def write_generation(self):
        manifest = {"contract_version": 1, "corpus_id": CORPUS, "edition": {"title": "Synthetic edition"},
                    "source": {"filename": "invented.pdf", "sha256": SOURCE, "pdf_pages": 4},
                    "documents": ["invented.md"],
                    "page_inventory": [{"pdf_page": page, "printed_page": "i" if page == 1 else str(page - 1),
                                        "disposition": "records"} for page in range(1, 5)]}
        document = "\n".join(render_record({k: v for k, v in r.items()
                                           if k not in {"markdown", "plain_text", "document", "context", "content_sha256"}},
                                          r["markdown"]) for r in self.records)
        manifest_bytes = json.dumps(manifest).encode()
        index_bytes = "".join(json.dumps(record) + "\n" for record in self.records).encode()
        (self.corpus / "invented.md").write_text(document)
        (self.corpus / "corpus.json").write_bytes(manifest_bytes)
        (self.corpus / "index.jsonl").write_bytes(index_bytes)
        metadata = {"contract_version": 1, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                    "source_sha256": SOURCE, "documents": {"invented.md": hashlib.sha256(document.encode()).hexdigest()},
                    "index_sha256": hashlib.sha256(index_bytes).hexdigest(), "record_count": len(self.records)}
        (self.corpus / "index.meta.json").write_text(json.dumps(metadata))

    def capture(self):
        return capture_comparison(self.reader, "inquiry")

    def test_order_duplicates_editorial_and_unresolved_cards_are_preserved(self):
        snapshot = self.capture()
        cards = snapshot["records"]
        self.assertEqual([card["requested_id"] for card in cards], self.targets)
        self.assertEqual([card["position"] for card in cards], list(range(5)))
        self.assertEqual(cards[0]["type"], "note")
        self.assertEqual(cards[0]["attribution"]["author"], "Synthetic editor")
        self.assertIn("full second paragraph", cards[0]["markdown"])
        self.assertEqual(cards[1]["state"], "retired")
        self.assertEqual(cards[1]["redirect_chain"], [RETIRED, FIRST])
        self.assertEqual(cards[1]["target_id"], FIRST)
        self.assertEqual(cards[4]["state"], "unresolved")
        self.assertEqual(cards[4]["target_id"], None)
        self.assertIn(MISSING, cards[4]["reason"])
        self.assertEqual(cards[4]["plain_text"], "")
        encoded = json.dumps(snapshot)
        self.assertNotIn("UNRELATED CANONICAL BODY", encoded)
        self.assertNotIn("UNRELATED PERSONAL NOTE", encoded)

    def test_full_bodies_location_review_flags_and_fingerprints_remain_literal(self):
        snapshot = self.capture()
        card = snapshot["records"][2]
        canonical = self.book.canonical_records[FIRST]
        self.assertEqual(card["markdown"], canonical["markdown"])
        self.assertEqual(card["plain_text"], canonical["plain_text"])
        self.assertEqual(card["sources"], canonical["sources"])
        self.assertEqual([source["pdf_page"] for source in card["sources"]], [2, 4])
        self.assertEqual(card["content_sha256"], canonical["content_sha256"])
        self.assertRegex(card["metadata_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(card["transcription_status"], "needs_visual_review")
        self.assertEqual(card["text_basis"], "loaded_canonical_record_at_capture")
        self.assertIn("not_comparison_save_time", snapshot["text_basis"])
        self.assertEqual(snapshot["corpus"]["source_verification"], "manifest_declared_only")
        self.assertEqual(snapshot["corpus"]["generation"]["state"], "current")
        self.assertEqual(snapshot["corpus"]["generation"]["index_sha256"], self.book.corpus_snapshot.index_sha256)

    def test_note_binding_status_preserves_retired_original_target(self):
        cards = self.capture()["records"]
        notes = {note["id"]: note for note in cards[2]["notes"]}
        self.assertEqual(notes[self.matching["id"]]["status"], "matching")
        self.assertEqual(notes[self.stale["id"]]["status"], "stale")
        self.assertEqual(notes[self.legacy["id"]]["status"], "legacy")
        old = notes[self.retired["id"]]
        self.assertEqual(old["status"], "stale")
        self.assertEqual(old["target_id"], RETIRED)
        self.assertEqual(old["resolved_target_id"], FIRST)
        self.assertEqual(old["redirect_chain"], [RETIRED, FIRST])
        self.assertEqual(old["reference_state"], "retired")
        self.assertIn("not transferred", old["status_reason"])
        unresolved = cards[4]["notes"][0]
        self.assertEqual(unresolved["id"], self.unresolved["id"])
        self.assertEqual(unresolved["status"], "unresolved")
        self.assertEqual(unresolved["resolved_target_id"], None)

    def test_personal_revision_actor_time_and_latest_body_are_preserved(self):
        revised = self.store.update_annotation(self.matching["id"], "An audited revised personal body.", expected_revision=1)
        snapshot = self.capture()
        note = next(note for note in snapshot["records"][2]["notes"] if note["id"] == self.matching["id"])
        self.assertEqual(note["revision"], 2)
        self.assertEqual(note["revision_audit"], "audited")
        self.assertEqual(note["body"], revised["body"])
        self.assertEqual(note["actor"], "Ada")
        self.assertEqual(note["created_at"], revised["created_at"])
        self.assertEqual(note["updated_at"], revised["updated_at"])
        self.assertEqual(snapshot["comparison"]["actor"], "Ada")
        self.assertTrue(snapshot["captured_at"].endswith("Z"))

    def test_capture_does_not_move_cursor_write_history_or_require_actor(self):
        before = stable_export(self.store)
        database = self.store.path.read_bytes()
        corpus = {p.name: p.read_bytes() for p in self.corpus.iterdir()}
        revision, resumed = self.reader.revision, self.reader.resumed_reference
        with patch.object(self.reader, "require_author", side_effect=AssertionError("authored writes forbidden")), \
                patch.object(self.reader, "checkpoint", side_effect=AssertionError("checkpoint forbidden")):
            self.capture()
        self.assertEqual(stable_export(self.store), before)
        self.assertEqual(self.store.path.read_bytes(), database)
        self.assertEqual(corpus, {p.name: p.read_bytes() for p in self.corpus.iterdir()})
        self.assertEqual(self.reader.revision, revision)
        self.assertIs(self.reader.resumed_reference, resumed)
        self.assertIsNone(self.reader.actor)

    def test_only_one_coherent_export_is_used_without_later_store_reads(self):
        exported = self.store.export()
        with patch.object(self.store, "export", return_value=exported) as export, \
                patch.object(self.store, "get_comparison", side_effect=AssertionError("later comparison read")), \
                patch.object(self.store, "list_annotations", side_effect=AssertionError("later annotation read")), \
                patch.object(self.store, "save_state", side_effect=AssertionError("state write")):
            snapshot = self.capture()
        export.assert_called_once_with()
        self.assertEqual(snapshot["workspace"]["exported_at"], exported["exported_at"])

    def test_snapshot_is_independent_of_book_store_export_and_other_cards(self):
        exported = self.store.export()
        with patch.object(self.store, "export", return_value=exported):
            snapshot = self.capture()
        snapshot["records"][2]["sources"][0]["printed_page"] = "changed"
        snapshot["records"][2]["notes"][0]["body"] = "changed"
        snapshot["comparison"]["question"] = "changed"
        self.assertEqual(snapshot["records"][3]["sources"][0]["printed_page"], "1")
        self.assertNotEqual(snapshot["records"][3]["notes"][0]["body"], "changed")
        self.assertEqual(self.book.canonical_records[FIRST]["sources"][0]["printed_page"], "1")
        self.assertNotEqual(exported["comparisons"][0]["question"], "changed")
        self.assertNotEqual(exported["annotations"][0]["body"], "changed")

    def test_changed_corpus_before_capture_is_refused_without_export(self):
        (self.corpus / "invented.md").write_text("changed canonical document")
        with patch.object(self.store, "export", wraps=self.store.export) as export:
            with self.assertRaisesRegex(WorkspaceError, "loaded corpus changed"):
                self.capture()
        export.assert_not_called()

    def test_changed_corpus_during_capture_is_refused_after_export(self):
        exported = self.store.export()
        def changed():
            (self.corpus / "invented.md").write_text("changed during capture")
            return exported
        with patch.object(self.store, "export", side_effect=changed):
            with self.assertRaisesRegex(WorkspaceError, "loaded corpus changed"):
                self.capture()

    def test_unknown_generation_is_truthfully_labeled(self):
        self.book.corpus_snapshot = None
        snapshot = self.capture()
        generation = snapshot["corpus"]["generation"]
        self.assertEqual(generation["state"], "unknown")
        self.assertIsNone(generation["index_sha256"])
        self.assertEqual(generation["documents"], {})
        self.assertIn("No verified", generation["reason"])

    def test_broken_explicit_retirement_chain_is_visible_without_guessing(self):
        self.book.corpus_snapshot = None
        self.book.canonical_records[RETIRED]["redirect_id"] = MISSING
        snapshot = self.capture()
        old = snapshot["records"][1]
        self.assertEqual(old["state"], "unresolved")
        self.assertEqual(old["redirect_chain"], [RETIRED, MISSING])
        self.assertEqual(old["plain_text"], "")
        old_note = next(note for note in old["notes"] if note["id"] == self.retired["id"])
        self.assertEqual(old_note["status"], "unresolved")
        self.assertEqual(old_note["redirect_chain"], [RETIRED, MISSING])

    def test_legacy_revision_and_no_text_binding_are_distinguished(self):
        exported = self.store.export()
        exported["schema_version"] = 1
        annotation = exported["annotations"][0]
        annotation["revision"] = None
        annotation["content_sha256"] = None
        with patch.object(self.store, "export", return_value=exported):
            snapshot = self.capture()
        notes = snapshot["records"][2]["notes"]
        note = next(note for note in notes if note["id"] == annotation["id"])
        self.assertIsNone(note["revision"])
        self.assertEqual(note["revision_audit"], "legacy")
        self.assertEqual(note["status"], "legacy")

    def test_missing_comparison_and_wrong_corpus_are_actionable_errors(self):
        with self.assertRaisesRegex(ComparisonError, "No comparison with that name"):
            capture_comparison(self.reader, "absent")
        exported = self.store.export()
        exported["corpus_id"] = MISSING
        with patch.object(self.store, "export", return_value=exported):
            with self.assertRaisesRegex(ComparisonError, "different canonical corpus"):
                self.capture()

    def test_store_supported_uppercase_flat_and_historical_source_provenance(self):
        for index, provenance in enumerate([
            {"source_sha256": SOURCE.upper()},
            {"source_sha256": SOURCE.upper(), "source": "historical source metadata"},
            {"source": {"sha256": SOURCE.upper()}},
        ]):
            with self.subTest(provenance=provenance):
                store = Workspace(self.directory / f"compatible-{index}.sqlite3", CORPUS, provenance, actor="Ada")
                self.addCleanup(store.close)
                store.save_comparison("inquiry", [FIRST], "A compatible source binding.")
                reader = WorkspaceReader(self.book, store, None, None, None, None)
                snapshot = capture_comparison(reader, "inquiry")
                self.assertEqual(snapshot["records"][0]["requested_id"], FIRST)

    def test_changed_metadata_gets_different_digest_without_altering_text_digest(self):
        before = self.capture()["records"][2]
        self.book.corpus_snapshot = None
        self.book.canonical_records[FIRST]["attribution"]["status"] = "unresolved"
        after = self.capture()["records"][2]
        self.assertEqual(before["content_sha256"], after["content_sha256"])
        self.assertNotEqual(before["metadata_sha256"], after["metadata_sha256"])


if __name__ == "__main__":
    unittest.main()
