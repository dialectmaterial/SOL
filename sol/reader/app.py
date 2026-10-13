#!/usr/bin/env python3
"""SOL: a terminal reader for the Cambridge *Science of Logic*.

Canonical local Markdown is indexed once and read through a verified JSONL
index using standard-library Python. Poppler remains available for explicit
legacy PDF reading. Corpus/PDF loading and the terminal interface stay separate.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
import os
import random
import re
import shlex
import shutil
import sys
import textwrap
import unicodedata
from pathlib import Path


from sol import __version__ as VERSION
from sol.corpus.edition import PDF_FILENAME, ROOT, default_pdf
from sol.core.config import (
    config_path, configured_corpus, discover_corpus, installed_project_directory,
    save_corpus, source_project_directory,
)
from sol.core.models import Book, Node, Passage, node_path, presentation_text
from sol.core.paths import alias, child_by_name, display_path
from sol.core.paths import resolve_path as resolve_book_path
from sol.reader.options import build_parser


def load_book(pdf: Path) -> Book:
    """Load historical PDF prose only when --pdf was explicitly requested."""
    from sol.reader.legacy_pdf import load_book as load_legacy_book

    return load_legacy_book(pdf)


def load_corpus_book(corpus: Path) -> Book:
    """Compatibility entry point for the shared verified-corpus loader."""
    from sol.core.corpus import load_corpus_book as load_canonical_book

    return load_canonical_book(corpus)


# 5. Navigation and display: no PDF extraction details belong in the shell.


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
    body = fold_body(presentation_text(passage.text, passage.facsimile_labels), width)
    if plain:
        return body
    metadata = source_line(passage)
    title = passage.heading or passage.node.title
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


def context_passages(book: Book, passage: Passage, radius: int) -> list[Passage]:
    if not 0 <= radius <= 10:
        raise ValueError("context must be between 0 and 10 paragraphs on each side")
    index = next((i for i, item in enumerate(book.passages)
                  if item.identifier == passage.identifier), None)
    if index is None:
        raise ValueError("this passage is not in the book")
    return book.passages[max(0, index - radius):index + radius + 1]


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
    return "\n".join(lines).rstrip()


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
    return "\n".join(textwrap.fill(line, width=width, break_on_hyphens=False) for line in lines)


def resolve_path(value: str | None, cwd: tuple[str, ...], root: Node = ROOT) -> tuple[Node, tuple[str, ...]]:
    """Keep the reader's edition-outline default over the shared path resolver."""
    return resolve_book_path(value, cwd, root)


def render_listing(node: Node) -> str:
    nodes = node.children if node.is_directory else (node,)
    return "\n".join(
        f"{child.name}{'/' if child.is_directory else ''}\n"
        f"    {child.label + '. ' if child.label else ''}{child.title} · p. {child.start_page}"
        for child in nodes
    )


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
        result = "\n".join(lines)
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
    result = "\n".join(lines)
    return unicodedata.normalize("NFKD", result).encode("ascii", "backslashreplace").decode() if ascii_only else result


def render_guide(book: Book | None = None, width: int = 80, depth: int = 1,
                 node: Node | None = None) -> str:
    """A compact, source-independent starting point for the virtual reader.

    The default reveals the three doctrines, not an overwhelming full outline.
    Explicit depth and node arguments use the loaded tree without reading files.
    """
    width = sensible_width(width)
    title = r""" ___   ___   _
/ __| / _ \ | |
\__ \| (_) || |__
|___/ \___/ |____|
SOL: SOL Organizes Logic

PROJECT ROADMAP
+-- BEING    CLI, reader, virtual shell [current]
+-- ESSENCE  applications, terminal emulator, classifiers
`-- CONCEPT  operating system, NixOS, Hyprland

BOOK TREE"""
    selected = node or (book.root if book is not None else ROOT)
    outline = render_tree(selected, depth=depth, ascii_only=True)
    starting = """START IN YOUR TERMINAL
  sol       start the reader; choose a workspace and actor
  sol -n    temporary reader, without a saved workspace
  sol -r    print one random quotation and leave

INSIDE SOL: enter these commands one at a time
  cd /being
  ls
  first
  next
  where
  search "ground" --word --limit 3
  open 1
  context 1

WITH A WORKSPACE
  bookmark add beginning
  note add "A personal interpretation, not Hegel's text."
  note draft
Personal notes require an actor. Passage IDs preserve references across sessions.
Actor means the name recorded on your personal notes, not the book's author.
note draft uses the enhanced prompt: Ctrl-S saves, Ctrl-C cancels.
Use note show NOTE_ID for its revision; note edit NOTE_ID edits your own note.
note history NOTE_ID shows earlier versions (replace NOTE_ID with a printed ID).

KEEP EXPLORING
  guide --depth 2   reveal more of the tree (or guide PATH --depth N)
  help             see command syntax
  neofetch         ASCII Hegel and SOL's concept preview
  tree --depth 3   explore divisions without the guide
  exit             leave SOL

Directories are divisions; files contain passages. '...' hides deeper divisions.
Search is literal and case-insensitive; --word matches whole words, not concepts.
Book paths are virtual: SOL never runs your host shell or edits canonical text.
Workspace notes and checkpoints stay local; backups and exports are your choice."""
    if book is None:
        starting += """\n\nCORPUS SETUP (the tree above is an abbreviated fallback)
  sol --set-corpus DIRECTORY
Use an existing converted corpus. For explicit conversion: sol-corpus --help.
Reading never performs PDF conversion automatically."""
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
    return "\n".join((title, outline, "", folded))


# Hand-drawn ASCII bust: swept-back hair, high forehead, and cravat.
HEGEL_ASCII = r'''          .-""""""-.
      _.-'  _.._    '-._
    .'  .-''    ''-.    '.
   /  .'            '.   \
  /  /                \   \
 (  |   _          _   |  )
  \ |  /_\        /_\  | /
   \|   .     |    .   |/
    |        /         |
    |       (__)       |
    |    .--------.    |
     \     '----'     /
      '.            .'
        '-.______.-'
     _____/|    |\_____
    /    / | /\ | \    \
   /    /  |/  \|  \    \
  /____/   / /\ \   \____\
       G. W. F. Hegel'''

