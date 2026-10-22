"""Terminal protection does not alter canonical text or raw pipeline output."""
from contextlib import redirect_stdout
from io import StringIO
import unittest

from sol.core.models import Node, Passage
from sol.reader.render import render_passage, render_search_results
from sol.presentation.text import display_text, safe_label, safe_output


class TTYOutput(StringIO):
    def isatty(self):
        return True


class TerminalTextTests(unittest.TestCase):
    def passage(self):
        return Passage("Source \x1b[31mtext\u202e remains literal.", 80, 7,
                       Node("a.txt", "Title\x1b[2J", 7), ("BEING", "a.txt"), 80, 7, "invented")

    def test_display_escapes_terminal_controls_but_retains_pipe_text(self):
        text = "prose\n\t\x1b[2J\u202e"
        self.assertEqual(display_text(text, StringIO()), text)
        self.assertEqual(display_text(text, TTYOutput()), "prose\n\t\\x1b[2J\\u202e")
        self.assertEqual(safe_label("a\nb\t"), "a\\u000ab\\u0009")
        self.assertEqual(safe_output("\ud800"), "\\ud800")

    def test_passage_display_keeps_trusted_styles_and_escapes_source(self):
        passage = self.passage()
        with redirect_stdout(TTYOutput()):
            rendered = render_passage(passage, 80, color=True)
            plain = render_passage(passage, 80, plain=True)
            results = render_search_results([passage], "\x1b[2J", 80)
        self.assertIn("\x1b[1m", rendered)
        self.assertNotIn("\x1b[31m", rendered)
        self.assertNotIn("\x1b", plain)
        self.assertNotIn("\x1b", results)
        self.assertIn("\\x1b[31m", plain)
        self.assertIn("\x1b[31m", passage.text)
        with redirect_stdout(StringIO()):
            self.assertIn("\x1b[31m", render_passage(passage, 80, plain=True))
