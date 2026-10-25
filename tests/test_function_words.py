"""The declared display vocabulary, also run against the wheel by packaging tests."""
import unittest

from sol.essence.function_words import load_function_words
from sol.essence.essence_as_reflection_within_itself.tokenization import word_tokens


class FunctionWordsTests(unittest.TestCase):
    def test_identity_and_criteria(self):
        catalog = load_function_words()
        self.assertEqual(set(catalog), {"id", "version", "criteria", "categories", "words"})
        self.assertEqual(catalog["id"], "english-closed-class-v1")
        self.assertEqual(catalog["version"], 1)
        self.assertIsInstance(catalog["criteria"], str)
        self.assertTrue(catalog["criteria"].strip())

    def test_sorted_unique_categories_and_token_union(self):
        catalog = load_function_words()
        categories = catalog["categories"]
        self.assertTrue(categories)
        self.assertEqual(list(categories), sorted(categories))
        flattened = []
        for name, words in categories.items():
            with self.subTest(category=name):
                self.assertTrue(words)
                self.assertEqual(words, sorted(words))
                for word in words:
                    self.assertEqual(list(word_tokens(word)), [(word, 0, len(word))])
                    self.assertNotIn("’", word)
                flattened.extend(words)
        self.assertEqual(len(flattened), len(set(flattened)))
        self.assertIsInstance(catalog["words"], frozenset)
        self.assertEqual(catalog["words"], frozenset(flattened))

    def test_grammatical_coverage_and_philosophical_exception(self):
        words = load_function_words()["words"]
        self.assertTrue({"the", "a", "an", "each", "he", "my", "ours", "herself",
                         "which", "this", "of", "and", "if", "to", "not", "never",
                         "also", "out", "can't", "it's", "we've",
                         "am", "are", "be", "been", "is", "was", "were",
                         "have", "has", "had", "having", "do", "does", "did",
                         "can", "could", "may", "might", "must", "shall", "should",
                         "will", "would"} <= words)
        self.assertTrue(words.isdisjoint({"being", "other", "one", "many",
                                         "beyond", "itself", "beings", "essence", "concept",
                                         "ground", "nothing", "becoming"}))

    def test_loads_are_independent(self):
        catalog = load_function_words()
        original = load_function_words()
        catalog["categories"]["determiners"].append("invented")
        catalog["id"] = "changed"
        self.assertEqual(load_function_words(), original)


if __name__ == "__main__":
    unittest.main()
