"""Word-aware soft wrapping without changing semantic source coordinates."""
from __future__ import annotations

import importlib.util
import re
import unicodedata
import unittest

from sol.reader.navigation import vertical_offset
from experiments.reader_surfaces.reading_layout import line_layout


def cell_width(character):
    if unicodedata.combining(character) or unicodedata.category(character) in {"Mn", "Me"}:
        return 0
    return 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1


def plan(source, width, **options):
    return line_layout(source, width, display_character=options.get("display_character", lambda c: c),
                       cell_width=options.get("cell_width", cell_width))


class ReadingLayoutTests(unittest.TestCase):
    def test_ordinary_words_stay_whole_at_several_widths(self):
        text = "The thought proceeds through existence and determination."
        for width in (10, 13, 20, 40, 72):
            with self.subTest(width=width):
                layout = plan(text, width)
                self.assertEqual(layout.source, text)
                self.assertNotIn("\n", layout.display_text)
                self.assertEqual(len(layout.positions), len(text) + 1)
                for word in re.finditer(r"\S+", text):
                    if len(word.group()) <= width:
                        rows = {layout.positions[index][0] for index in range(word.start(), word.end())}
                        self.assertEqual(len(rows), 1, word.group())

    def test_full_width_words_hide_only_edge_separator_presentation(self):
        text = "hello  world hello"
        layout = plan(text, 5)
        self.assertEqual(layout.display_text, "helloworldhello")
        self.assertEqual(layout.positions[7], (1, 0))
        self.assertEqual(layout.positions[13], (2, 0))
        self.assertEqual(layout.positions[5:8], ((1, 0),) * 3)
        self.assertEqual(layout.display_to_source(layout.source_to_display(5)), 7)
        # The hidden whitespace is still a distinct selectable semantic span.
        self.assertEqual(layout.source[5:7], "  ")
        self.assertEqual(layout.positions[-1], (3, 0))
        self.assertEqual(layout.row_count, 4)

    def test_padding_is_not_source_text_and_is_not_selected_or_emphasized(self):
        layout = plan("The thought", 10)
        fragments = layout.styled_fragments([
            ("", "The "), ("class:selected-text class:source.emphasis", "thou"),
            ("class:source.strong", "ght"),
        ])
        self.assertEqual(layout.padding[4], 6)
        self.assertIn(("", " " * 6), fragments)
        self.assertEqual("".join(fragment[1] for fragment in fragments), layout.display_text)
        self.assertEqual({layout.positions[index][0] for index in range(4, 11)}, {1})
        self.assertEqual(layout.source[4:11], "thought")
        for index in range(len(layout.source) + 1):
            self.assertEqual(layout.display_to_source(layout.source_to_display(index)), index)
        for index in range(layout.boundaries[3] + 1, layout.boundaries[4]):
            self.assertEqual(layout.display_to_source(index), 4)

    def test_fragment_style_boundaries_do_not_create_word_breaks(self):
        layout = plan("being determination", 15)
        fragments = layout.styled_fragments([
            ("", "being det"), ("class:source.emphasis", "ermi"),
            ("class:source.code", "nation"),
        ])
        self.assertEqual({layout.positions[index][0] for index in range(6, 19)}, {1})
        self.assertTrue(any(style == "class:source.emphasis" for style, _ in fragments))
        self.assertEqual(layout.display_text, "being " + " " * 9 + "determination")

    def test_character_wrapping_only_for_a_long_unbreakable_token(self):
        layout = plan("abcdefghijk", 5)
        self.assertEqual(layout.display_text, layout.source)
        self.assertEqual(layout.positions[0], (0, 0))
        self.assertEqual(layout.positions[5], (1, 0))
        self.assertEqual(layout.positions[10], (2, 0))

    def test_hyphens_provide_an_existing_boundary_without_new_hyphens(self):
        layout = plan("well-formed", 6)
        self.assertEqual(layout.positions[5], (1, 0))
        self.assertEqual(layout.source, "well-formed")
        self.assertEqual(layout.display_text.count("-"), 1)

    def test_unicode_wide_combining_greek_and_style_offsets(self):
        source = "Alpha λογος e\u0301 漢字終"
        layout = plan(source, 12)
        styles = [("class:source.emphasis", source[:10]), ("class:selected-text", source[10:])]
        self.assertEqual(len(layout.positions), len(source) + 1)
        self.assertEqual(layout.source, source)
        self.assertEqual(layout.display_text, "".join(item[1] for item in layout.styled_fragments(styles)))
        self.assertEqual(layout.positions[source.index("\u0301")][1],
                         layout.positions[source.index("\u0301") - 1][1] + 1)
        for index, character in enumerate(source):
            if character != " ":
                self.assertEqual(layout.display_to_source(layout.source_to_display(index)), index)
        self.assertEqual(source[10:15], "ς e\u0301 ")

    def test_escape_expansion_has_one_semantic_source_offset(self):
        source = "one \x1b thought"
        layout = plan(source, 10, display_character=lambda c: "\\x1b" if c == "\x1b" else c)
        index = source.index("\x1b")
        start = layout.source_to_display(index)
        for display in range(start, start + 4):
            self.assertEqual(layout.display_to_source(display), index)
        self.assertEqual(layout.source[index:index + 1], "\x1b")
        self.assertNotIn("\x1b", layout.display_text)
        self.assertEqual(layout.positions[source.index("thought")], (1, 0))

    def test_resize_reflows_rows_not_source_cursor_or_selection(self):
        source = "Being and thought retain source identity through reflow."
        start, end = 10, 39
        narrow, wide = plan(source, 12), plan(source, 40)
        self.assertEqual(narrow.source[start:end], wide.source[start:end])
        self.assertNotEqual(narrow.positions[end], wide.positions[end])
        self.assertEqual(narrow.source_to_display(end), narrow.boundaries[end])
        self.assertEqual(wide.source_to_display(end), wide.boundaries[end])
        destination, preferred = vertical_offset(narrow.positions, source.index("thought"), 1)
        self.assertEqual(narrow.positions[destination][0],
                         narrow.positions[source.index("thought")][0] + 1)
        back, _ = vertical_offset(narrow.positions, destination, -1, preferred)
        self.assertEqual(back, source.index("thought"))
        self.assertEqual(source[min(back, end):max(back, end)], narrow.source[10:end])

    def test_visual_motion_chooses_visible_word_not_hidden_wrap_separator(self):
        source = "hello  world hello"
        layout = plan(source, 5)
        down, column = vertical_offset(layout.positions, 0, 1)
        self.assertEqual(down, source.index("world"))
        further, _ = vertical_offset(layout.positions, down, 1, column)
        self.assertEqual(further, source.rindex("hello"))
        up, _ = vertical_offset(layout.positions, further, -1, column)
        self.assertEqual(up, down)
        self.assertEqual(vertical_offset(layout.positions, up, -1, column)[0], 0)
        # Those same separators remain two real source-character steps.
        self.assertEqual(source[down - 2:down], "  ")
        self.assertEqual(layout.positions[down - 1], layout.positions[down])

    def test_visual_motion_chooses_glyph_after_combining_boundary_tie(self):
        source = "abcdefgh e\u0301f rest"
        layout = plan(source, 8)
        first = 1
        down, column = vertical_offset(layout.positions, first, 1)
        self.assertEqual(source[down], "f")
        self.assertEqual(column, 1)
        combining = source.index("\u0301")
        self.assertEqual(layout.positions[combining], layout.positions[down])
        self.assertEqual(source[down - 1:down], "\u0301")

    def test_end_insertion_boundary_includes_renderer_cursor_space(self):
        self.assertEqual(plan("", 5).positions, ((0, 0),))
        layout = plan("abcde", 5)
        self.assertEqual(layout.positions[-1], (1, 0))
        self.assertEqual(layout.row_count, 2)
        self.assertEqual(layout.display_text, "abcde")

    def test_source_whitespace_and_explicit_newlines_are_not_normalized(self):
        layout = plan("  leading   spaces  ", 30)
        self.assertEqual(layout.display_text, layout.source)
        with self.assertRaisesRegex(ValueError, "source newlines"):
            plan("a\nb", 30)

    def test_rejects_invalid_width_projection_and_mismatched_fragments(self):
        for width in (0, -1, True, 1.2):
            with self.subTest(width=width), self.assertRaises(ValueError):
                plan("text", width)
        with self.assertRaisesRegex(ValueError, "nonempty"):
            plan("text", 10, display_character=lambda c: "")
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            plan("text", 10, cell_width=lambda c: -1)
        for fragments in ([("", "different")], [("", "te")]):
            with self.assertRaisesRegex(ValueError, "match the source"):
                plan("text", 10).styled_fragments(fragments)


