"""CommonMark typography on exact canonical plain-text codepoint offsets.

This is a presentation projection, not a second text extractor. Parsing is
lazy and uses the corpus contract's CommonMark tokens and visible-HTML rules.
Any disagreement with the indexed text discards all styles: a readable plain
fallback is safer than applying emphasis to the wrong source characters.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TypographySpan:
    """A half-open range in unchanged canonical plain text, not screen cells."""
    start: int
    end: int
    styles: tuple[str, ...]


@dataclass(frozen=True)
class Typography:
    """Nonoverlapping styled runs, or an explicit unstyled degradation."""
    spans: tuple[TypographySpan, ...] = ()
    degraded: bool = False
    reason: str | None = None


_STYLE_ORDER = ("quotation", "heading", "emphasis", "strong", "code")
_INLINE_STYLES = {"em": "emphasis", "strong": "strong"}
_HTML_STYLES = {
    "em": "emphasis", "i": "emphasis", "strong": "strong", "b": "strong",
    "code": "code", "pre": "code", "blockquote": "quotation",
}


def _ordered(styles) -> tuple[str, ...]:
    return tuple(style for style in _STYLE_ORDER if style in styles)


def _project(tokens: list) -> tuple[str, tuple[TypographySpan, ...]]:
    # Reuse the contract's HTML visibility, especially annotated note callouts.
    # The final independent projection check below catches any contract drift.
    from sol.corpus.contract import _VisibleHTML

    decorated: list[tuple[str, tuple[str, ...]]] = []

    def emit(value: str, styles=()) -> None:
        ordered = _ordered(styles)
        decorated.extend((character, ordered) for character in value)

    class StyledHTML(_VisibleHTML):
        def __init__(self, current_styles):
            super().__init__()
            self.counts: dict[str, int] = {}
            self.current_styles = current_styles

        def styles(self):
            return {style for style, count in self.counts.items() if count}

        def capture(self, operation, *arguments):
            previous = len(self.parts)
            operation(*arguments)
            for value in self.parts[previous:]:
                emit(value, self.current_styles() | self.styles())

        def handle_starttag(self, tag, attrs):
            style = _HTML_STYLES.get(tag)
            if style:
                self.counts[style] = self.counts.get(style, 0) + 1
            self.capture(super().handle_starttag, tag, attrs)

        def handle_endtag(self, tag):
            self.capture(super().handle_endtag, tag)
            style = _HTML_STYLES.get(tag)
            if style:
                self.counts[style] = max(0, self.counts.get(style, 0) - 1)

        def handle_data(self, data):
            self.capture(super().handle_data, data)

    def inline(children: list, inherited: set[str]) -> None:
        counts: dict[str, int] = {}

        def markdown_styles():
            return inherited | {style for style, count in counts.items() if count}

        markup = StyledHTML(markdown_styles)
        for token in children:
            if token.type.endswith("_open") and token.type[:-5] in _INLINE_STYLES:
                style = _INLINE_STYLES[token.type[:-5]]
                counts[style] = counts.get(style, 0) + 1
            elif token.type.endswith("_close") and token.type[:-6] in _INLINE_STYLES:
                style = _INLINE_STYLES[token.type[:-6]]
                counts[style] = max(0, counts.get(style, 0) - 1)
            elif token.type in {"text", "code_inline"}:
                if not markup.hidden:
                    styles = markdown_styles() | markup.styles()
                    if token.type == "code_inline":
                        styles.add("code")
                    emit(token.content, styles)
            elif token.type in {"softbreak", "hardbreak"}:
                if not markup.hidden:
                    emit("\n", markdown_styles() | markup.styles())
            elif token.type == "image":
                if not markup.hidden:
                    inline(token.children or [], markdown_styles() | markup.styles())
            elif token.type == "html_inline":
                markup.feed(token.content)
                markup.parts.clear()

    block_counts: dict[str, int] = {}
    for token in tokens:
        block_styles = {style for style, count in block_counts.items() if count}
        if token.type in {"blockquote_open", "heading_open"}:
            style = "quotation" if token.type == "blockquote_open" else "heading"
            block_counts[style] = block_counts.get(style, 0) + 1
        elif token.type == "blockquote_close":
            block_counts["quotation"] = max(0, block_counts.get("quotation", 0) - 1)
        elif token.type == "inline":
            inline(token.children or [], block_styles)
        elif token.type in {"fence", "code_block"}:
            emit(token.content.rstrip("\n") + "\n", block_styles | {"code"})
        elif token.type == "html_block":
            html_parts: list[tuple[str, tuple[str, ...]]] = []
            previous = decorated
            decorated = html_parts
            markup = StyledHTML(lambda: block_styles)
            markup.feed(token.content)
            markup.close()
            decorated = previous
            # The contract strips only surrounding newlines from HTML blocks.
            first, last = 0, len(html_parts)
            while first < last and html_parts[first][0] == "\n":
                first += 1
            while last > first and html_parts[last - 1][0] == "\n":
                last -= 1
            decorated.extend(html_parts[first:last])
            emit("\n", block_styles)
        elif token.type in {"paragraph_close", "heading_close", "list_item_close"}:
            emit("\n", block_styles)
            if token.type == "heading_close":
                block_counts["heading"] = max(0, block_counts.get("heading", 0) - 1)

    # Mirror the contract's newline collapse and strip without losing offsets.
    raw = "".join(character for character, _ in decorated)
    normalized: list[tuple[str, tuple[str, ...]]] = []
    cursor = 0
    for match in re.finditer(r"\n{3,}", raw):
        normalized.extend(decorated[cursor:match.start() + 2])
        cursor = match.end()
    normalized.extend(decorated[cursor:])
    projected = "".join(character for character, _ in normalized)
    left = len(projected) - len(projected.lstrip())
    right = len(projected.rstrip())
    normalized = normalized[left:right]
    projected = projected.strip()

    spans: list[TypographySpan] = []
    start = 0
    while start < len(normalized):
        styles = normalized[start][1]
        end = start + 1
        while end < len(normalized) and normalized[end][1] == styles:
            end += 1
        if styles:
            spans.append(TypographySpan(start, end, styles))
        start = end
    return projected, tuple(spans)


def map_typography(markdown: str, plain_text: str) -> Typography:
    """Map canonical CommonMark emphasis to exact indexed source positions.

    ``emphasis`` is an intention, not an ANSI escape or chosen terminal style.
    A view may show it as italics or underlining without changing any text.
    Importing this module needs no parser; missing optional dependencies and
    projection disagreement both return an explicit, completely unstyled result.
    """
    if not isinstance(markdown, str) or not isinstance(plain_text, str):
        return Typography(degraded=True, reason="Canonical typography source is unavailable.")
    from sol.corpus.contract import CorpusError, _commonmark_tokens, _plain_tokens
    try:
        tokens = _commonmark_tokens(markdown)
    except CorpusError:
        return Typography(degraded=True, reason="CommonMark typography parser is unavailable.")
    if _plain_tokens(tokens) != plain_text:
        return Typography(degraded=True, reason="Canonical Markdown and indexed text disagree; plain text shown.")
    projected, spans = _project(tokens)
    if projected != plain_text:
        return Typography(degraded=True, reason="Typography projection disagrees with source; plain text shown.")
    return Typography(spans)
