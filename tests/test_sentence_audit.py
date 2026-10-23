"""Audit accounting against invented offsets, independent of the segmenter."""
from hashlib import sha256
import unittest

from scripts.sentence_audit import score


class SentenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.text = "A. B. C."
        self.sample = [{"id": "invented", "plain_text": self.text}]
        self.gold = [{"id": "invented", "text_sha256": sha256(self.text.encode()).hexdigest(), "ends": [2, 5]}]

    def test_exact_internal_boundaries_do_not_get_credit_for_forced_passage_end(self):
        # One correct, one spurious, one missed; terminal offset excluded.
        result = score(self.sample, self.gold, lambda text: [(0, 2), (3, 4), (5, 8)])
        self.assertEqual(result, {"tp": 1, "fp": 1, "fn": 1, "predicted": 2, "gold": 2,
                                  "passages_with_errors": 1, "precision": 0.5, "recall": 0.5})

    def test_foreign_annotations_and_invalid_offsets_are_refused(self):
        for change in ({"id": "foreign"}, {"text_sha256": "0" * 64}, {"ends": [2, 2]},
                       {"ends": [5, 2]}, {"ends": [8]}, {"ends": [True]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                score(self.sample, [{**self.gold[0], **change}], lambda text: [])
        with self.assertRaises(ValueError):
            score(self.sample, [], lambda text: [])
