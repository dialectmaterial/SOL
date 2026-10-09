"""Verified structural importer for the supplied Cambridge di Giovanni edition.

This is deliberately not a generic PDF heading detector. The initial audit
examined all 747 main-text pages using independent font and word-position
extraction and checked the Greek labels against rendered source pages. Runtime
imports recheck the known anchors and expected heading counts. Nothing here
loads a generated manuscript or depends on a developer's temporary files.

``audit_id`` values only reconcile this import's headings. They are NOT the
permanent identifiers assigned by the canonical Markdown corpus contract.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any


EXPECTED_COUNTS = {
    "volume": 2,
    "prefatory_or_introductory_text": 9,
    "introduction_subdivision": 2,
    "book": 2,
    "section": 9,
    "chapter": 27,
    "major_subdivision": 78,
    "subdivision": 90,
    "unnumbered_subdivision": 2,
    "remark": 52,
    "greek_subdivision": 3,
    "doctrine": 1,
}

# Poppler renders these Greek labels as Latin a/b/g. Each correction was
# visually verified on the corresponding source page, not inferred from order.
GREEK_HEADINGS = {
    (174, 375.7): ("α", "The immediacy of finitude"),
    (176, 209.3): ("β", "Restriction and the ought"),
    (181, 97.7): ("γ", "Transition of the finite into the infinite"),
}

REMARK_SUBTITLES = {
    (277, 153.3): "The conceptual determination of the mathematical infinite",
    (307, 502.3): "The purpose of differential calculus deduced from its application",
    (333, 92.3): "Further forms associated with the qualitative determinateness of magnitude",
}

# These left-aligned, unlabeled italic headings were visually confirmed after
# expanding the independent audit beyond centered/labeled italic candidates.
# Explicit anchors prevent ordinary italic quotations becoming subdivisions.
UNNUMBERED_HEADINGS = {
    (193, 178.4): "Transition",
    (208, 340.3): "Repulsion",
}


def _near(mapping: dict, page: int, y: float, tolerance: float = 4) -> Any:
    return next((value for (p, z), value in mapping.items()
                 if p == page and abs(z - y) < tolerance), None)


def _line_record(line: Any) -> dict:
    return {
        "text": line.text,
        "y": round(line.y, 3),
        "x": round(line.x, 3),
        "end_y": round(max(word.y1 for word in line.words), 3),
        "end_x": round(max(word.x1 for word in line.words), 3),
    }


def _attach_source_span(row: dict, page: Any, index: int, reader: Any) -> None:
    """Include caption and wrapped title lines in one consumable source span.

    ``y`` remains the title's anchor. ``start_y`` can precede it because a
    'Chapter 2' or 'Section II' caption is part of the same heading. Importers
    must consume start_y..end_y, not merely the title's first line.
    """
    line = page.lines[index]
    source_lines = [line]
    if row["kind"] in ("chapter", "section", "book") and index:
        previous = page.lines[index - 1]
        compact = re.sub(r"\s+", "", previous.text).casefold()
        if (previous.height < page.body_height * .65
                and compact.startswith(("chapter", "section", "book"))):
            row["caption_text"] = previous.text
            row["caption_y"] = round(previous.y, 3)
            source_lines.insert(0, previous)

    title_lines = [line]
    target = reader.heading_key(row["title"])
    for extra in page.lines[index + 1:index + 3]:
        assembled = " ".join(item.text for item in title_lines)
        if (reader.heading_key(assembled) == target
                or extra.y - line.y > page.body_height * 4):
            break
        if extra.height < page.body_height * .65 or row["kind"] == "doctrine":
            title_lines.append(extra)
            source_lines.append(extra)
        else:
            break

    if row["kind"] == "remark":
        subtitle = _near(REMARK_SUBTITLES, page.number, line.y)
        if subtitle:
            if index + 1 >= len(page.lines):
                raise RuntimeError("A verified Remark subtitle is missing from this PDF.")
            following = page.lines[index + 1]
            if reader.heading_key(following.text) != reader.heading_key(subtitle):
                raise RuntimeError(f"Could not verify Remark subtitle: {subtitle}")
            row["subtitle"] = subtitle
            row["subtitle_y"] = round(following.y, 3)
            source_lines.append(following)
            row["evidence"].append("standalone italic Remark subtitle, independently audited")

    row["source_lines"] = [_line_record(item) for item in source_lines]
    row["start_y"] = min(item["y"] for item in row["source_lines"])
    row["end_y"] = max(item["end_y"] for item in row["source_lines"])


def _assign_parents(rows: list[dict]) -> None:
    """Assign the physical hierarchy, not the old CLI's convenience paths."""
    stack = {0: "book-root"}
    active = None
    for order, row in enumerate(rows, 1):
        row["audit_id"] = f"audit-h{order:04d}"
        row["order"] = order
        kind = row["kind"]
        if kind == "volume":
            depth = 1
        elif kind in ("doctrine", "book"):
            depth = 2
        elif kind == "prefatory_or_introductory_text":
            depth = 2 if row["pdf_page"] < 118 else 3
        elif kind in ("section", "introduction_subdivision"):
            depth = 3
        elif kind == "chapter":
            depth = 4
        elif kind == "major_subdivision":
            depth = 5
        elif kind == "subdivision":
            # Definition/Division/The theorem are inside Synthetic cognition.
            depth = 7 if 781 <= row["pdf_page"] <= 791 else 6
        elif kind in ("greek_subdivision", "unnumbered_subdivision"):
            depth = 7
        elif kind == "remark":
            if active is None:
                raise RuntimeError("A Remark has no source parent heading.")
            depth = active["depth"] + 1
        else:
            raise RuntimeError(f"Unsupported hierarchy kind: {kind}")
        row["depth"] = depth
        if kind == "remark":
            row["parent_audit_id"] = active["audit_id"]
        else:
            if depth - 1 not in stack:
                raise RuntimeError(f"Missing parent for verified heading: {row['title']}")
            row["parent_audit_id"] = stack[depth - 1]
            stack = {d: value for d, value in stack.items() if d < depth}
            stack[depth] = row["audit_id"]
            active = row