HEGEL_ASCII_SMALL = r'''      .-""""-.
    .' .-~~-. '.
   / .'      '. \
  ( |  _    _  | )
   \|  .    .  |/
    |    /     |
    |   (_)    |
    |  .---.   |
     \  '-'   /
      '.___.'
    ___|/|\|___
   /   /==\    \
  /___/ || \____\
  G. W. F. Hegel'''

# Project identity, not measurements of the host machine. Edit these later.
NEOFETCH_PLACEHOLDERS = (
    ("Kernel", "dialectic [placeholder]"),
    ("Packages", "[placeholder]"),
    ("Terminal", "[placeholder]"),
    ("Theme", "[placeholder]"),
)


def render_neofetch(book: Book, cwd: tuple[str, ...] = (), width: int = 80,
                    color: bool = False) -> str:
    """An in-world SOL identity card; never inspect or claim to be the host OS."""
    width = sensible_width(width)
    portrait = HEGEL_ASCII.splitlines()
    if max(map(len, portrait)) > width:
        portrait = HEGEL_ASCII_SMALL.splitlines()
    portrait_width = max(map(len, portrait))
    gap = 3
    side_by_side = width - portrait_width - gap >= 32
    panel_width = width - portrait_width - gap if side_by_side else width
    fields = (
        ("OS", "SOL (concept preview)"),
        ("Shell", f"SOL-shell {VERSION}"),
        ("Stage", "BEING"),
        *NEOFETCH_PLACEHOLDERS,
        ("Logic", "Being / Essence / Concept"),
        ("Passages", f"{len(book.passages):,}"),
        ("Location", display_path(cwd)),
    )
    panel = ["SOL@Idea", "--------"]
    for label, value in fields:
        panel.extend(textwrap.wrap(f"{label}: {value}", width=panel_width,
                                   subsequent_indent="  ", break_on_hyphens=False))

    def styled(value: str, code: str = "36") -> str:
        return f"\x1b[{code}m{value}\x1b[0m" if color and value.strip() else value

    def panel_style(line: str) -> str:
        if line in {"SOL@Idea", "--------"}:
            return styled(line, "1;36")
        if any(line.startswith(label + ":") for label, _ in fields):
            label, value = line.split(":", 1)
            return styled(label + ":", "1;36") + value
        return line

    if not side_by_side:
        return "\n".join([*(styled(line) for line in portrait), "",
                          *(panel_style(line) for line in panel)])
    rows = []
    for index in range(max(len(portrait), len(panel))):
        left = portrait[index] if index < len(portrait) else ""
        right = panel[index] if index < len(panel) else ""
        if right:
            rows.append(styled(left.ljust(portrait_width)) + " " * gap + panel_style(right))
        else:
            rows.append(styled(left))
    return "\n".join(rows)


@dataclass
class ReadingSession:
    """A cursor within an explicit selection; random reads also set the cursor."""
    book: Book
    path: tuple[str, ...] = ()
    cursor: int | None = None

    def current(self) -> Passage:
        if self.cursor is None:
            raise ValueError("no current paragraph; use first, read, or open")
        return self.book.selection(self.path)[self.cursor]

    def open(self, identifier: str) -> Passage:
        passage = self.book.find_passage(identifier)
        if self.cursor is None or passage.path[:len(self.path)] != self.path:
            self.path = passage.path
        matches = self.book.selection(self.path)
        self.cursor = next(index for index, item in enumerate(matches)
                           if item.identifier == passage.identifier)
        return passage

    def read(self, path: tuple[str, ...], first: bool = False) -> Passage:
        matches = self.book.selection(path)
        if first:
            self.path, self.cursor = path, 0
            return matches[0]
        candidates = [index for index, p in enumerate(matches)
                      if p.kind != "formula" and p.random_eligible and len(re.findall(r"[A-Za-z]{2,}", p.text)) >= 8]
        if not candidates:
            candidates = [index for index, p in enumerate(matches)
                          if p.kind != "formula" and p.random_eligible and len(re.findall(r"[A-Za-z]{2,}", p.text)) >= 3]
        if not candidates:
            raise ValueError("this file has no suitable random prose paragraph; use cat")
        index = random.choice(candidates)
        self.path, self.cursor = path, index
        return matches[index]

    def move(self, offset: int) -> Passage:
        if self.cursor is None and offset < 0:
            raise ValueError("no current paragraph; use first or read")
        matches = self.book.selection(self.path)
        index = 0 if self.cursor is None else self.cursor + offset
        if index < 0:
            raise ValueError("already at the beginning of this selection")
        if index >= len(matches):
            raise ValueError("already at the end of this selection")
        self.cursor = index
        return matches[index]


def install_completion(root: Node, get_cwd, workspace: bool = False):
    """Optional standard-library tab completion; safe on systems without readline."""
    try:
        import readline
    except ImportError:
        return lambda: None
    old_completer = readline.get_completer()
    old_delimiters = readline.get_completer_delims()
    commands = ("ls", "cd", "up", "pwd", "tree", "read", "first", "next", "previous",
                "cat", "search", "open", "context", "info", "where", "guide", "neofetch", "source", "help", "exit")
    if workspace:
        commands += ("workspace", "resume", "bookmark", "note", "compare", "review", "relate")
    def complete(text: str, state: int):
        try:
            buffer = readline.get_line_buffer()
            if " " not in buffer:
                choices = [command for command in commands if command.startswith(text)]
            elif buffer.startswith("source "):
                choices = [action for action in ("show", "close", "set-pdf", "info")
                           if action.startswith(text)] if buffer.count(" ") == 1 else []
            else:
                parent, _, fragment = text.rpartition("/")
                node, _ = resolve_path(parent + "/" if "/" in text else None, get_cwd(), root)
                choices = [
                    (parent + "/" if "/" in text else "") + child.name
                    + ("/" if child.is_directory else "")
                    for child in node.children if child.name.casefold().startswith(fragment.casefold())
                ]
            return choices[state] if state < len(choices) else None
        except (ValueError, IndexError):
            return None
    readline.set_completer_delims(" \t\n")
    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    def restore():
        readline.set_completer(old_completer)
        readline.set_completer_delims(old_delimiters)
    return restore


