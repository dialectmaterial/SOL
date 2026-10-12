#!/usr/bin/env python3
"""SOL: a terminal reader for the Cambridge *Science of Logic*.

Canonical local Markdown is indexed once and read through a verified JSONL
index using standard-library Python. Poppler remains available for explicit
legacy PDF reading. Corpus/PDF loading and the terminal interface stay separate.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from functools import cached_property
from importlib import metadata as package_metadata
import json
import os
import random
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import textwrap
import unicodedata
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
from pathlib import Path


# This index is specific to the Cambridge di Giovanni edition supplied with the
# project. Its printed page 7 is PDF page 80; page 827 begins the editor's
# appendix, so it is deliberately outside the readable corpus.
PDF_FILENAME = "Hegel-SOL.pdf"
FIRST_TEXT_PAGE = 80
LAST_TEXT_PAGE = 826
PRINTED_PAGE_OFFSET = 73
XML_NS = {"p": "http://www.w3.org/1999/xhtml"}
VERSION = "0.1.0"


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
    transcription_status: str = ""
    facsimile_labels: tuple[str, ...] = ()

    @property
    def needs_source_review(self) -> bool:
        """Transcription quality is independent of quotation eligibility/type."""
        return self.transcription_status in {"needs_review", "needs_visual_review"}


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
    redirects: dict[str, str] = field(default_factory=dict)
    canonical_records: dict[str, dict] = field(default_factory=dict, repr=False, compare=False)
    corpus_directory: Path | None = field(default=None, repr=False, compare=False)
    corpus_manifest: dict = field(default_factory=dict, repr=False, compare=False)
    corpus_snapshot: object | None = field(default=None, repr=False, compare=False)

    def selection(self, path: tuple[str, ...]) -> list[Passage]:
        matches = [p for p in self.passages if p.path[:len(path)] == path]
        if not matches:
            raise ValueError("this location has no prose")
        return matches

    def find_passage(self, identifier: str) -> Passage:
        """Resolve an exact ID, retired ID, or unambiguous prefix."""
        identifier = identifier.strip().casefold()
        if not identifier:
            raise ValueError("a passage identifier is required")
        by_id = {passage.identifier.casefold(): passage for passage in self.passages}
        redirects = {key.casefold(): value.casefold() for key, value in self.redirects.items()}
        candidates = [key for key in (*by_id, *redirects) if key.startswith(identifier)]
        if identifier in by_id or identifier in redirects:
            target = identifier
        elif len(candidates) == 1:
            target = candidates[0]
        elif len(candidates) > 1:
            raise ValueError("ambiguous identifier; use more of the passage ID")
        else:
            raise ValueError(f"no passage with identifier: {identifier}")
        seen: set[str] = set()
        while target in redirects:
            if target in seen:
                raise ValueError("invalid passage redirect cycle")
            seen.add(target)
            target = redirects[target]
        if target not in by_id:
            raise ValueError("this identifier does not refer to a readable Hegel passage")
        return by_id[target]

    def search(self, query: str, path: tuple[str, ...] = (),
               whole_word: bool = False, limit: int = 20) -> list[Passage]:
        """Literal Unicode search in a subtree, preserving book order."""
        if not query.strip():
            raise ValueError("search requires a nonempty query")
        if not 1 <= limit <= 1000:
            raise ValueError("search limit must be between 1 and 1000")
        pattern = re.escape(unicodedata.normalize("NFC", query.strip()).casefold())
        if whole_word:
            pattern = rf"(?<!\w){pattern}(?!\w)"
        expression = re.compile(pattern)
        return [passage for passage in self.selection(path)
                if expression.search(unicodedata.normalize("NFC", presentation_text(
                    passage.text, passage.facsimile_labels)).casefold())][:limit]


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
    from sol_corpus_contract import CorpusError, load_snapshot

    try:
        snapshot = load_snapshot(corpus)
        records = snapshot.records
    except CorpusError as error:
        if not (corpus / "corpus.json").is_file():
            raise ValueError(
                f"Cannot use local corpus {corpus}: corpus.json not found.\n"
                "Select its actual location with sol --set-corpus DIRECTORY or --corpus DIRECTORY.\n"
                "If SOL_CORPUS is set, update or unset that environment override."
            ) from error
        instruction = f"{shlex.quote(sys.executable)} -m sol_corpus_contract {shlex.quote(str(corpus))}"
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
            record.get("transcription_status", ""),
            tuple(re.findall(r"(?m)^!\[(Source facsimile, printed page [0-9ivxlcdm]+)\]"
                             r"\((?:\.\./)*assets/[^\s)]+\.png\)\s*$", record.get("markdown", ""))),
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
    redirects = {record["id"]: record["redirect_id"] for record in records
                 if record["type"] == "retired_record"}
    # Keep the complete verified record graph beside the convenient reader view.
    # Markdown, attribution, notes, source rectangles and retirement history must
    # not disappear merely because the terminal presents Hegel's prose as text.
    return Book(root, passages, redirects,
                {record["id"]: record for record in records}, snapshot.corpus_directory,
                snapshot.manifest, snapshot)


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


def presentation_text(text: str, facsimile_labels: tuple[str, ...] = ()) -> str:
    """Exclude generated facsimile captions from the terminal prose only."""
    for label in facsimile_labels:
        text = re.sub(r"(?m)^[ \t]*" + re.escape(label) + r"[ \t]*$", "", text)
    return text.strip()


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


def render_visual_help(book: Book | None = None, width: int = 80, depth: int = 2,
                       node: Node | None = None) -> str:
    """A portable ASCII manual using the actual loaded navigation tree."""
    title = r""" ___   ___   _
