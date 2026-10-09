#!/usr/bin/env python3
"""One-time, edition-specific PDF importer; canonical Markdown is edited thereafter.

Conversion uses font-aware Poppler coordinates. Reindexing and ordinary reading
never open the PDF. Generated manuscript text must stay local and Git-ignored.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET

from sol_corpus_contract import CorpusError, new_id, reindex, render_record
from sol_corpus_notes import extract_notes
from sol_corpus_structure import build_hierarchy

PDF_NAME = "georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf"
AUDITED_SOURCE_SHA256 = "f48a2272a6daa80f2742de91e271a2b4b8a93d0a29193b6f02a6e3c010fc0e26"
GAPS = [
    {"printed_page": "l", "before_pdf_page": 50, "after_pdf_page": 51,
     "material": "editor_introduction", "status": "missing_from_source_pdf"},
    {"printed_page": "lxix", "before_pdf_page": 68, "after_pdf_page": 69,
     "material": "translator_note", "status": "missing_from_source_pdf"},
]
EDITION = {
    "title": "The Science of Logic", "author": "G. W. F. Hegel",
    "translator": "George di Giovanni", "editor": "George di Giovanni",
    "publisher": "Cambridge University Press", "year": 2010,
    "isbn": "9780521832557", "language": "en",
}
# Verified source labels whose small-cap font inserts a space after each letter.
SMALL_CAPS_LABELS = {
    "2:30": "George", "2:31": "di", "2:32": "Giovanni",
    "3:0": "CAMBRIDGE HEGEL TRANSLATIONS", "4:3": "Translated and edited by",
    "8:10": "The Science of Logic", "8:12": "Volume One",
    "8:13": "The Objective Logic", "8:21": "Book One: The Doctrine of Being",
    "8:23": "Book Two: The Doctrine of Essence", "8:25": "Volume Two",
    "8:26": "The Science of Subjective Logic or The Doctrine of", "8:27": "The Concept",
    "9:33": "George di Giovanni", "12:1": "Prologue",
    "13:32": "The publication of the Logic", "15:66": "The genesis of the Logic",
    "28:41": "The idea of the Logic", "53:24": "Issues of interpretation",
    "63:1": "The history of translation", "64:56": "Issues of translation",
    "73:5": "The text of the present translation",
    "76:1": "Volume One: The Objective Logic", "76:10": "Book One: The Doctrine of Being",
    "76:16": "Section I: Determinateness (Quality)", "76:30": "Section II: Magnitude (Quantity)",
    "77:2": "Section III: Measure", "77:16": "Book Two: The Doctrine of Essence",
    "77:18": "Section I: Essence as reflection within", "77:32": "Section II: Appearance",
    "77:46": "Section III: Actuality",
    "77:60": "Volume Two: The Science of Subjective Logic or the",
    "77:61": "Doctrine of the Concept", "78:2": "Section I: Subjectivity",
    "78:16": "Section II: Objectivity", "78:30": "Section III: The Idea",
    "827:0": "Appendix",
}
EDITORIAL_SUBHEADINGS = ("12:1", "13:32", "15:66", "28:41", "53:24",
                        "63:1", "64:56", "73:5")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slug(text):
    value = unicodedata.normalize("NFKD", text).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^\w]+", "-", value, flags=re.UNICODE).strip("-")
    return value or "untitled"


def escape(text):
    text = text.replace("&", "&amp;")
    return re.sub(r"([\\*_\x60{}\[\]<>#!|])", r"\\\1", text)


def normalize_glyphs(text):
    accents = {"¨": "\u0308", "´": "\u0301", "ˆ": "\u0302", "˜": "\u0303",
               "˚": "\u030a", "ˇ": "\u030c"}
    text = re.sub(r"([¨´ˆ˜˚ˇ])([A-Za-zı])",
                  lambda m: ("i" if m[2] == "ı" else m[2]) + accents[m[1]], text)
    return unicodedata.normalize("NFC", text)


def load_layout(pdf, work):
    fingerprint = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if fingerprint != AUDITED_SOURCE_SHA256:
        raise CorpusError("This importer is audited for a different source fingerprint. "
                          "Inspect and adapt it before converting another PDF or edition.")
    work.mkdir(parents=True, exist_ok=True)
    cache = work / (fingerprint + ".xml")
    if not cache.exists():
        result = subprocess.run(
            ["pdftohtml", "-q", "-xml", "-i", "-hidden", "-fontfullname",
             "-zoom", "1", "-noroundcoord", "-stdout", str(pdf)],
            capture_output=True, check=True,
        )
        cache.write_bytes(result.stdout)
    raw = re.sub(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", "\ufffd".encode(), cache.read_bytes())
    root = ET.fromstring(raw)
    fonts, pages = {}, []
    for element in root.findall("page"):
        number = int(element.attrib["number"])
        for font in element.findall("fontspec"):
            fonts[font.attrib["id"]] = font.attrib
        spans = []
        for index, element_text in enumerate(element.findall("text")):
            font = fonts[element_text.attrib["font"]]
            family = font["family"]
            text = normalize_glyphs("".join(element_text.itertext()))
            if "RegularSC" in family:
                text = SMALL_CAPS_LABELS.get(f"{number}:{index}", text)
            spans.append({
                "source_id": f"{number}:{index}", "pdf_page": number,
                "x": float(element_text.attrib["left"]),
                "y": float(element_text.attrib["top"]),
                "width": float(element_text.attrib["width"]),
                "height": float(element_text.attrib["height"]),
                "size": float(font["size"]), "family": family, "text": text,
                "italic": "Italic" in family or element_text.find(".//i") is not None,
                "bold": "Bold" in family or element_text.find(".//b") is not None,
            })
        pages.append({"number": number, "width": float(element.attrib["width"]),
                      "height": float(element.attrib["height"]), "spans": spans})
    if [p["number"] for p in pages] != list(range(1, 864)):
        raise CorpusError("This importer supports the inspected 863-page Cambridge PDF only")
    return pages, fingerprint


def visible_labels(pages):
    labels, status = {}, {}
    for page in pages:
        n = page["number"]
        candidates = [
            s["text"].strip() for s in page["spans"]
            if (s["y"] < 48 or s["y"] > 548)
            and re.fullmatch(r"(?:[ivxlcdm]+|\d+)", s["text"].strip())
            and not s["italic"]
        ]
        candidates = list(dict.fromkeys(candidates))
        expected = str(n - 73) if n >= 74 else None
        roman = [v for v in candidates if not v.isdigit()]
        labels[n] = expected if expected in candidates else (roman[0] if len(roman) == 1 else None)
        status[n] = "visible" if labels[n] is not None else "unprinted"
    if [labels[n] for n in (50, 51, 68, 69)] != ["xlix", "li", "lxviii", "lxx"]:
        raise CorpusError("Visible front-matter labels do not match the audited source gaps")
    return labels, status


def line_plain(line):
    text, previous = "", None
    for span in line["spans"]:
        if previous and span["x"] - previous["x"] - previous["width"] > .7:
            text += " "
        text += span["text"]
        previous = span
    return text.strip()


def span_lines(spans):
    """Regular glyphs anchor lines; oldstyle digits and superscripts attach to them."""
    by_page = defaultdict(list)
    for span in spans:
        by_page[span["pdf_page"]].append(span)
    output = []
    for page, values in sorted(by_page.items()):
        anchors = []
        for span in sorted(values, key=lambda s: (s["y"], s["x"])):
            if ("Exp" not in span["family"] and span["height"] >= 7.8
                and span["height"] <= span["size"] * 1.2 and span["text"].strip() != "¨"):
                if not anchors or min(abs(span["y"] - a) for a in anchors) > .7:
                    anchors.append(span["y"])
        groups = defaultdict(list)
        for span in values:
            closest = min(anchors, key=lambda y: abs(y - span["y"])) if anchors else span["y"]
            allowance = (3.7 if "Exp" in span["family"] or span["height"] > span["size"] * 1.2
                         else 8 if span["text"].strip() == "¨"
                         else 5.8 if span["height"] < 7.8 else .7)
            anchor = closest if abs(closest - span["y"]) <= allowance else span["y"]
            groups[anchor].append(span)
        for y, group in sorted(groups.items()):
            group.sort(key=lambda s: s["x"])
            output.append({"page": page, "y": y, "x": min(s["x"] for s in group),
                           "right": max(s["x"] + s["width"] for s in group),
                           "spans": group})
    return output


def styled_text(lines, vocabulary):
    """Join line wraps before emitting emphasis, retaining genuine compounds."""
    runs = []
    for line in lines:
        current, previous = [], None
        values = [dict(s) for s in line["spans"] if s["text"].strip() != "¨"]
        for accent in (s for s in line["spans"] if s["text"].strip() == "¨"):
            targets = [s for s in values if s["text"] and s["x"] <= accent["x"] <= s["x"] + s["width"]]
            if targets:
                target = min(targets, key=lambda s: abs(accent["x"]-s["x"]))
                target["text"] = unicodedata.normalize("NFC", target["text"][0] + "\u0308" + target["text"][1:])
            else:
                values.append(accent)
                values.sort(key=lambda s: s["x"])
        for i in range(len(values)-1):
            first, following = values[i], values[i+1]
            if (first["text"].endswith("¨") and following["text"][:1].isalpha()
                and following["x"]-first["x"]-first["width"] < 2):
                first["text"] = first["text"][:-1]
                if re.search(r"[“‘(\[]\s+$", first["text"]):
                    first["text"] = first["text"].rstrip()
                following["text"] = unicodedata.normalize(
                    "NFC", following["text"][0]+"\u0308"+following["text"][1:])
        for span in values:
            text = span["text"].replace("\u00ad", "").replace("\u00a0", " ")
            if previous and span["x"] - previous["x"] - previous["width"] > .7 and not span.get("callout"):
                current.append([" ", None])
            if span.get("link"):
                current.append([span["link"], "raw"])
            elif span.get("superscript"):
                current.append(["<sup>" + escape(text) + "</sup>", "raw"])
            else:
                style = ("***" if span["bold"] and span["italic"] else
                         "*" if span["italic"] else "**" if span["bold"] else None)
                current.append([text, style])
            previous = span
        # Work on visible characters, not Markdown delimiters, for hyphen repair.
        before = "".join(t for t, st in runs if st != "raw").rstrip()
        after = "".join(t for t, st in current if st != "raw").lstrip()
        left = re.search(r"([A-Za-z]+(?:-[A-Za-z]+)*)-$", before)
        right = re.match(r"[A-Za-z]+", after)
        if left and right:
            a, b = left[1], right[0]
            compound, joined = (a + "-" + b).casefold(), (a + b).casefold()
            retain = compound in vocabulary or (joined not in vocabulary and (
                "-" in a or a.casefold() in {"self", "non", "being", "for", "in", "form", "sense", "co"}))
            if not retain:
                for run in reversed(runs):
                    if run[1] != "raw" and run[0].strip():
                        run[0] = run[0].rstrip()[:-1]
                        break
        elif runs:
            runs.append([" ", None])
        runs.extend(current)
    merged = []
    for text, style in runs:
        if merged and style == merged[-1][1]:
            merged[-1][0] += text
        else:
            merged.append([text, style])
    out = ""
    for text, style in merged:
        if style == "raw":
            out += text
        elif style:
            match = re.fullmatch(r"(\s*)(.*?)(\s*)", text, re.S)
            content = match[2]
            # CommonMark cannot always delimit emphasis ending in punctuation
            # immediately before a letter/digit (e.g. italic "self-" + "reference").
            if content and (not content[0].isalnum() or not content[-1].isalnum()):
                tag = "em" if style == "*" else "strong"
                visible = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                styled = f"<{tag}>{visible}</{tag}>"
                if style == "***":
                    styled = "<em>" + styled + "</em>"
            else:
                styled = style + escape(content) + style if content else ""
            out += match[1] + styled + match[3]
        else:
            out += escape(text)
    return out.strip()


def source_refs(spans, labels):
    groups = defaultdict(list)
    for span in spans:
        groups[span["pdf_page"]].append(span)
    return [
        {"pdf_page": n, "printed_page": labels[n],
         "bbox": [round(min(s["x"] for s in group), 3),
                  round(min(s["y"] for s in group), 3),
                  round(max(s["x"] + s["width"] for s in group), 3),
                  round(max(s["y"] + s["height"] for s in group), 3)]}
        for n, group in sorted(groups.items())
    ]


def render_source_text(lines, vocabulary):
    """Preserve the source-verified Subject/Predicate schema in its paragraph."""
    schema = [line for line in lines if line["page"] == 634 and 136 < line["y"] < 170]
    if not schema:
        starts = [i for i, line in enumerate(lines)
                  if re.match(r"^(?:[IVX]+|\d+|[a-z])[.)]\s", line_plain(line))]
        if len(starts) >= 2:
            before = styled_text(lines[:starts[0]], vocabulary)
            items = []
            boundaries = starts + [len(lines)]
            for a, b in zip(boundaries, boundaries[1:]):
                item = styled_text(lines[a:b], vocabulary)
                item = re.sub(r"^(\d+)([.)]) ", r"\1\\\2 ", item)
                items.append("- " + item)
            return (before + ("\n\n" if before else "") + "\n".join(items)).strip()
        return styled_text(lines, vocabulary)
    start, end = lines.index(schema[0]), lines.index(schema[-1]) + 1
    left = min(s["x"] for line in schema for s in line["spans"])
    rows = []
    for line in schema:
        row = ""
        for span in line["spans"]:
            column = round((span["x"]-left)/5)
            row += " "*max(1 if row else 0, column-len(row)) + span["text"]
        rows.append(row.rstrip())
    fence = chr(96)*3
    return (styled_text(lines[:start], vocabulary) + "\n\n" +
            fence + "text\n" + "\n".join(rows) + "\n" + fence + "\n\n" +
            styled_text(lines[end:], vocabulary)).strip()


def attribution(page, note=False):
    if note:
        return {"author": None, "role": "footnote", "status": "unverified",
                "reason": "Marker style is not sufficient evidence for authorship; editorial additions may occur within author notes."}
    if 80 <= page <= 826:
        return {"author": "G. W. F. Hegel", "role": "main_text", "status": "edition_attributed"}
    if 12 <= page <= 73:
        return {"author": "George di Giovanni", "role": "editorial", "status": "edition_attributed"}
    return {"author": None, "role": "reference" if page >= 830 else "front_or_back_matter",
            "status": "edition_material"}


class Importer:
    def __init__(self, pdf, pages, labels, hierarchy, stage):
        self.pdf, self.pages, self.labels = pdf, pages, labels
        self.hierarchy, self.stage = hierarchy, stage
        self.records, self.owners, self.claimed, self.review = [], {}, {}, []
        self.page_map = {p["number"]: p for p in pages}
        self.vocabulary = set(re.findall(r"[a-z]+(?:-[a-z]+)*",
            " ".join(s["text"].casefold() for p in pages for s in p["spans"])))
        self.note_lookup = defaultdict(list)
        self.note_records = []
        self.heads = []
        self.groups = []
        self.editorial_heads = []

    def make(self, kind, parent, spans, doc, markdown="", **extra):
        if not spans:
            raise CorpusError(f"Record {kind} lacks source evidence")
        page = spans[0]["pdf_page"]
        record = {
            "id": new_id(), "type": kind, "parent_id": parent["id"] if parent else None,
            "order": 0, "sources": source_refs(spans, self.labels),
            "attribution": attribution(page), **extra,
            "_doc": doc, "_md": markdown, "_spans": spans,
            "_position": (page, min(s["y"] for s in spans if s["pdf_page"] == page),
                          min(s["x"] for s in spans if s["pdf_page"] == page)),
        }
        self.records.append(record)
        return record

    def claim(self, spans, record=None, reason=None):
        for span in spans:
            sid = span["source_id"]
            if sid in self.claimed:
                raise CorpusError(f"Source span assigned twice: {sid}")
            self.claimed[sid] = ({"record_id": record["id"]} if record else
                                 {"reason": reason, "text": span["text"]})

    def structures(self):
        title = self.page_map[74]["spans"]
        root = self.make("section", None, title, "catalog.md", "# The Science of Logic",
                         title="The Science of Logic", path="/", generated_heading=True)
        root["_position"] = (0, 0, 0)
        self.root = root
        audit_map = {"book-root": root}
        children = Counter(row["parent_audit_id"] for row in self.hierarchy["headings"])
        for row in self.hierarchy["headings"]:
            parent = audit_map[row["parent_audit_id"]]
            page = row["pdf_page"]
            spans = [s for s in self.page_map[page]["spans"]
                     if any(abs(s["y"]-line["y"]) <= (
                                4 if "Exp" in s["family"] or s["size"] < 11 else .8)
                            and line["x"]-.8 <= s["x"] <= line["end_x"]+.8
                            for line in row["source_lines"])
                     and s["source_id"] not in self.claimed]
            # Volume Two and its doctrine wrapper share a displayed heading.
            evidence = spans or [s for s in self.page_map[page]["spans"]
                                if abs(s["y"] - row["y"]) < .7]
            label = row.get("label", "")
            name = slug((label + "-" if label else "") + row["title"])
            path = parent["path"].rstrip("/") + "/" + name
            doctrine = "being" if page < 410 else "essence" if page < 580 else "concept"
            parent_doc = parent["_doc"]
            if row["kind"] == "chapter":
                section_name = parent.get("_file_slug", "preliminary")
                doc = f"hegel/{doctrine}/{section_name}/{name}.md"
            elif row["kind"] in {"section", "book", "volume", "doctrine"}:
                doc = (f"hegel/{doctrine}/{name}/00-introduction.md"
                       if row["kind"] == "section" else "hegel/structure.md")
            elif row["kind"] == "prefatory_or_introductory_text" and page < 118:
                doc = f"hegel/preliminary/{name}.md"
            elif row["kind"] == "prefatory_or_introductory_text":
                doc = f"hegel/{doctrine}/preliminary/{name}.md"
            else:
                doc = parent_doc if parent_doc != "catalog.md" else "hegel/preliminary/introduction.md"
            kind = row["kind"]
            if kind in {"volume", "book", "doctrine"}:
                reader_path = "/" + doctrine.upper()
            else:
                reader_parent = parent.get("reader_path", "/" + doctrine.upper())
                # Book Two overrides the Volume One reader projection.
                if page >= 410 and reader_parent.startswith("/BEING"):
                    reader_parent = "/ESSENCE"
                reader_path = reader_parent + "/" + name
            if not children[row["audit_id"]] and kind not in {"volume", "book", "doctrine"}:
                reader_path += ".txt"
            record = self.make(
                "section", parent, evidence, doc,
                "#" * min(row["depth"] + 1, 6) + " " + escape(
                    ((label + ". ") if label else "") + row["title"]),
                title=row["title"], label=label, path=path, level=row["depth"],
                source_kind=kind, reader_path=reader_path, reader_title=row["title"],
                audit_id=row["audit_id"],
            )
            record["_file_slug"] = name
            record["source_heading"] = row["source_text"]
            if row.get("subtitle"):
                record["subtitle"] = row["subtitle"]
                record["_md"] += "\n\n*" + escape(row["subtitle"]) + "*"
            record["_position"] = (page, row["start_y"], 0)
            self.claim(spans, record)
            audit_map[row["audit_id"]] = record
            self.heads.append(record)
        for display in self.hierarchy.get("title_page_displays", []):
            spans = [s for s in self.page_map[display["pdf_page"]]["spans"]
                     if display["start_y"] - .65 <= s["y"] <= display["end_y"] + .65
                     and s["source_id"] not in self.claimed]
            if spans:
                record = self.make("title_display", audit_map[display["target_audit_id"]],
                                   spans, "hegel/structure.md",
                                   styled_text(span_lines(spans), self.vocabulary),
                                   title=display["title"])
                self.claim(spans, record)
        ranges = [
            (1, 11, "Publisher and front matter", "editorial/front-matter.md"),
            (12, 62, "Editor introduction", "editorial/introduction.md"),
            (63, 73, "Translator's note", "editorial/translator-note.md"),
            (74, 79, "Original title and published contents", "editorial/published-contents.md"),
            (827, 829, "Appendix", "references/appendix.md"),
            (830, 849, "Bibliography", "references/bibliography.md"),
            (850, 863, "Subject index", "references/index.md"),
        ]
        for lo, hi, title, doc in ranges:
            evidence = next(p["spans"] for p in self.pages if lo <= p["number"] <= hi and p["spans"])
            group = self.make("section", root, evidence[:1], doc, "## " + escape(title),
                              title=title, path="/" + slug(title), generated_heading=True)
            group["_position"] = (lo, 0, 0)
            self.groups.append((lo, hi, group))
            if lo in {12, 63, 827}:
                source_title = self.page_map[lo]["spans"][:1]
                self.claim(source_title, group)
                group["sources"] = source_refs(source_title, self.labels)
                group["generated_heading"] = False
        by_sid = {s["source_id"]: s for p in self.pages for s in p["spans"]}
        for sid in EDITORIAL_SUBHEADINGS:
            span = by_sid[sid]
            parent = next(group for lo, hi, group in self.groups if lo <= span["pdf_page"] <= hi)
            title = SMALL_CAPS_LABELS[sid]
            record = self.make("section", parent, [span], parent["_doc"],
                               "### " + escape(title), title=title,
                               source_kind="editorial_subdivision",
                               path=parent["path"]+"/"+slug(title))
            self.claim([span], record)
            self.editorial_heads.append(record)

    def owner(self, page, y):
        if 80 <= page <= 826:
            candidates = [r for r in self.heads if r["_position"][:2] <= (page, y)]
            return candidates[-1] if candidates else self.root
        lo, hi, group = next(row for row in self.groups if row[0] <= page <= row[1])
        candidates = [r for r in self.editorial_heads if lo <= r["_position"][0] <= hi
                      and r["_position"][:2] <= (page, y)]
        return candidates[-1] if candidates else group

    def setup_notes(self, extracted):
        for note in extracted["notes"]:
            parent = self.owner(note["start_page"], note["spans"][0]["y"])
            doc = "notes/" + parent["_doc"].removesuffix(".md").replace("/", "--") + ".md"
            record = self.make("note", parent, note["spans"], doc,
                               "#### Note " + escape(note["label"] or "unlabelled"),
                               label=note["label"] or "", note_ids=[], backlinks=[],
                               attribution=attribution(note["start_page"], note=True))
            record["_note"] = note
            record["_position"] = (note["start_page"], note["spans"][0]["y"], 0)
            self.note_records.append(record)
            self.note_lookup[(note["start_page"], note["label"])].append(record)
        self.review.extend(extracted["warnings"])

    def link_spans(self, record, spans):
        prose = [s for s in spans if "AGaramond" in s["family"]
                 and "Exp" not in s["family"] and s["text"].strip()]
        base_size = max(s["size"] for s in prose) if prose else 11
        for span in spans:
            candidate = re.sub(r"\s+", "", span["text"].strip())
            if (span["size"] > base_size - 1.2
                or not re.search(r"AGaramond(?:Exp)?-Regular(?:SC)?$", span["family"])
                or not re.fullmatch(r"(?:[a-z]|\d{1,3})(?:[,.;:–-]\d{0,3})*", candidate)):
                continue
            nearby = [s for s in prose if s["pdf_page"] == span["pdf_page"]
                      and abs(s["y"]-span["y"]) <= 6]
            if not nearby or span["y"] > min(nearby, key=lambda s: abs(s["x"]-span["x"]))["y"] + .8:
                continue
            targets = []
            for label in re.split(r"([,.;:–-])", candidate):
                found = self.note_lookup.get((span["pdf_page"], label), [])
                if len(found) == 1 and found[0]["id"] != record.get("parent_id"):
                    target = found[0]
                    preceding = [s for s in spans if s["pdf_page"] == span["pdf_page"]
                                 and abs(s["y"]-span["y"]) <= 6 and s["x"] < span["x"]]
                    previous = max(preceding, key=lambda s: s["x"] + s["width"]) if preceding else None
                    if (label.isdigit() and previous and not previous["family"].endswith("RegularSC")
                        and re.search(r"(?:^|\s)[a-z]$", previous["text"].strip())
                        and span["x"]-previous["x"]-previous["width"] < 1.5):
                        targets.append("<sup>" + escape(label) + "</sup>")
                        continue
                    href = os.path.relpath(target["_doc"], Path(record["_doc"]).parent).replace(os.sep, "/")
                    targets.append(f'<sup data-sol-note="{target["id"]}">[{escape(label)}]({href}#{target["id"]})</sup>')
                    record.setdefault("note_ids", []).append(target["id"])
                    target["backlinks"].append(record["id"])
                    if len(target["backlinks"]) == 1:
                        target["parent_id"] = record["id"]
                else:
                    targets.append(escape(label))
            if any("](" in t for t in targets):
                span["link"] = "".join(targets)
                span["callout"] = True
            else:
                span["superscript"] = True

    def heading_notes(self):
        for record in self.heads:
            self.link_spans(record, record["_spans"])
            links = [s["link"] for s in record["_spans"] if s.get("link")]
            if links:
                first, *rest = record["_md"].split("\n", 1)
                record["_md"] = first + " " + "".join(links) + ("\n" + rest[0] if rest else "")

    def paragraph_blocks(self, lines, note=False):
        """Recover indentation boundaries; never bridge a known missing source page."""
        current, previous, owner = [], None, None
        for line in lines:
            page = line["page"]
            active = self.owner(page, line["y"]) if not note else None
            left = self.left(page)
            if note:
                candidates = [s["x"] for s in self.page_map[page]["spans"]
                              if 7.3 <= s["size"] <= 8.5 and s["height"] >= 7.8 and len(s["text"]) > 15]
                left = min(candidates) if candidates else left
            indent = line["x"] - left
            new_indent = 5.5 < indent < (14 if note else 19)
            same_page_gap = previous and previous["page"] == page and line["y"] - previous["y"] > (15 if note else 19)
            gap = previous and (previous["page"], page) in {(50, 51), (68, 69)}
            text = line_plain(line)
            if (new_indent and previous and text[:1].islower()
                and not line_plain(previous).endswith((".", "!", "?", ":"))):
                new_indent = False
            start = new_indent or (same_page_gap and (line_plain(previous).endswith((".", "!", "?", ":"))))
            # A hanging centered equation is not an ordinary indented paragraph.
            if current and (active is not owner or start or gap):
                yield owner, current
                current = []
            if not current:
                owner = active
            current.append(line)
            previous = line
        if current:
            yield owner, current

    def left(self, page):
        values = [round(s["x"], 2) for s in self.page_map[page]["spans"]
                  if 10.3 <= s["size"] <= 11.7 and 50 < s["y"] < 550 and len(s["text"]) > 25]
        if values:
            count = Counter(values)
            return max(count, key=lambda x: (count[x], -x))
        label = self.labels[page]
        return 53.48 if label and label.isdigit() and int(label) % 2 else 66.12

    def cleaned_pages(self, extracted):
        output = []
        for page in extracted["pages"]:
            n, spans = page["number"], []
            for span in page["body_spans"]:
                if span["source_id"] in self.claimed:
                    continue
                text = span["text"].strip()
                if (n >= 8 and span["y"] < 47) or (
                    span["y"] > 550 and re.fullmatch(r"\d+|[ivxlcdm]+", text)):
                    self.claim([span], reason="running_header_or_printed_page_label")
                elif 80 <= n <= 826 and span["bold"] and re.fullmatch(r"\d+\.\d+", text) and (
                    span["x"] < self.left(n) - 5 or span["x"] > self.left(n) + 300):
                    self.claim([span], reason="critical_edition_margin_reference")
                elif not text and not re.search(r"MTSY|MTEX|CMSY|RMTMI", span["family"]):
                    self.claim([span], reason="empty_layout_span")
                else:
                    spans.append(span)
            output.append({"number": n, "body_spans": spans})
        return output

    def text_record(self, parent, lines, kind="paragraph", doc=None):
        spans = [s for line in lines for s in line["spans"]]
        record = self.make(kind, parent, spans, doc or parent["_doc"], note_ids=[])
        self.link_spans(record, spans)
        record["_md"] = render_source_text(lines, self.vocabulary)
        if sum(bool(re.match(r"^(?:[IVX]+|\d+|[a-z])[.)]\s", line_plain(line)))
               for line in lines) >= 2:
            record["contains_list"] = True
        # Ordinary source enumerations should not silently become Markdown lists.
        if re.match(r"^\d+[.)] ", record["_md"]):
            record["_md"] = re.sub(r"^(\d+)([.)]) ", r"\1\\\2 ", record["_md"])
        if record["_md"].startswith(("- ", "+ ")):
            record["_md"] = "\\" + record["_md"]
        if 80 <= spans[0]["pdf_page"] <= 826 and kind in {"paragraph", "list_item", "quotation", "formula"}:
            path = parent["reader_path"]
            record["reader_path"] = path if path.endswith(".txt") else path + "/00-introduction.txt"
            record["reader_title"] = parent["title"]
            record["heading"] = parent["title"]
        if any("\ufffd" in s["text"] for s in spans):
            record["transcription_status"] = "needs_review"
            self.review.append({"code": "unmapped_source_glyph", "record_id": record["id"],
                                "sources": record["sources"]})
        self.claim(spans, record)
        return record

    def body(self, cleaned):
        lines = []
        for page in cleaned:
            if page["number"] >= 830:
                continue
            lines.extend(span_lines(page["body_spans"]))
        for parent, block in self.paragraph_blocks(lines):
            page = block[0]["page"]
            kind = "published_contents_entry" if 74 <= page <= 79 else "paragraph"
            if parent is self.root:
                kind = "title_display"
            # Explicit formula typography is retained, separately reviewable.
            symbol = any(re.search(r"MTSY|MTEX|CMSY|RMTMI|BookCondensedItalic", s["family"])
                         or "\ufffd" in s["text"]
                         for line in block for s in line["spans"])
            if symbol and 80 <= page <= 826:
                prose_words = re.findall(r"[A-Za-z]{3,}", " ".join(line_plain(line) for line in block))
                kind = "paragraph" if len(prose_words) >= 12 else "formula"
            record = self.text_record(parent, block, kind)
            if symbol and 80 <= page <= 826:
                record["contains_math"] = True
                record["random_eligible"] = False
                record["transcription_status"] = "needs_visual_review"
                self.review.append({"code": "formula_transcription", "record_id": record["id"],
                                    "sources": record["sources"]})
                self.formula_image(record)
        for gap in GAPS:
            parent = self.owner(gap["before_pdf_page"], 550)
            span = self.page_map[gap["before_pdf_page"]]["spans"][-1:]
            record = self.make("source_gap", parent, span, parent["_doc"],
                "> Source gap: printed page " + gap["printed_page"] +
                " is missing from the supplied PDF. No text has been reconstructed.",
                gap=gap, generated_text=True)
            record["_position"] = (gap["before_pdf_page"], 600, 0)

    def formula_image(self, record):
        """Keep a facsimile when symbol encoding cannot support reliable transcription."""
        links = []
        for source in record["sources"]:
            x0, y0, x1, y1 = source["bbox"]
            filename = f"{record['id']}-{source['pdf_page']}"
            prefix = self.stage / "assets" / filename
            prefix.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["pdftoppm", "-f", str(source["pdf_page"]), "-l", str(source["pdf_page"]),
                 "-singlefile", "-png", "-r", "144", "-x", str(max(0, int(x0 * 2) - 5)),
                 "-y", str(max(0, int(y0 * 2) - 5)), "-W", str(int((x1-x0)*2)+12),
                 "-H", str(int((y1-y0)*2)+12), str(self.pdf), str(prefix)],
                capture_output=True, check=True,
            )
            relative = os.path.relpath(prefix.with_suffix(".png"), self.stage / Path(record["_doc"]).parent).replace(os.sep, "/")
            links.append(f"![Source facsimile, printed page {source['printed_page']}]({relative})")
        record["_md"] += "\n\n" + "\n\n".join(links)

    def notes(self):
        for container in self.note_records:
            source = container["_note"]
            definition = source["definition_source_id"]
            spans = [s for s in source["spans"] if s["source_id"] != definition]
            markers = [s for s in source["spans"] if s["source_id"] == definition]
            self.claim(markers, container)
            for _, block in self.paragraph_blocks(span_lines(spans), note=True):
                record = self.text_record(container, block, "note_paragraph", container["_doc"])
                record["attribution"] = attribution(source["start_page"], note=True)
                if any(re.search(r"MTSY|MTEX|CMSY|RMTMI|BookCondensedItalic", s["family"])
                       for line in block for s in line["spans"]):
                    record["transcription_status"] = "needs_visual_review"
                    self.formula_image(record)
                    self.review.append({"code": "note_formula_transcription", "record_id": record["id"],
                                        "sources": record["sources"]})
            if not container["backlinks"]:
                self.review.append({"code": "unlinked_note", "record_id": container["id"],
                                    "label": container["label"], "sources": container["sources"]})

    def references(self, cleaned):
        from sol_corpus_references import segment_references
        for kind, lo, hi in (("bibliography", 830, 849), ("index", 850, 863)):
            result = segment_references([p for p in cleaned if lo <= p["number"] <= hi], kind)
            self.review.extend(result["warnings"])
            parent = self.owner(lo, 0)
            container = parent
            category_root = parent
            for entry in result["entries"]:
                if entry["type"] == "section":
                    record = self.make("section", category_root, entry["spans"], container["_doc"],
                                       "### " + escape(entry["title"]), title=entry["title"],
                                       path=category_root["path"] + "/" + slug(entry["title"]))
                    self.claim(entry["spans"], record)
                    parent = record
                    if entry["title"].upper() in {"BIBLIOGRAPHY", "INDEX"}:
                        category_root = record
                else:
                    # Preserve the reference segmenter's column order, including
                    # an entry continued from left-column bottom to right top.
                    ordered_lines = []
                    for line in entry["lines"]:
                        ordered_lines.append({
                            "page": line["pdf_page"], "y": line["y"], "x": line["x"],
                            "right": max(s["x"]+s["width"] for s in line["spans"]),
                            "spans": line["spans"],
                        })
                    record = self.text_record(parent, ordered_lines,
                                              "bibliography_entry" if kind == "bibliography" else "index_entry")
                    record["title"] = entry["title"]
                    record["reference_section"] = entry.get("section")

    def serialize(self, fingerprint, label_status):
        by_id = {r["id"]: r for r in self.records}
        # A callout, not the footnote's position at the bottom of a page,
        # determines its semantic parent. Nested editorial notes remain nested.
        for note in self.note_records:
            if note["backlinks"]:
                anchor = min((by_id[i] for i in note["backlinks"]), key=lambda r: r["_position"])
                note["parent_id"] = anchor["id"]
                note["attachment_status"] = "linked_callout"
            else:
                note["attachment_status"] = "unresolved"
        docs = sorted({r["_doc"] for r in self.records if r["_doc"] != "catalog.md"})
        self.root["_md"] += (
            "\n\nLocal working corpus of the Cambridge 2010 edition. "
            "Generated conversion, not a fully proofread critical text. "
            "Keep this directory private and excluded from Git. "
            "Printed pages l and lxix are absent from the source PDF.\n\n"
            "## Documents\n\n" +
            "\n".join("- [" + escape(doc.removesuffix(".md").replace("/", " / ")) +
                      "](" + doc + ")" for doc in docs))
        # Reference containers have page evidence, but do not duplicate source ownership.
        pending = sorted(self.records, key=lambda r: r["_position"])
        ordered, emitted = [], set()
        while pending:
            progress = False
            for record in pending[:]:
                if record["parent_id"] is None or record["parent_id"] in emitted:
                    record["order"] = len(ordered)
                    ordered.append(record)
                    emitted.add(record["id"])
                    pending.remove(record)
                    progress = True
            if not progress:
                raise CorpusError("Canonical parent graph contains a cycle")
        by_doc = defaultdict(list)
        for record in ordered:
            for key in ("note_ids", "backlinks"):
                if key in record:
                    record[key] = list(dict.fromkeys(record[key]))
            metadata = {k: v for k, v in record.items() if not k.startswith("_")}
            by_doc[record["_doc"]].append(render_record(metadata, record["_md"]))
        for doc, fragments in by_doc.items():
            path = self.stage / doc
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(fragments), encoding="utf-8")
        all_ids = {s["source_id"] for p in self.pages for s in p["spans"]}
        if all_ids != set(self.claimed):
            missing = sorted(all_ids - set(self.claimed))
            raise CorpusError(f"{len(missing)} unaccounted source spans: {missing[:20]}")
        cited = {s["pdf_page"] for r in ordered for s in r["sources"]}
        inventory = [{"pdf_page": p["number"], "printed_page": self.labels[p["number"]],
                      "label_status": label_status[p["number"]],
                      "inferred_printed_page": str(p["number"]-73) if p["number"] >= 74 else None,
                      "disposition": "records" if p["number"] in cited else "blank" if not p["spans"] else "excluded",
                      "reason": "No text spans" if not p["spans"] else "All spans explicitly accounted for"}
                     for p in self.pages]
        manifest = {
            "contract_version": 1, "edition": EDITION,
            "source": {"filename": self.pdf.name, "sha256": fingerprint, "pdf_pages": len(self.pages)},
            "rights": {"redistribution": "not_authorized", "storage": "local_only"},
            "documents": sorted(by_doc), "page_inventory": inventory, "source_gaps": GAPS,
            "completeness": {"all_available_text_spans_accounted_for": True,
                             "published_edition_complete": False,
                             "manually_proofread_every_paragraph": False,
                             "note_authorship_fully_verified": False},
            "counts": {"records": len(ordered), "types": dict(Counter(r["type"] for r in ordered)),
                       "source_spans": len(all_ids), "headings": len(self.heads),
                       "notes": len(self.note_records), "review_items": len(self.review)},
        }
        write_json(self.stage / "corpus.json", manifest)
        write_json(self.stage / "audit" / "hierarchy.json", self.hierarchy)
        write_json(self.stage / "audit" / "source-spans.json", self.claimed)
        write_json(self.stage / "audit" / "review.json", {"source_gaps": GAPS, "items": self.review})
        return reindex(self.stage)


def require_ignored(output):
    probe = output.parent
    while not probe.exists():
        probe = probe.parent
    repo = subprocess.run(["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True)
    if repo.returncode:
        return
    root = Path(repo.stdout.strip())
    relative = output.relative_to(root)
    for sentinel in ("corpus.json", "hegel/chapter.md", "index.jsonl",
                     "assets/source.png", "audit/source.json", "layout.xml"):
        result = subprocess.run(["git", "-C", str(root), "check-ignore", "--quiet",
                                 str(relative / sentinel)])
        if result.returncode:
            raise CorpusError(f"Refusing conversion inside Git: ignore all of {relative}/ before proceeding")


def convert(pdf, output, work):
    pdf, output, work = pdf.resolve(), output.resolve(), work.resolve()
    if output.exists():
        raise CorpusError("Corpus already exists. Correct its Markdown and run index; do not regenerate permanent IDs.")
    require_ignored(output)
    require_ignored(work)
    work.mkdir(parents=True, exist_ok=True)
    # Failed attempts are retained privately for diagnosis, never overwritten.
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=output.name + ".building-", dir=output.parent))
    require_ignored(stage)
    pages, fingerprint = load_layout(pdf, work)
    labels, status = visible_labels(pages)
    hierarchy = build_hierarchy(pdf)
    importer = Importer(pdf, pages, labels, hierarchy, stage)
    importer.structures()
    extracted = extract_notes(pages)
    if len(extracted["notes"]) != 761 or extracted["warnings"]:
        raise CorpusError("Footnote segmentation differs from the audited 761-note source")
    importer.setup_notes(extracted)
    importer.heading_notes()
    cleaned = importer.cleaned_pages(extracted)
    importer.body(cleaned)
    importer.notes()
    importer.references(cleaned)
    summary = importer.serialize(fingerprint, status)
    stage.rename(output)
    summary["index"] = str(output / "index.jsonl")
    summary["metadata"] = str(output / "index.meta.json")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("convert", help="one-time conversion of the inspected Cambridge PDF")
    create.add_argument("--pdf", type=Path, default=Path("sources") / PDF_NAME)
    create.add_argument("--output", type=Path, default=Path("local-corpus"))
    create.add_argument("--work", type=Path, default=Path(".sol-corpus-work"))
    index = commands.add_parser("index", help="regenerate JSONL after canonical Markdown corrections")
    index.add_argument("corpus", type=Path, nargs="?", default=Path("local-corpus"))
    args = parser.parse_args(argv)
    try:
        summary = (convert(args.pdf, args.output, args.work) if args.command == "convert"
                   else reindex(args.corpus))
    except (CorpusError, OSError, subprocess.SubprocessError, ET.ParseError) as error:
        parser.exit(1, f"sol corpus: {error}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
