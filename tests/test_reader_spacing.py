"""Responsive reading gaps tested in the real toolkit layout, not host pixels.

These checks use an invented corpus and pipe input. They do not claim manual
inspection or physical-keyboard acceptance in any terminal emulator.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import importlib.util
import unittest

from fixtures_async import UIEventLoop

from sol.reader.actions import ReaderActions
from experiments.reader_surfaces.baseline import ReaderView
from test_reader_view import IDS, reader_book


OPTIONAL = (importlib.util.find_spec("prompt_toolkit") is not None
            and importlib.util.find_spec("markdown_it") is not None)


def spacing_book():
    book = reader_book()
    sentence = "Determinate thought and the Idea remain canonical source text. "
    plain = (sentence * 80).rstrip()
    markdown = (sentence.replace("thought", "*thought*").replace(
        "Idea", "**Idea**") * 80).rstrip()
    for index, passage in enumerate(book.passages):
        text = plain if index == 0 else "Another source passage remains readable."
        formatted = markdown if index == 0 else text
        book.passages[index] = replace(passage, text=text)
        book.canonical_records[passage.identifier].update(
            plain_text=text, markdown=formatted,
            content_sha256=sha256(formatted.encode()).hexdigest())
    return book


@unittest.skipUnless(OPTIONAL, "optional reader dependencies absent")
class ReaderSpacingTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, condition):
        deadline = asyncio.get_running_loop().time() + 3
        while not condition():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail("Reader did not reach its expected spacing state")
            await asyncio.sleep(.01)

    @asynccontextmanager
    async def running_view(self, *, book=None, rows=24, columns=100):
        from prompt_toolkit.data_structures import Size
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput

        class ResizableOutput(DummyOutput):
            def get_size(self):
                return Size(rows=self.rows, columns=self.columns)

        output = ResizableOutput()
        output.rows, output.columns = rows, columns
        actions = ReaderActions(book or spacing_book())
        actions.read(first=True)
        with create_pipe_input() as pipe:
            view = ReaderView(actions, input=pipe, output=output, emphasis="underline")
            view.application.ttimeoutlen = .01
            view.application.timeoutlen = .05
            task = asyncio.create_task(view.application.run_async())
            await self.wait_for(lambda: view.application.renderer._last_screen is not None)
            try:
                yield view, pipe, actions, output
            finally:
                if not task.done():
                    pipe.send_text("\x03")
                self.assertEqual(await asyncio.wait_for(task, 3), 0)

    async def rerender(self, view):
        counter = view.application.render_counter
        view.application.invalidate()
        await self.wait_for(lambda: view.application.render_counter > counter
                            and view.application.renderer._last_screen is not None)

    def assert_body_and_cursor_visible(self, view, output):
        screen = view.application.renderer._last_screen
        self.assertIn(view.body.window, screen.visible_windows)
        position = screen.visible_windows_to_write_positions[view.body.window]
        self.assertGreater(position.height, 0)
        self.assertLessEqual(position.ypos + position.height, output.rows)
        cursor = screen.get_cursor_position(view.body.window)
        self.assertGreaterEqual(cursor.x, position.xpos)
        self.assertLess(cursor.x, position.xpos + position.width)
        self.assertGreaterEqual(cursor.y, position.ypos)
        self.assertLess(cursor.y, position.ypos + position.height)

    @staticmethod
    def screen_text(view, output):
        screen = view.application.renderer._last_screen
        return "\n".join("".join(screen.data_buffer[row][column].char
                                 for column in range(output.columns))
                         for row in range(output.rows))

    async def test_normal_top_and_lead_gaps_are_responsive_and_column_aligned(self):
        async with self.running_view() as (view, pipe, actions, output):
            self.assertFalse(view.typography.degraded)
            for rows, gaps in ((12, (0, 0)), (18, (1, 1)),
                               (24, (2, 1)), (40, (3, 1))):
                with self.subTest(rows=rows):
                    output.rows = rows
                    await self.rerender(view)
                    self.assertEqual(view._reading_gaps(), gaps)
                    heading = view.heading_window.render_info
                    body = view.body.window.render_info
                    self.assertEqual(heading._y_offset, gaps[0])
                    self.assertEqual(body._y_offset, gaps[0] + 2 + gaps[1])
                    self.assertEqual(heading._x_offset, body._x_offset)
                    self.assertEqual(body.window_width, 72)
                    self.assertLessEqual(abs(body._x_offset - (output.columns - 72) // 2), 1)
                    self.assert_body_and_cursor_visible(view, output)
                    for index, gap in enumerate(gaps):
                        dimension = view._gap_height(index)
                        self.assertEqual((dimension.min, dimension.preferred, dimension.max),
                                         (0, gap, gap))

    async def test_context_and_focus_keep_the_measure_and_relinquish_lead_space(self):
        async with self.running_view() as (view, pipe, actions, output):
            for rows in (12, 18, 24, 40):
                with self.subTest(rows=rows):
                    output.rows = rows
                    view._focus_mode = False
                    view._context_visible = True
                    await self.rerender(view)
                    heading, context, body = (view.heading_window.render_info,
                                              view.context_window.render_info,
                                              view.body.window.render_info)
                    self.assertEqual(heading._x_offset, body._x_offset)
                    self.assertEqual(context._x_offset, body._x_offset)
                    self.assertGreaterEqual(body._y_offset,
                                            context._y_offset + context.window_height)
                    self.assertEqual(body.window_width, 72)
                    self.assert_body_and_cursor_visible(view, output)
                    view._context_visible = False
                    view._focus_mode = True
                    await self.rerender(view)
                    top, lead = view._reading_gaps()
                    self.assertEqual(lead, 0)
                    self.assertEqual(view.body.window.render_info._y_offset, top)
                    self.assertNotIn(view.heading_window,
                                     view.application.renderer._last_screen.visible_windows)
                    self.assert_body_and_cursor_visible(view, output)

    async def test_active_panels_consume_padding_before_reading_room(self):
        async with self.running_view() as (view, pipe, actions, output):
            self.assertEqual(view._reading_gaps(), (2, 1))
            self.assertTrue(view._act(lambda: actions.search("source", (), limit=20),
                                      project=False))
            self.assertEqual(len(view._state.results), 3)
            view._context_visible = view._help_visible = True
            view._searching = view._results_visible = True
            for rows in (12, 18, 24, 40):
                with self.subTest(rows=rows):
                    output.rows = rows
                    await self.rerender(view)
                    if rows <= 24:
                        self.assertEqual(view._reading_gaps(), (0, 0))
                    else:
                        self.assertEqual(view._reading_gaps(), (3, 1))
                    # A twelve-row window cannot fit all existing fixed help
                    # and input chrome. Do not mistake stale render_info for
                    # a freshly visible body in that already-known case.
                    if rows >= 18:
                        self.assert_body_and_cursor_visible(view, output)
            output.rows = 24
            view._context_visible = view._help_visible = False
            view._searching = view._results_visible = False
            await self.rerender(view)
            self.assertEqual(view._reading_gaps(), (2, 1))
            self.assertEqual(view.heading_window.render_info._y_offset, 2)
            self.assert_body_and_cursor_visible(view, output)

    async def test_vertical_resize_preserves_styled_selection_and_source_identity(self):
        book = spacing_book()
        records = deepcopy(book.canonical_records)
        async with self.running_view(book=book) as (view, pipe, actions, output):
            start, end = 1490, 1580
            self.assertTrue(view._act(lambda: actions.select_span(start, end)))
            await self.rerender(view)
            selection = actions.selection
            source = book.passages[0].text
            source_layout = view._source_positions()
            for rows in (40, 12, 24, 18):
                with self.subTest(rows=rows):
                    output.rows = rows
                    await self.rerender(view)
                    self.assertEqual(actions.snapshot().current.identifier, IDS[0])
                    self.assertEqual(actions.cursor_offset, end)
                    self.assertEqual(actions.selection, selection)
                    self.assertEqual(selection.text, source[start:end])
                    self.assertEqual(view.body.text, source)
                    self.assertEqual(view.body.buffer.cursor_position, end)
                    self.assertEqual(list(view.body.buffer.document.selection_ranges()),
                                     [(start, end)])
                    self.assertEqual(view._source_positions(), source_layout)
                    self.assertEqual(book.canonical_records, records)
                    self.assert_body_and_cursor_visible(view, output)

    async def test_half_page_uses_body_height_after_top_and_lead_spacing(self):
        async with self.running_view() as (view, pipe, actions, output):
            for rows in (12, 18, 24, 40):
                with self.subTest(rows=rows):
                    output.rows = rows
                    view._cursor_action(lambda: actions.set_cursor(0))
                    await self.rerender(view)
                    height = view.body.window.render_info.window_height
                    layout = view._source_positions()
                    pipe.send_text("\x04")
                    await self.wait_for(lambda: actions.cursor_offset > 0)
                    await self.rerender(view)
                    self.assertEqual(layout[actions.cursor_offset][0], max(1, height // 2))
                    self.assert_body_and_cursor_visible(view, output)
                    pipe.send_text("\x15")
                    await self.wait_for(lambda: actions.cursor_offset == 0)

    async def test_focus_warnings_remain_visible_at_small_heights(self):
        book = spacing_book()
        book.passages[0] = replace(book.passages[0], transcription_status="needs_review")
        async with self.running_view(book=book, columns=40) as (view, pipe, actions, output):
            view._focus_mode = True
            view.status = "Review the source attribution before reusing this quotation."
            for rows in (12, 18, 24, 40):
                with self.subTest(rows=rows):
                    output.rows = rows
                    await self.rerender(view)
                    self.assertEqual(view._reading_gaps()[1], 0)
                    self.assertIn("[source review]", self.screen_text(view, output))
                    self.assertIn("Review the source attribution",
                                  self.screen_text(view, output).replace("\n", ""))
                    self.assert_body_and_cursor_visible(view, output)


if __name__ == "__main__":
    unittest.main()
