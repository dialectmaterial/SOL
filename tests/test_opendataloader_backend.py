"""Optional local extraction boundary, using invented PDFs and a mocked SDK."""
from __future__ import annotations

import hashlib
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sol.corpus.backends import opendataloader as backend


class OpenDataLoaderBackendTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-odl-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.pdf = self.directory / "Invented source.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\nAn invented source, never read by a real SDK.\n")
        self.output = self.directory / "raw"
        self.document = {"file name": self.pdf.name, "number of pages": 3,
                         "author": None, "title": "Invented title", "creation date": None,
                         "modification date": None,
                         "kids": [{"type": "paragraph", "id": 7, "page number": 2,
                                   "bounding box": [10, 20, 30, 40], "font": "Times",
                                   "font size": 10, "text color": "[0.0]",
                                   "content": "An invented paragraph."}]}
        for target, value in [("metadata.version", backend.SUPPORTED_VERSION),
                              ("import_module", SimpleNamespace(convert=self.convert)),
                              ("shutil.which", "/invented/java")]:
            mock = patch(f"sol.corpus.backends.opendataloader.{target}", return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        self.arguments = None

    def convert(self, **arguments):
        self.arguments = arguments
        path = Path(arguments["output_dir"]) / (self.pdf.stem + ".json")
        path.write_text(json.dumps(self.document), encoding="utf-8")

    def extract(self, **kwargs):
        return backend.extract_pdf(self.pdf, self.output, **kwargs)

    def test_local_options_and_raw_metadata_are_preserved(self):
        original = self.pdf.read_bytes()
        result = self.extract(pages="2-3")
        self.assertEqual(self.arguments, {"input_path": [str(self.pdf)],
                                         "output_dir": str(self.output), "format": "json",
                                         "hybrid": "off", "image_output": "off", "quiet": True,
                                         "pages": "2-3"})
        self.assertEqual(result["source"], {"filename": self.pdf.name,
                                          "sha256": hashlib.sha256(original).hexdigest(),
                                          "pdf_pages": 3})
        self.assertEqual(result["document"], self.document)
        self.assertEqual(result["backend"]["version"], backend.SUPPORTED_VERSION)
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertNotIn("pages", self.extract_options_without_pages())

    def extract_options_without_pages(self):
        return backend.extract_pdf(self.pdf, self.directory / "other")["backend"]["options"]

    def test_missing_optional_sdk_does_not_create_output(self):
        with patch.object(backend.metadata, "version", side_effect=metadata.PackageNotFoundError):
            with self.assertRaisesRegex(backend.ExtractionError, "optional"):
                self.extract()
        self.assertFalse(self.output.exists())

    def test_missing_sdk_import_does_not_create_output(self):
        with patch.object(backend, "import_module", side_effect=ModuleNotFoundError):
            with self.assertRaisesRegex(backend.ExtractionError, "optional"):
                self.extract()
        self.assertFalse(self.output.exists())

    def test_untested_sdk_version_is_rejected(self):
        with patch.object(backend.metadata, "version", return_value="3.0.0"), \
                patch.object(backend, "import_module") as imported:
            with self.assertRaisesRegex(backend.ExtractionError, "Supported.*version"):
                self.extract()
            imported.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_missing_java_does_not_create_output(self):
        with patch.object(backend.shutil, "which", return_value=None):
            with self.assertRaisesRegex(backend.ExtractionError, "Java 11"):
                self.extract()
        self.assertFalse(self.output.exists())

    def test_sdk_runner_failure_is_actionable(self):
        with patch.object(backend, "import_module", return_value=SimpleNamespace(
                convert=lambda **kwargs: (_ for _ in ()).throw(FileNotFoundError("java")))):
            with self.assertRaisesRegex(backend.ExtractionError, "could not start"):
                self.extract()

    def test_process_failure_does_not_fall_back(self):
        with patch.object(backend, "import_module", return_value=SimpleNamespace(
                convert=lambda **kwargs: (_ for _ in ()).throw(
                    subprocess.CalledProcessError(1, ["java"])) )):
            with self.assertRaisesRegex(backend.ExtractionError, "no alternate or remote"):
                self.extract()

    def test_missing_json_is_not_guessed_or_reused(self):
        with patch.object(backend, "import_module", return_value=SimpleNamespace(convert=lambda **kwargs: None)):
            with self.assertRaisesRegex(backend.ExtractionError, "expected JSON"):
                self.extract()

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        original = self.output / "keep.txt"
        original.write_text("Keep this.")
        with self.assertRaisesRegex(backend.ExtractionError, "must not already exist"):
            self.extract()
        self.assertEqual(original.read_text(), "Keep this.")

    def test_symlink_parent_and_dangling_output_are_rejected(self):
        link = self.directory / "link"
        link.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaisesRegex(backend.ExtractionError, "symlinks"):
            backend.extract_pdf(self.pdf, link / "raw")
        self.output.symlink_to(self.directory / "missing", target_is_directory=True)
        with self.assertRaisesRegex(backend.ExtractionError, "must not already exist"):
            self.extract()

    def test_pdf_symlink_or_non_pdf_is_rejected(self):
        alias = self.directory / "alias.pdf"
        alias.symlink_to(self.pdf)
        with self.assertRaisesRegex(backend.ExtractionError, "non-symlink"):
            backend.extract_pdf(alias, self.output)
        self.pdf.write_bytes(b"Not a PDF")
        with self.assertRaisesRegex(backend.ExtractionError, "PDF header"):
            self.extract()

    def test_source_change_during_sdk_call_is_rejected(self):
        def modified(**kwargs):
            self.convert(**kwargs)
            self.pdf.write_bytes(b"%PDF-1.4\nA changed source")
        with patch.object(backend, "import_module", return_value=SimpleNamespace(convert=modified)):
            with self.assertRaisesRegex(backend.ExtractionError, "changed during extraction"):
                self.extract()

    def test_unexpected_sdk_error_still_checks_source_and_is_wrapped(self):
        def failed(**kwargs):
            raise RuntimeError("A synthetic SDK failure")
        with patch.object(backend, "import_module", return_value=SimpleNamespace(convert=failed)):
            with self.assertRaisesRegex(backend.ExtractionError, "extraction failed"):
                self.extract()

    def test_quiet_sdk_summary_is_not_mixed_into_callers_output(self):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        def printing(**kwargs):
            print("Synthetic summary")
            print("Synthetic diagnostic", file=sys.stderr)
            self.convert(**kwargs)
        stdout, stderr = StringIO(), StringIO()
        with patch.object(backend, "import_module", return_value=SimpleNamespace(convert=printing)), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            self.extract()
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_document_for_a_different_source_is_rejected(self):
        self.document["file name"] = "another.pdf"
        with self.assertRaisesRegex(backend.ExtractionError, "different source"):
            self.extract()

    def test_import_does_not_load_sdk_or_execute_java(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-B", "-c", "import sys; "
             "import sol.corpus.backends.opendataloader; "
             "assert 'opendataloader_pdf' not in sys.modules"],
            cwd=root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_json_symlink_is_not_followed(self):
        target = self.directory / "foreign.json"
        target.write_text(json.dumps(self.document))
        def linked(**kwargs):
            (self.output / (self.pdf.stem + ".json")).symlink_to(target)
        with patch.object(backend, "import_module", return_value=SimpleNamespace(convert=linked)):
            with self.assertRaisesRegex(backend.ExtractionError, "expected JSON"):
                self.extract()

    def test_json_invalid_numbers_duplicates_and_root_contract_are_rejected(self):
        fixtures = ["{\"x\":NaN}", "{\"x\":Infinity}", "{\"x\":1e999}",
                    "{\"x\":1,\"x\":2}", "[]", "{}", "{broken",
                    json.dumps({**self.document, "number of pages": True}),
                    json.dumps({**self.document, "number of pages": 0}),
                    json.dumps({**self.document, "kids": {}}),
                    json.dumps({**self.document, "author": 42})]
        for index, raw in enumerate(fixtures):
            with self.subTest(raw=raw):
                self.output = self.directory / f"invalid-{index}"
                def invalid(**kwargs):
                    (self.output / (self.pdf.stem + ".json")).write_text(raw)
                with patch.object(backend, "import_module", return_value=SimpleNamespace(convert=invalid)):
                    with self.assertRaises(backend.ExtractionError):
                        self.extract()

    def test_page_options_are_positive_explicit_ranges(self):
        for option in ("", "0", "1,0", "3-2", "2-0", "1 --hybrid", " 1", "1 ", "1-2-3", 2):
            with self.subTest(option=option):
                with self.assertRaisesRegex(backend.ExtractionError, "Pages|ranges"):
                    self.extract(pages=option)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
