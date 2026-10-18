"""ESSENCE's Textual shell: screens, leaving, saved state and the context file."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.essence import tui
from sol.essence.tui import __main__ as entry
from sol.essence.tui.context import check_context, read_context, write_context

TARGET = "bbbbbbbb-0000-4000-8000-000000000002"


def context(state_file=None):
    return {"version": 1, "reference": {"reference": {"target_id": TARGET}}, "cursor_offset": 3,
            "selection": None, "label": "Invented section | p. 7", "corpus": "/invented",
            "state_file": None if state_file is None else str(state_file)}


class ContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_written_context_is_private_and_round_trips(self):
        fields = {key: value for key, value in context().items() if key != "version"}
        path = write_context(self.root, **fields)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(read_context(path), context())
        self.assertNotEqual(write_context(self.root, **fields), path)  # Never overwrites.

    def test_malformed_contexts_are_refused(self):
        for change in ({"version": 2}, {"cursor_offset": -1}, {"cursor_offset": True}, {"reference": {}},
                       {"selection": "text"}, {"label": None}, {"extra": 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                check_context({**context(), **change})

    def test_importing_the_package_does_not_import_textual(self):
        code = "import sys; import sol.essence.tui, sol.essence.tui.context; print('textual' in sys.modules)"
        import subprocess
        import sys
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "False")

    def test_missing_textual_is_explained_not_a_traceback(self):
        path = self.root / "context.json"
        path.write_text(json.dumps(context()), encoding="utf-8")
        with patch.object(entry, "textual_available", return_value=False), \
                patch("sys.stderr") as stderr:
            self.assertEqual(entry.main(["--context", str(path)]), 2)
        self.assertIn("essence", "".join(call.args[0] for call in stderr.write.call_args_list))
        self.assertIn("pipx inject", tui.TEXTUAL_HINT)


@unittest.skipUnless(tui.textual_available(), "the essence extra (Textual) is not installed")
class EssenceAppTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-essence-")
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name) / "state" / "investigation.json"

    async def test_screens_switch_and_leaving_saves_only_the_open_screen(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context(self.state))
        async with app.run_test(size=(60, 24)) as pilot:
            origin = str(app.query_one("#origin").render())
            self.assertIn("Invented section | p. 7", origin)
            self.assertIn(TARGET[:8], origin)
            for key, screen in (("3", "experiment"), ("1", "encyclopedia"), ("4", "results")):
                await pilot.press(key)
                self.assertEqual(app.query_one("#screens").active, screen)
            await pilot.press("q")
        self.assertEqual(json.loads(self.state.read_text()),
                         {"version": 1, "screen": "results", "origin": TARGET})
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        # The next opening returns to the same screen, at any size.
        app = EssenceApp(context(self.state))
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            self.assertEqual(app.query_one("#screens").active, "results")
            await pilot.press("ctrl+q")
        self.assertFalse(app.is_running)

    async def test_temporary_sessions_save_nothing_and_unreadable_state_is_ignored(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test() as pilot:
            await pilot.press("2", "q")
        self.assertFalse(self.state.exists())
        self.state.parent.mkdir(parents=True)
        self.state.write_text("not json", encoding="utf-8")
        app = EssenceApp(context(self.state))
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(app.query_one("#screens").active, "encyclopedia")
            await pilot.press("q")

    async def test_the_command_palette_is_off(self):
        from sol.essence.tui.app import EssenceApp

        app = EssenceApp(context())
        async with app.run_test() as pilot:
            await pilot.press("ctrl+p")
            self.assertEqual(len(app.screen_stack), 1)
            await pilot.press("q")


if __name__ == "__main__":
    unittest.main()
