"""Comfortable reading, semantic selection and Vim bindings in a real layout."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from hashlib import sha256
import importlib.util
import unittest
from unittest.mock import patch

from sol.reader.actions import ReaderActions
from sol.terminal.reader import ReaderView, emphasis_style
from test_reader_view import IDS, reader_book


class EmphasisFallbackTests(unittest.TestCase):
    def test_unknown_terminal_has_deterministic_visible_fallback(self):
        with patch.dict("os.environ", {"TERM": "unknown-terminal"}, clear=True):
            self.assertEqual(emphasis_style(), "underline")
            self.assertEqual(emphasis_style("italic"), "italic")
        with patch.dict("os.environ", {"TERM": "xterm-kitty"}, clear=True):
            self.assertEqual(emphasis_style(), "italic")
            self.assertEqual(emphasis_style("underline"), "underline")
        with self.assertRaises(ValueError):
            emphasis_style("plain")


@unittest.skipUnless(importlib.util.find_spec("prompt_toolkit") and
                     importlib.util.find_spec("markdown_it"), "optional reader dependencies absent")
class ReaderExperienceTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, condition):
        deadline = asyncio.get_running_loop().time() + 2
        while not condition():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail("reader did not reach its expected state")
            await asyncio.sleep(.01)

    @asynccontextmanager
    async def view(self, *, book=None, width=None, emphasis="underline", workspace=None):
        from prompt_toolkit.data_structures import Size
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput

        class ResizableOutput(DummyOutput):
            columns = 160
            rows = 24
            def get_size(self):
                return Size(rows=self.rows, columns=self.columns)

        actions = ReaderActions(book or reader_book(), workspace)
        actions.read(first=True)
        output = ResizableOutput()
        with create_pipe_input() as pipe:
            measure = {} if width is None else {"width": width}
            view = ReaderView(actions, input=pipe, output=output, emphasis=emphasis, **measure)
            view.application.ttimeoutlen = .01
            view.application.timeoutlen = .05
            task = asyncio.create_task(view.application.run_async())
            await self.wait_for(lambda: view.body.window.render_info is not None)
            try:
                yield view, pipe, actions, output
            finally:
                if not task.done():
                    pipe.send_text("\x03")
                self.assertEqual(await asyncio.wait_for(task, 2), 0)

    async def test_reading_measure_is_centered_and_does_not_change_with_context(self):
        async with self.view(width=64) as (view, pipe, actions, output):
            info = view.body.window.render_info
            self.assertEqual(info.window_width, 64)
            self.assertLessEqual(abs(info._x_offset - (160 - 64) // 2), 1)
            self.assertFalse(view._context_visible)
            pipe.send_text("c")
            await self.wait_for(lambda: view._context_visible)
            self.assertEqual(view.body.window.render_info.window_width, 64)
            self.assertIn("Printed 1 | PDF 10", view._header())
            pipe.send_text("f")
            await self.wait_for(lambda: view._focus_mode)
            self.assertFalse(view._context_visible)
            self.assertEqual(view.body.window.render_info.window_width, 64)

    async def test_default_measure_and_primary_context_share_one_reading_column(self):
        async with self.view() as (view, pipe, actions, output):
            self.assertEqual(view.reading_width, 72)
            for columns in (160, 100, 72, 40, 20):
                output.columns = columns
                view.application.invalidate()
                await self.wait_for(lambda: view.body.window.render_info.window_width == min(72, columns)
                                    and abs(view.body.window.render_info._x_offset -
                                            (columns - min(72, columns)) // 2) <= 1)
                body = view.body.window.render_info
                heading = view.heading_window.render_info
                self.assertEqual(heading._x_offset, body._x_offset)
                self.assertEqual(heading.window_width, body.window_width)
                self.assertLessEqual(abs(body._x_offset - (columns - body.window_width) // 2), 1)
                self.assertLessEqual(view._toolkit["get_cwidth"](view._footer_text()), columns)
            self.assertNotIn("/quality.txt", "".join(text for _, text in view._document_heading()))
            pipe.send_text("c")
            await self.wait_for(lambda: view._context_visible and view.context_window.render_info is not None)
            self.assertEqual(view.context_window.render_info._x_offset, view.body.window.render_info._x_offset)
            self.assertIn("Scope: work", view._header())

    async def test_cached_results_do_not_reappear_when_returning_to_reading(self):
        async with self.view() as (view, pipe, actions, output):
            pipe.send_text("/Beta\r")
            await self.wait_for(lambda: view.application.layout.has_focus(view.results))
            self.assertTrue(view._results_visible)
            pipe.send_text("\r")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[1])
            self.assertFalse(view._results_visible)
            self.assertTrue(actions.results)
            pipe.send_text("}")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[2])
            self.assertFalse(view._results_visible)
            pipe.send_text("\x1b[1;3D")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[1])
            self.assertFalse(view._results_visible)
            self.assertEqual(actions.search_query, "Beta")
            pipe.send_text("/")
            await self.wait_for(lambda: view.application.layout.has_focus(view.search_input))
            self.assertEqual(view.search_input.text, "Beta")
            pipe.send_text("\r")
            await self.wait_for(lambda: view.application.layout.has_focus(view.results))
            self.assertTrue(view._results_visible)

    async def test_narrow_focus_view_keeps_review_and_typography_warnings_visible(self):
        book = reader_book()
        book.passages[0] = replace(book.passages[0], transcription_status="needs_review")
        # An intentionally mismatched projection must warn, not guess emphasis.
        book.canonical_records[IDS[0]]["markdown"] = "*Different source*"
        async with self.view(book=book) as (view, pipe, actions, output):
            output.columns = 20
            view.application.invalidate()
            await self.wait_for(lambda: view.body.window.render_info.window_width == 20)
            pipe.send_text("f")
            await self.wait_for(lambda: view._focus_mode)
            self.assertTrue(view.typography.degraded)
            self.assertTrue(view._status_text().startswith("[source review] | Typography fallback"))
            self.assertEqual(view._status_height().preferred, 3)
            await self.wait_for(lambda: "[source review]" in self.screen_text(view))
            self.assertIn("Typography fallback", self.screen_text(view).replace("\n", ""))
            self.assertEqual(view.body.text, book.passages[0].text)

    @staticmethod
    def screen_text(view):
        screen = view.application.renderer._last_screen
        size = view.application.output.get_size()
        return "\n".join("".join(screen.data_buffer[row][column].char
                                 for column in range(size.columns))
                         for row in range(size.rows))

    async def test_vim_selection_survives_resize_without_changing_source_identity(self):
        async with self.view() as (view, pipe, actions, output):
            pipe.send_text("vllll")
            await self.wait_for(lambda: actions.selection is not None and actions.selection.end == 4)
            selected = actions.selection
            source = view.body.text
            output.columns = 30
            view.application.invalidate()
            await self.wait_for(lambda: view.body.window.render_info.window_width == 30)
            self.assertEqual(actions.selection, selected)
            self.assertEqual(view.body.text, source)
            self.assertEqual(actions.cursor_offset, 4)
            pipe.send_text("hh")
            await self.wait_for(lambda: actions.cursor_offset == 2)
            self.assertEqual(actions.selection.text, source[:2])
            pipe.send_text("\x1b")
            await self.wait_for(lambda: actions.selection is None)

    async def test_emphasis_is_rendered_over_exact_plain_source_not_markup(self):
        book = reader_book()
        plain = "Being is nothing; the Idea is the truth."
        markdown = "*Being* is **nothing**; the *Idea* is the truth."
        book.passages[0] = replace(book.passages[0], text=plain)
        book.canonical_records[IDS[0]].update(markdown=markdown, plain_text=plain,
            content_sha256=sha256(markdown.encode()).hexdigest())
        async with self.view(book=book) as (view, pipe, actions, output):
            self.assertEqual(view.body.text, plain)
            self.assertFalse(view.typography.degraded)
            fragments = view.body.control.lexer.lex_document(view.body.buffer.document)(0)
            self.assertEqual("".join(text for _, text in fragments), plain)
            self.assertTrue(all("class:source.emphasis" in style for style, _ in fragments[:5]))
            start = plain.index("nothing")
            self.assertTrue(all("class:source.strong" in style for style, _ in fragments[start:start + 7]))
            pipe.send_text("vlllll")
            await self.wait_for(lambda: actions.selection is not None and actions.selection.end == 5)
            self.assertEqual(actions.selection.text, "Being")

    async def test_vim_scope_paragraph_and_search_movement_are_distinct(self):
        async with self.view() as (view, pipe, actions, output):
            pipe.send_text("G")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[-1])
            self.assertEqual(actions.cursor_offset, len(actions.snapshot().current.text))
            pipe.send_text("gg")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[0])
            self.assertEqual(actions.cursor_offset, 0)
            pipe.send_text("}")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[1])
            pipe.send_text("{")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[0])
            pipe.send_text("/source\r")
            await self.wait_for(lambda: view.application.layout.has_focus(view.results))
            pipe.send_text("\r")
            await self.wait_for(lambda: view.application.layout.has_focus(view.body))
            pipe.send_text("n")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[0])
            self.assertEqual(len(actions.snapshot().results), 1)

    async def test_half_page_uses_half_the_visible_height_and_keeps_codepoint_cursor(self):
        book = reader_book()
        plain = "abcdefgh " * 400
        book.passages[0] = replace(book.passages[0], text=plain)
        book.canonical_records[IDS[0]].update(markdown=plain, plain_text=plain,
            content_sha256=sha256(plain.encode()).hexdigest())
        async with self.view(book=book, width=40) as (view, pipe, actions, output):
            rows = view.body.window.render_info.window_height
            pipe.send_text("\x04")
            await self.wait_for(lambda: actions.cursor_offset > 0)
            self.assertEqual(view._source_positions()[actions.cursor_offset][0], rows // 2)
            pipe.send_text("\x15")
            await self.wait_for(lambda: actions.cursor_offset == 0)
            pipe.send_text("jk")
            await self.wait_for(lambda: actions.cursor_offset == 0)
            self.assertEqual(view.body.text, plain)

    async def test_review_warning_survives_focus_mode(self):
        book = reader_book()
        book.passages[0] = replace(book.passages[0], transcription_status="needs_review")
        async with self.view(book=book) as (view, pipe, actions, output):
            pipe.send_text("f")
            await self.wait_for(lambda: view._focus_mode)
            self.assertTrue(view._needs_review())
            self.assertIn("[source review]", view._status_text())

    async def test_viewport_anchor_resolves_to_visible_source_with_wide_and_combining_text(self):
        book = reader_book()
        plain = "A界e\u0301 text " * 400
        book.passages[0] = replace(book.passages[0], text=plain)
        book.canonical_records[IDS[0]].update(markdown=plain, plain_text=plain,
            content_sha256=sha256(plain.encode()).hexdigest())
        async with self.view(book=book, width=40) as (view, pipe, actions, output):
            pipe.send_text("\x04\x04\x04")
            await self.wait_for(lambda: actions.snapshot().viewport_offset is not None and
                                actions.snapshot().viewport_offset > 0)
            info = view.body.window.render_info
            visible = [column for (line, column), (row, _) in info._rowcol_to_yx.items()
                       if line == 0 and row == info._y_offset]
            self.assertTrue(visible)
            self.assertEqual(actions.snapshot().viewport_offset, min(visible))
            cursor = actions.cursor_offset
            viewport = actions.snapshot().viewport_offset
            view._project_body()
            view.application.invalidate()
            await self.wait_for(lambda: view.body.window.render_info.window_width == 40)
            self.assertEqual(actions.cursor_offset, cursor)
            self.assertEqual(actions.snapshot().viewport_offset, viewport)

    async def test_save_refusal_does_not_exit_or_overwrite_context(self):
        async with self.view() as (view, pipe, actions, output):
            pipe.send_text("ll")
            await self.wait_for(lambda: actions.cursor_offset == 2)
            with patch.object(actions, "save_position", side_effect=RuntimeError("another reader updated this workspace")):
                pipe.send_text("\x11")
                await self.wait_for(lambda: "another reader" in view.status)
                self.assertTrue(view.application.is_running)
                self.assertEqual(actions.cursor_offset, 2)


if __name__ == "__main__":
    unittest.main()