SHELL_HELP = """ls [PATH]                         list files and divisions
cd [PATH]                         navigate (/ root; .. parent; - previous)
up                                move to the parent directory
pwd                               print the current directory
tree [PATH] --depth N              show the outline; default is the full tree
read [PATH]                        read randomly and set the reading cursor
first [PATH]                       start the selection in book order
next / previous                   move within the reading selection
cat FILE                          display the complete file in book order
search QUERY [PATH] --word --limit N
                                  literal search (default: current subtree)
open ID|RESULT                    open a passage or latest search result
context [N]                       neighbors in book order (default 1; maximum 10)
where                             show current passage and reading position
info [PATH]                       title, pages, counts, and pending review
compare PATH_A PATH_B              open complete files together in kitty
compare open / close              refresh the last desk / close it
guide [PATH] --depth N             beginner guide and book tree (default depth 1)
neofetch                          ASCII Hegel and SOL's concept-preview identity
help / exit                       show commands / leave SOL
Search does not move the reading cursor. Context can cross file boundaries.
Quote multiword queries. Paths accept aliases; Tab completes full names.
This is a book-navigation shell: type one command per line."""


class ShellParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def shell_options(verb: str, arguments: list[str]) -> argparse.Namespace:
    parser = ShellParser(prog=verb, add_help=False)
    if verb == "search":
        parser.add_argument("query")
        parser.add_argument("path", nargs="?")
        parser.add_argument("--word", action="store_true")
        parser.add_argument("--limit", type=int, default=20)
    else:
        parser.add_argument("path", nargs="?")
        parser.add_argument("--depth", type=int, default=1 if verb == "guide" else None)
    return parser.parse_args(arguments)