@unittest.skipUnless(importlib.util.find_spec("prompt_toolkit"), "optional toolkit absent")
class ToolkitReadingLayoutTests(unittest.TestCase):
    def test_real_window_geometry_agrees_with_source_projection_and_styled_selection(self):
        from prompt_toolkit.data_structures import Point
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import UIContent
        from prompt_toolkit.layout.screen import Screen, WritePosition
        from prompt_toolkit.utils import get_cwidth
        for width, source in ((10, "The thought retains source"), (5, "hello world hello"),
                              (9, "λoγος e\u0301 漢字"), (7, "long-unbreakabletoken")):
            with self.subTest(width=width, source=source):
                layout = plan(source, width, cell_width=get_cwidth)
                start, end = source.index(" ") + 1 if " " in source else 0, len(source)
                fragments = layout.styled_fragments([
                    ("class:source.emphasis", source[:start]),
                    ("class:selected-text", source[start:end]),
                ])
                content = UIContent(get_line=lambda _: fragments + [("", " ")], line_count=1,
                                    cursor_position=Point(x=layout.boundaries[end], y=0))
                screen = Screen()
                _, coordinates = Window()._copy_body(content, screen,
                    WritePosition(xpos=0, ypos=0, width=width, height=30),
                    0, width, wrap_lines=True)
                for index in range(len(source) + 1):
                    if (0, layout.boundaries[index]) in coordinates:
                        self.assertEqual(coordinates[0, layout.boundaries[index]], layout.positions[index])
                for pad, boundary in zip(layout.padding, layout.boundaries):
                    if pad:
                        row, column = coordinates[0, boundary - 1]
                        self.assertNotIn("selected-text", screen.data_buffer[row][column].style)
                self.assertEqual(source[start:end], layout.source[start:end])
