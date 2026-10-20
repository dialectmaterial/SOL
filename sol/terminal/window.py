"""sol-window: the reader in a window of its own, set for reading.

The usual terminal keeps its font. This opens a new foot, kitty or Alacritty
window with Libertinus Mono, a monospaced book face bundled with SOL (SIL Open
Font License, fonts/OFL.txt), and SOL's Paper theme unless another is asked
for. The font is found through a private fontconfig file that adds SOL's font
directory to the system configuration; nothing is installed and no terminal
or fontconfig setting of the user's is changed. A proportional face such as
Source Serif cannot be used: terminals give every letter the same width.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from sol.reader.options import READER_THEMES
from sol.terminal.theme import _PALETTES

FONT = "Libertinus Mono"
FONT_DIRECTORY = Path(__file__).resolve().parent / "fonts"
TERMINALS = ("foot", "kitty", "alacritty")
DEFAULT_THEME = "paper"
DEFAULT_SIZE = 13


def font_config(cache_home=None):
    """Write the private fontconfig file that adds SOL's fonts; return its path."""
    cache = Path(cache_home or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "sol"
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = cache / "fonts.conf"
    path.write_text('<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
                    '<fontconfig>\n  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
                    f"  <dir>{_xml(str(FONT_DIRECTORY))}</dir>\n</fontconfig>\n", encoding="utf-8")
    return path


def _xml(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _foot_colors_section(which=shutil.which, run=subprocess.run):
    """foot 1.26 split [colors] into [colors-dark] and [colors-light]."""
    try:
        version = run([which("foot"), "--version"], capture_output=True, text=True, timeout=5).stdout
        major, minor = (int(part) for part in version.split()[2].split(".")[:2])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError, TypeError):
        return "colors-dark"
    return "colors-dark" if (major, minor) >= (1, 26) else "colors"


def terminal_command(terminal, inner, *, size=DEFAULT_SIZE, theme=DEFAULT_THEME, colors_section="colors-dark"):
    """The command that opens `terminal` running `inner` in SOL's font and page colors."""
    palette = _PALETTES.get(theme)
    if terminal == "foot":
        command = ["foot", "--app-id", "sol", "--title", "SOL", "-o", f"main.font={FONT}:size={size}",
                   "-o", "main.pad=28x20"]
        if palette:
            command += ["-o", f"{colors_section}.background={palette['page'][1:]}",
                        "-o", f"{colors_section}.foreground={palette['text'][1:]}"]
        return command + inner
    if terminal == "kitty":
        command = ["kitty", "--class", "sol", "--title", "SOL", "-o", f"font_family={FONT}",
                   "-o", f"font_size={size}", "-o", "window_padding_width=14"]
        if palette:
            command += ["-o", f"background={palette['page']}", "-o", f"foreground={palette['text']}"]
        return command + inner
    if terminal == "alacritty":
        command = ["alacritty", "--class", "sol", "--title", "SOL",
                   "-o", f'font.normal.family="{FONT}"', "-o", f"font.size={size}",
                   "-o", "window.padding.x=28", "-o", "window.padding.y=20"]
        if palette:
            command += ["-o", f'colors.primary.background="{palette["page"]}"',
                        "-o", f'colors.primary.foreground="{palette["text"]}"']
        return command + ["-e"] + inner
    raise ValueError(f"unsupported terminal: {terminal}")


def main(arguments=None, *, which=shutil.which, popen=subprocess.Popen):
    parser = argparse.ArgumentParser(
        prog="sol-window", description="Open the SOL reader in its own window, in a book face.",
        epilog="Other options are passed to sol, e.g. sol-window -w NAME.")
    parser.add_argument("--terminal", choices=TERMINALS, help="default: the first of foot, kitty, alacritty found")
    parser.add_argument("--font-size", type=int, default=DEFAULT_SIZE, metavar="POINTS")
    parser.add_argument("--theme", choices=READER_THEMES, default=DEFAULT_THEME,
                        help=f"reader theme for this window (default: {DEFAULT_THEME})")
    options, rest = parser.parse_known_args(arguments)
    if not 6 <= options.font_size <= 48:
        parser.error("--font-size must be between 6 and 48")
    terminal = options.terminal or next((name for name in TERMINALS if which(name)), None)
    if terminal is None or which(terminal) is None:
        print("sol-window: needs foot, kitty or Alacritty; install one, or run sol in your terminal.",
              file=sys.stderr)
        return 2
    inner = [sys.executable, "-m", "sol", "--theme", options.theme, *rest]
    command = terminal_command(terminal, inner, size=options.font_size, theme=options.theme,
                               colors_section=_foot_colors_section(which) if terminal == "foot" else "")
    environment = {**os.environ, "FONTCONFIG_FILE": str(font_config())}
    # The window outlives this command, which returns to the shell at once.
    popen(command, env=environment, start_new_session=True,
          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