def run_shell(book: Book, width: int, plain: bool = False, color: bool = False,
              workspace_reader=None, read_command=None, write_output=None,
              ui_mode="basic", editing_mode="emacs", draft_reader=None,
              source_pdf=None, source_pane=None, auto_width=False, comparison_pane=None) -> int:
    """Run the linear shell through replaceable, synchronous input/output seams.

    The optional adapter owns completion and accepts one command at a time;
    workspace operations remain unchanged. No third-party UI is required here.
    write_output follows print's calling convention, including end= for cat.
    """
    cwd: tuple[str, ...] = ()
    previous_cwd: tuple[str, ...] | None = None
    results: list[Passage] = []
    session = ReadingSession(book)
    emit = write_output if write_output is not None else print
    restore = lambda: None
    adapter = None
    source_service = None
    last_comparison = None

    def reflow_current():
        nonlocal width
        if not auto_width:
            return
        current_width = sensible_width(None)
        if current_width == width:
            return
        width = current_width
        if workspace_reader is not None:
            workspace_reader.width = width
        try:
            current = session.current()
        except ValueError:
            return
        emit(render_passage(current, width, plain, color))

    try:
        emit("SOL. Type 'guide' to get started; 'help' for commands.")
        if workspace_reader is not None:
            from sol.workspace.reader import safe_output
            emit(f"Workspace: {workspace_reader.store.path.stem}")
            emit("Actor: " + safe_output(workspace_reader.actor) if workspace_reader.actor else
                 "No actor selected; authored writes require --actor NAME.")
            if workspace_reader.store.get_state() is not None:
                try:
                    cwd, previous_cwd, passage, message = workspace_reader.restore(session)
                    if message:
                        emit(message)
                    emit(render_passage(passage, width, plain, color))
                except ValueError as error:
                    emit(f"sol: saved position not restored: {error}\n"
                         "The reference is retained. Inspect the workspace or deliberately start another reading.")
        if read_command is None and ui_mode != "basic":
            from sol.terminal.prompt import create_adapter
            adapter = create_adapter(book, lambda: cwd, workspace_reader, mode=ui_mode,
                                     plain=plain, editing_mode=editing_mode)
            if adapter is not None:
                read_command = adapter.read_command
                draft_reader = adapter.read_draft
        if read_command is None:
            restore = install_completion(book.root, lambda: cwd, workspace=workspace_reader is not None)
        while True:
            try:
                command = (read_command if read_command is not None else input)(f"sol:{display_path(cwd)}$ ")
            except EOFError:
                emit()
                return 0
            except KeyboardInterrupt:
                emit("\nType 'exit' to leave.")
                continue
            before_command = (cwd, previous_cwd, session.path, session.cursor,
                              workspace_reader.resumed_reference if workspace_reader else None)
            try:
                if not isinstance(command, str):
                    raise ValueError("command input must be text; adapters must signal cancellation or EOF explicitly")
                parts = shlex.split(command)
                if not parts:
                    continue
                verb, arguments = parts[0], parts[1:]
                if auto_width:
                    width = sensible_width(None)
                    if workspace_reader is not None:
                        workspace_reader.width = width
                if verb == "compare" and (not arguments or arguments[0] not in {"save", "list", "show"}):
                    from sol.workspace.reader import safe_output
                    from sol.workspace.comparison import capture_comparison, capture_paths
                    action = arguments[0] if arguments else ""
                    if action == "close":
                        if len(arguments) != 1:
                            raise ValueError("compare close does not take a name")
                        if comparison_pane is not None:
                            comparison_pane.close()
                        reflow_current()
                        emit("Comparison desk closed.")
                        continue
                    operands = arguments[1:] if action == "open" else arguments
                    parser = ShellParser(prog="compare", add_help=False)
                    parser.add_argument("paths", nargs="*")
                    parser.add_argument("--question", default=None)
                    options = parser.parse_intermixed_args(operands)
                    if not options.paths and action == "open" and options.question is None:
                        if last_comparison is None:
                            raise ValueError("Choose two paths: compare PATH_A PATH_B. "
                                             "Or use compare open NAME for a saved comparison.")
                        kind, targets, question = last_comparison
                    elif action == "open" and len(options.paths) == 1 and options.question is None:
                        kind, targets, question = "saved", options.paths[0], ""
                    elif len(options.paths) == 2:
                        kind, targets, question = "paths", options.paths, options.question or ""
                    else:
                        raise ValueError("Choose two paths: compare PATH_A PATH_B [--question TEXT]. "
                                         "Use compare open NAME for a saved comparison.")
                    if kind == "saved":
                        if workspace_reader is None:
                            raise ValueError("compare open NAME requires a reading workspace; start with sol-kitty")
                        captured = capture_comparison(workspace_reader, targets)
                        remembered = (kind, targets, question)
                        captured["refresh_command"] = "compare open"
                    else:
                        captured = capture_paths(book, targets, cwd=cwd, resolve_path=resolve_path,
                                                 workspace_reader=workspace_reader, question=question)
                        remembered = (kind, [s["path"] for s in captured["selections"]], question)
                    if comparison_pane is None:
                        from sol.terminal.kitty import ComparisonPane
                        comparison_pane = ComparisonPane()
                    comparison_pane.show(captured)
                    last_comparison = remembered
                    reflow_current()
                    if kind == "paths":
                        lines = ["Comparison desk opened."]
                        for label, card in zip(("A", "B"), captured["records"]):
                            lines.append(f"{label}: {card.get('display_path') or card['path']} ({len(card['members'])} text records)")
                        emit(safe_output("\n".join(lines)))
                    else:
                        emit(safe_output(f"Comparison desk: {captured['comparison']['name']}"))
                    emit("Select A or B in the desk to scroll that text. "
                         "Use compare open to refresh; compare close to close.")
                    continue
                if verb == "source":
                    from sol.terminal.source import SourceService
                    from sol.workspace.reader import safe_output
                    action = arguments[0] if arguments else "show"
                    targets = arguments[1:]
                    if action not in {"show", "close", "set-pdf", "info"}:
                        raise ValueError("use source show [UUID], source close, source set-pdf PATH, or source info")
                    if len(targets) > 1 or (action in {"close", "info"} and targets):
                        raise ValueError(f"source {action}: unexpected arguments")
                    if action == "close":
                        if source_pane is not None:
                            source_pane.close()
                        reflow_current()
                        emit("Source pane closed.")
                        continue
                    if source_service is None:
                        source_service = SourceService(book, source_pdf=source_pdf)
                    if action == "set-pdf":
                        if not targets:
                            raise ValueError("source set-pdf requires a local PDF path")
                        location = source_service.set_pdf(Path(targets[0]))
                        emit(safe_output(f"Verified source PDF remembered: {location}"))
                    elif action == "info":
                        emit(safe_output(json.dumps(source_service.inspect_info(), ensure_ascii=False, indent=2)))
                    else:
                        if source_pane is None:
                            from sol.terminal.kitty import SourcePane
                            source_pane = SourcePane()
                        identifier = targets[0] if targets else session.current().identifier
                        request = source_service.capture(identifier)
                        source_pane.show(request)
                        reflow_current()
                        emit(f"Source PDF verified; {len(request['sources'])} source page(s).\n"
                             f"Pinned source: {request['target_id']}\n"
                             "Use source show to refresh.")
                    continue
                if verb == "note" and arguments and arguments[0] == "edit" and len(arguments) == 2:
                    if workspace_reader is None:
                        raise ValueError("note edit requires a workspace and actor")
                    if draft_reader is None:
                        raise ValueError("multiline note editing requires the enhanced prompt; "
                                         "use note edit NOTE_ID \"TEXT\" --expect-revision N for basic input")
                    captured = workspace_reader.prepare_annotation_edit(arguments[1])
                    emit(f"Editing your annotation {captured.identifier} at revision {captured.revision}.\n"
                         "Ctrl-S saves; Ctrl-C cancels. Earlier revisions and original source binding are retained.")
                    try:
                        body = draft_reader("Edit personal note: ", default=captured.body)
                    except (KeyboardInterrupt, EOFError):
                        emit("Edit cancelled; nothing was saved.")
                        continue
                    record = workspace_reader.save_annotation_edit(captured, body)
                    emit(workspace_reader.annotation_edit_result(captured.revision, record))
                    continue
                if verb == "note" and arguments and arguments[0] == "draft":
                    if workspace_reader is None:
                        raise ValueError("note draft requires a workspace and actor")
                    if draft_reader is None:
                        raise ValueError("note draft requires the enhanced prompt in an interactive terminal; "
                                         "install .[shell] or use note add \"TEXT\"")
                    draft_options = ShellParser(prog="note draft", add_help=False)
                    draft_options.add_argument("--on", dest="identifier")
                    options = draft_options.parse_args(arguments[1:])
                    workspace_reader.require_author()
                    reference = workspace_reader.current_reference(session, options.identifier)
                    inspected_digest = reference.record['content_sha256']
                    inspected_target = reference.target_id
                    draft_actor = workspace_reader.actor
                    emit("Personal annotation draft. Ctrl-S saves; Ctrl-C cancels. Drafts are not stored in history.")
                    try:
                        body = draft_reader("Personal note: ")
                    except (KeyboardInterrupt, EOFError):
                        emit("Draft cancelled; nothing was saved.")
                        continue
                    workspace_reader.require_author()
                    if workspace_reader.actor != draft_actor or workspace_reader.store.actor != draft_actor:
                        raise ValueError("annotation actor changed during drafting; nothing was saved")
                    accepted = workspace_reader.current_reference(session, reference.requested_id)
                    if accepted.target_id != inspected_target or accepted.record['content_sha256'] != inspected_digest:
                        raise ValueError("annotation target changed during drafting; nothing was saved")
                    record = workspace_reader.store.add_annotation(reference.requested_id, body, inspected_digest)
                    emit(f"Personal annotation saved: {record['id']}\n{workspace_reader.authored(record)}")
                    continue
                if verb == "resume":
                    if len(arguments) > 1:
                        raise ValueError("resume takes at most one checkpoint revision")
                    if workspace_reader is None:
                        raise ValueError("resume requires starting SOL with --workspace NAME")
                    revision = int(arguments[0]) if arguments else None
                    cwd, previous_cwd, passage, message = workspace_reader.restore(session, revision)
                    results = []
                    if message:
                        emit(message)
                    emit(render_passage(passage, width, plain, color))
                    continue
                if verb in {"workspace", "bookmark", "note", "compare", "review", "relate"}:
                    if workspace_reader is None:
                        raise ValueError(f"{verb} requires starting SOL with --workspace NAME")
                    from sol.workspace.reader import safe_output
                    outcome = workspace_reader.execute(verb, arguments, session)
                    if outcome.open_id:
                        reference = workspace_reader.current_reference(session, outcome.open_id)
                        passage = session.open(reference.target_id)
                        workspace_reader.resumed_reference = reference
                        workspace_reader.checkpoint(session, cwd, previous_cwd)
                        emit(render_passage(passage, width, plain, color))
                    if outcome.text:
                        emit(safe_output(outcome.text))
                    continue
                if verb in {"search", "tree", "guide"}:
                    options = shell_options(verb, arguments)
                    node, path = resolve_path(options.path, cwd, book.root)
                    if verb == "search":
                        matches = book.search(options.query, path, options.word, options.limit)
                        results = matches
                        emit(render_search_results(matches, options.query, width, options.word))
                    elif verb == "tree":
                        emit(render_tree(node, depth=options.depth))
                    else:
                        emit(render_guide(book, width, options.depth, node))
                    continue
                if len(arguments) > 1:
                    raise ValueError(f"{verb} expects at most one argument")
                argument = arguments[0] if arguments else None
                if verb in {"exit", "quit"}:
                    if argument is not None:
                        raise ValueError(f"{verb} does not take an argument")
                    return 0
                if verb == "help":
                    if argument is not None:
                        raise ValueError("help does not take an argument")
                    emit(SHELL_HELP)
                    emit("\nsource show [UUID]   view verified source pages in the SOL kitty desk\n"
                         "source close         close the source pane\n"
                         "source set-pdf PATH  verify and remember this edition's local PDF\n"
                         "source info          inspect the source-file association")
                    if workspace_reader is not None:
                        from sol.workspace.reader import WORKSPACE_HELP
                        emit("\n" + WORKSPACE_HELP)
                elif verb == "neofetch":
                    if argument is not None:
                        raise ValueError("neofetch does not take an argument")
                    emit(render_neofetch(book, cwd, width, color and not plain))
                elif verb == "pwd":
                    if argument is not None:
                        raise ValueError("pwd does not take an argument")
                    emit(display_path(cwd))
                elif verb in {"next", "previous", "prev"}:
                    if argument is not None:
                        raise ValueError(f"{verb} does not take a path")
                    passage = session.move(1 if verb == "next" else -1)
                    if workspace_reader is not None:
                        workspace_reader.checkpoint(session, cwd, previous_cwd)
                    emit(render_passage(passage, width, plain, color))
                elif verb in {"cd", "up"}:
                    if verb == "up" and argument is not None:
                        raise ValueError("up does not take an argument")
                    if verb == "cd" and argument == "-":
                        if previous_cwd is None:
                            raise ValueError("no previous directory")
                        node, path = resolve_path(display_path(previous_cwd), (), book.root)
                    else:
                        node, path = resolve_path(".." if verb == "up" else argument or "/", cwd, book.root)
                    if not node.is_directory:
                        raise ValueError("not a directory")
                    if path != cwd:
                        previous_cwd = cwd
                        cwd = path
                        if workspace_reader is None:
                            session.path, session.cursor = cwd, None
                        else:
                            # Browsing and reading are independent in a workspace.
                            workspace_reader.checkpoint(session, cwd, previous_cwd)
                elif verb == "open":
                    if argument is None:
                        raise ValueError("open requires a passage ID or search result number")
                    if argument.isdecimal():
                        number = int(argument)
                        if not 1 <= number <= len(results):
                            raise ValueError("no such result in the latest search")
                        identifier = results[number - 1].identifier
                    else:
                        identifier = argument
                    passage = session.open(identifier)
                    if workspace_reader is not None:
                        workspace_reader.resumed_reference = workspace_reader.current_reference(session, identifier)
                        workspace_reader.checkpoint(session, cwd, previous_cwd)
                    emit(render_passage(passage, width, plain, color))
                elif verb == "context":
                    radius = 1 if argument is None else int(argument)
                    emit(render_context(book, session.current(), radius, width, plain, color))
                elif verb == "where":
                    if argument is not None:
                        raise ValueError("where does not take an argument")
                    current = session.current()
                    emit(render_info(book, current.node, current.path, width))
                    emit(f"ID {current.identifier}")
                    emit(f"Position {session.cursor + 1} of {len(book.selection(session.path))} "
                          f"in {display_path(session.path)}")
                elif verb in {"ls", "read", "first", "cat", "info"}:
                    node, path = resolve_path(argument, cwd, book.root)
                    if verb == "ls":
                        emit(render_listing(node))
                    elif verb == "info":
                        emit(render_info(book, node, path, width))
                    elif verb in {"read", "first"}:
                        passage = session.read(path, verb == "first")
                        if workspace_reader is not None:
                            workspace_reader.checkpoint(session, cwd, previous_cwd)
                        emit(render_passage(passage, width, plain, color))
                    else:
                        if node.is_directory:
                            raise ValueError("cat takes a file; use first or read for a directory")
                        for passage in book.selection(path):
                            emit(render_passage(passage, width, plain, color), end="\n\n")
                else:
                    raise ValueError(f"unknown command: {verb}; type help")
            except KeyboardInterrupt:
                emit("Command cancelled.")
            except (ValueError, RuntimeError) as error:
                if workspace_reader is not None:
                    from sol.workspace.store import WorkspaceError
                    if isinstance(error, WorkspaceError):
                        cwd, previous_cwd, session.path, session.cursor, workspace_reader.resumed_reference = before_command
                emit(f"sol: {error}")
    finally:
        restore()
        if adapter is not None:
            adapter.close()
        if source_pane is not None:
            source_pane.cleanup()
        if comparison_pane is not None:
            comparison_pane.cleanup()






