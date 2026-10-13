"""Synthetic, private-copy ingestion proofs; no edition text or personal data."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.corpus import contract, ingest


class ReviewedIngestionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-ingestion-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.baseline = self.root / "baseline"
        self.baseline.mkdir()
        self.output = self.root / "reviewed"
        self.candidate_path = self.root / "candidate.json"
        self.review_path = self.root / "review.json"
        self.section_id, self.paragraph_id, self.note_id, self.other_id = [contract.new_id() for _ in range(4)]
        self.manifest = {
            "contract_version": 1, "corpus_id": contract.new_id(),
            "edition": {"title": "Invented source", "translator": "Invented translator"},
            "source": {"filename": "historic-name.pdf", "sha256": "0" * 64, "pdf_pages": 2},
            "documents": ["hegel/main.md", "notes/main.md"],
            "page_inventory": [{"pdf_page": 1, "printed_page": "iv", "disposition": "records"},
                               {"pdf_page": 2, "printed_page": "1", "disposition": "records"}],
        }
        self.callout = f'<sup data-sol-note="{self.note_id}">[a](../notes/main.md#{self.note_id})</sup>'
        self.records = [
            (self.record(self.section_id, "section", None, 0, 1, title="Invented section"), "# Invented section"),
            (self.record(self.paragraph_id, "paragraph", self.section_id, 1, 1,
                         note_ids=[self.note_id], random_eligible=True), f"Old *invented* prose. {self.callout}"),
            (self.record(self.note_id, "note", self.paragraph_id, 2, 1,
                         label="a", backlinks=[self.paragraph_id]), "An invented note."),
            (self.record(self.other_id, "paragraph", self.section_id, 3, 2), "Untouched invented prose."),
        ]
        for name in self.manifest["documents"]:
            path = self.baseline / name
            path.parent.mkdir(parents=True, exist_ok=True)
            rows = self.records[2:3] if name.startswith("notes/") else [*self.records[:2], self.records[3]]
            path.write_text("\n".join(contract.render_record(meta, body) for meta, body in rows), encoding="utf-8")
        self.write_manifest()
        contract.reindex(self.baseline)
        self.before = {path.relative_to(self.baseline).as_posix(): path.read_bytes()
                       for path in self.baseline.rglob("*") if path.is_file()}
        self.raw = {"file name": "renamed-source.pdf", "number of pages": 2,
                    "author": None, "title": None, "creation date": None, "modification date": None,
                    "kids": [{"type": "paragraph", "id": 7, "page number": 1,
                              "bounding box": [10, 20, 100, 40], "content": "A physical paragraph."},
                             {"type": "paragraph", "id": 8, "page number": 2,
                              "bounding box": [10, 20, 100, 40], "content": "A physical note."}]}
        self.result = {"source": {"filename": "renamed-source.pdf", "sha256": "0" * 64, "pdf_pages": 2},
                       "backend": {"name": "opendataloader", "version": "2.5.13", "options": {"hybrid": "off"}},
                       "document": self.raw}
        self.write_candidate()
        self.review = {"review_version": 1, "artifact_sha256": self.digest(self.candidate_path),
                       "reviewer": "Invented review label",
                       "changes": [{"record_id": self.paragraph_id, "selectors": ["/kids/0"],
                                    "markdown": f"Approved *invented* prose. {self.callout}",
                                    "reason": "Explicit invented correction after source inspection"}],
                       "exclusions": [{"selector": "/kids/1", "reason": "Explicitly retain the baseline transcription"}]}
        self.write_review()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def record(self, identifier, kind, parent, order, page, **extra):
        return {"id": identifier, "type": kind, "parent_id": parent, "order": order,
                "sources": [{"pdf_page": page, "printed_page": "iv" if page == 1 else "1",
                             "bbox": [10, 20, 100, 40]}],
                "attribution": {"author": None, "status": "unverified", "role": "synthetic"}, **extra}

    def write_manifest(self):
        (self.baseline / "corpus.json").write_text(json.dumps(self.manifest, indent=3) + "\n", encoding="utf-8")

    def write_candidate(self):
        from sol.corpus import extraction
        artifact = extraction.make_artifact(self.result)
        self.candidate_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_review(self):
        self.review_path.write_text(json.dumps(self.review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def run_ingestion(self):
        return ingest.ingest_reviewed(self.candidate_path, self.review_path, self.baseline, self.output)

    def assert_baseline_unchanged(self):
        self.assertEqual(self.before, {path.relative_to(self.baseline).as_posix(): path.read_bytes()
                                     for path in self.baseline.rglob("*") if path.is_file()})

    def test_review_copy_preserves_identity_metadata_inventory_and_note_relations(self):
        before = contract.load_snapshot(self.baseline)
        result = self.run_ingestion()
        after = contract.load_snapshot(self.output)
        self.assertEqual((self.output / "corpus.json").read_bytes(), (self.baseline / "corpus.json").read_bytes())
        self.assertEqual(after.corpus_id, before.corpus_id)
        self.assertEqual([row["id"] for row in after.records], [row["id"] for row in before.records])
        for old, new in zip(before.records, after.records):
            self.assertEqual(ingest._metadata(old), ingest._metadata(new))
            self.assertEqual(new["markdown"], self.review["changes"][0]["markdown"]
                             if old["id"] == self.paragraph_id else old["markdown"])
        self.assertEqual(after.records[1]["note_ids"], [self.note_id])
        self.assertEqual(after.records[2]["backlinks"], [self.paragraph_id])
        self.assertEqual(result["changed_records"], 1)
        self.assertEqual(result["assigned_elements"], 1)
        self.assertEqual(result["excluded_elements"], 1)
        self.assert_baseline_unchanged()
        self.assertFalse((self.baseline / "historic-name.pdf").exists())

    def test_untouched_markdown_blocks_and_documents_remain_byte_exact(self):
        source = self.baseline / "hegel/main.md"
        # Valid canonical whitespace must not be silently reformatted elsewhere.
        original = source.read_text(encoding="utf-8")
        original = original.replace("Untouched invented prose.", "Untouched invented prose.  ")
        source.write_text(original, encoding="utf-8")
        contract.reindex(self.baseline)
        self.run_ingestion()
        self.assertEqual((self.output / "notes/main.md").read_bytes(), (self.baseline / "notes/main.md").read_bytes())
        original_section = contract.render_record(self.records[0][0], self.records[0][1]).encode()
        self.assertIn(original_section, (self.output / "hegel/main.md").read_bytes())
        self.assertIn(b"Untouched invented prose.  \n", (self.output / "hegel/main.md").read_bytes())

    def test_copies_assets_but_not_original_audits_pdf_or_personal_data(self):
        assets = self.baseline / "assets" / "source"
        assets.mkdir(parents=True)
        (assets / "formula.png").write_bytes(b"Invented asset bytes")
        (self.baseline / "private.pdf").write_bytes(b"Excluded invented PDF")
        (self.baseline / "private.sqlite3").write_bytes(b"Excluded invented DB")
        (self.baseline / "audit").mkdir()
        (self.baseline / "audit/source-spans.json").write_text("{}")
        self.run_ingestion()
        self.assertEqual((self.output / "assets/source/formula.png").read_bytes(), b"Invented asset bytes")
        self.assertFalse((self.output / "private.pdf").exists())
        self.assertFalse((self.output / "private.sqlite3").exists())
        self.assertFalse((self.output / "audit/source-spans.json").exists())
        audit = json.loads((self.output / "audit/review-ingestion.json").read_text())
        self.assertEqual(audit["review_sha256"], self.digest(self.review_path))
        self.assertEqual(audit["reviewer_status"], "caller_declared_not_authenticated")
        self.assertEqual(audit["counts"]["changed_records"], 1)
        self.assertNotIn("markdown", audit["changes"][0])

    def test_generated_directories_and_files_are_private(self):
        self.run_ingestion()
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        for path in self.output.rglob("*"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)

    def test_unknown_record_id_is_not_allocated_or_inferred(self):
        self.review["changes"][0]["record_id"] = contract.new_id()
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "unknown canonical record"):
            self.run_ingestion()
        self.assertFalse(self.output.exists())
        self.assert_baseline_unchanged()

    def test_metadata_or_unrecognized_review_fields_are_rejected(self):
        self.review["changes"][0]["parent_id"] = self.other_id
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "requires record_id"):
            self.run_ingestion()
        self.assertFalse(self.output.exists())

    def test_unknown_or_repeated_selector_is_rejected(self):
        for selectors in (["/kids/missing"], ["/kids/0", "/kids/0"]):
            with self.subTest(selectors=selectors):
                self.review["changes"][0]["selectors"] = selectors
                self.write_review()
                with self.assertRaises(contract.CorpusError):
                    self.run_ingestion()
                self.assertFalse(self.output.exists())

    def test_duplicate_change_is_rejected(self):
        self.review["changes"].append(copy.deepcopy(self.review["changes"][0]))
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "one approved change"):
            self.run_ingestion()

    def test_exclusion_must_be_reasoned_and_cannot_duplicate_assignment(self):
        for exclusion in ({"selector": "/kids/1", "reason": " "},
                          {"selector": "/kids/0", "reason": "Cannot exclude mapped evidence"}):
            with self.subTest(exclusion=exclusion):
                self.review["exclusions"] = [exclusion]
                self.write_review()
                with self.assertRaises(contract.CorpusError):
                    self.run_ingestion()

    def test_every_extracted_element_requires_a_disposition(self):
        self.review["exclusions"] = []
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "lack an explicit mapping"):
            self.run_ingestion()

    def test_review_cannot_map_evidence_from_another_pdf_page(self):
        self.review["changes"][0]["selectors"] = ["/kids/1"]
        self.review["exclusions"][0]["selector"] = "/kids/0"
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "PDF page is not among"):
            self.run_ingestion()

    def test_source_fingerprint_or_page_count_mismatch_is_rejected(self):
        for source in ({**self.result["source"], "sha256": "1" * 64},
                       {**self.result["source"], "pdf_pages": 3}):
            with self.subTest(source=source):
                self.result["source"] = source
                if source["pdf_pages"] == 3:
                    self.result["document"]["number of pages"] = 3
                self.write_candidate()
                self.review["artifact_sha256"] = self.digest(self.candidate_path)
                self.write_review()
                with self.assertRaisesRegex(contract.CorpusError, "baseline's exact source"):
                    self.run_ingestion()

    def test_stale_review_artifact_digest_is_rejected(self):
        self.review["artifact_sha256"] = "f" * 64
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "fingerprint does not match"):
            self.run_ingestion()

    def test_duplicate_json_keys_and_nonfinite_review_numbers_are_rejected(self):
        for raw in ('{"review_version":1,"review_version":1}', '{"x":NaN}'):
            with self.subTest(raw=raw):
                self.review_path.write_text(raw)
                with self.assertRaises(contract.CorpusError):
                    self.run_ingestion()

    def test_regular_reader_refuses_a_replaced_path_even_with_identical_bytes(self):
        original = os.fstat
        calls = 0
        def replaced(descriptor):
            nonlocal calls
            result = original(descriptor)
            calls += 1
            if calls == 2:
                displaced = self.root / "displaced-review.json"
                self.review_path.rename(displaced)
                self.review_path.write_bytes(displaced.read_bytes())
            return result
        with patch.object(ingest.os, "fstat", side_effect=replaced):
            with self.assertRaisesRegex(contract.CorpusError, "File changed while reading"):
                ingest._regular_bytes(self.review_path)

    def test_note_annotation_cannot_introduce_an_unregistered_identity(self):
        unknown = contract.new_id()
        self.review["changes"][0]["markdown"] = f'<sup data-sol-note="{unknown}">[x](#{unknown})</sup>'
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "absent from note_ids"):
            self.run_ingestion()

    def test_existing_visible_note_callout_cannot_be_dropped_with_frozen_metadata(self):
        self.review["changes"][0]["markdown"] = "An otherwise approved replacement without the callout."
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "retain the existing annotated note"):
            self.run_ingestion()
        self.assertFalse(self.output.exists())

    def test_visible_callout_cannot_retarget_its_file_with_the_same_note_uuid(self):
        self.review["changes"][0]["markdown"] = (
            f'Approved invented prose. <sup data-sol-note="{self.note_id}">'
            f'[a](../nonexistent-notes.md#{self.note_id})</sup>')
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "retain the existing annotated note link destinations"):
            self.run_ingestion()
        self.assertFalse(self.output.exists())

    def test_raw_html_note_anchor_destination_is_also_preserved(self):
        # The existing contract requires a matching CommonMark link; a raw HTML
        # anchor can coexist with it and must not escape destination preservation.
        original = self.baseline / "hegel/main.md"
        href = f"../notes/main.md#{self.note_id}"
        raw_callout = (f'<sup data-sol-note="{self.note_id}">[a]({href}) '
                       f'<a href="{href}">HTML note link</a></sup>')
        original.write_text(original.read_text().replace(self.callout, raw_callout))
        contract.reindex(self.baseline)
        self.review["changes"][0]["markdown"] = (
            "Approved invented prose. " + raw_callout.replace(
                f'<a href="{href}">', f'<a href="../wrong-file.md#{self.note_id}">'))
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "retain the existing annotated note link destinations"):
            self.run_ingestion()
        self.assertFalse(self.output.exists())
        self.review["changes"][0]["markdown"] = "Approved invented prose. " + raw_callout
        self.write_review()
        self.run_ingestion()
        self.assertIn(raw_callout, contract.load_snapshot(self.output).records[1]["markdown"])

    def test_section_replacement_requires_a_heading_and_no_nested_record_markers(self):
        self.review["changes"][0]["record_id"] = self.section_id
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "ATX heading"):
            self.run_ingestion()
        self.review["changes"][0]["record_id"] = self.paragraph_id
        self.review["changes"][0]["markdown"] = "Unapproved nested marker.\n<!-- /sol -->"
        self.write_review()
        with self.assertRaisesRegex(contract.CorpusError, "nested SOL record"):
            self.run_ingestion()

    def test_missing_explicit_corpus_identity_is_not_initialized_implicitly(self):
        del self.manifest["corpus_id"]
        self.write_manifest()
        contract.reindex(self.baseline)
        with self.assertRaisesRegex(contract.CorpusError, "explicitly initialized corpus ID"):
            self.run_ingestion()

    def test_existing_output_and_dangling_symlinks_are_not_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("Keep")
        with self.assertRaisesRegex(contract.CorpusError, "already exists"):
            self.run_ingestion()
        self.assertEqual(sentinel.read_text(), "Keep")
        sentinel.unlink()
        self.output.rmdir()
        self.output.symlink_to(self.root / "missing", target_is_directory=True)
        with self.assertRaisesRegex(contract.CorpusError, "Symbolic-link"):
            self.run_ingestion()
        self.assertTrue(self.output.is_symlink())

    def test_destination_created_at_publication_is_preserved(self):
        original = ingest._publish_directory_noreplace
        def racing(stage, target):
            target.mkdir()
            (target / "keep.txt").write_text("Concurrent owner's file")
            return original(stage, target)
        with patch.object(ingest, "_publish_directory_noreplace", side_effect=racing):
            with self.assertRaisesRegex(contract.CorpusError, "already exists"):
                self.run_ingestion()
        self.assertEqual((self.output / "keep.txt").read_text(), "Concurrent owner's file")
        self.assertFalse((self.output / "corpus.json").exists())
        self.assertEqual(list(self.root.glob("reviewed.building-*")), [])

    def test_assets_changed_during_reindex_are_not_published(self):
        assets = self.baseline / "assets"
        assets.mkdir()
        asset = assets / "formula.png"
        asset.write_bytes(b"Original invented asset")
        original = contract.reindex
        def altered(stage):
            result = original(stage)
            asset.write_bytes(b"Changed invented asset")
            return result
        with patch.object(ingest.contract, "reindex", side_effect=altered):
            with self.assertRaisesRegex(contract.CorpusError, "Baseline asset changed"):
                self.run_ingestion()
        self.assertFalse(self.output.exists())

    def test_assets_added_during_reindex_are_not_silently_omitted(self):
        assets = self.baseline / "assets"
        assets.mkdir()
        original = contract.reindex
        def added(stage):
            result = original(stage)
            (assets / "new-formula.png").write_bytes(b"New invented asset")
            return result
        with patch.object(ingest.contract, "reindex", side_effect=added):
            with self.assertRaisesRegex(contract.CorpusError, "Baseline asset inventory changed"):
                self.run_ingestion()
        self.assertFalse(self.output.exists())

    def test_symlink_parent_readonly_sources_and_baseline_nested_output_are_refused(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        sources = self.root / "sources"
        sources.mkdir()
        for target in (alias / "new", sources / "new", self.baseline / "new"):
            with self.subTest(target=target):
                self.output = target
                with self.assertRaises(contract.CorpusError):
                    self.run_ingestion()
                self.assertFalse(target.exists())

    def test_parent_traversal_cannot_hide_baseline_or_sources_destinations(self):
        outside = self.root / "outside"
        outside.mkdir()
        for target in (outside / ".." / "baseline" / "new", outside / ".." / "sources" / "new"):
            with self.subTest(target=target):
                self.output = target
                with self.assertRaisesRegex(contract.CorpusError, "parent traversal"):
                    self.run_ingestion()
                self.assertFalse(target.exists())
                self.assertEqual(list(self.baseline.glob("*.building-*")), [])
                self.assert_baseline_unchanged()

    def test_unsafe_document_paths_fail_before_publication(self):
        self.manifest["documents"] = ["../outside.md"]
        self.write_manifest()
        with self.assertRaisesRegex(contract.CorpusError, "Unsafe corpus path"):
            self.run_ingestion()
        self.assertFalse(self.output.exists())

    def test_asset_symlinks_and_personal_files_are_not_copied(self):
        assets = self.baseline / "assets"
        assets.mkdir()
        asset = assets / "linked.png"
        asset.symlink_to(self.review_path)
        with self.assertRaisesRegex(contract.CorpusError, "symbolic link"):
            self.run_ingestion()
        asset.unlink()
        (assets / "private.sqlite3").write_bytes(b"Not an asset")
        with self.assertRaisesRegex(contract.CorpusError, "not corpus assets"):
            self.run_ingestion()

    def test_inputs_changed_during_reindex_are_not_published(self):
        original = contract.reindex
        for target in (self.candidate_path, self.review_path):
            with self.subTest(target=target):
                self.write_candidate()
                self.review["artifact_sha256"] = self.digest(self.candidate_path)
                self.write_review()
                def altered(stage):
                    result = original(stage)
                    target.write_bytes(target.read_bytes() + b"\n")
                    return result
                with patch.object(ingest.contract, "reindex", side_effect=altered):
                    with self.assertRaisesRegex(contract.CorpusError, "changed during ingestion"):
                        self.run_ingestion()
                self.assertFalse(self.output.exists())
                self.assertEqual(list(self.root.glob("reviewed.building-*")), [])

    def test_baseline_change_during_reindex_is_not_published(self):
        original = contract.reindex
        def altered(stage):
            result = original(stage)
            path = self.baseline / "hegel/main.md"
            path.write_bytes(path.read_bytes() + b"\n")
            return result
        with patch.object(ingest.contract, "reindex", side_effect=altered):
            with self.assertRaisesRegex(contract.CorpusError, "Canonical Markdown changed"):
                self.run_ingestion()
        self.assertFalse(self.output.exists())

    def test_missing_markdown_parser_is_not_silently_bypassed(self):
        with patch.object(contract, "_commonmark_tokens", side_effect=contract.CorpusError("markdown-it-py missing")):
            with self.assertRaisesRegex(contract.CorpusError, "markdown-it-py missing"):
                self.run_ingestion()
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(shutil.which("git"), "Git is unavailable")
    def test_git_destination_requires_whole_private_outputs_and_staging_to_be_ignored(self):
        repository = self.root / "repository"
        repository.mkdir()
        subprocess.run(["git", "init", "--quiet", str(repository)], check=True,
                       capture_output=True)
        self.output = repository / "local-corpus"
        ignore = repository / ".gitignore"
        ignore.write_text("local-corpus/corpus.json\n")
        with self.assertRaisesRegex(contract.CorpusError, "Git-ignored"):
            self.run_ingestion()
        ignore.write_text("local-corpus/\n")
        with self.assertRaisesRegex(contract.CorpusError, "Git-ignored"):
            self.run_ingestion()
        ignore.write_text("local-corpus/\nlocal-corpus.building-*/\n")
        self.run_ingestion()
        self.assertTrue(self.output.is_dir())


@unittest.skipUnless(sys.platform == "linux", "Atomic prototype currently targets Linux")
class DirectoryPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-publish-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stage = self.root / "stage"
        self.stage.mkdir()
        (self.stage / "complete.txt").write_text("Complete staging")
        self.target = self.root / "target"

    def test_complete_directory_is_atomically_moved_to_new_name(self):
        ingest._publish_directory_noreplace(self.stage, self.target)
        self.assertFalse(self.stage.exists())
        self.assertEqual((self.target / "complete.txt").read_text(), "Complete staging")

    def test_racing_empty_destination_is_not_replaced(self):
        self.target.mkdir()
        original_inode = self.target.stat().st_ino
        with self.assertRaisesRegex(contract.CorpusError, "already exists"):
            ingest._publish_directory_noreplace(self.stage, self.target)
        self.assertEqual(self.target.stat().st_ino, original_inode)
        self.assertTrue(self.stage.is_dir())
        self.assertEqual(list(self.target.iterdir()), [])

    def test_racing_symlink_destination_is_not_replaced(self):
        self.target.symlink_to(self.root / "missing", target_is_directory=True)
        with self.assertRaisesRegex(contract.CorpusError, "Symbolic-link"):
            ingest._publish_directory_noreplace(self.stage, self.target)
        self.assertTrue(self.target.is_symlink())
        self.assertTrue(self.stage.is_dir())

    def test_unsupported_platform_and_unavailable_primitive_fail_closed(self):
        with patch.object(ingest.sys, "platform", "other"):
            with self.assertRaisesRegex(contract.CorpusError, "requires Linux"):
                ingest._publish_directory_noreplace(self.stage, self.target)
        with patch.object(ingest.ctypes, "CDLL", side_effect=AttributeError("renameat2 unavailable")):
            with self.assertRaisesRegex(contract.CorpusError, "unavailable"):
                ingest._publish_directory_noreplace(self.stage, self.target)
        self.assertFalse(self.target.exists())
        self.assertTrue(self.stage.exists())


if __name__ == "__main__":
    unittest.main()
