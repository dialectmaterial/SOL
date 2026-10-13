"""Invented physical evidence; canonical text and identities are never guessed."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.corpus import extraction


def node(kind="paragraph", page=2, **extra):
    return {"type": kind, "id": 17, "page number": page,
            "bounding box": [-2, 20, 100, 90], **extra}


def result():
    return {
        "source": {"filename": "invented.pdf", "sha256": "a" * 64, "pdf_pages": 6},
        "backend": {"name": "opendataloader", "version": "2.5.13", "options": {"pages": "2"}},
        "document": {"file name": "invented.pdf", "number of pages": 6,
                     "author": "PDF metadata, not passage attribution", "title": None,
                     "creation date": None, "modification date": None,
                     "kids": [node(content="Invented *text*\nline-wrap-\ncontinuation α.",
                                   font="SyntheticItalic", **{"font size": 12})]},
    }


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-artifacts-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "private" / "candidate.json"
        self.evidence = result()

    def test_content_typography_source_page_and_backend_ids_are_not_interpreted(self):
        artifact = extraction.make_artifact(self.evidence)
        self.assertEqual(artifact["raw_document"], self.evidence["document"])
        self.assertEqual(artifact["elements"][0]["content"], self.evidence["document"]["kids"][0]["content"])
        self.assertEqual(artifact["elements"][0]["pdf_page"], 2)
        self.assertEqual(artifact["source"]["pdf_pages"], 6)
        self.assertEqual(artifact["elements"][0]["backend_id"], 17)
        self.assertFalse(artifact["normalization"]["metadata_author_is_attribution"])
        self.assertTrue(artifact["normalization"]["semantic_review_required"])
        for key in ("id", "parent_id", "attribution", "printed_page", "markdown"):
            self.assertNotIn(key, artifact["elements"][0])
        self.assertEqual(artifact, extraction.make_artifact(self.evidence))
        artifact["raw_document"]["kids"][0]["content"] = "Do not mutate the input."
        self.assertNotEqual(artifact["raw_document"], self.evidence["document"])

    def test_native_coordinates_are_kept_unconverted_including_crop_negatives(self):
        box = extraction.make_artifact(self.evidence)["elements"][0]["bounding_box"]
        self.assertEqual(box["values"], [-2, 20, 100, 90])
        self.assertEqual(box["coordinate_space"], "opendataloader_pdf_points_bottom_left_unverified")

    def test_nested_lists_tables_headers_and_opaque_images_have_distinct_selectors(self):
        self.evidence["document"]["kids"] = [
            node("list", **{"list items": [node("list item", kids=[node(content="Invented list text")])]}),
            node("table", rows=[{"type": "table row", "row number": 1,
                                 "cells": [node("table cell", kids=[node(content="Invented cell")])]}]),
            node("header", kids=[node(content="Invented header")]),
            node("image", source="https://invalid.example/never-fetch.png"),
        ]
        artifact = extraction.make_artifact(self.evidence)
        self.assertEqual([element["selector"] for element in artifact["elements"]], [
            "/kids/0", "/kids/0/list items/0", "/kids/0/list items/0/kids/0",
            "/kids/1", "/kids/1/rows/0/cells/0", "/kids/1/rows/0/cells/0/kids/0",
            "/kids/2", "/kids/2/kids/0", "/kids/3",
        ])
        self.assertIsNone(artifact["elements"][-1]["content"])
        self.assertEqual(artifact["raw_document"]["kids"][-1]["source"], "https://invalid.example/never-fetch.png")

    def test_structural_row_exemption_cannot_hide_physical_content(self):
        invalid = [node("table row", content="Must not disappear"),
                   node("table", rows=[{"type": "table row", "cells": []}]),
                   node("table", rows=[{"type": "table row", "row number": True, "cells": []}]),
                   node("table", rows=[{"type": "table row", "row number": 1, "cells": [],
                                        "content": "Must not disappear"}])]
        for physical in invalid:
            with self.subTest(physical=physical):
                self.evidence["document"]["kids"] = [physical]
                with self.assertRaises(extraction.ExtractionError):
                    extraction.make_artifact(self.evidence)

    def test_unencodable_strings_and_unbounded_coordinates_fail_cleanly(self):
        for change in ({"content": "\ud800"}, {"bounding box": [0, 0, 10 ** 500, 10]}):
            with self.subTest(change=repr(change)):
                self.evidence = result()
                self.evidence["document"]["kids"][0].update(change)
                with self.assertRaises(extraction.ExtractionError):
                    extraction.make_artifact(self.evidence)

    def test_blank_or_selected_pages_can_have_no_elements(self):
        self.evidence["document"]["kids"] = []
        self.assertEqual(extraction.make_artifact(self.evidence)["elements"], [])

    def test_invalid_pages_boxes_content_and_children_are_rejected(self):
        changes = [
            {"page number": value} for value in (0, True, 7, "2")
        ] + [{"bounding box": value} for value in ([1, 2, 0, 4], [1, 2, 3], [1, False, 3, 4],
                                                    [1, float("inf"), 3, 4])] + [
            {"type": ""}, {"id": True}, {"content": ["not a string"]}, {"kids": {}},
        ]
        for change in changes:
            with self.subTest(change=change):
                evidence = copy.deepcopy(self.evidence)
                evidence["document"]["kids"][0].update(change)
                with self.assertRaises(extraction.ExtractionError):
                    extraction.make_artifact(evidence)

    def test_root_provenance_must_match_document_and_be_json(self):
        for field, value in (("filename", "../invented.pdf"), ("sha256", "A" * 64), ("pdf_pages", True),
                             ("pdf_pages", 1)):
            with self.subTest(field=field, value=value):
                evidence = copy.deepcopy(self.evidence)
                evidence["source"][field] = value
                with self.assertRaises(extraction.ExtractionError):
                    extraction.make_artifact(evidence)
        for change in ({"author": []}, {"kids": {}}, {"title": float("nan")}, {"file name": "other.pdf"}):
            with self.subTest(change=change):
                evidence = copy.deepcopy(self.evidence)
                evidence["document"].update(change)
                with self.assertRaises(extraction.ExtractionError):
                    extraction.make_artifact(evidence)

    def test_private_writer_is_deterministic_and_round_trips_exact_file_digest(self):
        artifact = extraction.make_artifact(self.evidence)
        digest = extraction.write_artifact(artifact, self.output)
        restored, actual = extraction.read_artifact(self.output)
        self.assertEqual(restored, artifact)
        self.assertEqual(digest, actual)
        self.assertEqual(actual, hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.output.parent.stat().st_mode), 0o700)
        other = self.root / "second.json"
        extraction.write_artifact(artifact, other)
        self.assertEqual(self.output.read_bytes(), other.read_bytes())
        self.assertEqual(list(self.output.parent.glob("*.building-*")), [])

    def test_read_rejects_tampered_derived_elements_and_metadata(self):
        artifact = extraction.make_artifact(self.evidence)
        for mutate in (lambda value: value["elements"][0].update(pdf_page=3),
                       lambda value: value["elements"][0].update(backend_id=True),
                       lambda value: value["normalization"].update(semantic_review_required=False),
                       lambda value: value.update(extra="not a supported field")):
            value = copy.deepcopy(artifact)
            mutate(value)
            source = self.root / "tampered.json"
            source.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(extraction.ExtractionError):
                extraction.read_artifact(source)

    def test_strict_json_rejects_duplicates_nonfinite_numbers_and_overflow(self):
        for text in ('{"artifact_version":1,"artifact_version":1}', '{"x":NaN}',
                     '{"x":Infinity}', '{"x":1e999}'):
            with self.subTest(text=text):
                source = self.root / "invalid.json"
                source.write_text(text, encoding="utf-8")
                with self.assertRaises(extraction.ExtractionError):
                    extraction.read_artifact(source)

    def test_existing_destination_and_symlink_paths_cannot_be_overwritten(self):
        artifact = extraction.make_artifact(self.evidence)
        existing = self.root / "existing.json"
        existing.write_bytes(b"preserve existing file")
        link = self.root / "link.json"
        link.symlink_to(self.root / "missing.json")
        parent = self.root / "linked-directory"
        parent.symlink_to(self.root, target_is_directory=True)
        for target in (existing, link, parent / "candidate.json", self.root / "sources" / "candidate.json",
                       self.root / "sources" / ".." / "candidate.json"):
            with self.subTest(target=target), self.assertRaises(extraction.ExtractionError):
                extraction.write_artifact(artifact, target)
        self.assertEqual(existing.read_bytes(), b"preserve existing file")
        self.assertFalse((self.root / "missing.json").exists())

    def test_concurrent_destination_wins_and_is_never_overwritten(self):
        real_link = os.link

        def competing_link(source, target, **kwargs):
            Path(target).write_bytes(b"concurrent writer")
            return real_link(source, target, **kwargs)

        with patch.object(extraction.os, "link", side_effect=competing_link), self.assertRaises(extraction.ExtractionError):
            extraction.write_artifact(extraction.make_artifact(self.evidence), self.output)
        self.assertEqual(self.output.read_bytes(), b"concurrent writer")
        self.assertFalse(list(self.output.parent.glob("*.building-*")))

    def test_git_outputs_and_temporary_files_must_be_ignored(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        (self.root / ".gitignore").write_text("private/\n", encoding="utf-8")
        artifact = extraction.make_artifact(self.evidence)
        extraction.write_artifact(artifact, self.output)
        with self.assertRaisesRegex(extraction.ExtractionError, "Git-ignored"):
            extraction.write_artifact(artifact, self.root / "public.json")
        self.assertFalse((self.root / "public.json").exists())

    def test_normalizer_hashes_pdf_but_labels_external_provenance_as_declared(self):
        pdf = self.root / "invented.pdf"
        pdf.write_bytes(b"%PDF-1.4\nInvented test bytes, not a real edition.\n")
        raw = self.root / "raw.json"
        raw.write_text(json.dumps(self.evidence["document"]), encoding="utf-8")
        summary = extraction.normalize_candidate(raw, pdf, self.output, backend_version="2.5.13")
        artifact, digest = extraction.read_artifact(self.output)
        self.assertEqual(summary["artifact_sha256"], digest)
        self.assertEqual(artifact["source"]["sha256"], hashlib.sha256(pdf.read_bytes()).hexdigest())
        self.assertEqual(artifact["backend"]["origin"], "external_json_declared")
        self.assertEqual(artifact["backend"]["options"], {})
        self.assertEqual(artifact["backend"]["raw_input_sha256"], hashlib.sha256(raw.read_bytes()).hexdigest())

    def test_normalization_requires_no_sdk_import_or_java_process(self):
        pdf = self.root / "invented.pdf"
        pdf.write_bytes(b"%PDF-1.4\nInvented bytes\n")
        raw = self.root / "raw.json"
        raw.write_text(json.dumps(self.evidence["document"]), encoding="utf-8")
        program = """
