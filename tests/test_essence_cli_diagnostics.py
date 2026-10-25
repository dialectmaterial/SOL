"""Exercise real CLI transports and bad paths with invented input only."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.essence import FileProvider, WordStudyError, analyze_words
from sol.essence.cli import main


class EssenceCLIDiagnosticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-cli-diagnostics-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "input.txt"
        self.source.write_text("Invented words only.", encoding="utf-8")

    def call(self, args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(args)
        return status, out.getvalue(), err.getvalue()

    def test_truncated_json_is_reported_as_invalid_json_not_an_unknown_protocol(self):
        saved = self.root / "truncated.json"
        for content in ('', '{"protocol":"sol.word-frequencies",', b'\xff'):
            saved.write_bytes(content.encode() if isinstance(content, str) else content)
            status, output, error = self.call(["check", str(saved), "--json"])
            self.assertEqual(status, 2)
            self.assertIn("JSON", error)
            self.assertNotIn("Unsupported", error)
            self.assertIn("JSON", json.loads(output)["error"])

    def test_unknown_home_is_a_typed_file_input_refusal(self):
        with patch.object(Path, "expanduser", side_effect=RuntimeError("Could not determine home directory.")):
            with self.assertRaises(WordStudyError):
                analyze_words(FileProvider(self.source))

    def test_unknown_home_paths_never_escape_the_cli(self):
        bad = "~invented-no-home-for-sol/source"
        expanduser = Path.expanduser

        def expand(path):
            if path == Path(bad):
                raise RuntimeError("Could not determine home directory.")
            return expanduser(path)

        cases = (["words", "--file", bad],
                 ["sentences", "--file", bad],
                 ["tfidf", "--file", bad],
                 ["prose", "--corpus", bad],
                 ["sentences", "--corpus", bad],
                 ["sentences", "--reference", bad],
                 ["words", "--corpus", bad],
                 ["words", "--file", str(self.source), "--reference-corpus", bad],
                 ["words", "--file", str(self.source), "--reference-file", bad],
                 ["check", bad], ["words-export", bad])
        for args in cases:
            with self.subTest(args=args), patch.object(Path, "expanduser", autospec=True, side_effect=expand):
                status, output, error = self.call(args)
                self.assertEqual((status, output), (2, ""))
                self.assertIn("home directory", error)

    def test_early_closed_pipes_are_quiet_for_installed_and_module_dispatch(self):
        # Distinct alphabetic words make the human table larger than a pipe buffer.
        self.source.write_text(" ".join("term" + chr(97 + i // 676) + chr(97 + i // 26 % 26)
                                        + chr(97 + i % 26) for i in range(4000)))
        for module, prefix in (("sol", ["essence"]), ("sol.essence.cli", [])):
            with self.subTest(module=module), subprocess.Popen(
                    [sys.executable, "-B", "-m", module, *prefix, "words", "--file", str(self.source)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                self.assertTrue(process.stdout.readline())
                process.stdout.close()
                error = process.stderr.read().decode()
                status = process.wait(timeout=10)
                self.assertEqual((status, error), (0, ""))

    def test_buffered_output_failure_is_also_quiet(self):
        for failure in ("write", "flush"):
            class ClosedOutput(StringIO):
                failed = False

                def write(self, value):
                    if failure == "write":
                        self.failed = True
                        raise BrokenPipeError("invented closed output pipe")
                    return super().write(value)

                def flush(self):
                    self.failed = True
                    raise BrokenPipeError("invented closed output pipe")

            output, error = ClosedOutput(), StringIO()
            with self.subTest(failure=failure), redirect_stdout(output), redirect_stderr(error):
                status = main(["words", "--file", str(self.source)])
                self.assertEqual((status, error.getvalue()), (0, ""))
                self.assertTrue(output.failed)
