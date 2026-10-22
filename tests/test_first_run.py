"""First-run import uses invented files; never converts the private book in tests."""
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fixtures_corpus import write_runtime_corpus
from sol.core.config import configured_corpus
from sol.corpus import contract
from sol.corpus import onboarding


class FirstRunTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source with spaces.pdf"
        self.source.write_bytes(b"Invented source, not a PDF")
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.output = self.root / "data" / "sol" / "corpora" / self.digest
        for mock in (patch.dict(os.environ, XDG_DATA_HOME=str(self.root / "data"),
                                XDG_CONFIG_HOME=str(self.root / "config"),
                                XDG_CACHE_HOME=str(self.root / "cache")),
                     patch("sol.corpus.convert.AUDITED_SOURCE_SHA256", self.digest),
                     patch.object(onboarding.sys, "stdin", SimpleNamespace(isatty=lambda: True)),
                     patch.object(onboarding.sys, "stdout", StringIO()),
                     patch.object(onboarding.shutil, "which", return_value="/invented/tool")):
            mock.start(); self.addCleanup(mock.stop)
        onboarding.sys.stdout.isatty = lambda: True

    def converted_fixture(self, source, output, work):
        self.assertEqual(source, self.source)
        self.assertTrue(work.is_dir())
        write_runtime_corpus(output)
        manifest_path = output / "corpus.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["source"]["sha256"] = self.digest
        manifest_path.write_text(json.dumps(manifest))
        metadata_path = output / "index.meta.json"
        metadata = json.loads(metadata_path.read_text())
        metadata.update(source_sha256=self.digest,
                        manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())
        metadata_path.write_text(json.dumps(metadata))
        contract.initialize_corpus_identity(output)

    def test_import_validates_remembers_and_reuses_without_reconversion(self):
        with patch("builtins.input", return_value=f'"{self.source}"'), \
                patch("sol.corpus.convert.convert", side_effect=self.converted_fixture) as convert:
            first = onboarding.prepare_first_corpus()
            before = {file.name: file.read_bytes() for file in self.output.iterdir()}
            second = onboarding.prepare_first_corpus()
        convert.assert_called_once()
        self.assertEqual(configured_corpus(), self.output)
        # The verified PDF is remembered for source previews.
        sources = json.loads((self.root / "config" / "sol" / "sources.json").read_text())
        self.assertEqual(sources["sources"], {self.digest: str(self.source.resolve())})
        self.assertEqual(first.corpus_manifest["corpus_id"], second.corpus_manifest["corpus_id"])
        self.assertEqual(before, {file.name: file.read_bytes() for file in self.output.iterdir()})

    def test_failure_to_remember_the_pdf_keeps_the_finished_import(self):
        from sol.core.source import SourceError
        with patch("builtins.input", return_value=str(self.source)), \
                patch("sol.corpus.convert.convert", side_effect=self.converted_fixture), \
                patch("sol.core.source.SourceService.set_pdf", side_effect=SourceError("Invented cache failure")):
            onboarding.prepare_first_corpus()
        self.assertEqual(configured_corpus(), self.output)
        self.assertIn("sol --set-source-pdf PATH", onboarding.sys.stdout.getvalue())

    def test_unsupported_pdf_creates_no_data_or_configuration(self):
        wrong = self.root / "different.pdf"
        wrong.write_bytes(b"unsupported edition")
        with patch("builtins.input", side_effect=[str(wrong), KeyboardInterrupt]), \
                patch("sol.corpus.convert.convert", side_effect=AssertionError("No conversion")), \
                self.assertRaises(KeyboardInterrupt):
            onboarding.prepare_first_corpus()
        self.assertFalse((self.root / "data").exists())
        self.assertFalse((self.root / "config").exists())

    def test_missing_and_invalid_paths_can_be_corrected(self):
        with patch("builtins.input", side_effect=["", str(self.root / "missing.pdf"), str(self.source)]), \
                patch("sol.corpus.convert.convert", side_effect=self.converted_fixture):
            onboarding.prepare_first_corpus()
        self.assertEqual(configured_corpus(), self.output)

    def test_failure_does_not_save_a_corpus_pointer(self):
        with patch("builtins.input", return_value=str(self.source)), \
                patch("sol.corpus.convert.convert", side_effect=ValueError("Invented failed extraction")), \
                self.assertRaisesRegex(ValueError, "failed extraction"):
            onboarding.prepare_first_corpus()
        self.assertIsNone(configured_corpus())

    def test_noninteractive_input_never_prompts_or_creates_data(self):
        with patch.object(onboarding.sys, "stdin", SimpleNamespace(isatty=lambda: False)), \
                patch("builtins.input", side_effect=AssertionError("No prompt")), \
                self.assertRaisesRegex(ValueError, "interactively"):
            onboarding.prepare_first_corpus()
        self.assertFalse((self.root / "data").exists())

    def test_missing_pdf_tools_fail_before_prompt_or_writes(self):
        with patch.object(onboarding.shutil, "which", return_value=None), \
                patch("builtins.input", side_effect=AssertionError("No prompt")), \
                self.assertRaisesRegex(ValueError, "install.py"):
            onboarding.prepare_first_corpus()
        self.assertFalse((self.root / "data").exists())
