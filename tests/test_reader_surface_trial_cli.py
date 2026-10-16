"""Named reading-trial launchers keep their derived extent and ordinary scope."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.reader_surfaces.__main__ import main
from experiments.reader_surfaces.common import sample_from_book
from experiments.reader_surfaces.trials import select_trial
from test_reader_surface_trials import trial_book


class ReaderSurfaceTrialCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-named-trial-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(["--corpus", str(self.corpus), *args])
        return status, out.getvalue(), err.getvalue()

    def test_conflicting_and_unknown_trials_are_rejected_before_loading(self):
        cases = (
            ("--trial", "beginning", "--start", "invented-id", "inventory"),
            ("--start", "invented-id", "--trial", "opening", "inventory"),
            ("--trial", "beginning", "--count", "24", "inventory"),
            ("--count", "0", "--trial", "opening", "inventory"),
            ("--trial", "missing", "inventory"),
        )
        with patch("sol.core.corpus.load_corpus_book") as load:
            for arguments in cases:
                with self.subTest(arguments=arguments), \
                        redirect_stdout(io.StringIO()) as out, \
                        redirect_stderr(io.StringIO()) as err:
                    with self.assertRaises(SystemExit) as stopped:
                        main(["--corpus", str(self.corpus), *arguments])
                    self.assertEqual(stopped.exception.code, 2)
                    self.assertFalse(out.getvalue())
                    self.assertIn("error:", err.getvalue())
            load.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_nontrial_default_still_selects_twenty_four_without_trial_metadata(self):
        book, _ = trial_book(opening_counts=(10, 10, 10))
        with patch("sol.core.corpus.load_corpus_book", return_value=book), \
                patch("experiments.reader_surfaces.common.sample_from_book", wraps=sample_from_book) as sample, \
                patch("experiments.reader_surfaces.trials.select_trial") as select:
            status, out, err = self.invoke("inventory")
        self.assertEqual((status, err), (0, ""))
        sample.assert_called_once_with(book, None, 24)
        select.assert_not_called()
        inventory = json.loads(out)
        self.assertEqual(inventory["sample_passages"], 24)
        self.assertEqual(inventory["start"], book.passages[0].identifier)
        self.assertIsNone(inventory["workspace"])
        self.assertNotIn("trial", inventory)
        self.assertNotIn("text", inventory)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_nontrial_explicit_count_and_start_are_unchanged(self):
        book, named = trial_book(opening_counts=(10, 10, 10))
        start = named["b-0"]["id"]
        with patch("sol.core.corpus.load_corpus_book", return_value=book), \
                patch("experiments.reader_surfaces.common.sample_from_book", wraps=sample_from_book) as sample:
            status, out, err = self.invoke("--start", start, "--count", "5", "inventory")
        self.assertEqual((status, err), (0, ""))
        sample.assert_called_once_with(book, start, 5)
        inventory = json.loads(out)
        self.assertEqual((inventory["start"], inventory["sample_passages"]), (start, 5))
        self.assertNotIn("trial", inventory)

    def test_named_inventory_uses_derived_source_extent_not_the_default_count(self):
        book, _ = trial_book(opening_counts=(2, 3, 2))
        before = deepcopy(book.canonical_records)
        for preset in ("opening", "beginning"):
            with self.subTest(preset=preset):
                expected = select_trial(book, preset)
                with patch("sol.core.corpus.load_corpus_book", return_value=book) as load:
                    status, out, err = self.invoke("--trial", preset, "inventory")
                self.assertEqual((status, err), (0, ""))
                load.assert_called_once_with(self.corpus)
                inventory = json.loads(out)
                self.assertEqual(inventory["sample_passages"], len(expected.sample.passages))
                self.assertEqual(inventory["start"], expected.sample.passages[0].identifier)
                self.assertEqual(inventory["trial"], expected.metadata)
                self.assertIsNone(inventory["workspace"])
                self.assertNotIn("text", inventory)
                for passage in book.passages:
                    self.assertNotIn(passage.text, out)
        self.assertEqual(book.canonical_records, before)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_named_views_receive_one_same_source_bound_sample_with_whole_work_scope(self):
        book, _ = trial_book(opening_counts=(2, 3, 2))
        before = deepcopy(book.canonical_records)
        for preset in ("opening", "beginning"):
            for mode in ("baseline", "tui", "html"):
                with self.subTest(preset=preset, mode=mode), ExitStack() as stack:
                    trial = select_trial(book, preset)
                    stack.enter_context(patch("sol.core.corpus.load_corpus_book", return_value=book))
                    select = stack.enter_context(patch("experiments.reader_surfaces.trials.select_trial", return_value=trial))
                    default_sample = stack.enter_context(patch("experiments.reader_surfaces.common.sample_from_book"))
                    environment = stack.enter_context(patch("sol.terminal.reader.validate_reader_environment"))
                    baseline = stack.enter_context(patch("sol.terminal.reader.ReaderView"))
                    baseline.return_value.run.return_value = 0
                    tui = stack.enter_context(patch("experiments.reader_surfaces.tui.run", return_value=0))
                    html = stack.enter_context(patch("experiments.reader_surfaces.html.write_html"))
                    output = self.root / f"{preset}.html"
                    arguments = ((mode, "--output", str(output)) if mode == "html"
                                 else (mode, "--width", "61"))
                    status, out, err = self.invoke("--trial", preset, *arguments)
                    self.assertEqual((status, err), (0, ""))
                    select.assert_called_once_with(book, preset)
                    default_sample.assert_not_called()
                    if mode == "baseline":
                        environment.assert_called_once_with()
                        baseline.assert_called_once_with(trial.sample.actions, width=61)
                        baseline.return_value.run.assert_called_once_with()
                        tui.assert_not_called()
                        html.assert_not_called()
                        self.assertFalse(out)
                    elif mode == "tui":
                        environment.assert_called_once_with()
                        tui.assert_called_once_with(trial.sample, width=61)
                        baseline.assert_not_called()
                        html.assert_not_called()
                        self.assertFalse(out)
                    else:
                        environment.assert_not_called()
                        html.assert_called_once_with(trial.sample, output, trial=trial)
                        baseline.assert_not_called()
                        tui.assert_not_called()
                        self.assertIn("Created private offline experiment", out)
                    state = trial.sample.actions.snapshot()
                    self.assertEqual(state.scope, ())
                    self.assertIs(state.current, trial.sample.passages[0])
                    self.assertIsNone(trial.sample.actions.workspace_reader)
        self.assertEqual(book.canonical_records, before)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unsupported_hierarchy_never_falls_back_opens_a_view_or_creates_output(self):
        for mode in ("inventory", "baseline", "tui", "html"):
            with self.subTest(mode=mode), ExitStack() as stack:
                book, named = trial_book()
                del book.canonical_records[named["b"]["id"]]
                before = deepcopy(book.canonical_records)
                stack.enter_context(patch("sol.core.corpus.load_corpus_book", return_value=book))
                stack.enter_context(patch("sol.terminal.reader.validate_reader_environment"))
                baseline = stack.enter_context(patch("sol.terminal.reader.ReaderView"))
                tui = stack.enter_context(patch("experiments.reader_surfaces.tui.run"))
                html = stack.enter_context(patch("experiments.reader_surfaces.html.write_html"))
                fallback = stack.enter_context(patch("experiments.reader_surfaces.common.sample_from_book"))
                output = self.root / "must-not-exist.html"
                arguments = (mode, "--output", str(output)) if mode == "html" else (mode,)
                status, out, err = self.invoke("--trial", "beginning", *arguments)
                self.assertEqual(status, 2)
                self.assertFalse(out)
                self.assertIn("reader experiment:", err)
                self.assertIn("Nothing", err)
                for operation in (baseline, tui, html, fallback):
                    operation.assert_not_called()
                self.assertFalse(output.exists())
                self.assertEqual(book.canonical_records, before)
        self.assertEqual(list(self.root.iterdir()), [])
