"""Measurement shape and isolation, never timing thresholds or book extracts."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import reader_timings as timings


class ReaderTimingTests(unittest.TestCase):
    def test_synthetic_report_contains_every_operation_and_repeat(self):
        with patch.dict(os.environ, {"SOL_CORPUS": "/must-not-discover-a-personal-book"}):
            environment = dict(os.environ)
            report = timings.benchmark(repeats=2, warmups=1)
            self.assertEqual(dict(os.environ), environment)
        self.assertEqual(set(report["operations"]), set(timings.OPERATIONS))
        for row in report["operations"].values():
            self.assertEqual(len(row["samples_ms"]), 2)
            self.assertEqual(set(row), {"median_ms", "min_ms", "max_ms", "p25_ms", "p75_ms", "samples_ms"})
            self.assertTrue(all(math.isfinite(value) and value >= 0 for value in row["samples_ms"]))
        self.assertEqual(report["dataset"]["kind"], "synthetic")
        self.assertEqual(report["dataset"]["ordinary"]["linked_notes"], 0)
        self.assertEqual(report["dataset"]["footnote_heavy"]["linked_notes"], 9)
        self.assertEqual(report["dataset"]["controller_study_section"]["passages"], 3)
        self.assertNotIn("Another **claim** follows", json.dumps(report))

    def test_explicit_corpus_is_read_only_and_temporary_state_is_removed(self):
        with tempfile.TemporaryDirectory(prefix="sol-timing-test-") as temporary:
            corpus = timings.synthetic_corpus(Path(temporary) / "source")
            before = {path.relative_to(corpus): path.read_bytes() for path in corpus.rglob("*") if path.is_file()}
            # No importer or canonical write is permitted on explicitly supplied data.
            with patch.object(timings.contract, "reindex", side_effect=AssertionError("must not reindex")):
                report = timings.benchmark(corpus, repeats=1, warmups=0, width=38)
            after = {path.relative_to(corpus): path.read_bytes() for path in corpus.rglob("*") if path.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(report["dataset"]["kind"], "explicit local corpus")
            self.assertEqual(report["width"], 38)
            self.assertEqual(list(Path(temporary).iterdir()), [corpus])

    def test_cli_defaults_to_synthetic_without_a_terminal_or_neovim(self):
        script = Path(timings.__file__)
        result = subprocess.run([sys.executable, "-B", str(script), "--repeats", "1", "--warmups", "0", "--json"],
                                capture_output=True, text=True, timeout=20, cwd=script.parents[1])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(set(report["operations"]), set(timings.OPERATIONS))
        self.assertIn("No Neovim process", " ".join(report["limits"]))

    def test_invalid_parameters_and_missing_source_refuse_instead_of_fabricating_timings(self):
        for arguments in ({"repeats": 0}, {"repeats": True}, {"repeats": 31},
                          {"warmups": -1}, {"width": 19}, {"width": 241}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                timings.benchmark(**arguments)
        with tempfile.TemporaryDirectory(prefix="sol-timing-missing-") as temporary:
            with self.assertRaises(ValueError):
                timings.benchmark(Path(temporary) / "missing", repeats=1, warmups=0)


if __name__ == "__main__":
    unittest.main()
