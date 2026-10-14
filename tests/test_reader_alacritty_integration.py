"""Opt-in real Alacritty/PTY acceptance with invented text and private storage.

Bindings are driven PROGRAMMATICALLY through the key processor, not by physical
keyboard events. The actual emulator and real toolkit output are used, but this
test does not claim that a human inspected glyphs, screenshots, or keyboard input.
"""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from sol.corpus import contract
from test_packaging import write_runtime_corpus


PROGRAM = r'''
import asyncio, json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
root, phase = Path(sys.argv[2]), sys.argv[3]
sys.stderr = (root / (phase + "-errors.txt")).open("w")
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.keys import Keys
from sol.reader import app
from sol.terminal import reader

class ObservedView(reader.ReaderView):
    def run(self):
        async def scenario():
            task = asyncio.create_task(self.application.run_async())
            async def wait(condition):
                deadline = asyncio.get_running_loop().time() + 5
                while not condition():
                    if task.done():
                        await task
                        raise AssertionError("Reader exited before the expected state")
                    if asyncio.get_running_loop().time() >= deadline:
                        raise AssertionError("Alacritty scenario timed out: " + self.status)
                    await asyncio.sleep(.01)
                await asyncio.sleep(.05)
            def keys(*values):
                self.application.key_processor.feed_multiple([
                    KeyPress(value, value if isinstance(value, str) and len(value) == 1 else "")
                    for value in values])
                self.application.key_processor.process_keys()
                self.application.invalidate()
            try:
                await wait(lambda: self.body.window.render_info is not None
                           and self.application.renderer.height_is_known)
                assert sys.stdin.isatty() and sys.stdout.isatty()
                assert not any(name.startswith("KITTY_") for name in os.environ)
                assert "sol.terminal.kitty" not in sys.modules
                first, source = self.actions.snapshot().current.identifier, self.body.text
                assert len(source) > 4000 and not self.typography.degraded
                assert any("emphasis" in span.styles for span in self.typography.spans)
                assert any("strong" in span.styles for span in self.typography.spans)
                columns = self.application.output.get_size().columns
                width = self.body.window.render_info.window_width
                assert self.reading_width == 72 and width <= min(72, columns)
                if self.application.output.get_size().rows >= 24:
                    assert self.heading_window.render_info._y_offset >= 2
                    assert self.body.window.render_info._y_offset > self.heading_window.render_info._y_offset + 2
                if phase == "first":
                    keys("j")
                    await wait(lambda: self.actions.cursor_offset > 0)
                    keys("k")
                    await wait(lambda: self.actions.cursor_offset == 0)
                    keys(Keys.ControlD)
                    await wait(lambda: self.actions.cursor_offset > 0)
                    keys(Keys.ControlU)
                    await wait(lambda: self.actions.cursor_offset == 0)
                    # The selected span crosses several semantic emphasis runs.
                    keys("v", *("l" * 160))
                    await wait(lambda: self.actions.selection is not None
                               and self.actions.selection.end == 160)
                    selected = self.actions.selection
                    keys("/", *"specific", Keys.ControlM)
                    await wait(lambda: self.application.layout.has_focus(self.results))
                    assert len(self.actions.snapshot().results) == 1
                    keys(Keys.ControlM)
                    await wait(lambda: self.actions.snapshot().current.identifier != first)
                    match = self.body.text.index("specific")
                    assert self.actions.cursor_offset == match
                    fragments = self.body.control._get_formatted_text_for_line_func(self.body.buffer.document)(0)
                    assert all("source.search" in style for style, _ in fragments[match:match + 8])
                    def marked():
                        screen = self.application.renderer._last_screen
                        return any("class:source.search" in cell.style
                                   for row in screen.data_buffer.values() for cell in row.values())
                    await wait(marked)
                    keys(Keys.Escape)
                    await wait(lambda: not marked())
                    assert self.actions.search_query == "specific"
                    keys(Keys.ControlN)
                    await wait(marked)
                    assert self.actions.cursor_offset == match
                    keys(Keys.Escape, Keys.Left)
                    await wait(lambda: self.actions.snapshot().current.identifier == first)
                    assert self.actions.selection == selected
                    assert self.actions.cursor_offset == selected.end
                    # Ordinary reading continues through one passage edge,
                    # while the existing source-span contract stays local.
                    keys(Keys.Escape)
                    self._cursor_action(lambda: self.actions.set_cursor(len(source)))
                    keys("j")
                    await wait(lambda: self.actions.snapshot().current.identifier != first)
                    assert self.body.text != source and self.actions.cursor_offset == 0
                    keys("k")
                    await wait(lambda: self.actions.snapshot().current.identifier == first)
                    assert self.body.text == source and self.actions.cursor_offset == len(source)
                    saved = self.actions.workspace_reader.store.get_state()
                    assert saved["position"]["cursor_offset"] == len(source)
                    keys("n")
                    await wait(lambda: self.actions.snapshot().current.identifier != first)
                    keys(Keys.ControlN)
                    await wait(lambda: self.actions.cursor_offset == self.body.text.index("specific"))
                    assert self.actions.snapshot().current.identifier != first
                    keys("b")
                    await wait(lambda: self.actions.snapshot().current.identifier == first)
                    self._cursor_action(lambda: self.actions.set_cursor(selected.end))
                else:
                    previous = json.loads((root / "first-result.json").read_text())
                    assert self.actions.cursor_offset == previous["cursor"] == 160
                    assert first == previous["target"]
                    assert self.actions.selection is None  # Deliberately transient.
                assert self.body.text == source
                assert len(self._source_positions()) == len(source) + 1
                cursor = self.body.window.render_info.cursor_position
                assert 0 <= cursor.x < width
                assert 0 <= cursor.y < self.body.window.render_info.window_height
                result = {"status": "passed", "target": first,
                          "cursor": self.actions.cursor_offset, "columns": columns,
                          "measure": width, "tty": True, "emphasis": self.emphasis}
                keys(Keys.ControlQ)
                assert await asyncio.wait_for(task, 5) == 0
                assert self._saved_on_exit
                state = self.actions.workspace_reader.store.get_state()
                assert state["position"]["cursor_offset"] == result["cursor"]
                (root / (phase + "-result.json")).write_text(json.dumps(result))
                return 0
            finally:
                if not task.done():
                    self.application.exit(result=1)
                await task
        return asyncio.run(scenario())

reader.ReaderView = ObservedView
raise SystemExit(app.main(["--reader", "--corpus", str(root / "corpus"),
    "--workspace", "acceptance", "--workspace-dir", str(root), "--actor", "Invented reader"]))
'''


