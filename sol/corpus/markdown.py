"""Shared CommonMark visibility and plain-text semantics, with lazy parsing."""
from __future__ import annotations

from html.parser import HTMLParser
import re

from sol.corpus.errors import CorpusError

_NOTE_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class VisibleHTML(HTMLParser):
    """Extract HTML's visible data without leaking anchors, tags, or comments."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0
        self.sup_hidden: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag == "sup":
            identifier = dict(attrs).get("data-sol-note")
            hide = isinstance(identifier, str) and _NOTE_UUID.fullmatch(identifier) is not None
            self.sup_hidden.append(hide)
            if hide:
                self.hidden += 1
        if self.hidden:
            return
        if tag in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" ")
        elif tag == "img":
            self.parts.append(dict(attrs).get("alt") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        elif tag == "sup" and self.sup_hidden:
            if self.sup_hidden.pop():
                self.hidden -= 1
        elif not self.hidden and tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _html_plain(markup: str) -> str:
    parser = VisibleHTML()
    parser.feed(markup)
    parser.close()
    return "".join(parser.parts)


def commonmark_tokens(markdown: str) -> list:
    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:
        raise CorpusError("Reindexing requires markdown-it-py; install it with python3 -m pip install markdown-it-py") from exc
    return MarkdownIt("commonmark").parse(markdown)


def tokens_plain_text(parsed_tokens: list) -> str:

    def inline(tokens: list) -> str:
        parts: list[str] = []
        markup = VisibleHTML()
        for token in tokens:
            if token.type in {"text", "code_inline"}:
                if not markup.hidden:
                    parts.append(token.content)
            elif token.type in {"softbreak", "hardbreak"}:
                if not markup.hidden:
                    parts.append("\n")
            elif token.type == "image":
                if not markup.hidden:
                    parts.append(inline(token.children or []))
            elif token.type == "html_inline":
                markup.feed(token.content)
                parts.extend(markup.parts)
                markup.parts.clear()
        return "".join(parts)

    parts: list[str] = []
    for token in parsed_tokens:
        if token.type == "inline":
            parts.append(inline(token.children or []))
        elif token.type in {"fence", "code_block"}:
            parts.append(token.content.rstrip("\n") + "\n")
        elif token.type == "html_block":
            parts.append(_html_plain(token.content).strip("\n") + "\n")
        elif token.type in {"paragraph_close", "heading_close", "list_item_close"}:
            parts.append("\n")
    return re.sub(r"\n{3,}", "\n\n", "".join(parts)).strip()


def plain_text(markdown: str) -> str:
    """CommonMark visible text, omitting only SOL-annotated note callouts.

    Paragraph/list/quotation boundaries remain newlines, code remains literal,
    and presentational emphasis does not become artificial classifier tokens.
    Ordinary mathematical superscripts remain visible.
    """
    return tokens_plain_text(commonmark_tokens(markdown))
