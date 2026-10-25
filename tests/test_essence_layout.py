"""Keyboard access and retained state across the ESSENCE panel breakpoints."""
from __future__ import annotations

import unittest
import json
from pathlib import Path
import tempfile

from fixtures_async import UIEventLoop
from sol.interchange.essence import textual_available


def context():
    return {"version": 1,
            "reference": {"reference": {"target_id": "bbbbbbbb-0000-4000-8000-000000000002"}},
            "cursor_offset": 0, "selection": None, "label": "Invented section · p. 7",
            "corpus": "", "state_file": None}


@unittest.skipUnless(textual_available(), "needs the essence extra (Textual)")
class PanelLayoutTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_large_counts_keep_a_space_before_them_and_the_strip_fits(self):
        from rich.cells import cell_len
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp

        with tempfile.TemporaryDirectory() as directory:
            target, reference = Path(directory) / "t.txt", Path(directory) / "r.txt"
            target.write_text("the being of nothing and " * 11600, encoding="utf-8")
            reference.write_text("the becoming of being and " * 28400, encoding="utf-8")
            count = words.run(context(), "file", "file", target_file=target, reference_file=reference)
        app = EssenceApp(context())
        async with app.run_test(size=(86, 48)) as pilot:
            app.last_run = ("words", "file", "file", str(target), str(reference), 20)
            app.show_result(count, None)
            await pilot.pause()
            await pilot.pause()
            table = app.query_one("#frequencies")
            widths = [column.width for column in table.columns.values() if str(column.label).strip() == "n"]
            self.assertTrue(widths and all(width >= len("11,600") + 2 for width in widths), widths)
            header = [str(column.label) for column in table.columns.values()]
            self.assertTrue(all(cell_len(label) <= column.width
                                for label, column in zip(header, table.columns.values())), header)
            title = app.query_one("#sources-label").render()
            self.assertLessEqual(cell_len(str(title)), app.query_one("#sources-label").size.width)
            self.assertIn("where", str(title))
            await pilot.press("q")

    async def test_catalog_reflows_without_losing_selection_or_keyboard_focus(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context(), theme="night")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("M", "2", "down", "down")
            screen = app.screen
            listing = screen.query_one("#methods-list")
            detail = screen.query_one("#methods-detail")
            selected = listing.highlighted
            entry = screen.query_one("#methods-entry").source
            for width, height in ((80, 24), (40, 24), (120, 40)):
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                self.assertIs(app.focused, listing)
                self.assertEqual(listing.highlighted, selected)
                self.assertEqual(screen.query_one("#methods-entry").source, entry)
                for widget in (listing, detail):
                    self.assertGreater(widget.content_region.height, 0)
                    self.assertGreater(widget.content_region.width, 0)
                    self.assertLessEqual(widget.region.right, width)
                    self.assertLessEqual(widget.region.bottom, height - 1)
                if width >= 100:
                    self.assertLessEqual(listing.region.right, detail.region.x)
                else:
                    self.assertLessEqual(listing.region.bottom, detail.region.y)
                await pilot.press("enter")
                self.assertIs(app.focused, detail)
                await pilot.press("escape")
                self.assertIs(app.focused, listing)
            app.exit()

    async def test_menu_reflow_keeps_choices_and_fields_reachable_in_a_reader_split(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context(), theme="paper")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("t", "f")
            menu = app.query_one("#menu")
            app.query_one("#target-file").value = "/invented/a long source name.txt"
            app.query_one("#top-n").value = "37"
            for width, height in ((86, 48), (80, 24), (40, 24), (120, 40)):
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                self.assertEqual((menu.study, menu.target, menu.reference), ("tfidf", "file", "none"))
                self.assertEqual(app.query_one("#target-file").value, "/invented/a long source name.txt")
                self.assertEqual(app.query_one("#top-n").value, "37")
                self.assertNotIn("Compare with", str(app.query_one("#menu-choices").render()))
                for selector in ("#target-file", "#top-n"):
                    widget = app.query_one(selector)
                    widget.focus()
                    await pilot.pause()
                    self.assertIs(app.focused, widget)
                    self.assertGreater(widget.region.width, 0)
                    self.assertLessEqual(widget.region.bottom, app.query_one("#result-status").region.y)
                    self.assertLessEqual(widget.region.right, width)
                # Narrow menus stack their groups; every choice stays readable.
                choices = str(app.query_one("#menu-choices").render())
                self.assertIn("TF-IDF", choices)
                self.assertIn("a text file", choices)
            app.exit()

    async def test_opening_shows_the_menu_with_an_explanation(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test(size=(86, 48)) as pilot:
            await pilot.pause()
            self.assertTrue(app.query_one("#intro").display)
            # A short window gives the menu the intro's lines.
            await pilot.resize_terminal(60, 24)
            await pilot.pause()
            self.assertFalse(app.query_one("#intro").display)
            self.assertFalse(app.query_one("#results").display)
            self.assertIs(app.focused, app.query_one("#menu"))
            self.assertIn("Will count the words of this passage", str(app.query_one("#menu-summary").render()))
            # Escape before any result keeps the menu: there is nothing to return to.
            await pilot.press("escape")
            self.assertTrue(app.query_one("#menu").display)
            app.exit()

    async def test_each_result_keeps_all_columns_inside_narrow_frames(self):
        from sol.essence.tui import sentences, tfidf, words
        from sol.essence.tui.app import EssenceApp

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.txt"
            reference = Path(directory) / "reference.txt"
            target.write_text("Alpha beta alpha. Gamma delta epsilon!", encoding="utf-8")
            reference.write_text("Alpha gamma gamma. Zeta eta theta.", encoding="utf-8")
            ctx = context()
            counts = [words.run(ctx, "file", "file", target_file=target, reference_file=reference),
                      sentences.run(ctx, "file", target_file=target),
                      tfidf.run(ctx, "file", target_file=target)]
            app = EssenceApp(ctx)
            async with app.run_test(size=(120, 40)) as pilot:
                for count in counts:
                    original = json.dumps(count.study, sort_keys=True)
                    app.show_result(count, None)
                    view = app.result_view(count)
                    for width in (40, 60, 86, 120, 190):
                        await pilot.resize_terminal(width, 24 if width < 100 else 40)
                        await pilot.pause()
                        await pilot.pause()
                        self.assertFalse(app.query_one("#intro").display)
                        for widget in view.query("VimTable"):
                            if widget.display and widget.region.height:
                                self.assertEqual(widget.max_scroll_x, 0, (widget.id, width))
                                self.assertLessEqual(widget.region.right, width)
                                self.assertLessEqual(widget.region.bottom, app.query_one("#result-status").region.y)
                        self.assertEqual(json.dumps(count.study, sort_keys=True), original)
                app.exit()

    async def test_resize_with_sort_menu_open_also_reflows_the_workspace(self):
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp
        from sol.essence.tui.results import WordSort

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invented.txt"
            path.write_text("Alpha beta beta. Gamma delta.", encoding="utf-8")
            app = EssenceApp(context())
            count = words.run(context(), "file", "file", target_file=path, reference_file=path)
            async with app.run_test(size=(120, 40)) as pilot:
                app.show_result(count, None)
                await pilot.pause()
                await pilot.press("s")
                await pilot.resize_terminal(80, 24)
                await pilot.pause()
                self.assertIsInstance(app.screen, WordSort)
                await pilot.press("escape")
                await pilot.pause()
                table = app.query_one("#frequencies")
                self.assertIs(app.focused, table)
                self.assertEqual(table.max_scroll_x, 0)
                self.assertLessEqual(table.region.right, 80)
                app.exit()
