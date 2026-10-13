"""Explicit extraction commands are optional and never replace normal reading."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.corpus import convert


class ExtractionCommandTests(unittest.TestCase):
    def run_command(self, arguments):
        output = StringIO()
        with redirect_stdout(output):
            convert.main(arguments)
        return json.loads(output.getvalue())

    def test_extract_dispatches_only_explicit_paths_and_page_ranges(self):
        with patch("sol.corpus.extraction.extract_candidate", return_value={"status": "candidate"}) as operation:
            result = self.run_command(["extract", "--pdf", "source with spaces.pdf", "--output",
                                       ".sol-extractions/candidate.json", "--pages", "80,282-283"])
        operation.assert_called_once_with(Path("source with spaces.pdf"),
                                          Path(".sol-extractions/candidate.json"), pages="80,282-283")
        self.assertEqual(result, {"status": "candidate"})

    def test_extract_without_page_ranges_passes_none(self):
        with patch("sol.corpus.extraction.extract_candidate", return_value={}) as operation:
            self.run_command(["extract", "--pdf", "source.pdf", "--output", "candidate.json"])
        operation.assert_called_once_with(Path("source.pdf"), Path("candidate.json"), pages=None)

    def test_normalize_requires_an_explicit_external_backend_version(self):
        with patch("sol.corpus.extraction.normalize_candidate", return_value={"status": "unreviewed"}) as operation:
            result = self.run_command(["normalize", "--json", "external.json", "--pdf", "source.pdf",
                                       "--output", "candidate.json", "--backend-version", "2.5.13"])
        operation.assert_called_once_with(Path("external.json"), Path("source.pdf"), Path("candidate.json"),
                                          backend_version="2.5.13")
        self.assertEqual(result, {"status": "unreviewed"})

    def test_actual_normalization_cli_keeps_external_provenance_and_sdk_unused(self):
        with tempfile.TemporaryDirectory(prefix="sol-normalize-cli-") as temporary:
            root = Path(temporary)
            # An explicit fixture repository exercises privacy checks and also
            # isolates any unrelated .git markers in the temporary parent.
            subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
            (root / ".gitignore").write_text(".sol-extractions/\n", encoding="utf-8")
            pdf, raw_json = root / "Invented.pdf", root / "external.json"
            output = root / ".sol-extractions" / "candidate.json"
            pdf.write_bytes(b"%PDF-1.4\nInvented fixture, not parsed by an extraction engine.\n")
            document = {
                "file name": pdf.name, "number of pages": 1,
                "author": "Metadata is not passage attribution", "title": "Invented source",
                "creation date": None, "modification date": None,
                "kids": [{"type": "paragraph", "page number": 1,
                          "bounding box": [10, 20, 30, 40], "content": "Invented candidate prose."}],
            }
            raw_json.write_text(json.dumps(document), encoding="utf-8")
            source_bytes, raw_bytes = pdf.read_bytes(), raw_json.read_bytes()
            with patch("sol.corpus.backends.opendataloader.import_module") as sdk:
                summary = self.run_command(["normalize", "--json", str(raw_json), "--pdf", str(pdf),
                                            "--output", str(output), "--backend-version", "2.5.13"])
            sdk.assert_not_called()
            self.assertEqual(summary["status"], "unreviewed_candidate")
            artifact = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(artifact["backend"]["origin"], "external_json_declared")
            self.assertFalse(artifact["normalization"]["metadata_author_is_attribution"])
            self.assertEqual(artifact["raw_document"], document)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(pdf.read_bytes(), source_bytes)
            self.assertEqual(raw_json.read_bytes(), raw_bytes)

    def test_ingest_dispatches_reviewed_copy_without_selecting_it_for_reader(self):
        with patch("sol.corpus.ingest.ingest_reviewed", return_value={"status": "reviewed_copy"}) as operation:
            result = self.run_command(["ingest", "--candidate", "candidate.json", "--review", "review.json",
                                       "--baseline", "local-corpus", "--output", ".sol-ingest-work/reviewed"])
        operation.assert_called_once_with(Path("candidate.json"), Path("review.json"),
                                          Path("local-corpus"), Path(".sol-ingest-work/reviewed"))
        self.assertEqual(result, {"status": "reviewed_copy"})

    def test_new_commands_have_no_implicit_input_or_output_paths(self):
        cases = [
            ["extract", "--pdf", "source.pdf"],
            ["extract", "--output", "candidate.json"],
            ["normalize", "--json", "external.json", "--pdf", "source.pdf", "--output", "candidate.json"],
            ["normalize", "--pdf", "source.pdf", "--output", "candidate.json", "--backend-version", "2.5.13"],
            ["ingest", "--candidate", "candidate.json", "--baseline", "local-corpus", "--output", "reviewed"],
            ["ingest", "--candidate", "candidate.json", "--review", "review.json", "--baseline", "local-corpus"],
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as result:
                convert.main(arguments)
            self.assertEqual(result.exception.code, 2)

    def test_network_ocr_and_overwrite_flags_are_not_exposed(self):
        for flag in ("--hybrid", "--server", "--ocr", "--overwrite"):
            with self.subTest(flag=flag), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as result:
                convert.main(["extract", "--pdf", "source.pdf", "--output", "candidate.json", flag, "on"])
            self.assertEqual(result.exception.code, 2)

    def test_existing_convert_and_index_dispatch_are_preserved(self):
        with patch.object(convert, "convert", return_value={"records": 2}) as operation:
            self.assertEqual(self.run_command(["convert", "--pdf", "source.pdf", "--output", "book", "--work", "work"]),
                             {"records": 2})
        operation.assert_called_once_with(Path("source.pdf"), Path("book"), Path("work"))
        with patch.object(convert, "reindex", return_value={"records": 2}) as operation:
            self.run_command(["index", "book"])
        operation.assert_called_once_with(Path("book"))

    def test_operation_errors_are_concise_and_return_nonzero(self):
        with patch("sol.corpus.extraction.extract_candidate", side_effect=ValueError("Candidate already exists")), \
                redirect_stderr(StringIO()) as error, redirect_stdout(StringIO()) as output, \
                self.assertRaises(SystemExit) as result:
            convert.main(["extract", "--pdf", "source.pdf", "--output", "candidate.json"])
        self.assertEqual(result.exception.code, 1)
        self.assertEqual(error.getvalue(), "sol corpus: Candidate already exists\n")
        self.assertFalse(output.getvalue())

    def test_help_imports_neither_adapter_sdk_nor_markdown_parser(self):
        program = """
import builtins, sys
original_import = builtins.__import__
def guard(name, *args, **kwargs):
    if name.split('.')[0] in {'opendataloader_pdf', 'markdown_it'} or name in {
        'sol.corpus.extraction', 'sol.corpus.ingest', 'sol.corpus.backends.opendataloader'}:
        raise AssertionError('Help imported an optional operation: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard
from sol.corpus.convert import main
main(sys.argv[1:])
"""
        for arguments in (["--help"], ["extract", "--help"], ["normalize", "--help"], ["ingest", "--help"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, "-B", "-c", program, *arguments],
                                        cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("usage:", result.stdout)


if __name__ == "__main__":
    unittest.main()
