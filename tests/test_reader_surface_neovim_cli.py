"""The native Neovim proof is explicit, isolated, and not the installed reader."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.reader_surfaces.__main__ import main
from sol.core.corpus import load_corpus_book
from sol.corpus import contract
from fixtures_corpus import write_runtime_corpus


class NeovimReaderCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-neovim-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.book = load_corpus_book(self.corpus)
        self.before = {p.name:p.read_bytes() for p in self.corpus.iterdir()}

    def tearDown(self):
        self.assertEqual(self.before, {p.name:p.read_bytes() for p in self.corpus.iterdir()})

    def call(self, *arguments):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            status = main(["--corpus", str(self.corpus), *arguments])
        return status, output.getvalue(), error.getvalue()

    def test_neovim_has_its_own_preflight_before_corpus_access(self):
        with patch("experiments.reader_surfaces.neovim.validate_environment", side_effect=ValueError("Neovim TTY unavailable")), \
                patch("sol.core.corpus.load_corpus_book", side_effect=AssertionError("No corpus I/O")), \
                patch("experiments.reader_surfaces.baseline.validate_reader_environment", side_effect=AssertionError("No Python view")):
            status, output, error = self.call("nvim")
        self.assertEqual(status, 2)
        self.assertFalse(output)
        self.assertIn("Neovim TTY unavailable", error)

    def test_neovim_receives_existing_sample_and_explicit_packet_paths(self):
        target, source = self.root / "out.json", self.root / "in.json"
        with patch("experiments.reader_surfaces.neovim.validate_environment") as preflight, \
                patch("experiments.reader_surfaces.neovim.run", return_value=0) as run, \
                patch("experiments.reader_surfaces.baseline.validate_reader_environment", side_effect=AssertionError("No Python view")):
            status, output, error = self.call("--count", "1", "nvim", "--width", "64",
                                               "--export", str(target), "--restore", str(source))
        self.assertEqual((status, output, error), (0, "", ""))
        preflight.assert_called_once_with(64)
        run.assert_called_once()
        sample = run.call_args.args[0]
        self.assertEqual(sample.passages[0].identifier, self.book.passages[0].identifier)
        self.assertEqual(sample.actions.snapshot().scope, ())
        self.assertIsNone(sample.actions.workspace_reader)
        self.assertEqual(run.call_args.kwargs, {"width":64,"export":target,"restore":source})
        self.assertFalse(target.exists())

    def test_existing_modes_do_not_validate_or_import_a_neovim_runtime(self):
        with patch("experiments.reader_surfaces.neovim.validate_environment", side_effect=AssertionError("No Neovim")):
            status, output, error = self.call("--count", "1", "inventory")
        self.assertEqual((status, error), (0, ""))
        self.assertIn('"sample_passages": 1', output)

    def test_named_trial_is_not_silently_replaced_for_neovim(self):
        with patch("experiments.reader_surfaces.neovim.validate_environment"), \
                patch("experiments.reader_surfaces.neovim.run", side_effect=AssertionError("No view")):
            status, output, error = self.call("--trial", "opening", "nvim")
        self.assertEqual(status, 2)
        self.assertFalse(output)
        self.assertIn("no substitute sample was chosen", error)


if __name__ == "__main__":
    unittest.main()
