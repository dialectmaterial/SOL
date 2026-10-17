"""A reading-exercise label cannot change a typeset source or its identity."""
from __future__ import annotations

from dataclasses import replace
import json
import stat
import unittest

import fixtures_corpus as fixtures

from experiments.reader_surfaces.common import sample_from_book, selection_packet
from experiments.reader_surfaces.html import render_html, write_html
from experiments.reader_surfaces.trials import ReadingTrial


class ReaderSurfaceTrialHTMLTests(fixtures.CorpusFixture, unittest.TestCase):

    def trial(self, sample=None):
        sample = sample if sample is not None else sample_from_book(self.book, count=1)
        first, last = sample.passages[0], sample.passages[-1]
        snapshot = self.book.corpus_snapshot
        notes = {identifier for passage in sample.passages for identifier in
                 self.book.canonical_records[passage.identifier].get("note_ids", [])}
        metadata = {
            "name": "invented-exercise", "title": "An invented reading exercise",
            "description": "A bounded fixture, not a philosophical or canonical classification.",
            "source_section_id": self.book.canonical_records[first.identifier]["parent_id"],
            "start": first.identifier, "end": last.identifier,
            "sample_passages": len(sample.passages),
            "printed_pages": [first.printed_page, last.end_printed_page],
            "pdf_pages": [first.pdf_page, last.end_pdf_page], "linked_notes": len(notes),
            "source_review_passages": sum(p.needs_source_review for p in sample.passages),
            "includes_remarks": False, "corpus_id": self.book.corpus_manifest["corpus_id"],
            "generation": {"manifest_sha256": snapshot.manifest_sha256,
                           "index_sha256": snapshot.index_sha256},
        }
        return ReadingTrial(sample, metadata)

    @staticmethod
    def data(document):
        return json.loads(next(text for _, attrs, text in document.blocks
                               if attrs.get("id") == "sol-data"))

    def corpus_files(self):
        return {path.relative_to(self.corpus): path.read_bytes()
                for path in self.corpus.rglob("*") if path.is_file()}

    def test_default_export_does_not_invent_or_embed_a_trial(self):
        document = fixtures._Document(render_html(sample_from_book(self.book, count=1)))
        self.assertNotIn("trial", self.data(document))
        self.assertFalse(any(attrs.get("id") == "trial-extent"
                             for _, attrs in document.elements))

    def test_trial_extent_is_visible_and_embedded_but_not_a_source_record(self):
        self.add_note()
        trial = self.trial()
        document = fixtures._Document(render_html(trial.sample, trial=trial))
        self.assertEqual(self.data(document)["trial"], trial.metadata)
        visible = "".join(document.text)
        self.assertNotIn(trial.metadata["title"], visible)
        for text in (trial.metadata["description"],
                     "invented-exercise", "1 passages", "printed 7–7", "PDF 80–80",
                     "1 linked notes"):
            self.assertIn(text, visible)
        self.assertTrue(any(attrs.get("id") == "trial-extent"
                            for _, attrs in document.elements))
        self.assertEqual([row["id"] for row in self.data(document)["records"]],
                         [self.identifier])

    def test_label_preserves_exact_unicode_text_semantics_and_existing_reference(self):
        self.rewrite_body("A🙂 e\u0301界 and an invented emphasis.",
                          markdown="A🙂 e\u0301界 and an invented *emphasis*.")
        trial = self.trial()
        before_files = self.corpus_files()
        before_state = trial.sample.actions.snapshot()
        before_packet = selection_packet(self.book, self.identifier, 1, 6)
        plain = fixtures._Document(render_html(trial.sample))
        labelled = fixtures._Document(render_html(trial.sample, trial=trial))
        self.assertEqual(self.data(labelled)["records"], self.data(plain)["records"])
        self.assertEqual(before_packet, selection_packet(self.book, self.identifier, 1, 6))
        self.assertEqual(before_packet["selection"]["text"], "🙂 e\u0301界")
        self.assertEqual(trial.sample.actions.snapshot(), before_state)
        self.assertEqual(self.corpus_files(), before_files)
        self.assertIn(("em", {}), labelled.elements)

    def test_trial_title_and_description_remain_inert_escaped_text(self):
        trial = self.trial()
        metadata = trial.metadata
        metadata.update(title='A <img src="https://invalid.test/x" onerror="bad()"> title',
                        description='An </p><script>bad()</script> & "invented" description.')
        trial = replace(trial, _metadata=metadata)
        document = fixtures._Document(render_html(trial.sample, trial=trial))
        self.assertNotIn(metadata["title"], "".join(document.text))
        self.assertIn(metadata["description"], "".join(document.text))
        self.assertEqual(self.data(document)["trial"], metadata)
        self.assertFalse(any(tag == "img" for tag, _ in document.elements))
        executable = [text for tag, attrs, text in document.blocks if tag == "script"
                      and attrs.get("type") != "application/json"]
        self.assertTrue(executable)
        self.assertTrue(all("bad()" not in text for text in executable))

    def test_metadata_mapping_or_a_different_sample_cannot_claim_the_extent(self):
        trial = self.trial()
        other = sample_from_book(self.book, count=1)
        for sample, label in ((trial.sample, trial.metadata), (other, trial)):
            with self.subTest(label_type=type(label).__name__), self.assertRaises(ValueError):
                render_html(sample, trial=label)

    def test_changed_start_end_or_count_is_refused_before_an_artifact_is_created(self):
        trial = self.trial()
        before = self.corpus_files()
        for key, value in (("start", "not-the-start"), ("end", "not-the-end"),
                           ("sample_passages", 2)):
            metadata = trial.metadata
            metadata[key] = value
            label = replace(trial, _metadata=metadata)
            output = self.root / (key + ".html")
            with self.subTest(key=key), self.assertRaises(ValueError):
                write_html(trial.sample, output, trial=label)
            self.assertFalse(output.exists())
        self.assertEqual(self.corpus_files(), before)

    def test_trial_output_is_owner_only_and_does_not_modify_the_corpus(self):
        trial = self.trial()
        before = self.corpus_files()
        output = self.root / "invented-reading-trial.html"
        write_html(trial.sample, output, trial=trial)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertEqual(output.read_text(encoding="utf-8"), render_html(trial.sample, trial=trial))
        self.assertEqual(self.corpus_files(), before)


if __name__ == "__main__":
    unittest.main()
