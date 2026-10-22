"""Analysis features exclude structural labels while retaining source-bound context."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from sol import core
from sol.corpus import contract
from sol.corpus.markdown import plain_text
from sol.essence import export_prose, prose_text
from fixtures_corpus import CorpusFixture


class ProseTextTests(unittest.TestCase):
    def test_structural_headings_are_removed_but_their_words_remain_in_prose(self):
        markdown = ("# Being\n\nBeing is a word in this sentence.\n\n"
                    "SetextHeadingOnly\n=================\n\n"
                    "> ## QuotedHeadingOnly\n>\n> A *quotation* about Being.\n\n"
                    "- ### ListedHeadingOnly\n\n- A list about Being.\n\n"
                    "<h2>HtmlHeadingOnly <em>emphasis</em></h2>\n\n"
                    "A [visible link](https://example.invalid/HiddenURL) and `Being`.\n\n"
                    "![ImageLabelOnly](image.png)\n\n<img src='image.png' alt='HtmlImageOnly'>")
        projected = prose_text(markdown)
        self.assertEqual(projected.count("Being"), 4)
        for label in ("SetextHeadingOnly", "QuotedHeadingOnly", "ListedHeadingOnly",
                      "HtmlHeadingOnly", "ImageLabelOnly", "HtmlImageOnly", "HiddenURL"):
            self.assertNotIn(label, projected)
            if label != "HiddenURL":
                self.assertIn(label, plain_text(markdown))
        for text in ("Being is a word", "A quotation about Being.", "A list about Being.", "visible link"):
            self.assertIn(text, projected)

    def test_authored_code_math_and_unicode_are_not_normalized_or_guessed_as_headings(self):
        markdown = "Being is *BEING*.\n\n```\n# literal argument schema\n```\n\nx<sup>2</sup> e\u0301."
        self.assertEqual(prose_text(markdown), plain_text(markdown))
        self.assertIn("# literal argument schema", prose_text(markdown))
        self.assertIn("e\u0301", prose_text(markdown))
        self.assertEqual(prose_text("# heading\n\n![caption](x.png)"), "")

    def test_inline_html_heading_and_note_callout_do_not_leak(self):
        note = "cccccccc-0000-4000-8000-000000000003"
        markdown = (f'Before <h3>InlineHeadingOnly</h3> after. '
                    f'<sup data-sol-note="{note}"><a href="#{note}">CalloutOnly</a></sup>'
                    ' Real prose and x<sup>2</sup>.')
        text = prose_text(markdown)
        self.assertNotIn("InlineHeadingOnly", text)
        self.assertNotIn("CalloutOnly", text)
        self.assertIn("Before", text)
        self.assertIn("after.", text)
        self.assertIn("x2", text)


class ProseExportTests(CorpusFixture, unittest.TestCase):
    def snapshot(self):
        return core.load_snapshot(self.corpus)

    def test_feature_text_and_hierarchy_have_separate_hashes_and_no_source_writes(self):
        rows = deepcopy(self.snapshot().records)
        section, paragraph = rows
        section.update(title="HeadingSentinel", markdown="# HeadingSentinel", plain_text="HeadingSentinel")
        paragraph.update(heading="LocalHeadingSentinel", reader_title="ReaderHeadingSentinel",
                         markdown="# EmbeddedHeadingSentinel\n\nBeing remains being.\n\n![CaptionSentinel](page.png)",
                         plain_text="EmbeddedHeadingSentinel\nBeing remains being.\nCaptionSentinel")
        # Cached context may be absent or stale; the export must follow parent IDs.
        paragraph["context"] = []
        self.write_records(rows)
        snapshot = self.snapshot()
        before = self.files()
        result = export_prose(snapshot)
        self.assertEqual(result, export_prose(snapshot))
        self.assertEqual(self.files(), before)
        self.assertEqual(result["format"], "sol.prose-input")
        self.assertEqual(result["method"]["feature_field"], "passages[].text")
        self.assertEqual(result["corpus"]["id"], snapshot.corpus_id)
        self.assertEqual(result["generation"]["index_sha256"], snapshot.index_sha256)
        self.assertEqual(len(result["passages"]), 1)
        row = result["passages"][0]
        self.assertEqual(row["text"], "Being remains being.")
        self.assertEqual(row["text_sha256"], sha256(row["text"].encode()).hexdigest())
        self.assertEqual(row["metadata"]["content_sha256"], snapshot.records[1]["content_sha256"])
        self.assertNotEqual(row["text_sha256"], row["metadata"]["content_sha256"])
        self.assertEqual(row["id"], self.identifier)
        self.assertEqual(row["metadata"]["sources"], snapshot.records[1]["sources"])
        self.assertEqual(row["metadata"]["heading"], "LocalHeadingSentinel")
        self.assertEqual(row["metadata"]["ancestry"][0]["id"], section["id"])
        self.assertEqual(row["metadata"]["ancestry"][0]["title"], "HeadingSentinel")
        row["metadata"]["sources"][0]["printed_page"] = "modified copy"
        self.assertEqual(snapshot.records[1]["sources"][0]["printed_page"], "7")

    def test_eligibility_excludes_nonprose_editorial_generated_and_pending_records(self):
        rows = deepcopy(self.snapshot().records)
        template = rows[1]
        variants = [
            {"type": "title_display"}, {"type": "formula"}, {"type": "note"},
            {"type": "published_contents_entry"}, {"type": "retired_record", "redirect_id": self.identifier},
            {"attribution": {"author": "Invented editor", "role": "main_text", "status": "confirmed"}},
            {"attribution": {"author": "G. W. F. Hegel", "role": "editorial_note", "status": "confirmed"}},
            {"generated_text": True}, {"transcription_status": "needs_review"},
            {"transcription_status": "needs_visual_review"},
            {"markdown": "# OnlyHeading", "plain_text": "OnlyHeading"},
            {"markdown": "![OnlyImage](page.png)", "plain_text": "OnlyImage"},
            {"type": "quotation"}, {"type": "list_item"},
        ]
        for number, changes in enumerate(variants, 3):
            row = deepcopy(template)
            row.update(id=f"bbbbbbbb-0000-4000-8000-{number:012d}", order=number, **changes)
            rows.append(row)
        # Reader paths do not define eligibility or secretly supply labels.
        rows[1].pop("reader_path")
        generated = {"markdown", "plain_text", "document", "context", "content_sha256"}
        document = "\n".join(contract.render_record(
            {key: value for key, value in row.items() if key not in generated}, row["markdown"])
            for row in rows)
        (self.corpus / "sample.md").write_text(document, encoding="utf-8")
        contract.reindex(self.corpus)
        result = export_prose(self.snapshot())
        self.assertEqual(len(result["passages"]), 3)
        self.assertEqual([row["metadata"]["type"] for row in result["passages"]],
                         ["paragraph", "quotation", "list_item"])
        exclusions = result["exclusions"]
        self.assertEqual(exclusions["by_reason"],
                         {"record_type": 6, "attribution": 2, "generated_text": 1, "review": 2, "empty_text": 2})
        self.assertEqual(exclusions["excluded_records"] + len(result["passages"]), exclusions["input_records"])

    def test_changed_generation_and_modified_snapshot_are_refused(self):
        snapshot = self.snapshot()
        snapshot.records[1]["markdown"] = "Modified in memory."
        with self.assertRaisesRegex(ValueError, "snapshot was modified"):
            export_prose(snapshot)
        snapshot = self.snapshot()
        path = self.corpus / "sample.md"
        path.write_text(path.read_text() + "\n")
        with self.assertRaises(core.CorpusError):
            export_prose(snapshot)

    def test_changes_during_projection_are_refused_before_return(self):
        from sol.essence.essence_as_reflection_within_itself import prose

        original = prose.prose_text
        def change(markdown):
            path = self.corpus / "sample.md"
            path.write_text(path.read_text() + "\n")
            return original(markdown)
        with patch.object(prose, "prose_text", side_effect=change):
            with self.assertRaises(core.CorpusError):
                export_prose(self.snapshot())


if __name__ == "__main__":
    unittest.main()