import builtins, subprocess, sys
original = builtins.__import__
def guard(name, *args, **kwargs):
    if name.split('.')[0] == 'opendataloader_pdf':
        raise AssertionError('SDK must remain optional')
    return original(name, *args, **kwargs)
builtins.__import__ = guard
subprocess.run = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('No Java or engine process'))
from sol.corpus.extraction import normalize_candidate
normalize_candidate(sys.argv[1], sys.argv[2], sys.argv[3], backend_version='2.5.13')
"""
        completed = subprocess.run([sys.executable, "-B", "-c", program, str(raw), str(pdf), str(self.output)],
                                   text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_extraction_is_lazy_and_wraps_backend_errors(self):
        from sol.corpus.backends import opendataloader
        with patch.object(opendataloader, "extract_pdf", side_effect=opendataloader.ExtractionError("No SDK")), \
                self.assertRaisesRegex(extraction.ExtractionError, "No SDK"):
            extraction.extract_candidate(self.root / "invented.pdf", self.output)
        self.assertFalse(self.output.exists())
        with patch.object(opendataloader, "extract_pdf", return_value=copy.deepcopy(self.evidence)) as engine:
            summary = extraction.extract_candidate(self.root / "invented.pdf", self.output, pages="2")
        self.assertEqual(engine.call_args.kwargs, {"pages": "2"})
        self.assertEqual(summary["backend"]["origin"], "sol_local_execution")
        self.assertEqual(summary["status"], "unreviewed_candidate")

    def test_unsafe_destination_is_rejected_before_engine_execution(self):
        from sol.corpus.backends import opendataloader
        target = self.root / "sources" / "candidate.json"
        with patch.object(opendataloader, "extract_pdf") as engine, self.assertRaises(extraction.ExtractionError):
            extraction.extract_candidate(self.root / "invented.pdf", target)
        engine.assert_not_called()

    def test_symlinked_source_parent_is_rejected_before_engine_execution(self):
        from sol.corpus.backends import opendataloader
        parent = self.root / "source-link"
        parent.symlink_to(self.root, target_is_directory=True)
        with patch.object(opendataloader, "extract_pdf") as engine, self.assertRaises(extraction.ExtractionError):
            extraction.extract_candidate(parent / "invented.pdf", self.output)
        engine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
