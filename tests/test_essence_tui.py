"""ESSENCE's Textual shell: screens, leaving, saved state and the context file."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.essence import tui
from sol.essence.tui import words as tui_words
from sol.essence.tui import __main__ as entry
from sol.essence.tui.context import check_context, read_context, write_context

TARGET = "bbbbbbbb-0000-4000-8000-000000000002"


def context(state_file=None):
    return {"version": 1, "reference": {"reference": {"target_id": TARGET}}, "cursor_offset": 3,
            "selection": None, "label": "Invented section | p. 7", "corpus": "/invented",
            "state_file": None if state_file is None else str(state_file)}


class ContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_written_context_is_private_and_round_trips(self):
        fields = {key: value for key, value in context().items() if key != "version"}
        path = write_context(self.root, **fields)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(read_context(path), context())
        self.assertNotEqual(write_context(self.root, **fields), path)  # Never overwrites.

    def test_malformed_contexts_are_refused(self):
        for change in ({"version": 2}, {"cursor_offset": -1}, {"cursor_offset": True}, {"reference": {}},
                       {"selection": "text"}, {"label": None}, {"extra": 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                check_context({**context(), **change})

    def test_importing_the_package_does_not_import_textual(self):
        code = "import sys; import sol.essence.tui, sol.essence.tui.context; print('textual' in sys.modules)"
        import subprocess
        import sys
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "False")

    def test_missing_textual_is_explained_not_a_traceback(self):
        path = self.root / "context.json"
        path.write_text(json.dumps(context()), encoding="utf-8")
        with patch.object(entry, "textual_available", return_value=False), \
                patch("sys.stderr") as stderr:
            self.assertEqual(entry.main(["--context", str(path)]), 2)
        self.assertIn("essence", "".join(call.args[0] for call in stderr.write.call_args_list))
        self.assertIn("pipx inject", tui.TEXTUAL_HINT)


@unittest.skipUnless(tui.textual_available(), "the essence extra (Textual) is not installed")
class EssenceAppTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-")
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name) / "state" / "investigation.json"

    async def test_screens_switch_and_leaving_saves_only_the_open_screen(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context(self.state))
        async with app.run_test(size=(60, 24)) as pilot:
            origin = str(app.query_one("#origin").render())
            self.assertIn("Invented section | p. 7", origin)
            self.assertIn(TARGET[:8], origin)
            for key, screen in (("3", "experiment"), ("1", "encyclopedia"), ("4", "results")):
                await pilot.press(key)
                self.assertEqual(app.query_one("#screens").active, screen)
            await pilot.press("q")
        self.assertEqual(json.loads(self.state.read_text()),
                         {"version": 1, "screen": "results", "origin": TARGET})
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        # The next opening returns to the same screen, at any size.
        app = EssenceApp(context(self.state))
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            self.assertEqual(app.query_one("#screens").active, "results")
            await pilot.press("ctrl+q")
        self.assertFalse(app.is_running)

    async def test_temporary_sessions_save_nothing_and_unreadable_state_is_ignored(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test() as pilot:
            await pilot.press("2", "q")
        self.assertFalse(self.state.exists())
        self.state.parent.mkdir(parents=True)
        self.state.write_text("not json", encoding="utf-8")
        app = EssenceApp(context(self.state))
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(app.query_one("#screens").active, "encyclopedia")
            await pilot.press("q")

    async def test_the_command_palette_is_off(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test() as pilot:
            await pilot.press("ctrl+p")
            self.assertEqual(len(app.screen_stack), 1)
            await pilot.press("q")


if __name__ == "__main__":
    unittest.main()


class FakeInputs:
    """The stage 2 engine's provider classes, as the interface uses them."""

    class CoreProvider:
        def __init__(self, snapshot, scope=None):
            self.snapshot, self.scope = snapshot, scope

    class FileProvider:
        def __init__(self, path, scope=None):
            self.path, self.scope = path, scope


class FakeWords:
    calls = []

    @classmethod
    def analyze_words(cls, target, *, reference=None):
        cls.calls.append((target, reference))
        def side(count):
            return {"provider": "core", "scope": {"kind": "corpus"},
                    "summary": {"token_count": count, "type_count": 2, "input_count": 1}}
        cell = lambda count, total: {"count": count, "denominator": total, "locations": [],
                                     "rate_per_10000_tokens": round(count * 10000 / total, 6) if total else None}
        return {"protocol": "sol.word-frequencies", "version": 1, "target": side(30),
                "reference": side(0) if reference is not None else None,
                "frequencies": [{"word": "being", "target": cell(20, 30), "reference": cell(0, 0) if reference else None},
                                {"word": "nothing", "target": cell(10, 30), "reference": cell(0, 0) if reference else None}],
                "warnings": ["The reference has zero tokens; its rates are undefined (null)."] if reference else []}

    @staticmethod
    def encode_word_result(result):
        return json.dumps(result, sort_keys=True)


