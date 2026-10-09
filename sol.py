#!/usr/bin/env python3
"""SOL: a terminal reader for the Cambridge *Science of Logic*.

Canonical local Markdown is indexed once and read through a verified JSONL
index using standard-library Python. Poppler remains available for the legacy
PDF fallback. Corpus/PDF loading and the terminal interface stay separate.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from functools import cached_property
import random
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import textwrap
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path


# This index is specific to the Cambridge di Giovanni edition supplied with the
# project. Its printed page 7 is PDF page 80; page 827 begins the editor's
# appendix, so it is deliberately outside the readable corpus.
PDF_FILENAME = "georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf"
FIRST_TEXT_PAGE = 80
LAST_TEXT_PAGE = 826
PRINTED_PAGE_OFFSET = 73
XML_NS = {"p": "http://www.w3.org/1999/xhtml"}


@dataclass
class Node:
    """One item in the virtual filesystem; children make a directory."""

    name: str
    title: str
    start_page: int
    children: tuple["Node", ...] = field(default_factory=tuple)
    label: str = ""
    anchor: tuple[int, float] | None = None
    parent: "Node | None" = field(default=None, repr=False, compare=False)

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
    end_pdf_page: int
    end_printed_page: int
    identifier: str
    heading: str = ""
    kind: str = "paragraph"
    random_eligible: bool = True


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class Line:
    words: tuple[Word, ...]
    pdf_page: int

    @cached_property
    def text(self) -> str:
        return unicodedata.normalize("NFC", " ".join(word.text for word in self.words))

    @cached_property
    def typographic_words(self) -> tuple[Word, ...]:
        # A short final line can contain one body word and several raised note
        # markers. Estimate its type from words, not those letters/numerals.
        words = tuple(word for word in self.words
                      if sum(character.isalpha() for character in word.text) >= 2)
        return words or self.words

    @cached_property
    def y(self) -> float:
        # Raised footnote numbers must not move the prose line's baseline.
        return statistics.median(word.y0 for word in self.typographic_words)

    @cached_property
    def x(self) -> float:
        return min(word.x0 for word in self.words)

    @cached_property
    def height(self) -> float:
        return statistics.median(word.height for word in self.typographic_words)

    @property
    def position(self) -> tuple[int, float]:
        return self.pdf_page, self.y


@dataclass(frozen=True)
class Page:
    number: int
    lines: tuple[Line, ...]
    body_height: float
    left: float
    right: float


@dataclass
class Book:
    root: Node
    passages: list[Passage]

    def selection(self, path: tuple[str, ...]) -> list[Passage]:
        matches = [p for p in self.passages if p.path[:len(path)] == path]
        if not matches:
            raise ValueError("this location has no prose")
        return matches


# Directories are divisions that contain further divisions. Files are passages
# attached to the heading that begins them. Numeric prefixes are display names,
# not claims about Hegel's own numbering; they keep `ls` in reading order.
# 1. Book index: the published TOC, followed by verified internal headings.
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

# Verified against this edition's headings, including their positions within
# the printed page. No classifier or inferred philosophical hierarchy is used.
SUBDIVISIONS = {
    59: (
        ("A", "Being", 59, 169.0),
        ("B", "Nothing", 59, 333.9),
        ("C", "Becoming", 59, 486.4),
    ),
    83: (
        ("A", "Existence as such", 83, 324.5),
        ("B", "Finitude", 90, 212.4),
        ("C", "Infinity", 108, 412.8),
    ),
    126: (
        ("A", "Being-for-itself as such", 126, 474.0),
        ("B", "The one and the many", 132, 411.7),
        ("C", "Repulsion and attraction", 138, 62.9),
    ),
    154: (
        ("A", "Pure quantity", 154, 181.5),
        ("B", "Continuous and discrete magnitude", 165, 438.6),
        ("C", "The limiting of quantity", 167, 249.8),
    ),
    168: (
        ("A", "Number", 168, 324.5),
        ("B", "Extensive and intensive quantum", 182, 125.2),
        ("C", "Quantitative infinity", 190, 100.3),
    ),
    271: (
        ("A", "The direct ratio", 272, 262.2),
        ("B", "The inverse ratio", 274, 62.9),
        ("C", "The ratio of powers", 278, 62.9),
    ),
    288: (
        ("A", "The specific quantum", 288, 336.9),
        ("B", "Specifying measure", 291, 355.6),
        ("C", "The being-for-itself in measure", 298, 275.7),
    ),
    302: (
        ("A", "The relation of independent measures", 303, 212.4),
        ("B", "Nodal lines of measure-relations", 318, 474.4),
        ("C", "The measureless", 323, 187.5),
    ),
    326: (
        ("A", "Absolute indifference", 326, 181.5),
        ("B", "Indifference as inverse ratio of its factors", 327, 63.1),
        ("C", "Transition into essence", 333, 486.4),
    ),
    341: (
        ("A", "The essential and the unessential", 341, 287.1),
        ("B", "Shine", 342, 312.0),
        ("C", "Reflection", 345, 411.7),
    ),
    354: (
        ("A", "Identity", 356, 274.7),
        ("B", "Difference", 361, 175.0),
        ("C", "Contradiction", 374, 224.8),
    ),
    386: (
        ("A", "Absolute ground", 389, 64.3),
        ("B", "Determinate ground", 397, 361.9),
        ("C", "Condition", 410, 62.9),
    ),
    420: (
        ("A", "The thing and its properties", 423, 137.6),
        ("B", "The constitution of the thing out of matters", 430, 361.9),
        ("C", "Dissolution of the thing", 432, 449.1),
    ),
    437: (
        ("A", "The law of appearance", 438, 449.1),
        ("B", "The world of appearance and the world-in-itself", 443, 150.1),
        ("C", "The dissolution of appearance", 447, 63.1),
    ),
    449: (
        ("A", "The relation of whole and parts", 450, 424.2),
        ("B", "The relation of force and its expression", 455, 187.5),
        ("C", "Relation of outer and inner", 460, 62.9),
    ),
    466: (
        ("A", "The exposition of the absolute", 466, 436.6),
        ("B", "The absolute attribute", 469, 199.9),
        ("C", "The mode of the absolute", 470, 312.0),
    ),
    477: (
        ("A", "Contingency or formal actuality, possibility, and necessity", 478, 371.6),
        ("B", "Relative necessity or real actuality, possibility, and necessity", 482, 62.9),
        ("C", "Absolute necessity", 485, 462.0),
    ),
    489: (
        ("A", "The relation of substantiality", 490, 125.2),
        ("B", "The relation of causality", 492, 436.7),
        ("C", "Reciprocity of action", 503, 150.1),
    ),
    529: (
        ("A", "The universal concept", 530, 175.0),
        ("B", "The particular concept", 534, 162.6),
        ("C", "The singular", 546, 187.5),
    ),
    550: (
        ("A", "The judgment of existence", 557, 187.5),
        ("B", "The judgment of reflection", 568, 411.7),
        ("C", "The judgment of necessity", 575, 175.0),
        ("D", "The judgment of the concept", 581, 462.2),
    ),
    588: (
        ("A", "The syllogism of existence", 590, 195.9),
        ("B", "The syllogism of reflection", 609, 62.7),
        ("C", "The syllogism of necessity", 617, 249.8),
    ),
    631: (
        ("A", "The mechanical object", 631, 499.1),
        ("B", "The mechanical process", 634, 177.5),
        ("C", "Absolute mechanism", 640, 499.4),
    ),
    645: (
        ("A", "The chemical object", 645, 260.1),
        ("B", "The process", 646, 361.9),
        ("C", "Transition of chemism", 649, 150.1),
    ),
    651: (
        ("A", "The subjective purpose", 657, 150.1),
        ("B", "The means", 659, 274.7),
        ("C", "The realized purpose", 662, 99.1),
    ),
    676: (
        ("A", "The living individual", 679, 224.9),
        ("B", "The life-process", 684, 62.9),
        ("C", "The genus", 686, 414.2),
    ),
    689: (
        ("A", "The idea of the true", 697, 175.0),
        ("B", "The idea of the good", 729, 187.5),
    ),
    735: (),  # No A/B/C subdivision in this final chapter.
}

# Requested verified next-level headings. Keys identify (chapter, major letter).
# Unlike small-cap A/B/C headings, the source displays these lower-case letters
# or Arabic numerals. Existence/B/c has a deeper Greek alpha/beta/gamma level;
# that further level is intentionally not included here.
SECOND_LEVEL = {
    (59, "C"): (
        ("1", "Unity of being and nothing", 59, 508.2),
        ("2", "The moments of becoming", 80, 259.1),
        ("3", "Sublation of becoming", 81, 147.0),
    ),
    (83, "A"): (
        ("a", "Existence in general", 83, 421.0),
        ("b", "Quality", 84, 495.8),
        ("c", "Something", 88, 297.0),
    ),
    (83, "B"): (
        ("a", "Something and an other", 90, 470.9),
        ("b", "Determination, constitution, and limit", 95, 256.4),
        ("c", "Finitude", 101, 105.7),
    ),
    (83, "C"): (
        ("a", "The infinite in general", 109, 259.1),
        ("b", "Alternating determination of finite and infinite", 110, 134.5),
        ("c", "Affirmative infinity", 114, 59.8),
    ),
    (126, "A"): (
        ("a", "Existence and being-for-itself", 127, 359.3),
        ("b", "Being-for-one", 128, 59.7),
        ("c", "The one", 132, 134.5),
    ),
    (126, "B"): (
        ("a", "The one within", 133, 171.9),
        ("b", "The one and the void", 133, 458.4),
        ("c", "Many ones", 135, 321.4),
    ),
    (126, "C"): (
        ("a", "Exclusion of the one", 138, 84.7),
        ("b", "The one one of attraction", 141, 59.8),
        ("c", "The connection of repulsion and attraction", 142, 97.2),
    ),
    (354, "B"): (
        ("1", "Absolute difference", 361, 196.8),
        ("2", "Diversity", 362, 321.4),
        ("3", "Opposition", 367, 433.5),
    ),
    (550, "A"): (
        ("a", "The positive judgment", 557, 446.0),
        ("b", "The negative judgment", 562, 59.9),
        ("c", "The infinite judgment", 567, 209.3),
    ),
    (550, "B"): (
        ("a", "The singular judgment", 570, 217.6),
        ("b", "The particular judgment", 570, 425.2),
        ("c", "The universal judgment", 572, 171.9),
    ),
    (550, "C"): (
        ("a", "The categorical judgment", 575, 358.8),
        ("b", "The hypothetical judgment", 576, 458.4),
        ("c", "The disjunctive judgment", 578, 122.1),
    ),
    (550, "D"): (
        ("a", "The assertoric judgment", 583, 159.4),
        ("b", "The problematic judgment", 584, 209.3),
        ("c", "The apodictic judgment", 585, 433.5),
    ),
    (689, "A"): (
        ("a", "Analytic cognition", 700, 134.5),
        ("b", "Synthetic cognition", 706, 411.3),
    ),
}

THIRD_LEVEL = {
    (689, "A", "b"): (
        ("1", "Definition", 708, 53.8),
        ("2", "Division", 713, 190.9),
        ("3", "The theorem", 718, 190.8),
    ),
}

ROOT = Node("", "The Science of Logic", 7, (BEING, ESSENCE, CONCEPT))


# 2. PDF layout: preserve positions until paragraphs and headings are resolved.
def extract_pages(pdf: Path) -> list[Page]:
    """Read word geometry with Poppler; no extra Python packages are required."""
    program = shutil.which("pdftotext")
    if not program:
        raise RuntimeError("Install Poppler first (on Ubuntu: sudo apt install poppler-utils).")
    try:
        result = subprocess.run(
            [program, "-f", str(FIRST_TEXT_PAGE), "-l", str(LAST_TEXT_PAGE),
             "-bbox-layout", str(pdf.resolve()), "-"],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "Could not extract the PDF.") from error
    # Poppler emits a handful of control characters from this PDF's fonts.
    xml = re.sub(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", result.stdout)
    try:
        document = ET.fromstring(xml)
    except ET.ParseError as error:
        raise RuntimeError("Poppler returned unreadable PDF layout data.") from error
    raw_pages = document.findall(".//p:page", XML_NS)
    if len(raw_pages) != LAST_TEXT_PAGE - FIRST_TEXT_PAGE + 1:
        raise RuntimeError("This reader requires the supplied 863-page Cambridge edition.")
    # A few pages contain more notes than prose. Learn the body font from the
    # whole document so those pages cannot mistake note type for main text.
    font_counts = Counter(
        round(float(word.attrib["yMax"]) - float(word.attrib["yMin"]), 1)
        for element in raw_pages for word in element.findall(".//p:word", XML_NS)
        if len(word.text or "") > 1
    )
    if not font_counts:
        raise RuntimeError("No searchable text found. Use the original text-based Cambridge PDF, not a scan.")
    body_height = font_counts.most_common(1)[0][0]
    pages = []
    for number, element in enumerate(raw_pages, FIRST_TEXT_PAGE):
        raw_lines = []
        for row in element.findall(".//p:line", XML_NS):
            words = tuple(
                Word(word.text or "", *(
                    float(word.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax")
                ))
                for word in row.findall("p:word", XML_NS)
            )
            if words:
                raw_lines.append(Line(words, number))
        height = float(element.attrib["height"])
        # Long prose lines identify the font and the margins independently of
        # the alternating left/right page layout.
        prose = [line for line in raw_lines if
                 len(line.words) >= 7 and height * .075 < line.y < height * .85]
        prose = [line for line in prose if abs(line.height - body_height) < body_height * .08]
        if not prose:
            prose = [line for line in raw_lines if
                     abs(line.height - body_height) < body_height * .08
                     and height * .075 < line.y < height * .85 and len(line.words) >= 3]
        if not prose:
            pages.append(Page(number, (), body_height, 0.0, 0.0))
            continue
        left = Counter(round(line.x, 1) for line in prose).most_common(1)[0][0]
        right = max(statistics.quantiles(
            [max(word.x1 for word in line.words) for line in prose], n=10
        )[7], left + 200) if len(prose) > 1 else max(word.x1 for word in prose[0].words)
        note_start = min((line.y for line in raw_lines if
                          body_height * .65 < line.height < body_height * .82
                          and left - 3 <= line.x <= left + body_height * 1.5
                          and line.y > height * .25
                          and (re.match(r"^\d{1,3}\b", line.text)
                               or len(re.findall(r"[A-Za-z]{2,}", line.text)) >= 3)),
                         default=height)
        lines = []
        for line in raw_lines:
            if not height * .075 < line.y < height * .855:
                continue  # Running title/page number or footer.
            if line.y >= note_start:
                continue  # All continuation lines of the footnote apparatus.
            # Small-caps headings are smaller than notes, but have recognizable
            # labels and are centered. Keep them for the verified heading index.
            small_heading = (
                line.height < body_height * .65
                and (line.x > left + body_height * 2
                     or re.match(r"^[a-d][.] ", line.text))
            )
            if line.height < body_height * .86 and not small_heading:
                continue  # Smaller type is the footnote apparatus.
            words = tuple(
                word for word in line.words
                if left - 3 <= word.x0 <= right + 3
                or line.height > body_height * 1.3
            )
            if not words:
                continue
            full_size = [word for word in words if word.height >= body_height * .86]
            baseline = statistics.median(word.y1 for word in (full_size or words))
            cleaned = []
            for word in words:
                # A raised number after prose is a note callout. Keep powers
                # following single-letter mathematical variables.
                is_callout = (
                    re.fullmatch(r"(?:[a-z]|\d{1,3})(?:[,–-](?:[a-z]|\d{1,3}))*", word.text) is not None
                    and word.y1 < baseline - body_height * .16
                    and (not cleaned or not re.fullmatch(r"[A-Za-z]", cleaned[-1].text))
                )
                if not is_callout:
                    cleaned.append(word)
            if cleaned:
                lines.append(Line(tuple(cleaned), number))
        lines.sort(key=lambda line: (round(line.y, 1), line.x))
        pages.append(Page(number, tuple(lines), body_height, left, right))
    return pages


# 3. Verified hierarchy: heading positions delimit logical divisions.
def heading_key(text: str) -> str:
    """Compare heading spelling despite small caps, ligatures, and spacing."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"^(?:chapter \d+|section [ivx]+):\s*", "", text)
    text = re.sub(r"^[a-zα-ω0-9]+[.)]\s*", "", text)
    text = re.sub(r"\s*\((?:book|volume).*", "", text)
    text = re.sub(r"^the\s+", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def find_anchor(pages: dict[int, Page], node: Node, expected_y: float | None = None) -> tuple[int, float]:
    """Verify a printed heading, including titles split over several lines."""
    page = pages[node.start_page + PRINTED_PAGE_OFFSET]
    target = heading_key(node.title)
    candidates = []
    for index, line in enumerate(page.lines):
        # A prose sentence containing the title is not the heading.
        if expected_y is not None and abs(line.y - expected_y) > 5:
            continue
        text = ""
        for following in page.lines[index:index + 3]:
            if following.y - line.y > page.body_height * 4:
                break
            text += " " + following.text
            if heading_key(text.strip()) == target:
                if expected_y is not None or (
                    line.x > page.left + page.body_height * 2
                    or line.height > page.body_height * 1.2
                ):
                    candidates.append(line.position)
    if not candidates:
        raise RuntimeError(
            f"Could not verify '{node.title}' on printed page {node.start_page}. "
            "Use the original Cambridge PDF; other editions are not supported."
        )
    return min(candidates)


def slug(title: str) -> str:
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", title).strip("-")


def indexed_tree(pages: list[Page]) -> tuple[Node, dict[tuple[int, float], Node]]:
    """Build a fresh tree and verify every indexed heading against the PDF."""
    root = deepcopy(ROOT)
    page_map = {page.number: page for page in pages}
    events = {}
    chapters = {}

    def attach(node: Node, parent: Node | None = None) -> None:
        node.parent = parent
        if node is not root and node is not root.children[0]:
            node.anchor = find_anchor(page_map, node)
            events[node.anchor] = node
        for child in node.children:
            if child.title.startswith("Chapter "):
                chapters[child.start_page] = child
            attach(child, node)

    attach(root)
    # Doctrine root headings have different wording from the descriptive TOC.
    # The leaf Foreword/Preface anchors already delimit text on their first page.
    for node in root.children:
        if node.anchor is None:
            node.anchor = (node.start_page + PRINTED_PAGE_OFFSET, 0.0)
    indexed = {}
    for chapter_page, headings in SUBDIVISIONS.items():
        chapter = chapters[chapter_page]
        for label, title, page, y in headings:
            node = Node(f"{label}-{slug(title)}.txt", title, page, label=label, parent=chapter)
            node.anchor = find_anchor(page_map, node, y)
            chapter.children += (node,)
            indexed[(chapter_page, label)] = node
            events[node.anchor] = node
    for table in (SECOND_LEVEL, THIRD_LEVEL):
        for key, headings in table.items():
            parent = indexed[key]
            for label, title, page, y in headings:
                node = Node(f"{label}-{slug(title)}.txt", title, page, label=label, parent=parent)
                node.anchor = find_anchor(page_map, node, y)
                parent.children += (node,)
                indexed[key + (label,)] = node
                events[node.anchor] = node
    return root, events


def is_heading(line: Line, page: Page) -> bool:
    """Recognize unindexed headings as prose boundaries, without guessing depth."""
    text = line.text
    if re.fullmatch(r"Remark(?: \d+)?", text):
        return True
    if line.height < page.body_height * .65:
        return True
    # Centered italic subsection titles have extra vertical spacing and labels.
    centered = abs((line.x + max(word.x1 for word in line.words)) / 2
                   - (page.left + page.right) / 2) < page.body_height * 1.5
    if line.height > page.body_height * 1.25:
        return centered and line.x > page.left + page.body_height * 2 and len(text) < 120
    return centered and line.x > page.left + page.body_height * 2 and bool(
        re.match(r"^(?:[a-zα-ω]|\d+)[.)]\s", text)
    )


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


def extract_passages(pdf: Path) -> list[Passage]:
    """Compatibility helper for experiments that previously imported this function."""
    return load_book(pdf).passages


def load_corpus_book(corpus: Path) -> Book:
    """Load the three-doctrine reader view without opening or parsing the PDF.

    The canonical corpus retains its richer edition/volume hierarchy. Its
    explicitly supplied reader_path metadata defines this convenient view;
    it is not reconstructed from heading spellings or assigned new IDs.
    """
    from sol_corpus_contract import CorpusError, load_index

    try:
        records = load_index(corpus, verify=True)
    except CorpusError as error:
        instruction = f"python3 sol_corpus_contract.py {shlex.quote(str(corpus))}"
        raise ValueError(
            f"Cannot use local corpus {corpus}: {error}\n"
            f"After correcting canonical Markdown if necessary, rebuild the index with:\n{instruction}"
        ) from error

    root = Node("", "The Science of Logic", 7)
    nodes: dict[tuple[str, ...], Node] = {(): root}
    children: dict[tuple[str, ...], list[Node]] = {(): []}
    node_orders: dict[tuple[str, ...], int] = {}
    for name, title, start in (
        ("BEING", "Doctrine of Being (Book One)", 7),
        ("ESSENCE", "Doctrine of Essence (Book Two)", 337),
        ("CONCEPT", "Doctrine of the Concept", 507),
    ):
        node = Node(name, title, start, parent=root)
        nodes[(name,)] = node
        children[()] += [node]
        children[(name,)] = []

    def reader_path(record: dict) -> tuple[str, ...]:
        value = record.get("reader_path")
        if not isinstance(value, str) or not value.startswith("/"):
            raise ValueError(f"Corpus record {record['id']} requires an absolute reader_path")
        parts = tuple(value[1:].split("/"))
        if not parts or parts[0] not in {"BEING", "ESSENCE", "CONCEPT"} or any(
            part in {"", ".", ".."} or "\\" in part for part in parts
        ):
            raise ValueError(f"Invalid corpus reader_path on {record['id']}: {value}")
        if any(part.endswith(".txt") for part in parts[:-1]):
            raise ValueError(f"Corpus reader_path descends through a virtual file: {value}")
        return parts

    def printed(source: dict, identifier: str) -> int:
        value = source["printed_page"]
        if not isinstance(value, str) or not re.fullmatch(r"\d+", value):
            raise ValueError(f"Main Hegel reader record {identifier} needs an Arabic printed-page label")
        return int(value)

    def ensure_node(path: tuple[str, ...], title: str, start: int, order: int, label: str = "") -> Node:
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Corpus reader title must be a nonempty string: /{'/'.join(path)}")
        for length in range(1, len(path) + 1):
            prefix = path[:length]
            node_orders[prefix] = min(node_orders.get(prefix, order), order)
            if prefix not in nodes:
                parent_path = prefix[:-1]
                name = prefix[-1]
                descriptive = name.removesuffix(".txt").replace("-", " ")
                node = Node(name, descriptive, start, parent=nodes[parent_path])
                nodes[prefix] = node
                children.setdefault(parent_path, []).append(node)
                children[prefix] = []
        node = nodes[path]
        node.title = title
        node.start_page = min(node.start_page, start)
        if label:
            node.label = label
        return node

    # Section metadata establishes titles, labels, and source order before leaf
    # passage files are attached. Editorial sections without reader_path belong
    # to the canonical corpus, not to this default Hegel-only convenience view.
    for record in records:
        if record["type"] == "section" and "reader_path" in record:
            path = reader_path(record)
            first = record["sources"][0]
            ensure_node(path, record.get("reader_title", record.get("title", record["plain_text"])),
                        printed(first, record["id"]), record["order"], record.get("label", ""))

    passages: list[Passage] = []
    for record in records:
        attribution = record["attribution"]
        if record["type"] not in {"paragraph", "list_item", "quotation", "formula"} or (
            attribution["author"] != "G. W. F. Hegel" or attribution["role"] != "main_text"
        ):
            continue
        path = reader_path(record)
        eligible = record.get("random_eligible", True)
        if not isinstance(eligible, bool):
            raise ValueError(f"Corpus random_eligible must be boolean: {record['id']}")
        if not path[-1].endswith(".txt"):
            raise ValueError(f"Main-text reader_path must identify a virtual .txt file: /{'/'.join(path)}")
        first, last = record["sources"][0], record["sources"][-1]
        title = record.get("reader_title", record.get("heading", path[-1].removesuffix(".txt")))
        node = ensure_node(path, title, printed(first, record["id"]), record["order"])
        # The first source paragraph determines the file's displayed start page.
        node.start_page = min(node.start_page, printed(first, record["id"]))
        passages.append(Passage(
            record["plain_text"], first["pdf_page"], printed(first, record["id"]),
            node, path, last["pdf_page"], printed(last, record["id"]),
            record["id"], record.get("heading", title), record["type"], eligible,
        ))

    for path, node in nodes.items():
        node.children = tuple(children[path])
        if node.children and node.name.endswith(".txt"):
            raise ValueError(f"Corpus maps both file and directory to /{'/'.join(path)}")
        # Put a directory's own introductory text before its subdivisions.
        node.children = tuple(sorted(node.children, key=lambda child: (
            child.name != "00-introduction.txt", node_orders.get(path + (child.name,), float("inf"))
        )))
    if not passages:
        raise ValueError("The local corpus contains no indexed Hegel main-text paragraphs for the reader")
    return Book(root, passages)


# 5. Navigation and display: no PDF extraction details belong in the shell.
def node_path(node: Node) -> tuple[str, ...]:
    parts = []
    while node.parent is not None:
        parts.append(node.name)
        node = node.parent
    return tuple(reversed(parts))


def display_path(path: tuple[str, ...]) -> str:
    return "/" + "/".join(path)


def sensible_width(requested: int | None) -> int:
    if requested is not None:
        if not 20 <= requested <= 240:
            raise ValueError("--width must be between 20 and 240.")
        return requested
    return max(20, min(88, shutil.get_terminal_size(fallback=(80, 24)).columns - 2))


def page_range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}–{end}"


