"""Geometry-based segmentation of the edition's bibliography and subject index.

``segment_references(pages, kind)`` accepts page dictionaries with ``number``
and ``body_spans`` (or ``spans``). Each span supplies x/y/width/height, size,
family, text and a distinct source_id. The caller removes running furniture.
The result has ``entries`` and ``warnings``. Entries have type, title, section,
start_page, end_page, spans, source_ids, lines, and folded text. Every incoming
span belongs to exactly one entry. Coordinates use pdftohtml's zoom=1 points.

Bibliography entries follow their hanging indents, including works whose
author is understood from the preceding entry. Index entries follow each
column from top to bottom, then continue across columns/pages. Repeated
``(cont.)`` headings remain in the source lines and belong to the same entry.
No permanent corpus IDs or attribution judgments are allocated here.
"""

from __future__ import annotations

from collections import Counter
import re
import unicodedata


_CONTINUED = re.compile(r"\s*\(cont\.?\)\s*$", re.IGNORECASE)
_BIBLIOGRAPHY_HEADINGS = {
    "BIBLIOGRAPHY",
    "SOURCES CITED BY HEGEL",
    "WORKS OF HEGEL CITED",
    "WORKS CITED BY THE EDITOR AND SELECTED READINGS",
}
_ACCENTS = {"¨": "\u0308", "´": "\u0301", "`": "\u0300",
            "ˆ": "\u0302", "˜": "\u0303", "˚": "\u030a", "ˇ": "\u030c"}


def _text(span: dict) -> str:
    return unicodedata.normalize("NFC", span.get("text", ""))


def _join_spans(spans: list[dict]) -> str:
    """Use printed gaps, so separately encoded old-style digits stay intact."""
    parts: list[str] = []
    previous = None
    accents = [span for span in spans if _text(span).strip() in _ACCENTS]
    for span in sorted(spans, key=lambda item: float(item["x"])):
        text = _text(span)
        if text.strip() in _ACCENTS:
            continue
        for accent in accents:
            # The two separated marks observed in this edition overprint the
            # initial capital of a word rather than occupy a text position.
            if text and 0 <= float(accent["x"]) - float(span["x"]) <= float(span.get("size", 10)):
                text = unicodedata.normalize("NFC", text[0] + _ACCENTS[_text(accent).strip()] + text[1:])
        if previous is not None and text:
            gap = float(span["x"]) - float(previous["x"]) - float(previous["width"])
            threshold = max(0.6, min(float(span.get("size", 10)),
                                     float(previous.get("size", 10))) * 0.12)
            if gap > threshold and parts and not parts[-1].endswith(" ") and not text.startswith(" "):
                parts.append(" ")
        parts.append(text)
        previous = span
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _lines(spans: list[dict], page: int, column: int = 0) -> list[dict]:
    """Group by glyph bottoms: old-style digits start higher than the prose."""
    groups: list[tuple[float, list[dict]]] = []
    accents = [span for span in spans if _text(span).strip() in _ACCENTS]
    ordered = sorted([span for span in spans if _text(span).strip() not in _ACCENTS],
                     key=lambda span: (float(span["y"]) + float(span["height"]),
                                             float(span["x"])))
    for span in ordered:
        bottom = float(span["y"]) + float(span["height"])
        if groups and abs(groups[-1][0] - bottom) <= 1.6:
            groups[-1][1].append(span)
        else:
            groups.append((bottom, [span]))
    for accent in accents:
        bottom = float(accent["y"]) + float(accent["height"])
        candidates = [(abs(anchor - bottom), values) for anchor, values in groups
                      if abs(anchor - bottom) <= 5 and any(
                          float(span["x"]) <= float(accent["x"]) <= float(span["x"]) + float(span["width"])
                          for span in values)]
        if candidates:
            min(candidates, key=lambda item: item[0])[1].append(accent)
        else:
            groups.append((bottom, [accent]))
    groups.sort(key=lambda item: item[0])
    output = []
    for _, values in groups:
        values.sort(key=lambda span: float(span["x"]))
        output.append({
            "pdf_page": page, "column": column,
            "x": min(float(span["x"]) for span in values),
            "y": min(float(span["y"]) for span in values),
            "spans": values, "text": _join_spans(values),
        })
    return output


def _header(line: dict, kind: str) -> bool:
    text = line["text"].upper()
    return text in (_BIBLIOGRAPHY_HEADINGS if kind == "bibliography" else {"INDEX"})


def _title(text: str, kind: str) -> str:
    text = _CONTINUED.sub("", text).strip()
    if kind == "index":
        if ":" in text:
            return text.split(":", 1)[0].strip()
        boundary = re.search(r",\s*(?=\d|[ivxlcdm]+\b|see(?:\s|$))", text,
                             flags=re.IGNORECASE)
        return text[:boundary.start()].strip() if boundary else text
    # A title is a convenient preview; the complete entry remains authoritative.
    return text[:120].rstrip() + ("…" if len(text) > 120 else "")


