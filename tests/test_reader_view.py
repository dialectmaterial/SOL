"""Reader surface checks with invented sources and the optional real toolkit."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fixtures_async import UIEventLoop

from sol.core.models import Book, Node, Passage
from sol.reader.actions import ReaderActions
from experiments.reader_surfaces.baseline import ReaderView, run_reader, safe_reader_text, validate_reader_environment


OPTIONAL = importlib.util.find_spec("prompt_toolkit") is not None
IDS = [f"aaaaaaaa-0000-4000-8000-{index:012d}" for index in range(1, 4)]


def reader_book():
    root = Node("", "Invented reader book", 1)
    leaf = Node("quality.txt", "Quality", 1, parent=root)
    root.children = (leaf,)
    bodies = ["  Alpha source keeps its spaces.\nA second source line.  ",
              "Beta is the destination found by searching.",
              "Gamma finishes the invented reading selection."]
    passages = [Passage(body, index + 10, index + 1, leaf, (leaf.name,),
                        index + 10, index + 1, IDS[index], leaf.title)
                for index, body in enumerate(bodies)]
    records = {passage.identifier: {
        "id": passage.identifier, "type": "paragraph", "plain_text": passage.text,
        "markdown": passage.text, "reader_path": "/" + "/".join(passage.path),
        "content_sha256": hashlib.sha256(passage.text.encode()).hexdigest(),
        "sources": [{"pdf_page": passage.pdf_page, "printed_page": str(passage.printed_page)}],
    } for passage in passages}
    return Book(root, passages, canonical_records=records)


class ReaderEnvironmentTests(unittest.TestCase):
    def test_module_and_core_import_do_not_load_optional_dependency(self):
        result = subprocess.run([sys.executable, "-B", "-c", """
