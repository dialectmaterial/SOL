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

from fixtures_async import UIEventLoop

from sol.interchange import essence as essence_launch
from sol.essence.tui import words as tui_words
from sol.essence.tui import __main__ as entry
from sol.interchange.essence import check_context, read_context, write_context

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
        code = "import sys; import sol.essence.tui, sol.interchange.essence; print('textual' in sys.modules)"
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
        self.assertIn("pipx inject", essence_launch.TEXTUAL_HINT)


@unittest.skipUnless(essence_launch.textual_available(), "the essence extra (Textual) is not installed")
class EssenceAppTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-")
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name) / "state" / "investigation.json"

    async def test_views_switch_and_leaving_saves_only_the_open_view(self):
        from textual.widgets import TabbedContent
        from sol.essence.tui.app import EssenceApp
        from sol.essence.tui.reference import ReferenceScreen

        app = EssenceApp(context(self.state))
        async with app.run_test(size=(60, 24)) as pilot:
            self.assertIn("Invented section | p. 7", str(app.query_one("#header").render()))
            # The study menu is home until a study has run.
            self.assertIs(app.focused, app.query_one("#menu"))
            await pilot.press("M")
            self.assertIsInstance(app.screen, ReferenceScreen)
            self.assertEqual(app.screen.query_one("#catalogs", TabbedContent).active, "encyclopedia")
            await pilot.press("2")
            self.assertEqual(app.screen.query_one("#catalogs", TabbedContent).active, "methods")
            await pilot.press("q")
        self.assertEqual(json.loads(self.state.read_text()),
                         {"version": 1, "screen": "methods", "origin": TARGET})
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        # The next opening returns to the same view, at any size.
        app = EssenceApp(context(self.state))
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            self.assertIsInstance(app.screen, ReferenceScreen)
            self.assertEqual(app.screen.query_one("#catalogs", TabbedContent).active, "methods")
            await pilot.press("escape")
            self.assertNotIsInstance(app.screen, ReferenceScreen)
            await pilot.press("ctrl+q")
        self.assertFalse(app.is_running)
        self.assertEqual(json.loads(self.state.read_text())["screen"], "workspace")
        # A state from the former four screens opens the workspace.
        self.state.write_text(json.dumps({"version": 1, "screen": "results", "origin": TARGET}))
        app = EssenceApp(context(self.state))
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertNotIsInstance(app.screen, ReferenceScreen)
            await pilot.press("q")

    async def test_temporary_sessions_save_nothing_and_unreadable_state_is_ignored(self):
        from sol.essence.tui.app import EssenceApp
        from sol.essence.tui.reference import ReferenceScreen

        app = EssenceApp(context())
        async with app.run_test() as pilot:
            await pilot.press("M", "q")
        self.assertFalse(self.state.exists())
        self.state.parent.mkdir(parents=True)
        self.state.write_text("not json", encoding="utf-8")
        app = EssenceApp(context(self.state))
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertNotIsInstance(app.screen, ReferenceScreen)
            self.assertIs(app.focused, app.query_one("#menu"))
            await pilot.press("q")

    async def test_the_opening_shows_the_chosen_studys_method_and_names_m(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test(size=(86, 48)) as pilot:
            await pilot.pause()
            primer = app.query_one("#primer-method")
            self.assertTrue(app.query_one("#primer").display)
            self.assertIn("Word frequencies", primer.source)
            footer = " ".join(active.binding.description for active in app.screen.active_bindings.values()
                              if active.binding.show)
            self.assertIn("Encyclopedia", footer)
            # Choosing another study before any run updates the header and the method shown.
            await pilot.press("s")
            await pilot.pause()
            self.assertIn("sentences", str(app.query_one("#header").render()))
            self.assertNotIn("words", str(app.query_one("#header").render()).split("   ")[0])
            self.assertIn("Sentence", primer.source)
            await pilot.press("w", "B")
            await pilot.pause()
            self.assertIn("comparison", primer.source.lower())
            # The reference frame names its catalog; the entry's heading names the entry.
            await pilot.press("M")
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#encyclopedia-detail").border_title, "Encyclopedia")
            await pilot.press("q")

    async def test_keys_typed_in_a_burst_reach_the_menu_r_just_opened(self):
        from textual import events
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invented.txt"
            path.write_text("Being is nothing. Nothing is being.", encoding="utf-8")
            count = words.run(context(), "file", "none", target_file=path)
        app = EssenceApp(context())
        async with app.run_test(size=(86, 48)) as pilot:
            app.last_run = ("words", "file", "none", str(path), "", 20)
            app.show_result(count, None)
            await pilot.pause()
            # The reader's terminal delivers `r s c` at once, before any refresh.
            for key in ("r", "s", "c"):
                app.post_message(events.Key(key, key))
            await pilot.pause()
            menu = app.query_one("#menu")
            self.assertIs(app.focused, menu)
            self.assertEqual((menu.study, menu.target), ("sentences", "section"))
            await pilot.press("q")

    async def test_methods_screen_browses_every_method(self):
        from textual.widgets import Markdown, OptionList
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("M", "2")
            screen = app.screen
            listing = screen.query_one("#methods-list", OptionList)
            self.assertIs(app.focused, listing)
            methods = app.methods["entries"]
            self.assertEqual(listing.option_count, len(methods))
            titles = {entry["id"]: entry["title"] for entry in app.catalog["entries"]}
            for number, method in enumerate(methods):
                await pilot.pause()
                shown = screen.query_one("#methods-entry", Markdown).source
                self.assertIn(method["title"], shown)
                self.assertIn(method["cli"], shown)
                if method["encyclopedia"] is not None:
                    # The encyclopedia entry by its title, not its ID.
                    self.assertIn(titles[method["encyclopedia"]], shown)
                if number < len(methods) - 1:
                    await pilot.press("down")
            await pilot.press("enter")
            self.assertIs(app.focused, screen.query_one("#methods-detail"))
            await pilot.press("escape")
            self.assertIs(app.focused, listing)
            await pilot.press("q")

    async def test_k_opens_the_current_study_method(self):
        from textual.widgets import OptionList, TabbedContent
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("t", "K")
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#catalogs", TabbedContent).active, "methods")
            option = app.screen.query_one("#methods-list", OptionList).highlighted_option
            self.assertEqual(app.methods["entries"][int(option.id)]["id"], "tfidf")
            await pilot.press("q")

    async def test_the_command_palette_opens_with_a_colon_and_offers_only_essence(self):
        from textual.command import CommandPalette
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test() as pilot:
            await pilot.press("ctrl+p")
            self.assertEqual(len(app.screen_stack), 1)
            await pilot.press("colon")
            await pilot.pause()
            self.assertIsInstance(app.screen, CommandPalette)
            self.assertEqual(list(app.get_system_commands(app.screen)), [])
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(len(app.screen_stack), 1)
            await pilot.press("q")

    async def test_draws_with_the_readers_own_palette(self):
        from sol.essence.tui.app import EssenceApp, TEXTUAL_THEMES
        from sol.presentation.theme import reader_palette

        for name in ("mocha", "latte", "paper", "night"):
            with self.subTest(theme=name):
                app = EssenceApp(context(), theme=name)
                async with app.run_test() as pilot:
                    palette = reader_palette(name)
                    colors = app.theme_variables
                    self.assertEqual(app.theme, TEXTUAL_THEMES[name])
                    for variable, role in (("background", "page"), ("foreground", "text"),
                                           ("primary", "heading"), ("text-muted", "muted"),
                                           ("block-cursor-background", "selection"),
                                           ("border-blurred", "border"), ("footer-background", "page")):
                        self.assertEqual(colors[variable].lower(), palette[role], variable)
                    await pilot.press("q")

    async def test_buttons_selections_and_an_open_palette_stay_visible_in_every_preset(self):
        from textual.color import Color
        from textual.command import CommandList
        from textual.widgets import Button
        from sol.essence.tui.app import EssenceApp, TEXTUAL_THEMES
        from sol.presentation.theme import contrast

        def hex_of(color):
            return Color.parse(color).hex.lower()

        for name in ("mocha", "latte", "paper", "night"):
            with self.subTest(theme=name):
                app = EssenceApp(context(), theme=name)
                async with app.run_test(size=(120, 40)) as pilot:
                    colors = app.theme_variables
                    # A blurred selection differs from the page it sits on.
                    self.assertNotEqual(hex_of(colors["block-cursor-blurred-background"]),
                                        hex_of(colors["background"]))
                    await pilot.press("K")
                    await pilot.pause()
                    button = app.screen.query_one("#use-method", Button)
                    self.assertGreaterEqual(contrast(hex_of(button.styles.color.hex),
                                                     hex_of(button.styles.background.hex)), 4.5)
                    await pilot.press("escape")
                    await pilot.pause()
                    await pilot.press("colon")
                    await pilot.pause(0.3)
                    other = "latte" if name != "latte" else "mocha"
                    app.theme = TEXTUAL_THEMES[other]
                    await pilot.pause(0.3)
                    # The open palette takes the new theme too.
                    listing = app.screen.query_one(CommandList)
                    self.assertEqual(listing.styles.background.hex.lower(),
                                     hex_of(app.theme_variables["background"]))
                    await pilot.press("escape")
                    await pilot.press("q")

    async def test_follows_the_reader_theme_while_open(self):
        from sol.essence.tui.app import EssenceApp

        theme_file = Path(tempfile.mkdtemp(prefix="sol-essence-theme-")) / "context.theme"
        theme_file.write_text("mocha", encoding="utf-8")
        app = EssenceApp(context(), theme="mocha", theme_file=str(theme_file))
        async with app.run_test() as pilot:
            self.assertEqual(app.theme, "sol-mocha")
            theme_file.write_text("latte", encoding="utf-8")
            await pilot.pause(0.8)
            self.assertEqual(app.theme, "sol-latte")
            # Anything unknown, or a vanished file, leaves the theme as it is.
            for content in ("sepia", None):
                if content is None:
                    theme_file.unlink()
                else:
                    theme_file.write_text(content, encoding="utf-8")
                await pilot.pause(0.8)
                self.assertEqual(app.theme, "sol-latte")
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


@unittest.skipUnless(essence_launch.textual_available(), "the essence extra (Textual) is not installed")
class WordScreenTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_count_fills_results_and_failures_keep_the_menu_open(self):
        from sol.essence.tui.app import EssenceApp

        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-screen-")
        self.addCleanup(temporary.cleanup)
        text = Path(temporary.name) / "invented.txt"
        text.write_text("Being and nothing.", encoding="utf-8")
        with patch.object(tui_words, "engine", return_value=(FakeWords, FakeInputs)):
            app = EssenceApp({**context(), "corpus": ""})
            async with app.run_test(size=(100, 40)) as pilot:
                # f chooses a text file and moves to its path; Enter there runs.
                await pilot.press("f")
                self.assertIs(app.focused, app.query_one("#target-file"))
                app.query_one("#target-file").value = str(text)
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertFalse(app.query_one("#menu").display)
                table = app.query_one("#frequencies")
                self.assertEqual(table.row_count, 2)
                self.assertIs(app.focused, table)
                self.assertIn("Not saved", str(app.query_one("#summary").render()))
                # A count that cannot run says why and keeps the previous result.
                await pilot.press("r")
                app.query_one("#target-file").value = ""
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertTrue(app.query_one("#menu").display)
                self.assertIn("Name a UTF-8 text file", str(app.query_one("#status").render()))
                self.assertEqual(table.row_count, 2)
                # Escape puts the menu away and returns to the result.
                await pilot.press("escape")
                self.assertFalse(app.query_one("#menu").display)
                self.assertIs(app.focused, table)
                app.exit()


def _engine_installed():
    from importlib.util import find_spec
    return find_spec("sol.essence.essence_as_reflection_within_itself.words") is not None


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


@unittest.skipUnless(essence_launch.textual_available(), "the essence extra (Textual) is not installed")
class CountOrderTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
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
                await pilot.press("f")
                field = app.query_one("#target-file")
                field.value = "a"
                await pilot.press("enter")
                await pilot.pause(0.2)
                field.value = "b"
                await pilot.press("enter")
                await pilot.pause(0.2)
                release.set()
                await pilot.pause(0.3)
                self.assertEqual(shown, ["b"])
                self.assertEqual([result["label"] for result in saved], ["b"])
                # A count still running when ESSENCE is left publishes nothing.
                release.clear()
                field.value = "a"
                field.focus()
                await pilot.press("enter")
                await pilot.press("ctrl+q")
            release.set()
            await asyncio.sleep(0.3)
            self.assertEqual(shown, ["b"])
            self.assertEqual(len(saved), 1)


def comparison_count():
    """A target from the corpus and a reference from a text file, as the engine shapes them."""
    digest = "c" * 64
    core_side = {"provider": "core", "scope": {"kind": "corpus"},
                 "summary": {"token_count": 30, "type_count": 2, "input_count": 1},
                 "inputs": [{"id": TARGET, "content_sha256": digest, "text_sha256": digest,
                             "reader_path": "/BEING/quality", "sources": [{"printed_page": "7"}]}]}
    file_side = {"provider": "file", "scope": {"kind": "file"},
                 "summary": {"token_count": 10, "type_count": 1, "input_count": 1},
                 "inputs": [{"span": [0, 40], "text_sha256": digest}]}
    cell = lambda count, total, locations: {"count": count, "denominator": total, "locations": locations,
                                            "rate_per_10000_tokens": round(count * 10000 / total, 6)}
    study = {"target": core_side, "reference": file_side, "warnings": [],
             "frequencies": [{"word": "being", "target": cell(20, 30, [[0, 20, 4, 9]]),
                              "reference": cell(5, 10, [[0, 5, 12, 17]])}]}
    rows = [{**study["frequencies"][0], "rate_difference_per_10000_tokens": 1666.666667,
             "rate_difference_status": "defined", "log2_rate_ratio": 0.415037, "log2_ratio_status": "defined"}]
    comparison = {"study": study, "rows": rows, "warnings": ["Descriptive only."]}
    return tui_words.Count(study, comparison, object(), object()), digest


@unittest.skipUnless(essence_launch.textual_available(), "the essence extra (Textual) is not installed")
class ComparisonScreenTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def counted(self, app, pilot):
        # ESSENCE opens on the study menu; Enter runs the chosen study.
        app.query_one("#menu").focus()
        await pilot.press("enter")
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
                self.assertEqual(str(list(table.columns.values())[-1].label).strip(), "log₂ ratio")
                self.assertTrue(str(table.get_row_at(0)[-1]).endswith("+0.42"))
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
                await pilot.press("j", "enter")
                await pilot.pause()
                self.assertEqual(len([data for data in written if data.startswith("\x1b]5379;")]), 1)
                self.assertIn("cannot be opened", str(app.query_one("#result-status").render()))
                await pilot.press("escape")
                await pilot.pause()
                self.assertIs(app.focused, table)
                # r brings the study menu over the result; Escape returns to it.
                await pilot.press("r")
                self.assertIs(app.focused, app.query_one("#menu"))
                await pilot.press("escape")
                self.assertIs(app.focused, table)
                # Fullscreen adds the difference, and the details stay beside.
                await pilot.resize_terminal(190, 50)
                await pilot.pause()
                await pilot.pause()
                labels = [str(column.label).strip() for column in table.columns.values()]
                self.assertIn("difference", labels)
                self.assertEqual(str(table.get_row_at(0)[labels.index("difference")]).strip(), "+1666.67")
                self.assertTrue(app.query_one("#summary-box").display)
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
                    await pilot.press("E")
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
        exported = []
        with patch.object(tui_words, "run", return_value=tui_words.Count(study, None, object(), None)), \
                patch.object(tui_words, "save", return_value=None), \
                patch.object(tui_words, "export", side_effect=lambda *arguments: exported.append(arguments)):
            app = EssenceApp(context(Path(tempfile.mkdtemp(prefix="sol-essence-noexport-")) / "state.json"))
            async with app.run_test(size=(120, 40)) as pilot:
                await self.counted(app, pilot)
                await pilot.press("e")
                await pilot.pause()
                self.assertEqual(exported, [])
                self.assertIn("Nothing to export", str(app.query_one("#result-status").render()))
                labels = [str(column.label).strip() for column in app.query_one("#frequencies").columns.values()]
                self.assertNotIn("log₂ ratio", labels)
                self.assertNotIn("reference", labels)
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
                await pilot.press("enter")
                await pilot.pause(0.2)
                self.assertIn("Esc cancels", str(app.query_one("#status").render()))
                await pilot.press("escape")
                await pilot.pause()
                release.set()
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual((shown, saved), ([], []))
                self.assertIn("Cancelled", str(app.query_one("#status").render()))
                self.assertFalse(app.counting)
                app.exit()

    async def test_escape_cancels_from_a_path_field_and_from_a_result(self):
        # Review of #121: an Input or a result view must not swallow the cancelling Escape.
        import threading
        from sol.essence.tui.app import EssenceApp

        release, shown, saved = threading.Event(), [], []
        def run(*arguments, **files):
            release.wait(5)
            return comparison_count()[0]
        with patch.object(tui_words, "run", side_effect=run), \
                patch.object(tui_words, "save", side_effect=lambda count: saved.append(count)):
            app = EssenceApp(context(Path(tempfile.mkdtemp(prefix="sol-essence-cancel-")) / "state.json"))
            async with app.run_test(size=(86, 48)) as pilot:
                await pilot.press("f")
                app.query_one("#target-file").value = "/invented/a.txt"
                await pilot.press("enter")  # Runs from the path field, which keeps the focus.
                await pilot.pause(0.1)
                self.assertTrue(app.counting)
                self.assertIs(app.focused, app.query_one("#target-file"))
                await pilot.press("escape")
                self.assertFalse(app.counting)
                release.set()
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual((app.last_count, saved), (None, []))
                # A finished result, then a rerun cancelled from the concordance.
                release.set()
                app.query_one("#menu").focus()
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                shown_count = app.last_count
                self.assertIsNotNone(shown_count)
                release.clear()
                await pilot.press("enter")
                self.assertIs(app.focused, app.query_one("#sources"))
                await pilot.press("R")
                await pilot.pause(0.1)
                self.assertTrue(app.counting)
                await pilot.press("escape")
                self.assertFalse(app.counting)
                self.assertIs(app.focused, app.query_one("#sources"))  # Escape only cancelled.
                release.set()
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertIs(app.last_count, shown_count)
                self.assertEqual(len(saved), 1)
                self.assertIn("Cancelled", str(app.query_one("#result-status").render()))
                app.exit()

    async def test_rerun_repeats_the_request_that_ran_not_unrun_menu_edits(self):
        # Review of #121: R reran with a path edited in the menu but never run.
        from sol.essence.tui.app import EssenceApp

        calls = []
        def run(context, target, reference, **files):
            calls.append((target, reference, files["target_file"], files["reference_file"]))
            return comparison_count()[0]
        with patch.object(tui_words, "run", side_effect=run), patch.object(tui_words, "save", return_value=None):
            app = EssenceApp(context())
            async with app.run_test(size=(86, 48)) as pilot:
                await pilot.press("f")
                app.query_one("#target-file").value = "/invented/a.txt"
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                await pilot.press("r", "f")
                app.query_one("#target-file").value = "/invented/b.txt"
                await pilot.press("escape", "escape")  # Out of the field, then the menu: nothing ran.
                self.assertFalse(app.query_one("#menu").display)
                await pilot.press("R")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual([call[2] for call in calls], ["/invented/a.txt", "/invented/a.txt"])
                app.exit()

    async def test_a_second_export_waits_for_the_first_even_across_a_resize(self):
        # Review of #121: the buttons' disabled state used to prevent a second file.
        import threading
        from sol.essence.tui.app import EssenceApp

        count, _ = comparison_count()
        release, exported = threading.Event(), []
        def export(chosen, table_format):
            exported.append(table_format)
            release.wait(5)
            return Path("/invented/words.csv")
        with patch.object(tui_words, "run", return_value=count), patch.object(tui_words, "save", return_value=None), \
                patch.object(tui_words, "export", side_effect=export):
            app = EssenceApp(context(Path(tempfile.mkdtemp(prefix="sol-essence-export-")) / "state.json"))
            async with app.run_test(size=(86, 48)) as pilot:
                await self.counted(app, pilot)
                await pilot.press("e")
                await pilot.pause(0.1)
                await pilot.resize_terminal(190, 50)
                await pilot.pause()
                app.query_one("#frequencies").focus()
                await pilot.press("e")
                await pilot.press("E")
                self.assertIn("still running", str(app.query_one("#result-status").render()))
                release.set()
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(exported, ["csv"])
                self.assertIn("Exported:", str(app.query_one("#result-status").render()))
                # Once finished, the next export may run.
                await pilot.press("E")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(exported, ["csv", "tsv"])
                app.exit()

    async def test_a_palette_entry_opens_that_topic_even_under_a_search(self):
        # Review of #121: the palette used an unfiltered index as a filtered position.
        from textual.widgets import Markdown
        from sol.essence.tui.app import EssenceApp
        from sol.essence.tui.reference import ReferenceScreen

        app = EssenceApp(context())
        async with app.run_test(size=(86, 48)) as pilot:
            target = next(entry for entry in app.catalog["entries"] if entry["id"] == "tf-idf")
            for search in ("Word counts", "no such topic"):
                await pilot.press("M", "/")
                app.screen.query_one("#encyclopedia-search").value = search
                await pilot.pause()
                # Enter to the list (or stay, with no matches), then Escape: the search stays.
                await pilot.press("enter")
                if search == "no such topic":
                    app.screen.query_one("#encyclopedia-list").focus()
                await pilot.press("escape")
                self.assertNotIsInstance(app.screen, ReferenceScreen)
                self.assertEqual(app.get_screen("reference").query_one("#encyclopedia-search").value, search)
                await pilot.press("colon")
                await pilot.pause()
                await pilot.press(*f"Encyclopedia: {target['title']}")
                await pilot.pause(0.5)
                await pilot.press("enter")
                await pilot.pause()
                await pilot.pause()
                self.assertIsInstance(app.screen, ReferenceScreen)
                self.assertIn(target["title"], app.screen.query_one("#encyclopedia-entry", Markdown).source)
                await pilot.press("escape")
            app.exit()

    async def test_ctrl_q_leaves_and_saves_even_from_a_text_field(self):
        # Quitting the reader sends Ctrl-Q; a focused input must not swallow it.
        from sol.essence.tui.app import EssenceApp

        state_file = Path(tempfile.mkdtemp(prefix="sol-essence-quit-")) / "state.json"
        app = EssenceApp(context(state_file))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("f")
            self.assertIs(app.focused, app.query_one("#target-file"))
            await pilot.press("ctrl+q")
            await pilot.pause()
        self.assertEqual(json.loads(state_file.read_text())["screen"], "workspace")


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
        # The reference file says "invented" twice; a file's words never open in the reader.
        self.assertEqual([item["open"] for item in found if item["side"] == "reference"], [None, None])
        data_home = root / "data"
        exported = tui_words.export(count, "csv", data_home=data_home)
        self.assertEqual(exported.suffix, ".csv")
        self.assertEqual(exported.stat().st_mode & 0o777, 0o600)
        self.assertTrue(exported.read_text(encoding="utf-8").startswith("word,"))
        self.assertNotEqual(tui_words.export(count, "csv", data_home=data_home), exported)
        # A source changed since the count is refused, not exported.
        reference_file.write_text("Something else entirely.", encoding="utf-8")
        from sol.essence.essence_as_reflection_within_itself.word_inputs import WordStudyError
        with self.assertRaises(WordStudyError) as caught:
            tui_words.export(count, "tsv", data_home=data_home)
        self.assertEqual(caught.exception.status, "stale")
        self.assertEqual(len(list((data_home / "sol" / "studies").iterdir())), 2)
        alone = tui_words.run(real, "passage", "none")
        with self.assertRaisesRegex(ValueError, "Export needs a reference"):
            tui_words.export(alone, "csv", data_home=data_home)


@unittest.skipUnless(_engine_installed(), "the ESSENCE engines are not installed")
class WordContextTests(unittest.TestCase):
    """A word's sources name their heading and page and show the words around it."""

    def test_sources_show_where_and_in_what_words(self):
        from fixtures_corpus import write_runtime_corpus
        from sol import core
        from sol.corpus import contract

        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-context-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        corpus = root / "corpus"
        identifier, _ = write_runtime_corpus(corpus)
        contract.initialize_corpus_identity(corpus)
        snapshot = core.load_snapshot(corpus)
        reference_file = root / "reference.txt"
        reference_file.write_text("Before the research reader, a long invented preamble of filler words "
                                  "appears; then the word research again, and more words after it here.",
                                  encoding="utf-8")
        real = {**context(), "corpus": str(corpus), "reference": core.capture_reference(snapshot, identifier)}
        count = tui_words.run(real, "passage", "file", reference_file=str(reference_file))
        index = next(n for n, row in enumerate(count.study["frequencies"]) if row["word"] == "research")
        target, reference, again = tui_words.sources(count, index)
        self.assertEqual(target["label"], "Synthetic section | p. 7")
        # Every occurrence is listed, numbered within its input, in reading order.
        self.assertEqual((target["number"], reference["number"], again["number"]), (None, 1, 2))
        self.assertEqual(again["context"]["left"], "…of filler words appears; then the word ")
        self.assertEqual([item["label"] for item in (reference, again)],
                         ["text file, at character 11", f"text file, at character {again['label'].split()[-1]}"])
        self.assertLess(int(reference["label"].split()[-1]), int(again["label"].split()[-1].replace(",", "")))
        self.assertEqual(len(tui_words.sources(count, index, limit=2)), 2)
        self.assertEqual(target["context"], {"left": "…invented passage makes this installed ", "word": "research",
                                             "right": " reader useful without extracting any…"})
        self.assertEqual(reference["context"]["word"], "research")
        self.assertEqual(reference["context"]["left"], "Before the ")
        # CRLF line endings keep their offsets.
        crlf = root / "crlf.txt"
        crlf.write_bytes("First line.\r\nThe research reader, in context.\r\nEnd.".encode("utf-8"))
        windows = tui_words.run(real, "passage", "file", reference_file=str(crlf))
        at = next(n for n, row in enumerate(windows.study["frequencies"]) if row["word"] == "research")
        self.assertEqual(tui_words.sources(windows, at)[1]["context"]["left"], "First line. The ")
        # A file changed since the count shows no context rather than the wrong one.
        # Nor can its later occurrences be found again: only the recorded first is listed.
        reference_file.write_text("Something else entirely, research included.", encoding="utf-8")
        count.texts.clear()
        changed = tui_words.sources(count, index)
        self.assertEqual(len(changed), 2)
        self.assertIsNone(changed[1]["context"])
        self.assertIsNone(changed[1]["number"])


@unittest.skipUnless(_engine_installed(), "the ESSENCE engines are not installed")
class SentenceStudyTests(unittest.TestCase):
    """Sentence lengths from the interface, on the real engine."""

    def setUp(self):
        from fixtures_corpus import write_runtime_corpus
        from sol import core
        from sol.corpus import contract

        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-sentences-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        corpus = self.root / "corpus"
        self.identifier, _ = write_runtime_corpus(corpus)
        contract.initialize_corpus_identity(corpus)
        self.snapshot = core.load_snapshot(corpus)
        self.context = {**context(), "corpus": str(corpus),
                        "reference": core.capture_reference(self.snapshot, self.identifier)}

    def test_corpus_targets_measure_open_and_save(self):
        from sol import core
        from sol.essence.essence_as_reflection_within_itself import sentences as engine
        from sol.essence.tui import sentences as tui_sentences

        text = next(p for p in core.load_corpus_book(Path(self.context["corpus"])).passages
                    if p.identifier == self.identifier).text
        for target in ("passage", "section", "book"):
            with self.subTest(target=target):
                count = tui_sentences.run(self.context, target)
                self.assertEqual(count.study["version"], 2)
                self.assertEqual(count.study["summary"]["sentences"], 1)
                lines = tui_sentences.summary(count)
                self.assertTrue(lines[0].startswith("1 sentence, 13 words, 1 input"), lines[0])
                self.assertIn("punctuation-rules-v1", lines[-1])
                (words_cell, beginning, where), = tui_sentences.rows(count)
                self.assertEqual((words_cell, where), ("13", "Synthetic section | p. 7"))
                self.assertTrue(text.startswith(beginning.removesuffix('…')))
                source = tui_sentences.source(count, 0)
                self.assertEqual((source["id"], source["start"]), (self.identifier, 0))
        saved = tui_sentences.save(count, data_home=self.root / "data")
        self.assertTrue(saved.name.startswith("sentences-"))
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        # No book text in the artifact, and it checks against the same provider.
        self.assertNotIn("invented passage", saved.read_text(encoding="utf-8").casefold())
        engine.check_sentence_result(count.target, engine.decode_sentence_result(saved.read_bytes()))

    def test_files_need_no_corpus_and_cannot_open_in_the_reader(self):
        from sol.essence.tui import sentences as tui_sentences

        text = self.root / "invented.txt"
        text.write_text("A short one. Then a somewhat longer second sentence follows here.", encoding="utf-8")
        count = tui_sentences.run({**context(), "corpus": ""}, "file", target_file=str(text))
        self.assertEqual([row[0] for row in tui_sentences.rows(count)], ["8", "3"])
        self.assertEqual(tui_sentences.rows(count)[0][1:], ("Then a somewhat longer second sentence follows here.", "text file"))
        self.assertIsNone(tui_sentences.source(count, 0))
        with self.assertRaisesRegex(ValueError, "no CORE corpus"):
            tui_sentences.run({**context(), "corpus": ""}, "book")

    def test_file_beginnings_are_verbatim_and_verified(self):
        # Reported by Codex's review of #34: CRLF was rewritten, shifting every slice.
        from sol.essence.tui import sentences as tui_sentences

        path = self.root / "crlf.txt"
        text = "\ufeffShort.\r\nThis sentence is much longer.\r\nFinal."
        path.write_bytes(text.encode("utf-8"))
        count = tui_sentences.run({**context(), "corpus": ""}, "file", target_file=str(path))
        self.assertEqual(tui_sentences.rows(count)[0][1], "This sentence is much longer.")
        lines = tui_sentences.summary(count)
        self.assertTrue(any(line.startswith("Mean words by place among the file's retained sentences") for line in lines))
        self.assertNotIn("paragraph", " ".join(lines))
        self.assertNotIn("translation's words", " ".join(lines))
        # A file changed after the count shows no beginnings rather than wrong ones.
        real = tui_sentences.engine()
        class Changing:
            @staticmethod
            def analyze_sentences(provider):
                study = real.analyze_sentences(provider)
                path.write_bytes(b"Something else entirely. Much shorter.")
                return study
        path.write_bytes(text.encode("utf-8"))
        with patch.object(tui_sentences, "engine", return_value=Changing):
            changed = tui_sentences.run({**context(), "corpus": ""}, "file", target_file=str(path))
        self.assertEqual([row[1] for row in tui_sentences.rows(changed)], ["", "", ""])

    def test_a_corpus_changed_since_the_reader_opened_is_refused(self):
        from sol import core
        from sol.corpus import contract
        from sol.essence.tui import sentences as tui_sentences

        source = Path(self.context["corpus"]) / "sample.md"
        source.write_text(source.read_text(encoding="utf-8").replace("An invented passage", "A replaced text", 1),
                          encoding="utf-8")
        contract.reindex(Path(self.context["corpus"]))
        with self.assertRaises(core.ProtocolError) as caught:
            tui_sentences.run(self.context, "section")
        self.assertEqual(caught.exception.code, "generation_changed")


@unittest.skipUnless(essence_launch.textual_available() and _engine_installed(), "needs Textual and the ESSENCE engines")
class SentenceScreenTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_sentence_results_draw_the_distribution_and_open_the_longest(self):
        from sol.essence.tui import sentences as tui_sentences
        from sol.essence.tui.app import EssenceApp

        digest = "d" * 64
        study = {"version": 2, "summary": {"sentences": 2, "tokens": 11, "mean": 5.5, "median": 5.5,
                                           "p10": 3, "p90": 8, "max": 8},
                 "histogram": [{"from": 1, "to": 10, "sentences": 2}, {"from": 11, "to": None, "sentences": 0}],
                 "by_position": {name: {"mean": 5.5, "sentences": 1} for name in ("first", "middle", "last", "only")},
                 "longest": [1, 0], "sentences": [[0, 0, 12, 3], [1, 4, 40, 8]],
                 "input": {"provider": "core", "scope": {"kind": "corpus"},
                           "inputs": [{"id": TARGET, "content_sha256": digest, "reader_path": "/BEING/a.txt",
                                       "sources": [{"printed_page": "7"}]},
                                      {"id": TARGET.replace("2", "3"), "content_sha256": digest,
                                       "reader_path": "/BEING/b.txt", "sources": []}]},
                 "exclusions": {"by_reason": {}, "outside_span": 0}}
        count = tui_sentences.SentenceCount(study, object(), {}, {TARGET: "First heading | p. 7"})
        written, calls = [], []
        def run(*arguments, **files):
            calls.append((arguments, files))
            return count
        with patch.object(tui_sentences, "run", side_effect=run), patch.object(tui_sentences, "save", return_value=None):
            app = EssenceApp(context())
            async with app.run_test(size=(120, 40)) as pilot:
                original = app._driver.write
                app._driver.write = lambda data: (written.append(data), original(data))[1]
                self.assertIs(app.focused, app.query_one("#menu"))
                await pilot.press("s")  # Sentence lengths
                self.assertEqual(app.query_one("#menu").study, "sentences")
                # Reference choices belong to word frequencies only.
                await pilot.press("B")
                self.assertEqual(app.query_one("#menu").reference, "none")
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(calls[0][0][1], "passage")
                self.assertEqual(app.query_one("#results").current, "sentences-view")
                # The distribution is the result itself, drawn as bars.
                histogram = str(app.query_one("#histogram").render())
                self.assertIn("1–10", histogram)
                self.assertIn("█", histogram)
                self.assertIn("median 5.5", histogram)
                table = app.query_one("#longest")
                self.assertEqual([str(column.label).strip() for column in table.columns.values()],
                                 ["words", "beginning", "where"])
                self.assertEqual([str(cell).strip() for cell in table.get_row_at(0)[::2]], ["8", "/BEING/b.txt"])
                self.assertEqual([str(cell).strip() for cell in table.get_row_at(1)[::2]], ["3", "p.7"])
                summary = str(app.query_one("#sentence-summary").render())
                self.assertIn("2 sentences, 11 words", summary)
                self.assertIs(app.focused, table)
                await pilot.press("enter")
                await pilot.pause()
                requests = [data for data in written if data.startswith("\x1b]5379;sol-essence;")]
                self.assertEqual(len(requests), 1)
                payload = json.loads(base64.b64decode(requests[0][len("\x1b]5379;sol-essence;"):-1]))
                self.assertEqual(payload["source"], {"id": TARGET.replace("2", "3"), "start": 4,
                                                     "content_sha256": digest})
                app.exit()


@unittest.skipUnless(essence_launch.textual_available(), "needs Textual")
class RefinedLayoutTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_conditional_fields_and_reference_free_columns(self):
        from sol.essence.tui.app import EssenceApp
        from sol.essence.tui.reference import BROWSERS
        app = EssenceApp(context())
        async with app.run_test(size=(100, 36)) as pilot:
            self.assertFalse(app.query_one('#target-file-row').display)
            self.assertFalse(app.query_one('#reference-file-row').display)
            self.assertFalse(app.query_one('#tfidf-settings').display)
            self.assertTrue(BROWSERS['encyclopedia'].startswith('Encyclopedia'))
            await pilot.press('f')
            app.query_one('#menu').focus()
            await pilot.press('F')
            await pilot.pause()
            self.assertTrue(app.query_one('#target-file-row').display)
            self.assertTrue(app.query_one('#reference-file-row').display)
            self.assertIs(app.focused, app.query_one('#reference-file'))
            await pilot.press('escape')
            self.assertIs(app.focused, app.query_one('#menu'))
            await pilot.press('t')
            await pilot.pause()
            self.assertFalse(app.query_one('#reference-file-row').display)
            self.assertTrue(app.query_one('#tfidf-settings').display)
            self.assertNotIn('Compare with', str(app.query_one('#menu-choices').render()))
            count = tui_words.Count(FakeWords.analyze_words(object()), None, object(), None)
            app.show_result(count, None)
            await pilot.pause()
            self.assertEqual([str(c.label).strip() for c in app.query_one('#frequencies').columns.values()],
                             ['word', 'n', '/10k', 'target'])
            self.assertNotIn('Reference:', str(app.query_one('#summary').render()))
            self.assertIn('1 input (', str(app.query_one('#summary').render()))

    async def test_concordance_aligns_the_word_and_keeps_its_spaces(self):
        from sol.essence.tui import views
        from sol.essence.tui.app import EssenceApp
        text = 'This objective thinking is thus the content of pure science.'
        start = text.index('is thus')
        left, word, right = views.kwic(tui_words._context(text, start, start + 2), 30, 30)
        self.assertEqual((left.strip(), word, right), ('This objective thinking', 'is', 'thus the content of pure scie…'))
        self.assertEqual(len(left), 30)
        count, _ = comparison_count()
        app = EssenceApp(context())
        async with app.run_test(size=(90, 36)) as pilot:
            app.show_result(count, None)
            await pilot.pause()
            table = app.query_one('#sources')
            labels = [str(c.label).strip() for c in table.columns.values()]
            self.assertEqual(labels[1:], ['left context', '', 'right context', 'where'])
            self.assertEqual(table.get_row_at(0)[4].plain.strip(), 'p.7')
            # One line per occurrence, so the word stays in one column.
            self.assertEqual({row.height for row in table.rows.values()}, {1})
            app.query_one('#result-status').update('Checking sources and exporting…')
            await pilot.resize_terminal(70, 30)
            await pilot.pause()
            await pilot.pause()
            self.assertIn('exporting', str(app.query_one('#result-status').render()))
            self.assertEqual(table.max_scroll_x, 0)


@unittest.skipUnless(essence_launch.textual_available() and _engine_installed(), "needs Textual and engines")
class TfidfStudyTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_tfidf_engine_save_passage_navigation_and_file_switch(self):
        from fixtures_corpus import write_runtime_corpus
        from sol import core
        from sol.corpus import contract
        from sol.essence import check_tfidf_result, decode_tfidf_result
        from sol.essence.tui import tfidf
        from sol.essence.tui.app import EssenceApp
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / 'corpus'
            identifier, _ = write_runtime_corpus(corpus)
            contract.initialize_corpus_identity(corpus)
            snapshot = core.load_snapshot(corpus)
            real = {**context(), 'corpus': str(corpus), 'reference': core.capture_reference(snapshot, identifier)}
            count = tfidf.run(real, 'section')
            self.assertEqual(count.study['protocol'], 'sol.tfidf')
            self.assertIn('Synthetic section\np. 7', tfidf.rows(count)[0][0])
            saved = tfidf.save(count, data_home=root / 'data')
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            check_tfidf_result(count.target, decode_tfidf_result(saved.read_bytes()))
            self.assertNotIn('Synthetic section', saved.read_text())
            source = tfidf.source(count, 0)
            self.assertEqual(source['id'], identifier)
            app = EssenceApp(real)
            real_run = tfidf.run
            with patch.object(tfidf, 'run', return_value=count):
                async with app.run_test(size=(100, 36)) as pilot:
                    await pilot.press('t')
                    self.assertEqual(app.query_one('#menu').study, 'tfidf')
                    await pilot.press('enter')
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    self.assertEqual(app.query_one('#results').current, 'tfidf-view')
                    self.assertEqual(app.query_one('#passages').row_count, len(count.study['documents']))
                    self.assertTrue(app.query_one('#overall').display)
                    self.assertIs(app.focused, app.query_one('#passages'))
                    with patch.object(app, 'open_in_reader') as opened:
                        await pilot.press('enter')
                        opened.assert_called_once_with(source)
                    path = root / 'input.txt'
                    path.write_text('Being and nothing. Being becomes.', encoding='utf-8')
                    file_count = real_run({**context(), 'corpus': ''}, 'file', target_file=str(path))
                    self.assertIsNone(tfidf.source(file_count, 0))
                    app.show_result(file_count, None)
                    await pilot.pause()
                    await pilot.press('enter')
                    self.assertIn('cannot be opened', str(app.query_one('#result-status').render()))
                    app.show_result(tui_words.run({**context(), 'corpus': ''}, 'file', 'none', target_file=str(path)), None)
                    await pilot.pause()
                    self.assertEqual(app.query_one('#results').current, 'words-view')
            with self.assertRaisesRegex(ValueError, 'no CORE corpus'):
                tfidf.run({**context(), 'corpus': ''}, 'book')
            file = corpus / 'sample.md'
            file.write_text(file.read_text().replace('An invented passage', 'A changed passage', 1))
            contract.reindex(corpus)
            with self.assertRaises(core.ProtocolError):
                tfidf.run(real, 'section')


class PresentationHelperTests(unittest.TestCase):
    def test_beginnings_end_at_a_word_with_an_ellipsis(self):
        from sol.essence.tui import sentences as tui_sentences
        long = "True, the individual is more than just restrictions on all sides and yet nothing"
        self.assertEqual(tui_sentences._beginning(long), "True, the individual is more than just restrictions on all…")
        self.assertEqual(tui_sentences._beginning("  A  short\nsentence "), "A short sentence")
        self.assertEqual(tui_sentences._beginning("x" * 70), "x" * 60 + "…")

    def test_a_section_scope_is_named_by_its_title_and_first_page(self):
        from types import SimpleNamespace
        passage = SimpleNamespace(path=("BEING", "quality", "p1"), printed_page=84,
                                  node=SimpleNamespace(title="Quality"))
        book = SimpleNamespace(passages=[passage])
        part = {"scope": {"kind": "section", "path": "/BEING/quality"}}
        self.assertEqual(tui_words.scope_name(book, part), "Quality, from p. 84")
        self.assertEqual(tui_words.scope_name(None, part), "/BEING/quality")
        self.assertEqual(tui_words.scope_name(book, {"scope": {"kind": "corpus"}}), "corpus")


@unittest.skipUnless(essence_launch.textual_available() and _engine_installed(), "needs Textual and engines")
class SmallResultsTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_each_study_fits_and_opens_sources_at_every_size(self):
        from fixtures_corpus import write_runtime_corpus
        from sol import core
        from sol.corpus import contract
        from sol.essence.tui import sentences, tfidf
        from sol.essence.tui.app import EssenceApp

        first = {"words-view": "#frequencies", "sentences-view": "#longest", "tfidf-view": "#passages"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / 'corpus'
            identifier, _ = write_runtime_corpus(corpus)
            contract.initialize_corpus_identity(corpus)
            ctx = {**context(), 'corpus': str(corpus),
                   'reference': core.capture_reference(core.load_snapshot(corpus), identifier)}
            counts = [tui_words.run(ctx, 'book', 'none'), tui_words.run(ctx, 'section', 'book'),
                      sentences.run(ctx, 'book'), tfidf.run(ctx, 'book')]
            app = EssenceApp(ctx)
            async with app.run_test(size=(120, 40)) as pilot:
                for count in counts:
                    receipt = json.dumps(count.study, sort_keys=True)
                    app.show_result(count, None)
                    await pilot.pause()
                    view = app.result_view(count)
                    table = view.query_one(first[view.id])
                    # Beside the reader (86 and 40 columns), fullscreen, and back.
                    for width, height in ((86, 48), (40, 24), (190, 50), (80, 24)):
                        with self.subTest(study=type(count).__name__, size=(width, height)):
                            table.focus()
                            if table.row_count > 1:
                                table.move_cursor(row=1)
                            row = table.cursor_row
                            await pilot.resize_terminal(width, height)
                            await pilot.pause()
                            await pilot.pause()
                            self.assertEqual(table.cursor_row, row)
                            self.assertIs(app.focused, table)
                            bottom = app.query_one('#result-status').region.y
                            for widget in view.query('VimTable'):
                                if not widget.display or not widget.region.height:
                                    continue
                                self.assertLessEqual(widget.region.bottom, bottom)
                                self.assertLessEqual(widget.region.right, width)
                                self.assertEqual(widget.max_scroll_x, 0, widget.id)
                            with patch.object(app, 'open_in_reader') as opened:
                                await pilot.press('enter')
                                if isinstance(count, tui_words.Count):
                                    sources = view.query_one('#sources')
                                    self.assertIs(app.focused, sources)
                                    await pilot.press('enter')
                                    opened.assert_called_once_with(view.shown_sources[sources.cursor_row]['open'])
                                    await pilot.press('escape')
                                    self.assertIs(app.focused, table)
                                else:
                                    opened.assert_called_once()
                    self.assertEqual(json.dumps(count.study, sort_keys=True), receipt)

    async def test_long_words_undefined_measures_and_themes_survive_resize(self):
        from sol.essence.tui.app import EssenceApp, TEXTUAL_THEMES

        count, _ = comparison_count()
        count.study['frequencies'][0]['word'] = '超長語' * 30
        count.comparison['rows'][0].update(log2_rate_ratio=None, log2_ratio_status='empty_reference')
        for theme in TEXTUAL_THEMES:
            with self.subTest(theme=theme):
                app = EssenceApp(context(), theme=theme)
                async with app.run_test(size=(120, 40)) as pilot:
                    app.show_result(count, None)
                    await pilot.pause()
                    await pilot.press('enter', 'j')
                    sources = app.query_one('#sources')
                    source_row = sources.cursor_row
                    app.query_one('#result-status').update('Checking sources and exporting…')
                    await pilot.resize_terminal(80, 24)
                    await pilot.pause()
                    await pilot.pause()
                    table = app.query_one('#frequencies')
                    self.assertEqual(table.max_scroll_x, 0)
                    self.assertEqual(sources.max_scroll_x, 0)
                    self.assertIs(app.focused, sources)
                    self.assertEqual(sources.cursor_row, source_row)
                    self.assertIn('exporting', str(app.query_one('#result-status').render()))
                    self.assertIn('empty reference', str(table.get_row_at(0)[-1]))
                    self.assertLessEqual(sources.region.bottom, app.query_one('#result-status').region.y)
                    await pilot.press('escape')
                    self.assertIs(app.focused, table)
