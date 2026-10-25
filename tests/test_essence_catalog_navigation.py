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
        from sol.essence.tui.reference import ReferenceScreen

        app = EssenceApp(context(), theme="night")
        async with app.run_test(size=(120, 40)) as pilot:
            base = app.screen
            base.query_one("#target-file").value = "/invented/retained.txt"
            await pilot.press("M", "2", "/")
            ref = app.screen
            field = ref.query_one("#methods-search")
            self.assertIs(app.focused, field)
            field.value = "tfidf"
            await pilot.pause()
            listing = ref.query_one("#methods-list")
            self.assertEqual(listing.option_count, 1)
            self.assertEqual(listing.highlighted, 0)
            self.assertIn("TF-IDF", ref.query_one("#methods-entry").source)
            await pilot.press("enter", "enter")
            self.assertIs(app.focused, ref.query_one("#methods-detail"))
            ref.query_one("#use-method").focus()
            await pilot.press("enter")
            await pilot.pause()
            self.assertNotIsInstance(app.screen, ReferenceScreen)
            self.assertEqual(base.query_one("#menu").study, "tfidf")
            self.assertEqual(base.query_one("#target-file").value, "/invented/retained.txt")
            self.assertIsNone(app.last_count)
            # The search is where it was left.
            await pilot.press("M", "2", "ctrl+f")
            self.assertIs(app.screen, ref)
            self.assertEqual(field.value, "tfidf")
            field.value = "Verify a saved study"
            await pilot.pause()
            self.assertEqual(listing.option_count, 1)
            self.assertIn("sol essence check", ref.query_one("#methods-entry").source)
            self.assertTrue(ref.query_one("#use-method").disabled)
            self.assertIn("CLI", str(ref.query_one("#method-availability").render()))
            field.value = "no matching method [bold]"
            await pilot.pause()
            self.assertEqual(listing.option_count, 0)
            self.assertIn("No matches", ref.query_one("#methods-entry").source)
            self.assertTrue(ref.query_one("#use-method").disabled)
            self.assertEqual(str(ref.query_one("#methods-count").render()), f"0 / {len(app.methods['entries'])}")
            await pilot.press("enter")
            self.assertIs(app.focused, field)
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(listing.option_count, len(app.methods["entries"]))
            self.assertFalse(ref.query_one("#use-method").disabled)
            self.assertIs(app.focused, field)
            await pilot.press("escape")
            self.assertIs(app.focused, listing)
            # From the list, Escape goes back to the study.
            await pilot.press("escape")
            self.assertNotIsInstance(app.screen, ReferenceScreen)
            app.exit()

    async def test_search_description_unicode_and_rapid_edits_keep_the_latest_entry(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        # A synthetic accented title exercises the same local matching as normal entries.
        app.catalog["entries"][0]["title"] = "Café’s word counts"
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("M", "/")
            ref = app.screen
            field = ref.query_one("#encyclopedia-search")
            field.value = "CAFE\u0301’S"
            await pilot.pause()
            self.assertEqual(ref.query_one("#encyclopedia-list").option_count, 1)
            self.assertIn("Café’s word counts", ref.query_one("#encyclopedia-entry").source)
            field.value = "TF-IDF"
            field.value = "nothing like any title"
            field.value = "CAFE\u0301'S"
            await pilot.pause()
            self.assertEqual(ref.query_one("#encyclopedia-list").option_count, 1)
            self.assertIn("Café’s word counts", ref.query_one("#encyclopedia-entry").source)
            ref.action_tab("methods")
            field = ref.query_one("#methods-search")
            field.focus()
            field.value = "normalized with NFC"
            await pilot.pause()
            self.assertEqual(ref.query_one("#methods-list").option_count, 1)
            self.assertIn("Word frequencies", ref.query_one("#methods-entry").source)
            app.exit()

    async def test_filtered_genealogy_reveals_entries_outside_the_search(self):
        from sol.essence.encyclopedia import genealogy_rows
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.press("M", "/")
            ref = app.screen
            field = ref.query_one("#encyclopedia-search")
            field.value = "Genealogy"
            await pilot.pause()
            self.assertEqual(ref.query_one("#encyclopedia-list").option_count, 1)
            await pilot.press("enter", "enter")
            tree = ref.query_one("#genealogy-map")
            self.assertIs(app.focused, tree)
            rows = genealogy_rows(app.catalog)
            index = next(index for index, row in enumerate(rows) if row["entry"] is not None)
            tree.highlighted = index
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(field.value, "")
            self.assertEqual(ref.query_one("#encyclopedia-list").option_count, len(app.catalog["entries"]) + 1)
            entry = next(item for item in app.catalog["entries"] if item["id"] == rows[index]["entry"])
            self.assertIn(entry["title"], ref.query_one("#encyclopedia-entry").source)
            self.assertIs(app.focused, ref.query_one("#encyclopedia-detail"))
            self.assertFalse(tree.display)
            await pilot.press("escape")
            self.assertIs(app.focused, ref.query_one("#encyclopedia-list"))
            app.exit()

    async def test_search_state_and_menu_choices_survive_resize(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context(), theme="paper")
        async with app.run_test(size=(120, 40)) as pilot:
            app.action_reference("methods")
            await pilot.pause()
            ref = app.screen
            field = ref.query_one("#methods-search")
            field.focus()
            field.value = "Sentence lengths"
            await pilot.pause()
            for width, height in ((80, 24), (40, 24), (120, 40)):
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                self.assertIs(app.focused, field)
                self.assertEqual(field.value, "Sentence lengths")
                self.assertEqual(ref.query_one("#methods-list").option_count, 1)
                self.assertIn("Sentence lengths", ref.query_one("#methods-entry").source)
                for selector in ("#methods-search", "#methods-count", "#methods-list", "#methods-detail", "#use-method"):
                    widget = ref.query_one(selector)
                    self.assertGreater(widget.content_region.width, 0)
                    self.assertGreater(widget.content_region.height, 0)
                    self.assertLessEqual(widget.region.right, width)
                    self.assertLessEqual(widget.region.bottom, height - 1)
            # Escape clears the search, then returns to the list, then to the study.
            await pilot.press("escape", "escape", "escape")
            menu = app.query_one("#menu")
            self.assertIs(app.focused, menu)
            await pilot.press("t")
            for width in (80, 40, 120):
                await pilot.resize_terminal(width, 24)
                await pilot.pause()
                self.assertEqual(menu.study, "tfidf")
                self.assertLessEqual(app.query_one("#menu-choices").region.right, width)
            await pilot.press("s")
            self.assertEqual(menu.study, "sentences")
            app.exit()