def render_passage(passage: Passage, width: int) -> str:
    metadata = (
        f"Book pp. {page_range(passage.printed_page, passage.end_printed_page)} · "
        f"PDF pp. {page_range(passage.pdf_page, passage.end_pdf_page)} · "
        f"{passage.identifier}"
    )
    title = passage.heading or passage.node.title
    return "\n".join((
        textwrap.fill(display_path(passage.path), width=width, break_on_hyphens=False),
        textwrap.fill(title, width=width, break_on_hyphens=False),
        textwrap.fill(metadata, width=width),
        *(() if passage.random_eligible and passage.kind != "formula" else
          ("Math transcription needs source review; see the Markdown facsimile.",)),
        "─" * width,
        textwrap.fill(passage.text, width=width, break_long_words=True, break_on_hyphens=False),
    ))


def alias(name: str) -> str:
    name = name.removesuffix(".txt").casefold()
    return re.sub(r"^(?:\d+|[a-d]|[ivxlcdm]+|[αβγ])-", "", name)


def child_by_name(node: Node, name: str) -> Node | None:
    exact = [child for child in node.children if child.name == name]
    if exact:
        return exact[0]
    matches = [child for child in node.children if
               child.name.casefold().removesuffix(".txt") == name.casefold().removesuffix(".txt")
               or alias(child.name) == alias(name)]
    if len(matches) > 1:
        raise ValueError(f"ambiguous name: {name}; use its full listed name")
    return matches[0] if matches else None


