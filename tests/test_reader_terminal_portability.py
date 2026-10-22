"""Real native TTY checks, without a GUI or terminal-family requirements.

These drive keys programmatically; they do not claim human visual acceptance.
"""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

from test_reader_surface_neovim import invented_sample, neovim_environment

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''
import sys
sys.path.insert(0, sys.argv[1])
from sol.being.neovim import host as neovim
from sol.being.neovim import channel as reader_channel
from sol.reader import app
original = reader_channel.subprocess.Popen
def launch(command, **options):
    if command[-1] == neovim._LOAD_ADAPTER:
        command = [*command, '-c', 'lua dofile(vim.env.SOL_TEST_SCENARIO)']
    return original(command, **options)
reader_channel.subprocess.Popen = launch
raise SystemExit(app.main(['-n', '--corpus', sys.argv[2]]))
'''
SCENARIO = '''
vim.defer_fn(function()
  local ok, problem = xpcall(function()
    local r = SOLNvimReader
    assert(vim.fn.has('ttyin') == 1 and vim.fn.has('ttyout') == 1)
    assert(not vim.env.KITTY_WINDOW_ID)
    local first, second = r.records[1].id, r.records[2].id
    vim.api.nvim_feedkeys('n', 'xt', false)
    assert(r.capture().reference.reference.target_id == second)
    vim.api.nvim_feedkeys('b', 'xt', false)
    assert(r.capture().reference.reference.target_id == first)
    vim.api.nvim_feedkeys('p99j99k', 'xt', false)
    r = SOLNvimReader
    assert(r.mode == 'paragraph' and r.capture().reference.reference.target_id == first)
    local before = r.capture()
    vim.api.nvim_feedkeys('f', 'xt', false)
    r = SOLNvimReader
    assert(vim.deep_equal(before, r.capture()))
    local tree = r.tree()
    local selected = tree.state().selected
    vim.o.columns = 40
    vim.api.nvim_exec_autocmds('VimResized', {})
    assert(tree.state().selected == selected)
    vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes('<Esc>', true, false, true), 'xt', false)
    assert(vim.deep_equal(before, r.capture()))
    vim.fn.writefile({vim.json.encode({ok = true, term = vim.env.TERM})}, vim.env.SOL_TEST_REPORT)
    vim.api.nvim_feedkeys(':q\\r', 't', false)
  end, debug.traceback)
  if not ok then
    vim.fn.writefile({vim.json.encode({ok = false, error = tostring(problem)})}, vim.env.SOL_TEST_REPORT)
    vim.cmd('cquit 1')
  end
end, 150)
'''


@unittest.skipUnless(shutil.which('nvim'), 'installed Neovim required; tests never install it')
class ReaderTerminalPortabilityTests(unittest.TestCase):
    def test_default_reader_in_xterm_vt100_and_screen_ttys(self):
        for terminal in ('xterm-256color', 'vt100', 'screen-256color'):
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                corpus, _ = invented_sample(root)
                scenario, report = root / 'scenario.lua', root / 'report.json'
                scenario.write_text(SCENARIO)
                environment = neovim_environment(root)
                environment.update(TERM=terminal, SOL_TEST_SCENARIO=str(scenario), SOL_TEST_REPORT=str(report))
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 28, 100, 0, 0))
                process = subprocess.Popen([sys.executable, '-I', '-B', '-c', PROGRAM, str(ROOT), str(corpus)],
                    stdin=slave, stdout=slave, stderr=slave, env=environment, cwd=root, start_new_session=True)
                os.close(slave)
                screen = bytearray()
                try:
                    deadline = time.monotonic() + 10
                    while process.poll() is None and time.monotonic() < deadline:
                        if select.select([master], [], [], .05)[0]:
                            try:
                                screen.extend(os.read(master, 65536))
                            except OSError:
                                break
                    self.assertEqual(process.wait(timeout=2), 0, bytes(screen)[-3000:])
                    self.assertTrue(report.exists(), bytes(screen)[-3000:])
                    result = json.loads(report.read_text())
                    self.assertTrue(result['ok'], result)
                    self.assertFalse((root / 'data' / 'sol' / 'workspaces').exists())
                finally:
                    if process.poll() is None:
                        process.terminate(); process.wait(timeout=3)
                    os.close(master)
