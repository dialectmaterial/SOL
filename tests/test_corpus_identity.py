"""Corpus lineage and verified snapshots using wholly synthetic book records."""

from __future__ import annotations

import builtins
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import sol_corpus_contract as contract


class CorpusIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "corpus"
        self.root.mkdir()
        section_id, paragraph_id = contract.new_id(), contract.new_id()
        base = {
            "sources": [{"pdf_page": 1, "printed_page": "1"}],
            "attribution": {"author": "Synthetic writer", "status": "known", "role": "main_text"},
        }
        section = {**base, "id": section_id, "type": "section", "parent_id": None,
                   "order": 0, "title": "Synthetic heading", "path": "/sample"}
        paragraph = {**base, "id": paragraph_id, "type": "paragraph",
                     "parent_id": section_id, "order": 1}
        pairs = [(section, "# Synthetic heading", "Synthetic heading"),
                 (paragraph, "A *synthetic* passage.", "A synthetic passage.")]
        self.manifest = {
            "contract_version": 1,
            "edition": {"title": "Synthetic edition", "translator": "Synthetic translator"},
            "source": {"filename": "absent.pdf", "sha256": "0" * 64, "pdf_pages": 1},
            "documents": ["sample.md"],
            "page_inventory": [{"pdf_page": 1, "printed_page": "1", "disposition": "records"}],
        }
        self.records = []
        for metadata, markdown, plain_text in pairs:
            self.records.append({
                **metadata, "markdown": markdown, "plain_text": plain_text,
                "document": "sample.md", "content_sha256": self.digest(markdown.encode()),
                "context": [] if metadata["parent_id"] is None else [
                    {"id": section_id, "type": "section", "title": section["title"], "path": "/sample"}
                ],
            })
        # Build a valid preexisting index without importing a Markdown parser.
        (self.root / "sample.md").write_text(
            "\n".join(contract.render_record(meta, text) for meta, text, _ in pairs), encoding="utf-8"
        )
        self.write_manifest()
        payload = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in self.records).encode()
        (self.root / "index.jsonl").write_bytes(payload)
        self.metadata = {
            "contract_version": 1,
            "manifest_sha256": self.digest((self.root / "corpus.json").read_bytes()),
            "source_sha256": self.manifest["source"]["sha256"],
            "documents": {"sample.md": self.digest((self.root / "sample.md").read_bytes())},
            "index_sha256": self.digest(payload), "record_count": len(self.records),
        }
        self.write_metadata()

    @staticmethod
    def digest(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def write_manifest(self) -> None:
        (self.root / "corpus.json").write_text(json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")

    def write_metadata(self) -> None:
        (self.root / "index.meta.json").write_text(json.dumps(self.metadata) + "\n", encoding="utf-8")

    def bytes_by_file(self) -> dict[str, bytes]:
        return {path.name: path.read_bytes() for path in self.root.iterdir() if path.is_file()}

    def test_legacy_corpus_snapshot_is_verified_and_read_only(self) -> None:
        original = self.bytes_by_file()
        snapshot = contract.load_snapshot(self.root)
        self.assertIsNone(snapshot.corpus_id)
        self.assertEqual(snapshot.manifest, self.manifest)
        self.assertEqual(snapshot.records, self.records)
        self.assertEqual(snapshot.manifest_sha256, self.metadata["manifest_sha256"])
        self.assertEqual(snapshot.index_sha256, self.metadata["index_sha256"])
        self.assertEqual(snapshot.corpus_directory, self.root.resolve())
        self.assertEqual(contract.load_index(self.root), snapshot.records)
        self.assertEqual(self.bytes_by_file(), original)

    def test_initialize_only_adds_identity_and_refreshes_manifest_digest(self) -> None:
        original = self.bytes_by_file()
        summary = contract.initialize_corpus_identity(self.root)
        self.assertTrue(summary["initialized"])
        self.assertEqual(summary["records"], 2)
        snapshot = contract.load_snapshot(self.root)
        self.assertEqual(snapshot.corpus_id, summary["corpus_id"])
        manifest_without_identity = {key: value for key, value in snapshot.manifest.items() if key != "corpus_id"}
        self.assertEqual(manifest_without_identity, self.manifest)
        self.assertEqual(snapshot.records, self.records)
        self.assertEqual((self.root / "sample.md").read_bytes(), original["sample.md"])
        self.assertEqual((self.root / "index.jsonl").read_bytes(), original["index.jsonl"])
        metadata = json.loads((self.root / "index.meta.json").read_text())
        self.assertEqual(metadata, {**self.metadata, "manifest_sha256": snapshot.manifest_sha256})
        self.assertFalse((self.root / ".sol-corpus-write.lock").exists())

    def test_initialization_is_idempotent_including_file_bytes(self) -> None:
        first = contract.initialize_corpus_identity(self.root)
        original = self.bytes_by_file()
        second = contract.initialize_corpus_identity(self.root)
        self.assertFalse(second["initialized"])
        self.assertEqual(second["corpus_id"], first["corpus_id"])
        self.assertEqual(self.bytes_by_file(), original)

    def test_copying_or_moving_corpus_preserves_lineage_identity(self) -> None:
        identifier = contract.initialize_corpus_identity(self.root)["corpus_id"]
        copied = self.root.parent / "copied"
        shutil.copytree(self.root, copied)
        self.assertEqual(contract.load_snapshot(copied).corpus_id, identifier)
        moved = self.root.parent / "moved"
        self.root.rename(moved)
        self.assertEqual(contract.load_snapshot(moved).corpus_id, identifier)

    def test_independent_imports_do_not_share_pdf_based_identity(self) -> None:
        copied = self.root.parent / "independent-import"
        shutil.copytree(self.root, copied)
        first = contract.initialize_corpus_identity(self.root)["corpus_id"]
        second = contract.initialize_corpus_identity(copied)["corpus_id"]
        self.assertNotEqual(first, second)
        self.assertEqual(contract.load_snapshot(self.root).manifest["source"],
                         contract.load_snapshot(copied).manifest["source"])

    def test_invalid_identity_values_are_rejected_without_writes(self) -> None:
        for value in (None, 17, True, "", "not-a-uuid", contract.new_id().upper()):
            with self.subTest(value=value):
                self.manifest["corpus_id"] = value
                self.write_manifest()
                original = self.bytes_by_file()
                with self.assertRaisesRegex(contract.CorpusError, "corpus_id.*UUID"):
                    contract.initialize_corpus_identity(self.root)
                self.assertEqual(self.bytes_by_file(), original)

    def test_stale_markdown_is_rejected_without_manifest_or_index_writes(self) -> None:
        with (self.root / "sample.md").open("a", encoding="utf-8") as stream:
            stream.write("\nEdited outside the index.\n")
        original = self.bytes_by_file()
        with self.assertRaisesRegex(contract.CorpusError, "Canonical Markdown.*reindex"):
            contract.initialize_corpus_identity(self.root)
        self.assertEqual(self.bytes_by_file(), original)

    def test_tampered_index_is_rejected_without_writes(self) -> None:
        with (self.root / "index.jsonl").open("a", encoding="utf-8") as stream:
            stream.write("{}\n")
        original = self.bytes_by_file()
        with self.assertRaisesRegex(contract.CorpusError, "Generated index was changed"):
            contract.initialize_corpus_identity(self.root)
        self.assertEqual(self.bytes_by_file(), original)

    def test_malformed_index_metadata_and_manifest_are_rejected(self) -> None:
        for filename in ("corpus.json", "index.meta.json"):
            with self.subTest(filename=filename):
                original = (self.root / filename).read_bytes()
                (self.root / filename).write_text('{"duplicate": 1, "duplicate": 2}')
                before = self.bytes_by_file()
                with self.assertRaisesRegex(contract.CorpusError, "Duplicate JSON key"):
                    contract.initialize_corpus_identity(self.root)
                self.assertEqual(self.bytes_by_file(), before)
                (self.root / filename).write_bytes(original)

    def test_verified_load_and_initialization_need_no_markdown_dependency(self) -> None:
        original_import = builtins.__import__

        def standard_library_only(name, *args, **kwargs):
            if name.startswith(("markdown_it", "fitz", "pypdf", "pdfplumber")):
                raise AssertionError(f"Unexpected dependency or PDF parser: {name}")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=standard_library_only):
            self.assertEqual(len(contract.load_snapshot(self.root).records), 2)
            summary = contract.initialize_corpus_identity(self.root)
            self.assertEqual(contract.load_snapshot(self.root).corpus_id, summary["corpus_id"])

    def test_manifest_race_is_detected_instead_of_mixing_identity_generations(self) -> None:
        original_read = contract._read_bytes
        manifest_path = self.root / "corpus.json"
        reads = 0

        def raced_read(path: Path) -> bytes:
            nonlocal reads
            data = original_read(path)
            if path == manifest_path:
                reads += 1
                if reads == 1:
                    changed = {**self.manifest, "corpus_id": contract.new_id()}
                    manifest_path.write_text(json.dumps(changed), encoding="utf-8")
            return data

        with patch.object(contract, "_read_bytes", side_effect=raced_read):
            with self.assertRaisesRegex(contract.CorpusError, "manifest changed while"):
                contract.load_snapshot(self.root)

    def test_edit_after_initial_validation_is_detected_without_overwriting_it(self) -> None:
        original_load = contract.load_snapshot
        original_manifest = (self.root / "corpus.json").read_bytes()

        def edited_load(*args, **kwargs):
            snapshot = original_load(*args, **kwargs)
            with (self.root / "sample.md").open("a", encoding="utf-8") as stream:
                stream.write("\nConcurrent human correction.\n")
            return snapshot

        with patch.object(contract, "load_snapshot", side_effect=edited_load):
            with self.assertRaisesRegex(contract.CorpusError, "Markdown changed while"):
                contract.initialize_corpus_identity(self.root)
        self.assertEqual((self.root / "corpus.json").read_bytes(), original_manifest)
        self.assertIn("Concurrent human correction", (self.root / "sample.md").read_text())

    def test_interrupted_commit_fails_closed_and_preserves_allocated_identity(self) -> None:
        original_write = contract._atomic_write

        def interrupted_write(path: Path, data: bytes) -> None:
            if path.name == "index.meta.json":
                raise contract.CorpusError("Synthetic interrupted metadata commit")
            original_write(path, data)

        original_index = (self.root / "index.jsonl").read_bytes()
        with patch.object(contract, "_atomic_write", side_effect=interrupted_write):
            with self.assertRaisesRegex(contract.CorpusError, "interrupted metadata"):
                contract.initialize_corpus_identity(self.root)
        allocated_id = contract.read_manifest(self.root)["corpus_id"]
        self.assertEqual((self.root / "index.jsonl").read_bytes(), original_index)
        with self.assertRaisesRegex(contract.CorpusError, "manifest changed; reindex"):
            contract.load_snapshot(self.root)
        contract.reindex(self.root)
        self.assertEqual(contract.load_snapshot(self.root).corpus_id, allocated_id)
        self.assertFalse(contract.initialize_corpus_identity(self.root)["initialized"])

    def test_existing_write_lock_prevents_competing_identity_or_reindex(self) -> None:
        lock = self.root / ".sol-corpus-write.lock"
        lock.write_text("pid=synthetic\n")
        before = self.bytes_by_file()
        for operation in (contract.initialize_corpus_identity, contract.reindex):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(contract.CorpusError, "Corpus write lock exists"):
                    operation(self.root)
                self.assertEqual(self.bytes_by_file(), before)

    def test_identity_initialization_does_not_replace_symlinked_metadata(self) -> None:
        manifest = self.root / "corpus.json"
        linked_target = self.root.parent / "linked-manifest.json"
        original = manifest.read_bytes()
        manifest.rename(linked_target)
        manifest.symlink_to(linked_target)
        with self.assertRaisesRegex(contract.CorpusError, "symlinked corpus metadata"):
            contract.initialize_corpus_identity(self.root)
        self.assertTrue(manifest.is_symlink())
        self.assertEqual(linked_target.read_bytes(), original)

    def test_atomic_commit_errors_are_actionable_contract_errors(self) -> None:
        with patch.object(contract.os, "replace", side_effect=OSError("Synthetic disk error")):
            with self.assertRaisesRegex(contract.CorpusError, "Cannot commit corpus write.*Synthetic disk error"):
                contract.initialize_corpus_identity(self.root)
        self.assertIsNone(contract.load_snapshot(self.root).corpus_id)
        self.assertFalse((self.root / ".sol-corpus-write.lock").exists())
        self.assertEqual(set(self.bytes_by_file()), {"corpus.json", "index.jsonl", "index.meta.json", "sample.md"})

    def test_cli_reports_initialization_then_retention(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(contract.main([str(self.root), "--initialize-identity"]), 0)
            self.assertEqual(contract.main([str(self.root), "--initialize-identity"]), 0)
        self.assertIn("Initialized corpus identity", output.getvalue())
        self.assertIn("Retained corpus identity", output.getvalue())


if __name__ == "__main__":
    unittest.main()
