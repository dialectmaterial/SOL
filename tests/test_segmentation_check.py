"""Synthetic gold annotations; no book sample or human-review claim in Git."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import os
import unittest
from unittest.mock import patch

from fixtures_corpus import CorpusFixture
from sol import core
from sol.essence import cli
from sol.essence.segmentation_check import (
    DOCTRINES, compare_sample, compare_text, decode_sample, prepare_sample, write_sample,
)
from sol.essence.sentences import analyze_sentences, encode_sentence_result, segment


PARENTHETICAL = ["The diary says (A bell rang.", "Another bell answered.) before its owner leaves."]
WRAPPED = "The traveller carried\nan unopened letter."


class BoundaryComparisonTests(unittest.TestCase):
    def test_counts_false_splits_and_misses_without_scoring_obligatory_ends(self):
        gold = ["A first line\ncontinues.", "another starts.", "Last ends."]
        text = " ".join(gold)
        result = compare_text(text, gold)
        self.assertEqual((result["true_positives"], result["false_splits"], result["misses"]), (1, 1, 1))
        self.assertEqual((result["precision"], result["recall"], result["f1"]), (0.5, 0.5, 0.5))
        self.assertEqual(result["false_split_offsets"], [text.index("\n")])
        self.assertEqual(result["missed_offsets"], [len(gold[0])])
        self.assertEqual((result["predicted_boundaries"], result["gold_boundaries"]), (2, 2))

    def test_unicode_and_repeated_sentences_use_exact_sequential_codepoints(self):
        gold = ["𝔸 carries e\u0301 and 界.", "Same words.", "Same words."]
        text = "  " + "  ".join(gold) + " \n"
        result = compare_text(text, gold)
        self.assertEqual(result["true_positives"], 2)
        self.assertEqual(result["f1"], 1)
        self.assertEqual(result["missed_offsets"], [])
        self.assertNotEqual(len(gold[0]), len(gold[0].encode("utf-8")))

    def test_zero_internal_boundaries_have_undefined_rates_not_perfect_accuracy(self):
        for text, gold in (("Only one thought.", ["Only one thought."]), ("  ", [])):
            result = compare_text(text, gold)
            self.assertIsNone(result["precision"])
            self.assertIsNone(result["recall"])
            self.assertIsNone(result["f1"])
            self.assertEqual(result["gold_boundaries"], 0)

    def test_annotations_cannot_drop_repeat_correct_or_normalize_the_source(self):
        text = "One thought. Another thought."
        for gold in (None, [], ["One thought."], ["A corrected thought.", "Another thought."],
                     [" One thought.", "Another thought."], ["Another thought.", "One thought."],
                     ["One thought.", "One thought.", "Another thought."], ["", text]):
            with self.subTest(gold=gold), self.assertRaises(ValueError):
                compare_text(text, gold)
        with self.assertRaises(ValueError):
            compare_text("e\u0301 remains.", ["é remains."])

    def test_representative_correct_hard_cases(self):
        for gold in (["Mr. Rowan cited e.g. a report.", "Then he left."],
                     ["G. W. P. Rowan spoke.", "A reply followed."],
                     ["The value is 3.14.", "Next comes another."],
                     ['She said, “The bell rang.”', "Then silence followed."],
                     ["A first thought.", "— Another begins!", "Does it?", "Yes."],
                     ["(One account ends.", "Another follows.)", "More follows."]):
            with self.subTest(gold=gold):
                self.assertEqual(compare_text(" ".join(gold), gold)["f1"], 1)


class KnownRuleLimitations(unittest.TestCase):
    """Human-desired boundaries deliberately fail against the frozen v1 method.

    Unexpected success requires reviewing a method change, not updating gold to
    whatever the algorithm predicts. The scorer also measures these errors in
    ordinary passing tests above and below.
    """
    @unittest.expectedFailure
    def test_sentence_inside_parenthesis_opened_mid_sentence(self):
        text = " ".join(PARENTHETICAL)
        self.assertEqual([text[a:b] for a, b in segment(text)], PARENTHETICAL)

    @unittest.expectedFailure
    def test_physical_line_break_inside_a_sentence_is_not_a_sentence_boundary(self):
        self.assertEqual([WRAPPED[a:b] for a, b in segment(WRAPPED)], [WRAPPED])

    @unittest.expectedFailure
    def test_an_abbreviation_can_also_end_a_sentence(self):
        gold = ["Consult ibid.", "Another account follows."]
        text = " ".join(gold)
        self.assertEqual([text[a:b] for a, b in segment(text)], gold)

    @unittest.expectedFailure
    def test_lowercase_sentence_start_is_a_boundary_when_marked_by_a_reviewer(self):
        gold = ["One event ends.", "another begins."]
        text = " ".join(gold)
        self.assertEqual([text[a:b] for a, b in segment(text)], gold)


class SegmentationSampleTests(CorpusFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        records = [deepcopy(next(row for row in self.book.canonical_records.values() if row["type"] == "section"))]
        original = deepcopy(self.book.canonical_records[self.identifier])
        self.gold = {}
        for doctrine in DOCTRINES:
            for number in range(2):
                sentences = ([WRAPPED] if (doctrine, number) == ("ESSENCE", 0) else
                             PARENTHETICAL if (doctrine, number) == ("BEING", 0) else
                             [f"The {doctrine.lower()} example ends.", "Another invented claim begins."])
                body = " ".join(sentences)
                row = deepcopy(original)
                row.update(id=f"cccccccc-0000-4000-8000-{len(records):012d}", order=len(records),
                           reader_path=f"/{doctrine}/invented.txt", markdown=body, plain_text=body)
                records.append(row)
                self.gold[row["id"]] = list(sentences)
        flagged = deepcopy(records[-1])
        flagged.update(id="dddddddd-0000-4000-8000-000000000100", order=len(records), transcription_status="needs_review")
        records.append(flagged)
        self.write_records(records)
        self.snapshot = core.load_snapshot(self.corpus)
        self.environment = {name: str(self.root / suffix) for name, suffix in (
            ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
            ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state"), ("NVIM_LOG_FILE", "nvim.log"))}

    def marked(self, per_doctrine=2):
        sample = prepare_sample(self.snapshot, per_doctrine=per_doctrine, seed=20261018)
        sample["reviewer"] = "Invented annotator, synthetic fixtures only"
        for row in sample["passages"]:
            row["gold_sentences"] = self.gold[row["id"]]
        return sample

    def call(self, arguments):
        output, errors = StringIO(), StringIO()
        with patch.dict(os.environ, self.environment), redirect_stdout(output), redirect_stderr(errors):
            status = cli.main([*arguments, "--corpus", str(self.corpus)])
        return status, output.getvalue(), errors.getvalue()

    def test_sampling_is_blind_balanced_reproducible_and_read_only(self):
        before = self.files()
        sample = prepare_sample(self.snapshot, per_doctrine=1, seed=7)
        self.assertEqual(sample, prepare_sample(self.snapshot, per_doctrine=1, seed=7))
        self.assertEqual(sorted(row["doctrine"] for row in sample["passages"]), sorted(DOCTRINES))
        self.assertEqual(sample["sampling"]["population"], dict.fromkeys(DOCTRINES, 2))
        self.assertEqual(sample["reviewer"], "")
        for row in sample["passages"]:
            self.assertIsNone(row["gold_sentences"])
            self.assertNotIn("sentences", row)
            self.assertNotIn("predicted", row)
            self.assertNotIn("transcription_status", row)
        self.assertEqual(self.files(), before)

    def test_sampling_reports_an_unexpected_doctrine_path_clearly(self):
        study = analyze_sentences(self.snapshot)
        for path in ("/OTHER/invented.txt", "/", "BEING/invented.txt", "", None):
            with self.subTest(path=path):
                unexpected = deepcopy(study)
                unexpected["passages"][0]["reader_path"] = path
                with patch("sol.essence.segmentation_check.analyze_sentences", return_value=unexpected):
                    with self.assertRaisesRegex(ValueError, "/BEING, /ESSENCE or /CONCEPT"):
                        prepare_sample(self.snapshot, per_doctrine=1, seed=7)

    def test_metrics_account_for_misses_false_splits_and_doctrines(self):
        result = compare_sample(self.snapshot, self.marked())
        counts = result["summary"]
        self.assertEqual((counts["passages"], counts["passages_with_errors"]), (6, 2))
        self.assertEqual((counts["true_positives"], counts["false_splits"], counts["misses"]), (4, 1, 1))
        self.assertEqual((counts["precision"], counts["recall"], counts["f1"]), (0.8, 0.8, 0.8))
        self.assertEqual(result["by_doctrine"]["BEING"]["recall"], 0.5)
        self.assertEqual(result["by_doctrine"]["ESSENCE"]["precision"], 0.5)
        self.assertEqual(result["by_doctrine"]["CONCEPT"]["f1"], 1)
        self.assertTrue(all("text" not in row and "gold_sentences" not in row for row in result["passages"]))
        self.assertNotIn(self.marked()["passages"][0]["text"], json.dumps(result))

    def test_pending_empty_and_all_excluded_reviews_are_refused(self):
        for change in (lambda s: s.update(reviewer=""),
                       lambda s: s["passages"][0].update(gold_sentences=None),
                       lambda s: [row.update(gold_sentences=None, exclude_reason="Not adjudicated") for row in s["passages"]]):
            sample = self.marked()
            change(sample)
            with self.assertRaises(ValueError):
                compare_sample(self.snapshot, sample)

    def test_exclusions_remain_visible_with_their_reasons(self):
        sample = self.marked()
        sample["passages"][0].update(gold_sentences=None, exclude_reason="Ambiguous aside; needs a second reviewer")
        result = compare_sample(self.snapshot, sample)
        self.assertEqual(result["summary"]["passages"], 5)
        self.assertEqual(result["excluded_passages"][0]["id"], sample["passages"][0]["id"])
        self.assertIn("second reviewer", result["excluded_passages"][0]["reason"])

    def test_source_selection_binding_and_order_cannot_be_changed(self):
        for change in (lambda s: s["generation"].update(index_sha256="0" * 64),
                       lambda s: s["method"].update(algorithm="another-method"),
                       lambda s: s["passages"].pop(),
                       lambda s: s["passages"].reverse(),
                       lambda s: s["passages"][0].update(text="A replacement.", gold_sentences=["A replacement."]),
                       lambda s: s["passages"][0].update(content_sha256="0" * 64),
                       lambda s: s["passages"][0].update(exclude_reason=""),
                       lambda s: s["passages"].__setitem__(0, deepcopy(s["passages"][1]))):
            sample = self.marked()
            change(sample)
            with self.assertRaises(ValueError):
                compare_sample(self.snapshot, sample)

    def test_corpus_change_refuses_old_review_and_does_not_repair_it(self):
        sample = self.marked()
        (self.corpus / "sample.md").write_text("Changed canonical source.")
        with self.assertRaises(ValueError):
            compare_sample(self.snapshot, sample)

    def test_size_and_seed_are_explicit_and_cannot_silently_shrink(self):
        for count, seed in ((0, 1), (True, 1), (3, 1), (1, True), (1, -1), (1, 2**32)):
            with self.subTest(count=count, seed=seed), self.assertRaises(ValueError):
                prepare_sample(self.snapshot, per_doctrine=count, seed=seed)

    def test_review_preserves_existing_sentence_artifacts_and_source_bytes(self):
        artifact = encode_sentence_result(analyze_sentences(self.snapshot))
        before = self.files()
        compare_sample(self.snapshot, self.marked())
        self.assertEqual(encode_sentence_result(analyze_sentences(self.snapshot)), artifact)
        self.assertEqual(self.files(), before)

    def test_private_writer_refuses_overwrite_symlinks_and_git_checkouts(self):
        path = self.root / "private-review.json"
        write_sample(self.marked(), path)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            write_sample(self.marked(), path)
        link = self.root / "link.json"
        link.symlink_to(path)
        with self.assertRaises(FileExistsError):
            write_sample(self.marked(), link)
        (self.root / ".git").mkdir()
        (self.root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        with self.assertRaisesRegex(ValueError, "outside every Git"):
            write_sample(self.marked(), self.root / "forbidden.json")

    def test_cli_prepares_then_checks_a_private_sample_without_reader_or_workspace(self):
        path = self.root / "review.json"
        code, output, errors = self.call(["segmentation-sample", "--per-doctrine", "2", "--seed", "20261018",
                                          "--output", str(path), "--json"])
        self.assertEqual(code, 0, errors)
        self.assertEqual(json.loads(output)["status"], "unmarked")
        code, _, errors = self.call(["segmentation-check", str(path)])
        self.assertEqual(code, 2)
        self.assertIn("reviewer", errors)
        path.write_text(json.dumps(self.marked()), encoding="utf-8")
        code, output, errors = self.call(["segmentation-check", str(path), "--json"])
        self.assertEqual(code, 0, errors)
        self.assertEqual(json.loads(output)["summary"]["misses"], 1)
        code, output, errors = self.call(["segmentation-check", str(path)])
        self.assertEqual(code, 0, errors)
        self.assertIn("1 false splits, 1 misses", output)
        self.assertIn("80.00%", output)
        self.assertFalse((self.root / "data").exists())

    def test_decoder_rejects_duplicate_nonfinite_oversized_and_invalid_inputs(self):
        for raw in (b'{"review_version":1,"review_version":1}', b'{"x":NaN}', b'{"x":1e999}',
                    b'\xff', b'[]', b'not json'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                decode_sample(raw)
        with patch("sol.essence.segmentation_check.MAX_REVIEW_BYTES", 10), self.assertRaises(ValueError):
            decode_sample(json.dumps(self.marked()))


if __name__ == "__main__":
    unittest.main()
