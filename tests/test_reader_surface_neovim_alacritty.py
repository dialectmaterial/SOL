"""Explicit native Neovim/Alacritty proof; every key/resize is programmatic.

Only the uniquely titled window created by this test is resized. Invented
temporary records and isolated XDG paths avoid personal configuration/state.
This is not physical-keyboard acceptance or evidence of sustained readability.
"""
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from test_reader_surface_neovim import invented_sample, neovim_environment


_SCENARIO = r'''
dofile(os.getenv('SOL_NVIM_ADAPTER'))
local reader = assert(SOLNvimReader)
local report_path = os.getenv('SOL_NVIM_TEST_REPORT')
local root = vim.fn.fnamemodify(report_path, ':h')
local input = assert(io.open(os.getenv('SOL_NVIM_INPUT'), 'r'))
local data = vim.json.decode(input:read('*a')); input:close()
local stage, selected = 0, nil
local function report(value)
  vim.fn.writefile({vim.json.encode(value)}, report_path)
end
local function fail(message)
  report({status = 'failed', error = tostring(message)})
  vim.cmd('cquit 1')
end
vim.defer_fn(function()
  local ok, error = xpcall(function()
    assert(vim.fn.has('ttyin') == 1 and vim.fn.has('ttyout') == 1)
    assert(not os.getenv('KITTY_WINDOW_ID'))
    local xid = assert(os.getenv('ALACRITTY_WINDOW_ID'), 'owned X11 window ID is unavailable')
    local location = assert(reader.source_point(data.records[1].id, 7))
    -- Offset 7 begins the invented word "thought", after a non-BMP glyph.
    vim.api.nvim_win_set_cursor(reader.window, {location.row, location.byte})
    vim.api.nvim_feedkeys('v6l', 'xt', false)
    selected = reader.capture()
    assert(selected.selection.text == 'thought')
    report({status = 'wide', xid = xid, columns = vim.o.columns, packet = selected})
    stage = 1
  end, debug.traceback)
  if not ok then fail(error) end
end, 180)
local timer = assert(vim.uv.new_timer())
timer:start(100, 70, vim.schedule_wrap(function()
  local ok, error = xpcall(function()
    if stage == 1 and vim.o.columns < 72 then
      assert(vim.deep_equal(reader.capture(), selected), 'native narrowing changed source selection')
      report({status = 'narrow', columns = vim.o.columns, packet = reader.capture()})
      stage = 2
    elseif stage == 2 and vim.o.columns > 90 then
      assert(vim.deep_equal(reader.capture(), selected), 'native widening changed source selection')
      reader.export()
      report({status = 'passed', columns = vim.o.columns, packet = reader.capture()})
      timer:stop(); timer:close()
      vim.cmd('qa!')
    end
  end, debug.traceback)
  if not ok then timer:stop(); timer:close(); fail(error) end
end))
vim.defer_fn(function() fail('native terminal proof timed out') end, 14000)
'''


@unittest.skipUnless(os.environ.get("SOL_TEST_LIVE_NVIM_ALACRITTY") == "1",
                     "real Neovim Alacritty proof is explicit opt-in")
class NeovimAlacrittyTests(unittest.TestCase):
    def test_native_visual_selection_and_owned_terminal_resize(self):
        if not shutil.which("alacritty") or not shutil.which("nvim") or not os.environ.get("DISPLAY"):
            self.skipTest("installed Neovim, Alacritty, and X11/XWayland display are required")
        from sol.being.surface import validate_packet
        from sol.being.neovim.host import build_payload

        with tempfile.TemporaryDirectory(prefix="sol-neovim-alacritty-") as temporary:
            root = Path(temporary)
            corpus, sample = invented_sample(root)
            before = {path.name: path.read_bytes() for path in corpus.iterdir()}
            config, script = root / "alacritty.toml", root / "scenario.lua"
            source, output, report = root / "input.json", root / "selection.json", root / "report.json"
            config.write_text("[general]\nipc_socket = false\n[window]\ndynamic_title = false\n"
                "dimensions = { columns = 100, lines = 28 }\n", encoding="utf-8")
            script.write_text(_SCENARIO, encoding="utf-8")
            source.write_text(json.dumps({**build_payload(sample), "navigation": {"next": False, "previous": False}, "notice": ""}, ensure_ascii=False), encoding="utf-8")
            adapter = Path(__file__).resolve().parents[1] / "sol/being/neovim/neovim.lua"
            environment = {**neovim_environment(root), "SOL_NVIM_INPUT": str(source),
                "SOL_NVIM_OUTPUT": str(output), "SOL_NVIM_ADAPTER": str(adapter),
                "SOL_NVIM_TEST_REPORT": str(report)}
            for key in ("WAYLAND_DISPLAY", "WAYLAND_SOCKET", "ALACRITTY_SOCKET", "ALACRITTY_WINDOW_ID"):
                environment.pop(key, None)
            process = subprocess.Popen(["alacritty", "--config-file", str(config), "--title",
                "SOL isolated Neovim reader acceptance", "-e", shutil.which("nvim"),
                "-u", "NONE", "--noplugin", "-i", "NONE", "-n", "-c", "lua dofile(" + json.dumps(str(script)) + ")"],
                cwd=root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            def wait(status):
                deadline = time.monotonic() + 7
                while time.monotonic() < deadline:
                    if report.exists():
                        try:
                            value = json.loads(report.read_text())
                        except json.JSONDecodeError:
                            continue
                        if value.get("status") == "failed":
                            self.fail(value["error"])
                        if value.get("status") == status:
                            return value
                    if process.poll() is not None:
                        self.fail("Owned Alacritty exited early: " + "".join(process.communicate()))
                    time.sleep(.03)
                self.fail("Owned Neovim terminal did not reach stage " + status)
            display = None
            try:
                wide = wait("wide")
                self.assertGreater(wide["columns"], 90)
                window = int(wide["xid"], 0)
                self.assertGreater(window, 0)
                x11 = ctypes.CDLL("libX11.so.6")
                x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
                x11.XOpenDisplay.restype = ctypes.c_void_p
                x11.XResizeWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_uint, ctypes.c_uint]
                x11.XFlush.argtypes = [ctypes.c_void_p]
                x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
                display = x11.XOpenDisplay(None)
                self.assertTrue(display)
                x11.XResizeWindow(display, window, 400, 640); x11.XFlush(display)
                narrow = wait("narrow")
                self.assertLess(narrow["columns"], 72)
                x11.XResizeWindow(display, window, 1600, 640); x11.XFlush(display)
                final = wait("passed")
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0, stdout + stderr)
                self.assertEqual(wide["packet"], narrow["packet"])
                self.assertEqual(wide["packet"], final["packet"])
                self.assertEqual(validate_packet(sample.book, json.loads(output.read_text())["packet"]).text, "thought")
                self.assertEqual(before, {path.name: path.read_bytes() for path in corpus.iterdir()})
                self.assertFalse(list(root.rglob("*.sqlite3")))
                self.assertFalse((root / "config" / "sol").exists())
                print("Neovim Alacritty proof:", json.dumps({"status": "passed", "tty": True,
                    "native_resize": True, "wide_columns": wide["columns"],
                    "narrow_columns": narrow["columns"], "selection": "thought"}))
            finally:
                if display:
                    x11.XCloseDisplay(display)
                if process.poll() is None:
                    process.terminate()
                    process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
