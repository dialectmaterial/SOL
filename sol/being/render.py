"""Text presentation for one-shot output and the optional book shell."""
from __future__ import annotations

from copy import deepcopy
import re
import shutil
import textwrap
import unicodedata

from sol import __version__ as VERSION
from sol.corpus.edition import ROOT
from sol.core.models import Book, Node, Passage, presentation_text
from sol.core.paths import display_path
from sol.being.actions import context_passages
from sol.terminal.text import display_text


def sensible_width(requested: int | None) -> int:
    if requested is not None:
        if not 20 <= requested <= 240:
            raise ValueError("--width must be between 20 and 240.")
        return requested
    return max(20, min(88, shutil.get_terminal_size(fallback=(80, 24)).columns - 2))


def page_range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}–{end}"


def source_line(passage: Passage) -> str:
    book_label = "p." if passage.printed_page == passage.end_printed_page else "pp."
    pdf_label = "p." if passage.pdf_page == passage.end_pdf_page else "pp."
    return (f"Book {book_label} {page_range(passage.printed_page, passage.end_printed_page)} · "
            f"PDF {pdf_label} {page_range(passage.pdf_page, passage.end_pdf_page)}")


def fold_path(path: tuple[str, ...], width: int) -> str:
    """Prefer path-component boundaries over splitting directory names."""
    path = tuple(display_text(part) for part in path)
    if len(display_path(path)) <= width:
        return display_path(path)
    lines: list[str] = []
    current = "/"
    for index, component in enumerate(path):
        token = component + ("/" if index < len(path) - 1 else "")
        if len(current) + len(token) <= width:
            current += token
            continue
        if current not in {"/", "  "}:
            lines.append(current)
            current = "  "
        wrapped = textwrap.wrap(token, width=width, initial_indent=current,
                                subsequent_indent="  ", break_on_hyphens=True)
        lines.extend(wrapped[:-1])
        current = wrapped[-1]
    lines.append(current)
    return "\n".join(lines)


def fold_body(text: str, width: int) -> str:
    """Wrap meaningful lines independently, including hanging list indents."""
    lines = []
    for line in text.strip().splitlines():
        if not line.strip():
            if lines and lines[-1] != "":
                lines.append("")
            continue
        match = re.match(r"^(\s*)(?:(?:[-*+]|\d+[.)])\s+)?", line)
        indent = match.group(0) if match else ""
        continuation = " " * min(len(indent), max(0, width - 4))
        lines.append(textwrap.fill(line, width=width, subsequent_indent=continuation,
                                   replace_whitespace=False, expand_tabs=False,
                                   break_on_hyphens=False))
    return "\n".join(lines)


def render_passage(passage: Passage, width: int, plain: bool = False,
                   color: bool = False) -> str:
    body = fold_body(display_text(presentation_text(passage.text, passage.facsimile_labels)), width)
    if plain:
        return body
    metadata = source_line(passage)
    title = display_text(passage.heading or passage.node.title)
    def styled(value: str, code: str) -> str:
        return f"\x1b[{code}m{value}\x1b[0m" if color else value
    return "\n".join((
        styled(textwrap.fill(title, width=width, break_on_hyphens=False), "1"),
        styled(fold_path(passage.path, width), "2"),
        styled(textwrap.fill(metadata, width=width, break_on_hyphens=False), "2"),
        styled(textwrap.fill(f"ID {passage.identifier}", width=width, break_on_hyphens=False), "2"),
        *((textwrap.fill(
            "Transcription needs source review; compare the canonical Markdown with its source.", width=width),)
          if passage.needs_source_review else ()),
        "",
        body,
    ))


def passage_data(passage: Passage, book: Book | None = None) -> dict:
    result = {
        "id": passage.identifier, "type": passage.kind,
        "heading": passage.heading or passage.node.title, "path": display_path(passage.path),
        "text": presentation_text(passage.text, passage.facsimile_labels),
        "printed_page": passage.printed_page, "end_printed_page": passage.end_printed_page,
        "pdf_page": passage.pdf_page, "end_pdf_page": passage.end_pdf_page,
        "random_eligible": passage.random_eligible,
        "transcription_status": passage.transcription_status or None,
        "needs_source_review": passage.needs_source_review,
    }
    if book is not None and passage.identifier in book.canonical_records:
        result["canonical"] = deepcopy(book.canonical_records[passage.identifier])
    if book is not None and book.corpus_manifest:
        result["corpus"] = {
            "id": book.corpus_manifest.get("corpus_id"),
            "edition": deepcopy(book.corpus_manifest.get("edition", {})),
            "source": deepcopy(book.corpus_manifest.get("source", {})),
        }
    return result


