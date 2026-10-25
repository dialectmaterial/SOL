"""Study controls exercised through Textual on disposable invented text files."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fixtures_async import UIEventLoop
from sol.interchange.essence import textual_available


def file_context(state=None):
    return {"version": 1, "reference": {"reference": {"target_id": "bbbbbbbb-0000-4000-8000-000000000002"}},
            "cursor_offset": 0, "selection": None, "label": "Invented files", "corpus": "",
            "state_file": str(state) if state else None}


@unittest.skipUnless(textual_available(), "needs the essence extra (Textual)")
class StudySettingsTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-settings-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "state.json"
        self.target = self.root / "target.txt"
        self.reference = self.root / "reference.txt"
        self.target.write_text(" ".join(["zeta"] * 12 + ["alpha", "beta"] * 3 +
                                        ["targetonly"] * 2 + ["low"]), encoding="utf-8")
        self.reference.write_text(" ".join(["zeta"] + ["alpha", "beta"] * 3 +
                                           ["refonly"] * 4 + ["low"] * 10), encoding="utf-8")
        env = patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root / "data")})
        env.start()
        self.addCleanup(env.stop)

    async def run_study(self, app, pilot):
        app.action_menu()
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

    async def choose_sort(self, app, pilot, option):
        from sol.essence.tui.results import WordSort
        app.query_one("#frequencies").focus()
        await pilot.press("s")
        self.assertIsInstance(app.screen, WordSort)
        await pilot.press("home", *(["down"] * option))
        options = app.screen.query_one("#sort-options")
        self.assertEqual(options.highlighted, option)
        self.assertLessEqual(options.region.bottom, app.screen.query_one("#sort-dialog").content_region.bottom)
        if option == 14:
            self.assertGreater(options.scroll_y, 0)  # Last choice is visibly scrolled into view.
        await pilot.press("enter")
        await pilot.pause()
        self.assertNotIsInstance(app.screen, WordSort)

    async def test_tfidf_choice_reaches_engine_header_and_existing_artifact_not_state(self):
        from sol.essence import analyze_tfidf
        from sol.essence.tui.app import EssenceApp
        app = EssenceApp(file_context(self.state))
        with patch("sol.essence.analyze_tfidf", wraps=analyze_tfidf) as analyze:
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.press("t")
                self.assertTrue(app.query_one("#tfidf-settings").display)
                self.assertEqual(app.query_one("#top-n").value, "20")
                await pilot.press("f")
                app.query_one("#target-file").value = str(self.target)
                for value in ("2", "1", "1000"):
                    app.action_menu()
                    await pilot.press("n")
                    top = app.query_one("#top-n")
                    self.assertIs(app.focused, top)
                    top.value = value
                    await pilot.press("enter")  # Enter in a menu field runs the study.
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    self.assertEqual(analyze.call_args.kwargs, {"top_n": int(value)})
                    self.assertIn(f"top {value} terms each", str(app.query_one("#tfidf-metrics").render()))
                    self.assertIn(f"top {value} terms each", str(app.query_one("#tfidf-summary").render()))
                    self.assertEqual(app.last_count.study["top_n"], int(value))
                    artifact = json.loads(app.last_saved.read_text(encoding="utf-8"))
                    self.assertEqual(artifact["top_n"], int(value))
                    self.assertEqual(len(artifact["documents"][0]["top_terms"]), min(int(value), 5))
                await pilot.press("ctrl+q")
        # Investigation v1 has never stored study choices. Preserve its shape.
        self.assertEqual(json.loads(self.state.read_text()),
                         {"version": 1, "screen": "workspace", "origin": "bbbbbbbb-0000-4000-8000-000000000002"})
        app = EssenceApp(file_context(self.state))
        async with app.run_test() as pilot:
            self.assertEqual(app.query_one("#top-n").value, "20")
            await pilot.pause()
            app.exit()

    async def test_invalid_top_n_never_starts_a_worker_or_saves(self):
        from sol.essence.tui.app import EssenceApp
        app = EssenceApp(file_context(self.state))
        with patch("sol.essence.analyze_tfidf") as analyze:
            async with app.run_test(size=(100, 36)) as pilot:
                await pilot.press("t")
                for value in ("", "0", "-1", "1001", "2.5", "word", "1e2", "9" * 5000):
                    with self.subTest(value=value[:12]):
                        app.query_one("#top-n").value = value
                        await self.run_study(app, pilot)
                        self.assertIn("integer from 1 to 1,000", str(app.query_one("#status").render()))
                        self.assertIs(app.focused, app.query_one("#top-n"))
                        self.assertTrue(app.query_one("#menu").display)
                        self.assertEqual(app.count_serial, 0)
                        self.assertFalse(app.counting)
                analyze.assert_not_called()
                self.assertIsNone(app.last_count)
                self.assertFalse((self.root / "data").exists())
                # Hidden TF-IDF settings cannot block the other studies.
                app.query_one("#menu").focus()
                await pilot.press("w")
                self.assertFalse(app.query_one("#tfidf-settings").display)
                app.exit()

    async def test_every_comparison_column_both_directions_stable_ties_nulls_and_sources(self):
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp
        count = words.run(file_context(), "file", "file", target_file=self.target, reference_file=self.reference)
        original = json.dumps(count.comparison, sort_keys=True)
        engine_order = [row["word"] for row in count.comparison["rows"]]
        self.assertEqual(engine_order, ["zeta", "alpha", "beta", "targetonly", "low", "refonly"])
        orders = [
            ("alpha beta low refonly targetonly zeta", "zeta targetonly refonly low beta alpha"),
            ("refonly low targetonly alpha beta zeta", "zeta alpha beta targetonly low refonly"),
            ("refonly low targetonly alpha beta zeta", "zeta alpha beta targetonly low refonly"),
            ("targetonly zeta alpha beta refonly low", "low refonly alpha beta zeta targetonly"),
            ("targetonly zeta alpha beta refonly low", "low refonly alpha beta zeta targetonly"),
            ("low refonly alpha beta targetonly zeta", "zeta targetonly alpha beta refonly low"),
            ("low alpha beta zeta targetonly refonly", "zeta alpha beta low targetonly refonly"),
        ]
        app = EssenceApp(file_context())
        async with app.run_test(size=(80, 24)) as pilot:
            app.show_result(count, None)
            await pilot.pause()
            table = app.query_one("#frequencies")
            self.assertEqual([table.get_row_at(i)[0] for i in range(table.row_count)], engine_order)
            for column, pair in enumerate(orders):
                for descending, expected in enumerate(pair):
                    with self.subTest(column=column, descending=descending):
                        await self.choose_sort(app, pilot, 1 + column * 2 + descending)
                        self.assertEqual([table.get_row_at(i)[0] for i in range(table.row_count)], expected.split())
                        status = str(app.query_one("#sort-status").render())
                        self.assertIn(words.SORT_COLUMNS[column], status)
                        self.assertIn("descending" if descending else "ascending", status)
                        self.assertIn("undefined last", status)
                        # A sorted row navigates to that word, never its old row number.
                        await pilot.press(*(["up"] * table.row_count), "down", "enter")
                        self.assertIs(app.focused, app.query_one("#sources"))
                        view = app.query_one("#words-view")
                        self.assertTrue(view.shown_sources)
                        for item in view.shown_sources:
                            self.assertEqual(item["context"]["word"], expected.split()[1])
                        await pilot.press("escape")
                        self.assertIs(app.focused, table)
            self.assertIn("∅ reference", str(table.get_row_at(4)[-1]))
            self.assertIn("∅ target", str(table.get_row_at(5)[-1]))
            selected_word = table.get_row_at(table.cursor_row)[0]
            await pilot.resize_terminal(120, 40)
            await pilot.pause()
            await pilot.pause()
            view = app.query_one("#words-view")
            self.assertEqual(table.get_row_at(table.cursor_row)[0], selected_word)
            self.assertEqual(view.word_sort, (6, True))
            # Escape cancels a menu; engine order can be restored explicitly.
            await pilot.press("s", "home", "escape")
            self.assertEqual(view.word_sort, (6, True))
            await self.choose_sort(app, pilot, 0)
            self.assertEqual([table.get_row_at(i)[0] for i in range(table.row_count)], engine_order)
            self.assertEqual(view.word_sort, (None, False))
            self.assertNotIn("ascending", str(app.query_one("#sort-status").render()))
            self.assertEqual(json.dumps(count.comparison, sort_keys=True), original)
            app.exit()

    async def test_empty_side_rates_and_measures_stay_undefined_last_in_both_directions(self):
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp
        self.reference.write_text("", encoding="utf-8")
        app = EssenceApp(file_context())
        async with app.run_test(size=(80, 24)) as pilot:
            for empty_side in ("reference", "target"):
                count = words.run(file_context(), "file", "file",
                                  target_file=self.target if empty_side == "reference" else self.reference,
                                  reference_file=self.reference if empty_side == "reference" else self.target)
                app.show_result(count, None)
                await pilot.pause()
                table = app.query_one("#frequencies")
                expected = [row["word"] for row in count.comparison["rows"]]
                for column in (4 if empty_side == "reference" else 2, 5, 6):
                    for descending in (0, 1):
                        await self.choose_sort(app, pilot, 1 + column * 2 + descending)
                        self.assertEqual([table.get_row_at(i)[0] for i in range(table.row_count)], expected)
                        labels = [str(label.label).strip() for label in table.columns.values()]
                        rates = [index for index, label in enumerate(labels) if label == "/10k"]
                        cells = table.get_row_at(0)
                        self.assertEqual(str(cells[rates[1 if empty_side == "reference" else 0]]).strip(), "undefined")
                        self.assertIn(f"empty {empty_side}", str(cells[-1]))
            empty = words.run(file_context(), "file", "file", target_file=self.reference, reference_file=self.reference)
            app.show_result(empty, None)
            await self.choose_sort(app, pilot, 14)
            self.assertEqual(table.row_count, 0)
            self.assertEqual(app.query_one("#words-view").shown_sources, ())
            app.exit()

    async def test_sort_is_before_display_limit_exports_keep_exact_engine_content_and_new_runs_reset(self):
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp
        count = words.run(file_context(), "file", "file", target_file=self.target, reference_file=self.reference)
        baseline = {fmt: words.export(count, fmt, data_home=self.root / "baseline").read_bytes()
                    for fmt in ("csv", "tsv")}
        original = json.dumps(count.comparison, sort_keys=True)
        app = EssenceApp(file_context(self.state))
        with patch.object(words, "ROW_LIMIT", 3):
            async with app.run_test(size=(100, 36)) as pilot:
                app.show_result(count, None)
                await pilot.pause()
                for option in (13, 14):
                    await self.choose_sort(app, pilot, option)
                    table = app.query_one("#frequencies")
                    self.assertEqual(table.row_count, 3)
                    self.assertEqual(table.get_row_at(0)[0], "low" if option == 13 else "zeta")
                    for fmt in ("csv", "tsv"):
                        table.focus()
                        await pilot.press("e" if fmt == "csv" else "E")
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                        status = app.query_one("#result-status").content
                        self.assertTrue(status.startswith("Exported: "), status)
                        exported = Path(status.removeprefix("Exported: "))
                        self.assertEqual(exported.read_bytes(), baseline[fmt])
                self.assertEqual(json.dumps(count.comparison, sort_keys=True), original)
                new_count = words.run(file_context(), "file", "file", target_file=self.target,
                                      reference_file=self.reference)
                app.show_result(new_count, None)
                self.assertEqual(app.query_one("#words-view").word_sort, (None, False))
                app.exit()