@unittest.skipUnless(os.environ.get("SOL_TEST_LIVE_ALACRITTY") == "1",
                     "real Alacritty GUI test is explicit opt-in")
@unittest.skipUnless(importlib.util.find_spec("prompt_toolkit") and
                     importlib.util.find_spec("markdown_it"),
                     "optional reader dependencies are absent")
class AlacrittyReaderIntegrationTests(unittest.TestCase):
    def test_real_tty_reader_reopens_source_position_at_a_different_measure(self):
        alacritty = shutil.which("alacritty")
        if not alacritty or not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            self.skipTest("Alacritty and a desktop display are required")
        with tempfile.TemporaryDirectory(prefix="sol-alacritty-reader-test-") as temporary:
            root, repository = Path(temporary), Path(__file__).resolve().parents[1]
            corpus = root / "corpus"
            write_runtime_corpus(corpus)
            records = [json.loads(line) for line in (corpus / "index.jsonl").read_text().splitlines()]
            sentence = ("An invented *thought* remains itself in **another**; α and 界 "
                        "are `source characters`, not visual columns. ")
            records[1]["markdown"] = (sentence * 70).rstrip()
            second = deepcopy(records[1])
            second.update(id="cccccccc-0000-4000-8000-000000000003", order=2,
                          markdown="A specific invented passage supports search and return.")
            records.append(second)
            generated = {"markdown", "plain_text", "document", "context", "content_sha256"}
            (corpus / "sample.md").write_text("\n".join(contract.render_record(
                {key: value for key, value in row.items() if key not in generated}, row["markdown"])
                for row in records), encoding="utf-8")
            contract.reindex(corpus)
            contract.initialize_corpus_identity(corpus)
            before = {path.name: path.read_bytes() for path in corpus.iterdir()}
            (root / "scenario.py").write_text(PROGRAM, encoding="utf-8")
            environment = {**os.environ, "XDG_CONFIG_HOME": str(root / "config"),
                           "XDG_DATA_HOME": str(root / "data"), "XDG_CACHE_HOME": str(root / "cache")}
            for name in tuple(environment):
                if name.startswith(("KITTY_", "SOL_ACTOR", "SOL_WORKSPACE")) or name in {
                        "SOL_CORPUS", "SOL_KITTY_SESSION", "ALACRITTY_SOCKET", "ALACRITTY_WINDOW_ID"}:
                    environment.pop(name)
            results = []
            for phase, columns in (("first", 100), ("reopen", 40)):
                configuration = root / (phase + ".toml")
                configuration.write_text(
                    "[general]\nipc_socket = false\n[window]\ndynamic_title = false\n"
                    f"dimensions = {{ columns = {columns}, lines = 28 }}\n", encoding="utf-8")
                command = [alacritty, "--config-file", str(configuration), "--title",
                           "SOL isolated Alacritty reader test", "-e", sys.executable, "-I", "-B",
                           str(root / "scenario.py"), str(repository), str(root), phase]
                child = subprocess.Popen(command, cwd=root, env=environment,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    _, error = child.communicate(timeout=20)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    try:
                        child.communicate(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.communicate(timeout=3)
                    self.fail("Owned Alacritty test window did not finish within 20 seconds")
                diagnostics = error + ((root / (phase + "-errors.txt")).read_text()
                                       if (root / (phase + "-errors.txt")).exists() else "")
                self.assertEqual(child.returncode, 0, diagnostics)
                result_path = root / (phase + "-result.json")
                self.assertTrue(result_path.exists(), diagnostics)
                results.append(json.loads(result_path.read_text()))
            self.assertEqual([row["status"] for row in results], ["passed", "passed"])
            self.assertEqual([row["cursor"] for row in results], [160, 160])
            self.assertNotEqual(results[0]["columns"], results[1]["columns"])
            self.assertGreater(results[0]["measure"], results[1]["measure"])
            self.assertEqual(before, {path.name: path.read_bytes() for path in corpus.iterdir()})
            self.assertFalse((root / "config" / "sol").exists())
            self.assertTrue((root / "acceptance.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
