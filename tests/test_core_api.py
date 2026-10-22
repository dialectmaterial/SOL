"""The public shared-core API preserves canonical identity and stays read-only."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import sol.core as core
from fixtures_corpus import write_runtime_corpus


class PublicCoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-core-api-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        self.identifier, self.body = write_runtime_corpus(self.corpus)

    def fingerprints(self):
        return {file.relative_to(self.root): sha256(file.read_bytes()).hexdigest()
                for file in self.root.rglob("*") if file.is_file()}

    def test_public_book_reference_path_and_snapshot_agree_without_writes(self):
        before = self.fingerprints()
        snapshot = core.load_snapshot(self.corpus)
        book = core.load_corpus_book(self.corpus)
        self.assertEqual(core.API_VERSION, 1)
        self.assertIsInstance(book, core.Book)
        self.assertIsInstance(book.root, core.Node)
        self.assertIsInstance(book.passages[0], core.Passage)
        self.assertIsInstance(snapshot, core.CorpusSnapshot)
        passage = book.find_passage(self.identifier)
        reference = core.resolve_reference(book, self.identifier)
        self.assertIsInstance(reference, core.Reference)
        self.assertEqual(reference.requested_id, self.identifier)
        self.assertEqual(reference.record["plain_text"], self.body)
        self.assertEqual(reference.record["markdown"], self.body)
        self.assertEqual(reference.record["sources"], snapshot.records[1]["sources"])
        node, path = core.resolve_path("/being/synthetic", (), book.root)
        self.assertIs(node, passage.node)
        self.assertEqual(path, passage.path)
        self.assertEqual(core.display_path(path), "/BEING/synthetic.txt")
        self.assertEqual(book.search("invented", limit=1), [passage])
        self.assertEqual(core.node_path(node), path)
        core.verify_snapshot_current(snapshot)
        self.assertEqual(self.fingerprints(), before)

    def test_explicit_generation_guard_refuses_changed_canonical_files(self):
        snapshot = core.load_snapshot(self.corpus)
        markdown = self.corpus / "sample.md"
        markdown.write_text(markdown.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(core.CorpusError):
            core.verify_snapshot_current(snapshot)
        with self.assertRaisesRegex(ValueError, "rebuild the index"):
            core.load_corpus_book(self.corpus)

    def test_missing_corpus_is_never_created_or_replaced_by_pdf_extraction(self):
        missing = self.root / "absent"
        with self.assertRaisesRegex(ValueError, "corpus.json not found"):
            core.load_corpus_book(missing)
        self.assertFalse(missing.exists())

    def test_lazy_facade_identity_exports_and_unknown_names(self):
        from sol.core import models, references
        from sol.corpus import contract

        self.assertIs(core.Node, models.Node)
        self.assertIs(core.Reference, references.Reference)
        self.assertIs(core.load_snapshot, contract.load_snapshot)
        self.assertIs(core.CorpusError, contract.CorpusError)
        self.assertEqual(len(core.__all__), len(set(core.__all__)))
        for name in core.__all__:
            with self.subTest(name=name):
                self.assertIn(name, dir(core))
                self.assertTrue(hasattr(core, name))
        with self.assertRaises(AttributeError):
            core.not_a_sol_api

    def test_fresh_public_import_and_model_request_do_no_io_or_optional_import(self):
        script = """
import builtins, pathlib, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(('sol.reader', 'sol.being.workspace', 'sol.terminal',
                        'markdown_it', 'prompt_toolkit', 'textual', 'rich')):
        raise AssertionError('Shared API imported an interface: ' + name)
    return original(name, *args, **kwargs)
def no_file_io(*args, **kwargs):
    raise AssertionError('An API import must not read or create application data')
builtins.__import__ = guarded
pathlib.Path.read_text = no_file_io
pathlib.Path.read_bytes = no_file_io
pathlib.Path.mkdir = no_file_io
import sol.core as core
assert core.API_VERSION == 1
assert 'sol.core.corpus' not in sys.modules
assert 'sol.corpus.contract' not in sys.modules
from sol.core import Node, resolve_reference, discover_corpus
assert 'sol.core.corpus' not in sys.modules
assert 'sol.corpus.contract' not in sys.modules
assert Node('', 'Invented root', 1).title == 'Invented root'
"""
        checkout = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=checkout,
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