def validate_options(args: argparse.Namespace) -> None:
    if args.command:
        actions = (args.structure, args.guide, args.shell, args.none, args.random, args.read is not None,
                   args.first is not None, args.cat is not None, args.search is not None,
                   args.passage is not None, args.info is not None, args.set_corpus is not None,
                   args.resume, args.workspace_export, args.workspace_check, args.workspace_backup is not None,
                   args.workspace_upgrade is not None,
                   args.review_queue)
        if any(actions):
            raise ValueError("guide cannot be combined with another action")
        args.guide = True
    actions = (args.structure, args.guide, args.shell, args.none, args.random, args.read is not None,
               args.first is not None, args.cat is not None, args.search is not None,
               args.passage is not None, args.info is not None, args.set_corpus is not None,
               args.resume, args.workspace_export, args.workspace_check, args.workspace_backup is not None,
               args.workspace_upgrade is not None,
               args.review_queue)
    if not any(actions) or args.none:
        args.shell = True
    if args.shell and not args.none and args.pdf is not None:
        raise ValueError("the persistent shell requires an indexed Markdown corpus, not --pdf. "
                         "Use sol -n --pdf PATH for a temporary legacy shell or sol -r --pdf PATH "
                         "for a legacy random passage.")
    if args.none and (args.workspace is not None or args.actor is not None or args.workspace_dir is not None):
        raise ValueError("-n/--none does not use a workspace or actor; omit workspace options")
    if not args.shell and (args.ui is not None or args.editing_mode is not None):
        raise ValueError("--ui and --editing-mode are available only in the shell")
    if args.source_pdf is not None and (not args.shell or args.pdf is not None):
        raise ValueError("--source-pdf is for source viewing in the canonical shell; omit --pdf and one-shot actions")
    if args.word and args.search is None:
        raise ValueError("--word requires --search")
    if args.search is None and not args.review_queue and (args.within is not None or args.limit is not None):
        raise ValueError("--within and --limit require --search or --review-queue")
    if args.search is not None and not args.search.strip():
        raise ValueError("search requires a nonempty query")
    if args.limit is not None and not 1 <= args.limit <= 1000:
        raise ValueError("--limit must be between 1 and 1000")
    if args.context is not None:
        if args.passage is None:
            raise ValueError("--context requires --passage")
        if not 0 <= args.context <= 10:
            raise ValueError("--context must be between 0 and 10")
    if args.depth is not None:
        if not args.structure and not args.guide:
            raise ValueError("--depth requires --structure or guide")
        if not 0 <= args.depth <= 32:
            raise ValueError("--depth must be between 0 and 32")
    if args.json and (args.shell or args.guide):
        raise ValueError("--json is not a shell/guide mode; use sol -r --json for a random passage")
    if args.set_corpus is not None and (args.corpus is not None or args.pdf is not None):
        raise ValueError("--set-corpus cannot be combined with --corpus or --pdf")
    if args.workspace is None and not args.shell and (args.workspace_dir is not None or args.actor is not None or args.resume
                                   or args.workspace_export or args.workspace_check or args.workspace_backup is not None
                                   or args.workspace_upgrade is not None):
        raise ValueError("workspace options require --workspace NAME")
    if args.resume_revision is not None and (not args.resume or args.resume_revision < 1):
        raise ValueError("--resume-revision requires --resume and a positive checkpoint revision")
    if args.review_queue and args.pdf is not None:
        raise ValueError("--review-queue requires the canonical corpus, not --pdf")
    if args.workspace is not None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.workspace):
            raise ValueError("workspace name must contain 1–64 letters, numbers, underscores or hyphens")
        if args.actor is not None and not args.actor.strip():
            raise ValueError("--actor requires a nonempty name")
        if args.pdf is not None or args.set_corpus is not None or args.guide or args.structure:
            raise ValueError("--workspace requires the indexed corpus and cannot accompany --pdf, --set-corpus, or an outline action")
        if args.search is not None or args.info is not None or args.cat is not None:
            raise ValueError("--workspace is available for reading, --shell, --resume, and --workspace-export")
        if args.context is not None:
            raise ValueError("workspace reading does not yet save a context view; use --passage ID --context N without --workspace")
    if args.workspace_export and args.plain:
        raise ValueError("--workspace-export emits an artifact, not plain passage output; omit --plain")
    if args.export_format is not None and not args.workspace_export:
        raise ValueError("--export-format requires --workspace-export")
    if args.workspace_export and args.export_format == "markdown" and args.json:
        raise ValueError("--json cannot accompany a Markdown export; omit --json or choose --export-format json")
    if args.include_passages and not (args.workspace_export and args.export_format == "markdown"):
        raise ValueError("--include-passages requires --workspace-export --export-format markdown")


