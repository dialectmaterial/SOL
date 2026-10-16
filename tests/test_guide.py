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
        tree = selected.split("BOOK TREE\n", 1)[1]
        self.assertIn("ESSENCE/", tree)
        self.assertIn("01-synthetic-passage.txt", tree)
        self.assertNotIn("BEING/", tree)
        self.assertNotIn("CONCEPT/", tree)

    def test_default_starts_with_reader_and_keeps_command_interface_optional(self):
        text = sol.render_guide(synthetic_book())
        self.assertIn("sol       open the reader", text)
        self.assertIn("sol -n", text)
        self.assertIn("sol -r", text)
        self.assertIn("sol --shell", text)
        self.assertLess(text.index("START READING"), text.index("BOOK TREE"))
        self.assertLess(text.index("IN THE READER"), text.index("sol --shell"))
        self.assertNotIn("PROJECT ROADMAP", text)
        self.assertNotIn("cd /being", text)

    def test_workspace_resume_and_recoverable_removal_are_discoverable(self):
        text = sol.render_guide(synthetic_book())
        for command in ("sol --actor NAME --workspace NAME", "sol --workspace-list",
                        "sol --workspace-delete NAME", "sol guide --depth 2", "sol --help"):
            self.assertIn(command, text)
        self.assertIn("last actor", text)
        self.assertIn("that actor's last workspace", text)
        self.assertIn("asks to create one", text)
        self.assertIn("archive a workspace (recoverable)", text)
        self.assertIn("name on your personal notes", text)
        self.assertNotIn("visual-help", text)

    def test_reader_navigation_search_selection_and_return_are_described(self):
        text = sol.render_guide(synthetic_book())
        for key in ("j / k", "h / l", "Ctrl-D / Ctrl-U", "b / n", "gg / G",
                    "v, then motion", "c / f / ?", "Ctrl-Q", "/ground, Enter",
                    "Ctrl-P / Ctrl-N", "Alt-Left/Right"):
            self.assertIn(key, text)
        self.assertIn("not printed page", text)
        self.assertIn("within this passage; Escape clears it", text)
        self.assertIn("beginning / end of reading scope", text)
        self.assertIn("save your position and quit", text)
        self.assertNotIn("q quits", text)

    def test_search_privacy_and_terminal_boundaries_are_clear(self):
        text = sol.render_guide(synthetic_book())
        self.assertIn("literal and case-insensitive", text)
        self.assertIn("not conceptual", " ".join(text.split()))
        self.assertIn("Canonical text is read-only", " ".join(text.split()))
        self.assertIn("personal notes stay local", text)
        self.assertIn("Alacritty", text)
        self.assertIn("Kitty is optional", text)

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
