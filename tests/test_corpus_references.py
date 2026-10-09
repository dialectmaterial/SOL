"""Synthetic reference layouts; no source-book prose is embedded in tests."""

import unittest

from sol_corpus_references import segment_references


def span(source_id, text, x, y, width=80, size=10, height=10, family="Serif"):
    return {"source_id": source_id, "text": text, "x": x, "y": y,
            "width": width, "size": size, "height": height, "family": family}


class ReferenceSegmentationTests(unittest.TestCase):
    def test_hanging_entries_and_same_author_works(self):
        pages = [{"number": 830, "body_spans": [
            span("h", "SOURCES CITED BY HEGEL", 130, 100, width=160),
            span("a", "Example, A. First work.", 53, 130),
            span("b", "Published in Example City.", 73, 141),
            span("c", "Second work.", 63, 152),
            span("d", "A second publisher.", 73, 163),
            span("e", "Other, B. Another work.", 53, 174),
        ]}]
        result = segment_references(pages, "bibliography")
        self.assertEqual([e["source_ids"] for e in result["entries"]],
                         [["h"], ["a", "b"], ["c", "d"], ["e"]])
        self.assertEqual(result["entries"][2]["section"], "SOURCES CITED BY HEGEL")

    def test_same_author_only_page_and_cross_page_continuation(self):
        pages = [
            {"number": 830, "body_spans": [span("a", "Author. First work.", 53, 500),
                                           span("b", "Continues here", 73, 511)]},
            {"number": 831, "body_spans": [span("c", "from the previous page.", 86, 60),
                                           span("d", "Second work.", 76, 71),
                                           span("e", "Publication information.", 86, 82)]},
        ]
        result = segment_references(pages, "bibliography")
        self.assertEqual([e["source_ids"] for e in result["entries"]],
                         [["a", "b", "c"], ["d", "e"]])
        self.assertEqual(result["entries"][0]["end_page"], 831)

    def test_old_style_digits_join_baseline_without_extra_spaces(self):
        pages = [{"number": 1, "body_spans": [
            span("a", "Example, A. Year ", 53, 100, width=80),
            span("b", "1900", 133, 97.8, width=18, height=13, family="SerifExp"),
            span("c", ".", 151, 100, width=3),
        ]}]
        result = segment_references(pages, "bibliography")
        self.assertEqual(result["entries"][0]["text"], "Example, A. Year 1900.")

    def test_index_column_order_and_wrapped_entry(self):
        pages = [{"number": 850, "body_spans": [
            span("a", "alpha: meaning, 1;", 53, 180, width=147, size=8, height=8),
            span("b", "another meaning, 2", 61, 189, width=139, size=8, height=8),
            span("c", "beta, 3", 53, 198, width=100, size=8, height=8),
            span("d", "gamma, 4", 215, 180, width=147, size=8, height=8),
            span("e", "delta, 5", 215, 189, width=100, size=8, height=8),
        ]}]
        result = segment_references(pages, "index")
        self.assertEqual([e["title"] for e in result["entries"]],
                         ["alpha", "beta", "gamma", "delta"])
        self.assertEqual(result["entries"][0]["source_ids"], ["a", "b"])

    def test_index_continues_across_column_and_page(self):
        pages = [
            {"number": 850, "body_spans": [
                span("a", "alpha, 1", 53, 180, width=147, size=8, height=8),
                span("b", "beta: first part, 2;", 53, 198, width=147, size=8, height=8),
                span("c", "second part, 3", 223, 180, width=139, size=8, height=8),
                span("d", "gamma: begins, 4;", 215, 189, width=147, size=8, height=8),
            ]},
            {"number": 851, "body_spans": [
                span("e", "gamma (cont.)", 66, 60, width=147, size=8, height=8),
                span("f", "ends, 5", 74, 69, width=139, size=8, height=8),
                span("g", "delta, 6", 66, 78, width=147, size=8, height=8),
                span("h", "epsilon, 7", 228, 60, width=147, size=8, height=8),
            ]},
        ]
        result = segment_references(pages, "index")
        self.assertEqual([e["source_ids"] for e in result["entries"]],
                         [["a"], ["b", "c"], ["d", "e", "f"], ["g"], ["h"]])
        self.assertEqual(result["warnings"], [])

    def test_index_title_preserves_person_name_and_definite_article(self):
        pages = [{"number": 1, "body_spans": [
            span("a", "Example, A., xii, 12", 53, 60),
            span("b", "absolute, the: a sense, 13", 53, 70),
            span("c", "alias, see example", 53, 80),
        ]}]
        result = segment_references(pages, "index")
        self.assertEqual([e["title"] for e in result["entries"]],
                         ["Example, A.", "absolute, the", "alias"])

    def test_unknown_continuation_is_preserved_and_flagged(self):
        pages = [{"number": 1, "body_spans": [span("a", "missing (cont.)", 53, 60)]}]
        result = segment_references(pages, "index")
        self.assertEqual(result["entries"][0]["source_ids"], ["a"])
        self.assertEqual(result["warnings"][0]["code"], "unmatched_index_continuation")

    def test_detached_accent_belongs_to_its_title_line(self):
        pages = [{"number": 1, "body_spans": [
            span("a", "Uber a title.", 63, 100, width=90),
            span("b", "¨", 66, 97.4, width=3.6),
            span("c", "Publication information.", 73, 111),
        ]}]
        result = segment_references(pages, "bibliography")
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(set(result["entries"][0]["source_ids"]), {"a", "b", "c"})
        self.assertTrue(result["entries"][0]["text"].startswith("Über a title."))

    def test_duplicate_span_identity_is_rejected(self):
        pages = [{"number": 1, "body_spans": [span("a", "First", 53, 60),
                                              span("a", "Second", 53, 70)]}]
        with self.assertRaisesRegex(ValueError, "distinct"):
            segment_references(pages, "bibliography")


if __name__ == "__main__":
    unittest.main()
