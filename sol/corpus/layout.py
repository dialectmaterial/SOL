"""Poppler geometry and heading verification for the supported edition.

This module is imported for conversion or explicit legacy PDF reading only.
Normal reading consumes the verified canonical index without loading it.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import unicodedata
import xml.etree.ElementTree as ET

from sol.corpus.edition import (
    FIRST_TEXT_PAGE, LAST_TEXT_PAGE, PRINTED_PAGE_OFFSET,
    ROOT, SUBDIVISIONS, SECOND_LEVEL, THIRD_LEVEL,
)
from sol.reader.models import Node

XML_NS = {"p": "http://www.w3.org/1999/xhtml"}


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
