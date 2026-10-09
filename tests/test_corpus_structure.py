"""Structure tests contain no manuscript fixture or copyrighted prose."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sol_corpus_structure import EXPECTED_COUNTS, _assign_parents, _attach_source_span, build_hierarchy


@dataclass
class Word:
    y1: float
    x1: float = 300


@dataclass
class Line:
    text: str
    y: float
    height: float = 11
    x: float = 100

    @property
    def words(self):
        return (Word(self.y + self.height),)


def key(text):
    text = re.sub(r"^[a-z][.)]\s+", "", text.casefold())
    return re.sub(r"[^a-z0-9]", "", text)


class SyntheticStructureTests(unittest.TestCase):
    def test_expected_structural_counts_cover_all_277_headings(self):
        self.assertEqual(sum(EXPECTED_COUNTS.values()), 277)
        self.assertEqual(EXPECTED_COUNTS["remark"], 52)
        self.assertEqual(EXPECTED_COUNTS["greek_subdivision"], 3)
        self.assertEqual(EXPECTED_COUNTS["unnumbered_subdivision"], 2)

    def test_shared_introduction_is_outside_being(self):
        rows = [{"kind": kind, "title": title, "pdf_page": page} for kind, title, page in (
            ("volume", "Objective Logic", 80),
            ("prefatory_or_introductory_text", "Introduction", 96),
            ("introduction_subdivision", "General division", 111),
            ("book", "Being", 118),
            ("prefatory_or_introductory_text", "Beginning", 118))]
        _assign_parents(rows)
        self.assertEqual(rows[1]["parent_audit_id"], rows[0]["audit_id"])
        self.assertEqual(rows[2]["parent_audit_id"], rows[1]["audit_id"])
        self.assertEqual(rows[4]["parent_audit_id"], rows[3]["audit_id"])

    def test_remark_does_not_parent_later_sibling_subdivisions(self):
        rows = [{"kind": kind, "title": kind, "pdf_page": 150} for kind in (
            "volume", "book", "section", "chapter", "major_subdivision",
            "subdivision", "remark", "remark", "subdivision")]
        _assign_parents(rows)
        self.assertEqual(rows[6]["parent_audit_id"], rows[5]["audit_id"])
        self.assertEqual(rows[7]["parent_audit_id"], rows[5]["audit_id"])
        self.assertEqual(rows[8]["parent_audit_id"], rows[4]["audit_id"])

    def test_unnumbered_heading_has_exact_lower_subdivision_parent(self):
        rows = [{"kind": kind, "title": kind, "pdf_page": 193} for kind in (
            "volume", "book", "section", "chapter", "major_subdivision",
            "subdivision", "unnumbered_subdivision", "remark")]
        _assign_parents(rows)
        self.assertEqual(rows[6]["parent_audit_id"], rows[5]["audit_id"])
        self.assertEqual(rows[6]["depth"], 7)
        self.assertEqual(rows[7]["parent_audit_id"], rows[6]["audit_id"])

    def test_caption_is_in_consumable_span_before_title_anchor(self):
        page = SimpleNamespace(number=132, body_height=11,
            lines=[Line("c h a p t e r 1", 68.9, 5.5), Line("Example", 88.5, 16)])
        row = {"kind": "chapter", "title": "Example", "y": 88.5, "evidence": []}
        _attach_source_span(row, page, 1, SimpleNamespace(heading_key=key))
        self.assertEqual(row["start_y"], 68.9)
        self.assertEqual(row["caption_y"], 68.9)
        self.assertEqual(row["end_y"], 104.5)
        self.assertEqual(len(row["source_lines"]), 2)

    def test_arbitrary_small_caps_are_not_a_caption(self):
        page = SimpleNamespace(number=132, body_height=11,
            lines=[Line("unrelated phrase", 68.9, 5.5), Line("Example", 88.5, 16)])
        row = {"kind": "chapter", "title": "Example", "y": 88.5, "evidence": []}
        _attach_source_span(row, page, 1, SimpleNamespace(heading_key=key))
        self.assertEqual(row["start_y"], 88.5)
        self.assertNotIn("caption_y", row)

    def test_wrapped_heading_is_one_source_span(self):
        page = SimpleNamespace(number=551, body_height=11,
            lines=[Line("a. example title", 374.1, 5), Line("continued title", 386.6, 5)])
        row = {"kind": "major_subdivision", "title": "example title continued title", "evidence": []}
        _attach_source_span(row, page, 0, SimpleNamespace(heading_key=key))
        self.assertEqual(row["end_y"], 391.6)
        self.assertEqual(len(row["source_lines"]), 2)

    def test_verified_remark_subtitle_is_consumed_not_prose(self):
        subtitle = "The conceptual determination of the mathematical infinite"
        page = SimpleNamespace(number=277, body_height=11,
            lines=[Line("Remark 1", 153.3), Line(subtitle, 165.8), Line("Body example.", 178.3)])
        row = {"kind": "remark", "title": "Remark 1", "evidence": []}
        _attach_source_span(row, page, 0, SimpleNamespace(heading_key=key))
        self.assertEqual(row["subtitle"], subtitle)
        self.assertEqual(row["end_y"], 176.8)
        self.assertEqual(len(row["source_lines"]), 2)

    def test_changed_verified_subtitle_fails_loudly(self):
        page = SimpleNamespace(number=277, body_height=11,
            lines=[Line("Remark 1", 153.3), Line("Wrong subtitle", 165.8)])
        row = {"kind": "remark", "title": "Remark 1", "evidence": []}
        with self.assertRaisesRegex(RuntimeError, "subtitle"):
            _attach_source_span(row, page, 0, SimpleNamespace(heading_key=key))


@unittest.skipUnless(os.environ.get("SOL_TEST_PDF"), "Set SOL_TEST_PDF to the local supported edition.")
class LocalPdfStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = build_hierarchy(os.environ["SOL_TEST_PDF"])

    def test_all_expected_headings_have_prior_parents_and_valid_source_spans(self):
        self.assertEqual(self.inventory["counts"], EXPECTED_COUNTS)
        known = {"book-root"}
        for row in self.inventory["headings"]:
            self.assertIn(row["parent_audit_id"], known)
            self.assertNotIn(row["audit_id"], known)
            self.assertLessEqual(row["start_y"], row["y"])
            self.assertGreaterEqual(row["end_y"], row["y"])
            known.add(row["audit_id"])

    def test_every_chapter_and_section_caption_is_included(self):
        for row in self.inventory["headings"]:
            if row["kind"] in ("chapter", "section", "book"):
                self.assertIn("caption_y", row)
                self.assertEqual(row["start_y"], row["caption_y"])
                self.assertEqual(row["source_lines"][0]["y"], row["start_y"])

    def test_greek_corrections_and_all_three_remark_subtitles_present(self):
        rows = self.inventory["headings"]
        self.assertEqual([row["label"] for row in rows if row["kind"] == "greek_subdivision"], ["α", "β", "γ"])
        self.assertEqual(len([row for row in rows if "subtitle" in row]), 3)

    def test_both_verified_unnumbered_headings_are_indexed(self):
        rows = self.inventory["headings"]
        indexed = {row["audit_id"]: row for row in rows}
        headings = [row for row in rows if row["kind"] == "unnumbered_subdivision"]
        self.assertEqual([row["title"] for row in headings], ["Transition", "Repulsion"])
        self.assertEqual([indexed[row["parent_audit_id"]]["title"] for row in headings],
                         ["Affirmative infinity", "Many ones"])


if __name__ == "__main__":
    unittest.main()
