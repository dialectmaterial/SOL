"""Impossible word receipts must stop before building an unbounded result table."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.essence import FileProvider, WordStudyError, analyze_tfidf, analyze_words, encode_word_result
from sol.essence.essence_as_reflection_within_itself.tokenization import word_tokens


class WordResultBudgetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-word-budget-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "input.txt"
        self.path.write_text(" ".join("word" + chr(97 + i // 26) + chr(97 + i % 26) for i in range(500)))

    def test_impossible_vocabulary_is_refused_before_exhausting_tokens(self):
        def guarded(text):
            yield from word_tokens(text)
            self.fail("An impossible result consumed the whole vocabulary before refusing it")

        for analyze in (analyze_words, analyze_tfidf):
            with self.subTest(analyze=analyze.__name__), \
                    patch("sol.essence.essence_as_reflection_within_itself.words.MAX_RESULT_BYTES", 4096), \
                    patch("sol.essence.essence_as_reflection_within_itself.words.word_tokens", side_effect=guarded):
                with self.assertRaises(WordStudyError) as caught:
                    analyze(FileProvider(self.path))
                self.assertEqual(caught.exception.code, "size_limit")

    def test_exact_valid_output_budget_and_repeated_words_are_unchanged(self):
        self.path.write_text("Cafe\u0301 漢字 isn't " * 500)
        source = FileProvider(self.path)
        result = analyze_words(source, reference=source)
        size = len(encode_word_result(result).encode()) + 1
        with patch("sol.essence.essence_as_reflection_within_itself.words.MAX_RESULT_BYTES", size):
            self.assertEqual(analyze_words(source, reference=source), result)
        with patch("sol.essence.essence_as_reflection_within_itself.words.MAX_RESULT_BYTES", size - 1):
            with self.assertRaises(WordStudyError):
                analyze_words(source, reference=source)

    def test_words_outside_a_span_do_not_spend_the_result_budget(self):
        source = FileProvider(self.path, {"kind": "span", "start": 0, "end": 6})
        result = analyze_words(source)
        size = len(encode_word_result(result).encode()) + 1
        with patch("sol.essence.essence_as_reflection_within_itself.words.MAX_RESULT_BYTES", size):
            self.assertEqual(analyze_words(source), result)
