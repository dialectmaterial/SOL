"""Invented text-editor forms only; no private book samples or markings."""
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
from sol.essence.segmentation_check import compare_sample, prepare_sample, write_sample
from sol.essence.segmentation_marking import (
    decode_marking_form, export_marking_form, import_marking_form, write_marking_form,
)
from sol.essence.sentences import analyze_sentences, encode_sentence_result


class SegmentationMarkingTests(CorpusFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        records = [deepcopy(next(row for row in self.book.canonical_records.values() if row["type"] == "section"))]
        original = deepcopy(self.book.canonical_records[self.identifier])
        self.gold = {}
        for doctrine in ("BEING", "ESSENCE", "CONCEPT"):
            for number in range(2):
                sentences = (["The traveller carried\nan unopened letter."] if (doctrine, number) == ("ESSENCE", 0)
                             else ["The diary says (A bell rang.", "Another bell answered.) before its owner leaves."]
                             if (doctrine, number) == ("BEING", 0)
                             else [f"The {doctrine.lower()} example ends.", "Another invented claim begins."])
                text = " ".join(sentences)
                row = deepcopy(original)
                row.update(id=f"eeeeeeee-0000-4000-8000-{len(records):012d}", order=len(records),
                           reader_path=f"/{doctrine}/invented.txt", markdown=text, plain_text=text)
                records.append(row)
                self.gold[row["id"]] = sentences
        self.write_records(records)
        self.snapshot = core.load_snapshot(self.corpus)
        self.sample = prepare_sample(self.snapshot, per_doctrine=2, seed=20261018)
        self.form = export_marking_form(self.snapshot, self.sample)
        self.environment = {name: str(self.root / suffix) for name, suffix in (
            ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
            ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state"), ("NVIM_LOG_FILE", "nvim.log"))}

    def marked_form(self):
        form = self.form
        for row in self.sample["passages"]:
            cursor, ends = 0, []
            for sentence in self.gold[row["id"]][:-1]:
                cursor = row["text"].index(sentence, cursor) + len(sentence)
                ends.append(cursor)
            body = row["text"]
            for end in reversed(ends):
                body = body[:end] + "\n" + body[end:]
            form = self.replace_body(form, row, body)
        return form

    def replace_body(self, form, row, body):
        suffix = f"\nEND PASSAGE {row['id']}\n\n"
        return form.replace("TEXT\n" + row["text"] + suffix, "TEXT\n" + body + suffix, 1)

    def imported(self, form=None, sample=None):
        return import_marking_form(self.snapshot, self.sample if sample is None else sample,
                                   self.marked_form() if form is None else form, reviewer="Synthetic reviewer")

    def call(self, arguments):
        output, errors = StringIO(), StringIO()
        with patch.dict(os.environ, self.environment), redirect_stdout(output), redirect_stderr(errors):
            status = cli.main([*arguments, "--corpus", str(self.corpus)])
        return status, output.getvalue(), errors.getvalue()

    def test_export_is_unsplit_and_independent_of_predicted_boundaries(self):
        for row in self.sample["passages"]:
            self.assertIn("TEXT\n" + row["text"] + f"\nEND PASSAGE {row['id']}", self.form)
        with patch("sol.essence.sentences.segment", side_effect=lambda text: [(0, len(text))]):
            self.assertEqual(export_marking_form(self.snapshot, self.sample), self.form)
        for predicted_field in ("gold_sentences", "predicted_boundaries", "false_splits", "sentences:"):
            self.assertNotIn(predicted_field, self.form)

    def test_added_breaks_round_trip_to_the_existing_review_and_expected_scores(self):
        before = self.files()
        artifact = encode_sentence_result(analyze_sentences(self.snapshot))
        review = self.imported()
        for original, row in zip(self.sample["passages"], review["passages"]):
            self.assertEqual(row["gold_sentences"], self.gold[row["id"]])
            self.assertEqual({key: value for key, value in original.items() if key != "gold_sentences"},
                             {key: value for key, value in row.items() if key != "gold_sentences"})
        scores = compare_sample(self.snapshot, review)["summary"]
        self.assertEqual((scores["true_positives"], scores["false_splits"], scores["misses"]), (4, 1, 1))
        self.assertEqual(scores["f1"], 0.8)
        self.assertEqual(encode_sentence_result(analyze_sentences(self.snapshot)), artifact)
        self.assertEqual(self.files(), before)

    def test_original_newlines_are_not_marks_and_can_be_marked_with_an_extra_enter(self):
        review = self.imported(self.form)
        source = next(row for row in self.sample["passages"] if "\n" in row["text"])
        row = next(row for row in review["passages"] if row["id"] == source["id"])
        self.assertEqual(row["gold_sentences"], [source["text"]])
        marked = self.replace_body(self.form, source, source["text"].replace("\n", "\n\n"))
        row = next(row for row in self.imported(marked)["passages"] if row["id"] == source["id"])
        self.assertEqual(row["gold_sentences"], source["text"].split("\n"))

    def test_unicode_spaces_and_blank_lines_retain_exact_source_slices(self):
        records = deepcopy(list(self.snapshot.records))
        record = next(row for row in records if row["id"] == self.sample["passages"][0]["id"])
        text = "  𝔸 carries e\u0301 and 界.\t  “Another thought.”\nremains whole.  "
        record.update(markdown=text, plain_text=text)
        self.write_records(records)
        snapshot = core.load_snapshot(self.corpus)
        sample = prepare_sample(snapshot, per_doctrine=2, seed=20261018)
        form = export_marking_form(snapshot, sample)
        source = sample["passages"][0]
        body = "\n" + text.replace("界.", "界.\n\n") + "\n"
        review = import_marking_form(snapshot, sample, self.replace_body(form, source, body), reviewer="Synthetic")
        self.assertEqual(review["passages"][0]["gold_sentences"],
                         ["𝔸 carries e\u0301 and 界.", "“Another thought.”\nremains whole."])
        self.assertEqual(review["passages"][0]["text"], text)

    def test_word_whitespace_punctuation_and_normalization_edits_name_the_passage_and_place(self):
        row = self.sample["passages"][0]
        for body in (row["text"].replace("diary", "journal"), row["text"].replace(" ", "", 1),
                     row["text"] + " ", row["text"].replace("rang.", "rang!"), row["text"][:-1]):
            with self.subTest(body=body):
                form = self.replace_body(self.form, row, body)
                with self.assertRaisesRegex(ValueError, rf"Passage 1 \({row['id']}\).*codepoint \d+ .*form line"):
                    self.imported(form)
        records = deepcopy(list(self.snapshot.records))
        record = next(record for record in records if record["id"] == row["id"])
        record.update(markdown="e\u0301 remains.", plain_text="e\u0301 remains.")
        self.write_records(records)
        snapshot = core.load_snapshot(self.corpus)
        sample = prepare_sample(snapshot, per_doctrine=2, seed=20261018)
        form = export_marking_form(snapshot, sample).replace("e\u0301", "é")
        with self.assertRaisesRegex(ValueError, "source mismatch.*codepoint"):
            import_marking_form(snapshot, sample, form, reviewer="Synthetic")

    def test_deleting_or_replacing_an_original_newline_is_refused(self):
        row = next(row for row in self.sample["passages"] if "\n" in row["text"])
        for replacement in ("", " "):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "source mismatch"):
                self.imported(self.replace_body(self.form, row, row["text"].replace("\n", replacement)))

    def test_dropped_duplicated_reordered_passages_and_edited_headings_are_refused(self):
        first = self.form.index("PASSAGE 1 |")
        second = self.form.index("PASSAGE 2 |")
        third = self.form.index("PASSAGE 3 |")
        for form in (self.form[:first] + self.form[second:],
                     self.form[:second] + self.form[first:second] + self.form[second:],
                     self.form[:first] + self.form[second:third] + self.form[first:second] + self.form[third:],
                     self.form.replace("PASSAGE 1 | BEING", "PASSAGE 1 | ESSENCE", 1),
                     self.form.replace("END OF FORM\n", ""), self.form + "Unexpected tail\n"):
            with self.subTest(form=form[-100:]), self.assertRaisesRegex(ValueError, "changed or missing|unexpected"):
                self.imported(form)

    def test_changed_sample_or_binding_and_already_marked_samples_are_refused(self):
        changed = prepare_sample(self.snapshot, per_doctrine=2, seed=9)
        with self.assertRaisesRegex(ValueError, "header/sample binding"):
            self.imported(sample=changed)
        for mutate in (lambda sample: sample["passages"][0].update(text="Changed source."),
                       lambda sample: sample["generation"].update(index_sha256="0" * 64),
                       lambda sample: sample.update(reviewer="Already reviewed"),
                       lambda sample: sample["passages"][0].update(gold_sentences=["A sentence."]),
                       lambda sample: sample["passages"].reverse()):
            sample = deepcopy(self.sample)
            mutate(sample)
            with self.subTest(sample=sample["reviewer"]), self.assertRaisesRegex(ValueError, "sample changed"):
                export_marking_form(self.snapshot, sample)
            with self.assertRaisesRegex(ValueError, "sample changed"):
                self.imported(sample=sample)

    def test_exclusion_lines_do_not_allow_text_changes_or_silent_omissions(self):
        form = self.marked_form().replace("EXCLUDE: \n", "EXCLUDE: Doubtful aside; second reader needed.\n", 1)
        review = self.imported(form)
        self.assertIsNone(review["passages"][0]["gold_sentences"])
        self.assertIn("second reader", review["passages"][0]["exclude_reason"])
        self.assertEqual(len(compare_sample(self.snapshot, review)["excluded_passages"]), 1)
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            self.imported(form.replace("diary", "journal", 1))
        with self.assertRaisesRegex(ValueError, "TEXT heading"):
            self.imported(form.replace("Doubtful aside;", "Doubtful\naside;", 1))
        with self.assertRaisesRegex(ValueError, "no scored passages"):
            self.imported(self.form.replace("EXCLUDE: \n", "EXCLUDE: Unadjudicated\n"))

    def test_reviewer_and_current_corpus_are_required(self):
        for reviewer in ("", " ", None):
            with self.subTest(reviewer=reviewer), self.assertRaisesRegex(ValueError, "reviewer"):
                import_marking_form(self.snapshot, self.sample, self.form, reviewer=reviewer)
        (self.corpus / "sample.md").write_text("Changed canonical document.")
        with self.assertRaises(ValueError):
            self.imported()

    def test_utf8_lf_and_bounds_are_strict(self):
        for data in (b"\xff", "\ud800", {}, b"\xef\xbb\xbf" + self.form.encode("utf-8"),
                     self.form.replace("\n", "\r\n")):
            with self.subTest(data=type(data)), self.assertRaises(ValueError):
                self.imported(data)
        with patch("sol.essence.segmentation_marking.MAX_REVIEW_BYTES", 10), self.assertRaises(ValueError):
            decode_marking_form(self.form)

    def test_form_output_is_private_outside_git_and_never_overwrites(self):
        path = write_marking_form(self.form, self.root / "marking.txt")
        self.assertEqual(path.read_bytes(), self.form.encode("utf-8"))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            write_marking_form(self.form, path)
        link = self.root / "link.txt"
        link.symlink_to(path)
        with self.assertRaises(FileExistsError):
            write_marking_form(self.form, link)
        (self.root / ".git").write_text("gitdir: /invented/worktree\n")
        with self.assertRaisesRegex(ValueError, "outside every Git"):
            write_marking_form(self.form, self.root / "forbidden.txt")

    def test_cli_export_mark_import_check_and_refuse_existing_output(self):
        sample, form, review = (self.root / name for name in ("sample.json", "mark.txt", "review.json"))
        write_sample(self.sample, sample)
        source_bytes = sample.read_bytes()
        code, output, errors = self.call(["segmentation-export", str(sample), "--output", str(form), "--json"])
        self.assertEqual(code, 0, errors)
        self.assertEqual(json.loads(output)["status"], "unmarked")
        self.assertNotIn(self.sample["passages"][0]["text"], output)
        form.write_bytes(self.marked_form().encode("utf-8"))
        arguments = ["segmentation-import", str(sample), str(form), "--reviewer", "Synthetic reviewer", "--output", str(review)]
        code, output, errors = self.call(arguments + ["--json"])
        self.assertEqual(code, 0, errors)
        self.assertEqual(json.loads(output)["status"], "marked")
        self.assertEqual(review.stat().st_mode & 0o777, 0o600)
        code, output, errors = self.call(["segmentation-check", str(review), "--json"])
        self.assertEqual(code, 0, errors)
        self.assertEqual(json.loads(output)["summary"]["f1"], 0.8)
        review_bytes = review.read_bytes()
        code, _, errors = self.call(arguments)
        self.assertEqual(code, 2)
        self.assertIn("exist", errors)
        self.assertEqual(review.read_bytes(), review_bytes)
        self.assertEqual(sample.read_bytes(), source_bytes)

    def test_cli_invalid_form_creates_no_output_and_is_checked_before_corpus_discovery(self):
        sample, form, review = (self.root / name for name in ("sample.json", "mark.txt", "review.json"))
        write_sample(self.sample, sample)
        form.write_bytes(self.form.replace("diary", "journal", 1).encode("utf-8"))
        arguments = ["segmentation-import", str(sample), str(form), "--reviewer", "Synthetic", "--output", str(review), "--json"]
        code, output, errors = self.call(arguments)
        self.assertEqual(code, 2)
        self.assertIn("form line", json.loads(output)["error"])
        self.assertFalse(review.exists())
        with patch("sol.core.discover_corpus", side_effect=AssertionError("must not discover")):
            form.write_bytes(b"\xff")
            code, _, errors = self.call(arguments)
            self.assertEqual(code, 2)
            self.assertIn("UTF-8", errors)
            code, _, errors = self.call(["segmentation-import", "-", "-", "--reviewer", "Synthetic", "--output", str(review)])
            self.assertEqual(code, 2)
            self.assertIn("only one", errors)


if __name__ == "__main__":
    unittest.main()
