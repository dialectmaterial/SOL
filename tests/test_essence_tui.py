"""ESSENCE's Textual shell: screens, leaving, saved state and the context file."""
from __future__ import annotations

import asyncio
import base64
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


class FakeComparison:
    """The stage 3 engine's two functions, over FakeWords' study."""

    exports = []

    @staticmethod
    def compare_words(target, *, reference, result=None):
        study = FakeWords.analyze_words(target, reference=reference) if result is None else result
        rows = [{**row, "rate_difference_per_10000_tokens": None, "rate_difference_status": "empty_reference",
                 "log2_rate_ratio": None, "log2_ratio_status": "empty_reference"} for row in study["frequencies"]]
        return {"method": {}, "study": study, "study_sha256": "0" * 64, "rows": rows,
                "warnings": [*study["warnings"], "Descriptive only."]}

    @classmethod
    def export_word_comparison(cls, target, *, reference, result=None, format="csv"):
        cls.exports.append((target, reference, result, format))
        separator = "," if format == "csv" else "\t"
        return f"word{separator}target_count\n" + "".join(
            f"{row['word']}{separator}{row['target']['count']}\n" for row in result["frequencies"])


def fake_engines(test):
    """Patch both engine lookups for one test."""
    for name, value in (("engine", (FakeWords, FakeInputs)), ("comparison_engine", FakeComparison)):
        patcher = patch.object(tui_words, name, return_value=value)
        patcher.start()
        test.addCleanup(patcher.stop)


class WordChoiceTests(unittest.TestCase):
    def setUp(self):
        FakeWords.calls.clear()
        fake_engines(self)
        # These tests cover choices, not the reference check, which has its own test.
        checker = patch("sol.core.check_reference", return_value=None)
        checker.start()
        self.addCleanup(checker.stop)
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
        alone = tui_words.Count(FakeWords.analyze_words(object()), None, object(), None)
        self.assertEqual(tui_words.rows(alone)[0][0], ("being", "20", "6666.67", "", ""))
        self.assertNotIn(tui_words.METHOD_LINE, tui_words.summary(alone))
        result = tui_words.run(context(), "passage", "book", loader=lambda directory: self.book())
        shown, total = tui_words.rows(result)
        # Undefined measures say why, in the engine's terms.
        self.assertEqual(shown[0], ("being", "20", "6666.67", "0", "undefined", "empty reference", "empty reference"))
        self.assertEqual(total, 2)
        lines = tui_words.summary(result)
        self.assertTrue(lines[0].startswith("Target: 30 tokens, 2 distinct words"))
        self.assertIn(tui_words.METHOD_LINE, lines)
        self.assertEqual(lines[-1], "Note: Descriptive only.")
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
                count = tui_words.run(real, target, reference)
                result = count.study
                self.assertEqual(result["protocol"], "sol.word-frequencies")
                self.assertEqual(count.comparison is None, reference == "none")
                self.assertGreater(result["target"]["summary"]["token_count"], 0)
                self.assertEqual(result["reference"] is None, reference == "none")
                shown, total = tui_words.rows(count)
                self.assertEqual(len(shown), total)


@unittest.skipUnless(_engine_installed(), "the ESSENCE stage 2 engine is not merged yet")
class StaleContextTests(unittest.TestCase):
    def test_a_corpus_changed_since_the_reader_opened_is_refused(self):
        # Reported by Codex's review of PR #25.
        from fixtures_corpus import write_runtime_corpus
        from sol import core
        from sol.corpus import contract

        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-stale-")
        self.addCleanup(temporary.cleanup)
        corpus = Path(temporary.name) / "corpus"
        identifier, _ = write_runtime_corpus(corpus)
        contract.initialize_corpus_identity(corpus)
        reference = core.capture_reference(core.load_snapshot(corpus), identifier)
        source = corpus / "sample.md"
        # The same passage, now with different words: its ID is unchanged.
        source.write_text(source.read_text(encoding="utf-8").replace("An invented passage", "A replaced text", 1),
                          encoding="utf-8")
        contract.reindex(corpus)
        stale = {**context(), "corpus": str(corpus), "reference": reference}
        for target in ("passage", "section", "book"):
            with self.subTest(target=target), self.assertRaises(core.ProtocolError) as caught:
                tui_words.run(stale, target, "none")
            self.assertEqual(caught.exception.code, "generation_changed")


