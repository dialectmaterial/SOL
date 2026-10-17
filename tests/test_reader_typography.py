"""Typographic presentation never edits canonical source or selection offsets."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib.util
import subprocess
import sys
import unittest
from unittest.mock import patch

from sol.corpus.markdown import plain_text
from sol.reader.typography import Typography, TypographySpan, map_typography


HAS_COMMONMARK = importlib.util.find_spec("markdown_it") is not None


class TypographyFallbackTests(unittest.TestCase):
    def test_import_stays_dependency_light(self):
        result = subprocess.run([
            sys.executable, "-S", "-c",
            "import sys; import sol.reader.typography; "
            "assert 'markdown_it' not in sys.modules; "
            "assert 'prompt_toolkit' not in sys.modules; "
            "assert 'sol.corpus.contract' not in sys.modules",
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_optional_parser_explicitly_degrades_without_styles(self):
        original_import = __import__

        def without_parser(name, *args, **kwargs):
            if name == "markdown_it":
                raise ImportError("Synthetic missing optional parser")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", without_parser):
            result = map_typography("A *term*.", "A term.")
        self.assertTrue(result.degraded)
        self.assertEqual(result.spans, ())
        self.assertIn("parser", result.reason)

    def test_missing_record_fields_explicitly_degrade(self):
        for markdown, plain in ((None, "Source"), ("*Source*", None)):
            with self.subTest(markdown=markdown, plain=plain):
                result = map_typography(markdown, plain)
                self.assertEqual(result.spans, ())
                self.assertTrue(result.degraded)

    def test_public_values_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            Typography().degraded = True
        with self.assertRaises(FrozenInstanceError):
            TypographySpan(1, 4, ("emphasis",)).end = 9


@unittest.skipUnless(HAS_COMMONMARK, "Optional CommonMark parser unavailable")
class CommonMarkTypographyTests(unittest.TestCase):
    def projection(self, markdown):
        from sol.corpus.contract import plain_text
        text = plain_text(markdown)
        typography = map_typography(markdown, text)
        self.assertFalse(typography.degraded, typography.reason)
        previous = 0
        for span in typography.spans:
            self.assertGreaterEqual(span.start, previous)
            self.assertLess(span.start, span.end)
            self.assertLessEqual(span.end, len(text))
            self.assertTrue(span.styles)
            previous = span.end
        return text, typography.spans

    def styled(self, text, spans, style):
        return "".join(text[span.start:span.end] for span in spans if style in span.styles)

    def test_exact_nested_emphasis_strong_and_code(self):
        markdown = "Plain *italic **strong inside***, **bold**, `*literal*`, and ***both***."
        text, spans = self.projection(markdown)
        self.assertEqual(text, "Plain italic strong inside, bold, *literal*, and both.")
        self.assertEqual(self.styled(text, spans, "emphasis"), "italic strong insideboth")
        self.assertEqual(self.styled(text, spans, "strong"), "strong insideboldboth")
        self.assertEqual(self.styled(text, spans, "code"), "*literal*")
        self.assertTrue(any(span.styles == ("emphasis", "strong") for span in spans))

    def test_escaped_and_intraword_markers_are_not_styled(self):
        text, spans = self.projection(r"\*literal\* and a_name_b but _italic_ and **bold**.")
        self.assertIn("*literal* and a_name_b", text)
        self.assertEqual(self.styled(text, spans, "emphasis"), "italic")
        self.assertEqual(self.styled(text, spans, "strong"), "bold")

    def test_entities_links_images_and_mathematical_html(self):
        markdown = ("α &amp; β [a **label**](https://example.invalid) "
                    "![diagram *description*](image.png) and x<sup>2</sup>, "
                    "<em>HTML italic</em> and <strong>HTML bold</strong>.")
        text, spans = self.projection(markdown)
        self.assertIn("α & β a label diagram description and x2", text)
        self.assertEqual(self.styled(text, spans, "emphasis"), "descriptionHTML italic")
        self.assertEqual(self.styled(text, spans, "strong"), "labelHTML bold")

    def test_annotated_notes_and_scripts_have_no_visible_styles(self):
        note_id = "d22d0747-2431-44e1-bf1f-44f48de2a7d2"
        markdown = (f"*Before*<sup data-sol-note=\"{note_id}\"><em>"
                    f"[14](notes.md#{note_id})</em></sup>, "
                    "<script>*hidden*</script> **after** <!-- invisible -->.")
        text, spans = self.projection(markdown)
        self.assertEqual(text, "Before,  after .")
        self.assertEqual(self.styled(text, spans, "emphasis"), "Before")
        self.assertEqual(self.styled(text, spans, "strong"), "after")

    def test_unicode_ranges_count_source_codepoints_not_bytes_or_cells(self):
        text, spans = self.projection("界🙂 e\u0301 *α界e\u0301🙂* end.")
        span = next(span for span in spans if "emphasis" in span.styles)
        self.assertEqual(text[span.start:span.end], "α界e\u0301🙂")
        self.assertEqual((span.start, span.end), (6, 11))
        self.assertNotEqual(len(text[:span.start].encode("utf-8")), span.start)

    def test_blockquotes_headings_lists_and_breaks_use_contract_projection(self):
        markdown = "# A *heading*\n\n> Quoted *term*\n> another line\n\n1. **first**\n2. second\n\nFinal."
        text, spans = self.projection(markdown)
        self.assertEqual(self.styled(text, spans, "emphasis"), "headingterm")
        self.assertIn("Quoted term\nanother line", self.styled(text, spans, "quotation"))
        self.assertIn("A heading", self.styled(text, spans, "heading"))
        self.assertEqual(self.styled(text, spans, "strong"), "first")
        self.assertIn("first\n\nsecond", text)

    def test_soft_and_hard_breaks_and_outer_whitespace(self):
        text, spans = self.projection("  *first\nsecond*  \nthird\n\n\n\n*last*  ")
        self.assertEqual(text, "first\nsecond\nthird\nlast")
        self.assertEqual(self.styled(text, spans, "emphasis"), "first\nsecondlast")

    def test_literal_code_blocks_never_acquire_emphasis(self):
        for markdown in ("```text\n*literal* &amp; α\n```", "    *literal* &amp; α"):
            with self.subTest(markdown=markdown):
                text, spans = self.projection(markdown)
                self.assertEqual(text, "*literal* &amp; α")
                self.assertEqual(self.styled(text, spans, "emphasis"), "")
                self.assertEqual(self.styled(text, spans, "code"), text)

    def test_html_blocks_follow_existing_visible_html_rules(self):
        markdown = ("<div>\n<p>First <i>italic</i>.</p>\n"
                    "<script>hidden()</script>\n<p><b>Bold</b>.</p>\n</div>")
        text, spans = self.projection(markdown)
        self.assertEqual(self.styled(text, spans, "emphasis"), "italic")
        self.assertEqual(self.styled(text, spans, "strong"), "Bold")
        self.assertNotIn("hidden", text)

    def test_plain_text_without_emphasis_is_success_not_degradation(self):
        self.assertEqual(map_typography("Ordinary prose.", "Ordinary prose."), Typography())
        self.assertEqual(map_typography("", ""), Typography())

    def test_mismatch_never_fuzzy_aligns_similar_source(self):
        for source in ("A term!", " A term.", "A  term.", "term. A term."):
            with self.subTest(source=source):
                result = map_typography("A *term*.", source)
                self.assertTrue(result.degraded)
                self.assertEqual(result.spans, ())
                self.assertIn("disagree", result.reason)

    def test_mapping_contract_drift_explicitly_degrades(self):
        with patch("sol.reader.typography._project", return_value=("changed", (), ())):
            result = map_typography("A *term*.", "A term.")
        self.assertTrue(result.degraded)
        self.assertEqual(result.spans, ())
        self.assertIn("projection", result.reason)

    def test_footnote_callouts_keep_their_plain_text_offsets(self):
        markdown = ('Kant,<sup data-sol-note="aaaaaaaa-0000-4000-8000-000000000001">[7](notes.md#aaaaaaaa-0000-4000-8000-000000000001)</sup> *Critique*\n\n\n\n'
                    'Fichte.<sup data-sol-note="aaaaaaaa-0000-4000-8000-000000000002">[8](notes.md#aaaaaaaa-0000-4000-8000-000000000002)</sup>')
        text = plain_text(markdown)
        result = map_typography(markdown, text)
        self.assertFalse(result.degraded)
        self.assertEqual(text, "Kant, Critique\nFichte.")
        self.assertEqual(result.callouts, ((5, "aaaaaaaa-0000-4000-8000-000000000001"), (len(text), "aaaaaaaa-0000-4000-8000-000000000002")))
        self.assertEqual(text[:5], "Kant,")

    def test_untrusted_controls_are_source_characters_not_generated_escape_styles(self):
        text, spans = self.projection("*A\x1b[31mB\u202eC*")
        self.assertEqual(text, "A\x1b[31mB\u202eC")
        self.assertEqual(self.styled(text, spans, "emphasis"), text)
        self.assertEqual(spans[0].end, len(text))
        # This module assigns ranges only; the display processor escapes source
        # controls with its own source-to-display map, without offset mutation.


if __name__ == "__main__":
    unittest.main()
