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
    async def test_catalog_reflows_without_losing_selection_or_keyboard_focus(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context(), theme="night")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("2", "down", "down")
            listing = app.query_one("#methods-list")
            detail = app.query_one("#methods-detail")
            selected = listing.highlighted
            entry = app.query_one("#methods-entry").source
            for width, height in ((80, 24), (40, 24), (120, 40)):
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                self.assertIs(app.focused, listing)
                self.assertEqual(listing.highlighted, selected)
                self.assertEqual(app.query_one("#methods-entry").source, entry)
                for widget in (listing, detail):
                    self.assertGreater(widget.content_region.height, 0)
                    self.assertGreater(widget.content_region.width, 0)
                    self.assertLessEqual(widget.region.right, width)
                    self.assertLessEqual(widget.region.bottom, app.query_one("#layout-hint").region.y)
                if width >= 100:
                    self.assertLessEqual(listing.region.right, detail.region.x)
                else:
                    self.assertLessEqual(listing.region.bottom, detail.region.y)
                await pilot.press("enter")
                self.assertIs(app.focused, detail)
                await pilot.press("escape")
                self.assertIs(app.focused, listing)
            app.exit()

    async def test_form_reflow_keeps_choices_and_fields_reachable_in_a_reader_split(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context(), theme="paper")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("3", "down", "down", "enter")
            app.query_one("#target").focus()
            await pilot.press("down", "down", "down", "enter")
            app.query_one("#target-file").value = "/invented/a long source name.txt"
            app.query_one("#top-n").value = "37"
            for width, height in ((80, 24), (40, 24), (120, 40)):
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                self.assertEqual(app.choice("study"), "tfidf")
                self.assertEqual(app.choice("target"), "file")
                self.assertEqual(app.query_one("#target-file").value, "/invented/a long source name.txt")
                self.assertEqual(app.query_one("#top-n").value, "37")
                self.assertFalse(app.query_one("#reference-group").display)
                for selector in ("#target-file", "#top-n", "#run"):
                    widget = app.query_one(selector)
                    widget.focus()
                    widget.scroll_visible(animate=False)
                    await pilot.pause()
                    self.assertIs(app.focused, widget)
                    self.assertGreater(widget.region.width, 0)
                    self.assertGreaterEqual(widget.region.y, app.query_one("#experiment-body").content_region.y)
                    self.assertLessEqual(widget.region.bottom, app.query_one("#experiment-body").content_region.bottom)
                    self.assertLessEqual(widget.region.right, width)
            app.exit()

    async def test_empty_results_offer_a_keyboard_route_to_configuration(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test(size=(60, 24)) as pilot:
            await pilot.press("4")
            self.assertTrue(app.query_one("#empty-results").display)
            self.assertFalse(app.query_one("#results-workspace").display)
            self.assertIs(app.focused, app.query_one("#configure"))
            await pilot.press("enter")
            self.assertEqual(app.query_one("#screens").active, "experiment")
            self.assertIs(app.focused, app.query_one("#study"))
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
                    for width in (40, 60, 120):
                        await pilot.resize_terminal(width, 24 if width < 100 else 40)
                        await pilot.pause()
                        table = app.query_one("#frequencies")
                        self.assertEqual(table.max_scroll_x, 0)
                        self.assertGreater(table.content_region.height, 1)
                        self.assertFalse(app.query_one("#empty-results").display)
                        for selector in ("#frequencies", "#sources", "#overall"):
                            widget = app.query_one(selector)
                            if widget.display:
                                self.assertEqual(widget.max_scroll_x, 0)
                                self.assertLessEqual(widget.region.right, width)
                                self.assertLessEqual(widget.region.bottom, app.query_one("#layout-hint").region.y)
                        self.assertEqual(json.dumps(count.study, sort_keys=True), original)
                app.exit()

    async def test_resize_with_sort_menu_open_also_reflows_the_workspace(self):
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp, WordSort

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
                await pilot.press("escape", "2")
                await pilot.pause()
                listing = app.query_one("#methods-list")
                detail = app.query_one("#methods-detail")
                self.assertLessEqual(listing.region.bottom, detail.region.y)
                self.assertIs(app.focused, listing)
                app.exit()
