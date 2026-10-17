"""Fresh offline exports remain exact while avoiding duplicate CORE checks.

All corpus content here is invented and disposable. Imported references still
use the full public CORE check; the faster path is only for locally captured
references during one bounded, read-only experiment export.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from sol import core

from experiments.reader_surfaces import common, html
import fixtures_corpus as fixtures


RETIRED_A = "dddddddd-0000-4000-8000-000000000004"
RETIRED_B = "eeeeeeee-0000-4000-8000-000000000005"
SECOND_PASSAGE = "ffffffff-0000-4000-8000-000000000006"


class ReaderSurfaceExportGuardTests(fixtures.CorpusFixture, unittest.TestCase):

    def records(self):
        return [json.loads(line) for line in
                (self.corpus / "index.jsonl").read_text(encoding="utf-8").splitlines()]

    def add_retirements(self):
        records = self.records()
        source = next(record for record in records if record["id"] == self.identifier)
        for identifier, target in ((RETIRED_A, RETIRED_B), (RETIRED_B, self.identifier)):
            record = copy.deepcopy(source)
            record.update(id=identifier, order=len(records), type="retired_record", redirect_id=target,
                          markdown="An invented retired reference.", plain_text="An invented retired reference.")
            records.append(record)
        self.write_records(records)

    def test_render_captures_each_main_record_and_shared_note_only_once(self):
        note_id = self.add_note()
        records = self.records()
        paragraph = next(record for record in records if record["id"] == self.identifier)
        second = copy.deepcopy(paragraph)
        second.update(id=SECOND_PASSAGE, order=len(records), markdown="Another invented paragraph.",
                      plain_text="Another invented paragraph.")
        records.append(second)
        next(record for record in records if record["id"] == note_id)["backlinks"].append(SECOND_PASSAGE)
        self.write_records(records)
        sample = common.sample_from_book(self.book, count=2)
        with patch.object(common, "capture_references", wraps=core.capture_references) as capture, \
                patch.object(common, "check_reference", side_effect=AssertionError("fresh export checked twice")):
            rendered = html.render_html(sample)
        capture.assert_called_once()
        requested = capture.call_args.args[1]
        self.assertCountEqual(requested, [self.identifier, SECOND_PASSAGE, note_id])
        self.assertEqual(requested.count(note_id), 1)
        self.assertIn(second["plain_text"], rendered)

    def test_every_serialized_reference_passes_unchanged_independent_core_check(self):
        self.add_note()
        sample = common.sample_from_book(self.book, count=1)
        before = self.files()
        document = fixtures._Document(html.render_html(sample))
        embedded = next(text for tag, attrs, text in document.blocks if attrs.get("id") == "sol-data")
        rows = json.loads(embedded)["records"]
        self.assertEqual(len(rows), 1)
        for payload in rows:
            reference = core.check_reference(self.book.corpus_snapshot, payload["reference"])
            self.assertEqual(reference.target_id, payload["id"])
            self.assertEqual(reference.record["plain_text"], payload["plain_text"])
            self.assertEqual(payload["plain_text_sha256"],
                             hashlib.sha256(reference.record["plain_text"].encode("utf-8")).hexdigest())
        self.assertEqual(self.files(), before)

    def test_capture_keeps_full_retirement_chain_and_requested_identity(self):
        self.add_retirements()
        capture = common.CaptureExport(self.book)
        payload, reference = capture.capture(RETIRED_A[:8])
        capture.finish()
        expected = (RETIRED_A, RETIRED_B, self.identifier)
        self.assertEqual(reference.chain, expected)
        self.assertEqual(reference.requested_id, RETIRED_A)
        self.assertEqual(reference.target_id, self.identifier)
        self.assertEqual(payload["reference"]["chain"], list(expected))
        self.assertEqual(core.check_reference(self.book.corpus_snapshot, payload).chain, expected)

    def test_cached_capture_is_defensive_and_uses_canonical_requested_identity(self):
        self.add_retirements()
        capture = common.CaptureExport(self.book)
        with patch.object(common, "capture_reference", wraps=core.capture_reference) as operation:
            first, reference = capture.capture(RETIRED_A[:8])
            first["reference"]["chain"].append(self.identifier)
            reference.record["plain_text"] = "An invented corrupt caller-owned return value."
            again, restored = capture.capture(RETIRED_A)
            capture.finish()
        self.assertEqual(operation.call_count, 1)
        self.assertEqual(again["reference"]["chain"], [RETIRED_A, RETIRED_B, self.identifier])
        self.assertEqual(restored.record["plain_text"], self.body)
        self.assertEqual(core.check_reference(self.book.corpus_snapshot, again).chain, restored.chain)

    def test_finished_capture_cannot_be_reused_as_a_long_lived_trust_cache(self):
        before = self.files()
        capture = common.CaptureExport(self.book)
        capture.capture(self.identifier)
        capture.finish()
        with patch.object(common, "capture_reference", wraps=core.capture_reference) as operation:
            with self.assertRaises(ValueError):
                capture.capture(self.identifier)
            with self.assertRaises(ValueError):
                capture.finish()
        self.assertEqual(operation.call_count, 0)
        self.assertEqual(self.files(), before)

    def test_failed_finish_closes_capture_even_after_corpus_files_are_restored(self):
        capture = common.CaptureExport(self.book)
        capture.capture(self.identifier)
        source = self.corpus / "sample.md"
        original = source.read_bytes()
        source.write_bytes(original + b"\nAn invented unindexed edit.\n")
        with self.assertRaises(ValueError):
            capture.finish()
        source.write_bytes(original)
        with patch.object(common, "capture_reference", wraps=core.capture_reference) as operation:
            with self.assertRaises(ValueError):
                capture.capture(self.identifier)
            with self.assertRaises(ValueError):
                capture.finish()
        self.assertEqual(operation.call_count, 0)

    def test_unverified_or_missing_snapshot_has_a_clean_refusal(self):
        before = self.files()
        for snapshot in (None, object(), {"records": [], "manifest": {}}):
            with self.subTest(snapshot=snapshot), patch.object(self.book, "corpus_snapshot", snapshot):
                with self.assertRaises(ValueError):
                    common.CaptureExport(self.book)
        self.assertEqual(self.files(), before)

    def test_detached_alias_shortcut_is_refused_even_when_final_target_is_unchanged(self):
        self.add_retirements()
        self.book.canonical_records = copy.deepcopy(self.book.canonical_records)
        self.book.canonical_records[RETIRED_A]["redirect_id"] = self.identifier
        with self.assertRaises(ValueError):
            capture = common.CaptureExport(self.book)
            capture.capture(RETIRED_A)
            capture.finish()

    def test_loaded_snapshot_record_corruption_is_not_accepted_as_disk_authority(self):
        sample = common.sample_from_book(self.book, count=1)
        source = next(record for record in self.book.corpus_snapshot.records if record["id"] == self.identifier)
        text = "An invented false replacement with a freshly computed local digest."
        source.update(markdown=text, plain_text=text, content_sha256=hashlib.sha256(text.encode()).hexdigest())
        with self.assertRaises(ValueError):
            html.render_html(sample)

    def test_loaded_snapshot_manifest_corruption_is_refused(self):
        sample = common.sample_from_book(self.book, count=1)
        self.book.corpus_snapshot.manifest["edition"]["translator"] = "An invented wrong translator"
        with self.assertRaises(ValueError):
            html.render_html(sample)

    def test_loaded_snapshot_document_fingerprints_cannot_be_overridden(self):
        sample = common.sample_from_book(self.book, count=1)
        self.book.corpus_snapshot.documents["sample.md"] = "0" * 64
        with self.assertRaises(ValueError):
            html.render_html(sample)

    def test_finish_detects_snapshot_mutation_after_its_successful_capture(self):
        capture = common.CaptureExport(self.book)
        capture.capture(self.identifier)
        source = next(record for record in self.book.corpus_snapshot.records if record["id"] == self.identifier)
        source["plain_text"] = "An invented late mutation of caller-owned snapshot memory."
        with self.assertRaises(ValueError):
            capture.finish()

    def test_old_loaded_sample_cannot_mix_with_a_new_valid_disk_generation(self):
        sample = common.sample_from_book(self.book, count=1)
        self.rewrite_body(self.body + " An invented correction made another valid generation.")
        with self.assertRaises(ValueError):
            html.render_html(sample)

    def test_captured_record_binding_must_agree_before_rendering(self):
        changes = (
            ("content_sha256", "0" * 64),
            ("type", "note"),
            ("sources", [{"pdf_page": 1, "printed_page": "1"}]),
            ("attribution", {"author": "Wrong author", "role": "main_text", "status": "confirmed"}),
            ("chain", [self.identifier, RETIRED_A]),
            ("target_id", RETIRED_A),
        )
        for field, value in changes:
            with self.subTest(field=field):
                def changed(snapshot, identifiers):
                    payloads = core.capture_references(snapshot, identifiers)
                    payloads[0]["reference"][field] = value
                    return payloads
                with patch.object(common, "capture_references", side_effect=changed), self.assertRaises(ValueError):
                    html.render_html(common.sample_from_book(self.book, count=1))

    def test_captured_corpus_and_generation_bindings_cannot_be_mixed(self):
        for group, field, value in (("corpus", "id", RETIRED_A),
                                    ("corpus", "edition_sha256", "0" * 64),
                                    ("corpus", "source", {"sha256": "1" * 64, "pdf_pages": 80}),
                                    ("generation", "index_sha256", "0" * 64),
                                    ("generation", "manifest_sha256", "0" * 64)):
            with self.subTest(group=group, field=field):
                def changed(snapshot, identifiers):
                    payloads = core.capture_references(snapshot, identifiers)
                    payloads[0][group][field] = value
                    return payloads
                with patch.object(common, "capture_references", side_effect=changed), self.assertRaises(ValueError):
                    html.render_html(common.sample_from_book(self.book, count=1))

    def test_source_edit_during_last_typography_projection_leaves_no_artifact(self):
        sample = common.sample_from_book(self.book, count=1)
        output = self.root / "refused.html"
        project = html.map_typography
        def changed(markdown, text):
            result = project(markdown, text)
            source = self.corpus / "sample.md"
            source.write_text(source.read_text(encoding="utf-8") + "\nUnindexed invented edit.\n", encoding="utf-8")
            return result
        with patch.object(html, "map_typography", side_effect=changed), self.assertRaises(ValueError):
            html.write_html(sample, output)
        self.assertFalse(output.exists())
        self.assertFalse(output.is_symlink())

    def test_detached_main_record_change_during_render_is_refused_without_artifact(self):
        sample = common.sample_from_book(self.book, count=1)
        output = self.root / "refused.html"
        project = html.map_typography
        def changed(markdown, text):
            result = project(markdown, text)
            self.book.canonical_records = copy.deepcopy(self.book.canonical_records)
            self.book.canonical_records[self.identifier]["plain_text"] = "A false late replacement."
            return result
        with patch.object(html, "map_typography", side_effect=changed), self.assertRaises(ValueError):
            html.write_html(sample, output)
        self.assertFalse(output.exists())

    def test_detached_note_change_during_its_projection_is_refused_without_artifact(self):
        note_id = self.add_note()
        sample = common.sample_from_book(self.book, count=1)
        output = self.root / "refused.html"
        project = html.map_typography
        note_text = self.book.canonical_records[note_id]["plain_text"]
        def changed(markdown, text):
            result = project(markdown, text)
            if text == note_text:
                self.book.canonical_records = copy.deepcopy(self.book.canonical_records)
                self.book.canonical_records[note_id]["attribution"]["author"] = "A false late note author"
            return result
        with patch.object(html, "map_typography", side_effect=changed), self.assertRaises(ValueError):
            html.write_html(sample, output)
        self.assertFalse(output.exists())

    def test_imported_packet_validation_still_uses_full_core_check(self):
        selected = common.selection_packet(self.book, self.identifier, 3, 14)
        with patch.object(common, "check_reference", wraps=core.check_reference) as check:
            restored = common.validate_packet(self.book, selected)
        self.assertEqual(check.call_count, 1)
        self.assertEqual(restored.text, self.body[3:14])


if __name__ == "__main__":
    unittest.main()
