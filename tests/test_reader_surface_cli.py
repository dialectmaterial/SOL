"""Checkout-only launchers remain explicit, bounded, private, and read-only."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.corpus import contract
from sol.core.corpus import load_corpus_book
from experiments.reader_surfaces.__main__ import main
from experiments.reader_surfaces.common import sample_from_book, selection_packet
from experiments.reader_surfaces.html import write_html
from fixtures_corpus import write_runtime_corpus


class ReaderSurfaceCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-surface-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        self.identifier, _ = write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.book = load_corpus_book(self.corpus)
        self.before = {p.name:p.read_bytes() for p in self.corpus.iterdir()}

    def tearDown(self):
        self.assertEqual(self.before, {p.name:p.read_bytes() for p in self.corpus.iterdir()})

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(["--corpus", str(self.corpus), *args])
        return status, out.getvalue(), err.getvalue()

    def test_inventory_reports_bounded_verified_sample_without_quotes_or_workspace(self):
        status, out, err = self.invoke("--count", "1", "inventory")
        self.assertEqual((status, err), (0, ""))
        data = json.loads(out)
        self.assertEqual(data["sample_passages"], 1)
        self.assertIsNone(data["workspace"])
        self.assertEqual(data["start"], self.identifier)
        self.assertNotIn("text", data)
        self.assertFalse(list(self.root.rglob("*.sqlite3")))

    def test_count_and_start_are_validated_without_repair(self):
        for args in (("--count", "0", "inventory"), ("--count", "65", "inventory"),
                     ("--start", "does-not-exist", "inventory")):
            with self.subTest(args=args):
                status, out, err = self.invoke(*args)
                self.assertEqual(status, 2)
                self.assertFalse(out)
                self.assertTrue(err)
        for count in (True, 0, 65, 1.5):
            with self.assertRaises(ValueError):
                sample_from_book(self.book, count=count)

    def test_html_is_private_and_existing_files_are_preserved(self):
        output = self.root / "reading.html"
        status, _, err = self.invoke("--count", "1", "html", "--output", str(output))
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        before = output.read_bytes()
        status, _, err = self.invoke("html", "--output", str(output))
        self.assertEqual(status, 2)
        self.assertIn("overwrite", err)
        self.assertEqual(before, output.read_bytes())

    def test_export_into_canonical_directory_is_refused(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            write_html(sample_from_book(self.book), self.corpus / "new.html")

    def test_validate_packet_reports_identity_but_does_not_import_or_print_selected_text(self):
        packet = self.root / "selection.json"
        packet.write_text(json.dumps(selection_packet(self.book, self.identifier, 0, 5)))
        status, out, err = self.invoke("validate", str(packet))
        self.assertEqual((status, err), (0, ""))
        data = json.loads(out)
        self.assertEqual(data["span"], [0, 5])
        self.assertFalse(data["workspace_written"])
        self.assertNotIn("text", data)

    def test_duplicate_and_oversized_packets_are_refused(self):
        packet = self.root / "selection.json"
        packet.write_text('{"reference":null,"reference":null}')
        self.assertEqual(self.invoke("validate", str(packet))[0], 2)
        packet.write_text(" " * (1024 * 1024 + 1))
        self.assertEqual(self.invoke("validate", str(packet))[0], 2)

    def test_tui_checks_terminal_before_loading_or_opening_a_view(self):
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment", side_effect=ValueError("interactive terminal required")), \
                patch("sol.core.corpus.load_corpus_book", side_effect=AssertionError("must fail before loading")):
            status, out, err = self.invoke("tui")
        self.assertEqual(status, 2)
        self.assertFalse(out)
        self.assertIn("interactive terminal", err)
