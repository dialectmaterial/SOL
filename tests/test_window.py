"""sol-window: its command lines and private font configuration, without opening a window."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import re
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.being.neovim import window


class WindowTests(unittest.TestCase):
    def test_the_bundled_font_and_its_license_ship_with_sol(self):
        self.assertTrue((window.FONT_DIRECTORY / "LibertinusMono-Regular.ttf").is_file())
        self.assertIn("SIL OPEN FONT LICENSE", (window.FONT_DIRECTORY / "OFL.txt").read_text(encoding="utf-8"))

    def test_font_config_adds_sols_fonts_to_the_system_configuration(self):
        with tempfile.TemporaryDirectory() as cache:
            text = window.font_config(cache).read_text(encoding="utf-8")
        self.assertIn("<include ignore_missing=\"yes\">/etc/fonts/fonts.conf</include>", text)
        self.assertIn(f"<dir>{window.FONT_DIRECTORY}</dir>", text)

    def test_each_terminal_gets_the_font_size_and_page_colors(self):
        inner = ["python", "-m", "sol", "--theme", "paper"]
        foot = window.terminal_command("foot", inner, size=14, theme="paper")
        self.assertIn("main.font=Libertinus Mono:size=14", foot)
        self.assertIn("colors-dark.background=f3f0e6", foot)
        self.assertEqual(foot[-len(inner):], inner)
        kitty = window.terminal_command("kitty", inner, theme="night")
        self.assertIn("background=#1b1820", kitty)
        alacritty = window.terminal_command("alacritty", inner)
        self.assertEqual(alacritty[-len(inner) - 1:], ["-e", *inner])
        # Terminal keeps the user's own colors.
        self.assertFalse(any("background" in part for part in window.terminal_command("foot", inner, theme="terminal")))

    def test_main_opens_a_detached_window_with_the_reader(self):
        launched = []
        def popen(command, **options):
            launched.append((command, options))
        with tempfile.TemporaryDirectory() as cache, patch.dict("os.environ", {"XDG_CACHE_HOME": cache}):
            status = window.main(["--terminal", "foot", "--workspace", "study"], which=lambda name: f"/usr/bin/{name}",
                                 popen=popen)
            self.assertTrue(Path(launched[0][1]["env"]["FONTCONFIG_FILE"]).is_file())
        self.assertEqual(status, 0)
        command, options = launched[0]
        self.assertEqual(command[-6:], [sys.executable, "-m", "sol", "--theme", "paper", "--workspace", "study"][-6:])
        self.assertTrue(options["start_new_session"])

    def test_font_cache_failure_is_reported_without_starting_a_window(self):
        error = StringIO()
        with patch.object(window, "font_config", side_effect=PermissionError("invented font cache refusal")), \
                redirect_stderr(error), patch.object(window.subprocess, "Popen") as launched:
            status = window.main(["--terminal", "kitty"], which=lambda name: "/invented/kitty", popen=launched)
        self.assertEqual(status, 2)
        self.assertIn("sol-window:", error.getvalue())
        self.assertIn("invented font cache refusal", error.getvalue())
        launched.assert_not_called()

    def test_terminal_launch_failure_is_reported_without_a_traceback(self):
        error = StringIO()
        with tempfile.TemporaryDirectory() as cache, patch.dict("os.environ", {"XDG_CACHE_HOME": cache}), \
                redirect_stderr(error), patch.object(window.subprocess, "Popen", side_effect=FileNotFoundError(
                    "invented missing terminal")) as launched:
            status = window.main(["--terminal", "kitty"], which=lambda name: "/invented/kitty", popen=launched)
        self.assertEqual(status, 2)
        self.assertIn("sol-window:", error.getvalue())
        self.assertIn("invented missing terminal", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())

    def test_help_workspace_example_is_accepted_by_sol(self):
        from sol.app.options import build_parser, validate_options
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as caught:
            window.main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        example = re.search(r"e\.g\. (sol-window .*?)\.", output.getvalue()).group(1)
        args = build_parser().parse_args(shlex.split(example)[1:])
        validate_options(args)
        self.assertEqual(args.workspace, "NAME")

    def test_no_supported_terminal_is_reported(self):
        self.assertEqual(window.main([], which=lambda name: None, popen=lambda *a, **k: None), 2)


if __name__ == "__main__":
    unittest.main()
