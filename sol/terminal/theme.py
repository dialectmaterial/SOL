"""Three reading presets, sent to the Neovim reader as highlight data only.

Presentation never reaches canonical text, source offsets or workspace records.
No colorscheme file is sourced and the user's terminal theme is not changed;
Lua validates these groups again before applying them to its own session.
"""
from __future__ import annotations

import os
import re

from sol.reader.options import DEFAULT_READER_THEME as DEFAULT_THEME, READER_THEMES as THEMES

LABELS = {"terminal": "Terminal", "dark": "Dark", "paper": "Paper"}

# Highlight groups the reader owns. Lua refuses any other name or attribute.
GROUPS = ("Normal", "SOLPanel", "SOLPanelBorder", "SOLSourceHeading", "SOLSourceWarning",
          "StatusLine", "StatusLineNC", "Visual", "Search", "CurSearch", "IncSearch",
          "CursorLine", "ErrorMsg", "WarningMsg", "NonText", "EndOfBuffer")

# Body text meets WCAG AAA (7:1) against the page and panel; status, warning
# and match text meet at least AA (4.5:1). tests/test_reader_theme.py checks it.
_PALETTES = {
    "dark": {"page": "#1c1b19", "text": "#d9d3c5", "heading": "#efe8d8", "muted": "#9a9384",
             "warning": "#e0a85e", "panel": "#262420", "border": "#4d483f",
             "selection": "#3b4452", "search": "#5a4b25", "search_text": "#efe8d8",
             "current": "#c9a650", "current_text": "#1c1b19"},
    "paper": {"page": "#f5f0e4", "text": "#2a2620", "heading": "#16130f", "muted": "#6a6253",
              "warning": "#8c4a0c", "panel": "#ece5d5", "border": "#b5aa93",
              "selection": "#d3dbe6", "search": "#ead59a", "search_text": "#2a2620",
              "current": "#d9b65e", "current_text": "#16130f"},
}
_HEX = re.compile(r"#[0-9a-f]{6}")
_CUBE = (0, 95, 135, 175, 215, 255)


def _rgb(value):
    if not _HEX.fullmatch(value):
        raise ValueError(f"invalid reader color {value!r}")
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def xterm256(value):
    """Nearest xterm-256 cube or grey entry, for terminals without 24-bit color."""
    red, green, blue = _rgb(value)
    def nearest(channel):
        return min(range(6), key=lambda index: abs(_CUBE[index] - channel))
    cube = tuple(nearest(channel) for channel in (red, green, blue))
    cube_rgb = tuple(_CUBE[index] for index in cube)
    grey_index = min(23, max(0, round(((red + green + blue) / 3 - 8) / 10)))
    grey_rgb = (8 + 10 * grey_index,) * 3
    def distance(other):
        return sum((a - b) ** 2 for a, b in zip((red, green, blue), other))
    if distance(grey_rgb) < distance(cube_rgb):
        return 232 + grey_index
    return 16 + 36 * cube[0] + 6 * cube[1] + cube[2]


def contrast(foreground, background):
    """WCAG 2 contrast ratio between two #rrggbb colors."""
    def luminance(value):
        channels = [channel / 255 for channel in _rgb(value)]
        channels = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def color_capability(environment=None):
    """Return truecolor, 256 or basic from standard terminal declarations."""
    environment = os.environ if environment is None else environment
    if environment.get("COLORTERM", "").lower() in {"truecolor", "24bit"}:
        return "truecolor"
    term = environment.get("TERM", "").lower()
    if "256color" in term or term.startswith(("alacritty", "xterm-kitty", "wezterm", "foot")):
        return "256"
    return "basic"


def _color(fg=None, bg=None, **attributes):
    group = dict(attributes)
    if fg is not None:
        group.update(fg=fg, ctermfg=xterm256(fg))
    if bg is not None:
        group.update(bg=bg, ctermbg=xterm256(bg))
    return group


def _palette_groups(p):
    return {
        "Normal": _color(p["text"], p["page"]),
        "SOLPanel": _color(p["text"], p["panel"]),
        "SOLPanelBorder": _color(p["border"], p["panel"]),
        "SOLSourceHeading": _color(p["heading"], bold=True),
        "SOLSourceWarning": _color(p["warning"]),
        "StatusLine": _color(p["muted"], p["page"]),
        "StatusLineNC": _color(p["muted"], p["page"]),
        "Visual": _color(bg=p["selection"]),
        "Search": _color(p["search_text"], p["search"]),
        "CurSearch": _color(p["current_text"], p["current"], bold=True),
        "IncSearch": _color(p["current_text"], p["current"], bold=True),
        "CursorLine": _color(bg=p["selection"]),
        "ErrorMsg": _color(p["warning"], bold=True),
        "WarningMsg": _color(p["warning"]),
        "NonText": _color(p["muted"]),
        "EndOfBuffer": _color(p["page"]),
    }


def _terminal_groups(colored):
    """Inherit the host's foreground, background and palette; attributes carry structure."""
    warning = {"ctermfg": 1} if colored else {"bold": True}
    return {
        "Normal": {}, "SOLPanel": {}, "SOLPanelBorder": {}, "NonText": {}, "EndOfBuffer": {},
        "StatusLine": {}, "StatusLineNC": {},
        "SOLSourceHeading": {"bold": True},
        "SOLSourceWarning": dict(warning),
        "Visual": {"reverse": True}, "Search": {"reverse": True},
        "CurSearch": {"reverse": True, "bold": True}, "IncSearch": {"reverse": True, "bold": True},
        "CursorLine": {"reverse": True},
        "ErrorMsg": {**warning, "bold": True}, "WarningMsg": dict(warning),
    }


def theme_payload(active=DEFAULT_THEME, environment=None):
    """All three presets, so the reader can switch without a Python round trip.

    Without 256-color support, Dark and Paper fall back to Terminal visibly
    rather than drawing approximate colors. NO_COLOR removes Terminal's accent.
    """
    if active not in THEMES:
        raise ValueError(f"reader theme must be one of: {', '.join(THEMES)}")
    environment = os.environ if environment is None else environment
    capability = color_capability(environment)
    colored = not environment.get("NO_COLOR")
    presets = [{"name": "terminal", "label": LABELS["terminal"],
                "groups": _terminal_groups(colored), "notice": ""}]
    for name in ("dark", "paper"):
        if capability == "basic":
            presets.append({"name": name, "label": LABELS[name], "groups": _terminal_groups(colored),
                            "notice": f"{LABELS[name]} needs a 256-color or truecolor terminal; "
                                      "showing Terminal colors instead."})
        else:
            presets.append({"name": name, "label": LABELS[name],
                            "groups": _palette_groups(_PALETTES[name]), "notice": ""})
    return {"active": active, "truecolor": capability == "truecolor", "presets": presets}
