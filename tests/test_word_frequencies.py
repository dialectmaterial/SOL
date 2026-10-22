"""Invented input only; compare exact scopes, provenance and refusal paths."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol import core
from sol.essence import (CoreProvider, FileProvider, WordStudyError, analyze_words,
                         check_word_result, decode_word_result, encode_word_result)
from sol.essence import cli
from sol.essence.essence_as_reflection_within_itself.tokenization import word_tokens
from fixtures_corpus import CorpusFixture


def table(result):
    return {row["word"]: row for row in result["frequencies"]}


class FileWordTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-words-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "ordinary input.txt"
        self.path.write_text("An invented word. A word!", encoding="utf-8")
        self.provider = FileProvider(self.path)

    def test_file_counts_types_rates_locations_and_determinism(self):
        result = analyze_words(self.provider)
        self.assertEqual(result["target"]["summary"], {"token_count": 5, "type_count": 4, "input_count": 1})
        word = table(result)["word"]["target"]
        self.assertEqual(word, {"count": 2, "denominator": 5, "rate_per_10000_tokens": 4000.0,
                                "locations": [[0, 2, 12, 16]]})
        self.assertEqual(result, check_word_result(self.provider, decode_word_result(encode_word_result(result))))
        self.assertEqual(encode_word_result(result), encode_word_result(analyze_words(self.provider)))
        self.assertEqual(result["target"]["binding"], {"sha256": sha256(self.path.read_bytes()).hexdigest(),
                                                       "bytes": self.path.stat().st_size})
        serialized = encode_word_result(result)
        self.assertNotIn(self.path.read_text(), serialized)
        self.assertNotIn(str(self.path), serialized)
        self.assertNotIn('"text":', serialized)
        self.assertNotIn('"context":', serialized)

    def test_unicode_normalization_apostrophes_and_original_offsets(self):
        text = "Straße STRASSE Cafe\u0301 CAFÉ isn't isn’t α\u0301 Ά well-being 123 漢字"
        self.path.write_text(text, encoding="utf-8")
        result = analyze_words(self.provider)
        counts = {word: row["target"]["count"] for word, row in table(result).items()}
        self.assertEqual(counts, {"strasse": 2, "café": 2, "isn't": 2, "ά": 2, "well": 1, "being": 1, "漢字": 1})
        self.assertEqual(result["target"]["summary"]["token_count"], 11)
        for word, row in table(result).items():
            _, _, start, end = row["target"]["locations"][0]
            self.assertEqual(list(word_tokens(text[start:end]))[0][0], word)

    def test_empty_input_and_empty_reference_have_undefined_rates(self):
        self.path.write_bytes(b"")
        empty = analyze_words(self.provider)
        self.assertEqual(empty["target"]["summary"]["token_count"], 0)
        self.assertEqual(empty["target"]["summary"]["type_count"], 0)
        self.assertEqual(empty["frequencies"], [])
        other = self.root / "other.txt"
        other.write_text("only")
        result = analyze_words(FileProvider(other), reference=self.provider)
        self.assertEqual(table(result)["only"]["reference"]["count"], 0)
        self.assertIsNone(table(result)["only"]["reference"]["rate_per_10000_tokens"])
        self.assertEqual(check_word_result(FileProvider(other), result, reference=self.provider), result)
        self.path.write_text("123 — !!! \u0301")
        self.assertEqual(analyze_words(self.provider)["frequencies"], [])

    def test_unequal_independent_files_union_and_explicit_denominators(self):
        self.path.write_text("red red blue")
        reference = self.root / "reference.txt"
        reference.write_text("blue green green green green green")
        result = analyze_words(self.provider, reference=FileProvider(reference))
        self.assertEqual(result["reference"]["summary"]["type_count"], 2)
        self.assertEqual(table(result)["blue"]["target"]["denominator"], 3)
        self.assertEqual(table(result)["blue"]["reference"]["denominator"], 6)
        self.assertEqual(table(result)["blue"]["target"]["rate_per_10000_tokens"], 3333.333333)
        self.assertEqual(table(result)["blue"]["reference"]["rate_per_10000_tokens"], 1666.666667)
        self.assertEqual(table(result)["green"]["target"]["count"], 0)
        self.assertEqual([row["word"] for row in result["frequencies"]], ["red", "blue", "green"])
        self.assertTrue(any("Unequal" in warning for warning in result["warnings"]))

    def test_file_span_uses_codepoints_and_never_counts_partial_words(self):
        self.path.write_text("αα Café word ending")
        provider = FileProvider(self.path, {"kind": "span", "start": 1, "end": 11})
        result = analyze_words(provider)
        self.assertEqual(list(table(result)), ["café"])
        self.assertEqual(table(result)["café"]["target"]["locations"], [[0, 1, 3, 7]])
        empty = FileProvider(self.path, {"kind": "span", "start": 0, "end": 0})
        self.assertEqual(analyze_words(empty)["frequencies"], [])

    def test_bom_and_crlf_are_not_silently_rewritten(self):
        self.path.write_bytes(b"\xef\xbb\xbfOne\r\nTwo")
        result = analyze_words(self.provider)
        self.assertEqual(table(result)["two"]["target"]["locations"], [[0, 1, 6, 9]])
        self.assertEqual(result["target"]["binding"]["sha256"], sha256(self.path.read_bytes()).hexdigest())

    def test_changed_unselected_bytes_refused_even_with_identical_counts(self):
        provider = FileProvider(self.path, {"kind": "span", "start": 0, "end": 2})
        result = analyze_words(provider)
        self.path.write_text("An invented word? A word!")
        with self.assertRaises(WordStudyError) as caught:
            check_word_result(provider, result)
        self.assertEqual(caught.exception.code, "file_changed")
        self.assertEqual(caught.exception.status, "stale")

    def test_changed_reference_refused(self):
        other = self.root / "reference.txt"
        other.write_text("word")
        result = analyze_words(self.provider, reference=FileProvider(other))
        other.write_text("Word")
        with self.assertRaises(WordStudyError):
            check_word_result(self.provider, result, reference=FileProvider(other))
        with self.assertRaises(WordStudyError):
            check_word_result(self.provider, result)

    def test_file_changed_during_counting_refused(self):
        original = word_tokens

        def changed(text):
            self.path.write_text("A different input.")
            yield from original(text)

        with patch("sol.essence.essence_as_reflection_within_itself.words.word_tokens", side_effect=changed), self.assertRaises(WordStudyError) as caught:
            analyze_words(self.provider)
        self.assertEqual(caught.exception.code, "file_changed")

    def test_invalid_utf8_symlink_special_missing_and_oversize_refused(self):
        self.path.write_bytes(b"\xff")
        with self.assertRaises(WordStudyError):
            analyze_words(self.provider)
        link = self.root / "link"
        link.symlink_to(self.path)
        for path in (link, self.root):
            with self.subTest(path=path), self.assertRaises(WordStudyError):
                analyze_words(FileProvider(path))
        if hasattr(os, "mkfifo"):
            fifo = self.root / "fifo"
            os.mkfifo(fifo)
            with self.assertRaises(WordStudyError):
                analyze_words(FileProvider(fifo))
        with self.assertRaises(OSError):
            analyze_words(FileProvider(self.root / "missing"))
        from sol.essence.essence_as_reflection_within_itself.word_inputs import MAX_INPUT_BYTES
        with self.path.open("wb") as stream:
            stream.truncate(MAX_INPUT_BYTES + 1)  # Sparse, never read/allocated.
        with self.assertRaises(WordStudyError):
            analyze_words(self.provider)

    def test_replacement_while_reading_refused_even_when_bytes_match(self):
        original_fstat, calls = os.fstat, 0

        def replaced(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                content = self.path.read_bytes()
                self.path.rename(self.root / "previous.txt")
                self.path.write_bytes(content)
            return original_fstat(descriptor)

        with patch("sol.essence.essence_as_reflection_within_itself.word_inputs.os.fstat", side_effect=replaced), self.assertRaises(WordStudyError) as caught:
            analyze_words(self.provider)
        self.assertEqual(caught.exception.code, "file_changed")

    def test_invalid_scopes_and_provider_refused(self):
        for scope in ({"kind": "span", "start": True, "end": 2}, {"kind": "span", "start": 3, "end": 2},
                      {"kind": "span", "start": 0, "end": 999}, {"kind": "within", "path": "/BEING"},
                      {"kind": "file", "text": "injected"}, {"kind": []}):
            with self.subTest(scope=scope), self.assertRaises(WordStudyError):
                analyze_words(FileProvider(self.path, scope))
        with self.assertRaises(WordStudyError):
            analyze_words(self.path)

    def test_artifact_mutation_and_untrusted_json_refused(self):
        result = analyze_words(self.provider)
        for key, value in (("version", True), ("version", 2), ("method", {}), ("text", "invented")):
            altered = deepcopy(result)
            altered[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(WordStudyError):
                decode_word_result(json.dumps(altered))
        for raw in (b"\xff", '{"protocol":1,"protocol":2}', '{"bad":NaN}', "[]", "{" * 1000):
            with self.subTest(raw=raw[:60]), self.assertRaises(WordStudyError):
                decode_word_result(raw)
        altered = deepcopy(result)
        altered["target"]["inputs"][0]["text_sha256"] = "0" * 64
        with self.assertRaises(WordStudyError):
            check_word_result(self.provider, altered)
        for field, value in (("count", True), ("denominator", 10), ("rate_per_10000_tokens", 1.0),
                             ("locations", [[0, 2, 900, 904]])):
            altered = deepcopy(result)
            altered["frequencies"][0]["target"][field] = value
            with self.subTest(field=field), self.assertRaises(WordStudyError):
                check_word_result(self.provider, altered)
        with patch("sol.essence.essence_as_reflection_within_itself.words.MAX_RESULT_BYTES", 10), self.assertRaises(WordStudyError):
            encode_word_result(result)

    def test_file_api_and_cli_run_with_core_and_ui_imports_forbidden(self):
        script = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, *args):
        if name.startswith(("sol.core", "sol.corpus", "sol.reader", "sol.terminal", "sol.being.workspace", "textual", "torch")):
            raise AssertionError("Forbidden import: " + name)
sys.meta_path.insert(0, Block())
from sol.essence import FileProvider, analyze_words, check_word_result
from sol.essence.cli import main
source = FileProvider(sys.argv[1])
result = analyze_words(source)
check_word_result(source, result)
assert main(["words", "--file", sys.argv[1], "--json"]) == 0
from sol.essence.essence_as_reflection_within_itself.words import encode_word_result
from pathlib import Path
saved = Path(sys.argv[2])
saved.write_text(encode_word_result(result))
assert main(["check", str(saved), "--input-file", sys.argv[1], "--json"]) == 0
'''
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
        run = subprocess.run([sys.executable, "-B", "-c", script, str(self.path), str(self.root / "artifact.json")],
                             env=env, cwd=self.root, capture_output=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr.decode())


class CoreWordTests(CorpusFixture, unittest.TestCase):
    def source(self, scope=None):
        return CoreProvider(self.book.corpus_snapshot, scope)

    def test_core_projection_uses_shared_tokenizer(self):
        self.rewrite_body("Ground and ground. Café isn't a number: 123.")
        result = analyze_words(self.source())
        self.assertEqual(result["target"]["summary"]["token_count"], 7)
        self.assertEqual(table(result)["ground"]["target"]["count"], 2)
        self.assertEqual(result["target"]["inputs"][0]["id"], self.identifier)
        self.assertEqual(check_word_result(self.source(), result), result)

    def test_passage_span_and_section_scopes_with_unequal_reference(self):
        self.rewrite_body("Ground ground other words.")
        target = self.source({"kind": "span", "id": self.identifier, "start": 0, "end": 6})
        reference = self.source({"kind": "within", "path": "/BEING"})
        result = analyze_words(target, reference=reference)
        self.assertEqual(result["target"]["summary"]["token_count"], 1)
        self.assertEqual(result["reference"]["summary"]["token_count"], 4)
        self.assertEqual(table(result)["ground"]["reference"]["rate_per_10000_tokens"], 5000.0)
        passage = analyze_words(self.source({"kind": "passages", "ids": [self.identifier]}))
        self.assertEqual(passage["target"]["summary"]["token_count"], 4)

    def test_changed_unselected_corpus_material_refuses_old_artifact_and_snapshot(self):
        result = analyze_words(self.source({"kind": "passages", "ids": [self.identifier]}))
        old = self.source()
        rows = deepcopy(self.book.corpus_snapshot.records)
        rows[0]["markdown"] = "# A changed heading"
        rows[0]["plain_text"] = "A changed heading"
        self.write_records(rows)
        with self.assertRaises(ValueError) as caught:
            check_word_result(self.source({"kind": "passages", "ids": [self.identifier]}), result)
        self.assertEqual(caught.exception.code, "generation_changed")
        with self.assertRaises(ValueError):
            analyze_words(old)

    def test_modified_in_memory_snapshot_is_refused(self):
        self.book.corpus_snapshot.records[1]["plain_text"] = "An injected replacement."
        with self.assertRaises(ValueError) as caught:
            analyze_words(self.source())
        self.assertEqual(caught.exception.code, "snapshot_modified")

    def test_pending_editorial_generated_and_facsimile_material_is_excluded(self):
        self.add_note()
        rows = deepcopy(self.book.corpus_snapshot.records)
        original = next(row for row in rows if row["id"] == self.identifier)
        original["markdown"] = "Actual words.\n\n![Source facsimile, printed page 7](" + self.identifier + "-80.png)"
        original["plain_text"] = "Actual words.\nSource facsimile, printed page 7"
        for number, attributes in enumerate(({"transcription_status": "needs_review"},
                                              {"transcription_status": "needs_visual_review"},
                                              {"generated_text": True}), 5):
            row = deepcopy(original)
            row.pop("note_ids", None)
            row.update(id=f"bbbbbbbb-0000-4000-8000-{number:012d}", order=number, **attributes)
            rows.append(row)
        self.write_records(rows)
        result = analyze_words(self.source())
        self.assertEqual(set(table(result)), {"actual", "words"})
        self.assertEqual(result["target"]["exclusions"]["by_reason"]["review"], 2)
        self.assertEqual(result["target"]["exclusions"]["masked_tokens"], 4)

    def test_valid_empty_core_scope_and_unknown_or_malformed_scope(self):
        rows = deepcopy(self.book.corpus_snapshot.records)
        rows[1]["transcription_status"] = "needs_review"
        self.write_records(rows)
        self.assertEqual(analyze_words(self.source())["frequencies"], [])
        for scope in ({"kind": "within", "path": "/missing"}, {"kind": "within", "path": "/BEING/../x"},
                      {"kind": "passages", "ids": ["bbbb"]}, {"kind": "passages", "ids": [[]]},
                      {"kind": "passages", "ids": [self.identifier, self.identifier]},
                      {"kind": "span", "id": self.identifier, "start": 0, "end": 9999}):
            with self.subTest(scope=scope), self.assertRaises(WordStudyError):
                analyze_words(self.source(scope))

    def test_mixed_provider_comparison_warns_and_checks_both(self):
        path = self.root / "plain.txt"
        path.write_text("invented invented", encoding="utf-8")
        result = analyze_words(self.source(), reference=FileProvider(path))
        self.assertTrue(any("projections differ" in warning for warning in result["warnings"]))
        self.assertEqual(check_word_result(self.source(), result, reference=FileProvider(path)), result)
        path.write_text("changed changed")
        with self.assertRaises(WordStudyError):
            check_word_result(self.source(), result, reference=FileProvider(path))


class WordCLITests(CorpusFixture, unittest.TestCase):
    def call(self, args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = cli.main(args)
        return status, out.getvalue(), err.getvalue()

    def test_cli_matches_api_and_verifies_core_scopes(self):
        self.rewrite_body("A ground is a ground.")
        args = ["words", "--corpus", str(self.corpus), "--passage", self.identifier, "--span", "0", "8", "--compare", "--json"]
        status, out, err = self.call(args)
        self.assertEqual(status, 0, err)
        source = self.book.corpus_snapshot
        result = analyze_words(CoreProvider(source, {"kind": "span", "id": self.identifier, "start": 0, "end": 8}),
                               reference=CoreProvider(source))
        self.assertEqual(json.loads(out), result)
        saved = self.root / "words.json"
        saved.write_text(out)
        status, out, err = self.call(["check", str(saved), "--corpus", str(self.corpus), "--json"])
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)["status"], "current")

    def test_cli_file_comparison_spans_human_output_and_safe_words(self):
        path = self.root / "file.txt"
        path.write_text("α β β")
        with patch("sol.core.discover_corpus", side_effect=AssertionError("No CORE")):
            status, out, err = self.call(["words", "--file", str(path), "--span", "0", "1", "--compare"])
        self.assertEqual(status, 0, err)
        self.assertIn("1 / 1", out)
        self.assertIn("2 / 3", out)
        self.assertIn("Unequal", out)
        from sol.essence.word_cli import render_words
        result = analyze_words(FileProvider(path))
        result["frequencies"][0]["word"] += "\x1b\u202e"
        rendered = render_words(result)
        self.assertNotIn("\x1b", rendered)
        self.assertNotIn("\u202e", rendered)

    def test_cli_requires_explicit_file_and_refuses_wrong_provider_options(self):
        path = self.root / "file.txt"
        path.write_text("words")
        artifact = self.root / "words.json"
        artifact.write_text(encode_word_result(analyze_words(FileProvider(path))))
        for args in (["check", str(artifact), "--json"],
                     ["words", "--file", str(path), "--within", "/BEING", "--json"],
                     ["words", "--provider", "core", "--file", str(path), "--json"],
                     ["words", "--corpus", str(self.corpus), "--span", "0", "4", "--json"]):
            with self.subTest(args=args):
                status, out, err = self.call(args)
                self.assertEqual(status, 2)
                self.assertEqual(json.loads(out)["status"], "invalid")

    def test_file_artifact_dispatch_accepts_escaped_protocol_and_stdin(self):
        path = self.root / "file.txt"
        path.write_text("words")
        encoded = encode_word_result(analyze_words(FileProvider(path))).replace("sol.word-frequencies", "sol.\\u0077ord-frequencies")
        with patch.object(sys, "stdin", StringIO(encoded)):
            status, out, err = self.call(["check", "-", "--input-file", str(path), "--json"])
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)["status"], "current")

    def test_word_artifact_above_legacy_byte_limit_checks_from_stdin(self):
        path = self.root / "vocabulary.txt"
        def spelling(number):
            letters = []
            for _ in range(4):
                letters.append(chr(ord("a") + number % 26))
                number //= 26
            return "w" + "".join(letters)
        path.write_text(" ".join(spelling(number) for number in range(10000)))
        encoded = encode_word_result(analyze_words(FileProvider(path)))
        self.assertGreater(len(encoded), 1048576)
        with patch.object(sys, "stdin", StringIO(encoded)):
            status, out, err = self.call(["check", "-", "--input-file", str(path), "--json"])
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)["target"]["summary"]["type_count"], 10000)


if __name__ == "__main__":
    unittest.main()
