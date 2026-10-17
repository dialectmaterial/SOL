"""Opt-in end-to-end workspace proof in owned Alacritty windows.

Keys and X11 resizes are programmatic, not human visual/readability acceptance.
Only invented sources and temporary actor/config/workspace paths are used.
"""
from copy import deepcopy
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

from fixtures_corpus import CorpusFixture
from sol.reader.actions import ReaderActions
from sol.workspace.store import Workspace


_LAUNCH = r'''
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from sol.reader import app
from sol.terminal import neovim
from sol.terminal import reader_channel
original = reader_channel.subprocess.Popen
def native(command, **options):
    if command[-1] == neovim._LOAD_ADAPTER:
        command = [*command, '-c', 'lua dofile(vim.env.SOL_NVIM_TEST_SCENARIO)']
    return original(command, **options)
reader_channel.subprocess.Popen = native
raise SystemExit(app.main(['--engine', 'neovim', '--actor', 'Invented acceptance reader',
    '--workspace', 'reading', '--workspace-dir', sys.argv[2], '--width', sys.argv[3]]))
'''

_SCENARIO = r'''
local api, reader = vim.api, assert(SOLNvimReader)
local file = assert(io.open(vim.env.SOL_NVIM_INPUT, 'r'))
local data = vim.json.decode(file:read('*a')); file:close()
local report_path, phase = vim.env.SOL_NVIM_TEST_REPORT, vim.env.SOL_NVIM_TEST_PHASE
local function report(value) vim.fn.writefile({vim.json.encode(value)}, report_path) end
local function fail(problem) report({status = 'failed', error = tostring(problem)}); vim.cmd('cquit 1') end
local saved, stage, timer = nil, 0, vim.uv.new_timer()
api.nvim_create_autocmd('VimResized', { callback = function()
  vim.fn.writefile({vim.json.encode({columns = vim.o.columns, stage = stage})}, report_path .. '.size')
end })
vim.defer_fn(function()
  local ok, problem = xpcall(function()
    assert(vim.fn.has('ttyin') == 1 and vim.fn.has('ttyout') == 1)
    assert(not vim.env.KITTY_WINDOW_ID)
    assert(#data.records == 2 and data.integrated == true)
    assert(vim.wo[reader.window].linebreak and vim.wo[reader.window].wrap)
    assert(not vim.bo[reader.buffer].modifiable)
    assert(#reader.styles > 0)
    if phase == 'reopen' then
      assert(data.width == 40 and data.restore.cursor_offset == 11)
      assert(data.restore.reference.reference.target_id == data.records[2].id)
      assert(reader.capture().cursor_offset == 11)
      assert(reader.marker_slots().slots[2].target == data.records[2].id)
      local prior, original_reader = reader.capture(), reader
      reader.context()
      api.nvim_feedkeys('2', 'xt', false)
      assert(vim.wait(3000, function() return SOLNvimReader ~= original_reader end, 10), 'marker jump was not acknowledged')
      reader = SOLNvimReader
      assert(reader.capture().cursor_offset == 0)
      reader.restore(prior)
      reader.help()
      api.nvim_feedkeys(api.nvim_replace_termcodes('<Esc>', true, false, true), 'xt', false)
      reader.context()
      api.nvim_feedkeys(api.nvim_replace_termcodes('<Esc>', true, false, true), 'xt', false)
      report({status = 'reopened', packet = reader.capture()})
      api.nvim_feedkeys('q', 'xt', false)
      return
    end
    -- Exercise native line, half-window, scope-end and local search mechanics.
    api.nvim_feedkeys('jkhl', 'xt', false)
    api.nvim_feedkeys(api.nvim_replace_termcodes('<C-d><C-u>', true, false, true), 'xt', false)
    api.nvim_feedkeys('Ggg', 'xt', false)
    assert(vim.fn.search('thought', 'W') > 0)
    local cp = reader.source_point(data.records[2].id, 11)
    api.nvim_win_set_cursor(reader.window, {cp.row, cp.byte})
    saved = reader.capture()
    api.nvim_feedkeys('m2', 'xt', false)
    assert(vim.wait(3000, function()
      return reader.marker_slots().slots[2].target == data.records[2].id
    end, 10), 'marker was not immediately saved')
    reader.toggle_mode()
    reader = SOLNvimReader
    assert(reader.mode == 'paragraph')
    api.nvim_feedkeys('99j99k', 'xt', false)
    assert(reader.capture().reference.reference.target_id == data.records[2].id)
    reader.restore(saved)
    local tree = reader.tree()
    api.nvim_feedkeys(api.nvim_replace_termcodes('<Tab>', true, false, true), 'xt', false)
    assert(tree.state().layout == 'horizontal')
    api.nvim_feedkeys(api.nvim_replace_termcodes('<Esc>', true, false, true), 'xt', false)
    assert(vim.deep_equal(reader.capture(), saved))
    report({status = 'wide', xid = assert(vim.env.ALACRITTY_WINDOW_ID), columns = vim.o.columns})
    stage = 1
  end, debug.traceback)
  if not ok then fail(problem) end
end, 200)
timer:start(80, 70, vim.schedule_wrap(function()
  local ok, problem = xpcall(function()
    if stage == 1 and vim.o.columns < 72 then
      assert(vim.deep_equal(saved, reader.capture()), 'resize changed the semantic cursor')
      report({status = 'narrow', columns = vim.o.columns})
      stage = 2
    elseif stage == 2 and vim.o.columns > 72 then
      assert(vim.deep_equal(saved, reader.capture()))
      report({status = 'saved', packet = reader.capture()})
      timer:stop(); timer:close()
      api.nvim_feedkeys('q', 'xt', false)
    end
  end, debug.traceback)
  if not ok then timer:stop(); timer:close(); fail(problem) end
end))
vim.defer_fn(function() fail('owned installed-reader acceptance timed out') end, 14000)
'''