class WordChoiceTests(unittest.TestCase):
    def setUp(self):
        FakeWords.calls.clear()
        patcher = patch.object(tui_words, "engine", return_value=(FakeWords, FakeInputs))
        patcher.start()
        self.addCleanup(patcher.stop)
        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-words-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def book(self):
        class Passage:
            path = ("BEING", "quality", "1-being.txt")
        class Book:
            corpus_snapshot = object()
            def find_passage(self, identifier):
                assert identifier == TARGET
                return Passage()
        return Book()

    def test_choices_become_the_engine_scopes(self):
        book = self.book()
        cases = {("passage", "none"): ({"kind": "passages", "ids": [TARGET]}, None),
                 ("section", "book"): ({"kind": "within", "path": "/BEING/quality"}, "book"),
                 ("book", "section"): (None, "section")}
        for (target, reference), (scope, other) in cases.items():
            with self.subTest(target=target, reference=reference):
                tui_words.run(context(), target, reference, loader=lambda directory: book)
                chosen, compared = FakeWords.calls[-1]
                self.assertIs(chosen.snapshot, book.corpus_snapshot)
                self.assertEqual(chosen.scope, scope)
                self.assertEqual(None if compared is None else ("book" if compared.scope is None else "section"), other)

    def test_files_need_no_corpus_and_must_be_named(self):
        text = self.root / "invented.txt"
        text.write_text("Being and nothing.", encoding="utf-8")
        no_corpus = {**context(), "corpus": ""}
        tui_words.run(no_corpus, "file", "none", target_file=str(text))
        self.assertEqual(FakeWords.calls[-1][0].path, text)
        with self.assertRaisesRegex(ValueError, "Name a UTF-8 text file"):
            tui_words.run(no_corpus, "file", "none", target_file="  ")
        with self.assertRaisesRegex(ValueError, "no CORE corpus"):
            tui_words.run(no_corpus, "book", "none")

    def test_rows_summary_and_owner_only_saving(self):
        result = FakeWords.analyze_words(object(), reference=object())
        shown, total = tui_words.rows(result)
        self.assertEqual(shown[0], ("being", "20", "6666.67", "0", "undefined"))
        self.assertEqual(total, 2)
        lines = tui_words.summary(result)
        self.assertTrue(lines[0].startswith("Target: 30 tokens, 2 distinct words"))
        self.assertIn("undefined", lines[-1])
        first = tui_words.save(result, data_home=self.root)
        second = tui_words.save(result, data_home=self.root)
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, self.root / "sol" / "studies")
        self.assertEqual(first.stat().st_mode & 0o777, 0o600)

    def test_a_missing_engine_is_explained(self):
        with patch.object(tui_words, "engine", side_effect=tui_words.EngineMissing("engine not installed")):
            with self.assertRaises(tui_words.EngineMissing):
                tui_words.run(context(), "passage", "none")


@unittest.skipUnless(tui.textual_available(), "the essence extra (Textual) is not installed")
class WordScreenTests(unittest.IsolatedAsyncioTestCase):
    async def test_count_fills_results_and_failures_stay_on_the_experiment_screen(self):
        from sol.essence.tui.app import EssenceApp

        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-screen-")
        self.addCleanup(temporary.cleanup)
        text = Path(temporary.name) / "invented.txt"
        text.write_text("Being and nothing.", encoding="utf-8")
        with patch.object(tui_words, "engine", return_value=(FakeWords, FakeInputs)):
            app = EssenceApp({**context(), "corpus": ""})
            async with app.run_test(size=(100, 40)) as pilot:
                await pilot.press("3")
                app.query_one("#target-file").value = str(text)
                for button in app.query("#target RadioButton"):
                    button.value = button.name == "file"
                await pilot.click("#run")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(app.query_one("#screens").active, "results")
                table = app.query_one("#frequencies")
                self.assertEqual(table.row_count, 2)
                self.assertIn("Not saved", str(app.query_one("#summary").render()))
                # A count that cannot run says why and keeps the previous results.
                await pilot.press("3")
                app.query_one("#target-file").value = ""
                await pilot.click("#run")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(app.query_one("#screens").active, "experiment")
                self.assertIn("Name a UTF-8 text file", str(app.query_one("#status").render()))
                self.assertEqual(table.row_count, 2)
                app.exit()


def _engine_installed():
    from importlib.util import find_spec
    return find_spec("sol.essence.words") is not None


@unittest.skipUnless(_engine_installed(), "the ESSENCE stage 2 engine is not merged yet")
class RealEngineTests(unittest.TestCase):
    """Runs once Codex's engine lands: the interface's choices against the real thing."""

    def test_interface_choices_run_on_the_real_engine(self):
        from fixtures_corpus import write_runtime_corpus
        from sol import core
        from sol.corpus import contract

        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-real-")
        self.addCleanup(temporary.cleanup)
        corpus = Path(temporary.name) / "corpus"
        identifier, _ = write_runtime_corpus(corpus)
        contract.initialize_corpus_identity(corpus)
        snapshot = core.load_snapshot(corpus)
        real = {**context(), "corpus": str(corpus),
                "reference": core.capture_reference(snapshot, identifier)}
        for target, reference in (("passage", "none"), ("section", "book"), ("book", "none")):
            with self.subTest(target=target, reference=reference):
                result = tui_words.run(real, target, reference)
                self.assertEqual(result["protocol"], "sol.word-frequencies")
                self.assertGreater(result["target"]["summary"]["token_count"], 0)
                self.assertEqual(result["reference"] is None, reference == "none")
                shown, total = tui_words.rows(result)
                self.assertEqual(len(shown), total)
