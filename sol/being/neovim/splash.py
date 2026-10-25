"""The opening screen while the reader prepares: SOL's name and Being's first movement.

Shown only on an interactive terminal, from the moment the reader is chosen
until Neovim takes the screen. Two marks travel the line beneath the title,
the full ● of Being and the empty ○ of Nothing; each vanishes into the other
in ◉, Becoming, and they part again. The page and accent colours are the
reader theme's own.

The screen is drawn on the terminal's alternate screen by one daemon thread.
`handoff()` stops it and leaves the last frame for Neovim to replace; `stop()`
also restores the screen, for a prompt or an error. Keys typed meanwhile are
not echoed and are discarded at handoff, so they cannot become commands.
"""
from __future__ import annotations

import math
import os
import sys
import threading
import time

from sol.presentation.theme import _PALETTES

# The maintainer's screensaver title, SOL's recursive name: SOL / ORGANIZES / LOGIC.
_BLOCKS = (
    ("███████╗ ██████╗ ██╗",
     "██╔════╝██╔═══██╗██║",
     "███████╗██║   ██║██║",
     "╚════██║██║   ██║██║",
     "███████║╚██████╔╝███████╗",
     "╚══════╝ ╚═════╝ ╚══════╝"),
    (" ██████╗ ██████╗  ██████╗  █████╗ ███╗   ██╗██╗███████╗███████╗███████╗",
     "██╔═══██╗██╔══██╗██╔════╝ ██╔══██╗████╗  ██║██║╚══███╔╝██╔════╝██╔════╝",
     "██║   ██║██████╔╝██║  ███╗███████║██╔██╗ ██║██║  ███╔╝ █████╗  ███████╗",
     "██║   ██║██╔══██╗██║   ██║██╔══██║██║╚██╗██║██║ ███╔╝  ██╔══╝  ╚════██║",
     "╚██████╔╝██║  ██║╚██████╔╝██║  ██║██║ ╚████║██║███████╗███████╗███████║",
     " ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚══════╝╚══════╝╚══════╝"),
    ("██╗      ██████╗  ██████╗ ██╗ ██████╗",
     "██║     ██╔═══██╗██╔════╝ ██║██╔════╝",
     "██║     ██║   ██║██║  ███╗██║██║",
     "██║     ██║   ██║██║   ██║██║██║",
     "███████╗╚██████╔╝╚██████╔╝██║╚██████╗",
     "╚══════╝ ╚═════╝  ╚═════╝ ╚═╝ ╚═════╝"),
)
TITLE_WIDTH = max(len(line) for block in _BLOCKS for line in block)
# Each block centred over the widest, with a blank line between blocks.
TITLE = tuple(line for number, block in enumerate(_BLOCKS)
              for line in ((("",) if number else ())
                           + tuple(" " * ((TITLE_WIDTH - max(map(len, block))) // 2) + row for row in block)))
MOMENTS = ("Being", "Nothing", "Becoming")
TRACK = 41  # columns the two marks travel
PERIOD = 2.6  # seconds from apart, through Becoming, to apart again
FRAME = 1 / 24

ENTER, LEAVE = "\x1b[?1049h\x1b[?25l", "\x1b[0m\x1b[2J\x1b[?25h\x1b[?1049l"


def frame(t, columns, rows, theme="mocha"):
    """The whole screen at time `t`, as text with escape sequences."""
    palette = _PALETTES.get(theme)
    if palette:
        page = _bg(palette["page"])
        ink, accent, quiet = _fg(palette["text"]), _fg(palette["heading"]), _fg(palette["muted"])
    else:
        page, ink, accent, quiet = "", "", "\x1b[1m", "\x1b[2m"
    reset = "\x1b[0m" + page
    compact = columns < TITLE_WIDTH + 4 or rows < len(TITLE) + 5
    title = ("S O L",) if compact else TITLE
    width = 5 if compact else TITLE_WIDTH
    top = max(0, (rows - len(title) - 4) // 2)
    left = max(0, (columns - width) // 2)
    out = [page, "\x1b[2J"]
    for number, line in enumerate(title):
        out.append(f"\x1b[{top + number + 1};{left + 1}H{accent}{line}{reset}")
    below = top + len(title) + 1
    track = max(1, min(TRACK, columns - 2))
    if track % 2 == 0:
        track -= 1
    line, moment = _movement(t, track)
    out.append(_centred(below + 1, columns, f"{quiet}{line}{reset}".replace("●", f"{accent}●{quiet}")
                        .replace("○", f"{accent}○{quiet}").replace("◉", f"{accent}◉{quiet}"), track))
    labels = "   ".join(f"{accent}{name}{reset}" if name in moment else f"{quiet}{name}{reset}" for name in MOMENTS)
    out.append(_centred(below + 2, columns, labels, sum(map(len, MOMENTS)) + 6))
    return "".join(out) + ink


def _movement(t, width=TRACK):
    """The track at time t, and which moments are present: apart, or one in the other."""
    phase = (t % PERIOD) / PERIOD
    half = (width - 1) // 2
    # Apart at phase 0, meeting at 0.5; eased, so the vanishing lingers.
    distance = round(half * abs(math.cos(math.pi * phase)) ** 1.6)
    cells = ["·" if index % 2 == 0 else " " for index in range(width)]
    if distance == 0:
        cells[half] = "◉"
        return "".join(cells), ("Becoming",)
    cells[half - distance], cells[half + distance] = "●", "○"
    return "".join(cells), ("Being", "Nothing")


def _centred(row, columns, text, visible):
    return f"\x1b[{row};{max(0, (columns - visible) // 2) + 1}H{text}"


def _fg(value):
    return "\x1b[38;2;{};{};{}m".format(*(int(value[i:i + 2], 16) for i in (1, 3, 5)))


def _bg(value):
    return "\x1b[48;2;{};{};{}m".format(*(int(value[i:i + 2], 16) for i in (1, 3, 5)))


class Splash:
    def __init__(self, theme, output=None, now=time.monotonic):
        self.theme, self.now = theme, now
        self.output = output if output is not None else sys.__stdout__.fileno()
        self.stopping, self.thread, self.saved = threading.Event(), None, None

    def start(self):
        self.saved = _quiet_input()
        self._write(ENTER)
        self.thread = threading.Thread(target=self._run, name="sol-splash", daemon=True)
        self.thread.start()
        return self

    def _run(self):
        began, size = self.now(), None
        while not self.stopping.is_set():
            try:
                size = os.get_terminal_size(self.output)
            except OSError:
                size = size or os.terminal_size((80, 24))
            self._write(frame(self.now() - began, size.columns, size.lines, self.theme))
            self.stopping.wait(FRAME)

    def _write(self, text):
        try:
            os.write(self.output, text.encode("utf-8"))
        except OSError:
            self.stopping.set()

    def finish(self, restore):
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(1)
        _restore_input(self.saved)
        if restore:
            self._write(LEAVE)


_current = None
# Handed to Neovim but not yet known to have started: still ours to restore.
_handed = None


def start(theme):
    """Show the opening screen if this is an interactive terminal; never fails the reader."""
    global _current
    if _current is not None or os.environ.get("SOL_NO_SPLASH") or os.environ.get("TERM", "dumb") == "dumb":
        return
    try:
        if not (sys.__stdout__.isatty() and sys.__stdin__.isatty()):
            return
        _current = Splash(theme).start()
    except (OSError, ValueError, AttributeError):
        _current = None


def handoff():
    """Neovim is about to start: stop moving and leave the frame for it to replace.

    Until `forget()` says Neovim ran, `stop()` can still restore the screen.
    """
    global _current, _handed
    current, _current = _current, None
    if current is not None:
        current.finish(restore=False)
        _handed = current


def forget():
    """Neovim ran and restored the terminal itself; nothing is left to undo."""
    global _handed
    _handed = None


def stop():
    """Put the terminal back as it was, for a prompt, an error or an exit."""
    global _current, _handed
    current, _current = _current, None
    handed, _handed = _handed, None
    if current is not None:
        current.finish(restore=True)
    elif handed is not None:
        handed._write(LEAVE)


def _quiet_input():
    """Turn off echo while the screen shows; return what to restore."""
    try:
        import termios
        descriptor = sys.__stdin__.fileno()
        saved = termios.tcgetattr(descriptor)
        quiet = termios.tcgetattr(descriptor)
        quiet[3] &= ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(descriptor, termios.TCSANOW, quiet)
        return descriptor, saved
    except Exception:  # termios.error is not an OSError; no terminal, no change
        return None


def _restore_input(saved):
    if saved is None:
        return
    try:
        import termios
        descriptor, attributes = saved
        # Keys pressed while loading are dropped, not handed to the reader.
        termios.tcflush(descriptor, termios.TCIFLUSH)
        termios.tcsetattr(descriptor, termios.TCSANOW, attributes)
    except Exception:  # termios.error included
        pass
