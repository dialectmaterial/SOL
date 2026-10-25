"""Bound pathological punctuation inputs without changing segmentation methods."""
import random
import re
import subprocess
import sys
import unittest

from sol.essence.essence_as_reflection_within_itself import sentences


class SentencePerformanceTests(unittest.TestCase):
    def test_long_nonmatching_word_suffix_does_not_stall_either_method(self):
        code = '''
from sol.essence.essence_as_reflection_within_itself.sentences import segment, segment_v2
for splitter in (segment, segment_v2):
    for suffix, end in ((" . Next.", 60002), ("1b. Next.", 60003)):
        text = "a" * 60000 + suffix
        assert splitter(text) == [(0, end), (end + 1, len(text))]
'''
        run = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, timeout=3)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_repeated_abbreviations_do_not_copy_the_entire_sentence(self):
        code = '\n'.join((
            "from sol.essence.essence_as_reflection_within_itself.sentences import segment, segment_v2",
            "text = 'p. A ' * 80000",
            "for splitter in (segment, segment_v2):",
            "    assert splitter(text) == [(0, len(text) - 1)]",
        ))
        run = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, timeout=3)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_leading_padding_and_attached_period_chains_do_not_rescan(self):
        code = '\n'.join((
            "from sol.essence.essence_as_reflection_within_itself.sentences import segment, segment_v2",
            "for splitter in (segment, segment_v2):",
            "    text = ' ' * 60000 + 'p. A ' * 6000",
            "    assert splitter(text) == [(60000, len(text) - 1)]",
            "    text = 'a.' * 60000",
            "    assert splitter(text) == [(0, len(text))]",
        ))
        run = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, timeout=3)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_suffix_optimization_matches_the_original_regex(self):
        rng = random.Random(20261025)
        alphabet = "aApPéαΓⅣ²3_. '’\t\n\u0301"
        texts = ["", "a.approx", "A..B", "word ", "word\n", "word\n\n", "a" * 100 + "1b"]
        texts += ["".join(rng.choices(alphabet, k=rng.randrange(80))) for _ in range(1000)]
        for text in texts:
            start = rng.randrange(len(text) + 1)
            end = rng.randrange(start, len(text) + 1)
            old = re.search(r"([^\W\d_]+(?:\.[^\W\d_]+)*)$", text[start:end])
            expected = old.group(1) if old else ""
            with self.subTest(text=text, start=start, end=end):
                self.assertEqual(sentences._ending_token(text, start, end), expected)


if __name__ == "__main__":
    unittest.main()
