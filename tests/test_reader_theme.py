"""Reader presets are presentation data: legible, degradable and explicitly saved."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fixtures_corpus import write_runtime_corpus
from sol.core import config
from sol.corpus import contract
from sol.reader import app
from sol.reader.options import LEGACY_READER_THEMES, READER_THEMES
from sol.terminal import theme


TRUECOLOR = {"COLORTERM": "truecolor", "TERM": "alacritty"}


class ThemePresetTests(unittest.TestCase):
    def preset(self, name, environment=TRUECOLOR):
        payload = theme.theme_payload(name, environment)
        return next(row for row in payload["presets"] if row["name"] == name)["groups"]

    def test_every_preset_defines_exactly_the_owned_groups(self):
        payload = theme.theme_payload("mocha", TRUECOLOR)
        self.assertEqual([row["name"] for row in payload["presets"]], list(READER_THEMES))
        self.assertEqual(payload["active"], "mocha")
        for row in payload["presets"]:
            with self.subTest(preset=row["name"]):
                self.assertEqual(set(row["groups"]), set(theme.GROUPS))

    def test_catppuccin_presets_meet_reading_contrast(self):
        for name in ("mocha", "latte", "paper", "night"):
            groups = self.preset(name)
            page, panel = groups["Normal"]["bg"], groups["SOLPanel"]["bg"]
            with self.subTest(preset=name):
                # Body text: WCAG AAA. Secondary text and matches: at least AA.
                self.assertGreaterEqual(theme.contrast(groups["Normal"]["fg"], page), 7)
                self.assertGreaterEqual(theme.contrast(groups["SOLPanel"]["fg"], panel), 7)
                for group in ("SOLSourceHeading", "SOLSourceWarning", "StatusLine", "NonText"):
                    self.assertGreaterEqual(theme.contrast(groups[group]["fg"], page), 4.5, group)
                self.assertGreaterEqual(theme.contrast(groups["SOLSourceWarning"]["fg"], panel), 4.5)
                self.assertGreaterEqual(theme.contrast(groups["Normal"]["fg"], groups["Visual"]["bg"]), 4.5)
                for group in ("Search", "CurSearch"):
                    self.assertGreaterEqual(theme.contrast(groups[group]["fg"], groups[group]["bg"]), 4.5, group)

    def test_terminal_preset_inherits_host_colors(self):
        groups = self.preset("terminal")
        self.assertEqual(groups["Normal"], {})
        self.assertFalse(any(key in group for group in groups.values() for key in ("fg", "bg", "ctermbg")))
        self.assertEqual(groups["SOLSourceWarning"], {"ctermfg": 1})
        self.assertEqual(self.preset("terminal", {**TRUECOLOR, "NO_COLOR": "1"})["SOLSourceWarning"], {"bold": True})

    def test_every_color_has_a_256_color_fallback(self):
        for name in ("mocha", "latte", "paper", "night"):
            for group, attributes in self.preset(name).items():
                for channel in ("fg", "bg"):
                    if channel in attributes:
                        self.assertEqual(attributes["cterm" + channel], theme.xterm256(attributes[channel]), group)
        self.assertEqual(theme.xterm256("#000000"), 16)
        self.assertEqual(theme.xterm256("#ffffff"), 231)
        self.assertEqual(theme.xterm256("#808080"), 244)
        self.assertEqual(theme.xterm256("#ff0000"), 196)
        with self.assertRaises(ValueError):
            theme.xterm256("red")

    def test_capability_detection_and_basic_terminal_fallback(self):
        self.assertEqual(theme.color_capability(TRUECOLOR), "truecolor")
        self.assertEqual(theme.color_capability({"TERM": "xterm-256color"}), "256")
        self.assertEqual(theme.color_capability({"TERM": "linux"}), "basic")
        self.assertFalse(theme.theme_payload("latte", {"TERM": "xterm-256color"})["truecolor"])
        basic = theme.theme_payload("latte", {"TERM": "linux"})
        paper = next(row for row in basic["presets"] if row["name"] == "latte")
        self.assertEqual(paper["groups"], self.preset("terminal", {"TERM": "linux"}))
        self.assertIn("256-color", paper["notice"])

    def test_catppuccin_colors_are_the_published_palette(self):
        self.assertEqual(self.preset("mocha")["Normal"], theme._color("#cdd6f4", "#1e1e2e"))
        self.assertEqual(self.preset("latte")["Normal"], theme._color("#4c4f69", "#eff1f5"))

    def test_unknown_theme_is_refused(self):
        with self.assertRaisesRegex(ValueError, "mocha, latte, paper, night, terminal"):
            theme.theme_payload("sepia", TRUECOLOR)


class ThemeConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-theme-config-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        guard = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "configuration")}, clear=True)
        guard.start()
        self.addCleanup(guard.stop)

    def saved(self):
        return json.loads(config.config_path().read_text(encoding="utf-8"))

    def test_theme_is_absent_until_explicitly_saved(self):
        self.assertIsNone(config.configured_theme(READER_THEMES))
        self.assertFalse((self.root / "configuration").exists())
        config.save_theme("latte", READER_THEMES)
        self.assertEqual(config.configured_theme(READER_THEMES), "latte")
        self.assertEqual(self.saved(), {"version": 1, "theme": "latte"})
        # A theme-only file is not a broken corpus pointer.
        self.assertIsNone(config.configured_corpus())

    def test_theme_and_corpus_settings_preserve_each_other(self):
        corpus = self.root / "corpus"
        with patch("sol.core.corpus.load_corpus_book"):
            config.save_corpus(corpus)
        config.save_theme("mocha", READER_THEMES)
        self.assertEqual(self.saved(), {"version": 1, "corpus": str(corpus.resolve()), "theme": "mocha"})
        with patch("sol.core.corpus.load_corpus_book"):
            config.save_corpus(corpus)
        self.assertEqual(self.saved()["theme"], "mocha")
        self.assertEqual(config.configured_corpus(), corpus.resolve())

    def test_dark_saved_before_catppuccin_reads_as_mocha_and_paper_is_sols_own(self):
        for saved, current in (("dark", "mocha"), ("paper", "paper")):
            config.save_theme(saved, (saved,))
            self.assertEqual(config.configured_theme(READER_THEMES, LEGACY_READER_THEMES), current)

    def test_invalid_saved_theme_explains_the_reset(self):
        path = config.config_path()
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"version": 1, "theme": "sepia"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sol --set-theme NAME"):
            config.configured_theme(READER_THEMES)
        # Malformed values get the same diagnostic, not a TypeError from the rename lookup.
        for malformed in ([], {}, ["dark"]):
            path.write_text(json.dumps({"version": 1, "theme": malformed}), encoding="utf-8")
            with self.subTest(theme=malformed), self.assertRaisesRegex(ValueError, "sol --set-theme NAME"):
                config.configured_theme(READER_THEMES, LEGACY_READER_THEMES)
        with self.assertRaises(ValueError):
            config.save_theme("sepia", READER_THEMES)


class ThemeCommandTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-theme-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        corpus = self.root / "corpus"
        write_runtime_corpus(corpus)
        contract.initialize_corpus_identity(corpus)
        guard = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "config"),
                                        "XDG_DATA_HOME": str(self.root / "data"), "SOL_CORPUS": str(corpus)})
        guard.start()
        self.addCleanup(guard.stop)

    def call(self, arguments):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            status = app.main(arguments)
        return status, output.getvalue(), error.getvalue()

    def reader_theme(self, arguments):
        with patch("sol.being.neovim.host.validate_environment"), \
                patch.object(app, "run_reader", return_value=0) as view:
            status, _, error = self.call(arguments)
        self.assertEqual(status, 0, error)
        return view.call_args.kwargs["theme"]

    def test_set_theme_saves_without_loading_a_corpus(self):
        with patch.dict(os.environ, {"SOL_CORPUS": str(self.root / "absent")}):
            status, output, error = self.call(["--set-theme", "latte", "--json"])
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)["theme"], "latte")
        self.assertEqual(config.configured_theme(READER_THEMES), "latte")

    def test_saved_theme_is_the_default_and_flag_overrides_it_for_one_session(self):
        self.assertEqual(self.reader_theme(["-n"]), "mocha")
        self.call(["--set-theme", "latte"])
        self.assertEqual(self.reader_theme(["-n"]), "latte")
        self.assertEqual(self.reader_theme(["-n", "--theme", "terminal"]), "terminal")
        self.assertEqual(config.configured_theme(READER_THEMES), "latte")

    def test_theme_is_reader_only(self):
        status, _, error = self.call(["-r", "--theme", "mocha"])
        self.assertNotEqual(status, 0)
        self.assertIn("--theme selects the interactive reader", error)


if __name__ == "__main__":
    unittest.main()
