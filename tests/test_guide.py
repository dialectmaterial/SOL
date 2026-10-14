"""The beginner guide is compact, portable, and independent of source files."""
from __future__ import annotations

from unittest.mock import patch
import unittest

import sol.reader.app as sol


def synthetic_book():
    root = sol.Node("", "Synthetic Science of Logic", 1)
    doctrines = []
    for index, name in enumerate(("BEING", "ESSENCE", "CONCEPT"), 1):
        doctrine = sol.Node(name, name.title(), index, parent=root)
        section = sol.Node("01-synthetic-division", "A synthetic division", index, parent=doctrine)
        leaf = sol.Node("01-synthetic-passage.txt", "A synthetic passage", index, parent=section)
        section.children = (leaf,)
        doctrine.children = (section,)
        doctrines.append(doctrine)
    root.children = tuple(doctrines)
    return sol.Book(root, [])


class GuideTests(unittest.TestCase):
    def test_default_guide_is_under_65_lines_and_contains_three_doctrines(self):
        text = sol.render_guide()
        self.assertLessEqual(len(text.splitlines()), 65)
        self.assertLessEqual(max(map(len, text.splitlines())), 80)
        self.assertTrue(text.isascii())
        self.assertIn("SOL: SOL Organizes Logic", text)
        self.assertIn("BOOK TREE", text)
        for name in ("BEING", "ESSENCE", "CONCEPT"):
            self.assertIn(name + "/", text)

    def test_loaded_tree_is_used_without_expanding_every_division(self):
        text = sol.render_guide(synthetic_book())
        self.assertIn("Synthetic Science of Logic", text)
        self.assertNotIn("01-synthetic-division", text)
        self.assertNotIn("CORPUS SETUP", text)
        self.assertIn("...", text)

    def test_depth_is_explicit_and_selected_subtree_is_respected(self):
        book = synthetic_book()
        deep = sol.render_guide(book, depth=3)
        self.assertIn("01-synthetic-division", deep)
        self.assertIn("01-synthetic-passage.txt", deep)
        selected = sol.render_guide(book, depth=2, node=book.root.children[1])
        tree = selected.split("BOOK TREE\n", 1)[1].split("START IN YOUR TERMINAL", 1)[0]
        self.assertIn("ESSENCE/", tree)
        self.assertIn("01-synthetic-passage.txt", tree)
        self.assertNotIn("BEING/", tree)
        self.assertNotIn("CONCEPT/", tree)

    def test_default_starts_with_terminal_invocations_and_separate_shell_examples(self):
        text = sol.render_guide(synthetic_book())
        self.assertIn("sol       start the reader", text)
        self.assertIn("sol -n", text)
        self.assertIn("sol -r", text)
        examples = ("cd /being", "ls", "first", "next", "where",
                    'search "ground" --word --limit 3', "open 1", "context 1")
        positions = [text.index("  " + command + "\n") for command in examples]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("enter these commands one at a time", text)
        self.assertNotIn("; search", text)

    def test_workspace_notes_and_guide_controls_are_discoverable(self):
        text = sol.render_guide(synthetic_book())
        for command in ("bookmark add beginning", "note add", "note draft",
                        "guide --depth 2", "help", "tree --depth 3", "exit"):
            self.assertIn(command, text)
        self.assertIn("Personal notes require an actor", text)
        self.assertIn("name recorded on your personal notes", text)
        self.assertNotIn("visual-help", text)

    def test_search_and_privacy_boundaries_are_clear(self):
        text = sol.render_guide(synthetic_book())
        self.assertIn("literal and case-insensitive", text)
        self.assertIn("not concepts", " ".join(text.split()))
        self.assertIn("Book paths are virtual", text)
        self.assertIn("never runs your host shell or edits canonical text", text)
        self.assertIn("Optional essence opens real Zsh", text)
        self.assertIn("accept returns explicitly in BEING", text)
        self.assertIn("checkpoints stay local", text)

    def test_source_free_guide_explains_configuration_without_loading_or_conversion(self):
        with patch("sol.reader.app.load_corpus_book", side_effect=AssertionError("No corpus load")), \
                patch("sol.reader.app.load_book", side_effect=AssertionError("No PDF extraction")), \
                patch("builtins.open", side_effect=AssertionError("No file I/O")):
            text = sol.render_guide()
        self.assertIn("abbreviated fallback", text)
        self.assertIn("sol --set-corpus DIRECTORY", text)
        self.assertIn("sol-corpus --help", text)
        self.assertIn("never performs PDF conversion automatically", text)

    def test_narrow_output_folds_prose_and_tree_without_terminal_styles(self):
        for width in (20, 40, 80):
            with self.subTest(width=width):
                text = sol.render_guide(synthetic_book(), width=width)
                self.assertLessEqual(max(map(len, text.splitlines())), width)
                self.assertNotIn("\x1b", text)
                self.assertTrue(text.isascii())

    def test_invalid_depth_and_width_are_rejected(self):
        for depth in (-1, 33):
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                sol.render_guide(depth=depth)
        for width in (19, 241):
            with self.subTest(width=width), self.assertRaises(ValueError):
                sol.render_guide(width=width)


if __name__ == "__main__":
    unittest.main()