def _new_entry(kind: str, line: dict, section: str | None, *, orphan: bool = False) -> dict:
    return {
        "type": f"{kind}_entry", "title": _title(line["text"], kind),
        "section": section, "start_page": line["pdf_page"],
        "end_page": line["pdf_page"], "spans": [], "source_ids": [],
        "lines": [], "text": "", "orphan": orphan,
    }


def _append(entry: dict, line: dict) -> None:
    entry["lines"].append(line)
    entry["spans"].extend(line["spans"])
    entry["source_ids"].extend(span["source_id"] for span in line["spans"])
    entry["end_page"] = line["pdf_page"]


def _bib_start_limit(lines: list[dict]) -> float:
    """Start indents are 0 or +10pt; hanging continuation is +20pt.

    Some pages have only same-author works (+10) and their continuations (+20).
    Infer their rightmost common first-line indent instead of assuming the
    leftmost indent always means a newly printed author's name.
    """
    if not lines:
        return 0
    left = min(line["x"] for line in lines)
    near = [line["x"] for line in lines if line["x"] <= left + 25]
    buckets = Counter(round(value * 2) / 2 for value in near)
    hanging = max(buckets)
    if hanging - left < 4.5:
        return left + 2.5  # Entirely single-line entries.
    return hanging - 4.5


def _ordered_index_lines(spans: list[dict], number: int) -> list[dict]:
    if not spans:
        return []
    # The inner content margins, rather than the page centre, define the gutter;
    # recto/verso pages shift both columns by about 12.6pt in this edition.
    left = min(float(span["x"]) for span in spans)
    right = max(float(span["x"]) + float(span["width"]) for span in spans)
    gutter = (left + right) / 2
    left_spans = [span for span in spans if float(span["x"]) < gutter]
    right_spans = [span for span in spans if float(span["x"]) >= gutter]
    # A very short synthetic or single-column page must not split one text row
    # just because its word spans surround its content midpoint.
    if right_spans and min(float(span["x"]) for span in right_spans) - left < 70:
        return _lines(spans, number)
    return _lines(left_spans, number, 0) + _lines(right_spans, number, 1)


def segment_references(pages: list[dict], kind: str) -> dict:
    """Segment a reference section; reject duplicate/lost source-span IDs."""
    if kind not in {"bibliography", "index"}:
        raise ValueError("kind must be 'bibliography' or 'index'")
    entries: list[dict] = []
    warnings: list[dict] = []
    input_ids: list[str] = []
    active = None
    section = None

    for page in sorted(pages, key=lambda value: int(value["number"])):
        number = int(page["number"])
        spans = page.get("body_spans", page.get("spans", []))
        input_ids.extend(span["source_id"] for span in spans)
        full_lines = _lines(spans, number)
        headers = [line for line in full_lines if _header(line, kind)]
        if kind == "index":
            header_ids = {span["source_id"] for line in headers for span in line["spans"]}
            lines = _ordered_index_lines([span for span in spans
                                          if span["source_id"] not in header_ids], number)
            # The opening Index title precedes both columns, never interrupts one.
            lines = headers + lines
        else:
            lines = full_lines
        content_lines = [line for line in lines if not _header(line, kind)]
        start_limit = _bib_start_limit(content_lines) if kind == "bibliography" else None
        lefts = {column: min(line["x"] for line in content_lines if line["column"] == column)
                 for column in {line["column"] for line in content_lines}}

        for line in lines:
            if _header(line, kind):
                heading = _new_entry(kind, line, section)
                heading["type"] = "section"
                heading["title"] = line["text"]
                _append(heading, line)
                entries.append(heading)
                if line["text"].upper() not in {"BIBLIOGRAPHY", "INDEX"}:
                    section = line["text"]
                    active = None
                continue
            continued = bool(_CONTINUED.search(line["text"]))
            is_start = (line["x"] <= start_limit if kind == "bibliography"
                        else line["x"] <= lefts[line["column"]] + 2.5)
            if continued:
                title = _title(line["text"], kind)
                if active is None or active["title"].casefold() != title.casefold():
                    active = _new_entry(kind, line, section, orphan=True)
                    entries.append(active)
                    warnings.append({"code": "unmatched_index_continuation", "pdf_page": number,
                                     "title": title, "source_ids": [s["source_id"] for s in line["spans"]]})
            elif is_start or active is None:
                orphan = not is_start
                active = _new_entry(kind, line, section, orphan=orphan)
                entries.append(active)
                if orphan:
                    warnings.append({"code": "orphan_reference_continuation", "pdf_page": number,
                                     "source_ids": [s["source_id"] for s in line["spans"]]})
            _append(active, line)

    counts = Counter(input_ids)
    if any(count != 1 for count in counts.values()):
        raise ValueError("Reference source_id values must be distinct")
    output_ids = [source_id for entry in entries for source_id in entry["source_ids"]]
    if Counter(output_ids) != counts:
        raise ValueError("Reference segmentation lost or duplicated source spans")
    for entry in entries:
        # Keep repeated continuation headings visible, with a paragraph boundary.
        entry["text"] = " ".join(line["text"] for line in entry["lines"]).strip()
    return {"entries": entries, "warnings": warnings}
