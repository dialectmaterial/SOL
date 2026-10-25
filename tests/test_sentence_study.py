"""The sentence study uses invented corpora; no PDF, model or network is involved."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sol.corpus import contract
from sol.essence.essence_as_reflection_within_itself.sentences import (
    SentenceStudyError, analyze_sentences, check_sentence_result, decode_sentence_result,
    encode_sentence_result, segment,
)
from fixtures_corpus import write_runtime_corpus
import hashlib
from sol import core

_GENERATED = {"markdown", "plain_text", "document", "context", "content_sha256"}


def sentences(text):
    return [text[start:end] for start, end in segment(text)]


class SegmentationTests(unittest.TestCase):
    def test_ordinary_sentences_and_dash_openings(self):
        self.assertEqual(sentences("Being, pure being – without further determination. It is pure "
                                   "emptiness. – There is nothing to be intuited in it."),
                         ["Being, pure being – without further determination.", "It is pure emptiness.",
                          "– There is nothing to be intuited in it."])

    def test_citations_abbreviations_and_initials_do_not_end_sentences(self):
        self.assertEqual(sentences("Newton (Princ. Math. Phil. Natu. Lib. II, Lemma II, Propos. VII) – the "
                                   "device, e.g. the product, see p. 113. G. W. F. Hegel wrote it. Next."),
                         ["Newton (Princ. Math. Phil. Natu. Lib. II, Lemma II, Propos. VII) – the device, "
                          "e.g. the product, see p. 113.", "G. W. F. Hegel wrote it.", "Next."])

    def test_variables_and_schemas_can_end_sentences(self):
        self.assertEqual(sentences("It is neither C nor D. Or also: the “I.” The middle is S-U-P. The P."),
                         ["It is neither C nor D.", "Or also: the “I.”", "The middle is S-U-P.", "The P."])

    def test_a_parenthesis_that_opens_the_sentence_still_splits(self):
        self.assertEqual(sentences("(Thus it is a square. Because it falls, it moves.) Then more."),
                         ["(Thus it is a square.", "Because it falls, it moves.)", "Then more."])

    def test_decimals_ellipses_lowercase_and_newlines(self):
        self.assertEqual(sentences("As 0.285714 . . . or 1 + a and so on. The series etc. are long.\nA list"),
                         ["As 0.285714 . . . or 1 + a and so on.", "The series etc. are long.", "A list"])


PARENTHETICAL = ["The diary says (A bell rang.", "Another bell answered.) before its owner leaves."]
WRAPPED = "The traveller carried\nan unopened letter."


class KnownRuleLimitations(unittest.TestCase):
    """Human-desired boundaries deliberately fail against the frozen v1 method.

    Unexpected success requires reviewing a method change, not updating gold to
    whatever the algorithm predicts. These cases document limits of the retained
    sentence segmenter.
    """
    @unittest.expectedFailure
    def test_sentence_inside_parenthesis_opened_mid_sentence(self):
        text = " ".join(PARENTHETICAL)
        self.assertEqual([text[a:b] for a, b in segment(text)], PARENTHETICAL)

    @unittest.expectedFailure
    def test_physical_line_break_inside_a_sentence_is_not_a_sentence_boundary(self):
        self.assertEqual([WRAPPED[a:b] for a, b in segment(WRAPPED)], [WRAPPED])

    @unittest.expectedFailure
    def test_an_abbreviation_can_also_end_a_sentence(self):
        gold = ["Consult ibid.", "Another account follows."]
        text = " ".join(gold)
        self.assertEqual([text[a:b] for a, b in segment(text)], gold)

    @unittest.expectedFailure
    def test_lowercase_sentence_start_is_a_boundary_when_marked_by_a_reviewer(self):
        gold = ["One event ends.", "another begins."]
        text = " ".join(gold)
        self.assertEqual([text[a:b] for a, b in segment(text)], gold)


class SentenceStudyTests(unittest.TestCase):
    def rewrite(self, modify):
        manifest = json.loads((self.corpus / "corpus.json").read_text())
        rows = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        modify(manifest, rows)
        for row in rows:
            row["content_sha256"] = hashlib.sha256(row["markdown"].encode()).hexdigest()
        markdown = "\n".join(contract.render_record(
            {key: value for key, value in row.items() if key not in _GENERATED}, row["markdown"])
            for row in rows)
        manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode()
        index_bytes = ("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                               + "\n" for row in rows)).encode()
        (self.corpus / "corpus.json").write_bytes(manifest_bytes)
        (self.corpus / "sample.md").write_text(markdown, encoding="utf-8")
        (self.corpus / "index.jsonl").write_bytes(index_bytes)
        (self.corpus / "index.meta.json").write_text(json.dumps({
            "contract_version": 1, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "source_sha256": manifest["source"]["sha256"],
            "documents": {"sample.md": hashlib.sha256(markdown.encode()).hexdigest()},
            "index_sha256": hashlib.sha256(index_bytes).hexdigest(), "record_count": len(rows),
        }), encoding="utf-8")
        return core.load_snapshot(self.corpus)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-sentence-study-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.snapshot = self.rewrite(lambda manifest, rows: self.add_prose(rows))

    @staticmethod
    def add_prose(rows):
        bodies = [("BEING", "Being is. Being is pure being, without further determination, it seems."),
                  ("BEING", "Nothing is empty. It is the same."),
                  ("ESSENCE", "Essence shines. Its shine is its own, as reflection.")]
        template = copy.deepcopy(rows[1])
        rows.pop()
        for number, (doctrine, body) in enumerate(bodies, 1):
            record = copy.deepcopy(template)
            record.update(id=f"cccccccc-0000-4000-8000-{number:012d}", order=number,
                          reader_path=f"/{doctrine}/synthetic-{number}.txt", markdown=body, plain_text=body)
            rows.append(record)
        rows[-1]["transcription_status"] = "needs_visual_review"

    def test_lengths_positions_and_exclusions(self):
        result = analyze_sentences(self.snapshot)
        self.assertEqual([row[3] for row in result["sentences"]], [2, 9, 3, 4])
        self.assertEqual(result["summary"], {"sentences": 4, "tokens": 18, "mean": 4.5, "median": 3,
                                             "p10": 2, "p90": 9, "max": 9})
        self.assertEqual(result["by_position"]["last"]["sentences"], 2)
        self.assertEqual(result["longest"][0], 1)
        self.assertEqual(result["exclusions"]["by_reason"]["review"], 1)
        self.assertNotIn("Being is", encode_sentence_result(result), "artifacts store offsets, not book text")

    def test_scope_by_path_and_by_passages(self):
        within = analyze_sentences(self.snapshot, scope={"kind": "within", "path": "/BEING/synthetic-2.txt"})
        self.assertEqual([passage["id"] for passage in within["passages"]], ["cccccccc-0000-4000-8000-000000000002"])
        chosen = analyze_sentences(self.snapshot, scope={"kind": "passages",
                                                         "ids": ["cccccccc-0000-4000-8000-000000000001"]})
        self.assertEqual(chosen["summary"]["sentences"], 2)
        with self.assertRaises(SentenceStudyError):
            analyze_sentences(self.snapshot, scope={"kind": "passages", "ids": ["not-in-this-corpus"]})

    def test_malformed_saved_scopes_are_typed_refusals(self):
        original = analyze_sentences(self.snapshot)
        for scope in ({"kind": []}, {"kind": {}},
                      {"kind": "passages", "ids": [{}]},
                      {"kind": "passages", "ids": [[]]}):
            altered = copy.deepcopy(original)
            altered["scope"] = scope
            with self.subTest(scope=scope):
                with self.assertRaises(SentenceStudyError) as caught:
                    decode_sentence_result(json.dumps(altered))
                self.assertEqual(caught.exception.code, "invalid_scope")

    def test_check_recomputes_and_refuses_tampering_or_a_changed_corpus(self):
        result = analyze_sentences(self.snapshot)
        decoded = decode_sentence_result(encode_sentence_result(result))
        self.assertEqual(check_sentence_result(self.snapshot, decoded), result)
        tampered = copy.deepcopy(result)
        tampered["sentences"][0][3] = 3
        with self.assertRaises(SentenceStudyError) as refused:
            check_sentence_result(self.snapshot, tampered)
        self.assertEqual(refused.exception.code, "result_mismatch")
        changed = self.rewrite(lambda manifest, rows: rows[1].update(markdown="Being is. Changed.",
                                                                     plain_text="Being is. Changed."))
        with self.assertRaises(SentenceStudyError) as stale:
            check_sentence_result(changed, result)
        self.assertEqual(stale.exception.status, "stale")

    def test_cli_runs_and_checks_a_saved_study(self):
        command = [sys.executable, "-B", "-m", "sol", "essence"]
        study = subprocess.run(command + ["sentences", "--corpus", str(self.corpus), "--json"],
                               capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(study)["protocol"], "sol.sentence-study")
        saved = self.root / "study.json"
        saved.write_text(study, encoding="utf-8")
        checked = subprocess.run(command + ["check", str(saved), "--corpus", str(self.corpus)],
                                 capture_output=True, text=True, check=True).stdout
        self.assertIn("Verified against the current corpus generation.", checked)
        self.assertIn("4 sentences, 18 tokens in 2 passages.", checked)


if __name__ == "__main__":
    unittest.main()