def render_context(book: Book, passage: Passage, radius: int, width: int,
                   plain: bool = False, color: bool = False) -> str:
    return "\n\n".join(render_passage(item, width, plain, color)
                        for item in context_passages(book, passage, radius))


def render_search_results(passages: list[Passage], query: str, width: int,
                          whole_word: bool = False) -> str:
    if not passages:
        return f"No matches for {query!r}."
    lines = [f"{len(passages)} result(s) for {query!r}. Showing up to the selected limit.", ""]
    for number, passage in enumerate(passages, 1):
        text = unicodedata.normalize("NFC", " ".join(presentation_text(
            passage.text, passage.facsimile_labels).split()))
        pattern = re.escape(unicodedata.normalize("NFC", query.strip()).casefold())
        if whole_word:
            pattern = rf"(?<!\w){pattern}(?!\w)"
        found = re.search(pattern, text.casefold())
        # Case folding can expand a character, as with German sharp s. Map
        # the match back to the displayed text rather than using its offset.
        offsets = [index for index, character in enumerate(text)
                   for _ in character.casefold()]
        match_start = offsets[found.start()] if found and found.start() < len(offsets) else 0
        start = max(0, match_start - 35) if found else 0
        if start and text[start - 1] != " ":
            boundary = text.find(" ", start, match_start)
            start = boundary + 1 if boundary != -1 else match_start
        end = min(len(text), start + 180)
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        excerpt = ("..." if start else "") + text[start:end]
        if end < len(text):
            excerpt += "..."
        lines.extend((textwrap.fill(f"{number}. {passage.heading or passage.node.title}", width=width),
                      fold_path(passage.path, width),
                      textwrap.fill(source_line(passage), width=width),
                      textwrap.fill(f"ID {passage.identifier}", width=width, break_on_hyphens=False),
                      *((textwrap.fill("Source review pending: " + passage.transcription_status, width=width),)
                        if passage.needs_source_review else ()),
                      textwrap.fill(excerpt, width=width, break_on_hyphens=False), ""))
    return display_text("\n".join(lines).rstrip())


def location_data(book: Book, node: Node, path: tuple[str, ...]) -> dict:
    passages = [item for item in book.passages if item.path[:len(path)] == path]
    return {
        "title": node.title, "path": display_path(path), "directory": node.is_directory,
        "children": len(node.children), "passages": len(passages),
        "printed_page": min((item.printed_page for item in passages), default=None),
        "end_printed_page": max((item.end_printed_page for item in passages), default=None),
        "pdf_page": min((item.pdf_page for item in passages), default=None),
        "end_pdf_page": max((item.end_pdf_page for item in passages), default=None),
        "pending_review": sum(item.needs_source_review for item in passages),
    }


def render_info(book: Book, node: Node, path: tuple[str, ...], width: int = 80) -> str:
    data = location_data(book, node, path)
    lines = [data["title"], data["path"],
             f"{data['passages']} passages · {data['children']} children · "
             f"{data['pending_review']} awaiting source review"]
    if data["printed_page"] is not None:
        lines.append(f"Book pp. {page_range(data['printed_page'], data['end_printed_page'])} · "
                     f"PDF pp. {page_range(data['pdf_page'], data['end_pdf_page'])}")
    return display_text("\n".join(textwrap.fill(line, width=width, break_on_hyphens=False) for line in lines))


def render_listing(node: Node) -> str:
    nodes = node.children if node.is_directory else (node,)
    return display_text("\n".join(
        f"{child.name}{'/' if child.is_directory else ''}\n"
        f"    {child.label + '. ' if child.label else ''}{child.title} · p. {child.start_page}"
        for child in nodes
    ))