def interactive_input_available() -> bool:
    return bool(sys.stdin.isatty())


def shell_identity(book: Book, args) -> None:
    """Ask only for missing labels; accepting a name explicitly creates it later."""
    from sol.workspace.profiles import actor_name, list_actors
    from sol.workspace.reader import workspace_path

    if not book.corpus_manifest.get('corpus_id'):
        raise ValueError("a persistent shell needs an identified Markdown corpus. "
                         "Run sol-corpus-check DIRECTORY --initialize-identity, or use sol -n.")
    known = list_actors()
    if (args.workspace is None or args.actor is None) and not interactive_input_available():
        raise ValueError("workspace and actor prompts need interactive input. "
                         "Supply --workspace NAME --actor NAME, use sol -n for a temporary shell, "
                         "or sol -r for a random passage.")
    if args.workspace is None:
        from sol.workspace.catalog import discover_workspaces
        source_digest = book.corpus_manifest.get('source', {}).get('sha256')
        recent = discover_workspaces(book.corpus_manifest['corpus_id'], source_digest, args.workspace_dir)
        default_workspace = recent[0]['name'] if recent else 'reading'
        if recent:
            print('Recent workspaces for this corpus:')
            for number, entry in enumerate(recent, 1):
                print(f"  {number}. {entry['name']} | {entry['last_activity'][:10]} | {entry['scope'] or '[no reading yet]'}")
            print('Choose a displayed number, type a workspace name, or enter a new name.')
        while True:
            response = input(f'Workspace [{default_workspace}]: ').strip()
            name = response or default_workspace
            if recent and response.isdecimal():
                number = int(response) if len(response) <= 2 else 0
                if not 1 <= number <= len(recent):
                    print('sol: choose a displayed workspace number or a name (use --workspace for a numeric name)')
                    continue
                name = recent[number - 1]['name']
            try:
                workspace_path(name, args.workspace_dir)
            except ValueError as error:
                print(f'sol: {error}')
                continue
            args.workspace = name
            break
    if args.actor is None:
        if known:
            print('Known actors: ' + ', '.join(profile['name'] for profile in known[-10:]))
        default = known[-1]['name'] if known else None
        while True:
            value = input(f'Actor [{default}]: ' if default else 'Actor (name for your own notes): ')
            try:
                args.actor = actor_name(value or default or '')
            except ValueError as error:
                print(f'sol: {error}')
                continue
            break
    else:
        args.actor = actor_name(args.actor)


