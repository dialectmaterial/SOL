"""Filtered catalog actions keep their identity and fit reader splits."""
from __future__ import annotations

import unittest

from fixtures_async import UIEventLoop
from sol.interchange.essence import textual_available


def context():
    return {"version": 1,
            "reference": {"reference": {"target_id": "bbbbbbbb-0000-4000-8000-000000000002"}},
            "cursor_offset": 0, "selection": None, "label": "Invented section",
            "corpus": "", "state_file": None}


@unittest.skipUnless(textual_available(), "needs the essence extra (Textual)")
class CatalogNavigationTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_filtered_method_configures_its_identity_and_empty_matches_disable_actions(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context(), theme="night")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("2", "/")
            field = app.query_one("#methods-search")
            self.assertIs(app.focused, field)
            field.value = "tfidf"
            await pilot.pause()
            listing = app.query_one("#methods-list")
            self.assertEqual(listing.option_count, 1)
            self.assertEqual(listing.highlighted, 0)
            self.assertIn("TF-IDF", app.query_one("#methods-entry").source)
            await pilot.press("enter", "enter")
            self.assertIs(app.focused, app.query_one("#methods-detail"))
            app.query_one("#target-file").value = "/invented/retained.txt"
            app.query_one("#use-method").focus()
            await pilot.press("enter")
            self.assertEqual(app.query_one("#screens").active, "experiment")
            self.assertEqual(app.choice("study"), "tfidf")
            self.assertEqual(app.query_one("#target-file").value, "/invented/retained.txt")
            self.assertIsNone(app.last_count)
            await pilot.press("2", "ctrl+f")
            self.assertEqual(field.value, "tfidf")
            field.value = "Verify a saved study"
            await pilot.pause()
            self.assertEqual(listing.option_count, 1)
            self.assertIn("sol essence check", app.query_one("#methods-entry").source)
            self.assertTrue(app.query_one("#use-method").disabled)
            self.assertIn("CLI", str(app.query_one("#method-availability").render()))
            field.value = "no matching method [bold]"
            await pilot.pause()
            self.assertEqual(listing.option_count, 0)
            self.assertIn("No matches", app.query_one("#methods-entry").source)
            self.assertTrue(app.query_one("#use-method").disabled)
            self.assertEqual(str(app.query_one("#methods-count").render()), f"0 / {len(app.methods['entries'])}")
            await pilot.press("enter")
            self.assertIs(app.focused, field)
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(listing.option_count, len(app.methods["entries"]))
            self.assertFalse(app.query_one("#use-method").disabled)
            self.assertIs(app.focused, field)
            await pilot.press("escape")
            self.assertIs(app.focused, listing)
            app.exit()

    async def test_search_description_unicode_and_rapid_edits_keep_the_latest_entry(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        # A synthetic accented title exercises the same local matching as normal entries.
        app.catalog["entries"][0]["title"] = "Café’s word counts"
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("/")
            field = app.query_one("#encyclopedia-search")
            field.value = "CAFE\u0301’S"
            await pilot.pause()
            self.assertEqual(app.query_one("#encyclopedia-list").option_count, 1)
            self.assertIn("Café’s word counts", app.query_one("#encyclopedia-entry").source)
            field.value = "TF-IDF"
            field.value = "nothing like any title"
            field.value = "CAFE\u0301'S"
            await pilot.pause()
            self.assertEqual(app.query_one("#encyclopedia-list").option_count, 1)
            self.assertIn("Café’s word counts", app.query_one("#encyclopedia-entry").source)
            app.action_screen("methods")
            field = app.query_one("#methods-search")
            field.focus()
            field.value = "normalized with NFC"
            await pilot.pause()
            self.assertEqual(app.query_one("#methods-list").option_count, 1)
            self.assertIn("Word frequencies", app.query_one("#methods-entry").source)
            app.exit()

    async def test_filtered_genealogy_reveals_entries_outside_the_search(self):
        from sol.essence.encyclopedia import genealogy_rows
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.press("/")
            field = app.query_one("#encyclopedia-search")
            field.value = "Genealogy"
            await pilot.pause()
            self.assertEqual(app.query_one("#encyclopedia-list").option_count, 1)
            await pilot.press("enter", "enter")
            tree = app.query_one("#genealogy-map")
            self.assertIs(app.focused, tree)
            rows = genealogy_rows(app.catalog)
            index = next(index for index, row in enumerate(rows) if row["entry"] is not None)
            tree.highlighted = index
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(field.value, "")
            self.assertEqual(app.query_one("#encyclopedia-list").option_count, len(app.catalog["entries"]) + 1)
            entry = next(item for item in app.catalog["entries"] if item["id"] == rows[index]["entry"])
            self.assertIn(entry["title"], app.query_one("#encyclopedia-entry").source)
            self.assertIs(app.focused, app.query_one("#encyclopedia-detail"))
            self.assertFalse(tree.display)
            await pilot.press("escape")
            self.assertIs(app.focused, app.query_one("#encyclopedia-list"))
            app.exit()

    async def test_search_state_and_horizontal_study_choices_survive_resize(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context(), theme="paper")
        async with app.run_test(size=(120, 40)) as pilot:
            app.action_screen("methods")
            field = app.query_one("#methods-search")
            field.focus()
            field.value = "Sentence lengths"
            await pilot.pause()
            for width, height in ((80, 24), (40, 24), (120, 40)):
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                self.assertIs(app.focused, field)
                self.assertEqual(field.value, "Sentence lengths")
                self.assertEqual(app.query_one("#methods-list").option_count, 1)
                self.assertIn("Sentence lengths", app.query_one("#methods-entry").source)
                for selector in ("#methods-search", "#methods-count", "#methods-list", "#methods-detail", "#use-method"):
                    widget = app.query_one(selector)
                    self.assertGreater(widget.content_region.width, 0)
                    self.assertGreater(widget.content_region.height, 0)
                    self.assertLessEqual(widget.region.right, width)
                    self.assertLessEqual(widget.region.bottom, app.query_one("#layout-hint").region.y)
            app.action_screen("experiment")
            await pilot.press("down", "down", "enter")
            self.assertEqual(app.choice("study"), "tfidf")
            for width in (80, 40, 120):
                await pilot.resize_terminal(width, 24)
                await pilot.pause()
                choices = list(app.query("#study RadioButton"))
                self.assertEqual(app.choice("study"), "tfidf")
                if width < 100:
                    self.assertEqual(len({button.region.y for button in choices}), 1)
                    self.assertLessEqual(app.query_one("#study-panel").region.height, 3)
                for button in choices:
                    self.assertGreater(button.content_region.width, len(button.label.plain))
                    self.assertLessEqual(button.region.right, app.query_one("#study").content_region.right)
            await pilot.press("left", "enter")
            self.assertEqual(app.choice("study"), "sentences")
            app.exit()
