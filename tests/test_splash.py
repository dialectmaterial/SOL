"""The opening screen: its frames, the movement, and that it never blocks the reader."""
import os
import unittest
from unittest.mock import patch

from sol.terminal import splash


class FrameTests(unittest.TestCase):
    def test_being_and_nothing_part_and_vanish_into_becoming(self):
        apart, moments = splash._movement(0)
        self.assertEqual((apart[0], apart[-1]), ("●", "○"))
        self.assertEqual(moments, ("Being", "Nothing"))
        together, moments = splash._movement(splash.PERIOD / 2)
        self.assertEqual(together.count("◉"), 1)
        self.assertNotIn("●", together)
        self.assertEqual(moments, ("Becoming",))
        # Never wider than the track, at any moment.
        for step in range(50):
            line, _ = splash._movement(step * splash.PERIOD / 50)
            self.assertEqual(len(line), splash.TRACK)

    def test_full_title_in_the_theme_colors_when_it_fits(self):
        text = splash.frame(0.3, 120, 40, "paper")
        self.assertIn(splash.TITLE[7], text)  # ORGANIZES
        self.assertIn(splash.SUBTITLE, text)
        self.assertIn("\x1b[48;2;243;240;230m", text)  # Paper's page
        self.assertIn("\x1b[38;2;85;48;138m", text)  # the Actual Spirit purple

    def test_small_terminals_get_a_compact_title_and_terminal_theme_no_colors(self):
        text = splash.frame(0.3, 60, 20, "terminal")
        self.assertIn("S O L", text)
        self.assertNotIn(splash.TITLE[7], text)
        self.assertNotIn("38;2;", text)


class LifecycleTests(unittest.TestCase):
    def test_not_shown_without_a_terminal_or_when_turned_off(self):
        with patch.dict(os.environ, {"SOL_NO_SPLASH": "1"}):
            splash.start("mocha")
        self.assertIsNone(splash._current)
        with patch.object(splash.sys, "__stdout__") as stdout:
            stdout.isatty.return_value = False
            splash.start("mocha")
        self.assertIsNone(splash._current)
        # Stopping or handing off with nothing shown does nothing.
        splash.stop()
        splash.handoff()

    def test_handoff_leaves_the_frame_and_stop_restores_the_screen(self):
        read, write = os.pipe()
        self.addCleanup(os.close, read)
        try:
            for restore in (False, True):
                with self.subTest(restore=restore):
                    shown = splash.Splash("night", output=write).start()
                    shown.stopping.wait(0.1)
                    shown.finish(restore)
                    self.assertFalse(shown.thread.is_alive())
                    output = os.read(read, 1 << 20).decode("utf-8")
                    self.assertTrue(output.startswith(splash.ENTER))
                    self.assertEqual(output.endswith(splash.LEAVE), restore)
        finally:
            os.close(write)

    def test_a_launch_that_fails_after_handoff_is_still_restored(self):
        read, write = os.pipe()
        self.addCleanup(os.close, read)
        self.addCleanup(os.close, write)
        for neovim_ran in (False, True):
            with self.subTest(neovim_ran=neovim_ran):
                splash._current = splash.Splash("mocha", output=write).start()
                splash.handoff()
                if neovim_ran:
                    splash.forget()
                splash.stop()
                output = os.read(read, 1 << 20).decode("utf-8")
                # Restored only when Neovim never took the screen.
                self.assertEqual(output.endswith(splash.LEAVE), not neovim_ran)
                self.assertIsNone(splash._handed)

    def test_neovim_launch_hands_over_at_the_last_moment(self):
        from pathlib import Path
        from sol.terminal import neovim
        order = []
        with patch.object(neovim, "_isolated_environment", side_effect=lambda *a: order.append("prepared") or {}), \
                patch.object(splash, "handoff", side_effect=lambda: order.append("handoff")), \
                patch.object(neovim.subprocess, "run", side_effect=FileNotFoundError("nvim")):
            with self.assertRaises(FileNotFoundError):
                neovim.launch_payload({"records": []}, "/missing/nvim")
        self.assertEqual(order, ["prepared", "handoff"])


if __name__ == "__main__":
    unittest.main()
