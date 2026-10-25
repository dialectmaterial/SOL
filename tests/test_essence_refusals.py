"""Invented inputs for truthful refusals and clean sentence-artifact saves."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sol.essence import (CoreProvider, FileProvider, WordStudyError, analyze_sentences,
                         analyze_tfidf, analyze_words, check_sentence_result,
                         decode_sentence_result, encode_word_result)
from sol.essence.cli import main
from sol.essence.encyclopedia import load_catalog
from sol.essence.essence_as_reflection_within_itself.sentences import save_sentence_result


class EssenceRefusalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-refusals-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.left = self.root / "left.txt"
        self.right = self.root / "right.txt"
        self.left.write_text("Blue blue green.")
        self.right.write_text("Green green green.")

    def call(self, args):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            status = main(args)
        return status, output.getvalue(), error.getvalue()

    def test_scoped_sentence_checker_validates_the_envelope_before_scope_access(self):
        source = CoreProvider(None, {"kind": "corpus"})
        for result in (None, [], "invented", 1, {}):
            with self.subTest(result=result):
                with self.assertRaises(ValueError) as caught:
                    check_sentence_result(source, result)
                self.assertEqual(caught.exception.code, "invalid_fields")

    def test_invalid_sentence_save_does_not_create_a_directory_or_empty_artifact(self):
        directory = self.root / "studies"
        with self.assertRaises(ValueError):
            save_sentence_result({}, directory)
        self.assertFalse(directory.exists())

    def test_failed_sentence_save_removes_the_partial_artifact(self):
        result = analyze_sentences(FileProvider(self.left))
        directory = self.root / "studies"
        fdopen = os.fdopen
        for error_type in (OSError, KeyboardInterrupt):
            @contextmanager
            def interrupted(descriptor, *args, **kwargs):
                with fdopen(descriptor, *args, **kwargs) as stream:
                    def write(data):
                        stream.write(data[:7])
                        raise error_type("invented interrupted save")
                    yield SimpleNamespace(write=write)

            with self.subTest(error=error_type):
                with patch("os.fdopen", side_effect=interrupted), self.assertRaises(error_type):
                    save_sentence_result(result, directory)
                self.assertEqual(list(directory.iterdir()), [])

    def test_valid_sentence_saves_keep_the_original_encoding_and_permissions(self):
        result = analyze_sentences(FileProvider(self.left))
        path = save_sentence_result(result, self.root / "studies")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertTrue(path.read_bytes().endswith(b"\n"))
        self.assertEqual(decode_sentence_result(path.read_bytes()), result)

    def test_missing_independent_reference_is_not_reported_as_a_changed_file(self):
        result = analyze_words(FileProvider(self.left), reference=FileProvider(self.right))
        saved = self.root / "words.json"
        saved.write_text(encode_word_result(result))
        for command in ("check", "words-export"):
            for options in ([], ["--reference-provider", "file"]):
                with self.subTest(command=command, options=options):
                    args = [command, str(saved), "--input-file", str(self.left), *options]
                    if command == "check":
                        args.append("--json")
                    status, output, error = self.call(args)
                    self.assertEqual(status, 2)
                    self.assertIn("--reference-file", error)
                    if command == "check":
                        self.assertEqual(json.loads(output)["code"], "missing_file")
                    else:
                        self.assertEqual(output, "")

    def test_same_file_comparison_still_reuses_the_explicit_target_path(self):
        source = FileProvider(self.left)
        saved = self.root / "same-file.json"
        saved.write_text(encode_word_result(analyze_words(source, reference=source)))
        status, output, error = self.call(["check", str(saved), "--input-file", str(self.left), "--json"])
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)["status"], "current")

    def test_invalid_tfidf_limits_name_the_parameter_and_accepted_range(self):
        for limit in (0, -1, True, 1.5, 1001):
            with self.subTest(limit=limit), self.assertRaisesRegex(WordStudyError, "top_n.*1.*1000"):
                analyze_tfidf(FileProvider(self.left), top_n=limit)
        status, output, error = self.call(["tfidf", "--file", str(self.left), "--top-n", "0", "--json"])
        self.assertEqual(status, 2)
        self.assertIn("top_n", error)
        self.assertEqual(json.loads(output)["code"], "invalid_number")

    def test_tfidf_catalog_acknowledges_the_implemented_experiment_screen(self):
        entry = next(item for item in load_catalog()["entries"] if item["id"] == "tf-idf")
        self.assertIn("Experiment", entry["essence"])
        self.assertNotIn("pending", entry["essence"])


if __name__ == "__main__":
    unittest.main()