@unittest.skipUnless(tui.textual_available(), "the essence extra (Textual) is not installed")
class CountOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_an_older_count_never_replaces_a_newer_one(self):
        # Reported by Codex's review of PR #25: delayed A, fast B.
        import threading
        from sol.essence.tui.app import EssenceApp

        release = threading.Event()
        def run(context, target, reference, **files):
            if files["target_file"] == "a":
                release.wait(5)
                return {"label": "a"}
            return {"label": "b"}
        shown, saved = [], []
        with patch.object(tui_words, "run", side_effect=run), \
                patch.object(tui_words, "save", side_effect=lambda result: saved.append(result) or None), \
                patch.object(EssenceApp, "show_result", lambda self, result, path: shown.append(result["label"])):
            app = EssenceApp(context(Path(tempfile.mkdtemp(prefix="sol-essence-order-")) / "state.json"))
            async with app.run_test() as pilot:
                await pilot.press("3")
                field = app.query_one("#target-file")
                field.value = "a"
                await pilot.click("#run")
                await pilot.pause(0.4)  # A button ignores presses while it shows the last one.
                field.value = "b"
                await pilot.click("#run")
                await pilot.pause(0.2)
                release.set()
                await pilot.pause(0.3)
                self.assertEqual(shown, ["b"])
                self.assertEqual([result["label"] for result in saved], ["b"])
                # A count still running when ESSENCE is left publishes nothing.
                release.clear()
                field.value = "a"
                await pilot.pause(0.4)
                await pilot.click("#run")
                await pilot.press("q")
            release.set()
            await asyncio.sleep(0.3)
            self.assertEqual(shown, ["b"])
            self.assertEqual(len(saved), 1)


def comparison_count():
    """A target from the corpus and a reference from a text file, as the engine shapes them."""
    digest = "c" * 64
    core_side = {"provider": "core", "scope": {"kind": "corpus"},
                 "summary": {"token_count": 30, "type_count": 2, "input_count": 1},
                 "inputs": [{"id": TARGET, "content_sha256": digest, "reader_path": "/BEING/quality",
                             "sources": [{"printed_page": "7"}]}]}
    file_side = {"provider": "file", "scope": {"kind": "file"},
                 "summary": {"token_count": 10, "type_count": 1, "input_count": 1}, "inputs": [{"span": [0, 40]}]}
    cell = lambda count, total, locations: {"count": count, "denominator": total, "locations": locations,
                                            "rate_per_10000_tokens": round(count * 10000 / total, 6)}
    study = {"target": core_side, "reference": file_side, "warnings": [],
             "frequencies": [{"word": "being", "target": cell(20, 30, [[0, 20, 4, 9]]),
                              "reference": cell(5, 10, [[0, 5, 12, 17]])}]}
    rows = [{**study["frequencies"][0], "rate_difference_per_10000_tokens": 1666.666667,
             "rate_difference_status": "defined", "log2_rate_ratio": 0.415037, "log2_ratio_status": "defined"}]
    comparison = {"study": study, "rows": rows, "warnings": ["Descriptive only."]}
    return tui_words.Count(study, comparison, object(), object()), digest