def resolve_path(value: str | None, cwd: tuple[str, ...], root: Node = ROOT) -> tuple[Node, tuple[str, ...]]:
    node = root
    if not value or not value.startswith("/"):
        for piece in cwd:
            child = child_by_name(node, piece)
            if child is None:
                raise ValueError("the current path no longer exists")
            node = child
    for piece in (value or "").split("/"):
        if piece in ("", "."):
            continue
        if not node.is_directory:
            raise ValueError(f"not a directory: {node.name}")
        if piece == "..":
            node = node.parent or root
            continue
        child = child_by_name(node, piece)
        if child is None:
            raise ValueError(f"no such path: {value}")
        node = child
    return node, node_path(node)


def render_listing(node: Node) -> str:
    nodes = node.children if node.is_directory else (node,)
    return "\n".join(
        f"{child.name}{'/' if child.is_directory else ''}\n"
        f"    {child.label + '. ' if child.label else ''}{child.title} · p. {child.start_page}"
        for child in nodes
    )


def render_tree(node: Node = ROOT, prefix: str = "", include_self: bool = True) -> str:
    lines = []
    if include_self:
        lines.append(("/" if not node.name else node.name + ("/" if node.is_directory else ""))
                     + f"  {node.title}")
    for index, child in enumerate(node.children):
        last = index == len(node.children) - 1
        connector, extension = ("└── ", "    ") if last else ("├── ", "│   ")
        suffix = "/" if child.is_directory else ""
        lines.append(f"{prefix}{connector}{child.name}{suffix}  · p. {child.start_page}")
        if child.children:
            lines.extend(render_tree(child, prefix + extension, False).splitlines())
    return "\n".join(lines)


