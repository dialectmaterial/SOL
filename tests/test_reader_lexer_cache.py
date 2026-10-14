"""Live semantic styles invalidate the toolkit's unchanged-document cache."""
import importlib.util
import unittest

from sol.reader.typography import Typography, TypographySpan
from sol.terminal.reader import _typography_lexer


@unittest.skipUnless(importlib.util.find_spec('prompt_toolkit'),
                     'optional prompt_toolkit is absent')
class ReaderLexerCacheTests(unittest.TestCase):
    def setUp(self):
        from prompt_toolkit.lexers import Lexer
        from prompt_toolkit.widgets import TextArea

        self.source = 'one ground and thought'
        self.typography = Typography()
        self.matches = ()
        self.lexer = _typography_lexer(
            {'Lexer': Lexer}, lambda: self.typography, lambda: self.matches)
        self.area = TextArea(text=self.source, read_only=True, lexer=self.lexer)
        # ReaderView deliberately installs this stable lexer directly: the
        # TextArea wrapper identifies dynamic lexers by object identity only.
        self.area.control.lexer = self.lexer

    def cached_line(self):
        """Use the same cache used by BufferControl during actual rendering."""
        return self.area.control._get_formatted_text_for_line_func(
            self.area.buffer.document)(0)

    def assert_span_style(self, fragments, start, end, name, *, present=True):
        self.assertTrue(all((name in style) == present
                            for style, _ in fragments[start:end]))
        self.assertEqual(''.join(text for _, text in fragments), self.source)
        self.assertEqual(self.area.buffer.text, self.source)

    def test_new_search_invalidates_cached_normal_source_styles(self):
        normal = self.cached_line()
        self.assert_span_style(normal, 4, 10, 'source.search', present=False)
        self.matches = ((4, 10),)
        marked = self.cached_line()
        self.assert_span_style(marked, 4, 10, 'source.search')
        self.assert_span_style(marked, 15, 22, 'source.search', present=False)

    def test_dismissing_marks_invalidates_cached_search_styles(self):
        self.matches = ((4, 10),)
        self.assert_span_style(self.cached_line(), 4, 10, 'source.search')
        self.matches = ()
        self.assert_span_style(self.cached_line(), 4, 10, 'source.search', present=False)

    def test_restoring_marks_after_dismissal_uses_current_cached_state(self):
        self.matches = ((4, 10),)
        self.assert_span_style(self.cached_line(), 4, 10, 'source.search')
        self.matches = ()
        self.assert_span_style(self.cached_line(), 4, 10, 'source.search', present=False)
        self.matches = ((4, 10),)
        self.assert_span_style(self.cached_line(), 4, 10, 'source.search')

    def test_changed_query_ranges_do_not_reuse_previous_match_styles(self):
        self.matches = ((4, 10),)
        self.assert_span_style(self.cached_line(), 4, 10, 'source.search')
        self.matches = ((15, 22),)
        changed = self.cached_line()
        self.assert_span_style(changed, 4, 10, 'source.search', present=False)
        self.assert_span_style(changed, 15, 22, 'source.search')

    def test_typography_changes_invalidate_cache_without_changing_plain_source(self):
        self.typography = Typography((TypographySpan(4, 10, ('emphasis',)),))
        self.assert_span_style(self.cached_line(), 4, 10, 'source.emphasis')
        self.typography = Typography((TypographySpan(4, 10, ('strong',)),))
        strong = self.cached_line()
        self.assert_span_style(strong, 4, 10, 'source.emphasis', present=False)
        self.assert_span_style(strong, 4, 10, 'source.strong')
        self.typography = Typography()
        self.assert_span_style(self.cached_line(), 4, 10, 'source.strong', present=False)

    def test_hiding_matches_preserves_cached_semantic_emphasis(self):
        self.typography = Typography((TypographySpan(4, 10, ('emphasis',)),))
        self.matches = ((4, 10),)
        marked = self.cached_line()
        self.assert_span_style(marked, 4, 10, 'source.search')
        self.assert_span_style(marked, 4, 10, 'source.emphasis')
        self.matches = ()
        hidden = self.cached_line()
        self.assert_span_style(hidden, 4, 10, 'source.search', present=False)
        self.assert_span_style(hidden, 4, 10, 'source.emphasis')


if __name__ == '__main__':
    unittest.main()