@unittest.skipUnless(tui.textual_available(), "the essence extra (Textual) is not installed")
class ComparisonScreenTests(unittest.IsolatedAsyncioTestCase):
    async def counted(self, app, pilot):
        await pilot.press("3")
        await pilot.click("#run")
        await app.workers.wait_for_complete()
        await pilot.pause()

    async def test_measures_sources_and_opening_one_in_the_reader(self):
        from sol.essence.tui.app import EssenceApp

        count, digest = comparison_count()
        written = []
        with patch.object(tui_words, "run", return_value=count), patch.object(tui_words, "save", return_value=None):
            app = EssenceApp(context())
            async with app.run_test(size=(120, 40)) as pilot:
                original = app._driver.write
                app._driver.write = lambda data: (written.append(data), original(data))[1]
                await self.counted(app, pilot)
                table = app.query_one("#frequencies")
                self.assertEqual([str(column.label) for column in table.columns.values()][-2:],
                                 ["Difference", "Log₂ ratio"])
                self.assertEqual(table.get_row_at(0)[-2:], ["+1666.67", "+0.42"])
                self.assertIn(tui_words.METHOD_LINE, str(app.query_one("#summary").render()))
                sources = app.query_one("#sources")
                self.assertEqual(sources.row_count, 2)
                # The keyboard path: words are focused after a count, Enter
                # goes to the word's sources, Enter there opens one.
                self.assertIs(app.focused, table)
                await pilot.press("enter")
                await pilot.pause()
                self.assertIs(app.focused, sources)
                await pilot.press("enter")
                await pilot.pause()
                requests = [data for data in written if data.startswith("\x1b]5379;sol-essence;")]
                self.assertEqual(len(requests), 1)
                self.assertTrue(requests[0].endswith("\x07"))
                encoded = requests[0][len("\x1b]5379;sol-essence;"):-1]
                self.assertEqual(json.loads(base64.b64decode(encoded)),
                                 {"version": 1, "op": "open_source",
                                  "source": {"id": TARGET, "start": 4, "content_sha256": digest}})
                # The text file's occurrence is listed but cannot open in the reader.
                await pilot.press("down", "enter")
                await pilot.pause()
                self.assertEqual(len([data for data in written if data.startswith("\x1b]5379;")]), 1)
                self.assertIn("cannot be opened", str(app.query_one("#result-status").render()))
                await pilot.press("escape")
                await pilot.pause()
                self.assertIs(app.focused, table)
                # Switching screens starts on that screen's first control.
                await pilot.press("3")
                self.assertEqual(app.focused.id, "target")
                await pilot.press("4")
                self.assertIs(app.focused, table)
                app.exit()

    async def test_export_writes_only_in_workspace_sessions(self):
        from sol.essence.tui.app import EssenceApp

        count, _ = comparison_count()
        exported = []
        def export(chosen, table_format):
            exported.append((chosen, table_format))
            return Path("/invented/words.tsv")
        for state_file in (None, Path(tempfile.mkdtemp(prefix="sol-essence-export-")) / "state.json"):
            exported.clear()
            with self.subTest(workspace=state_file is not None), patch.object(tui_words, "run", return_value=count), \
                    patch.object(tui_words, "save", return_value=None), patch.object(tui_words, "export", side_effect=export):
                app = EssenceApp(context(state_file))
                async with app.run_test(size=(120, 40)) as pilot:
                    await self.counted(app, pilot)
                    await pilot.click("#export-tsv")
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    status = str(app.query_one("#result-status").render())
                    if state_file is None:
                        self.assertEqual(exported, [])
                        self.assertIn("Not exported", status)
                    else:
                        self.assertEqual(exported, [(count, "tsv")])
                        self.assertIn("Exported: /invented/words.tsv", status)
                    app.exit()

    async def test_without_a_reference_there_is_nothing_to_export(self):
        from sol.essence.tui.app import EssenceApp

        study = FakeWords.analyze_words(object())
        with patch.object(tui_words, "run", return_value=tui_words.Count(study, None, object(), None)), \
                patch.object(tui_words, "save", return_value=None):
            app = EssenceApp(context())
            async with app.run_test(size=(120, 40)) as pilot:
                await self.counted(app, pilot)
                self.assertTrue(app.query_one("#export-csv").disabled)
                self.assertEqual(len(app.query_one("#frequencies").columns), 5)
                app.exit()

    async def test_a_cancelled_count_shows_and_saves_nothing(self):
        import threading
        from sol.essence.tui.app import EssenceApp

        release, shown, saved = threading.Event(), [], []
        def run(*arguments, **files):
            release.wait(5)
            return comparison_count()[0]
        with patch.object(tui_words, "run", side_effect=run), \
                patch.object(tui_words, "save", side_effect=lambda count: saved.append(count)), \
                patch.object(EssenceApp, "show_result", lambda self, count, path: shown.append(count)):
            app = EssenceApp(context(Path(tempfile.mkdtemp(prefix="sol-essence-cancel-")) / "state.json"))
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.press("3")
                await pilot.click("#run")
                await pilot.pause(0.2)
                self.assertFalse(app.query_one("#cancel").disabled)
                await pilot.click("#cancel")
                await pilot.pause()
                release.set()
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual((shown, saved), ([], []))
                self.assertIn("Cancelled", str(app.query_one("#status").render()))
                self.assertTrue(app.query_one("#cancel").disabled)
                app.exit()

    async def test_ctrl_q_leaves_and_saves_even_from_a_text_field(self):
        # Quitting the reader sends Ctrl-Q; a focused input must not swallow it.
        from sol.essence.tui.app import EssenceApp

        state_file = Path(tempfile.mkdtemp(prefix="sol-essence-quit-")) / "state.json"
        app = EssenceApp(context(state_file))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("3")
            app.query_one("#target-file").focus()
            await pilot.press("ctrl+q")
            await pilot.pause()
        self.assertEqual(json.loads(state_file.read_text())["screen"], "experiment")


