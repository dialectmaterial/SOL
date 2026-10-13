"""Explicit compatibility reader for pre-corpus PDF workflows.

This slow, edition-specific projection has historical page-based identifiers.
It is never a fallback for a missing or stale canonical Markdown corpus.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unicodedata

from sol.corpus.edition import PRINTED_PAGE_OFFSET
from sol.corpus.layout import Line, extract_pages, heading_key, indexed_tree, is_heading
from sol.reader.models import Book, Node, Passage, node_path


# 4. Prose reconstruction: paragraphs, their source spans, and readable text.
def join_lines(lines: list[Line], vocabulary: set[str]) -> str:
    """Undo line wraps conservatively, retaining genuine compound-word hyphens."""
    text = ""
    for line in lines:
        fragment = unicodedata.normalize("NFC", line.text)
        # Some callouts are fused to punctuation rather than separate PDF words.
        fragment = re.sub(r"(?<=[A-Za-z])([,.;:])\d{1,3}(?=\s|$)", r"\1", fragment)
        if text.endswith("-") and re.match(r"^[A-Za-z]", fragment):
            left = re.search(r"([A-Za-z]+(?:-[A-Za-z]+)*)-$", text)
            right = re.match(r"[A-Za-z]+", fragment)
            if left and right:
                a, b = left.group(1), right.group(0)
                compound, joined = (a + "-" + b).casefold(), (a + b).casefold()
                retain = compound in vocabulary or (
                    joined not in vocabulary and (
                        "-" in a or a.casefold() in {
                            "self", "non", "being", "for", "in", "form", "sense", "co"
                        }
                    )
                )
                text = text + fragment if retain else text[:-1] + fragment
                continue
        text += (" " if text else "") + fragment
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def load_book(pdf: Path) -> Book:
    """Recover paragraph indents and page continuations, then attach source paths."""
    pages = extract_pages(pdf)
    root, events = indexed_tree(pages)
    vocabulary = {
        word.casefold()
        for page in pages for line in page.lines
        for word in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*", line.text)
    }
    records = []
    current: list[Line] = []
    active = root.children[0].children[0]
    detail = ""
    previous: Line | None = None
    body_started = False
    skip_title_until = -1.0

    def finish() -> None:
        nonlocal current
        if current:
            text = join_lines(current, vocabulary)
            if text:
                records.append((text, current[0].pdf_page, current[-1].pdf_page, active, detail))
        current = []

    for page in pages:
        previous = None
        skip_title_until = -1.0
        for line in page.lines:
            event = events.get(line.position)
            if event is not None:
                finish()
                active, detail = event, ""
                body_started = True
                # Ignore remaining lines of a verified wrapped title.
                skip_title_until = line.y
                target = heading_key(event.title)
                accumulated = line.text
                index = page.lines.index(line)
                for following in page.lines[index + 1:index + 3]:
                    if heading_key(accumulated) == target:
                        break
                    accumulated += " " + following.text
                    skip_title_until = following.y
                previous = None
                continue
            if line.y <= skip_title_until:
                continue
            if is_heading(line, page):
                finish()
                # Display otherwise unindexed lower-level headings as context,
                # but do not invent their hierarchy from typography alone.
                detail = line.text
                previous = None
                continue
            if not body_started:
                continue
            # Paragraphs in this edition are indented by one em, not separated
            # by blank lines. Ignore page changes themselves: unindented prose
            # at the top of the next page continues the preceding paragraph.
            indentation = line.x - page.left
            indented = page.body_height * .6 < indentation < page.body_height * 1.8
            # Italic end-of-line fragments can have the same inset as a new
            # paragraph. A lowercase continuation of an unfinished sentence
            # (or a divided word) is still part of the preceding paragraph.
            if current and re.match(r"^[a-z]", line.text) and not re.search(
                r"[.!?:][\"’”)]?$", current[-1].text
            ):
                indented = False
            gap = (previous is not None
                   and line.y - previous.y > page.body_height * 1.8
                   and re.search(r"[.!?][\"’”)]?$", previous.text) is not None)
            # Body enumerations belong to the preceding introductory paragraph.
            enumerated_list = re.match(r"^[A-Z][.)]\s", line.text) is not None
            if current and (indented or gap) and not enumerated_list:
                finish()
            current.append(line)
            previous = line
    finish()

    # A directory's own introductory prose becomes a real virtual text file.
    by_node = {}
    for _, start, _, node, _ in records:
        by_node.setdefault(id(node), start - PRINTED_PAGE_OFFSET)

    def finish_tree(node: Node) -> None:
        if node.children:
            if node.name.endswith(".txt"):
                node.name = node.name[:-4]
            if id(node) in by_node:
                intro = Node("00-introduction.txt", "Introduction — " + node.title,
                             by_node[id(node)], parent=node)
                node.children = (intro,) + node.children
            for child in node.children:
                finish_tree(child)

    finish_tree(root)
    page_counts = Counter()
    passages = []
    for text, start, end, node, heading in records:
        if node.children:
            node = node.children[0]
        path = node_path(node)
        printed = start - PRINTED_PAGE_OFFSET
        page_counts[printed] += 1
        identifier = f"p{printed:04d}-{page_counts[printed]:02d}"
        passages.append(Passage(text, start, printed, node, path, end,
                                end - PRINTED_PAGE_OFFSET, identifier, heading))
    if not passages:
        raise RuntimeError("No paragraphs found in the PDF.")
    return Book(root, passages)