/ __| / _ \ | |
\__ \| (_) || |__
|___/ \___/ |____|

SOL: SOL Organizes Logic

PROJECT ROADMAP
SOL
 |
 +-- BEING    CLI, reader, virtual shell  [current work]
 +-- ESSENCE  applications, terminal emulator, classifiers
 `-- CONCEPT  operating system, NixOS, Hyprland

BOOK TREE"""
    outline = render_tree(node or (book.root if book is not None else ROOT),
                          depth=depth, ascii_only=True)
    notice = "" if book is not None else "\nAbbreviated fallback outline. Load a corpus for the full book structure.\n"
    guide = (
        "Directories contain divisions. Their own prose is 00-introduction.txt; "
        "leaf divisions are text files. An ellipsis marks deeper hidden divisions.\n\n"
        "READ: first [PATH], read [PATH], next, previous, cat FILE\n"
        "EXPLORE: ls [PATH], tree [PATH] --depth N, info [PATH]\n"
        "NAVIGATE: cd PATH, up, cd -, pwd\n"
        "RESEARCH: search QUERY [PATH] --word --limit N, open ID|RESULT, context N\n\n"
        "IDENTITY: neofetch (ASCII Hegel and the SOL concept preview)\n\n"
        "Example: cd /essence; search \"ground\" --word; open 1; context 2\n"
        "Type each example command separately inside sol --shell.\n"
        "CLI: sol --search \"ground\" --within /essence --word\n"
        "CLI: sol --passage ID --context 2; sol --info /being\n"
        "OUTPUT: --plain for passage text; --json for structured CLI results\n"
        "Type help for command syntax; exit to leave."
    )
    folded = "\n".join(textwrap.fill(line, width=width, break_on_hyphens=False)
                        if line else "" for line in guide.splitlines())
    return "\n".join((title, outline, notice, folded))


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


def install_completion(root: Node, get_cwd, workspace: bool = False):
    """Optional standard-library tab completion; safe on systems without readline."""
    try:
        import readline
    except ImportError:
        return lambda: None
    old_completer = readline.get_completer()
    old_delimiters = readline.get_completer_delims()
    commands = ("ls", "cd", "up", "pwd", "tree", "read", "first", "next", "previous",
                "cat", "search", "open", "context", "info", "where", "visual-help", "neofetch", "help", "exit")
    if workspace:
        commands += ("workspace", "resume", "bookmark", "note", "compare", "review", "relate")
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
visual-help [PATH] --depth N       ASCII guide and book tree (default depth 2)
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
        parser.add_argument("--depth", type=int, default=2 if verb == "visual-help" else None)
    return parser.parse_args(arguments)


def run_shell(book: Book, width: int, plain: bool = False, color: bool = False,
              workspace_reader=None, read_command=None, write_output=None) -> int:
    """Run the linear shell through replaceable, synchronous input/output seams.

    A future prompt adapter owns its completion and accepts one command at a time;
    workspace operations remain unchanged. No UI dependency is imported here.
    write_output follows print's calling convention, including end= for cat.
    """
    cwd: tuple[str, ...] = ()
    previous_cwd: tuple[str, ...] | None = None
    results: list[Passage] = []
    session = ReadingSession(book)
    emit = write_output if write_output is not None else print
    restore = lambda: None
    try:
        emit("SOL. Type 'visual-help' for the guide; 'help' for commands.")
        if workspace_reader is not None:
            emit(f"Workspace: {workspace_reader.store.path.stem}. Authored writes require --actor NAME.")
            if workspace_reader.store.get_state() is not None:
                try:
                    cwd, previous_cwd, passage, message = workspace_reader.restore(session)
                    if message:
                        emit(message)
                    emit(render_passage(passage, width, plain, color))
                except ValueError as error:
                    emit(f"sol: saved position not restored: {error}\n"
                         "The reference is retained. Inspect the workspace or deliberately start another reading.")
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
                    from sol_workspace_reader import safe_output
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
                if verb in {"search", "tree", "visual-help"}:
                    options = shell_options(verb, arguments)
                    node, path = resolve_path(options.path, cwd, book.root)
                    if verb == "search":
                        matches = book.search(options.query, path, options.word, options.limit)
                        results = matches
                        emit(render_search_results(matches, options.query, width, options.word))
                    elif verb == "tree":
                        emit(render_tree(node, depth=options.depth))
                    else:
                        emit(render_visual_help(book, width, options.depth, node))
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
                    if workspace_reader is not None:
                        from sol_workspace_reader import WORKSPACE_HELP
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
            except ValueError as error:
                if workspace_reader is not None:
                    from sol_workspace import WorkspaceError
                    if isinstance(error, WorkspaceError):
                        cwd, previous_cwd, session.path, session.cursor, workspace_reader.resumed_reference = before_command
                emit(f"sol: {error}")
    finally:
        restore()


def default_pdf() -> Path:
    """Look in the working directory first, then preserve the user's sources layout."""
    direct = Path.cwd() / PDF_FILENAME
    local_source = Path.cwd() / "sources" / PDF_FILENAME
    return direct if direct.is_file() or not local_source.is_file() else local_source


def config_path() -> Path:
    """Keep the corpus pointer outside the package, following the XDG layout."""
    configured = os.environ.get("XDG_CONFIG_HOME")
    directory = Path(configured).expanduser() if configured else Path.home() / ".config"
    if not directory.is_absolute():
        raise ValueError("XDG_CONFIG_HOME must be an absolute directory")
    return directory / "sol" / "config.json"


def configured_corpus() -> Path | None:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, UnicodeError) as error:
        raise ValueError(f"Cannot read SOL configuration {path}: {error}\n"
                         "Reset it with sol --set-corpus DIRECTORY.") from error
    value = data.get("corpus") if isinstance(data, dict) else None
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise ValueError(f"Invalid SOL configuration {path}: corpus must be an absolute path.\n"
                         "Reset it with sol --set-corpus DIRECTORY.")
    return Path(value)


def installed_project_directory() -> Path | None:
    """Recover a local pip/pipx checkout, without putting its corpus in a wheel.

    PEP 610 records a local-directory install's file URL in direct_url.json.
    Archive and remote Git installations do not identify a persistent checkout.
    """
    try:
        origin = package_metadata.distribution("sol-organizes-logic").read_text("direct_url.json")
        if not origin:
            return None
        data = json.loads(origin)
        if not isinstance(data, dict) or not isinstance(data.get("dir_info"), dict):
            return None
        if "archive_info" in data or "vcs_info" in data:
            return None
        url = data.get("url")
        if not isinstance(url, str):
            return None
        parsed = urlsplit(url)
        if (parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}
                or parsed.query or parsed.fragment):
            return None
        decoded = unquote(parsed.path, errors="strict")
        if os.name == "nt" and re.match(r"^/[A-Za-z]:/", decoded):
            decoded = decoded[1:]
        directory = Path(decoded)
        if not directory.is_absolute():
            return None
        subdirectory = data.get("subdirectory", "")
        if not isinstance(subdirectory, str):
            return None
        relative = Path(subdirectory)
        if relative.is_absolute() or ".." in relative.parts:
            return None
        return directory / relative
    except (package_metadata.PackageNotFoundError, OSError, ValueError, TypeError):
        return None


def discover_corpus(explicit: Path | None = None) -> Path | None:
    """Select a canonical corpus independently of the shell's working directory.

    An explicitly selected or saved location must never silently change sources
    when broken. Auto-discovered locations are used only when a manifest exists.
    """
    if explicit is not None:
        return explicit.expanduser()
    environment = os.environ.get("SOL_CORPUS")
    if environment:
        return Path(environment).expanduser()
    local = Path.cwd() / "local-corpus"
    if (local / "corpus.json").is_file():
        return local
    saved = configured_corpus()
    if saved is not None:
        return saved
    project = installed_project_directory()
    candidates = ([project / "local-corpus"] if project is not None else [])
    candidates.append(Path(__file__).resolve().parent / "local-corpus")
    return next((candidate for candidate in candidates if (candidate / "corpus.json").is_file()), None)


def save_corpus(directory: Path) -> tuple[Path, Path]:
    """Validate first, then atomically save a portable absolute corpus pointer."""
    corpus = directory.expanduser().resolve()
    load_corpus_book(corpus)
    path = config_path()
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".config-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"version": 1, "corpus": str(corpus)}, stream, indent=2)
            stream.write("\n")
        temporary.replace(path)
    except OSError as error:
        raise ValueError(f"Cannot save SOL configuration {path}: {error}") from error
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return corpus, path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sol", description="Read and navigate Hegel's Science of Logic.")
    parser.add_argument("command", nargs="?", choices=("visual-help",), help="open the ASCII manual")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--structure", action="store_true", help="show the outline (prefer the indexed local corpus)")
    mode.add_argument("--visual-help", action="store_true", help="ASCII manual, roadmap, and book tree")
    mode.add_argument("--shell", action="store_true", help="open the interactive reader")
    mode.add_argument("--read", metavar="PATH", help="read a random paragraph within a virtual path")
    mode.add_argument("--first", metavar="PATH", help="read the first paragraph within a virtual path")
    mode.add_argument("--cat", metavar="FILE", help="display a virtual file completely, in book order")
    mode.add_argument("--search", metavar="QUERY", help="literal case-insensitive passage search")
    mode.add_argument("--passage", metavar="ID", help="open a passage by exact ID or unique prefix")
    mode.add_argument("--info", metavar="PATH", help="show location, source range, and passage counts")
    mode.add_argument("--set-corpus", type=Path, metavar="DIRECTORY",
                      help="validate and remember the default corpus for reading from any directory")
    mode.add_argument("--resume", action="store_true", help="resume the named workspace's saved passage")
    mode.add_argument("--workspace-export", action="store_true", help="export the named workspace as JSON")
    mode.add_argument("--workspace-check", action="store_true", help="report unresolved, retired and versioned workspace references")
    mode.add_argument("--workspace-backup", type=Path, metavar="FILE", help="create a new, verified .sqlite3 backup without overwriting")
    mode.add_argument("--review-queue", action="store_true", help="show canonical pending transcriptions; optionally include workspace testimony")
    parser.add_argument("--workspace", metavar="NAME", help="opt into a persistent, named reading workspace")
    parser.add_argument("--workspace-dir", type=Path, metavar="DIRECTORY", help="directory for local workspace databases")
    parser.add_argument("--actor", metavar="NAME", help="explicit author for workspace notes and assertions")
    parser.add_argument("--resume-revision", type=int, metavar="N", help="with --resume, restore a historical checkpoint as a new visit")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--corpus", type=Path, metavar="DIRECTORY",
                        help="canonical corpus for this run (otherwise discover a local or saved corpus)")
    source.add_argument("--pdf", type=Path, metavar="PATH",
                        help="explicit legacy PDF reading (slow; not used for ordinary reading)")
    parser.add_argument("--width", type=int, metavar="COLUMNS", help="line width (20–240; default fits the terminal, up to 88)")
    parser.add_argument("--within", metavar="PATH", help="restrict --search to this subtree")
    parser.add_argument("--word", action="store_true", help="whole-word --search rather than substring")
    parser.add_argument("--limit", type=int, metavar="N", help="maximum search results (1–1000; default 20)")
    parser.add_argument("--context", type=int, metavar="N", help="neighbors around --passage (0–10 on each side)")
    parser.add_argument("--depth", type=int, metavar="N", help="outline depth (0–32; visual-help default 2)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--plain", action="store_true", help="passage text without metadata or ANSI styling")
    output.add_argument("--json", action="store_true", help="structured output for scripts")
    return parser


def validate_options(args: argparse.Namespace) -> None:
    if args.command:
        actions = (args.structure, args.visual_help, args.shell, args.read is not None,
                   args.first is not None, args.cat is not None, args.search is not None,
                   args.passage is not None, args.info is not None, args.set_corpus is not None,
                   args.resume, args.workspace_export, args.workspace_check, args.workspace_backup is not None,
                   args.review_queue)
        if any(actions):
            raise ValueError("visual-help cannot be combined with another action")
        args.visual_help = True
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
        if not args.structure and not args.visual_help:
            raise ValueError("--depth requires --structure or visual-help")
        if not 0 <= args.depth <= 32:
            raise ValueError("--depth must be between 0 and 32")
    if args.json and (args.shell or args.visual_help):
        raise ValueError("--json is available for reading, search, info, and structure")
    if args.set_corpus is not None and (args.corpus is not None or args.pdf is not None):
        raise ValueError("--set-corpus cannot be combined with --corpus or --pdf")
    if args.workspace is None and (args.workspace_dir is not None or args.actor is not None or args.resume
                                   or args.workspace_export or args.workspace_check or args.workspace_backup is not None):
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
        if args.pdf is not None or args.set_corpus is not None or args.visual_help or args.structure:
            raise ValueError("--workspace requires the indexed corpus and cannot accompany --pdf, --set-corpus, or an outline action")
        if args.search is not None or args.info is not None or args.cat is not None:
            raise ValueError("--workspace is available for reading, --shell, --resume, and --workspace-export")
        if args.context is not None:
            raise ValueError("workspace reading does not yet save a context view; use --passage ID --context N without --workspace")
    if args.workspace_export and args.plain:
        raise ValueError("--workspace-export always emits JSON; omit --plain")


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
    """Opt-in durable state; ordinary invocations do not open a database."""
    from sol_workspace import Workspace
    from sol_workspace_reader import WorkspaceReader, workspace_path

    identity = book.corpus_manifest.get("corpus_id")
    if not identity:
        directory = shlex.quote(str(book.corpus_directory))
        raise ValueError("this corpus needs an explicit permanent identity before workspace use.\n"
                         f"Run once: sol-corpus-check {directory} --initialize-identity\n"
                         "This preserves canonical text and passage IDs; do not reconvert the PDF.")
    location = workspace_path(args.workspace, args.workspace_dir)
    if (args.resume or args.workspace_export or args.workspace_check or args.workspace_backup is not None
            or args.review_queue) and not location.exists():
        raise ValueError(f"workspace does not exist: {args.workspace}; start with --workspace NAME --shell")
    provenance = {"edition": book.corpus_manifest["edition"], "source": book.corpus_manifest["source"]}
    with Workspace(location, identity, provenance, actor=args.actor or "Reader") as store:
        reader = WorkspaceReader(book, store, args.actor, resolve_path, display_path,
                                 render_passage, width, args.plain, color)
        if args.workspace_export:
            emit_json(store.export())
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
        if args.shell:
            return run_shell(book, width, args.plain, color, reader)
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
        if args.visual_help and args.corpus is None and args.pdf is None:
            # The guide must still explain setup when an automatic source is broken.
            try:
                corpus = discover_corpus()
                book = load_corpus_book(corpus) if corpus is not None else None
            except ValueError as error:
                print(f"sol: {error}\nShowing the abbreviated visual guide.", file=sys.stderr)
                book = None
            print(render_visual_help(book, width, 2 if args.depth is None else args.depth))
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
            if args.visual_help:
                print(render_visual_help(width=width, depth=2 if args.depth is None else args.depth))
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
        if args.workspace is not None:
            return run_workspace_cli(book, args, width, color)
        if args.review_queue:
            if not book.canonical_records:
                raise ValueError("--review-queue requires the canonical Markdown corpus, not the legacy PDF reader")
            from sol_workspace_diagnostics import review_queue
            from sol_workspace_reader import render_review_queue
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
        elif args.visual_help:
            print(render_visual_help(book, width, 2 if args.depth is None else args.depth))
        elif args.shell:
            return run_shell(book, width, args.plain, color)
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
