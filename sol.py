#!/usr/bin/env python3
"""A small terminal reader and virtual filesystem for Hegel's *Science of Logic*."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import random
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


# This index is specific to the Cambridge di Giovanni edition supplied with the
# project. Its printed page 7 is PDF page 80; page 827 begins the editor's
# appendix, so it is deliberately outside the readable corpus.
PDF_FILENAME = "georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf"
FIRST_TEXT_PAGE = 80
LAST_TEXT_PAGE = 826
PRINTED_PAGE_OFFSET = 73
MIN_PARAGRAPH_LENGTH = 160


@dataclass(frozen=True)
class Node:
    """One item in the virtual filesystem; children make a directory."""

    name: str
    title: str
    start_page: int
    children: tuple["Node", ...] = field(default_factory=tuple)

    @property
    def is_directory(self) -> bool:
        return bool(self.children)


@dataclass(frozen=True)
class Passage:
    text: str
    pdf_page: int
    printed_page: int
    node: Node
    path: tuple[str, ...]


# Directories are divisions that contain further divisions. Files are passages
# attached to the heading that begins them. Numeric prefixes are display names,
# not claims about Hegel's own numbering; they keep `ls` in reading order.
BEING = Node(
    "BEING",
    "Doctrine of Being (Book One)",
    7,
    (
        Node("00-preface-to-the-first-edition.txt", "Preface to the first edition", 7),
        Node("01-preface-to-the-second-edition.txt", "Preface to the second edition", 11),
        Node("02-introduction.txt", "Introduction", 23),
        Node("03-with-what-must-the-beginning-of-science-be-made.txt", "With what must the beginning of science be made?", 45),
        Node("04-general-division-of-being.txt", "General division of being", 56),
        Node(
            "05-determinateness-quality",
            "Section I: Determinateness (Quality)",
            58,
            (
                Node("01-being.txt", "Chapter 1: Being", 59),
                Node("02-existence.txt", "Chapter 2: Existence", 83),
                Node("03-being-for-itself.txt", "Chapter 3: Being-for-itself", 126),
            ),
        ),
        Node(
            "06-magnitude-quantity",
            "Section II: Magnitude (Quantity)",
            152,
            (
                Node("01-quantity.txt", "Chapter 1: Quantity", 154),
                Node("02-quantum.txt", "Chapter 2: Quantum", 168),
                Node("03-ratio-or-the-quantitative-relation.txt", "Chapter 3: Ratio or the quantitative relation", 271),
            ),
        ),
        Node(
            "07-measure",
            "Section III: Measure",
            282,
            (
                Node("01-specific-quantity.txt", "Chapter 1: Specific quantity", 288),
                Node("02-real-measure.txt", "Chapter 2: Real measure", 302),
                Node("03-the-becoming-of-essence.txt", "Chapter 3: The becoming of essence", 326),
            ),
        ),
    ),
)

ESSENCE = Node(
    "ESSENCE",
    "Doctrine of Essence (Book Two)",
    337,
    (
        Node(
            "01-essence-as-reflection-within",
            "Section I: Essence as reflection within",
            340,
            (
                Node("01-shine.txt", "Chapter 1: Shine", 341),
                Node("02-the-essentialities-or-the-determinations-of-reflection.txt", "Chapter 2: The essentialities or the determinations of reflection", 354),
                Node("03-ground.txt", "Chapter 3: Ground", 386),
            ),
        ),
        Node(
            "02-appearance",
            "Section II: Appearance",
            418,
            (
                Node("01-concrete-existence.txt", "Chapter 1: Concrete existence", 420),
                Node("02-appearance.txt", "Chapter 2: Appearance", 437),
                Node("03-the-essential-relation.txt", "Chapter 3: The essential relation", 449),
            ),
        ),
        Node(
            "03-actuality",
            "Section III: Actuality",
            465,
            (
                Node("01-the-absolute.txt", "Chapter 1: The absolute", 466),
                Node("02-actuality.txt", "Chapter 2: Actuality", 477),
                Node("03-the-absolute-relation.txt", "Chapter 3: The absolute relation", 489),
            ),
        ),
    ),
)

CONCEPT = Node(
    "CONCEPT",
    "Doctrine of the Concept (Volume Two / Subjective Logic)",
    507,
    (
        Node("00-foreword.txt", "Foreword", 507),
        Node("01-of-the-concept-in-general.txt", "Of the concept in general", 508),
        Node("02-division.txt", "Division", 526),
        Node(
            "03-subjectivity",
            "Section I: Subjectivity",
            528,
            (
                Node("01-the-concept.txt", "Chapter 1: The concept", 529),
                Node("02-judgment.txt", "Chapter 2: Judgment", 550),
                Node("03-the-syllogism.txt", "Chapter 3: The syllogism", 588),
            ),
        ),
        Node(
            "04-objectivity",
            "Section II: Objectivity",
            625,
            (
                Node("01-mechanism.txt", "Chapter 1: Mechanism", 631),
                Node("02-chemism.txt", "Chapter 2: Chemism", 645),
                Node("03-teleology.txt", "Chapter 3: Teleology", 651),
            ),
        ),
        Node(
            "05-the-idea",
            "Section III: The idea",
            670,
            (
                Node("01-life.txt", "Chapter 1: Life", 676),
                Node("02-the-idea-of-cognition.txt", "Chapter 2: The idea of cognition", 689),
                Node("03-the-absolute-idea.txt", "Chapter 3: The absolute idea", 735),
            ),
        ),
    ),
)

ROOT = Node("", "The Science of Logic", 7, (BEING, ESSENCE, CONCEPT))


def extract_pages(pdf: Path) -> list[str]:
    """Extract precisely the PDF pages that contain Hegel's text."""
    program = shutil.which("pdftotext")
    if not program:
        raise RuntimeError("pdftotext is required. Install Poppler (for example: sudo apt install poppler-utils).")
    try:
        result = subprocess.run(
            [program, "-f", str(FIRST_TEXT_PAGE), "-l", str(LAST_TEXT_PAGE), "-layout", str(pdf), "-"],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(error.stderr.strip() or "PDF extraction failed.") from error
    pages = result.stdout.split("\f")
    expected = LAST_TEXT_PAGE - FIRST_TEXT_PAGE + 1
    if len(pages) < expected:
        raise RuntimeError("The PDF did not yield every expected text page.")
    return pages[:expected]


def clean_line(raw_line: str) -> str | None:
    """Remove this edition's recurring page furniture, retaining body prose."""
    compact = " ".join(raw_line.split())
    if not compact:
        return ""
    # Odd-numbered pages place the printed page number alone at the foot.
    if re.fullmatch(r"\d{1,3}", compact):
        return None
    if re.fullmatch(r"\d+ Georg Wilhelm Friedrich Hegel", compact):
        return None
    if re.fullmatch(r"(?:The Science of Logic|The absolute idea|Quantum|Specific quantity|Real measure|The becoming of essence) \d+", compact):
        return None
    # Marginal references to the German critical edition can occur at either
    # edge of a prose line. They are not part of the translation.
    line = re.sub(r"^\s*\d+\.\d+\s+", "", raw_line)
    line = re.sub(r"\s{2,}\d+\.\d+\s*$", "", line)
    compact = " ".join(line.split())
    # A stand-alone title and printed page number is a running header.
    if re.fullmatch(r"[A-Z][A-Za-z ,’'\-]{0,80}\s+\d{1,3}", compact):
        return None
    # Stand-alone numbered notes are editorial or translator footnotes.
    if re.fullmatch(r"\d+\s+.+", compact) and len(compact) < 120:
        return None
    return compact


def starts_note(raw_line: str) -> bool:
    """Identify a note block before its continuation lines can enter the prose."""
    compact = " ".join(raw_line.split())
    return bool(
        # Ordinary enumerated prose uses a period ("1."). Bare Arabic
        # numerals followed by text are notes in this edition.
        re.match(r"^\s*\d+\s+\S", raw_line)
        and not re.fullmatch(r"\d+ Georg Wilhelm Friedrich Hegel", compact)
    )


def tidy_paragraph(lines: list[str]) -> str:
    text = " ".join(lines)
    # Repair a word divided by the source line wrap, but preserve real hyphens.
    text = re.sub(r"(?<=[A-Za-z])-[ ]+(?=[a-z])", "", text)
    # Footnote markers are rendered as attached decimal-looking numbers.
    text = re.sub(r"\s+\d+\.\d+\s+", " ", text)
    text = re.sub(r"(?<=[A-Za-z,;:])\d{1,3}(?=\s)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def node_for_page(page: int, node: Node = ROOT, path: tuple[str, ...] = ()) -> tuple[Node, tuple[str, ...]]:
    """Find the deepest indexed logical division that has begun on ``page``."""
    eligible = [child for child in node.children if child.start_page <= page]
    if not eligible:
        return node, path
    child = eligible[-1]
    return node_for_page(page, child, path + (child.name,))


def extract_passages(pdf: Path) -> list[Passage]:
    """Return readable main-text paragraphs, each tied to source and logic path."""
    passages: list[Passage] = []
    current: list[str] = []
    start_pdf_page: int | None = None

    def finish() -> None:
        nonlocal current, start_pdf_page
        if not current or start_pdf_page is None:
            current, start_pdf_page = [], None
            return
        text = tidy_paragraph(current)
        # Do not serve headings or free-standing editor/translator footnotes.
        if (
            len(text) >= MIN_PARAGRAPH_LENGTH
            and not re.fullmatch(r"[A-Z0-9 .,:;—-]+", text)
            and not re.match(r"^\d+\s", text)
        ):
            printed_page = start_pdf_page - PRINTED_PAGE_OFFSET
            node, path = node_for_page(printed_page)
            passages.append(Passage(text, start_pdf_page, printed_page, node, path))
        current, start_pdf_page = [], None

    skipping_note = False
    for page_offset, raw_page in enumerate(extract_pages(pdf)):
        pdf_page = FIRST_TEXT_PAGE + page_offset
        for raw_line in raw_page.splitlines():
            if skipping_note:
                if not raw_line.strip():
                    skipping_note = False
                continue
            if starts_note(raw_line):
                # Notes in this edition begin with an Arabic numeral and can
                # wrap onto several otherwise ordinary-looking lines.
                finish()
                skipping_note = True
                continue
            line = clean_line(raw_line)
            if line == "":
                finish()
            elif line is not None:
                if start_pdf_page is None:
                    start_pdf_page = pdf_page
                current.append(line)
    finish()
    if not passages:
        raise RuntimeError("No readable paragraphs were extracted from the selected PDF pages.")
    return passages


def display_path(path: tuple[str, ...]) -> str:
    return "/" + "/".join(path)


def sensible_width(requested: int | None) -> int:
    if requested is not None:
        if requested < 40:
            raise ValueError("--width must be at least 40.")
        return requested
    terminal_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(52, min(88, terminal_width - 2))


def render_passage(passage: Passage, width: int) -> str:
    location = display_path(passage.path)
    rule = "─" * width
    return "\n".join(
        (
            location,
            f"{passage.node.title} · book p. {passage.printed_page} · PDF p. {passage.pdf_page}",
            rule,
            textwrap.fill(passage.text, width=width, break_long_words=False, break_on_hyphens=False),
        )
    )


def child_by_name(node: Node, name: str) -> Node | None:
    return next((child for child in node.children if child.name == name), None)


def resolve_path(value: str | None, cwd: tuple[str, ...]) -> tuple[Node, tuple[str, ...]]:
    """Resolve a Unix-like virtual path; paths are case-sensitive like Unix."""
    pieces = [] if value is None else value.split("/")
    path = [] if value and value.startswith("/") else list(cwd)
    for piece in pieces:
        if piece in ("", "."):
            continue
        if piece == "..":
            if path:
                path.pop()
            continue
        path.append(piece)
    node = ROOT
    resolved: list[str] = []
    for piece in path:
        child = child_by_name(node, piece)
        if child is None:
            raise ValueError(f"no such path: {value}")
        node = child
        resolved.append(piece)
    return node, tuple(resolved)


def render_listing(node: Node) -> str:
    if not node.is_directory:
        return f"{node.name}\t{node.title} · book p. {node.start_page}"
    rows = []
    for child in node.children:
        suffix = "/" if child.is_directory else ""
        rows.append(f"{child.name}{suffix}\n    {child.title} · book p. {child.start_page}")
    return "\n".join(rows) or "(empty)"


def render_tree(node: Node = ROOT, prefix: str = "", include_self: bool = True) -> str:
    lines: list[str] = []
    if include_self:
        name = "/" if node is ROOT else node.name + ("/" if node.is_directory else "")
        lines.append(f"{prefix}{name}  {node.title}")
    for child in node.children:
        child_name = child.name + ("/" if child.is_directory else "")
        lines.append(f"{prefix}├── {child_name}  {child.title} · p. {child.start_page}")
        if child.is_directory:
            lines.extend(render_tree(child, prefix + "│   ", include_self=False).splitlines())
    return "\n".join(lines)


def passages_at(passages: list[Passage], path: tuple[str, ...]) -> list[Passage]:
    matches = [passage for passage in passages if passage.path[: len(path)] == path]
    if not matches:
        raise ValueError("this location has no extracted prose passages")
    return matches


def run_shell(passages: list[Passage], width: int) -> int:
    """Run a deliberately small, familiar navigation shell."""
    cwd: tuple[str, ...] = ()
    print("Science of Logic virtual filesystem. Type 'help' for commands.")
    while True:
        try:
            command = input(f"sol:{display_path(cwd)}$ ").strip()
        except EOFError:
            print()
            return 0
        if not command:
            continue
        parts = command.split(maxsplit=1)
        verb, argument = parts[0], parts[1] if len(parts) == 2 else None
        try:
            if verb in {"exit", "quit"}:
                return 0
            if verb == "help":
                print("ls [PATH]     list a logical division\ncd [PATH]     move through the virtual filesystem\npwd           show the current path\nread [PATH]   print a random passage from a file or division\ncat [PATH]    alias for read\ntree [PATH]   show a nested structure\nexit          leave the reader")
            elif verb == "pwd":
                print(display_path(cwd))
            elif verb == "ls":
                node, _ = resolve_path(argument, cwd)
                print(render_listing(node))
            elif verb == "cd":
                node, path = resolve_path(argument or "/", cwd)
                if not node.is_directory:
                    raise ValueError("not a directory")
                cwd = path
            elif verb in {"read", "cat"}:
                _, path = resolve_path(argument, cwd)
                print(render_passage(random.choice(passages_at(passages, path)), width))
            elif verb == "tree":
                node, _ = resolve_path(argument, cwd)
                print(render_tree(node))
            else:
                print(f"unknown command: {verb}. Type 'help' for commands.")
        except ValueError as error:
            print(f"sol: {error}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sol", description="Read and navigate Hegel's Science of Logic.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--structure", action="store_true", help="print the virtual filesystem's complete outline")
    mode.add_argument("--shell", action="store_true", help="open the interactive virtual filesystem")
    mode.add_argument("--read", metavar="PATH", help="read a random passage from a virtual path")
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path.cwd() / PDF_FILENAME,
        metavar="PATH",
        help=f"PDF to read (default: ./{PDF_FILENAME} in the current directory)",
    )
    parser.add_argument("--width", type=int, metavar="COLUMNS", help="line width for a displayed passage (default: terminal width, maximum 88)")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.structure:
        print(render_tree())
        return 0
    try:
        width = sensible_width(args.width)
    except ValueError as error:
        print(f"sol: {error}", file=sys.stderr)
        return 2
    if not args.pdf.is_file():
        print(f"sol: PDF not found: {args.pdf}", file=sys.stderr)
        print(f"Put {PDF_FILENAME} in the current directory or use: sol --pdf /path/to/the_science_of_logic.pdf", file=sys.stderr)
        return 2
    try:
        passages = extract_passages(args.pdf)
        if args.shell:
            return run_shell(passages, width)
        if args.read:
            _, path = resolve_path(args.read, ())
            print(render_passage(random.choice(passages_at(passages, path)), width))
        else:
            print(render_passage(random.choice(passages), width))
    except (RuntimeError, ValueError) as error:
        print(f"sol: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
