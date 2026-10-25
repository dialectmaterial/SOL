"""Deterministic counting/formula properties over invented Unicode documents."""
from collections import Counter
from copy import deepcopy
import math
from pathlib import Path
import random
import tempfile
import unittest

from fixtures_corpus import CorpusFixture
from sol.essence import (CoreProvider, FileProvider, analyze_sentences, analyze_tfidf,
                         analyze_words, check_tfidf_result, compare_words,
                         decode_tfidf_result, encode_tfidf_result)
from sol.essence.essence_as_reflection_within_itself.sentences import _ABBREVIATIONS, segment, segment_v2


# Expected normalized words are specified independently of the tokenizer.
_ATOMS = (("Cafe\u0301", ("café",)), ("CAFÉ", ("café",)), ("isn’t", ("isn't",)),
          ("isn't", ("isn't",)), ("ﬃ", ("ffi",)), ("漢字", ("漢字",)),
          ("אבג", ("אבג",)), ("α\u0301", ("ά",)), ("Straße", ("strasse",)),
          ("soft\u00adhyphen", ("soft", "hyphen")), ("\u0301", ()), ("123", ()))


class FileMeasurementProperties(unittest.TestCase):
    def test_unicode_counts_sentence_totals_rates_and_log_ratios(self):
        with tempfile.TemporaryDirectory(prefix="sol-measurement-properties-") as directory:
            paths = [Path(directory) / name for name in ("target.txt", "reference.txt")]
            for seed in range(20):
                rng = random.Random(seed)
                expected = []
                for path in paths:
                    atoms = [rng.choice(_ATOMS) for _ in range(rng.randrange(1, 80))]
                    path.write_text("\n".join(raw for raw, _ in atoms), encoding="utf-8")
                    expected.append(Counter(word for _, words in atoms for word in words))
                providers = [FileProvider(path) for path in paths]
                study = analyze_words(providers[0], reference=providers[1])
                comparison = compare_words(providers[0], reference=providers[1], result=study)
                with self.subTest(seed=seed):
                    for name, counts, provider in zip(("target", "reference"), expected, providers):
                        total = sum(counts.values())
                        self.assertEqual(study[name]["summary"]["token_count"], total)
                        self.assertEqual(sum(row[name]["count"] for row in study["frequencies"]), total)
                        self.assertEqual(analyze_sentences(provider)["summary"]["tokens"], total)
                        for row in study["frequencies"]:
                            cell = row[name]
                            self.assertEqual(cell["count"], counts[row["word"]])
                            self.assertEqual(cell["rate_per_10000_tokens"],
                                             round(counts[row["word"]] * 10000 / total, 6) if total else None)
                    nt, nr = (sum(counts.values()) for counts in expected)
                    for row in comparison["rows"]:
                        a, b = (counts[row["word"]] for counts in expected)
                        if nt and nr:
                            self.assertEqual(row["rate_difference_per_10000_tokens"], round(10000 * (a / nt - b / nr), 6))
                        if a and b:
                            self.assertEqual(row["log2_rate_ratio"], round(math.log2(a / nt) - math.log2(b / nr), 6))
                        else:
                            self.assertIsNone(row["log2_rate_ratio"])

    def test_every_small_unicode_span_counts_only_whole_original_tokens(self):
        text = "e\u0301 ﬃ isn’t 漢字 אב"
        tokens = (("é", 0, 2), ("ffi", 3, 4), ("isn't", 5, 10), ("漢字", 11, 13), ("אב", 14, 16))
        with tempfile.TemporaryDirectory(prefix="sol-span-properties-") as directory:
            path = Path(directory) / "input.txt"
            path.write_text(text, encoding="utf-8")
            for start in range(len(text) + 1):
                for end in range(start, len(text) + 1):
                    result = analyze_words(FileProvider(path, {"kind": "span", "start": start, "end": end}))
                    expected = Counter(word for word, left, right in tokens if start <= left and right <= end)
                    with self.subTest(start=start, end=end):
                        self.assertEqual({row["word"]: row["target"]["count"] for row in result["frequencies"]}, dict(expected))
                        for row in result["frequencies"]:
                            _, _, left, right = row["target"]["locations"][0]
                            self.assertIn((row["word"], left, right), tokens)

    def test_all_declared_abbreviations_and_initial_chains_preserve_boundaries(self):
        for splitter in (segment, segment_v2):
            for abbreviation in sorted(_ABBREVIATIONS):
                text = f"Prefix {abbreviation}. Following material. Next."
                with self.subTest(method=splitter.__name__, abbreviation=abbreviation):
                    self.assertEqual([text[a:b] for a, b in splitter(text)],
                                     [f"Prefix {abbreviation}. Following material.", "Next."])
            for initials in ("A. B.", "G. W. F.", "Α. Β."):
                text = f"{initials} Example continues. Next."
                with self.subTest(method=splitter.__name__, initials=initials):
                    self.assertEqual([text[a:b] for a, b in splitter(text)],
                                     [f"{initials} Example continues.", "Next."])


class CoreTfidfProperties(CorpusFixture, unittest.TestCase):
    def test_document_vectors_are_l2_normalised_and_recompute_from_counts(self):
        for seed in range(8):
            rng = random.Random(seed)
            rows = deepcopy(self.book.corpus_snapshot.records[:1])
            template = deepcopy(self.book.corpus_snapshot.records[1])
            counts = []
            for index in range(6):
                words = [rng.choice(("red", "blue", "green", "amber")) for _ in range(rng.randrange(20))]
                text = " ".join(words) or "123"
                counts.append(Counter(words))
                row = deepcopy(template)
                row.update(id=f"bbbbbbbb-0000-4000-8000-{index + 2:012d}", order=index + 1,
                           markdown=text, plain_text=text)
                rows.append(row)
            self.write_records(rows)
            source = CoreProvider(self.book.corpus_snapshot)
            result = analyze_tfidf(source, top_n=1000)
            with self.subTest(seed=seed):
                self.assertEqual(len(result["documents"]), len(counts))
                overall = Counter()
                for document, terms in zip(result["documents"], counts):
                    actual = {row["word"]: row["score"] for row in document["top_terms"]}
                    weights = {word: count * (1 + math.log((1 + len(counts)) /
                               (1 + sum(word in other for other in counts)))) for word, count in terms.items()}
                    norm = math.sqrt(sum(weight ** 2 for weight in weights.values()))
                    self.assertEqual(actual, {word: round(weight / norm, 12) for word, weight in weights.items()})
                    self.assertAlmostEqual(sum(score ** 2 for score in actual.values()), 1 if terms else 0, places=10)
                    overall.update({word: weight / norm / len(counts) for word, weight in weights.items()})
                self.assertEqual({row["word"]: row["score"] for row in result["overall"]},
                                 {word: round(score, 12) for word, score in overall.items()})
                self.assertEqual(check_tfidf_result(source, decode_tfidf_result(encode_tfidf_result(result))), result)
