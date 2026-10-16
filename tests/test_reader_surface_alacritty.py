"""Explicit opt-in real Alacritty proof; all keys are programmatic.

Only an owned, uniquely titled temporary window is resized/captured. This is not
physical-keyboard or sustained-reading acceptance. Invented in-memory records
and a private XDG directory prevent personal corpus/workspace writes.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PROGRAM = r'''
import asyncio, copy, ctypes, json, os, subprocess, sys
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, str(Path(sys.argv[1]) / "tests"))
root = Path(sys.argv[2])
sys.stderr = (root / "errors.txt").open("w")
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.keys import Keys
from test_reader_surface_tui import sample, IDS
from experiments.reader_surfaces.tui import ContinuousView, SourceLocation

selection = sample()
selection.book.passages[1] = replace(selection.book.passages[1], transcription_status="needs_review",
                                    heading="An invented section transition")
selection.passages = tuple(selection.book.passages)
before = copy.deepcopy(selection.book.canonical_records)
texts_before = tuple(p.text for p in selection.passages)
view = ContinuousView(selection, width=72)
view.application.ttimeoutlen = .01
view.application.timeoutlen = .03

async def scenario():
    task = asyncio.create_task(view.application.run_async())
    async def wait(condition):
        deadline = asyncio.get_running_loop().time() + 5
        while not condition():
            if task.done():
                await task
                raise AssertionError("Owned continuous proof exited early")
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("Continuous proof timed out: " + repr(view.status))
            await asyncio.sleep(.01)
        await asyncio.sleep(.05)
    def keys(*values):
        view.application.key_processor.feed_multiple([
            KeyPress(value, value if isinstance(value,str) and len(value)==1 else "")
            for value in values])
        view.application.key_processor.process_keys()
        view.application.invalidate()
    try:
        await wait(lambda: view.body_window.render_info is not None and
                   view.application.renderer.height_is_known)
        assert sys.stdin.isatty() and sys.stdout.isatty()
        assert not any(name.startswith("KITTY_") for name in os.environ)
        assert "sol.terminal.kitty" not in sys.modules
        assert selection.actions.workspace_reader is None
        screen = view.application.renderer._last_screen
        visible = "\n".join("".join(cell.char for _,cell in sorted(row.items()))
                            for _,row in sorted(screen.data_buffer.items()))
        assert "Thought remains" in visible and "The Idea" in visible and "Unicode" in visible, visible
        assert "[source review]" in visible and view.location.target_id == IDS[0], visible
        assert "An invented section transition" in visible, visible
        assert view.body_window.render_info._y_offset == view.heading_window.render_info._y_offset + 3
        old_columns = view.application.output.get_size().columns
        assert old_columns > 72
        # Capture only the X11 client belonging to this process, never desktop.
        xid = os.environ.get("ALACRITTY_WINDOW_ID")
        assert xid, "Owned X11 Alacritty window ID is unavailable"
        window_id = int(xid, 0)
        capture = os.environ.get("SOL_SURFACE_CAPTURE")
        if capture:
            path = Path(capture).resolve()
            assert path.parent == Path("/tmp") and path.name.startswith("sol-continuous-")
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "x11grab",
                "-window_id", str(window_id), "-i", os.environ["DISPLAY"], "-frames:v", "1", str(path)],
                capture_output=True, check=True, timeout=5)
        keys("v", *("l" * 7))
        await wait(lambda: selection.actions.selection is not None and
                   selection.actions.selection.text == "Thought")
        selected = selection.actions.selection
        keys("n")
        await wait(lambda: "Selection stops" in view.status)
        assert selection.actions.selection == selected and view.location.target_id == IDS[0]
        keys(Keys.Escape)
        await wait(lambda: view.anchor is None)
        selection.actions.set_cursor(len(selection.passages[0].text))
        keys("j")
        await wait(lambda: view.location.target_id == IDS[1])
        keys("k")
        await wait(lambda: view.location.target_id == IDS[0])
        selection.actions.set_cursor(0)
        keys("v", *("l" * 55))
        await wait(lambda: view.location.offset == 55)
        source_location, selected = view.location, selection.actions.selection
        old_point = view.projection().position(source_location)
        # Native resize targets only our own X11 client. A real SIGWINCH/PTTY
        # size update drives the same reflow used by ordinary terminal resize.
        x11 = ctypes.CDLL("libX11.so.6")
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XResizeWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_uint, ctypes.c_uint]
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(None)
        assert display
        try:
            x11.XResizeWindow(display, window_id, 400, 640)
            x11.XFlush(display)
            await wait(lambda: view.application.output.get_size().columns < 72 and
                       view.body_window.render_info.window_width < 72)
            assert view.location == source_location
            assert selection.actions.selection == selected
            assert view.projection().position(source_location) != old_point
            narrow_columns = view.application.output.get_size().columns
            x11.XResizeWindow(display, window_id, 1600, 640)
            x11.XFlush(display)
            await wait(lambda: view.application.output.get_size().columns >= 72 and
                       view.body_window.render_info.window_width == 72)
            assert view.location == source_location
            assert selection.actions.selection == selected
            assert view.projection().position(source_location) == old_point
        finally:
            x11.XCloseDisplay(display)
        keys(Keys.Escape, Keys.ControlD)
        await wait(lambda: view.location != source_location)
        keys(Keys.ControlU)
        await asyncio.sleep(.1)
        assert selection.book.canonical_records == before
        assert tuple(p.text for p in selection.passages) == texts_before
        assert set(view.projection().positions) == set(IDS)
        keys("q")
        assert await asyncio.wait_for(task,5) == 0
        (root / "result.json").write_text(json.dumps({"status":"passed", "tty":True,
            "simultaneous_records":3, "source_offsets_unchanged":True,
            "selection_crossing_refused":True, "wide_columns":old_columns,
            "narrow_columns":narrow_columns, "native_resize":True}))
    finally:
        if not task.done():
            view.application.exit(result=1)
        await task

asyncio.run(scenario())
'''


@unittest.skipUnless(os.environ.get("SOL_TEST_LIVE_SURFACE_ALACRITTY") == "1",
                     "real continuous Alacritty proof is explicit opt-in")
@unittest.skipUnless(importlib.util.find_spec("prompt_toolkit") and
                     importlib.util.find_spec("markdown_it"), "optional reader dependencies absent")
class ContinuousAlacrittyTests(unittest.TestCase):
    def test_real_continuous_surface_and_native_resize_without_workspace(self):
        if not shutil.which("alacritty") or not os.environ.get("DISPLAY"):
            self.skipTest("Alacritty and X11/XWayland display are required")
        with tempfile.TemporaryDirectory(prefix="sol-continuous-alacritty-") as temporary:
            root = Path(temporary)
            configuration = root / "alacritty.toml"
            configuration.write_text(
                "[general]\nipc_socket = false\n[window]\ndynamic_title = false\n"
                "dimensions = { columns = 100, lines = 28 }\n", encoding="utf-8")
            (root / "scenario.py").write_text(PROGRAM, encoding="utf-8")
            environment = {**os.environ, "XDG_CONFIG_HOME": str(root / "config"),
                           "XDG_DATA_HOME": str(root / "data"), "XDG_CACHE_HOME": str(root / "cache")}
            for name in tuple(environment):
                if name.startswith(("KITTY_", "SOL_ACTOR", "SOL_WORKSPACE")) or name in {
                    "WAYLAND_DISPLAY", "WAYLAND_SOCKET", "ALACRITTY_SOCKET", "ALACRITTY_WINDOW_ID",
                    "SOL_CORPUS", "SOL_KITTY_SESSION"}:
                    environment.pop(name)
            completed = subprocess.run([
                "alacritty", "--config-file", str(configuration), "--title",
                "SOL continuous surface isolated acceptance", "-e", sys.executable, "-I", "-B",
                str(root / "scenario.py"), str(Path(__file__).resolve().parents[1]), str(root)],
                cwd=root, env=environment, capture_output=True, text=True, timeout=25)
            errors = completed.stderr + ((root / "errors.txt").read_text()
                                         if (root / "errors.txt").exists() else "")
            self.assertEqual(completed.returncode, 0, errors)
            self.assertTrue((root / "result.json").exists(), errors)
            import json
            result = json.loads((root / "result.json").read_text())
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["simultaneous_records"], 3)
            self.assertLess(result["narrow_columns"], result["wide_columns"])
            self.assertTrue(result["selection_crossing_refused"])
            self.assertTrue(result["source_offsets_unchanged"])
            self.assertTrue(result["native_resize"])
            self.assertFalse(list(root.rglob("*.sqlite3")))
            self.assertFalse((root / "config" / "sol").exists())

