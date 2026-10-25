"""Legacy sentence receipts must agree with their rows; invented fixtures only."""
from copy import deepcopy
import json
import unicodedata
import unittest

from fixtures_sentence_v1 import BASELINES
from sol.essence import decode_sentence_result, encode_sentence_result
from sol.essence.essence_as_reflection_within_itself.sentences import SentenceStudyError


class SentenceReceiptInvariantTests(unittest.TestCase):
    def receipt(self):
        result = json.loads(BASELINES["corpus"])
        result["method"]["unicode_version"] = unicodedata.unidata_version
        return result

    def test_legacy_derived_statistics_must_agree_with_rows(self):
        changes = (
            lambda r: r["summary"].update(tokens=999),
            lambda r: r["summary"].update(mean=None),
            lambda r: r["histogram"][0].update(sentences=1),
            lambda r: r["by_position"]["only"].update(tokens=0),
            lambda r: r.update(longest=[]),
            lambda r: r.update(summary=[]),
        )
        for change in changes:
            result = self.receipt()
            change(result)
            for operation in (lambda: decode_sentence_result(json.dumps(result)),
                              lambda: encode_sentence_result(result)):
                with self.subTest(change=change, operation=operation), self.assertRaises(SentenceStudyError):
                    operation()

    def test_legacy_counts_are_checked_per_passage_not_just_in_total(self):
        result = self.receipt()
        other = deepcopy(result["passages"][0])
        other.update(id="bbbbbbbb-0000-4000-8000-000000000003", sentences=0)
        result["passages"].append(other)
        result["exclusions"]["input_records"] += 1
        # Still one sentence in total, but its declared passage has none.
        result["passages"][0]["sentences"] = 0
        result["passages"][1]["sentences"] = 1
        with self.assertRaises(SentenceStudyError):
            decode_sentence_result(json.dumps(result))

    def test_valid_legacy_encodings_remain_byte_identical(self):
        for name, raw in BASELINES.items():
            with self.subTest(name=name):
                raw = raw.replace('"unicode_version":"16.0.0"',
                                  '"unicode_version":' + json.dumps(unicodedata.unidata_version))
                self.assertEqual(encode_sentence_result(decode_sentence_result(raw)), raw)
