"""Invented provider inputs, independent formula checks and strict receipts."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
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

from fixtures_corpus import CorpusFixture
from sol.essence import (CoreProvider, FileProvider, WordStudyError, analyze_tfidf,
                         check_tfidf_result, decode_tfidf_result, encode_tfidf_result)
from sol.essence.cli import main


class FileTfidfTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "input.txt"
        self.path.write_text("Red red blue\nblue green", encoding="utf-8")
        self.source = FileProvider(self.path)

    def test_one_file_is_one_document_and_top_n_does_not_change_norm(self):
        result = analyze_tfidf(self.source, top_n=1)
        self.assertEqual(len(result["documents"]), 1)
        # N=df=1, so idf=1; vector (blue=2, red=2, green=1), norm=3.
        expected = [{"word": "blue", "score": round(2 / 3, 12)}]
        self.assertEqual(result["documents"][0]["top_terms"], expected)
        self.assertEqual(result["overall"], expected)
        self.assertEqual(check_tfidf_result(self.source, decode_tfidf_result(encode_tfidf_result(result))), result)
        self.assertEqual(encode_tfidf_result(result), encode_tfidf_result(analyze_tfidf(self.source, top_n=1)))
        self.assertNotIn(str(self.path), encode_tfidf_result(result))
        self.assertNotIn(self.path.read_text(), encode_tfidf_result(result))

    def test_unicode_span_empty_and_invalid_limit(self):
        self.path.write_text("Straße STRASSE Café Cafe\u0301", encoding="utf-8")
        result = analyze_tfidf(self.source)
        self.assertEqual([row["word"] for row in result["overall"]], ["café", "strasse"])
        scoped = FileProvider(self.path, {"kind": "span", "start": 0, "end": 6})
        self.assertEqual(analyze_tfidf(scoped)["overall"], [{"word": "strasse", "score": 1.0}])
        self.path.write_text("123 !")
        empty = analyze_tfidf(self.source)
        self.assertEqual(empty["documents"], [{"input_index": 0, "top_terms": []}])
        self.assertEqual(empty["overall"], [])
        for limit in (0, -1, 1001, True, 1.5, "2"):
            with self.subTest(limit=limit), self.assertRaises(WordStudyError):
                analyze_tfidf(self.source, top_n=limit)

    def test_tampering_versions_and_strict_json(self):
        original = analyze_tfidf(self.source)
        for change in (lambda r: r.update(version=True), lambda r: r.update(version=2),
                       lambda r: r["method"].update(tf="log"),
                       lambda r: r["overall"][0].update(score=0),
                       lambda r: r["documents"].clear(),
                       lambda r: r["word_study"]["target"]["binding"].update(path="/arbitrary")):
            altered = deepcopy(original)
            change(altered)
            with self.assertRaises(WordStudyError):
                decode_tfidf_result(json.dumps(altered))
        for raw in ('{"protocol":"sol.tfidf","protocol":"sol.tfidf"}', '{"score":NaN}', b'\xff'):
            with self.assertRaises(WordStudyError):
                decode_tfidf_result(raw)

    def test_changed_bytes_even_with_same_tokens_are_stale(self):
        result = analyze_tfidf(self.source)
        self.path.write_text(self.path.read_text() + "!")
        with self.assertRaises(WordStudyError) as caught:
            check_tfidf_result(self.source, result)
        self.assertEqual((caught.exception.status, caught.exception.code), ("stale", "file_changed"))

    def test_result_size_bound_and_no_saved_file_authority(self):
        result = analyze_tfidf(self.source)
        with patch("sol.essence.essence_as_reflection_within_itself.tfidf.MAX_RESULT_BYTES", 100), self.assertRaises(WordStudyError) as caught:
            encode_tfidf_result(result)
        self.assertEqual(caught.exception.code, "size_limit")
        saved = self.root / "study.json"
        saved.write_text(encode_tfidf_result(result))
        status, receipt, _ = self.invoke(["check", str(saved), "--json"])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(receipt)["code"], "missing_file")

    def invoke(self, args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(args)
        return status, out.getvalue(), err.getvalue()

    def test_cli_json_human_saved_scope_check_and_reference_refusal(self):
        status, raw, error = self.invoke(["tfidf", "--file", str(self.path), "--span", "0", "3", "--top-n", "1", "--json"])
        self.assertEqual(status, 0, error)
        saved = self.root / "study.json"
        saved.write_text(raw)
        status, receipt, error = self.invoke(["check", str(saved), "--input-file", str(self.path), "--json"])
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(receipt)["status"], "current")
        self.assertEqual(self.invoke(["tfidf", "--file", str(self.path)])[0], 0)
        self.assertIn("TF-IDF", self.invoke(["tfidf", "--file", str(self.path)])[1])
        self.assertEqual(self.invoke(["check", str(saved), "--input-file", str(self.path), "--compare"])[0], 2)
        status, raw, _ = self.invoke(["tfidf", "--file", str(self.path), "--top-n", "0", "--json"])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(raw)["code"], "invalid_number")

    def test_file_api_cli_and_piped_check_without_core_or_ui(self):
        script = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, *args):
        if name.startswith(("sol.core", "sol.corpus", "sol.reader", "sol.terminal", "sol.workspace", "textual", "torch", "sklearn", "numpy")):
            raise AssertionError("Forbidden import: " + name)
sys.meta_path.insert(0, Block())
from sol.essence import FileProvider, analyze_tfidf, check_tfidf_result
from sol.essence.cli import main
source = FileProvider(sys.argv[1])
check_tfidf_result(source, analyze_tfidf(source))
assert main(["tfidf", "--file", sys.argv[1], "--json"]) == 0
assert main(["check", "-", "--input-file", sys.argv[1], "--json"]) == 0
'''
        run = subprocess.run([sys.executable, "-B", "-c", script, str(self.path)],
                             input=encode_tfidf_result(analyze_tfidf(self.source)), text=True,
                             capture_output=True, cwd=self.root, timeout=10,
                             env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])})
        self.assertEqual(run.returncode, 0, run.stderr)


class CoreTfidfTests(CorpusFixture, unittest.TestCase):
    def source(self, scope=None):
        return CoreProvider(self.book.corpus_snapshot, scope)

    def test_multiple_documents_idf_l2_and_overall_before_truncation(self):
        self.rewrite_body("common rare rare")
        rows = deepcopy(self.book.corpus_snapshot.records)
        second = deepcopy(rows[1])
        second.update(id="bbbbbbbb-0000-4000-8000-000000000003", order=2,
                      markdown="common other", plain_text="common other")
        rows.append(second)
        self.write_records(rows)
        result = analyze_tfidf(self.source(), top_n=1)
        rare_idf = 1 + math.log(3 / 2)
        first_norm = math.sqrt(1 + (2 * rare_idf) ** 2)
        second_norm = math.sqrt(1 + rare_idf ** 2)
        self.assertEqual(result["documents"][0]["top_terms"],
                         [{"word": "rare", "score": round(2 * rare_idf / first_norm, 12)}])
        self.assertEqual(result["documents"][1]["top_terms"],
                         [{"word": "other", "score": round(rare_idf / second_norm, 12)}])
        self.assertEqual(result["overall"], [{"word": "rare", "score": round(rare_idf / first_norm, 12)}])
        full = analyze_tfidf(self.source())
        common = next(row["score"] for row in full["overall"] if row["word"] == "common")
        self.assertEqual(common, round((1 / first_norm + 1 / second_norm) / 2, 12))
        self.assertEqual(check_tfidf_result(self.source(), result), result)
        self.assertEqual(len(result["word_study"]["target"]["inputs"]), 2)

    def test_empty_document_in_N_and_empty_eligible_corpus(self):
        self.rewrite_body("123 !!!")
        rows = deepcopy(self.book.corpus_snapshot.records)
        second = deepcopy(rows[1])
        second.update(id="bbbbbbbb-0000-4000-8000-000000000003", order=2,
                      markdown="word", plain_text="word")
        rows.append(second)
        self.write_records(rows)
        result = analyze_tfidf(self.source())
        self.assertEqual(result["documents"][0]["top_terms"], [])
        self.assertEqual(result["overall"], [{"word": "word", "score": 0.5}])
        for row in rows[1:]:
            row["transcription_status"] = "needs_review"
        self.write_records(rows)
        result = analyze_tfidf(self.source())
        self.assertEqual(result["documents"], [])
        self.assertEqual(result["overall"], [])

    def test_scopes_and_changed_unselected_generation(self):
        self.rewrite_body("Ground ground other")
        scope = {"kind": "span", "id": self.identifier, "start": 0, "end": 6}
        result = analyze_tfidf(self.source(scope))
        self.assertEqual(result["overall"], [{"word": "ground", "score": 1.0}])
        rows = deepcopy(self.book.corpus_snapshot.records)
        rows[0].update(markdown="# Changed heading", plain_text="Changed heading")
        self.write_records(rows)
        with self.assertRaises(WordStudyError) as caught:
            check_tfidf_result(self.source(scope), result)
        self.assertEqual(caught.exception.code, "generation_changed")

    def test_core_cli_check_and_projection_match_word_study(self):
        from sol.essence import analyze_words

        self.rewrite_body("Actual words.")
        result = analyze_tfidf(self.source({"kind": "within", "path": "/BEING"}))
        self.assertEqual(result["word_study"], analyze_words(self.source({"kind": "within", "path": "/BEING"})))
        saved = self.root / "study.json"
        out = StringIO()
        with redirect_stdout(out):
            status = main(["tfidf", "--corpus", str(self.corpus), "--passage", self.identifier, "--json"])
        self.assertEqual(status, 0)
        saved.write_text(out.getvalue())
        out = StringIO()
        with redirect_stdout(out):
            status = main(["check", str(saved), "--corpus", str(self.corpus), "--json"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "current")
