"""Search presentation must never become canonical source identity."""
from dataclasses import FrozenInstanceError
import unicodedata
import unittest

from sol.core.models import Book, Node, Passage, presentation_text
from sol.reader.search import SearchProjection, search_projection


class ReaderSearchProjectionTests(unittest.TestCase):
    def project(self, text, query, *, whole_word=False, labels=()):
        result = search_projection(text, query, whole_word, labels)
        # Exact returned source substrings must reproduce the search spelling.
        expected = unicodedata.normalize("NFC", query.strip()).casefold()
        for start, end in result.spans:
            self.assertIsInstance(start, int)
            self.assertTrue(0 <= start < end <= len(text))
            self.assertEqual(unicodedata.normalize("NFC", text[start:end]).casefold(),
                             expected)
        root = Node("", "Logic", 1)
        passage = Passage(text, 1, 1, root, (), 1, 1, "test-passage",
                          facsimile_labels=labels)
        found = bool(Book(root, [passage]).search(query, whole_word=whole_word))
        self.assertEqual(found, bool(result.spans) or result.degraded)
        return result

    def test_literal_repeated_matches_keep_source_offsets(self):
        source = "Ground is ground; GROUND remains."
        result = self.project(source, "ground")
        self.assertEqual(result, SearchProjection(((0, 6), (10, 16), (18, 24))))
        self.assertEqual(source, "Ground is ground; GROUND remains.")

    def test_query_is_literal_not_a_regular_expression(self):
        result = self.project("x [a.*] y [a.*] z", "[a.*]")
        self.assertEqual(result.spans, ((2, 7), (10, 15)))
        self.assertEqual(self.project("ground", "g.*d").spans, ())

    def test_query_strip_and_source_trim_preserve_original_offsets(self):
        result = self.project(" \t\n  Ground \n", "\t ground \n")
        self.assertEqual(result.spans, ((5, 11),))
        self.assertFalse(result.degraded)

    def test_internal_whitespace_is_literal_and_not_collapsed(self):
        self.assertEqual(self.project("two  words two words", "two words").spans,
                         ((11, 20),))
        self.assertEqual(self.project("two\nwords", "two words").spans, ())
        self.assertEqual(self.project("two\nwords", "two\nwords").spans, ((0, 9),))

    def test_casefold_expansion_maps_the_complete_original_character(self):
        self.assertEqual(self.project("Straße STRASSE", "strasse").spans,
                         ((0, 6), (7, 14)))
        self.assertEqual(self.project("Straße", "ss").spans, ((4, 5),))
        self.assertEqual(self.project("ﬃ", "ffi").spans, ((0, 1),))

    def test_partial_expansion_degrades_without_guessing_an_offset(self):
        result = self.project("ß", "s")
        self.assertEqual(result.spans, ())
        self.assertTrue(result.degraded)
        self.assertIn("exact contiguous source span", result.reason)
        result = self.project("ß s", "s")
        self.assertEqual(result.spans, ((2, 3),))
        self.assertTrue(result.degraded)

    def test_dotted_i_complete_and_partial_matches(self):
        self.assertEqual(self.project("İ", "i\u0307").spans, ((0, 1),))
        self.assertEqual(self.project("I\u0307", "İ").spans, ((0, 2),))
        partial = self.project("İ", "i")
        self.assertEqual(partial.spans, ())
        self.assertTrue(partial.degraded)

    def test_composed_and_decomposed_accents_return_source_codepoints(self):
        self.assertEqual(self.project("café cafe\u0301", "café").spans,
                         ((0, 4), (5, 10)))
        self.assertEqual(self.project("café cafe\u0301", "cafe\u0301").spans,
                         ((0, 4), (5, 10)))
        self.assertEqual(self.project("e\u0301", "é").spans, ((0, 2),))

    def test_independent_combining_mark_can_have_an_exact_source_span(self):
        self.assertEqual(self.project("a\u0301\u0315", "á").spans, ((0, 2),))
        self.assertEqual(self.project("a\u0301\u0315", "\u0315").spans, ((2, 3),))

    def test_reordered_combining_mark_fragment_is_not_guessed(self):
        source = "a\u0315\u0301"
        result = self.project(source, "á")
        self.assertEqual(result.spans, ())
        self.assertTrue(result.degraded)
        complete = self.project(source, "á\u0315")
        self.assertEqual(complete.spans, ((0, 3),))
        self.assertFalse(complete.degraded)

    def test_hangul_jamo_composition_is_not_split_at_class_zero(self):
        self.assertEqual(self.project("\u1100\u1161\u11a8 각", "각").spans,
                         ((0, 3), (4, 5)))
        self.assertEqual(self.project("각", "\u1100\u1161\u11a8").spans,
                         ((0, 1),))

    def test_non_hangul_class_zero_composition_is_also_verified(self):
        # Bengali vowel signs E + AA canonically compose to vowel sign O.
        self.assertEqual(self.project("\u09c7\u09be", "\u09cb").spans, ((0, 2),))

    def test_facsimile_caption_is_excluded_but_later_offsets_do_not_move(self):
        source = "  [facsimile]\n Ground\n\t[other]\t\nGround  "
        labels = ("[facsimile]", "[other]")
        self.assertEqual(self.project(source, "Ground", labels=labels).spans,
                         ((15, 21), (32, 38)))
        self.assertEqual(self.project(source, "facsimile", labels=labels).spans, ())
        self.assertEqual(self.project(source, "other", labels=labels).spans, ())
        self.assertEqual(presentation_text(source, labels), "Ground\n\nGround")

    def test_inline_caption_text_is_not_removed(self):
        self.assertEqual(self.project("A [facsimile] remains", "[facsimile]",
                                      labels=("[facsimile]",)).spans, ((2, 13),))

    def test_match_crossing_removed_caption_cannot_be_a_contiguous_source_span(self):
        result = self.project("one\n[caption]\ntwo", "one\n\ntwo",
                              labels=("[caption]",))
        self.assertEqual(result.spans, ())
        self.assertTrue(result.degraded)

    def test_repeated_caption_filtering_preserves_original_indices(self):
        source = "A\n label \nB\n label \nC"
        self.assertEqual(self.project(source, "C", labels=("label", "label")).spans,
                         ((20, 21),))

    def test_whole_word_uses_the_same_unicode_boundaries_as_book_search(self):
        source = "ground grounding _ground ground2 ground. Ground"
        self.assertEqual(self.project(source, "ground", whole_word=True).spans,
                         ((0, 6), (33, 39), (41, 47)))
        self.assertEqual(self.project("λόγος λόγος2", "ΛΌΓΟΣ", whole_word=True).spans,
                         ((0, 5),))
        self.assertEqual(self.project("Straße", "ss", whole_word=True).spans, ())

    def test_long_combining_sequence_has_a_bounded_explicit_fallback(self):
        source = "a" + "\u0315" * 140 + " ground"
        result = self.project(source, "\u0315")
        self.assertTrue(result.degraded)
        self.assertIn("unusually long", result.reason)
        self.assertEqual(result.spans, ())
        self.assertEqual(self.project(source, "ground").spans, ((142, 148),))
        complete = self.project(source, source[:141])
        self.assertEqual(complete.spans, ((0, 141),))
        self.assertFalse(complete.degraded)

    def test_no_matches_and_empty_source_do_not_degrade(self):
        self.assertEqual(self.project("nothing", "ground"), SearchProjection())
        self.assertEqual(self.project("\n \t", "ground"), SearchProjection())

    def test_projection_is_frozen_and_inputs_are_validated(self):
        with self.assertRaises(FrozenInstanceError):
            SearchProjection().degraded = True
        for query in ("", " ", "\t\n"):
            with self.assertRaises(ValueError):
                search_projection("text", query)
        with self.assertRaises(TypeError):
            search_projection(None, "text")
        with self.assertRaises(TypeError):
            search_projection("text", None)
        with self.assertRaises(TypeError):
            search_projection("text", "text", whole_word="yes")
        with self.assertRaises(TypeError):
            search_projection("text", "text", facsimile_labels=["caption"])
        with self.assertRaises(TypeError):
            search_projection("text", "text", facsimile_labels=(None,))


if __name__ == "__main__":
    unittest.main()
