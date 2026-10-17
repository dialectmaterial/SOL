"""Same-start comparisons use the existing reader without a personal workspace."""
from contextlib import redirect_stdout, redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.reader_surfaces.__main__ import main
from sol.corpus import contract
from sol.reader.actions import ReaderActions
from fixtures_corpus import write_runtime_corpus
from test_reader_actions import IDS, invented_book


class ReaderSurfaceBaselineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-surface-baseline-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        self.identifier, _ = write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.before = {p.name: p.read_bytes() for p in self.corpus.iterdir()}

    def tearDown(self):
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.corpus.iterdir()})
        self.assertFalse(list(self.root.rglob("*.sqlite3")))

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(["--corpus", str(self.corpus), *args])
        return status, out.getvalue(), err.getvalue()

    def test_preflight_refuses_nonterminal_before_loading_corpus_or_view(self):
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment", side_effect=ValueError("interactive terminal required")), \
                patch("sol.core.corpus.load_corpus_book", side_effect=AssertionError("must not load")), \
                patch("experiments.reader_surfaces.baseline.ReaderView", side_effect=AssertionError("must not open")):
            status, out, err = self.invoke("baseline")
        self.assertEqual(status, 2)
        self.assertFalse(out)
        self.assertIn("interactive terminal", err)

    def test_preflight_refuses_missing_optional_dependencies_before_loading(self):
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment", side_effect=ImportError("optional toolkit absent")), \
                patch("sol.core.corpus.load_corpus_book", side_effect=AssertionError("must not load")):
            status, out, err = self.invoke("baseline")
        self.assertEqual(status, 2)
        self.assertFalse(out)
        self.assertIn("optional toolkit", err)

    def test_default_launch_uses_existing_reader_actions_and_never_prompts(self):
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment") as preflight, \
                patch("experiments.reader_surfaces.baseline.ReaderView") as view, \
                patch("builtins.input", side_effect=AssertionError("no workspace prompt")):
            view.return_value.run.return_value = 0
            status, out, err = self.invoke("baseline")
        self.assertEqual((status, out, err), (0, "", ""))
        preflight.assert_called_once_with()
        view.assert_called_once()
        actions = view.call_args.args[0]
        self.assertIsInstance(actions, ReaderActions)
        self.assertIsNone(actions.workspace_reader)
        self.assertEqual(actions.snapshot().current.identifier, self.identifier)
        self.assertEqual(actions.snapshot().scope, ())
        self.assertEqual(actions.cursor_offset, 0)
        self.assertEqual(view.call_args.kwargs, {"width": 72})
        view.return_value.run.assert_called_once_with()

    def test_requested_existing_id_selects_same_start_and_preserves_width(self):
        book = invented_book()
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment"), \
                patch("sol.core.corpus.load_corpus_book", return_value=book), \
                patch("experiments.reader_surfaces.baseline.ReaderView") as view:
            view.return_value.run.return_value = 0
            status, out, err = self.invoke("--start", IDS[1], "--count", "1", "baseline", "--width", "88")
        self.assertEqual((status, out, err), (0, "", ""))
        actions = view.call_args.args[0]
        self.assertIs(actions.book, book)
        self.assertIs(actions.snapshot().current, book.passages[1])
        self.assertEqual(actions.snapshot().scope, ())
        self.assertEqual(view.call_args.kwargs, {"width": 88})

    def test_unambiguous_prefix_reuses_existing_resolution(self):
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment"), \
                patch("experiments.reader_surfaces.baseline.ReaderView") as view:
            view.return_value.run.return_value = 0
            status, out, err = self.invoke("--start", self.identifier[:8], "baseline")
        self.assertEqual((status, out, err), (0, "", ""))
        self.assertEqual(view.call_args.args[0].snapshot().current.identifier, self.identifier)

    def test_count_does_not_fence_the_original_readers_ordinary_scope(self):
        book = invented_book()
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment"), \
                patch("sol.core.corpus.load_corpus_book", return_value=book), \
                patch("experiments.reader_surfaces.baseline.ReaderView") as view:
            view.return_value.run.return_value = 0
            status, _, err = self.invoke("--count", "1", "baseline")
        self.assertEqual((status, err), (0, ""))
        actions = view.call_args.args[0]
        self.assertIs(actions.snapshot().current, book.passages[0])
        self.assertIs(actions.move(1), book.passages[1])
        self.assertIsNone(actions.workspace_reader)

    def test_same_start_retains_normal_whole_work_scope_across_section_boundaries(self):
        book = invented_book()
        self.assertNotEqual(book.passages[1].path, book.passages[2].path)
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment"), \
                patch("sol.core.corpus.load_corpus_book", return_value=book), \
                patch("experiments.reader_surfaces.baseline.ReaderView") as view:
            view.return_value.run.return_value = 0
            status, out, err = self.invoke("--start", IDS[1], "--count", "2", "baseline")
        self.assertEqual((status, out, err), (0, "", ""))
        actions = view.call_args.args[0]
        self.assertEqual(actions.snapshot().scope, ())
        self.assertIs(actions.snapshot().current, book.passages[1])
        # These are the source actions used by the reader's b/n bindings.
        self.assertIs(actions.move_paragraph(1), book.passages[2])
        self.assertIs(actions.move_paragraph(-1), book.passages[1])
        self.assertEqual(actions.snapshot().scope, ())
        self.assertIsNone(actions.workspace_reader)

    def test_invalid_start_or_count_does_not_open_reader(self):
        for args in (("--start", "missing"), ("--count", "0"), ("--count", "65")):
            with self.subTest(args=args), patch("experiments.reader_surfaces.baseline.validate_reader_environment"), \
                    patch("experiments.reader_surfaces.baseline.ReaderView") as view:
                status, out, err = self.invoke(*args, "baseline")
            self.assertEqual(status, 2)
            self.assertFalse(out)
            self.assertTrue(err)
            view.assert_not_called()

    def test_invalid_width_uses_existing_reader_validation_without_loading_toolkit(self):
        for width in ("19", "241"):
            with self.subTest(width=width), patch("experiments.reader_surfaces.baseline.validate_reader_environment"), \
                    patch("experiments.reader_surfaces.baseline._load_toolkit", side_effect=AssertionError("must not load toolkit")):
                status, out, err = self.invoke("baseline", "--width", width)
            self.assertEqual(status, 2)
            self.assertFalse(out)
            self.assertIn("20 and 240", err)

    def test_original_reader_return_status_and_errors_are_not_hidden(self):
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment"), \
                patch("experiments.reader_surfaces.baseline.ReaderView") as view:
            view.return_value.run.return_value = 1
            self.assertEqual(self.invoke("baseline"), (1, "", ""))
            view.return_value.run.side_effect = OSError("terminal unavailable")
            status, out, err = self.invoke("baseline")
        self.assertEqual(status, 2)
        self.assertFalse(out)
        self.assertIn("terminal unavailable", err)