@dataclass
class ReadingSession:
    """A cursor within an explicit selection; random reads also set the cursor."""
    book: Book
    path: tuple[str, ...] = ()
    cursor: int | None = None

    def read(self, path: tuple[str, ...], first: bool = False) -> Passage:
        matches = self.book.selection(path)
        candidates = [index for index, p in enumerate(matches)
                      if p.kind != "formula" and p.random_eligible and len(re.findall(r"[A-Za-z]{2,}", p.text)) >= 8]
        if not first and not candidates:
            candidates = [index for index, p in enumerate(matches)
                          if p.kind != "formula" and p.random_eligible and len(re.findall(r"[A-Za-z]{2,}", p.text)) >= 3]
        if not first and not candidates:
            raise ValueError("this file has no suitable random prose paragraph; use cat")
        index = 0 if first else random.choice(candidates)
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


def install_completion(root: Node, get_cwd):
    """Optional standard-library tab completion; safe on systems without readline."""
    try:
        import readline
    except ImportError:
        return lambda: None
    old_completer = readline.get_completer()
    old_delimiters = readline.get_completer_delims()
    commands = ("ls", "cd", "pwd", "tree", "read", "first", "next", "previous", "cat", "help", "exit")
    def complete(text: str, state: int):
        try:
            buffer = readline.get_line_buffer()
            if " " not in buffer:
                choices = [command for command in commands if command.startswith(text)]
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


