"""Synthetic importer regressions; no source-edition text is embedded here."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import sol_corpus as converter
from sol_corpus_contract import CorpusError, plain_text
from sol_corpus_notes import extract_notes


def span(identifier, text, x=53.5, y=100, width=100, size=11,
         height=10.96, family="AGaramond-Regular", page=80, italic=False, bold=False):
    return {
        "source_id": identifier, "pdf_page": page, "text": text,
        "x": x, "y": y, "width": width, "height": height,
        "size": size, "family": family, "italic": italic, "bold": bold,
    }


def page(number, *spans):
    return {"number": number, "width": 430, "height": 646, "spans": list(spans)}


def reference_line(value, column=0):
    return {"pdf_page": value["pdf_page"], "column": column,
            "x": value["x"], "y": value["y"], "spans": [value], "text": value["text"]}


class ConversionTextTests(unittest.TestCase):
    def test_explicit_roman_enumerations_retain_separate_markdown_items(self):
        values = [span("first", "I. First synthetic item.", y=100),
                  span("second", "II. Second synthetic item.", y=113)]
        markdown = converter.render_source_text(converter.span_lines(values), set())
        self.assertEqual(markdown, "- I. First synthetic item.\n- II. Second synthetic item.")
        self.assertEqual(plain_text(markdown), "I. First synthetic item.\n\nII. Second synthetic item.")

    def test_oldstyle_digits_and_tall_italic_dagger_share_their_prose_line(self):
        spans = [
            span("before", "Synthetic person (", x=65, y=400, width=90, size=8, height=7.97),
            span("dagger", "†", x=155, y=398.2, width=4, size=8, height=10.36,
                 family="AGaramond-Italic", italic=True),
            span("year", "1618", x=159, y=398.2, width=15, size=8, height=10.36,
                 family="AGaramondExp-Regular"),
            span("after", ") synthetic body.", x=174, y=400, width=80, size=8, height=7.97),
        ]
        lines = converter.span_lines(spans)
        self.assertEqual(len(lines), 1)
        self.assertEqual(plain_text(converter.styled_text(lines, set())), "Synthetic person (†1618) synthetic body.")

    def test_wrapped_italic_hyphenation_is_repaired_without_losing_emphasis(self):
        spans = [
            span("first", "deter-", italic=True, y=100),
            span("second", "mination", italic=True, y=113),
        ]
        markdown = converter.styled_text(converter.span_lines(spans), {"determination"})
        self.assertEqual(markdown, "*determination*")
        self.assertEqual(plain_text(markdown), "determination")

    def test_genuine_wrapped_compound_is_preserved(self):
        spans = [span("first", "form-", y=100), span("second", "determinateness", y=113)]
        markdown = converter.styled_text(converter.span_lines(spans), {"form-determinateness"})
        self.assertEqual(plain_text(markdown), "form-determinateness")

    def test_italic_continues_across_ordinary_line_wrap(self):
        spans = [span("first", "first italic", italic=True, y=100), span("second", "second italic", italic=True, y=113)]
        markdown = converter.styled_text(converter.span_lines(spans), set())
        self.assertEqual(plain_text(markdown), "first italic second italic")
        self.assertIn("*first italic*", markdown)
        self.assertIn("*second italic*", markdown)

    def test_literal_entities_and_markdown_symbols_remain_literal(self):
        source = r"Literal &amp; and *asterisks* [brackets] <angles> identifier_name."
        markdown = converter.styled_text(converter.span_lines([span("literal", source)]), set())
        self.assertEqual(plain_text(markdown), source)

    def test_raised_callout_attaches_to_its_regular_line(self):
        spans = [span("prose", "Synthetic prose", width=100),
                 span("callout", "a", x=153.5, y=97, width=4, size=6, height=7.67,
                      family="AGaramondExp-Regular")]
        lines = converter.span_lines(spans)
        self.assertEqual(len(lines), 1)
        self.assertEqual(converter.line_plain(lines[0]), "Synthetic prosea")

    def test_detached_accent_normalization_retains_dotless_i_semantics(self):
        self.assertEqual(converter.normalize_glyphs('na¨ıve'), 'naïve')
        self.assertEqual(converter.normalize_glyphs('¨uber'), 'über')
        self.assertEqual(converter.normalize_glyphs('unaccented ı remains'), 'unaccented ı remains')

    def test_cross_span_umlaut_fallback_preserves_quotation_and_style(self):
        spans = [span('before', '“ ¨', x=53.5, width=10),
                 span('following', 'uber”', x=63.5, width=40, italic=True)]
        markdown = converter.styled_text(converter.span_lines(spans), set())
        self.assertEqual(plain_text(markdown), '“über”')


class ImporterGraphTests(unittest.TestCase):
    def test_spaced_small_cap_heading_marker_is_not_math_power(self):
        values = [span("heading", "s y n t h e t i c", height=5.02, family="AGaramond-RegularSC"),
                  span("callout", "1 5", x=154, y=97, width=8, size=8,
                       height=3.51, family="AGaramond-RegularSC")]
        importer, root = self.importer(values)
        note = importer.make("note", root, [values[0]], "notes.md",
                             "#### Synthetic note", label="15", backlinks=[], note_ids=[])
        importer.note_lookup[(80, "15")].append(note)
        record = importer.text_record(root, converter.span_lines(values))
        self.assertEqual(record["note_ids"], [note["id"]])
        self.assertIn(record["id"], note["backlinks"])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name)

    def importer(self, spans):
        importer = converter.Importer(Path("synthetic.pdf"), [page(80, *spans)], {80: "7"}, {"headings": []}, self.stage)
        root = importer.make("section", None, [spans[0]], "synthetic.md", "# Synthetic section",
                             title="Synthetic section", path="/synthetic", reader_path="/BEING/synthetic.txt")
        root["_position"] = (80, 50, 0)
        importer.heads = [root]
        importer.root = root
        return importer, root

    def test_nested_note_links_have_reciprocal_child_backlinks(self):
        spans = [
            span("main", "Synthetic body", width=100),
            span("body-n", "n", x=153.5, y=97, width=4, size=6, height=7.67, family="AGaramondExp-Regular"),
            span("def-n", "n", y=397, width=5, size=6, height=7.77, family="AGaramondExp-Regular"),
            span("note-n", "Synthetic note includes", x=65, y=400, width=100, size=8, height=7.97),
            span("callout-145", "145", x=165, y=397, width=8, size=6, height=7.77, family="AGaramondExp-Regular"),
            span("tail-n", " nested reference.", x=173, y=400, width=90, size=8, height=7.97),
            span("def-145", "145", y=427, width=8, size=6, height=7.77, family="AGaramondExp-Regular"),
            span("note-145", "A nested synthetic note.", x=65, y=430, size=8, height=7.97),
        ]
        importer, root = self.importer(spans)
        extracted = extract_notes(importer.pages)
        importer.setup_notes(extracted)
        body = importer.text_record(root, converter.span_lines(extracted["pages"][0]["body_spans"]))
        importer.notes()
        note_n, note_145 = importer.note_records
        self.assertEqual(body["note_ids"], [note_n["id"]])
        self.assertIn(body["id"], note_n["backlinks"])
        referring_children = [record for record in importer.records
                              if record["type"] == "note_paragraph" and record["parent_id"] == note_n["id"]]
        self.assertEqual(len(referring_children), 1)
        child = referring_children[0]
        self.assertIn(note_145["id"], child["note_ids"])
        self.assertIn(child["id"], note_145["backlinks"])
        self.assertNotIn(note_n["id"], note_145["backlinks"])
        self.assertIn(note_145["id"], child["_md"])
        self.assertIsNone(child["attribution"]["author"])
        self.assertEqual(set(importer.claimed), {s["source_id"] for s in spans})

    def test_note_semantic_parent_follows_callout_not_later_footer_heading(self):
        spans = [span("early", "Earlier heading", y=60), span("body", "Earlier prose", y=150),
                 span("callout", "a", x=154, y=147, width=4, size=6, height=7.67, family="AGaramondExp-Regular"),
                 span("late", "Later heading", y=200),
                 span("def", "a", y=397, width=4, size=6, height=7.77, family="AGaramondExp-Regular"),
                 span("note", "A note on the earlier prose.", x=65, y=400, size=8, height=7.97)]
        importer, early = self.importer(spans)
        later = importer.make("section", early, [spans[3]], "later.md", "# Later heading", title="Later heading",
                              path="/synthetic/later", reader_path="/BEING/later.txt")
        later["_position"] = (80, 200, 0)
        importer.heads.append(later)
        extracted = extract_notes(importer.pages)
        importer.setup_notes(extracted)
        referring_paragraph = importer.text_record(early, converter.span_lines([spans[1], spans[2]]))
        importer.notes()
        self.assertEqual(importer.note_records[0]["parent_id"], referring_paragraph["id"])

    def test_math_exponent_does_not_silently_become_note_link(self):
        spans = [span("context", "Equation with ", width=70), span("variable", "x", x=123.5, width=6),
                 span("power", "12", x=129.5, y=97, width=8, size=6, height=7.67, family="AGaramondExp-Regular")]
        importer, root = self.importer(spans)
        note = importer.make("note", root, [spans[0]], "notes.md", "#### Note 12", label="12", backlinks=[], note_ids=[])
        importer.note_lookup[(80, "12")].append(note)
        formula = importer.text_record(root, converter.span_lines(spans), kind="formula")
        self.assertEqual(formula["note_ids"], [])
        self.assertEqual(note["backlinks"], [])

    def test_indented_lowercase_incomplete_line_is_not_new_paragraph(self):
        spans = [span("first", "A synthetic unfinished", x=53.5, y=100, width=200),
                 span("tail", "continuation.", x=64.5, y=113, italic=True)]
        importer, root = self.importer(spans)
        lines = converter.span_lines(spans)
        with patch.object(importer, "left", return_value=53.5):
            blocks = list(importer.paragraph_blocks(lines))
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0], root)

    def test_bibliography_categories_are_siblings_not_a_parent_chain(self):
        spans = [span("seed", "Bibliography", page=830),
                 span("header-a", "SOURCES CITED BY A", y=120, page=830),
                 span("entry-a", "Synthetic reference A.", y=140, page=830),
                 span("header-b", "WORKS CITED BY B", y=180, page=830),
                 span("entry-b", "Synthetic reference B.", y=200, page=830)]
        importer = converter.Importer(Path("synthetic.pdf"), [page(830, *spans)], {830: "757"}, {"headings": []}, self.stage)
        root = importer.make("section", None, [spans[0]], "references.md", "# Bibliography", title="Bibliography", path="/bibliography")
        importer.owner = lambda number, y: root

        def entries(pages, kind):
            if kind != "bibliography":
                return {"entries": [], "warnings": []}
            return {"warnings": [], "entries": [
                {"type": "section", "title": "SOURCES CITED BY A", "spans": [spans[1]]},
                {"type": "bibliography_entry", "title": "Reference A", "spans": [spans[2]], "lines": [reference_line(spans[2])], "section": "SOURCES CITED BY A"},
                {"type": "section", "title": "WORKS CITED BY B", "spans": [spans[3]]},
                {"type": "bibliography_entry", "title": "Reference B", "spans": [spans[4]], "lines": [reference_line(spans[4])], "section": "WORKS CITED BY B"},
            ]}

        with patch("sol_corpus_references.segment_references", side_effect=entries):
            importer.references([{"number": 830, "body_spans": spans}])
        sections = [record for record in importer.records if record["type"] == "section" and record is not root]
        self.assertEqual([record["parent_id"] for record in sections], [root["id"], root["id"]])
        references = [record for record in importer.records if record["type"] == "bibliography_entry"]
        self.assertEqual([record["parent_id"] for record in references], [sections[0]["id"], sections[1]["id"]])

    def test_index_column_continuation_uses_helper_order_not_global_y(self):
        first = span("left-bottom", "Synthetic subject,", x=53.5, y=500, page=850)
        continued = span("right-top", "1–3; continued.", x=240, y=60, page=850)
        importer = converter.Importer(Path("synthetic.pdf"), [page(850, first, continued)], {850: "777"}, {"headings": []}, self.stage)
        root = importer.make("section", None, [first], "index.md", "# Subject index", title="Subject index", path="/index")
        importer.owner = lambda number, y: root

        def entries(pages, kind):
            if kind != "index":
                return {"entries": [], "warnings": []}
            return {"warnings": [], "entries": [{
                "type": "index_entry", "title": "Synthetic subject", "section": "INDEX",
                "spans": [first, continued],
                "lines": [reference_line(first), reference_line(continued, 1)],
            }]}

        with patch("sol_corpus_references.segment_references", side_effect=entries):
            importer.references([{"number": 850, "body_spans": [first, continued]}])
        record = next(record for record in importer.records if record["type"] == "index_entry")
        self.assertEqual(plain_text(record["_md"]), "Synthetic subject, 1–3; continued.")


class ConversionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_existing_corpus_is_never_overwritten(self):
        output = self.root / "local-corpus"
        output.mkdir()
        with patch.object(converter, "load_layout", side_effect=AssertionError("Must not extract")):
            with self.assertRaisesRegex(CorpusError, "already exists"):
                converter.convert(self.root / "source.pdf", output, self.root / "work")
        self.assertFalse((self.root / "local-corpus.building").exists())

    def test_staging_directory_is_checked_for_git_exclusion_before_extraction(self):
        output, work = self.root / "local-corpus", self.root / "work"
        with patch.object(converter, "require_ignored") as check, patch.object(converter, "load_layout", side_effect=CorpusError("Synthetic stop")):
            with self.assertRaisesRegex(CorpusError, "Synthetic stop"):
                converter.convert(self.root / "source.pdf", output, work)
        checked = [call.args[0] for call in check.call_args_list]
        self.assertIn(output, checked)
        self.assertIn(work, checked)
        self.assertTrue(any(path not in {output, work} and path.name.startswith(output.name)
                            and "building" in path.name for path in checked))

    def test_ignoring_only_manifest_does_not_authorize_private_markdown_and_cache(self):
        def git_result(arguments, **kwargs):
            if "rev-parse" in arguments:
                return SimpleNamespace(returncode=0, stdout=str(self.root) + "\n", stderr="")
            return SimpleNamespace(returncode=0 if arguments[-1].endswith("corpus.json") else 1, stdout="", stderr="")

        with patch.object(converter.subprocess, "run", side_effect=git_result):
            with self.assertRaises(CorpusError):
                converter.require_ignored(self.root / "private")


if __name__ == "__main__":
    unittest.main()