def _volume(page: Any, label: str, title: str, positions: tuple[float, ...]) -> dict:
    lines = []
    for y in positions:
        matching = [line for line in page.lines if abs(line.y - y) < 2]
        if len(matching) != 1:
            raise RuntimeError(f"Could not verify Volume {label} title-page display.")
        lines.append(matching[0])
    source_lines = [_line_record(line) for line in lines]
    return {
        "pdf_page": page.number,
        "printed_page": page.number - 73,
        "y": source_lines[0]["y"],
        "start_y": source_lines[0]["y"],
        "end_y": max(line["end_y"] for line in source_lines),
        "x": min(line["x"] for line in source_lines),
        "title": title,
        "label": label,
        "kind": "volume",
        "source_text": " ".join(line["text"] for line in source_lines),
        "source_lines": source_lines,
        "confidence": "high",
        "evidence": ["source title-page display, verified Poppler geometry"],
    }


def build_hierarchy(pdf_path: str | Path) -> dict:
    """Return the complete verified main-text hierarchy for this one edition.

    This reads the PDF only during conversion. The corpus and reader subsequently
    use canonical Markdown and generated indexes. Unsupported editions fail
    verification rather than silently receiving this edition's structure.
    """
    import sol as reader

    pages = reader.extract_pages(Path(pdf_path).expanduser())
    page_map = {page.number: page for page in pages}
    root, _events = reader.indexed_tree(pages)
    known = {}

    def walk(node: Any) -> None:
        for child in node.children:
            if child.parent is root:
                kind = "doctrine" if child.name == "CONCEPT" else "book"
            elif child.title.startswith("Section "):
                kind = "section"
            elif child.title.startswith("Chapter "):
                kind = "chapter"
            elif child.label and child.label in "ABCD":
                kind = "major_subdivision"
            elif child.label:
                kind = "subdivision"
            else:
                kind = "prefatory_or_introductory_text"
            known[child.anchor] = (child, kind)
            walk(child)

    walk(root)
    # The reader formerly filed shared prefaces under BEING. Its first synthetic
    # anchor is not the canonical start of Book One, which is printed page 45.
    known.pop(root.children[0].anchor)
    known[(118, 75.713)] = (root.children[0], "book")
    known.pop(root.children[2].anchor)
    known[(580, 76.244)] = (root.children[2], "doctrine")
    rows = []
    consumed = set()
    for page in pages:
        for index, line in enumerate(page.lines):
            match = _near(known, page.number, line.y)
            if match:
                node, kind = match
                anchor = next(key for key, value in known.items() if value == match)
                if anchor in consumed:
                    continue
                consumed.add(anchor)
                title, label = node.title, node.label
                if kind in ("doctrine", "book"):
                    title = {"BEING": "The Doctrine of Being",
                             "ESSENCE": "The Doctrine of Essence",
                             "CONCEPT": "The Science of Subjective Logic or The Doctrine of the Concept"}[node.name]
                if kind in ("section", "chapter"):
                    parsed = re.fullmatch(r"(?:Section|Chapter)\s+([^:]+):\s*(.*)", title)
                    if parsed is None:
                        raise RuntimeError(f"Invalid source index heading: {title}")
                    label, title = parsed.groups()
                evidence = ["published TOC or existing source-verified index", "Poppler word geometry"]
            else:
                unnumbered = _near(UNNUMBERED_HEADINGS, page.number, line.y)
                if not reader.is_heading(line, page) and not unnumbered:
                    continue
                text = line.text
                if re.fullmatch(r"Remark(?: \d+)?", text):
                    title, kind = text, "remark"
                    label = re.sub(r"^Remark\s*", "", text)
                elif unnumbered:
                    if reader.heading_key(text) != reader.heading_key(unnumbered):
                        raise RuntimeError(f"Could not verify unnumbered heading: {unnumbered}")
                    label, title, kind = "", unnumbered, "unnumbered_subdivision"
                elif _near(GREEK_HEADINGS, page.number, line.y):
                    label, title = _near(GREEK_HEADINGS, page.number, line.y)
                    kind = "greek_subdivision"
                elif re.match(r"^[a-z0-9][.)]\s+[A-Za-z]", text):
                    label, title = re.fullmatch(r"([a-z0-9])[.)]\s+(.*)", text).groups()
                    kind = "subdivision"
                elif (page.number, text) in ((96, "general concept of logic"),
                        (111, "general division of the logic"), (410, "essence")):
                    title, label = text.capitalize(), ""
                    kind = "introduction_subdivision" if page.number != 410 else "prefatory_or_introductory_text"
                else:
                    # Equation pieces, chapter captions, and title continuations
                    # are not independent logical subdivisions.
                    continue
                evidence = ["independent whole-main-text font-style audit",
                            "Poppler explicit-anchor heading geometry" if kind == "unnumbered_subdivision"
                            else "Poppler centered/labeled heading geometry"]
            row = {
                "pdf_page": page.number, "printed_page": page.number - 73,
                "y": round(line.y, 3), "x": round(line.x, 3),
                "title": title, "label": label, "kind": kind,
                "source_text": line.text, "confidence": "high", "evidence": evidence,
            }
            _attach_source_span(row, page, index, reader)
            if kind == "greek_subdivision":
                row["evidence"].append("visually verified Greek α/β/γ, replacing extracted Latin a/b/g")
            elif kind == "unnumbered_subdivision":
                row["evidence"].append("visually verified standalone unnumbered italic heading at explicit anchor")
            if kind == "book":
                row["label"] = "One" if page.number == 118 else "Two"
                row["doctrine"] = "Being" if page.number == 118 else "Essence"
            elif kind == "doctrine":
                row["doctrine"] = "Concept"
            rows.append(row)

    missing = [(page, y, node.title) for (page, y), (node, _) in known.items()
               if (page, y) not in consumed]
    if missing:
        raise RuntimeError(f"Source heading verification failed: {missing}")
    rows.extend((_volume(page_map[80], "One", "The Objective Logic", (139.4, 160.2)),
                 _volume(page_map[580], "Two", "The Science of Subjective Logic", (55.4,))))
    rows.sort(key=lambda row: (row["pdf_page"], row["y"]))
    _assign_parents(rows)
    counts = dict(Counter(row["kind"] for row in rows))
    if counts != EXPECTED_COUNTS:
        raise RuntimeError(f"Supported-edition heading counts changed: expected {EXPECTED_COUNTS}, got {counts}")

    being = next(row["audit_id"] for row in rows if row.get("doctrine") == "Being")
    displays = []
    for y, title, kind, target in ((53.3, "The Science of Logic", "work_title", "book-root"),
            (182.1, "Book One", "book_title_page_display", being),
            (204.1, "The Doctrine of Being", "doctrine_title_page_display", being)):
        line = next(item for item in page_map[80].lines if abs(item.y - y) < 1)
        displays.append({**_line_record(line), "pdf_page": 80, "printed_page": 7,
            "start_y": round(line.y, 3), "title": title, "kind": kind,
            "target_audit_id": target})

    return {
        "schema": "sol.heading-audit.v1",
        "scope": {"first_pdf_page": 80, "last_pdf_page": 826, "pages_examined": 747,
                  "edition": "Cambridge, George di Giovanni translation, 2010",
                  "runtime_verification": "Poppler word geometry, anchors, and exact structural counts",
                  "audit_verification": "independent full-main-text font scan; selected rendered source pages"},
        "counts": counts, "title_page_displays": displays, "headings": rows,
        "notes": [
            "Audit IDs are reconciliation keys, not permanent corpus IDs.",
            "Shared prefaces and Introduction belong to Volume One, outside Being.",
            "Book One / Doctrine of Being begins on printed page 45.",
            "Volume Two contains Doctrine of Concept without a separate Book number.",
            "Consume each start_y..end_y span, including caption and subtitle lines.",
            "Logical depth can exceed CommonMark's six visual heading levels.",
            "Prose enumerations and centered equations are not promoted to structural headings.",
            "Transition and Repulsion are explicitly verified unnumbered headings, not style-inferred quotation headings.",
        ],
    }
