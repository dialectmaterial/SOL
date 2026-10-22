"""Provider, source-binding and compatibility checks over invented text only."""
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
import unicodedata
import unittest
from unittest.mock import patch

from sol import core
from sol.corpus import contract
from sol.essence import (CoreProvider, FileProvider, SentenceStudyError, analyze_sentences,
                         check_sentence_result, decode_sentence_result, encode_sentence_result)
from sol.essence.cli import main
from fixtures_corpus import CorpusFixture, write_runtime_corpus
from fixtures_sentence_v1 import BASELINES


def call(arguments, stdin=None):
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err), patch.object(sys, "stdin", stdin or StringIO()):
        status = main(arguments)
    return status, out.getvalue(), err.getvalue()


class FileSentenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-sentence-files-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "source.txt"
        self.text = "Café isn't e\u0301. Ω exists.\r\nA third sentence!"
        self.path.write_bytes(self.text.encode("utf-8"))
        self.provider = FileProvider(self.path)

    def test_unicode_crlf_offsets_and_file_binding_round_trip_without_text_or_paths(self):
        result = analyze_sentences(self.provider)
        self.assertEqual(result["version"], 2)
        self.assertEqual(result["input"]["binding"], {"sha256": sha256(self.text.encode()).hexdigest(),
                                                     "bytes": len(self.text.encode())})
        self.assertEqual([self.text[start:end] for _, start, end, _ in result["sentences"]],
                         ["Café isn't e\u0301.", "Ω exists.", "A third sentence!"])
        self.assertEqual([row[3] for row in result["sentences"]], [3, 2, 3])
        self.assertEqual(result["summary"]["tokens"], 8)
        self.assertEqual(result["by_position"]["middle"]["mean"], 2)
        encoded = encode_sentence_result(result)
        self.assertEqual(check_sentence_result(self.provider, decode_sentence_result(encoded)), result)
        self.assertNotIn(str(self.path), encoded)
        self.assertNotIn("Caf", encoded)
        self.assertEqual(set(result["input"]["inputs"][0]), {"text_sha256", "span", "sentences"})

    def test_spans_cutting_sentences_keep_only_original_complete_sentences(self):
        text = "First complete. Second whole sentence. Third final."
        self.path.write_text(text, encoding="utf-8")
        scope = {"kind": "span", "start": text.index("complete"), "end": text.index("final")}
        result = analyze_sentences(FileProvider(self.path, scope))
        self.assertEqual(result["sentences"], [[0, text.index("Second"), text.index(" Third"), 3]])
        self.assertEqual(result["exclusions"]["outside_span"], 2)
        self.assertEqual(result["input"]["scope"], scope)
        scope["start"] = 0
        self.assertNotEqual(result["input"]["scope"], scope)

    def test_empty_spans_empty_files_and_punctuation_have_undefined_statistics(self):
        for text, scope in (("", None), ("123 !", None), (self.text, {"kind": "span", "start": 1, "end": 1}),
                            (self.text, {"kind": "span", "start": len(self.text), "end": len(self.text)})):
            with self.subTest(text=text, scope=scope):
                self.path.write_bytes(text.encode())
                provider = FileProvider(self.path, scope)
                result = analyze_sentences(provider)
                self.assertEqual(result["sentences"], [])
                self.assertEqual(result["summary"]["tokens"], 0)
                self.assertIsNone(result["summary"]["mean"])
                self.assertIsNone(result["summary"]["p90"])
                self.assertEqual(check_sentence_result(provider, result), result)

    def test_utf8_bom_remains_in_the_binding_and_offset_coordinate_system(self):
        raw = b"\xef\xbb\xbf" + "Café. Other.".encode()
        self.path.write_bytes(raw)
        result = analyze_sentences(self.provider)
        self.assertEqual(result["input"]["binding"]["sha256"], sha256(raw).hexdigest())
        self.assertEqual(result["sentences"], [[0, 0, 6, 1], [0, 7, 13, 1]])

    def test_invalid_and_out_of_range_scopes_are_refused(self):
        for scope in ({"kind": "corpus"}, {"kind": "span", "start": True, "end": 3},
                      {"kind": "span", "start": 4, "end": 3}, {"kind": "span", "start": -1, "end": 3},
                      {"kind": "span", "start": 0, "end": len(self.text) + 1}):
            with self.subTest(scope=scope), self.assertRaises(SentenceStudyError):
                analyze_sentences(FileProvider(self.path, scope))
        with self.assertRaisesRegex(SentenceStudyError, "on the provider"):
            analyze_sentences(self.provider, scope={"kind": "file"})

    def test_regular_utf8_file_and_size_guards_are_shared_with_the_word_engine(self):
        link = self.root / "link.txt"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(SentenceStudyError, "regular file"):
            analyze_sentences(FileProvider(link))
        self.path.write_bytes(b"\xff")
        with self.assertRaisesRegex(SentenceStudyError, "UTF-8"):
            analyze_sentences(self.provider)
        with self.path.open("wb") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
        with self.assertRaises(SentenceStudyError) as caught:
            analyze_sentences(self.provider)
        self.assertEqual(caught.exception.code, "size_limit")

    def test_file_change_even_outside_the_selected_span_is_stale(self):
        provider = FileProvider(self.path, {"kind": "span", "start": 0, "end": len("Café isn't e\u0301.")})
        result = analyze_sentences(provider)
        self.path.write_bytes((self.text + " ").encode())
        with self.assertRaises(SentenceStudyError) as caught:
            check_sentence_result(provider, result)
        self.assertEqual((caught.exception.status, caught.exception.code), ("stale", "file_changed"))

    def test_a_file_changed_during_analysis_is_refused(self):
        from sol.essence.essence_as_reflection_within_itself.sentences import segment
        def change(text):
            self.path.write_bytes((text + " ").encode())
            return segment(text)
        with patch("sol.essence.essence_as_reflection_within_itself.sentence_inputs.segment", side_effect=change), self.assertRaises(SentenceStudyError) as caught:
            analyze_sentences(self.provider)
        self.assertEqual(caught.exception.code, "file_changed")

    def test_tampered_rows_metadata_method_and_statistics_are_refused(self):
        original = analyze_sentences(self.provider)
        changes = [lambda r: r["sentences"][0].__setitem__(1, 1),
                   lambda r: r["input"]["inputs"][0].__setitem__("text_sha256", "0" * 64),
                   lambda r: r["method"].__setitem__("algorithm", "unreviewed"),
                   lambda r: r["summary"].__setitem__("tokens", 999),
                   lambda r: r["input"]["binding"].__setitem__("path", "/untrusted/file")]
        for change in changes:
            altered = deepcopy(original)
            change(altered)
            with self.subTest(change=change), self.assertRaises(ValueError):
                check_sentence_result(self.provider, altered)

    def test_decoder_refuses_duplicate_fields_nonfinite_values_and_unknown_versions(self):
        encoded = encode_sentence_result(analyze_sentences(self.provider))
        for altered in (encoded.replace('"version":2', '"version":2,"version":2'),
                        encoded.replace('"mean":', '"mean":NaN,"ignored":', 1),
                        encoded.replace('"version":2', '"version":3')):
            with self.subTest(data=altered[:30]), self.assertRaises(ValueError):
                decode_sentence_result(altered)

    def test_v2_transport_has_room_for_provenance_while_v1_keeps_its_original_bound(self):
        encoded = encode_sentence_result(analyze_sentences(self.provider))
        self.assertEqual(decode_sentence_result(" " * 1048576 + encoded), json.loads(encoded))
        with self.assertRaisesRegex(SentenceStudyError, "16 MiB"):
            decode_sentence_result(b" " * (16 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(SentenceStudyError, "1 MiB"):
            decode_sentence_result(" " * 1048576 + BASELINES["corpus"])

    def test_file_anchor_is_rejected_before_any_source_is_opened(self):
        with patch("sol.essence.essence_as_reflection_within_itself.sentence_inputs.load_input", side_effect=AssertionError("No source open")):
            with self.assertRaisesRegex(SentenceStudyError, "reference anchor"):
                analyze_sentences(self.provider, origin={})

    def test_cli_file_and_span_check_require_explicit_paths_and_preserve_scope(self):
        status, out, err = call(["sentences", "--file", str(self.path), "--span", "0", str(len("Café isn't e\u0301.")), "--json"])
        self.assertEqual(status, 0, err)
        result = json.loads(out)
        saved = self.root / "study.json"
        saved.write_text(out)
        self.assertEqual(result["summary"]["sentences"], 1)
        for name in (str(saved), "-"):
            status, checked, err = call(["check", name, "--input-file", str(self.path), "--json"], StringIO(out))
            self.assertEqual(status, 0, err)
            self.assertEqual(json.loads(checked)["status"], "current")
        self.assertEqual(call(["check", str(saved)])[0], 2)
        self.path.write_bytes((self.text + ".").encode())
        status, out, _ = call(["check", str(saved), "--input-file", str(self.path), "--json"])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(out)["code"], "file_changed")

    def test_cli_rejects_incompatible_source_scope_and_anchor_options(self):
        for extra in (["--within", "/BEING"], ["--corpus", str(self.root)], ["--reference", "not-opened"],
                      ["--span", "-1", "2"]):
            with self.subTest(extra=extra):
                status, out, err = call(["sentences", "--file", str(self.path), *extra])
                self.assertEqual((status, out), (2, ""))
                self.assertTrue(err)

    def test_installed_dispatch_runs_a_file_study_with_no_configured_corpus(self):
        environment = {**os.environ, **{f"XDG_{name}_HOME": str(self.root / name.lower())
                                       for name in ("CONFIG", "DATA", "STATE", "CACHE")}}
        completed = subprocess.run([sys.executable, "-B", "-m", "sol", "essence", "sentences",
                                    "--file", str(self.path), "--json"], capture_output=True, text=True,
                                   env=environment, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["input"]["provider"], "file")

    def test_file_api_and_essence_cli_import_no_core_corpus_reader_or_interface(self):
        script = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, *args):
        if name.startswith(('sol.core','sol.corpus','sol.reader','sol.terminal','sol.essence.tui','textual')):
            raise AssertionError('Forbidden import: ' + name)