SHELL_HELP = """ls [PATH]      list files and divisions
cd [PATH]      navigate (.. goes up; / goes to root)
pwd            print the current path
tree [PATH]    show the nested outline
read [PATH]    read a random paragraph and set the reading cursor
first [PATH]   start reading the selection in book order
next           read the next paragraph in the same selection
previous       return to the previous paragraph
cat FILE       display the complete file in book order
help           show these commands
exit           leave SOL
Paths accept lowercase names without numeric prefixes; Tab completes full names."""


def run_shell(book: Book, width: int) -> int:
    cwd: tuple[str, ...] = ()
    session = ReadingSession(book)
    restore = install_completion(book.root, lambda: cwd)
    print("SOL — Soul Organizes Logic. Type 'help'; Tab completes paths.")
    try:
        while True:
            try:
                command = input(f"sol:{display_path(cwd)}$ ")
            except EOFError:
                print()
                return 0
            except KeyboardInterrupt:
                print("\nType 'exit' to leave.")
                continue
            try:
                parts = shlex.split(command)
                if not parts:
                    continue
                verb, arguments = parts[0], parts[1:]
                if len(arguments) > 1:
                    raise ValueError("expected at most one path")
                argument = arguments[0] if arguments else None
                if verb in {"exit", "quit"}:
                    return 0
                if verb == "help":
                    print(SHELL_HELP)
                elif verb == "pwd":
                    print(display_path(cwd))
                elif verb in {"next", "previous", "prev"}:
                    if argument:
                        raise ValueError(f"{verb} does not take a path")
                    print(render_passage(session.move(1 if verb == "next" else -1), width))
                elif verb == "cd":
                    node, path = resolve_path(argument or "/", cwd, book.root)
                    if not node.is_directory:
                        raise ValueError("not a directory")
                    cwd = path
                    session.path, session.cursor = cwd, None
                elif verb in {"ls", "tree", "read", "first", "cat"}:
                    node, path = resolve_path(argument, cwd, book.root)
                    if verb == "ls":
                        print(render_listing(node))
                    elif verb == "tree":
                        print(render_tree(node))
                    elif verb in {"read", "first"}:
                        print(render_passage(session.read(path, verb == "first"), width))
                    else:
                        if node.is_directory:
                            raise ValueError("cat takes a file; use first or read for a directory")
                        for passage in book.selection(path):
                            print(render_passage(passage, width), end="\n\n")
                else:
                    raise ValueError(f"unknown command: {verb}; type help")
            except ValueError as error:
                print(f"sol: {error}")
    finally:
        restore()


