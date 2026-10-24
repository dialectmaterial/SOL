"""Text drawings for ESSENCE's results: bars, concordance lines, dispersion.

Neovim's terminal shows no image protocol, so every picture here is made of
Unicode block characters. This module holds no Textual code; each function
takes plain values and returns strings, so the drawings are tested without a
terminal.
"""
from __future__ import annotations

import math

EIGHTHS = " ▏▎▍▌▋▊▉█"
SPARKS = "▁▂▃▄▅▆▇█"
EMPTY = "·"  # a dispersion cell with no occurrence


def bar(value, maximum, cells):
    """A left-aligned bar `cells` wide, in eighths of a cell; blank for nothing."""
    if cells <= 0:
        return ""
    if not value or not maximum or value <= 0 or maximum <= 0:
        return " " * cells
    eighths = max(1, min(cells * 8, round(value / maximum * cells * 8)))
    full, rest = divmod(eighths, 8)
    return ("█" * full + (EIGHTHS[rest] if rest else "")).ljust(cells)


def diverging(value, cells=4, scale=3.0):
    """A log ratio as a bar left (below zero) or right (above) of a centre tick.

    Returns (left, right), each `cells` wide; `scale` is the magnitude that
    fills one side. None, for an undefined measure, has no bar.
    """
    if value is None:
        return None
    length = 0 if value == 0 else min(cells, max(1, round(abs(value) / scale * cells)))
    if value < 0:
        return " " * (cells - length) + "█" * length, " " * cells
    return " " * cells, ("█" * length).ljust(cells)


def dispersion(positions, cells):
    """Where occurrences fall, as `cells` characters from start to end.

    `positions` are fractions of the scope in [0, 1]. Each cell's height is
    its share of the fullest cell; an empty cell shows a dot, so the width of
    the scope stays visible.
    """
    if cells <= 0:
        return ""
    counts = [0] * cells
    for position in positions:
        counts[min(cells - 1, max(0, int(position * cells)))] += 1
    peak = max(counts) or 1
    return "".join(EMPTY if count == 0 else SPARKS[min(7, math.ceil(count / peak * 8) - 1)]
                   for count in counts)


def kwic(context, left_width, right_width):
    """One concordance line's parts: left context (right-aligned), node, right context.

    `context` is the sources' {"left", "word", "right"}; None means the text
    changed since the count. Cut text is marked with an ellipsis; punctuation
    right after the node stays attached to it.
    """
    if context is None:
        return " " * left_width, "", "(the text has changed since the count)"[:right_width]
    left = " ".join(context["left"].split())
    right = " ".join(context["right"].split())
    left_cut = left.startswith("…")
    left = left.lstrip("…")
    if len(left) > left_width or (left_cut and len(left) >= left_width):
        left = "…" + left[-(left_width - 1):] if left_width > 1 else ""
    elif left_cut:
        left = "…" + left
    if len(right) > right_width:
        right = right[:max(0, right_width - 1)].rstrip() + "…"
    return left.rjust(left_width), context["word"], right


def context_key(context, side):
    """Sort key for a concordance line: the nearest word on one side, then the next.

    `side` is "left" (1L, 2L…) or "right" (1R, 2R…). Lines without a context
    sort last.
    """
    if context is None:
        return (1, ())
    if side == "left":
        words = [_bare(word) for word in reversed(context["left"].split())]
    else:
        words = [_bare(word) for word in context["right"].split()]
    return (0, tuple(word for word in words if word))


def _bare(word):
    return word.strip("….,;:!?()[]\"'“”‘’—–-").casefold()


def histogram(rows, width):
    """Sentence-length bins as (label, bar, count) with bars scaled to the fullest bin."""
    peak = max((row["sentences"] for row in rows), default=0)
    lines = []
    for row in rows:
        label = f"{row['from']}–{row['to']}" if row["to"] is not None else f"{row['from']}+"
        lines.append((label, bar(row["sentences"], peak, width), row["sentences"]))
    return lines


def plural(number, noun):
    return f"{number:,} {noun}" + ("" if number == 1 else "s")