@unittest.skipUnless(_engine_installed(), "the ESSENCE stage 2 engine is not merged yet")
class RealComparisonTests(unittest.TestCase):
    def test_sources_and_export_from_the_real_engines(self):
        from fixtures_corpus import write_runtime_corpus
        from sol import core
        from sol.corpus import contract

        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-compare-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        corpus = root / "corpus"
        identifier, _ = write_runtime_corpus(corpus)
        contract.initialize_corpus_identity(corpus)
        snapshot = core.load_snapshot(corpus)
        reference_file = root / "reference.txt"
        reference_file.write_text("An invented reference, with an invented word or two.", encoding="utf-8")
        real = {**context(), "corpus": str(corpus), "reference": core.capture_reference(snapshot, identifier)}
        count = tui_words.run(real, "passage", "file", reference_file=str(reference_file))
        self.assertIsNotNone(count.comparison)
        index = next(number for number, row in enumerate(count.study["frequencies"]) if row["word"] == "invented")
        found = tui_words.sources(count, index)
        corpus_sources = [item for item in found if item["side"] == "target"]
        self.assertEqual([item["open"]["id"] for item in corpus_sources], [identifier])
        text = next(p for p in core.load_corpus_book(corpus).passages if p.identifier == identifier).text
        start = corpus_sources[0]["open"]["start"]
        self.assertEqual(text[start:start + len("invented")].casefold(), "invented")
        self.assertEqual([item["open"] for item in found if item["side"] == "reference"], [None])
        data_home = root / "data"
        exported = tui_words.export(count, "csv", data_home=data_home)
        self.assertEqual(exported.suffix, ".csv")
        self.assertEqual(exported.stat().st_mode & 0o777, 0o600)
        self.assertTrue(exported.read_text(encoding="utf-8").startswith("word,"))
        self.assertNotEqual(tui_words.export(count, "csv", data_home=data_home), exported)
        # A source changed since the count is refused, not exported.
        reference_file.write_text("Something else entirely.", encoding="utf-8")
        from sol.essence.word_inputs import WordStudyError
        with self.assertRaises(WordStudyError) as caught:
            tui_words.export(count, "tsv", data_home=data_home)
        self.assertEqual(caught.exception.status, "stale")
        self.assertEqual(len(list((data_home / "sol" / "studies").iterdir())), 2)
        alone = tui_words.run(real, "passage", "none")
        with self.assertRaisesRegex(ValueError, "Export needs a reference"):
            tui_words.export(alone, "csv", data_home=data_home)