import json, sys
import sol.core
import experiments.reader_surfaces.baseline
print(json.dumps(sorted(sys.modules)))
"""], cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=True)
        modules = json.loads(result.stdout)
        self.assertFalse(any(name == "prompt_toolkit" or name.startswith("prompt_toolkit.")
                             for name in modules))

    def test_preflight_rejects_nonterminal_and_dumb_without_optional_import(self):
        tty = SimpleNamespace(isatty=lambda: True)
        pipe = SimpleNamespace(isatty=lambda: False)
        for stdin, stdout, term in ((pipe, tty, "xterm"), (tty, pipe, "xterm"), (tty, tty, "dumb")):
            with self.subTest(term=term, stdin=stdin, stdout=stdout), \
                    patch("experiments.reader_surfaces.baseline.sys.stdin", stdin), \
                    patch("experiments.reader_surfaces.baseline.sys.stdout", stdout), \
                    patch.dict("os.environ", {"TERM": term}), \
                    patch("experiments.reader_surfaces.baseline._load_toolkit") as loader:
                with self.assertRaisesRegex(ValueError, "interactive terminal"):
                    validate_reader_environment()
                loader.assert_not_called()

    def test_missing_reader_dependency_has_actionable_error(self):
        tty = SimpleNamespace(isatty=lambda: True)
        with patch("experiments.reader_surfaces.baseline.sys.stdin", tty), \
                patch("experiments.reader_surfaces.baseline.sys.stdout", tty), \
                patch.dict("os.environ", {"TERM": "xterm"}), \
                patch("experiments.reader_surfaces.baseline._load_toolkit", side_effect=ImportError("absent")):
            with self.assertRaisesRegex(ValueError, r"pipx install --force \."):
                validate_reader_environment()

    def test_metadata_controls_bidi_and_invisible_characters_are_literal(self):
        raw = "title\x1b]0;unsafe\x07\r\n\t\u202e\u200b\u00a0\ufe0f\u115f\u17b4"
        displayed = safe_reader_text(raw)
        for character in ("\x1b", "\x07", "\r", "\n", "\t", "\u202e", "\u200b", "\u00a0", "\ufe0f",
                          "\u115f", "\u17b4"):
            self.assertNotIn(character, displayed)
        self.assertIn("\\x1b", displayed)
        self.assertIn("\\u202e", displayed)
        self.assertIn("\\u200b", displayed)

    def test_saved_restore_refusal_does_not_start_or_replace_reading(self):
        book = reader_book()
        reader = SimpleNamespace(book=book, resumed_reference=None,
            store=SimpleNamespace(get_state=lambda: {"current_id": "missing"}),
            restore=lambda *args: (_ for _ in ()).throw(ValueError("saved source is missing")))
        captured = []
        class CapturedView:
            def __init__(self, actions):
                self.actions = actions
                self.status = ""
                captured.append(self)
            def run(self):
                return 0
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment"), \
                patch("experiments.reader_surfaces.baseline.ReaderView", CapturedView), \
                patch.object(ReaderActions, "read", side_effect=AssertionError("No new visit")):
            self.assertEqual(run_reader(book, reader), 0)
        self.assertIsNone(captured[0].actions.snapshot().current)
        self.assertEqual(captured[0].status, "saved source is missing")

    def test_new_workspace_starts_through_one_normal_guarded_action(self):
        book = reader_book()
        checkpoints = []
        reader = SimpleNamespace(book=book, resumed_reference=None,
            store=SimpleNamespace(get_state=lambda: None),
            checkpoint=lambda session, cwd, previous: checkpoints.append(session.current()))
        captured = []
        class CapturedView:
            def __init__(self, actions):
                self.actions = actions
                self.status = ""
                captured.append(self)
            def run(self):
                return 0
        with patch("experiments.reader_surfaces.baseline.validate_reader_environment"), \
                patch("experiments.reader_surfaces.baseline.ReaderView", CapturedView):
            self.assertEqual(run_reader(book, reader), 0)
        self.assertEqual(checkpoints, [book.passages[0]])
        self.assertIs(captured[0].actions.snapshot().current, book.passages[0])


@unittest.skipUnless(OPTIONAL, "optional prompt_toolkit is absent")
class ReaderViewTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def wait_for(self, condition):
        deadline = asyncio.get_running_loop().time() + 2
        while not condition():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail("Reader did not reach the expected state")
            await asyncio.sleep(0.01)

    async def test_pending_transcription_review_remains_visible_in_the_reading_context(self):
        book = reader_book()
        book.passages[0] = replace(book.passages[0], transcription_status="needs_review")
        actions = ReaderActions(book)
        actions.read(first=True)
        async with self.running_view(actions) as (view, pipe, task):
            self.assertIn("[source review]", view._status_text())
            view.status = "A harmless contextual error"
            self.assertIn("[source review]", view._status_text())

    async def test_search_scope_does_not_inherit_a_hidden_compatibility_shell_directory(self):
        from test_reader_actions import invented_book
        book = invented_book()
        workspace = SimpleNamespace(book=book, resumed_reference=None, checkpoint=lambda *args: None)
        actions = ReaderActions(book, workspace)
        actions.read(('BEING',), first=True)
        actions.browse(('ESSENCE',))
        async with self.running_view(actions) as (view, pipe, task):
            pipe.send_text('/ground\r')
            await self.wait_for(lambda: view.application.layout.has_focus(view.results))
            self.assertEqual(len(actions.results), 3)
            self.assertEqual(actions.snapshot().current.identifier, book.passages[0].identifier)

    @asynccontextmanager
    async def running_view(self, actions, *, output=None):
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        with create_pipe_input() as pipe:
            view = ReaderView(actions, input=pipe, output=output or DummyOutput())
            view.application.ttimeoutlen = 0.01
            view.application.timeoutlen = 0.05
            task = asyncio.create_task(view.application.run_async())
            await self.wait_for(lambda: view.application.is_running)
            try:
                yield view, pipe, task
            finally:
                if not task.done():
                    pipe.send_text("\x11")
                self.assertEqual(await asyncio.wait_for(task, 2), 0)

    async def test_navigation_search_result_and_history_restore_selected_source(self):
        actions = ReaderActions(reader_book())
        first = actions.read(first=True)
        async with self.running_view(actions) as (view, pipe, task):
            self.assertEqual(view.body.text, first.text)
            self.assertTrue(view.body.read_only)
            pipe.send_text("\x1b[1;2C\x1b[1;2C\x1b[1;2C")
            await self.wait_for(lambda: actions.selection is not None and actions.selection.end == 3)
            self.assertEqual(actions.selection.text, first.text[:3])
            pipe.send_text("/Beta\r")
            await self.wait_for(lambda: view.application.layout.has_focus(view.results))
            self.assertEqual(view.body.text, first.text)
            self.assertEqual(view.search_input.text, "Beta")
            self.assertEqual(len(actions.snapshot().results), 1)
            self.assertNotIn(IDS[1], "".join(fragment[1] for fragment in view._result_text()))
            pipe.send_text("\r")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[1])
            self.assertEqual(view.body.text, actions.book.passages[1].text)
            pipe.send_text("\x1b[1;3D")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[0])
            self.assertEqual(actions.selection.text, first.text[:3])
            self.assertEqual(view.body.buffer.cursor_position, 3)
            self.assertEqual(list(view.body.buffer.document.selection_ranges()), [(0, 3)])
            pipe.send_text("\x1b[1;3C")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[1])
            pipe.send_text("}")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[2])
            pipe.send_text("\x1b[5~")
            await self.wait_for(lambda: actions.snapshot().current.identifier == IDS[1])

    async def test_failed_checkpoint_preserves_body_cursor_and_selection(self):
        book = reader_book()
        reader = SimpleNamespace(book=book, resumed_reference=None, checkpoint=lambda *args: None)
        actions = ReaderActions(book, reader)
        actions.read(first=True)
        async with self.running_view(actions) as (view, pipe, task):
            pipe.send_text("\x1b[C\x1b[1;2C\x1b[1;2C")
            await self.wait_for(lambda: actions.selection is not None and actions.selection.end == 3)
            before = (view.body.text, view.body.buffer.cursor_position,
                      list(view.body.buffer.document.selection_ranges()), actions.snapshot())
            def refuse(*args):
                raise RuntimeError("loaded corpus changed\x1b[31m")
            reader.checkpoint = refuse
            pipe.send_text("}")
            await self.wait_for(lambda: "loaded corpus changed" in view.status)
            after = (view.body.text, view.body.buffer.cursor_position,
                     list(view.body.buffer.document.selection_ranges()), actions.snapshot())
            self.assertEqual(before, after)
            self.assertNotIn("\x1b", view._status_text())
            self.assertIn("\\x1b", view._status_text())

    async def test_query_cancel_clear_selection_and_bounded_search_results(self):
        actions = ReaderActions(reader_book())
        actions.read(first=True)
        async with self.running_view(actions) as (view, pipe, task):
            pipe.send_text("\x1b[1;2C")
            await self.wait_for(lambda: actions.selection is not None)
            pipe.send_text("/")
            await self.wait_for(lambda: view.application.layout.has_focus(view.search_input))
            pipe.send_text("unfinished\x1b")
            await self.wait_for(lambda: view.application.layout.has_focus(view.body))
            self.assertIsNotNone(actions.selection)
            pipe.send_text("\x1b")
            await self.wait_for(lambda: actions.selection is None)
            self.assertIsNone(view.body.buffer.selection_state)
            pipe.send_text("/reading\r")
            await self.wait_for(lambda: view.application.layout.has_focus(view.results))
            pipe.send_text("\t")
            await self.wait_for(lambda: view.application.layout.has_focus(view.body))
            pipe.send_text("?")
            await self.wait_for(lambda: view._help_visible)

    async def test_source_escape_mapping_and_selection_keep_exact_raw_offsets(self):
        from prompt_toolkit.layout.processors import TransformationInput
        book = reader_book()
        raw = " A\x1b[31m\t\u202e\u200b\ufe0fZ \nend "
        book.passages[0] = replace(book.passages[0], text=raw,
            heading="Unsafe\x1b]0;title\x07")
        book.canonical_records[IDS[0]]["plain_text"] = raw
        book.canonical_records[IDS[0]]["markdown"] = raw
        book.canonical_records[IDS[0]]["content_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
        actions = ReaderActions(book)
        actions.read(first=True)
        async with self.running_view(actions) as (view, pipe, task):
            self.assertEqual(view.body.text, raw)
            line = raw.split("\n")[0]
            transformed = view.source_processor.apply_transformation(TransformationInput(
                view.body.control, view.body.buffer.document, 0, lambda x: x,
                [("", line)], 80, 20))
            display = "".join(fragment[1] for fragment in transformed.fragments)
            self.assertEqual(display, safe_reader_text(line))
            for index in range(len(line) + 1):
                self.assertEqual(transformed.display_to_source(transformed.source_to_display(index)), index)
            esc_index = raw.index("\x1b")
            display_start = transformed.source_to_display(esc_index)
            for offset in range(4):
                self.assertEqual(transformed.display_to_source(display_start + offset), esc_index)
            self.assertNotIn("\x1b", view._header())
            pipe.send_text("\x1b[1;2C" * 4)
            await self.wait_for(lambda: actions.selection is not None and actions.selection.end == 4)
            self.assertEqual(actions.selection.text, raw[:4])

    async def test_long_path_keeps_page_header_and_long_paragraph_scrolls_in_narrow_terminal(self):
        from prompt_toolkit.data_structures import Size
        from prompt_toolkit.output import DummyOutput
        class NarrowOutput(DummyOutput):
            def get_size(self):
                return Size(rows=18, columns=46)
        book = reader_book()
        path = ("BEING", "01-determinateness-quality", "2-existence", "b-finitude",
                "03-transition-of-the-finite-into-the-infinite.txt")
        raw = "source text remains exact " * 150
        book.passages[0] = replace(book.passages[0], text=raw, path=path)
        book.canonical_records[IDS[0]].update(
            plain_text=raw, markdown=raw, reader_path="/" + "/".join(path),
            content_sha256=hashlib.sha256(raw.encode()).hexdigest())
        actions = ReaderActions(book)
        actions.read(first=True)
        async with self.running_view(actions, output=NarrowOutput()) as (view, pipe, task):
            await self.wait_for(lambda: view.body.window.render_info is not None)
            self.assertIn("Printed 1 | PDF 10", view._header())
            self.assertGreater(view.body.window.render_info.window_height, 3)
            self.assertLessEqual(view.body.window.render_info.window_width, 46)
            from sol.reader.navigation import vertical_offset
            positions = view._source_positions()
            start, _ = vertical_offset(positions, 0, 20)
            end, _ = vertical_offset(positions, start, 1)
            pipe.send_text("\x1b[B" * 20)
            await self.wait_for(lambda: view.body.buffer.cursor_position == start)
            self.assertEqual(view.body.text, raw)
            self.assertIsNone(actions.selection)
            pipe.send_text("\x1b[1;2B")
            await self.wait_for(lambda: actions.selection is not None)
            self.assertEqual(actions.selection.text, raw[start:end])

    async def test_search_limit_result_scroll_and_result_cursor_open(self):
        book = reader_book()
        for number in range(30):
            passage = replace(book.passages[1], identifier=f"bbbbbbbb-0000-4000-8000-{number:012d}",
                              text=f"Findword destination number {number}")
            book.passages.append(passage)
            record = dict(book.canonical_records[IDS[1]], id=passage.identifier,
                          plain_text=passage.text, markdown=passage.text,
                          content_sha256=hashlib.sha256(passage.text.encode()).hexdigest())
            book.canonical_records[passage.identifier] = record
        actions = ReaderActions(book)
        actions.read(first=True)
        async with self.running_view(actions) as (view, pipe, task):
            source = view.body.text
            pipe.send_text("/Findword\r")
            await self.wait_for(lambda: view.application.layout.has_focus(view.results))
            self.assertEqual(len(actions.snapshot().results), 20)
            self.assertEqual(view.body.text, source)
            pipe.send_text("\x1b[B" * 12)
            await self.wait_for(lambda: view._result_index == 12)
            await self.wait_for(lambda: view.results_window.render_info is not None)
            self.assertLessEqual(view.results_window.render_info.window_height, 6)
            self.assertGreater(view.results_window.vertical_scroll, 0)
            expected = actions.snapshot().results[12]
            pipe.send_text("\r")
            await self.wait_for(lambda: actions.snapshot().current is expected)
            self.assertEqual(view.body.text, expected.text)

    async def test_quit_restores_terminal_state_and_source_controls_are_never_written(self):
        from prompt_toolkit.output import DummyOutput
        class CapturedOutput(DummyOutput):
            def __init__(self):
                self.events = []
                self.text = []
            def enter_alternate_screen(self):
                self.events.append("enter")
            def quit_alternate_screen(self):
                self.events.append("leave")
            def write(self, data):
                self.text.append(data)
            def write_raw(self, data):
                self.text.append(data)
        book = reader_book()
        book.passages[0] = replace(book.passages[0], text="unsafe\x1b]0;source\x07\u202e\u200b")
        actions = ReaderActions(book)
        actions.read(first=True)
        output = CapturedOutput()
        async with self.running_view(actions, output=output) as (view, pipe, task):
            await self.wait_for(lambda: "enter" in output.events)
            pipe.send_text("\x11")
            self.assertEqual(await asyncio.wait_for(task, 2), 0)
        self.assertIn("leave", output.events)
        rendered = "".join(output.text)
        self.assertNotIn("\x1b]0;source", rendered)
        self.assertNotIn("\x07", rendered)
        self.assertNotIn("\u202e", rendered)
        self.assertNotIn("\u200b", rendered)


if __name__ == "__main__":
    unittest.main()