def tree_data(node: Node, depth: int | None = None) -> dict:
    return {
        "title": node.title, "path": display_path(node_path(node)), "name": node.name,
        "directory": node.is_directory, "printed_page": node.start_page,
        "truncated": depth == 0 and bool(node.children),
        "children": [] if depth == 0 else [
            tree_data(child, None if depth is None else depth - 1) for child in node.children
        ],
    }


def terminal_color() -> bool:
    return bool(sys.stdout.isatty() and "NO_COLOR" not in os.environ
                and os.environ.get("TERM") != "dumb")


def emit_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def run_workspace_cli(book: Book, args, width: int, color: bool) -> int:
    """Named durable state, kept separate from corpus-only one-shot reading."""
    from sol.workspace.store import Workspace
    from sol.workspace.reader import WorkspaceReader, workspace_path

    identity = book.corpus_manifest.get("corpus_id")
    if not identity:
        directory = shlex.quote(str(book.corpus_directory))
        raise ValueError("this corpus needs an explicit permanent identity before workspace use.\n"
                         f"Run once: sol-corpus-check {directory} --initialize-identity\n"
                         "This preserves canonical text and passage IDs; do not reconvert the PDF.")
    location = workspace_path(args.workspace, args.workspace_dir)
    if (args.resume or args.workspace_export or args.workspace_check or args.workspace_backup is not None
            or args.workspace_upgrade is not None
            or args.review_queue) and not location.exists():
        raise ValueError(f"workspace does not exist: {args.workspace}; start with --workspace NAME --shell")
    provenance = {"edition": book.corpus_manifest["edition"], "source": book.corpus_manifest["source"]}
    with Workspace(location, identity, provenance, actor=args.actor or "Reader") as store:
        if args.shell:
            from sol.workspace.profiles import register_actor
            register_actor(args.actor)
        reader = WorkspaceReader(book, store, args.actor, resolve_path, display_path,
                                 render_passage, width, args.plain, color)
        if args.workspace_export:
            print(reader.export_text(args.export_format or 'json', include_passages=args.include_passages))
            return 0
        if args.workspace_check:
            report = reader.health()
            if args.json:
                emit_json(report)
            else:
                print(reader.render_health(report))
            return 0
        if args.review_queue:
            within = None if args.within is None else resolve_path(args.within, (), book.root)[1]
            rows = reader.queue(within, 20 if args.limit is None else args.limit)
            if args.json:
                emit_json(rows)
            else:
                print(reader.render_queue(rows))
            return 0
        if args.workspace_backup is not None:
            destination = store.backup(args.workspace_backup)
            if args.json:
                emit_json({"backup": str(destination), "corpus_id": identity})
            else:
                print(f"Verified workspace backup: {destination}")
            return 0
        if args.workspace_upgrade is not None:
            reader.ensure_corpus_current()
            requested = args.workspace_upgrade.expanduser().absolute()
            if requested.name != workspace_path(requested.stem, requested.parent).name:
                raise ValueError("an upgraded workspace filename must end in lowercase .sqlite3 "
                                 "so reopening its workspace name selects the same file")
            destination = store.upgrade_copy(requested)
            result = {"upgraded_copy": str(destination), "source_workspace": str(store.path),
                      "schema_version": 2, "corpus_id": identity}
            if args.json:
                emit_json(result)
            else:
                print(f"Verified upgraded copy: {destination}\nOriginal workspace retained.\n"
                      f"Open with: sol --workspace {shlex.quote(destination.stem)} "
                      f"--workspace-dir {shlex.quote(str(destination.parent))}")
            return 0
        if args.shell:
            return run_shell(book, width, args.plain, color, reader,
                             ui_mode=args.ui or 'auto', editing_mode=args.editing_mode or 'emacs',
                             source_pdf=args.source_pdf, auto_width=args.width is None)
        session = ReadingSession(book)
        cwd, previous = (), None
        if args.resume:
            cwd, previous, passage, message = reader.restore(session, args.resume_revision)
            if message:
                print(message, file=sys.stderr)
            # Latest resume is inspection; a historical resume appends a new visit.
        elif args.passage is not None:
            reference = reader.current_reference(session, args.passage)
            passage = session.open(reference.target_id)
            reader.resumed_reference = reference
            reader.checkpoint(session, cwd, previous)
        else:
            value = args.first if args.first is not None else args.read
            _, path = resolve_path(value, (), book.root)
            passage = session.read(path, args.first is not None)
            reader.checkpoint(session, cwd, previous)
        if args.json:
            data = passage_data(passage, book)
            data["workspace"] = {"name": args.workspace, "corpus_id": identity,
                                 "revision": reader.revision,
                                 "requested_id": reader.resumed_reference.requested_id
                                 if reader.resumed_reference else passage.identifier}
            emit_json(data)
        else:
            print(render_passage(passage, width, args.plain, color))
        return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] in {"read", "compare"}:
        from sol.terminal.commands import main as command_main
        return command_main(arguments)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_options(args)
        if args.set_corpus is not None:
            corpus, configuration = save_corpus(args.set_corpus)
            if args.json:
                emit_json({"corpus": str(corpus), "configuration": str(configuration)})
            else:
                print(f"Default corpus: {corpus}\nSaved in: {configuration}")
            return 0
        width = sensible_width(args.width)
        color = terminal_color() and not args.plain and not args.json
        if args.guide and args.corpus is None and args.pdf is None:
            # The guide must still explain setup when an automatic source is broken.
            try:
                corpus = discover_corpus()
                book = load_corpus_book(corpus) if corpus is not None else None
            except ValueError as error:
                print(f"sol: {error}\nShowing the abbreviated visual guide.", file=sys.stderr)
                book = None
            print(render_guide(book, width, 1 if args.depth is None else args.depth))
            return 0
        corpus = None if args.pdf is not None else discover_corpus(args.corpus)
        if corpus is not None:
            book = load_corpus_book(corpus)
        elif args.pdf is not None:
            pdf = args.pdf.expanduser()
            if args.passage and re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", args.passage):
                raise ValueError("A canonical passage UUID requires the Markdown corpus, not --pdf.\n"
                                 "Use sol --set-corpus DIRECTORY, then rerun without --pdf. "
                                 "The legacy PDF reader has different passage identifiers.")
            if not pdf.is_file():
                raise ValueError(f"PDF not found: {pdf}")
            book = load_book(pdf)
        else:
            if args.guide:
                print(render_guide(width=width, depth=1 if args.depth is None else args.depth))
                return 0
            if args.structure:
                if args.json:
                    emit_json({"outline": tree_data(ROOT, args.depth), "abbreviated": True})
                else:
                    print(render_tree(depth=args.depth))
                    print("\nAbbreviated outline. Select a corpus with --set-corpus DIRECTORY for subdivisions.")
                return 0
            raise ValueError(
                "No local Markdown corpus found.\n"
                "Select an existing corpus once with sol --set-corpus DIRECTORY, "
                "or use --corpus DIRECTORY / SOL_CORPUS.\n"
                f"For an initial import: sol-corpus convert --pdf {PDF_FILENAME}\n"
                "PDF extraction is never automatic; --pdf PATH explicitly selects the slow legacy reader."
            )
        if args.shell and not args.none:
            shell_identity(book, args)
        if args.workspace is not None:
            return run_workspace_cli(book, args, width, color)
        if args.review_queue:
            if not book.canonical_records:
                raise ValueError("--review-queue requires the canonical Markdown corpus, not the legacy PDF reader")
            from sol.workspace.diagnostics import review_queue
            from sol.workspace.reader import render_review_queue
            within = None if args.within is None else resolve_path(args.within, (), book.root)[1]
            rows = review_queue(book, {"reviews": []}, within, 20 if args.limit is None else args.limit)
            if args.json:
                emit_json(rows)
            else:
                print(render_review_queue(rows, width))
            return 0
        if args.structure:
            if args.json:
                emit_json({"outline": tree_data(book.root, args.depth), "abbreviated": False})
            else:
                print(render_tree(book.root, depth=args.depth))
        elif args.guide:
            print(render_guide(book, width, 1 if args.depth is None else args.depth))
        elif args.shell:
            return run_shell(book, width, args.plain, color, ui_mode=args.ui or 'auto',
                             editing_mode=args.editing_mode or 'emacs', source_pdf=args.source_pdf,
                             auto_width=args.width is None)
        elif args.search is not None:
            _, path = resolve_path(args.within, (), book.root)
            passages = book.search(args.search, path, args.word,
                                   20 if args.limit is None else args.limit)
            if args.json:
                emit_json([passage_data(passage, book) for passage in passages])
            elif args.plain:
                print("\n\n".join(render_passage(passage, width, plain=True) for passage in passages))
            else:
                print(render_search_results(passages, args.search, width, args.word))
        elif args.info is not None:
            node, path = resolve_path(args.info, (), book.root)
            if args.json:
                emit_json(location_data(book, node, path))
            else:
                print(render_info(book, node, path, width))
        elif args.passage is not None:
            passage = book.find_passage(args.passage)
            if args.context is not None:
                if args.json:
                    emit_json([passage_data(item, book) for item in context_passages(book, passage, args.context)])
                else:
                    print(render_context(book, passage, args.context, width, args.plain, color))
            elif args.json:
                emit_json(passage_data(passage, book))
            else:
                print(render_passage(passage, width, args.plain, color))
        elif args.cat is not None:
            node, path = resolve_path(args.cat, (), book.root)
            if node.is_directory:
                raise ValueError("--cat takes a virtual file")
            if args.json:
                emit_json([passage_data(passage, book) for passage in book.selection(path)])
            else:
                for passage in book.selection(path):
                    print(render_passage(passage, width, args.plain, color), end="\n\n")
        else:
            value = args.first if args.first is not None else args.read
            _, path = resolve_path(value, (), book.root)
            passage = ReadingSession(book).read(path, args.first is not None)
            if args.json:
                emit_json(passage_data(passage, book))
            else:
                print(render_passage(passage, width, args.plain, color))
        return 0
    except ValueError as error:
        print(f"sol: {error}", file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(f"sol: {error}", file=sys.stderr)
        return 1
    except EOFError:
        print("\nsol: setup cancelled; no workspace or actor was created", file=sys.stderr)
        return 0


def cli(argv: list[str] | None = None) -> int:
    """Console entry shared by pipx and direct script execution."""
    try:
        status = main(argv)
        sys.stdout.flush()
        return status
    except KeyboardInterrupt:
        print("\nsol: interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        # Avoid a second broken-pipe error while Python flushes at shutdown.
        try:
            with open(os.devnull, "w") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except (OSError, AttributeError, ValueError):
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(cli())