def render_tree(node: Node = ROOT, prefix: str = "", include_self: bool = True,
                depth: int | None = None, ascii_only: bool = False) -> str:
    if depth is not None and not 0 <= depth <= 32:
        raise ValueError("tree depth must be between 0 and 32")
    lines = []
    if include_self:
        lines.append(("/" if not node.name else node.name + ("/" if node.is_directory else ""))
                     + f"  {node.title}")
    if depth == 0:
        if node.children:
            lines.append(prefix + ("    ..." if ascii_only else "    …"))
        result = display_text("\n".join(lines))
        return unicodedata.normalize("NFKD", result).encode("ascii", "backslashreplace").decode() if ascii_only else result
    for index, child in enumerate(node.children):
        last = index == len(node.children) - 1
        if ascii_only:
            connector, extension = ("`-- ", "    ") if last else ("+-- ", "|   ")
        else:
            connector, extension = ("└── ", "    ") if last else ("├── ", "│   ")
        suffix = "/" if child.is_directory else ""
        separator = "  p. " if ascii_only else "  · p. "
        lines.append(f"{prefix}{connector}{child.name}{suffix}{separator}{child.start_page}")
        if child.children:
            lines.extend(render_tree(child, prefix + extension, False,
                                     None if depth is None else depth - 1, ascii_only).splitlines())
    result = display_text("\n".join(lines))
    return unicodedata.normalize("NFKD", result).encode("ascii", "backslashreplace").decode() if ascii_only else result


def render_guide(book: Book | None = None, width: int = 80, depth: int = 1,
                 node: Node | None = None) -> str:
    """A compact, source-independent introduction to reading in BEING.

    The default reveals the three doctrines, not an overwhelming full outline.
    Explicit depth and node arguments use the loaded tree without reading files.
    """
    width = sensible_width(width)
    title = r""" ___   ___   _
/ __| / _ \ | |
\__ \| (_) || |__
|___/ \___/ |____|
SOL: SOL Organizes Logic"""
    selected = node or (book.root if book is not None else ROOT)
    outline = render_tree(selected, depth=depth, ascii_only=True)
    starting = """START READING
  sol       open the reader and resume your saved position
  sol -n    read temporarily, without a workspace or actor
  sol -r    print one random quotation and leave
SOL remembers the last actor and that actor's last workspace. If none exists,
it asks to create one. Choose explicitly: sol --actor NAME --workspace NAME.
An actor is the name on your personal notes, not the book's author.

IN THE READER
  j/k  h/l  w     lines / source characters / words
  Ctrl-D / Ctrl-U half a visible page down / up
  b / n           previous / next passage, not printed page
  p / f / T       one-paragraph reading / quiet focus / colour theme
  gg / G          beginning / end of the loaded reading section
  t               outline: j/k move, h/l branches, Enter read
  v, then y       select text and copy it (Escape clears); y alone copies
  c / ?           pages, footnotes, your notes and markers / every key
  :q / :qa!       save your exact position and quit / quit without saving

FIND AND RETURN
  /ground, Enter  search the whole book; every matching passage is listed
  Ctrl-N / Ctrl-P next / previous occurrence, counted as "4 of 770"
  gp 240, Enter   go to a printed page
  Alt-Left/Right  back / forward through your reading trail
  m1 / M / L      a quick marker ('1 returns) / name this place / list places
Search is literal, case-insensitive, not conceptual. Escape closes panels.

PRINTED PAGE, NOTES AND ESSENCE
  s / S           the printed crop / the page in Zathura, passage highlighted
  a               a note on this passage (Ctrl-S saves, Ctrl-C discards)
  E               ESSENCE studies beside the reader (Alt-R returns)
  sol-window      its own window in a book face; keys.json moves your keys

YOUR LOCAL WORKSPACE
  sol --workspace-list         list saved workspaces
  sol --workspace-delete NAME  archive a workspace (recoverable)
Position and notes stay local. Canonical text is read-only.

MORE WHEN YOU NEED IT
  sol guide --depth 2  reveal more of the book's structure
  sol --help          see options and one-shot reading commands
  sol --shell         browse the book in a minimal command line
There, help lists the commands; nothing is saved.
SOL has one Neovim-backed reader, with its own configuration and simple keys.
It runs in capable terminals, including Alacritty; Kitty is not required."""
    if book is None:
        starting += """\n\nCORPUS SETUP (the book tree is an abbreviated fallback)
  sol --set-corpus DIRECTORY
Or run sol: first launch asks for the supported PDF and imports it once.
Normal reading reuses that corpus; it never reconverts the PDF."""
    # Preserve command indentation and avoid filling source tree lines as prose.
    folded = "\n".join(
        textwrap.fill(line, width=width, subsequent_indent="  " if line.startswith("  ") else "",
                      break_on_hyphens=False) if line else ""
        for line in starting.splitlines()
    )
    title = "\n".join(textwrap.fill(line, width=width, subsequent_indent="    ",
                                    break_on_hyphens=False) if line else ""
                      for line in title.splitlines())
    outline = "\n".join(textwrap.fill(line, width=width, subsequent_indent="    ",
                                      break_on_hyphens=False) for line in outline.splitlines())
    return "\n".join((title, "", folded, "", "BOOK TREE", outline))