sys.meta_path.insert(0, Block())
from pathlib import Path
from sol.essence import FileProvider, analyze_sentences, check_sentence_result, encode_sentence_result, decode_sentence_result
from sol.essence.cli import main
provider = FileProvider(sys.argv[1])
result = analyze_sentences(provider)
assert check_sentence_result(provider, decode_sentence_result(encode_sentence_result(result))) == result
Path(sys.argv[2]).write_text(encode_sentence_result(result))
assert main(['sentences', '--file', sys.argv[1], '--json']) == 0
assert main(['check', sys.argv[2], '--input-file', sys.argv[1]]) == 0
'''
        completed = subprocess.run([sys.executable, "-B", "-c", script, str(self.path), str(self.root / "study.json")],
                                   cwd=self.root, env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
                                   capture_output=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())


class CoreSentenceTests(CorpusFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.text = "First complete. Second whole sentence. Third final."
        self.rewrite_body(self.text)
        self.snapshot = self.book.corpus_snapshot

    def test_provider_scopes_keep_canonical_identity_and_match_legacy_statistics(self):
        legacy = analyze_sentences(self.snapshot)
        scopes = [None, {"kind": "within", "path": "/BEING"}, {"kind": "passages", "ids": [self.identifier]}]
        for scope in scopes:
            provider = CoreProvider(self.snapshot, scope)
            result = analyze_sentences(provider)
            self.assertEqual(result["summary"], legacy["summary"])
            self.assertEqual(result["sentences"], legacy["sentences"])
            self.assertEqual(result["input"]["inputs"][0]["id"], self.identifier)
            self.assertEqual(check_sentence_result(provider, result), result)
            self.assertNotIn("First complete", encode_sentence_result(result))

    def test_core_span_cuts_sentences_without_inventing_fragments(self):
        scope = {"kind": "span", "id": self.identifier, "start": 6, "end": self.text.index("final")}
        provider = CoreProvider(self.snapshot, scope)
        origin = core.capture_reference(self.snapshot, self.identifier)
        result = analyze_sentences(provider, origin=origin)
        self.assertEqual(result["sentences"], [[0, 16, 38, 3]])
        self.assertEqual(result["exclusions"]["outside_span"], 2)
        self.assertEqual(result["origin"], origin)
        self.assertEqual(check_sentence_result(provider, result), result)
        with self.assertRaises(SentenceStudyError):
            check_sentence_result(CoreProvider(self.snapshot), result)

    def test_pending_review_exclusion_and_unknown_scopes(self):
        records = deepcopy(self.snapshot.records)
        records[1]["transcription_status"] = "needs_visual_review"
        self.write_records(records)
        result = analyze_sentences(CoreProvider(self.book.corpus_snapshot))
        self.assertEqual(result["summary"]["sentences"], 0)
        self.assertEqual(result["exclusions"]["by_reason"]["review"], 1)
        for scope in ({"kind": "passages", "ids": ["unknown"]},
                      {"kind": "span", "id": self.identifier, "start": 0, "end": 9999}):
            with self.subTest(scope=scope), self.assertRaises(SentenceStudyError):
                analyze_sentences(CoreProvider(self.book.corpus_snapshot, scope))

    def test_core_generation_and_in_memory_changes_are_refused(self):
        result = analyze_sentences(CoreProvider(self.snapshot))
        altered = deepcopy(self.snapshot)
        altered.records[1]["plain_text"] += " Different."
        with self.assertRaises(SentenceStudyError):
            analyze_sentences(CoreProvider(altered))
        self.rewrite_body(self.text + " Changed.")
        with self.assertRaises(SentenceStudyError) as caught:
            check_sentence_result(CoreProvider(self.book.corpus_snapshot), result)
        self.assertEqual(caught.exception.code, "generation_changed")

    def test_cli_core_span_and_v1_verification_both_work(self):
        status, out, err = call(["sentences", "--corpus", str(self.corpus), "--passage", self.identifier,
                                 "--span", "6", str(self.text.index("final")), "--json"])
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)["summary"]["sentences"], 1)
        for result in (json.loads(out), analyze_sentences(self.snapshot)):
            saved = self.root / "study.json"
            saved.write_text(encode_sentence_result(result))
            status, receipt, err = call(["check", str(saved), "--corpus", str(self.corpus), "--json"])
            self.assertEqual(status, 0, err)
            self.assertEqual(json.loads(receipt)["status"], "current")


class SentenceV1CompatibilityTests(unittest.TestCase):
    def test_four_original_v1_artifacts_still_recompute_and_encode_byte_for_byte(self):
        # Captured from main at 759338c before any implementation changes.
        with tempfile.TemporaryDirectory(prefix="sol-sentence-v1-") as root:
            corpus = Path(root) / "corpus"
            write_runtime_corpus(corpus)
            manifest_path = corpus / "corpus.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["corpus_id"] = "eeeeeeee-0000-4000-8000-000000000001"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            contract.reindex(corpus)
            snapshot = core.load_snapshot(corpus)
            for label, encoded in BASELINES.items():
                with self.subTest(label=label):
                    old_unicode = json.loads(encoded)["method"]["unicode_version"]
                    encoded = encoded.replace(f'"unicode_version":"{old_unicode}"',
                                              f'"unicode_version":"{unicodedata.unidata_version}"')
                    original = decode_sentence_result(encoded)
                    fresh = analyze_sentences(snapshot, scope=original["scope"], origin=original["origin"])
                    self.assertEqual(encode_sentence_result(fresh), encoded)
                    self.assertEqual(encode_sentence_result(check_sentence_result(snapshot, original)), encoded)