def default_pdf() -> Path:
    """Look in the working directory first, then preserve the user's sources layout."""
    direct = Path.cwd() / PDF_FILENAME
    local_source = Path.cwd() / "sources" / PDF_FILENAME
    return direct if direct.is_file() or not local_source.is_file() else local_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sol", description="Read and navigate Hegel's Science of Logic.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--structure", action="store_true", help="show the outline (prefer the indexed local corpus)")
    mode.add_argument("--shell", action="store_true", help="open the interactive reader")
    mode.add_argument("--read", metavar="PATH", help="read a random paragraph within a virtual path")
    mode.add_argument("--first", metavar="PATH", help="read the first paragraph within a virtual path")
    mode.add_argument("--cat", metavar="FILE", help="display a virtual file completely, in book order")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--corpus", type=Path, metavar="DIRECTORY",
                        help="canonical local corpus (default: ./local-corpus when corpus.json exists)")
    source.add_argument("--pdf", type=Path, metavar="PATH",
                        help=f"explicit PDF fallback (otherwise ./{PDF_FILENAME}, then ./sources/{PDF_FILENAME})")
    parser.add_argument("--width", type=int, metavar="COLUMNS", help="line width (20–240; default fits the terminal, up to 88)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pdf_explicit = args.pdf is not None
    corpus_explicit = args.corpus is not None
    corpus = (args.corpus or Path.cwd() / "local-corpus").expanduser()
    pdf = (args.pdf or default_pdf()).expanduser()
    try:
        width = sensible_width(args.width)
        if not pdf_explicit and (corpus_explicit or (corpus / "corpus.json").is_file()):
            book = load_corpus_book(corpus)
        else:
            if args.structure and not pdf.is_file():
                if pdf_explicit:
                    raise ValueError(f"PDF not found: {pdf}")
                print(render_tree())
                print("\nTop-level outline only. Supply a local corpus or the Cambridge PDF for subdivisions.")
                return 0
            if not pdf.is_file():
                raise ValueError(
                    f"No local corpus at {corpus}, and PDF not found: {pdf}\n"
                    f"Create the local corpus, put {PDF_FILENAME} in the current directory "
                    "or sources/, or use --corpus DIRECTORY / --pdf PATH."
                )
            book = load_book(pdf)
        if args.structure:
            print(render_tree(book.root))
        elif args.shell:
            return run_shell(book, width)
        elif args.cat is not None:
            node, path = resolve_path(args.cat, (), book.root)
            if node.is_directory:
                raise ValueError("--cat takes a virtual file")
            for passage in book.selection(path):
                print(render_passage(passage, width), end="\n\n")
        else:
            value = args.first if args.first is not None else args.read
            _, path = resolve_path(value, (), book.root)
            print(render_passage(ReadingSession(book).read(path, args.first is not None), width))
        return 0
    except ValueError as error:
        print(f"sol: {error}", file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(f"sol: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nsol: interrupted", file=sys.stderr)
        raise SystemExit(130)
    except BrokenPipeError:
        # Piping a long cat/tree output to head is normal terminal use.
        raise SystemExit(0)
