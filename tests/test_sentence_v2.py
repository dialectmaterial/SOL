"""Punctuation-method v2 rules and artifact dispatch; all prose is invented."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import unicodedata

from fixtures_corpus import CorpusFixture
from fixtures_sentence_provider_v1 import BASELINE
from sol import core
from sol.essence import CoreProvider

from sol.essence import (FileProvider, SentenceStudyError, analyze_sentences,
                         check_sentence_result, decode_sentence_result, encode_sentence_result)
from sol.essence.essence_as_reflection_within_itself.sentences import (
    _ABBREVIATIONS_V2, segment, segment_v2,
)
from test_sentence_providers import call


class PunctuationV2Tests(unittest.TestCase):
    def split(self, text):
        return [text[a:b] for a, b in segment_v2(text)]

    def test_line_leading_numbers_stay_with_the_item_including_offsets(self):
        for prefix in ("1.", "23.", "  7.", "\t9."):
            text = prefix + " A lantern glows. Another dims."
            with self.subTest(prefix=prefix):
                self.assertEqual(self.split(text), [(prefix + " A lantern glows.").strip(), "Another dims."])
                first = len(text) - len(text.lstrip())
                self.assertEqual(segment_v2(text)[0], (first, text.index(" Another")))
        self.assertEqual(self.split("1. A lantern glows.\n2. A second dims."),
                         ["1. A lantern glows.", "2. A second dims."])
        # Only a line-leading integer marker changes; ordinary final numbers
        # and logical variables still terminate a sentence.
        self.assertEqual(self.split("The count is 3. A letter is P. Next."),
                         ["The count is 3.", "A letter is P.", "Next."])
        self.assertEqual(["1.", "A lantern glows."],
                         ["1. A lantern glows."[a:b] for a, b in segment("1. A lantern glows.")])

    def test_numeric_callouts_stay_with_preceding_punctuation(self):
        for suffix in ("12", "[12]", "¹²"):
            for punctuation in (".", "!", "?", "…"):
                text = "A lantern glows" + punctuation + suffix + " Another dims."
                with self.subTest(suffix=suffix, punctuation=punctuation):
                    self.assertEqual(self.split(text), [text[:text.index(" Another")], "Another dims."])
                    self.assertEqual(segment_v2(text)[0][1], text.index(" Another"))
        self.assertEqual(self.split("“A lantern glows.”12 Another dims."),
                         ["“A lantern glows.”12", "Another dims."])
        self.assertEqual(self.split("(A lantern glows.12) Another dims."),
                         ["(A lantern glows.12)", "Another dims."])
        self.assertEqual(self.split("A lantern glows.12"), ["A lantern glows.12"])
        self.assertEqual(self.split("A lantern glows.12 another dims."),
                         ["A lantern glows.12 another dims."])

    def test_callout_guard_preserves_decimals_and_ordinary_numbers(self):
        text = "A value is 0.25 Approximately. A second is 2. Next."
        self.assertEqual(self.split(text), ["A value is 0.25 Approximately.", "A second is 2.", "Next."])
        # A number after whitespace is not consumed as an attached callout.
        self.assertEqual(self.split("A lantern glows. 12 lamps dim."),
                         ["A lantern glows.", "12 lamps dim."])
        self.assertEqual(self.split("See p.12 Another table."), ["See p.12 Another table."])

    def test_every_declared_abbreviation_before_a_capital_is_retained(self):
        for abbreviation in sorted(_ABBREVIATIONS_V2):
            with self.subTest(abbreviation=abbreviation):
                text = f"See {abbreviation}. Amber notes. Next."
                self.assertEqual(self.split(text), [f"See {abbreviation}. Amber notes.", "Next."])
        self.assertEqual(self.split("See p. 8, pp. 9–10 and § 3; cf. Ash. Next."),
                         ["See p. 8, pp. 9–10 and § 3; cf. Ash.", "Next."])

    def test_initial_chains_and_uppercase_logical_letters(self):
        self.assertEqual(self.split("A. B. C. Alder wrote. The value is P. Next."),
                         ["A. B. C. Alder wrote.", "The value is P.", "Next."])

    def test_ellipses_quotes_brackets_semicolons_and_colons(self):
        cases = (
            ("A pause… Then speech.", ["A pause…", "Then speech."]),
            ("A pause . . . then speech.", ["A pause . . . then speech."]),
            ("A pause . . . Then speech.", ["A pause . . .", "Then speech."]),
            ('“A lantern glows.” [Another dims.] Next.', ['“A lantern glows.”', '[Another dims.]', 'Next.']),
            ("A lantern (see Fig. IV) glows. Next.", ["A lantern (see Fig. IV) glows.", "Next."]),
            ("A lantern glows; Another dims: Both fade.", ["A lantern glows; Another dims: Both fade."]),
            ("(A lantern glows. Another dims.) Next.", ["(A lantern glows.", "Another dims.)", "Next."]),
        )
        for text, gold in cases:
            with self.subTest(text=text):
                self.assertEqual(self.split(text), gold)

    def test_other_v1_limits_are_explicitly_retained(self):
        for text in ("A parcel\narrives.", "Consult ibid. Another report.",
                     "One ends. another begins.", "A report (A bell rang. Another rang.) arrives."):
            with self.subTest(text=text):
                self.assertEqual(segment_v2(text), segment(text))


class SentenceMethodTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-sentence-v2-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "input.txt"
        self.text = "1. A lantern glows.12 Another dims."
        self.path.write_text(self.text)
        self.provider = FileProvider(self.path)

    def test_both_provider_methods_encode_decode_and_check_by_recorded_method(self):
        for method in ("punctuation-rules-v1", "punctuation-rules-v2"):
            with self.subTest(method=method):
                result = analyze_sentences(self.provider, segmentation=method)
                self.assertTrue(result["method"]["segmentation"].startswith(method + ":"))
                self.assertEqual(result["version"], 2)  # artifact protocol, not punctuation version
                self.assertEqual(check_sentence_result(self.provider, decode_sentence_result(
                    encode_sentence_result(result))), result)
        self.assertEqual(analyze_sentences(self.provider),
                         analyze_sentences(self.provider, segmentation="punctuation-rules-v1"))
        result = analyze_sentences(self.provider, segmentation="punctuation-rules-v2")
        self.assertEqual(result["sentences"], [[0, 0, 21, 3], [0, 22, len(self.text), 2]])

    def test_provider_v1_artifact_from_main_still_checks_and_encodes_byte_for_byte(self):
        # Captured from origin/main 6ae639d, before this implementation.
        encoded = BASELINE
        old_unicode = json.loads(encoded)["method"]["unicode_version"]
        encoded = encoded.replace(f'"unicode_version":"{old_unicode}"',
                                  f'"unicode_version":"{unicodedata.unidata_version}"')
        saved = decode_sentence_result(encoded)
        self.assertEqual(encode_sentence_result(analyze_sentences(self.provider)), encoded)
        self.assertEqual(encode_sentence_result(check_sentence_result(self.provider, saved)), encoded)

    def test_changed_method_cannot_relabel_existing_rows(self):
        old = analyze_sentences(self.provider)
        fresh = analyze_sentences(self.provider, segmentation="punctuation-rules-v2")
        old["method"] = fresh["method"]
        with self.assertRaises(SentenceStudyError) as caught:
            check_sentence_result(self.provider, old)
        self.assertEqual(caught.exception.code, "result_mismatch")
        altered = deepcopy(fresh)
        altered["method"]["abbreviations"].append("invented")
        with self.assertRaises(SentenceStudyError) as caught:
            decode_sentence_result(encode_sentence_result(altered))
        self.assertEqual(caught.exception.code, "unsupported_method")
        with self.assertRaises(SentenceStudyError):
            analyze_sentences(self.provider, segmentation="punctuation-rules-v99")

    def test_span_filter_runs_after_v2_segmentation(self):
        provider = FileProvider(self.path, {"kind": "span", "start": 1, "end": len(self.text)})
        result = analyze_sentences(provider, segmentation="punctuation-rules-v2")
        self.assertEqual(result["sentences"], [[0, 22, len(self.text), 2]])
        self.assertEqual(result["exclusions"]["outside_span"], 1)
        self.assertEqual(check_sentence_result(provider, result), result)

    def test_cli_selects_and_renders_both_methods_and_checks_without_an_override(self):
        for method in ("punctuation-rules-v1", "punctuation-rules-v2"):
            with self.subTest(method=method):
                args = ["sentences", "--file", str(self.path), "--segmentation", method]
                status, rendered, err = call(args)
                self.assertEqual(status, 0, err)
                self.assertIn(method + " on the original text", rendered)
                status, out, err = call(args + ["--json"])
                self.assertEqual(status, 0, err)
                saved = self.path.with_suffix(".json")
                saved.write_text(out)
                self.assertEqual(json.loads(out)["version"], 2)
                self.assertEqual(call(["check", str(saved), "--input-file", str(self.path)])[0], 0)


class CoreSentenceV2Tests(CorpusFixture, unittest.TestCase):
    def test_explicit_core_method_selection_and_cli_do_not_change_legacy(self):
        snapshot = self.book.corpus_snapshot
        provider = CoreProvider(snapshot)
        old = analyze_sentences(snapshot)
        for method in ("punctuation-rules-v1", "punctuation-rules-v2"):
            result = analyze_sentences(provider, segmentation=method,
                                       origin=core.capture_reference(snapshot, self.identifier))
            self.assertEqual(check_sentence_result(provider, result), result)
            status, out, err = call(["sentences", "--corpus", str(self.corpus),
                                     "--segmentation", method, "--json"])
            self.assertEqual(status, 0, err)
            self.assertEqual(json.loads(out)["version"], 2)
            self.assertTrue(json.loads(out)["method"]["segmentation"].startswith(method + ":"))
        self.assertEqual(old, analyze_sentences(snapshot))
        self.assertEqual(check_sentence_result(snapshot, old), old)
        with self.assertRaisesRegex(SentenceStudyError, "explicit CoreProvider"):
            analyze_sentences(snapshot, segmentation="punctuation-rules-v2")
