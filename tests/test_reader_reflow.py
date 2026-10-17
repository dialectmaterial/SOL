"""Real-toolkit reflow checks; terminal names here are environments, not live hosts.

The source fixture is invented and workspaces are genuine schema-3 temporary
databases. Pipes exercise bindings and toolkit rendering without claiming that a
person inspected Alacritty or Kitty.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from hashlib import sha256
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.core.paths import display_path, resolve_path
from sol.reader.actions import ReaderActions
from experiments.reader_surfaces.baseline import ReaderView
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace
from test_workspace_reader import CORPUS_ID, IDS, invented_book


OPTIONAL = (importlib.util.find_spec("prompt_toolkit") is not None
            and importlib.util.find_spec("markdown_it") is not None)


def styled_book():
    book = invented_book()
    sentence = ("Determinate thought remains itself in another; α and 界 and e\u0301 "
                "are source characters, not visual columns. ")
    markdown_sentence = sentence.replace("thought", "*thought*").replace(
        "another", "**another**").replace("source characters", "`source characters`")
    plain, markdown = sentence * 40, (markdown_sentence * 40).rstrip()
    # The contract strips the Markdown paragraph's surrounding whitespace.
    plain = plain.rstrip()
    book.passages[0] = replace(book.passages[0], text=plain)
    book.canonical_records[IDS[0]].update(
        plain_text=plain, markdown=markdown,
        content_sha256=sha256(markdown.encode()).hexdigest())
    return book


@unittest.skipUnless(OPTIONAL, "optional reader dependencies absent")
class ReaderReflowTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, condition):
        deadline = asyncio.get_running_loop().time() + 3
        while not condition():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail("Reader did not reach the expected reflow state")
            await asyncio.sleep(.01)

    @asynccontextmanager
    async def running_view(self, actions, *, columns=100, width=120):
        from prompt_toolkit.data_structures import Size
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput

        class ResizableOutput(DummyOutput):
            def __init__(self, columns):
                self.columns = columns
            def get_size(self):
                return Size(rows=22, columns=self.columns)

        output = ResizableOutput(columns)
        with create_pipe_input() as pipe:
            view = ReaderView(actions, input=pipe, output=output, width=width)
            view.application.ttimeoutlen = .01
            view.application.timeoutlen = .05
            task = asyncio.create_task(view.application.run_async())
            await self.wait_for(lambda: view.body.window.render_info is not None)
            try:
                yield view, pipe, output, task
            finally:
                if not task.done():
                    pipe.send_text("\x03")
                self.assertEqual(await asyncio.wait_for(task, 3), 0)

    async def resize(self, view, output, columns):
        output.columns = columns
        view.application.invalidate()
        await self.wait_for(lambda: view.body.window.render_info.window_width == columns)

    def assert_cursor_visible(self, view):
        info = view.body.window.render_info
        point = info.cursor_position
        self.assertGreaterEqual(point.x, 0)
        self.assertLess(point.x, info.window_width)
        self.assertGreaterEqual(point.y, 0)
        self.assertLess(point.y, info.window_height)

    async def test_source_and_styled_selection_survive_40_72_100_column_reflow(self):
        book = styled_book()
        actions = ReaderActions(book)
        first = actions.read(first=True)
        source, record = first.text, dict(book.canonical_records[IDS[0]])
        async with self.running_view(actions) as (view, pipe, output, task):
            self.assertFalse(view.typography.degraded)
            start = source.index("thought")
            end = source.index("source characters") + len("source characters")
            view._cursor_action(lambda: actions.set_cursor(start))
            pipe.send_text("v" + "l" * (end - start))
            await self.wait_for(lambda: actions.selection is not None
                                and actions.selection.end == end)
            selected, cursor = actions.selection, actions.cursor_offset
            self.assertEqual(selected.text, source[start:end])
            geometry = []
            for columns in (40, 72, 100):
                await self.resize(view, output, columns)
                positions = view._source_positions()
                geometry.append(positions[cursor])
                self.assertEqual(len(positions), len(source) + 1)
                self.assertEqual(actions.selection, selected)
                self.assertEqual(actions.cursor_offset, cursor)
                self.assertEqual(view.body.buffer.cursor_position, cursor)
                self.assertEqual(view.body.text, source)
                self.assertEqual(book.canonical_records[IDS[0]], record)
                self.assertEqual(list(view.body.buffer.document.selection_ranges()),
                                 [(start, end)])
                self.assert_cursor_visible(view)
            self.assertGreater(len(set(geometry)), 1)
            pipe.send_text("h")
            await self.wait_for(lambda: actions.cursor_offset == cursor - 1)
            self.assertEqual(actions.selection.text, source[start:cursor - 1])

    async def test_visual_motion_and_half_pages_use_reflowed_source_geometry(self):
        book = styled_book()
        actions = ReaderActions(book)
        first = actions.read(first=True)
        async with self.running_view(actions) as (view, pipe, output, task):
            for columns in (40, 72, 100):
                await self.resize(view, output, columns)
                view._cursor_action(lambda: actions.set_cursor(0))
                layout = view._source_positions()
                pipe.send_text("j")
                await self.wait_for(lambda: actions.cursor_offset > 0)
                self.assertEqual(layout[actions.cursor_offset][0], layout[0][0] + 1)
                pipe.send_text("k")
                await self.wait_for(lambda: actions.cursor_offset == 0)
                height = view.body.window.render_info.window_height
                pipe.send_text("\x04")
                await self.wait_for(lambda: actions.cursor_offset > 0)
                self.assertEqual(layout[actions.cursor_offset][0],
                                 layout[0][0] + max(1, height // 2))
                pipe.send_text("\x15")
                await self.wait_for(lambda: actions.cursor_offset == 0)
                self.assertEqual(view.body.text, first.text)

    async def test_history_return_restores_selected_source_at_a_new_reading_measure(self):
        book = styled_book()
        actions = ReaderActions(book)
        first = actions.read(first=True)
        async with self.running_view(actions) as (view, pipe, output, task):
            start, end = 1210, 1299
            view._cursor_action(lambda: actions.set_cursor(start))
            pipe.send_text("v" + "l" * (end - start))
            await self.wait_for(lambda: actions.selection is not None
                                and actions.selection.end == end)
            selected = actions.selection
            pipe.send_text("}")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[1])
            await self.resize(view, output, 40)
            pipe.send_text("\x1b[1;3D")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[0])
            self.assertEqual(actions.cursor_offset, end)
            self.assertEqual(view.body.buffer.cursor_position, end)
            self.assertEqual(actions.selection, selected)
            self.assertEqual(actions.selection.text, first.text[start:end])
            self.assertEqual(list(view.body.buffer.document.selection_ranges()), [(start, end)])
            self.assertEqual(view.body.window.render_info.window_width, 40)
            self.assertEqual(view.body.text, first.text)
            self.assert_cursor_visible(view)

    async def test_resize_resets_preferred_visual_column_before_next_motion(self):
        from sol.reader.navigation import vertical_offset
        actions = ReaderActions(styled_book())
        source = actions.read(first=True).text
        async with self.running_view(actions) as (view, pipe, output, task):
            view._cursor_action(lambda: actions.set_cursor(60))
            wide = view._source_positions()
            wide_offset, old_column = vertical_offset(wide, 60, 1)
            pipe.send_text("j")
            await self.wait_for(lambda: actions.cursor_offset == wide_offset)
            await self.resize(view, output, 40)
            narrow = view._source_positions()
            self.assertEqual(actions.cursor_offset, wide_offset)
            expected, new_column = vertical_offset(narrow, wide_offset, 1)
            stale, _ = vertical_offset(narrow, wide_offset, 1, old_column)
            self.assertNotEqual(expected, stale, "fixture must expose a stale preferred column")
            pipe.send_text("j")
            await self.wait_for(lambda: actions.cursor_offset == expected)
            self.assertEqual(actions._preferred_column, new_column)
            self.assertEqual(view.body.text, source)
            self.assert_cursor_visible(view)

    async def test_quit_reopen_preserves_semantic_position_across_terminal_environments(self):
        book = styled_book()
        provenance = {key: book.corpus_manifest[key] for key in ("edition", "source")}
        with tempfile.TemporaryDirectory(prefix="sol-reader-reflow-") as directory:
            path = Path(directory) / "reading.sqlite3"
            with patch.dict("os.environ", {"TERM": "alacritty"}, clear=True):
                store = Workspace(path, CORPUS_ID, provenance, actor="Ada")
                self.addCleanup(store.close)
                adapter = WorkspaceReader(book, store, "Ada", resolve_path, display_path,
                                          lambda *args, **kwargs: None)
                actions = ReaderActions(book, adapter)
                actions.read(first=True)
                self.assertEqual(store.schema_version, 3)
                async with self.running_view(actions, columns=100) as (view, pipe, output, task):
                    pipe.send_text("\x04\x04\x04")
                    await self.wait_for(lambda: actions.cursor_offset > 800
                                        and actions.snapshot().viewport_offset is not None)
                    cursor = actions.cursor_offset
                    pipe.send_text("\x11")
                    self.assertEqual(await asyncio.wait_for(task, 3), 0)
                saved = store.get_state()
                self.assertEqual(saved["current_id"], IDS[0])
                self.assertEqual(saved["position"]["cursor_offset"], cursor)
                self.assertFalse({"row", "column", "width", "terminal"} & saved["position"].keys())
                store.close()
            for term, columns in (("xterm-kitty", 40), ("alacritty", 72)):
                with self.subTest(term=term, columns=columns), \
                        patch.dict("os.environ", {"TERM": term}, clear=True):
                    reopened = Workspace(path, CORPUS_ID, provenance, actor="Ada")
                    self.addCleanup(reopened.close)
                    adapter = WorkspaceReader(book, reopened, "Ada", resolve_path, display_path,
                                              lambda *args, **kwargs: None)
                    actions = ReaderActions(book, adapter)
                    actions.restore()
                    self.assertEqual(actions.cursor_offset, cursor)
                    self.assertEqual(actions.snapshot().current.identifier, IDS[0])
                    revision = reopened.get_state()["revision"]
                    async with self.running_view(actions, columns=columns) as (view, pipe, output, task):
                        self.assertEqual(view.body.buffer.cursor_position, cursor)
                        self.assertEqual(view.body.text, book.passages[0].text)
                        self.assertEqual(actions.cursor_offset, cursor)
                        self.assertEqual(reopened.get_state()["revision"], revision)
                        self.assertNotIn("KITTY_WINDOW_ID", __import__("os").environ)
                        self.assert_cursor_visible(view)
                    self.assertEqual(reopened.get_state()["position"]["cursor_offset"], cursor)
                    reopened.close()

    async def test_boundary_flow_uses_current_reflow_and_preserves_canonical_records(self):
        book = styled_book()
        records = {identifier: dict(record) for identifier, record in book.canonical_records.items()}
        actions = ReaderActions(book)
        first = actions.read(first=True)
        async with self.running_view(actions) as (view, pipe, output, task):
            for columns in (40, 72, 100):
                await self.resize(view, output, columns)
                layout = view._source_positions()
                offset = next(index for index, point in enumerate(layout)
                              if point[0] == layout[-1][0])
                view._cursor_action(lambda: actions.set_cursor(offset))
                pipe.send_text("j")
                await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[1])
                self.assertEqual(view.body.text, book.passages[1].text)
                self.assertEqual(actions.cursor_offset, 0)
                self.assert_cursor_visible(view)
                pipe.send_text("k")
                await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[0])
                self.assertEqual(view.body.text, first.text)
                self.assertEqual(actions.cursor_offset, len(first.text))
                self.assert_cursor_visible(view)
                self.assertEqual(book.canonical_records, records)

    async def test_backward_entry_is_saved_atomically_and_reopens_at_source_tail(self):
        book = styled_book()
        provenance = {key: book.corpus_manifest[key] for key in ("edition", "source")}
        with tempfile.TemporaryDirectory(prefix="sol-flow-reopen-") as directory:
            path = Path(directory) / "reading.sqlite3"
            store = Workspace(path, CORPUS_ID, provenance, actor="Ada")
            self.addCleanup(store.close)
            adapter = WorkspaceReader(book, store, "Ada", resolve_path, display_path,
                                      lambda *args, **kwargs: None)
            actions = ReaderActions(book, adapter)
            first = actions.read(first=True)
            async with self.running_view(actions) as (view, pipe, output, task):
                view._cursor_action(lambda: actions.set_cursor(len(first.text)))
                pipe.send_text("j")
                await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[1])
                self.assertEqual(store.get_state()["position"]["cursor_offset"], 0)
                pipe.send_text("k")
                await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[0])
                # Verify the passage checkpoint BEFORE a separate quit/save.
                saved = store.get_state()
                self.assertEqual(saved["current_id"], IDS[0])
                self.assertEqual(saved["position"]["cursor_offset"], len(first.text))
                pipe.send_text("\x11")
                self.assertEqual(await asyncio.wait_for(task, 3), 0)
            store.close()
            reopened = Workspace(path, CORPUS_ID, provenance, actor="Ada")
            self.addCleanup(reopened.close)
            adapter = WorkspaceReader(book, reopened, "Ada", resolve_path, display_path,
                                      lambda *args, **kwargs: None)
            restored = ReaderActions(book, adapter)
            restored.restore()
            self.assertEqual(restored.cursor_offset, len(first.text))
            revision = reopened.get_state()["revision"]
            async with self.running_view(restored, columns=40) as (view, pipe, output, task):
                self.assertEqual(view.body.text, first.text)
                self.assertEqual(view.body.buffer.cursor_position, len(first.text))
                self.assertEqual(reopened.get_state()["revision"], revision)
                self.assert_cursor_visible(view)


if __name__ == "__main__":
    unittest.main()
