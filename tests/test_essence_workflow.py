"""Presentation-only filtering, details, and method-to-setup navigation."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fixtures_async import UIEventLoop
from sol.interchange.essence import textual_available


def context():
    return {"version": 1,
            "reference": {"reference": {"target_id": "bbbbbbbb-0000-4000-8000-000000000002"}},
            "cursor_offset": 0, "selection": None, "label": "Invented study",
            "corpus": "", "state_file": None}


@unittest.skipUnless(textual_available(), "needs the essence extra (Textual)")
class WorkflowTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-workflow-")
        self.addCleanup(temporary.cleanup)
        self.target = Path(temporary.name) / "target.txt"
        self.reference = Path(temporary.name) / "reference.txt"
        self.target.write_text("Alpha alpha alpha beta beta café cafe\u0301 can’t. Zeta!", encoding="utf-8")
        self.reference.write_text("Alpha beta café can’t gamma.", encoding="utf-8")

    def count(self):
        from sol.essence.tui import words
        return words.run(context(), "file", "file", target_file=self.target, reference_file=self.reference)

    async def test_filter_normalizes_unicode_tracks_sources_and_never_changes_export(self):
        from sol.essence import export_word_comparison
        from sol.essence.tui.app import EssenceApp

        count = self.count()
        original = json.dumps(count.study, sort_keys=True)
        exported = export_word_comparison(count.target, reference=count.reference, result=count.study)
        app = EssenceApp(context())
        async with app.run_test(size=(80, 24)) as pilot:
            app.show_result(count, None)
            await pilot.pause()
            view = app.query_one("#words-view")
            field = app.query_one("#word-filter")
            self.assertFalse(field.display)
            await pilot.press("/")
            self.assertTrue(field.display)
            self.assertIs(app.focused, field)
            field.value = "CAFE\u0301"
            await pilot.pause()
            table = app.query_one("#frequencies")
            self.assertEqual(table.row_count, 1)
            self.assertEqual(table.get_row_at(0)[0], "café")
            self.assertTrue(view.shown_sources)
            self.assertTrue(all(item["context"]["word"] in ("café", "cafe\u0301") for item in view.shown_sources))
            self.assertIn("café", str(app.query_one("#sources-label").render()))
            field.value = "CAN’T"
            await pilot.pause()
            self.assertEqual(table.get_row_at(0)[0], "can't")
            await pilot.press("enter")
            self.assertIs(app.focused, table)
            await pilot.resize_terminal(40, 24)
            await pilot.pause()
            self.assertEqual(table.get_row_at(0)[0], "can't")
            self.assertEqual(field.value, "CAN’T")
            field.value = "[bold]"
            await pilot.pause()
            self.assertIn("[bold]", str(app.query_one("#summary").render()))
            await pilot.press("/", "escape")
            await pilot.pause()
            self.assertEqual(field.value, "")
            self.assertGreater(table.row_count, 1)
            await pilot.press("escape")
            self.assertIs(app.focused, table)
            self.assertFalse(field.display)
            app.exit()
        self.assertEqual(json.dumps(count.study, sort_keys=True), original)
        self.assertEqual(export_word_comparison(count.target, reference=count.reference, result=count.study), exported)

    async def test_filter_precedes_display_limit_and_empty_matches_clear_old_sources(self):
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp

        count = self.count()
        app = EssenceApp(context())
        with patch.object(words, "ROW_LIMIT", 2):
            async with app.run_test(size=(80, 24)) as pilot:
                app.show_result(count, None)
                await pilot.pause()
                view = app.query_one("#words-view")
                table = app.query_one("#frequencies")
                self.assertEqual(table.row_count, 2)
                field = app.query_one("#word-filter")
                field.value = "zeta"
                await pilot.pause()
                self.assertEqual(table.get_row_at(0)[0], "zeta")
                self.assertEqual(view.word_order,
                                 (next(i for i, row in enumerate(count.study["frequencies"]) if row["word"] == "zeta"),))
                view.sort_words((0, True))
                await pilot.pause()
                self.assertEqual(table.get_row_at(0)[0], "zeta")
                field.value = "no such word"
                await pilot.pause()
                self.assertEqual(table.row_count, 0)
                self.assertEqual(view.shown_sources, ())
                self.assertEqual(app.query_one("#sources").row_count, 0)
                self.assertIn("No matching words", str(app.query_one("#sort-status").render()))
                app.show_result(self.count(), None)
                await pilot.pause()
                self.assertEqual(field.value, "")
                self.assertEqual(view.word_filter, "")
                self.assertEqual(table.row_count, 2)
                app.exit()

    async def test_function_words_hide_only_from_the_display(self):
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp

        count = self.count()
        original = json.dumps(count.study, sort_keys=True)
        catalog = {"id": "invented-list-v1", "words": frozenset({"alpha", "beta"})}
        app = EssenceApp(context())
        with patch.object(EssenceApp, "function_words", return_value=catalog):
            async with app.run_test(size=(86, 48)) as pilot:
                app.show_result(count, None)
                await pilot.pause()
                table = app.query_one("#frequencies")
                shown = lambda: [table.get_row_at(row)[0] for row in range(table.row_count)]
                self.assertIn("alpha", shown())  # Off by default.
                await pilot.press("f")
                await pilot.pause()
                self.assertNotIn("alpha", shown())
                self.assertNotIn("beta", shown())
                self.assertIn("zeta", shown())
                self.assertIn("function words hidden (invented-list-v1)", str(app.query_one("#sort-status").render()))
                self.assertIn("Counts, denominators, saved artifacts and exports keep every word",
                              str(app.query_one("#summary").render()))
                # Counts and totals still describe the whole study.
                self.assertIn(f"{count.study['target']['summary']['token_count']:,} tokens",
                              str(app.query_one("#result-metrics").render()))
                await pilot.press("f")
                await pilot.pause()
                self.assertIn("alpha", shown())
                app.exit()
        self.assertEqual(json.dumps(count.study, sort_keys=True), original)
        with patch.object(EssenceApp, "function_words", return_value=None):
            app = EssenceApp(context())
            async with app.run_test(size=(86, 48)) as pilot:
                app.show_result(count, None)
                await pilot.pause()
                await pilot.press("f")
                await pilot.pause()
                self.assertIn("no function-word list", str(app.query_one("#result-status").render()))
                app.exit()

    async def test_details_and_metrics_for_each_study_survive_resize_without_losing_selection(self):
        from sol.essence.tui import sentences, tfidf
        from sol.essence.tui.app import EssenceApp

        counts = [self.count(), sentences.run(context(), "file", target_file=self.target),
                  tfidf.run(context(), "file", target_file=self.target, top_n=3)]
        first = {"words-view": ("#frequencies", "#summary-box", "#result-metrics"),
                 "sentences-view": ("#longest", "#sentence-details", "#sentence-metrics"),
                 "tfidf-view": ("#passages", "#tfidf-details", "#tfidf-metrics")}
        app = EssenceApp(context(), theme="paper")
        async with app.run_test(size=(120, 40)) as pilot:
            for count in counts:
                app.show_result(count, None)
                await pilot.pause()
                view = app.result_view(count)
                table_id, details_id, metrics_id = first[view.id]
                table, details = app.query_one(table_id), app.query_one(details_id)
                table.move_cursor(row=min(1, table.row_count - 1))
                row = table.cursor_row
                self.assertTrue(str(app.query_one(metrics_id).render()))
                self.assertFalse(details.display)
                await pilot.press("i")
                self.assertTrue(details.display)
                self.assertIs(app.focused, details)
                for width in (80, 40):
                    await pilot.resize_terminal(width, 24)
                    await pilot.pause()
                    await pilot.pause()
                    self.assertTrue(details.display)
                    self.assertEqual(table.cursor_row, row)
                    for widget in view.query("VimTable"):
                        if widget.display:
                            self.assertLessEqual(widget.region.right, width)
                            self.assertLessEqual(widget.region.bottom, app.query_one("#result-status").region.y)
                await pilot.press("escape", "i")
                self.assertFalse(details.display)
                self.assertIs(app.focused, table)
                self.assertEqual(table.cursor_row, row)
                # Fullscreen always shows the details beside the result.
                await pilot.resize_terminal(190, 50)
                await pilot.pause()
                await pilot.pause()
                self.assertTrue(details.display)
                self.assertGreater(details.region.x, table.region.x)
                await pilot.resize_terminal(120, 40)
                await pilot.pause()
                await pilot.pause()
            app.exit()

    async def test_method_shortcuts_preserve_menu_values_and_never_run_a_study(self):
        from sol.essence.tui.app import EssenceApp
        from sol.essence.tui.reference import ReferenceScreen

        app = EssenceApp(context())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("f")
            app.query_one("#target-file").value = str(self.target)
            app.query_one("#top-n").value = "37"
            menu = app.query_one("#menu")
            await pilot.press("escape")  # From the path field back to the menu's keys.
            self.assertIs(app.focused, menu)
            with patch.object(app, "count_words") as run:
                for index, study in ((0, "words"), (1, "words"), (2, "tfidf"), (3, "sentences")):
                    await pilot.press("M", "2")
                    screen = app.screen
                    screen.query_one("#methods-list").highlighted = index
                    await pilot.pause()
                    button = screen.query_one("#use-method")
                    self.assertFalse(button.disabled)
                    button.focus()
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertNotIsInstance(app.screen, ReferenceScreen)
                    self.assertIs(app.focused, menu)
                    self.assertEqual(menu.study, study)
                    if index == 1:
                        # Word comparison supplies a reference when none was chosen.
                        self.assertEqual(menu.reference, "file")
                    self.assertEqual(app.query_one("#target-file").value, str(self.target))
                    self.assertEqual(app.query_one("#top-n").value, "37")
                run.assert_not_called()
            for index in (4, 5):
                await pilot.press("M", "2")
                screen = app.screen
                screen.query_one("#methods-list").highlighted = index
                await pilot.pause()
                self.assertTrue(screen.query_one("#use-method").disabled)
                self.assertIn("CLI", str(screen.query_one("#method-availability").render()))
                await pilot.press("escape")
            app.exit()
