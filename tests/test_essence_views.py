"""ESSENCE's text drawings, and following the reader's position."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fixtures_async import UIEventLoop
from sol.essence.tui import views
from sol.interchange.essence import textual_available


class DrawingTests(unittest.TestCase):
    def test_bars_scale_in_eighths_and_stay_their_width(self):
        self.assertEqual(views.bar(10, 10, 4), "████")
        self.assertEqual(views.bar(5, 10, 4), "██  ")
        self.assertEqual(views.bar(1, 10, 4), "▍   ")  # 3.2 eighths, rounded to 3
        self.assertEqual(views.bar(0.001, 10, 4), "▏   ")  # Anything counted shows.
        for value, maximum in ((0, 10), (None, 10), (5, 0), (-1, 10)):
            self.assertEqual(views.bar(value, maximum, 4), "    ")
        self.assertEqual(views.bar(20, 10, 3), "███")  # Never wider than asked.
        self.assertEqual(views.bar(1, 1, 0), "")

    def test_diverging_bars_sit_either_side_of_zero(self):
        self.assertEqual(views.diverging(1.5), ("    ", "██  "))
        self.assertEqual(views.diverging(-3.0), ("████", "    "))
        self.assertEqual(views.diverging(-9.0), ("████", "    "))
        self.assertEqual(views.diverging(0.01), ("    ", "█   "))
        self.assertEqual(views.diverging(0), ("    ", "    "))
        self.assertIsNone(views.diverging(None))

    def test_dispersion_shows_where_and_how_many(self):
        self.assertEqual(views.dispersion([0.0, 0.05, 0.99], 4), "█··▄")
        self.assertEqual(views.dispersion([], 3), "···")
        self.assertEqual(views.dispersion([1.0], 2), "·█")  # The end falls in the last cell.
        self.assertEqual(views.dispersion([0.5], 0), "")

    def test_concordance_lines_align_the_node_and_mark_cuts(self):
        context = {"left": "…the movement of nothing to ", "word": "nothing", "right": ", and thereby…"}
        left, word, right = views.kwic(context, 12, 8)
        self.assertEqual(left, "… nothing to")
        self.assertEqual(word, "nothing")
        self.assertEqual(right, ", and t…")
        short = views.kwic({"left": "Being ", "word": "is", "right": " shine."}, 10, 20)
        self.assertEqual(short, ("     Being", "is", "shine."))
        changed = views.kwic(None, 6, 50)
        self.assertEqual(changed[0], "      ")
        self.assertIn("changed", changed[2])

    def test_context_sort_keys_read_outward_from_the_node(self):
        lines = [{"left": "pure being and ", "word": "x", "right": " nothing else"},
                 {"left": "Becoming, ", "word": "x", "right": " Being."},
                 None]
        by_left = sorted(lines, key=lambda line: views.context_key(line, "left"))
        self.assertEqual(by_left, [lines[0], lines[1], None])  # "and" before "becoming"
        by_right = sorted(lines, key=lambda line: views.context_key(line, "right"))
        self.assertEqual(by_right, [lines[1], lines[0], None])  # "being" before "nothing"

    def test_items_wrap_between_items_and_clip_to_fit(self):
        items = ["being 0.25", "nothing 0.21", "becoming 0.19", "determinate 0.11"]
        lines = views.wrap_items(items, 27, " · ")
        self.assertEqual(lines, ["being 0.25 · nothing 0.21 ·", "becoming 0.19 ·", "determinate 0.11"])
        self.assertTrue(all(len(line) <= 27 for line in lines))
        self.assertEqual(views.wrap_items(["extraordinarily-long 0.5"], 10, " · "), ["extraordi…"])
        self.assertEqual(views.wrap_items([], 10, " · "), [])
        self.assertEqual(views.clip("Preface to the first edition", 12), "Preface to…")
        self.assertEqual(views.clip("超長語超長語", 7), "超長語…")

    def test_histogram_rows_and_plurals(self):
        rows = [{"from": 1, "to": 10, "sentences": 4}, {"from": 11, "to": None, "sentences": 2}]
        self.assertEqual(views.histogram(rows, 4), [("1–10", "████", 4), ("11+", "██  ", 2)])
        self.assertEqual(views.plural(1, "word"), "1 word")
        self.assertEqual(views.plural(1200, "word"), "1,200 words")


class LongestSentenceTests(unittest.TestCase):
    def test_the_saved_twelve_come_first_then_the_rest_by_length(self):
        from sol.essence.tui import sentences
        lengths = [5, 40, 7, 33, 9, 21, 2, 30, 18, 27, 11, 25, 16, 3, 24, 8]
        study = {"sentences": [[0, index, index + 1, length] for index, length in enumerate(lengths)]}
        ranked = sorted(range(len(lengths)), key=lambda index: -lengths[index])
        study["longest"] = ranked[:12]
        self.assertEqual(sentences.longest(study), ranked)
        self.assertEqual(sentences.longest(study, 3), ranked[:3])
        # Equal lengths keep the source order.
        study = {"sentences": [[0, 0, 1, 4], [0, 1, 2, 9], [0, 2, 3, 4]], "longest": [1]}
        self.assertEqual(sentences.longest(study), [1, 0, 2])


class PositionTests(unittest.TestCase):
    def test_every_occurrence_counts_by_its_input(self):
        from sol.essence.tui import words

        class Count:
            study = {"target": {"inputs": [{}, {}, {}, {}]},
                     "frequencies": [{"target": {"locations": [[0, 2, 0, 3], [3, 1, 9, 12]]}}]}
        self.assertEqual(words.positions(Count, 0), [0.125, 0.125, 0.875])
        # Drawn, the last quarter shows too, though a listing might stop in the first.
        self.assertEqual(views.dispersion(words.positions(Count, 0), 4), "█··▄")


def context():
    return {"version": 1, "reference": {"reference": {"target_id": "bbbbbbbb-0000-4000-8000-000000000002"}},
            "cursor_offset": 0, "selection": None, "label": "First passage · p. 7", "corpus": "",
            "state_file": None}


@unittest.skipUnless(textual_available(), "needs the essence extra (Textual)")
class FollowReaderTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_this_passage_follows_the_reader_and_a_moved_result_offers_a_rerun(self):
        import sol.interchange.essence as exchange
        from sol.essence.tui import words
        from sol.essence.tui.app import EssenceApp

        position_file = Path(tempfile.mkdtemp(prefix="sol-essence-position-")) / "context.position"
        positions = []
        def read(path):
            self.assertEqual(Path(path), position_file)
            if not positions:
                raise OSError("not written yet")
            return positions[-1]
        moved = {"version": 1, "reference": {"reference": {"target_id": "cccccccc-0000-4000-8000-000000000003"}},
                 "cursor_offset": 12, "selection": None, "label": "Second passage · p. 9"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invented.txt"
            path.write_text("Alpha beta.", encoding="utf-8")
            count = words.run(context(), "file", "none", target_file=path)
        app = EssenceApp(context(), position_file=str(position_file))
        with patch.object(exchange, "read_position", side_effect=read, create=True):
            async with app.run_test(size=(86, 48)) as pilot:
                await pilot.pause(0.6)  # Nothing written yet: nothing changes.
                self.assertIn("First passage", str(app.query_one("#header").render()))
                app.last_run = ("words", "passage", "none", "", "", 20)
                app.show_result(count, None)
                positions.append(moved)
                await pilot.pause(0.8)
                header = str(app.query_one("#header").render())
                self.assertIn("Second passage · p. 9", header)
                self.assertIn("R reruns", header)
                # The next count uses the reader's new passage.
                self.assertEqual(app.context["reference"], moved["reference"])
                self.assertEqual(app.context["cursor_offset"], 12)
                self.assertEqual(app.context["corpus"], "")  # Launch fields stay.
                with patch.object(app, "count_words") as run:
                    await pilot.press("R")
                    run.assert_called_once()
                    self.assertEqual(run.call_args.args[1:3], ("passage", "none"))
                self.assertNotIn("R reruns", str(app.query_one("#header").render()))
                app.exit()

    async def test_a_book_wide_result_does_not_go_stale_when_reading_moves(self):
        import sol.interchange.essence as exchange
        from sol.essence.tui.app import EssenceApp

        moved = {"version": 1, "reference": {"reference": {"target_id": "cccccccc-0000-4000-8000-000000000003"}},
                 "cursor_offset": 0, "selection": None, "label": "Elsewhere · p. 90"}
        app = EssenceApp(context(), position_file="/invented/context.position")
        with patch.object(exchange, "read_position", return_value=moved, create=True):
            async with app.run_test(size=(86, 48)) as pilot:
                app.last_run = ("words", "book", "none", "", "", 20)
                await pilot.pause(0.8)
                header = str(app.query_one("#header").render())
                self.assertIn("Elsewhere · p. 90", header)
                self.assertNotIn("R reruns", header)
                app.exit()


if __name__ == "__main__":
    unittest.main()
