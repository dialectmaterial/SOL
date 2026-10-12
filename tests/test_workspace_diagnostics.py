"""Pure workspace diagnostics over synthetic references, without private text."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sol_workspace_diagnostics import reference_data, review_queue, workspace_health


CORPUS = "aaaaaaaa-0000-4000-8000-000000000001"
FIRST = "bbbbbbbb-0000-4000-8000-000000000001"
SECOND = "bbbbbbbb-0000-4000-8000-000000000002"
EDITORIAL = "cccccccc-0000-4000-8000-000000000001"
RETIRED = "dddddddd-0000-4000-8000-000000000001"
MISSING = "eeeeeeee-0000-4000-8000-000000000001"
SOURCE_SHA = "0" * 64


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        def record(identifier, order, path, author="Synthetic philosopher", role="main_text"):
            body = "Private synthetic prose that diagnostics must not export."
            return {
                "id": identifier, "type": "paragraph", "order": order,
                "reader_path": path, "reader_title": "Synthetic heading",
                "attribution": {"author": author, "role": role, "status": "confirmed"},
                "sources": [{"pdf_page": order + 1, "printed_page": str(order + 1)}],
                "markdown": body, "plain_text": body,
                "content_sha256": hashlib.sha256((identifier + body).encode()).hexdigest(),
                "transcription_status": "needs_review",
            }
        records = {
            FIRST: record(FIRST, 0, "/BEING/01-sample.txt"),
            SECOND: record(SECOND, 1, "/BEINGNESS/01-sample.txt"),
            EDITORIAL: record(EDITORIAL, 2, None, "Synthetic editor", "editorial_note"),
            RETIRED: {"id": RETIRED, "type": "retired_record", "redirect_id": FIRST, "order": 3},
        }
        records[EDITORIAL].pop("reader_path")
        records[EDITORIAL]["type"] = "note"
        records[EDITORIAL]["transcription_status"] = "needs_visual_review"

        def find_passage(identifier):
            if identifier not in (FIRST, SECOND):
                raise ValueError("not readable main text")
            return SimpleNamespace(identifier=identifier)

        self.book = SimpleNamespace(
            canonical_records=records, find_passage=find_passage,
            corpus_manifest={"corpus_id": CORPUS, "source": {"sha256": SOURCE_SHA}},
        )
        self.snapshot = {
            "format": "sol-workspace", "schema_version": 1, "corpus_id": CORPUS,
            "provenance": {"source": {"sha256": SOURCE_SHA}}, "state": None,
            "history": [], "bookmarks": [], "annotations": [], "comparisons": [],
            "reviews": [], "relations": [],
        }

    def review(self, identifier=FIRST, **extra):
        digest = self.book.canonical_records[FIRST]["content_sha256"]
        return {
            "id": "ffffffff-0000-4000-8000-000000000001", "target_id": identifier,
            "actor": "Ada", "outcome": "verified", "created_at": "2026-10-12T10:00:00Z",
            "content_sha256": digest, "source_sha256": SOURCE_SHA, **extra,
        }

    def test_reference_is_json_safe_and_contains_metadata_not_prose(self):
        reference = reference_data(self.book, FIRST)
        self.assertEqual(reference["requested_id"], FIRST)
        self.assertEqual(reference["resolved_id"], FIRST)
        self.assertEqual(reference["state"], "live")
        self.assertTrue(reference["readable"])
        self.assertEqual(reference["sources"], self.book.canonical_records[FIRST]["sources"])
        self.assertNotIn("Private synthetic prose", json.dumps(reference))
        self.assertNotIn("markdown", reference)
        reference["sources"][0]["pdf_page"] = 99
        self.assertEqual(self.book.canonical_records[FIRST]["sources"][0]["pdf_page"], 1)

    def test_retired_reference_preserves_requested_uuid_and_explicit_chain(self):
        reference = reference_data(self.book, RETIRED)
        self.assertEqual(reference["requested_id"], RETIRED)
        self.assertEqual(reference["resolved_id"], FIRST)
        self.assertEqual(reference["redirect_chain"], [RETIRED, FIRST])
        self.assertEqual(reference["state"], "retired")
        self.assertTrue(reference["readable"])

    def test_editorial_reference_is_live_but_not_a_main_text_passage(self):
        reference = reference_data(self.book, EDITORIAL)
        self.assertEqual(reference["state"], "live")
        self.assertFalse(reference["readable"])
        self.assertEqual(reference["attribution"]["role"], "editorial_note")

    def test_absent_and_missing_identifiers_are_distinct_without_exceptions(self):
        self.assertEqual(reference_data(self.book, None)["state"], "absent")
        missing = reference_data(self.book, MISSING)
        self.assertEqual(missing["state"], "unresolved")
        self.assertEqual(missing["requested_id"], MISSING)
        self.assertIsNone(missing["resolved_id"])
        self.assertEqual(reference_data(self.book, "")["state"], "unresolved")
        with self.assertRaises(ValueError):
            reference_data(self.book, 1)

    def test_unambiguous_prefix_expands_to_full_uuid(self):
        reference = reference_data(self.book, "cccccccc")
        self.assertEqual(reference["requested_id"], EDITORIAL)
        ambiguous = reference_data(self.book, "bbbbbbbb")
        self.assertEqual(ambiguous["state"], "unresolved")
        self.assertIn("ambiguous", ambiguous["reason"])

    def test_empty_workspace_health_distinguishes_pending_corpus_from_workspace_integrity(self):
        report = workspace_health(self.book, self.snapshot)
        self.assertEqual(report["format"], "sol-workspace-health")
        self.assertEqual(report["status"], "no_workspace_issues_detected")
        self.assertEqual(report["canonical_review_state"], "pending")
        self.assertEqual(report["counts"]["pending_source_review"], 3)
        self.assertEqual(report["issues"], [])
        self.assertNotIn("Private synthetic prose", json.dumps(report))

    def test_all_reference_collections_are_checked_including_history_and_relation_endpoints(self):
        self.snapshot.update({
            "state": {"revision": 2, "current_id": None},
            "history": [{"revision": 1, "current_id": MISSING}],
            "bookmarks": [{"name": "old", "target_id": RETIRED}],
            "comparisons": [{"name": "pair", "target_ids": [FIRST, MISSING]}],
            "relations": [{"id": "relation", "kind": "compares-with", "source_id": MISSING, "target_id": RETIRED}],
        })
        report = workspace_health(self.book, self.snapshot)
        self.assertEqual(report["counts"]["references"], 7)
        self.assertEqual(report["counts"]["unresolved_references"], 3)
        self.assertEqual(report["counts"]["retired_references"], 2)
        self.assertEqual(report["counts"]["absent_references"], 1)
        self.assertEqual({issue["collection"] for issue in report["issues"]},
                         {"state", "history", "bookmarks", "comparisons", "relations"})
        self.assertEqual(report["status"], "attention_required")

    def test_annotation_staleness_and_missing_version_are_explicit(self):
        self.snapshot["annotations"] = [
            {"id": "old", "target_id": FIRST, "actor": "Ada", "content_sha256": "1" * 64},
            {"id": "unversioned", "target_id": SECOND, "actor": "Ada", "content_sha256": None},
        ]
        report = workspace_health(self.book, self.snapshot)
        self.assertEqual(report["counts"]["stale_annotations"], 1)
        self.assertEqual(report["counts"]["unversioned_annotations"], 1)
        self.assertEqual({issue["kind"] for issue in report["issues"]},
                         {"annotation_stale", "annotation_unversioned"})

    def test_reading_checkpoints_history_and_bookmarks_must_target_readable_passages(self):
        self.snapshot.update({
            "state": {"revision": 2, "current_id": EDITORIAL},
            "history": [{"revision": 1, "current_id": EDITORIAL}],
            "bookmarks": [{"name": "editorial", "target_id": EDITORIAL}],
        })
        report = workspace_health(self.book, self.snapshot)
        self.assertEqual(report["counts"]["unreadable_reading_references"], 3)
        self.assertEqual(report["counts"]["unresolved_references"], 0)
        self.assertEqual(report["status"], "attention_required")
        self.assertEqual({issue["collection"] for issue in report["issues"]}, {"state", "history", "bookmarks"})
        self.assertTrue(all(issue["kind"] == "unreadable_reading_reference" for issue in report["issues"]))
        self.assertTrue(all(issue["reference"]["state"] == "live" for issue in report["issues"]))

    def test_retired_reading_reference_redirecting_to_editorial_material_remains_unreadable(self):
        self.book.canonical_records[RETIRED]["redirect_id"] = EDITORIAL
        self.snapshot["state"] = {"revision": 1, "current_id": RETIRED}
        report = workspace_health(self.book, self.snapshot)
        self.assertEqual(report["counts"]["retired_references"], 1)
        self.assertEqual(report["counts"]["unreadable_reading_references"], 1)
        unreadable = next(issue for issue in report["issues"] if issue["kind"] == "unreadable_reading_reference")
        self.assertEqual(unreadable["target_id"], RETIRED)
        self.assertEqual(unreadable["reference"]["resolved_id"], EDITORIAL)

    def test_editorial_targets_are_valid_for_annotations_comparisons_reviews_and_relations(self):
        self.snapshot.update({
            "annotations": [{"id": "note", "target_id": EDITORIAL, "actor": "Ada",
                             "content_sha256": self.book.canonical_records[EDITORIAL]["content_sha256"]}],
            "comparisons": [{"name": "editorial pair", "target_ids": [EDITORIAL, FIRST]}],
            "reviews": [self.review(identifier=EDITORIAL,
                                    content_sha256=self.book.canonical_records[EDITORIAL]["content_sha256"])],
            "relations": [{"id": "relation", "kind": "discusses", "source_id": EDITORIAL, "target_id": FIRST}],
        })
        report = workspace_health(self.book, self.snapshot)
        self.assertEqual(report["counts"]["unreadable_reading_references"], 0)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["status"], "no_workspace_issues_detected")

    def test_review_versions_distinguish_text_changes_source_changes_and_missing_hashes(self):
        for extra, kind in (({"content_sha256": "1" * 64}, "review_stale"),
                            ({"source_sha256": "1" * 64}, "review_stale"),
                            ({"content_sha256": None}, "review_unversioned"),
                            ({"source_sha256": None}, "review_unversioned")):
            with self.subTest(extra=extra):
                self.snapshot["reviews"] = [self.review(**extra)]
                report = workspace_health(self.book, self.snapshot)
                self.assertEqual(report["issues"][0]["kind"], kind)
                self.assertEqual(report["issues"][0]["provenance_binding"], "text_and_pdf_fingerprint_only")

    def test_identity_and_source_mismatch_are_reported_not_reconciled(self):
        self.snapshot["corpus_id"] = MISSING
        self.snapshot["provenance"]["source"]["sha256"] = "9" * 64
        report = workspace_health(self.book, self.snapshot)
        self.assertEqual({issue["kind"] for issue in report["issues"]},
                         {"corpus_identity_mismatch", "source_fingerprint_mismatch"})

    def test_queue_includes_editorial_material_and_remains_pending_after_verified_testimony(self):
        self.snapshot["reviews"] = [self.review()]
        queue = review_queue(self.book, self.snapshot)
        self.assertEqual([record["id"] for record in queue], [FIRST, SECOND, EDITORIAL])
        self.assertEqual(queue[0]["latest_review"]["outcome"], "verified")
        self.assertEqual(queue[0]["latest_review"]["version_state"], "current_text_and_pdf")
        self.assertEqual(queue[0]["transcription_status"], "needs_review")
        self.assertEqual(queue[2]["attribution"]["role"], "editorial_note")
        self.assertNotIn("Private synthetic prose", json.dumps(queue))

    def test_queue_scope_obeys_path_component_boundaries_and_excludes_unmapped_editorial_records(self):
        self.assertEqual([record["id"] for record in review_queue(self.book, self.snapshot, ("BEING",))], [FIRST])
        self.assertEqual([record["id"] for record in review_queue(self.book, self.snapshot, ())], [FIRST, SECOND])
        self.assertEqual(review_queue(self.book, self.snapshot, ("ESSENCE",)), [])
        self.assertEqual([record["id"] for record in review_queue(self.book, self.snapshot, ("BEING", "01-sample.txt"))], [FIRST])

    def test_queue_limits_are_validated_and_applied_after_filtering(self):
        self.assertEqual(len(review_queue(self.book, self.snapshot, limit=1)), 1)
        for value in (0, -1, 1001, True, "2", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review_queue(self.book, self.snapshot, limit=value)
        for scope in ("/BEING", ["BEING"], ("..",), ("BEING/other",), ("",)):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                review_queue(self.book, self.snapshot, within=scope)

    def test_queue_uses_append_order_and_discloses_equal_timestamp_ambiguity(self):
        old = self.review(created_at="2026-10-12T09:00:00Z", outcome="correction_needed")
        new = self.review(id="ffffffff-0000-4000-8000-000000000002", actor="Bela")
        self.snapshot["reviews"] = [old, new]
        latest = review_queue(self.book, self.snapshot)[0]["latest_review"]
        self.assertEqual(latest["actor"], "Bela")
        self.assertFalse(latest["chronology_ambiguous"])
        self.assertEqual(latest["chronology_basis"], "exported_append_order")
        old["created_at"] = new["created_at"]
        latest = review_queue(self.book, self.snapshot)[0]["latest_review"]
        self.assertFalse(latest["chronology_ambiguous"])
        self.assertTrue(latest["timestamp_ambiguous"])

    def test_newer_append_with_backwards_clock_does_not_resurrect_old_verified_testimony(self):
        old = self.review(created_at="2026-10-12T10:00:00Z", outcome="verified")
        new = self.review(id="ffffffff-0000-4000-8000-000000000002", actor="Bela",
                          created_at="2026-10-12T09:00:00Z", outcome="correction_needed")
        self.snapshot["reviews"] = [old, new]
        latest = review_queue(self.book, self.snapshot)[0]["latest_review"]
        self.assertEqual(latest["actor"], "Bela")
        self.assertEqual(latest["outcome"], "correction_needed")
        self.assertTrue(latest["timestamps_non_monotonic"])

    def test_retired_testimony_is_not_reused_as_verification_of_redirect_target(self):
        self.snapshot["reviews"] = [self.review(identifier=RETIRED)]
        queue = review_queue(self.book, self.snapshot)
        self.assertEqual(queue[0]["latest_review"]["version_state"], "retired")
        self.assertEqual(queue[0]["latest_review"]["target_id"], RETIRED)
        report = workspace_health(self.book, self.snapshot)
        self.assertEqual(report["issues"][0]["kind"], "reference_retired")

    def test_source_metadata_edits_are_not_misrepresented_as_fully_bound_review_versions(self):
        self.snapshot["reviews"] = [self.review()]
        self.book.canonical_records[FIRST]["sources"][0]["pdf_page"] = 99
        self.book.canonical_records[FIRST]["attribution"]["author"] = "Corrected attribution"
        latest = review_queue(self.book, self.snapshot)[0]["latest_review"]
        self.assertEqual(latest["version_state"], "current_text_and_pdf")
        self.assertEqual(latest["provenance_binding"], "text_and_pdf_fingerprint_only")

    def test_diagnostics_are_read_only_and_do_not_open_files_or_databases(self):
        original_book, original_workspace = deepcopy(self.book.canonical_records), deepcopy(self.snapshot)
        with patch("builtins.open", side_effect=AssertionError("No file I/O")), \
                patch("sqlite3.connect", side_effect=AssertionError("No database I/O")):
            workspace_health(self.book, self.snapshot)
            queue = review_queue(self.book, self.snapshot)
        queue[0]["sources"][0]["pdf_page"] = 100
        self.assertEqual(self.book.canonical_records, original_book)
        self.assertEqual(self.snapshot, original_workspace)

    def test_batch_diagnostics_build_readability_once_without_rebuilding_passage_maps(self):
        self.book.passages = [SimpleNamespace(identifier=FIRST), SimpleNamespace(identifier=SECOND)]
        self.snapshot["bookmarks"] = [{"name": "live", "target_id": FIRST}]
        self.snapshot["reviews"] = [self.review()]
        with patch.object(self.book, "find_passage", side_effect=AssertionError("No repeated passage map scans")):
            report = workspace_health(self.book, self.snapshot)
            queue = review_queue(self.book, self.snapshot)
        self.assertEqual(report["issues"], [])
        self.assertEqual(queue[0]["latest_review"]["version_state"], "current_text_and_pdf")

    def test_malformed_snapshot_shapes_fail_clearly(self):
        for malformed in (None, [], {"reviews": None}, {"annotations": [None]}, {"state": "wrong"},
                          {"comparisons": [{"target_ids": "wrong"}]}):
            with self.subTest(snapshot=malformed), self.assertRaises(ValueError):
                workspace_health(self.book, malformed)


if __name__ == "__main__":
    unittest.main()
