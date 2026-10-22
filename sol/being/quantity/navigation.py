"""Source-codepoint navigation geometry without a terminal dependency.

Layouts map each insertion boundary in canonical plain text to a displayed row
and cell column. Interfaces may supply their actual renderer's positions; the
fallback handles escaped controls, combining marks, and wide characters. A
resize changes this projection, never the semantic source cursor.
"""
from __future__ import annotations

import unicodedata


def character_cells(character: str) -> int:
    """Cell width of the reader's escaped display, not a mutation of its text."""
    code = ord(character)
    if character == "\n":
        return 0
    if (unicodedata.category(character) in {"Cc", "Cf", "Cs", "Zl", "Zp"}
            or (character.isspace() and character != " ")
            or code in {0x034f, 0x115f, 0x1160, 0x17b4, 0x17b5, 0x2800, 0x3164, 0xffa0}
            or 0x180b <= code <= 0x180f or 0x2060 <= code <= 0x206f
            or 0xfe00 <= code <= 0xfe0f or 0xfff0 <= code <= 0xfff8
            or 0xe0000 <= code <= 0xeffff):
        return 2 if character == "\t" else 4 if code <= 0xff else 6 if code <= 0xffff else 10
    if unicodedata.combining(character) or unicodedata.category(character) in {"Mn", "Me"}:
        return 0
    return 2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1


def source_layout(text: str, width: int, *, cell_width=character_cells) -> tuple[tuple[int, int], ...]:
    """Project source boundaries onto wrapped rows using supplied cell widths."""
    if type(width) is not int or width < 1:
        raise ValueError("reading width must be a positive integer")
    positions, row, column = [], 0, 0
    for character in text:
        if character == "\n":
            positions.append((row, column))
            row, column = row + 1, 0
        else:
            cells = cell_width(character)
            if type(cells) is not int or cells < 0:
                raise ValueError("display cell widths must be nonnegative integers")
            if cells and column == width:
                row, column = row + 1, 0
            if (column and cells == 2 and unicodedata.east_asian_width(character) in {"W", "F"}
                    and column + cells > width):
                row, column = row + 1, 0
            positions.append((row, column))
            total = column + cells
            if total > width:
                row += (total - 1) // width
                column = (total - 1) % width + 1
            else:
                column = total
    positions.append((row, column))
    return tuple(positions)


def validate_layout(layout, text_length: int) -> tuple[tuple[int, int], ...]:
    """Reject mismatched source geometry before an interface can move state."""
    try:
        positions = tuple(tuple(point) for point in layout)
    except TypeError as error:
        raise ValueError("reading layout must contain source-boundary row/column pairs") from error
    if len(positions) != text_length + 1:
        raise ValueError("reading layout must describe every source insertion boundary")
    previous = (-1, 0)
    for point in positions:
        if (len(point) != 2 or any(type(value) is not int or value < 0 for value in point)
                or point < previous):
            raise ValueError("reading layout positions must be ordered nonnegative cell coordinates")
        previous = point
    return positions


def vertical_offset(layout, offset: int, rows: int, preferred_column: int | None = None):
    """Return source offset and preferred cell column after a wrapped-row move."""
    row, column = layout[offset]
    preferred = column if preferred_column is None else preferred_column
    target = min(max(layout[0][0], row + rows), layout[-1][0])
    if target == row:
        return offset, preferred
    candidates = [(index, point) for index, point in enumerate(layout) if point[0] == target]
    if not candidates:
        # One escaped source character can span several display rows. Such rows
        # have no legal insertion boundary. Keep moving in the requested
        # direction instead of getting trapped at the same source character.
        eligible = [point for point in layout if point[0] >= target] if rows > 0 else [
            point for point in layout if point[0] <= target]
        distance = min(abs(point[0] - target) for point in eligible)
        candidates = [(index, point) for index, point in enumerate(layout)
                      if (point[0] >= target if rows > 0 else point[0] <= target)
                      and abs(point[0] - target) == distance]
    index, _ = min(candidates, key=lambda item: (
        abs(item[1][0] - target), abs(item[1][1] - preferred),
        # Hidden wrap separators/combining boundaries can share a coordinate
        # with the following visible glyph. Visual motion lands on that glyph,
        # while horizontal source-character motion still visits every offset.
        item[1][1] > preferred, -item[0]))
    return index, preferred
