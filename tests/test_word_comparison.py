"""Auditable effect sizes and private tabular exports over invented text."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import csv
from hashlib import sha256
from io import StringIO
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.essence import (CoreProvider, FileProvider, WordStudyError, analyze_words, check_word_result,
                         compare_words, encode_word_result, export_word_comparison)
from sol.essence import cli
from sol.essence.comparison import EXPORT_FIELDS
from fixtures_corpus import CorpusFixture


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-comparison-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.left, self.right = self.root / "target.txt", self.root / "reference.txt"
        self.left.write_text("red red blue", encoding="utf-8")
        self.right.write_text("red blue green green green green", encoding="utf-8")
        self.target, self.reference = FileProvider(self.left), FileProvider(self.right)

    def compare(self, **options):
        return compare_words(self.target, reference=self.reference, **options)

    def export(self, **options):
        return export_word_comparison(self.target, reference=self.reference, **options)

    def test_known_unequal_denominators_and_formula_direction(self):
        view = self.compare()
        rows = {row["word"]: row for row in view["rows"]}
        red = rows["red"]
        self.assertEqual(red["target"]["count"], 2)
        self.assertEqual(red["target"]["denominator"], 3)
        self.assertEqual(red["reference"]["denominator"], 6)
        self.assertEqual(red["rate_difference_per_10000_tokens"], 5000.0)
        self.assertEqual(red["log2_rate_ratio"], 2.0)
        self.assertEqual(red["log2_ratio_status"], "defined")
        self.assertEqual(rows["blue"]["log2_rate_ratio"], 1.0)
        self.assertEqual(rows["blue"]["rate_difference_per_10000_tokens"], 1666.666667)
        self.assertIn("no smoothing", view["method"]["zero_policy"])
        self.assertTrue(any("not significance" in warning for warning in view["warnings"]))
        self.assertTrue(any("Unequal" in warning for warning in view["warnings"]))

    def test_difference_is_computed_from_counts_before_rate_rounding(self):
        self.left.write_text("red blue blue")
        self.right.write_text("red blue blue blue blue blue blue")
        red = next(row for row in self.compare()["rows"] if row["word"] == "red")
        self.assertEqual(red["rate_difference_per_10000_tokens"], 1904.761905)
        self.assertEqual(red["log2_rate_ratio"], round(math.log2(7 / 3), 6))

    def test_swapping_sides_negates_both_defined_measures(self):
        forward = {row["word"]: row for row in self.compare()["rows"]}
        backward = compare_words(self.reference, reference=self.target)
        for row in backward["rows"]:
            old = forward[row["word"]]
            self.assertEqual(row["rate_difference_per_10000_tokens"], -old["rate_difference_per_10000_tokens"])
            if row["log2_rate_ratio"] is not None:
                self.assertEqual(row["log2_rate_ratio"], -old["log2_rate_ratio"])

    def test_zero_occurrences_have_defined_difference_but_undefined_unsmoothed_ratio(self):
        self.left.write_text("red red")
        self.right.write_text("blue blue blue")
        rows = {row["word"]: row for row in self.compare()["rows"]}
        self.assertEqual(rows["red"]["rate_difference_per_10000_tokens"], 10000.0)
        self.assertEqual(rows["blue"]["rate_difference_per_10000_tokens"], -10000.0)
        self.assertIsNone(rows["red"]["log2_rate_ratio"])
        self.assertIsNone(rows["blue"]["log2_rate_ratio"])
        self.assertEqual(rows["red"]["log2_ratio_status"], "zero_reference_count")
        self.assertEqual(rows["blue"]["log2_ratio_status"], "zero_target_count")
        self.assertEqual(rows["red"]["rate_difference_status"], "defined")

    def test_empty_denominators_and_empty_union(self):
        for left, right, status in (("", "blue", "empty_target"), ("red", "123 !", "empty_reference")):
            with self.subTest(status=status):
                self.left.write_text(left)
                self.right.write_text(right)
                row = self.compare()["rows"][0]
                self.assertIsNone(row["rate_difference_per_10000_tokens"])
                self.assertIsNone(row["log2_rate_ratio"])
                self.assertEqual(row["rate_difference_status"], status)
                self.assertEqual(row["log2_ratio_status"], status)
                exported = next(csv.DictReader(StringIO(self.export())))
                self.assertEqual(exported["rate_difference_per_10000_tokens"], "")
                self.assertEqual(exported["log2_rate_ratio"], "")
                empty = "target" if status == "empty_target" else "reference"
                self.assertEqual(exported[empty + "_denominator"], "0")
                self.assertEqual(exported[empty + "_rate_per_10000_tokens"], "")
        self.left.write_text("")
        self.right.write_text("")
        result = self.compare()
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["study"]["target"]["summary"]["token_count"], 0)
        self.assertEqual(list(csv.DictReader(StringIO(self.export()))), [])
        self.assertEqual(tuple(next(csv.reader(StringIO(self.export())))), EXPORT_FIELDS)

    def test_identical_overlapping_scopes_are_allowed_and_descriptive(self):
        result = compare_words(self.target, reference=self.target)
        for row in result["rows"]:
            self.assertEqual(row["rate_difference_per_10000_tokens"], 0.0)
            self.assertEqual(row["log2_rate_ratio"], 0.0)
        self.assertTrue(any("Overlapping" in warning for warning in result["warnings"]))

    def test_v1_shape_encoding_and_check_are_unchanged(self):
        result = analyze_words(self.target, reference=self.reference)
        before = encode_word_result(result)
        view = self.compare(result=result)
        self.assertEqual(result, view["study"])
        self.assertEqual(encode_word_result(view["study"]), before)
        self.assertEqual(encode_word_result(result), before)
        self.assertEqual(view["study_sha256"], sha256(before.encode()).hexdigest())
        self.assertEqual(check_word_result(self.target, result, reference=self.reference), result)
        self.assertEqual(view, self.compare())

    def test_csv_and_tsv_round_trip_unicode_counts_nulls_and_provenance(self):
        self.left.write_text("Café isn't α α")
        self.right.write_text("CAFÉ β β isn't isn't")
        view = self.compare()
        expected = {row["word"]: row for row in view["rows"]}
        for format, separator in (("csv", ","), ("tsv", "\t")):
            with self.subTest(format=format):
                exported = self.export(format=format, result=view["study"])
                reader = csv.DictReader(StringIO(exported), delimiter=separator)
                actual = list(reader)
                self.assertEqual(tuple(reader.fieldnames), EXPORT_FIELDS)
                self.assertEqual([row["word"] for row in actual], [row["word"] for row in view["rows"]])
                for row in actual:
                    original = expected[row["word"]]
                    for name in ("target", "reference"):
                        for key in ("count", "denominator"):
                            self.assertEqual(int(row[name + "_" + key]), original[name][key])
                        self.assertEqual(json.loads(row[name + "_binding"]), view["study"][name]["binding"])
                        scope = json.dumps(view["study"][name]["scope"], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                        self.assertEqual(row[name + "_scope_sha256"], sha256(scope.encode()).hexdigest())
                    self.assertEqual(row["study_sha256"], view["study_sha256"])
                    self.assertEqual(json.loads(row["warnings"]), view["warnings"])
                    for key in ("rate_difference_per_10000_tokens", "log2_rate_ratio"):
                        self.assertEqual(float(row[key]) if row[key] else None, original[key])
                    self.assertEqual(row["log2_ratio_status"], original["log2_ratio_status"])
                self.assertNotIn(str(self.root), exported)
                self.assertNotIn(self.left.read_text(), exported)

    def test_missing_reference_and_invalid_format_are_refused(self):
        with self.assertRaisesRegex(WordStudyError, "explicit reference"):
            compare_words(self.target, reference=None)
        with patch("sol.essence.comparison.compare_words", side_effect=AssertionError("No source open")):
            with self.assertRaises(WordStudyError):
                self.export(format="html")

    def test_changed_target_or_reference_refuses_comparison_and_export(self):
        original = analyze_words(self.target, reference=self.reference)
        for path in (self.left, self.right):
            before = path.read_bytes()
            path.write_bytes(before + b".")  # Same counts, different digest.
            for operation in (self.compare, self.export):
                with self.subTest(path=path, operation=operation), self.assertRaises(WordStudyError) as caught:
                    operation(result=original)
                self.assertEqual(caught.exception.code, "file_changed")
            path.write_bytes(before)

    def test_modified_counts_and_missing_reference_artifact_are_refused(self):
        result = analyze_words(self.target, reference=self.reference)
        altered = deepcopy(result)
        altered["frequencies"][0]["target"]["count"] += 1
        with self.assertRaises(WordStudyError):
            self.export(result=altered)
        with self.assertRaises(WordStudyError):
            self.export(result=analyze_words(self.target))

    def call(self, args, stdin=None):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err), patch.object(sys, "stdin", stdin or StringIO()):
            status = cli.main(args)
        return status, out.getvalue(), err.getvalue()

    def test_cli_exports_saved_study_and_stdin_with_explicit_sources(self):
        result = analyze_words(self.target, reference=self.reference)
        saved = self.root / "study.json"
        saved.write_text(encode_word_result(result))
        for format in ("csv", "tsv"):
            args = ["words-export", str(saved), "--input-file", str(self.left),
                    "--reference-file", str(self.right), "--format", format]
            status, out, err = self.call(args)
            self.assertEqual(status, 0, err)
            self.assertEqual(out, self.export(result=result, format=format))
            args[1] = "-"
            self.assertEqual(self.call(args, StringIO(saved.read_text())), (status, out, err))

    def test_cli_stale_malformed_and_implicit_file_sources_have_no_table_output(self):
        saved = self.root / "study.json"
        saved.write_text(encode_word_result(analyze_words(self.target, reference=self.reference)))
        for arguments in (["words-export", str(saved)], ["words-export", str(saved), "--input-file", str(self.left),
                         "--reference-file", str(self.right)]):
            if "--input-file" in arguments:
                self.right.write_text("A changed reference")
            status, out, err = self.call(arguments)
            self.assertEqual(status, 2)
            self.assertEqual(out, "")
            self.assertTrue(err)
        saved.write_text('{"protocol":"sol.word-frequencies","version":2}')
        with patch("sol.core.discover_corpus", side_effect=AssertionError("No discovery")):
            status, out, err = self.call(["words-export", str(saved)])
        self.assertEqual((status, out), (2, ""))

    def test_file_comparison_api_and_cli_import_no_core_or_ui(self):
        result = analyze_words(self.target, reference=self.reference)
        saved = self.root / "study.json"
        saved.write_text(encode_word_result(result))
        script = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, *args):
        if name.startswith(('sol.core','sol.corpus','sol.reader','sol.terminal','sol.essence.tui','textual')):
            raise AssertionError('Forbidden import: ' + name)
sys.meta_path.insert(0, Block())
from sol.essence import FileProvider, compare_words, export_word_comparison
from sol.essence.cli import main
target, reference = FileProvider(sys.argv[1]), FileProvider(sys.argv[2])
view = compare_words(target, reference=reference)
assert export_word_comparison(target, reference=reference, result=view['study'])
assert main(['words-export', sys.argv[3], '--input-file', sys.argv[1], '--reference-file', sys.argv[2]]) == 0
'''
        run = subprocess.run([sys.executable, "-B", "-c", script, str(self.left), str(self.right), str(saved)],
                             cwd=self.root, env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
                             capture_output=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr.decode())


class CoreComparisonTests(CorpusFixture, unittest.TestCase):
    def test_cli_core_export_recovers_verified_saved_scopes(self):
        target = CoreProvider(self.book.corpus_snapshot, {"kind": "within", "path": "/BEING"})
        reference = CoreProvider(self.book.corpus_snapshot)
        result = analyze_words(target, reference=reference)
        saved = self.root / "study.json"
        saved.write_text(encode_word_result(result))
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            status = cli.main(["words-export", str(saved), "--corpus", str(self.corpus), "--format", "tsv"])
        self.assertEqual(status, 0, error.getvalue())
        self.assertEqual(output.getvalue(), export_word_comparison(target, reference=reference, result=result, format="tsv"))

    def test_core_unequal_scopes_and_source_metadata_without_heading_text(self):
        self.rewrite_body("Ground ground other words.")
        target = CoreProvider(self.book.corpus_snapshot, {"kind": "span", "id": self.identifier, "start": 0, "end": 6})
        reference = CoreProvider(self.book.corpus_snapshot)
        view = compare_words(target, reference=reference)
        row = view["rows"][0]
        self.assertEqual(row["word"], "ground")
        self.assertEqual(row["rate_difference_per_10000_tokens"], 5000.0)
        self.assertEqual(row["log2_rate_ratio"], 1.0)
        text = export_word_comparison(target, reference=reference, result=view["study"])
        rows = list(csv.DictReader(StringIO(text)))
        self.assertEqual(json.loads(rows[0]["target_binding"])["corpus"]["id"], self.book.corpus_snapshot.corpus_id)
        self.assertNotIn(self.body, text)
        self.assertNotIn("/BEING/synthetic.txt", text)
        self.assertNotIn(self.identifier, text)

    def test_changed_unselected_core_record_refuses_saved_comparison(self):
        source = CoreProvider(self.book.corpus_snapshot)
        result = analyze_words(source, reference=source)
        records = deepcopy(self.book.corpus_snapshot.records)
        records[0]["markdown"], records[0]["plain_text"] = "# Changed heading", "Changed heading"
        self.write_records(records)
        fresh = CoreProvider(self.book.corpus_snapshot)
        for operation in (compare_words, export_word_comparison):
            with self.subTest(operation=operation), self.assertRaises(WordStudyError) as caught:
                operation(fresh, reference=fresh, result=result)
            self.assertEqual(caught.exception.code, "generation_changed")


if __name__ == "__main__":
    unittest.main()
