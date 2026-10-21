"""Canonical reading and comparison as real shell commands."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import fcntl
import pty
import select
import shutil
import struct
import termios
import time
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.reader import app
from fixtures_corpus import write_runtime_corpus


class NativeCommandsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sol-native-commands-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.corpus = self.root / "corpus with spaces"
        self.identifier, self.body = write_runtime_corpus(self.corpus)
        self.env = {**os.environ, "SOL_CORPUS": str(self.corpus), "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    def run_cli(self, arguments, cwd=None):
        return subprocess.run([sys.executable, "-B", "-m", "sol", *arguments],
                              cwd=cwd or self.corpus, env=self.env, text=True, capture_output=True)

    def test_read_preserves_headings_and_unwrapped_body_from_cwd(self):
        result = self.run_cli(["read", "sample.md", "--plain"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Synthetic section", result.stdout)
        self.assertIn(self.body, result.stdout.splitlines())
        self.assertNotIn(self.identifier, result.stdout)

    def test_absolute_and_corpus_relative_paths_match(self):
        absolute = self.run_cli(["read", str(self.corpus / "sample.md"), "--plain"], cwd=self.root)
        relative = self.run_cli(["read", "sample.md", "--plain"], cwd=self.root)
        self.assertEqual(absolute.returncode, 0, absolute.stderr)
        self.assertEqual(relative.stdout, absolute.stdout)

    def test_existing_outside_file_is_not_silently_resolved_to_corpus(self):
        (self.root / "sample.md").write_text("Unrelated host file")
        result = self.run_cli(["read", "sample.md"], cwd=self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("inside the configured SOL corpus", result.stderr)
        self.assertFalse(result.stdout)

    def test_markdown_and_json_preserve_exact_canonical_records(self):
        result = self.run_cli(["read", "sample.md", "--json"])
        self.assertEqual(result.returncode, 0, result.stderr)
        snapshot = json.loads(result.stdout)
        self.assertEqual([r["type"] for r in snapshot["records"]], ["section", "paragraph"])
        paragraph = snapshot["records"][1]
        self.assertEqual(paragraph["id"], self.identifier)
        self.assertEqual(paragraph["plain_text"], self.body)
        self.assertTrue(paragraph["attribution"])
        self.assertTrue(paragraph["sources"])
        markdown = self.run_cli(["read", "sample.md", "--markdown"])
        self.assertEqual(markdown.stdout, "\n\n".join(r["markdown"] for r in snapshot["records"]) + "\n")

    def test_virtual_path_compatibility_and_missing_file_errors(self):
        result = self.run_cli(["read", "/BEING/synthetic.txt", "--plain"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.body, result.stdout)
        result = self.run_cli(["read", "missing.md"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("Not a canonical Markdown file", result.stderr)

    def test_real_zsh_pipeline_redirection_and_current_directory(self):
        zsh = shutil.which("zsh")
        if not zsh or not shutil.which("rg"):
            self.skipTest("the native pipeline check requires Zsh and ripgrep")
        output = self.root / "reading output.txt"
        # Positional arguments carry paths; no interpolated shell code.
        script = 'cd -- "$1" && "$2" -B -m sol read sample.md --plain | rg --fixed-strings "$3" > "$4"'
        result = subprocess.run([zsh, "-f", "-c", script, "sol-test", str(self.corpus),
                                 sys.executable, self.body, str(output)], env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), self.body + "\n")


    def test_readonly_commands_do_not_change_corpus_files(self):
        before = {p.name: p.read_bytes() for p in self.corpus.iterdir()}
        self.run_cli(["read", "sample.md"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.corpus.iterdir()})

if __name__ == "__main__":
    unittest.main()