@unittest.skipUnless(os.environ.get("SOL_TEST_LIVE_NVIM_ALACRITTY") == "1",
                     "real installed Neovim/Alacritty workspace proof is explicit opt-in")
class InstalledNeovimAlacrittyTests(CorpusFixture, unittest.TestCase):
    def test_installed_backend_saves_and_reopens_after_native_resize(self):
        if not all(shutil.which(name) for name in ("alacritty", "nvim")) or not os.environ.get("DISPLAY"):
            self.skipTest("installed Neovim, Alacritty, and an X11/XWayland display are required")
        # Native source rows stay long enough to wrap at each tested measure.
        text = ("🙂 The thought of being remains readable. " * 12).strip() + " \u0099"
        self.rewrite_body(text, markdown=("🙂 The *thought* of **being** remains readable. " * 12).strip() + " \u0099")
        records = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().split("\n") if line]
        second = deepcopy(records[1])
        second.update(id="ffffffff-0000-4000-8000-000000000006", order=2)
        records.append(second)
        self.write_records(records)
        before = {path.name: path.read_bytes() for path in self.corpus.iterdir()}
        script, scenario = self.root / "launch.py", self.root / "scenario.lua"
        script.write_text(_LAUNCH)
        scenario.write_text(_SCENARIO)
        configuration = self.root / "alacritty.toml"
        configuration.write_text("[general]\nipc_socket = false\n[window]\ndynamic_title = false\n"
                                 "dimensions = { columns = 100, lines = 28 }\n")
        report = self.root / "report.json"
        environment = dict(os.environ, SOL_CORPUS=str(self.corpus),
                           XDG_CONFIG_HOME=str(self.root / "config"), XDG_DATA_HOME=str(self.root / "data"),
                           XDG_STATE_HOME=str(self.root / "state"), XDG_CACHE_HOME=str(self.root / "cache"),
                           SOL_NVIM_TEST_REPORT=str(report), SOL_NVIM_TEST_SCENARIO=str(scenario))
        for key in ("WAYLAND_DISPLAY", "WAYLAND_SOCKET", "ALACRITTY_SOCKET", "ALACRITTY_WINDOW_ID", "KITTY_WINDOW_ID"):
            environment.pop(key, None)
        x11 = ctypes.CDLL("libX11.so.6")
        x11.XOpenDisplay.argtypes, x11.XOpenDisplay.restype = [ctypes.c_char_p], ctypes.c_void_p
        x11.XResizeWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_uint, ctypes.c_uint]
        x11.XFlush.argtypes, x11.XCloseDisplay.argtypes = [ctypes.c_void_p], [ctypes.c_void_p]
        display = x11.XOpenDisplay(None)
        self.assertTrue(display)
        self.addCleanup(x11.XCloseDisplay, display)
        workspace_dir = self.root / "workspaces"
        for phase, width in (("first", "72"), ("reopen", "40")):
            report.unlink(missing_ok=True)
            process = subprocess.Popen(["alacritty", "--config-file", str(configuration), "--title",
                "SOL installed Neovim isolated acceptance", "-e", sys.executable, "-I", "-B", str(script),
                str(Path(__file__).resolve().parents[1]), str(workspace_dir), width], cwd=self.root,
                env=dict(environment, SOL_NVIM_TEST_PHASE=phase), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            def wait(status):
                deadline = time.monotonic() + 8
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
                        self.fail("Owned reader exited early: " + "".join(process.communicate()))
                    time.sleep(.03)
                size = report.with_suffix(".json.size")
                self.fail("Owned reader did not reach " + status + "; last report: "
                          + (report.read_text() if report.exists() else "none") + "; size: "
                          + (size.read_text() if size.exists() else "none"))
            try:
                if phase == "first":
                    wide = wait("wide")
                    window = int(wide["xid"], 0)
                    self.assertGreater(window, 0)
                    x11.XResizeWindow(display, window, 400, 640); x11.XFlush(display)
                    self.assertLess(wait("narrow")["columns"], 72)
                    x11.XResizeWindow(display, window, 1600, 640); x11.XFlush(display)
                    wait("saved")
                else:
                    wait("reopened")
                stdout, stderr = process.communicate(timeout=8)
                self.assertEqual(process.returncode, 0, stdout + stderr)
            finally:
                if process.poll() is None:
                    process.terminate(); process.communicate(timeout=5)
        from sol.workspace.reader import WorkspaceReader
        from sol.reader import app
        from sol.core.paths import display_path, resolve_path
        with Workspace(workspace_dir / "reading.sqlite3", self.book.corpus_manifest["corpus_id"],
                       self.book.corpus_manifest, read_only=True) as store:
            service = WorkspaceReader(self.book, store, None, resolve_path, display_path,
                                      app.render_passage, 72, False, False)
            actions = ReaderActions(self.book, service)
            actions.restore()
            self.assertEqual(actions.cursor_offset, 11)
            self.assertEqual(actions.snapshot().current.identifier, second["id"])
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.corpus.iterdir()})
