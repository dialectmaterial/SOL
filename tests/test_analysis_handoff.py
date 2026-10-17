"""A native lexical experiment can return a verified hit without personal writes."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sol import core
from sol.corpus import contract
from sol.reader.actions import ReaderActions
from sol.terminal.handoff import HandoffSession
from fixtures_corpus import write_runtime_corpus


class AnalysisHandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-analysis-handoff-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        self.identifier, _ = write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.book = core.load_corpus_book(self.corpus)
        self.reader = ReaderActions(self.book)
        self.reader.open(self.identifier)
        self.exchange = HandoffSession.create(self.reader.capture_active_reference())
        self.addCleanup(self.exchange.close)
        self.environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                            "XDG_CONFIG_HOME": str(self.root / "config"),
                            "XDG_DATA_HOME": str(self.root / "data"),
                            "SOL_CORPUS": str(self.corpus), "SOL_HANDOFF_DIR": str(self.exchange.directory)}
        self.result_file = self.root / "invented.sol-analysis.json"
        self.originals = {path.name: path.read_bytes() for path in self.corpus.iterdir()}

    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, "-B", "-m", "sol", *arguments],
                              cwd=self.root, env=self.environment, capture_output=True, timeout=10)

    def study(self):
        result = self.run_cli("analyze", "term", "invented", "--reference", str(self.exchange.outgoing_file), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.result_file.write_bytes(result.stdout)
        return json.loads(result.stdout)

    def test_read_compute_check_propose_and_deliberately_return_preserves_the_reference(self):
        artifact = self.study()
        self.assertEqual(artifact["origin"]["reference"]["requested_id"], self.identifier)
        self.assertEqual(artifact["totals"]["occurrences"], 1)
        selected = artifact["matches"][0]["id"]
        self.assertEqual(selected, self.identifier)
        checked = self.run_cli("analyze", "check", str(self.result_file), "--json")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["status"], "current")
        proposed = self.run_cli("reference", "return", selected)
        self.assertEqual(proposed.returncode, 0, proposed.stderr)
        self.assertEqual(json.loads(proposed.stdout)["status"], "proposed")
        packet = self.exchange.read_return()
        self.assertEqual(self.reader.check_return_reference(packet).target_id, selected)
        self.assertEqual(self.reader.session.current().identifier, self.identifier)
        self.assertEqual(self.reader.accept_return_reference(packet).identifier, selected)
        self.assertEqual(self.originals, {path.name: path.read_bytes() for path in self.corpus.iterdir()})
        self.assertFalse((self.root / "config").exists())
        self.assertFalse((self.root / "data").exists())

    def test_experiment_result_is_not_itself_a_navigation_packet_or_an_annotation(self):
        artifact = self.study()
        with self.assertRaises(core.ProtocolError):
            self.reader.accept_return_reference(artifact)
        self.assertFalse((self.exchange.directory / "returned.json").exists())
        self.assertFalse(list(self.root.glob("*.sqlite3")))

    def test_help_dispatch_does_not_read_a_corpus_or_start_workspace_onboarding(self):
        from sol.reader import app
        from unittest.mock import patch

        for arguments in (["analyze", "--help"], ["analyze", "term", "--help"], ["analyze", "check", "--help"]):
            with self.subTest(arguments=arguments), \
                    patch.object(core, "discover_corpus", side_effect=AssertionError("No corpus for help")), \
                    patch("builtins.input", side_effect=AssertionError("No onboarding for help")), \
                    redirect_stdout(StringIO()), self.assertRaises(SystemExit) as caught:
                app.main(arguments)
            self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
