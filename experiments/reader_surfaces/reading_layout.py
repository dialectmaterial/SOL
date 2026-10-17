"""Word-aware presentation over unchanged source characters.

The ordinary terminal renderer wraps at cell boundaries. A plan inserts only
display padding before a token which fits a row but not its remaining cells,
making that renderer wrap at the word boundary instead. Separators which would
otherwise occupy the beginning of a soft-wrapped row are hidden in presentation.
They remain in the source buffer and in its cursor/selection coordinates.

No terminal library, ANSI sequences, or canonical-text changes are involved.
The same plan supplies styles, processor mappings, and navigation geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class LineLayout:
    """A physical source line projected onto zero or more visual wraps.

    ``positions`` describes each semantic insertion boundary. ``boundaries``
    and ``reverse`` address display *characters*, not terminal cell columns.
    Hidden wrap separators can share a displayed location; reverse mapping
    resolves that ambiguity toward the following visible source character.
    ``row_count`` includes the renderer's final cursor-space after the line.
    """

    source: str
    width: int
    padding: tuple[int, ...]
    displayed: tuple[str, ...]
    boundaries: tuple[int, ...]
    reverse: tuple[int, ...]
    positions: tuple[tuple[int, int], ...]
    row_count: int

    @property
    def display_text(self) -> str:
        return "".join(" " * pad + value for pad, value in zip(self.padding, self.displayed))

    def source_to_display(self, index: int) -> int:
        return self.boundaries[max(0, min(index, len(self.boundaries) - 1))]

    def display_to_source(self, index: int) -> int:
        return self.reverse[max(0, min(index, len(self.reverse) - 1))]

    def styled_fragments(self, fragments):
        """Retain semantic/selection styles on glyphs, never on inserted padding."""
        result, index = [], 0
        for fragment in fragments:
            style, text, *extra = fragment
            for character in text:
                if index >= len(self.source) or character != self.source[index]:
                    raise ValueError("reading fragments must match the source line")
                if self.padding[index]:
                    result.append(("", " " * self.padding[index]))
                if self.displayed[index]:
                    result.append((style, self.displayed[index], *extra))
                index += 1
        if index != len(self.source):
            raise ValueError("reading fragments must match the source line")
        return result


def _break_after(character: str) -> bool:
    # A source hyphen/dash is already a meaningful break; no discretionary
    # hyphen is inserted. CJK prose also has usable boundaries without spaces.
    return (character in " -\u2010\u2013\u2014" or
            unicodedata.east_asian_width(character) in {"W", "F"})


def line_layout(source: str, width: int, *, display_character, cell_width) -> LineLayout:
    """Plan one source line using the renderer's own escape and width functions.

    Word wrapping cannot be determined from styled fragments independently:
    an italic span may begin in the middle of a word. Token boundaries come
    from source semantics first, and styles are mapped onto the finished plan.
    Long unbreakable tokens use the ordinary renderer's character fallback.
    """
    if type(width) is not int or width < 1:
        raise ValueError("reading width must be a positive integer")
    if "\n" in source:
        raise ValueError("reading line plans cannot contain source newlines")
    displayed = [display_character(character) for character in source]
    if any(not isinstance(value, str) or not value for value in displayed):
        raise ValueError("every source character needs a nonempty display projection")

    def cells(character):
        value = cell_width(character)
        if type(value) is not int or value < 0:
            raise ValueError("display cell widths must be nonnegative integers")
        return value

    widths = [sum(cells(character) for character in value) for value in displayed]
    tokens, start = {}, 0
    for index, character in enumerate(source):
        # Combining source codepoints stay attached to the preceding token.
        following_combines = index + 1 < len(source) and (
            unicodedata.combining(source[index + 1]) or
            unicodedata.category(source[index + 1]) in {"Mn", "Me"})
        if _break_after(character) and not following_combines:
            if source[start] != " ":
                end = index if character == " " else index + 1
                if end > start:
                    tokens[start] = sum(widths[start:end])
            start = index + 1
    if start < len(source) and source[start] != " ":
        tokens[start] = sum(widths[start:])

    row, column = 0, 0
    padding, boundaries, reverse, output = [], [], [], []

    def emit(character):
        nonlocal row, column
        count = cells(character)
        if column + count > width:
            row, column = row + 1, 0
        output.append((row, column))
        column += count

    for index, value in enumerate(displayed):
        token_width = tokens.get(index, 0)
        pad = (width - column if column and column < width and
               token_width <= width and token_width > width - column else 0)
        padding.append(pad)
        for _ in range(pad):
            reverse.append(index)
            emit(" ")
        boundaries.append(len(reverse))
        # Retaining a full-width row's separator as a visible leading space
        # would indent the next word, or even manufacture an empty row before
        # another full-width word. Hide only these layout-edge spaces.
        if source[index] == " " and column == width:
            displayed[index] = value = ""
        for character in value:
            reverse.append(index)
            emit(character)

    boundaries.append(len(reverse))
    reverse.append(len(source))
    # BufferControl always appends a final space for the end insertion point.
    # Include its glyph-before-wrap position, but not the space in fragments.
    emit(" ")
    positions = tuple(output[index] for index in boundaries)
    return LineLayout(source, width, tuple(padding), tuple(displayed),
                      tuple(boundaries), tuple(reverse), positions, row + 1)
