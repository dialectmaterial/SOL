"""BEING's ordinary reader has no terminal-hosting dependency.

These checks exercise generic preflight and the real optional toolkit. They are
not manual emulator checks: the renderer test uses synthetic terminal output.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments.reader_surfaces.baseline import emphasis_style, validate_reader_environment


class OrdinaryTerminalTests(unittest.TestCase):
    def test_preflight_accepts_capable_terminals_without_kitty_environment(self):
        tty = SimpleNamespace(isatty=lambda: True)
        for term in ("alacritty", "xterm-256color", "xterm-kitty", "unknown-terminal"):
            with self.subTest(term=term), \
                    patch.dict(os.environ, {"TERM": term, "PATH": ""}, clear=True), \
                    patch("experiments.reader_surfaces.baseline.sys.stdin", tty), \
                    patch("experiments.reader_surfaces.baseline.sys.stdout", tty), \
                    patch("experiments.reader_surfaces.baseline._load_toolkit") as toolkit:
                validate_reader_environment()
                toolkit.assert_called_once_with()
                self.assertNotIn("KITTY_WINDOW_ID", os.environ)

    def test_semantic_emphasis_maps_to_standard_terminal_styles(self):
        for term, expected in (("alacritty", "italic"), ("xterm-256color", "italic"),
                               ("xterm-kitty", "italic"), ("unknown-terminal", "underline"),
                               ("vt100", "underline")):
            with self.subTest(term=term), patch.dict(os.environ, {"TERM": term}, clear=True):
                self.assertEqual(emphasis_style(), expected)
                self.assertEqual(emphasis_style("italic"), "italic")
                self.assertEqual(emphasis_style("underline"), "underline")

    @unittest.skipUnless(importlib.util.find_spec("prompt_toolkit") and
                         importlib.util.find_spec("markdown_it"),
                         "optional reader dependencies unavailable")
    def test_real_reader_runs_without_kitty_imports_processes_or_executable(self):
        repository = Path(__file__).resolve().parents[1]
        statement = r'''
import asyncio, builtins, json, os, subprocess, sys
sys.path.insert(0, str(__import__('pathlib').Path.cwd() / 'tests'))
original_import = builtins.__import__
def without_host_modules(name, *args, **kwargs):
    if name in {'sol.terminal.kitty', 'sol.terminal.handoff', 'sol.terminal.source'}:
        raise AssertionError('Generic reader imported optional host: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_host_modules
def no_child_process(*args, **kwargs):
    raise AssertionError('Generic reader launched a child process')
subprocess.Popen = no_child_process
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from sol.reader.actions import ReaderActions
from experiments.reader_surfaces.baseline import ReaderView
from test_reader_view import reader_book

async def check():
    actions = ReaderActions(reader_book())
    source = actions.read(first=True).text
    with create_pipe_input() as pipe:
        view = ReaderView(actions, input=pipe, output=DummyOutput())
        task = asyncio.create_task(view.application.run_async())
        deadline = asyncio.get_running_loop().time() + 2
        while view.body.window.render_info is None:
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError('Generic reader did not render')
            await asyncio.sleep(.01)
        pipe.send_text('vlll')
        while actions.selection is None or actions.selection.end != 3:
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError('Generic reader did not select source text')
            await asyncio.sleep(.01)
        assert actions.selection.text == source[:3]
        assert view.body.text == source
        assert 'sol.terminal.kitty' not in sys.modules
        pipe.send_text('\x03')
        assert await asyncio.wait_for(task, 2) == 0
        print(json.dumps({'emphasis': view.emphasis, 'selected': actions.selection.end}))
asyncio.run(check())
'''
        for term, expected in (("alacritty", "italic"), ("xterm-kitty", "italic"),
                               ("unknown-terminal", "underline")):
            environment = dict(os.environ, TERM=term, PATH="")
            for name in tuple(environment):
                if name.startswith("KITTY_"):
                    environment.pop(name)
            with self.subTest(term=term):
                completed = subprocess.run([sys.executable, "-B", "-c", statement],
                                           cwd=repository, env=environment,
                                           capture_output=True, text=True, timeout=10)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout),
                                 {"emphasis": expected, "selected": 3})


if __name__ == "__main__":
    unittest.main()
