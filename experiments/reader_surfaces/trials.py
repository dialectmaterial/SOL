"""Edition-specific reading exercises over supplied structure, not inferred logic.

Preset names are conveniences for a disposable comparison, never corpus IDs.
Boundaries come from explicit sections and parent relationships. Incompatible
editions fail visibly rather than guessing from prose or selecting a default.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from sol.reader.actions import ReaderActions
from .common import Sample, sample_from_book


PRESETS = ("beginning", "opening")
_READABLE = {"paragraph", "list_item", "quotation", "formula"}


@dataclass(frozen=True)
class ReadingTrial:
    sample: Sample
    _metadata: dict = field(repr=False)

    @property
    def metadata(self):
        return deepcopy(self._metadata)


def select_trial(book, name: str) -> ReadingTrial:
    if name not in PRESETS:
        raise ValueError("unknown reading trial; choose beginning or opening")
    records = book.canonical_records

    def unsupported(reason):
        raise ValueError(f"reading trial {name!r} is unavailable: {reason}; no substitute sample was chosen")

    def section(title, label, parent=None, path=None):
        matches = [record for record in records.values()
                   if record.get("type") == "section" and record.get("title") == title
                   and record.get("label") == label
                   and (parent is None or record.get("parent_id") == parent["id"])
                   and (path is None or record.get("reader_path") == path)]
        if len(matches) != 1:
            unsupported(f"expected one supplied {label} {title} section in the supported hierarchy")
        record = matches[0]
        if type(record.get("order")) is not int:
            unsupported("section source order is invalid")
        return record

    objective = section("The Objective Logic", "One", path="/BEING")
    doctrine = section("The Doctrine of Being", "One", objective, "/BEING")
    quality = section("Determinateness (Quality)", "I", doctrine)
    chapter = section("Being", "1", quality)
    following = section("Existence", "2", quality)
    being = section("Being", "A", chapter)
    nothing = section("Nothing", "B", chapter)
    becoming = section("Becoming", "C", chapter)
    unity = section("Unity of being and nothing", "1", becoming)
    moments = section("The moments of becoming", "2", becoming)
    sublation = section("Sublation of becoming", "3", becoming)
    remark = section("Remark 1", "1", unity)

    def child_sections(parent):
        children = [record for record in records.values()
                    if record.get("type") == "section" and record.get("parent_id") == parent["id"]]
        if any(type(record.get("order")) is not int for record in children):
            unsupported("child section source order is invalid")
        return sorted(children, key=lambda record: record["order"])

    if child_sections(chapter) != [being, nothing, becoming]:
        unsupported("chapter subdivisions are missing, additional, or reordered")
    if child_sections(becoming) != [unity, moments, sublation]:
        unsupported("Becoming subdivisions are missing, additional, or reordered")
    siblings = child_sections(quality)
    if siblings.index(chapter) + 1 >= len(siblings) or siblings[siblings.index(chapter) + 1] != following:
        unsupported("the following supplied chapter is not Existence")
    if not child_sections(unity) or child_sections(unity)[0] != remark:
        unsupported("the first supplied remark under Unity has changed")
    anchors = [objective, doctrine, quality, chapter, being, nothing, becoming, unity, remark, moments, sublation, following]
    if any(left["order"] >= right["order"] for left, right in zip(anchors, anchors[1:])):
        unsupported("supplied sections are not in their expected source order")

    def below(record, ancestor):
        seen = set()
        identifier = record.get("parent_id")
        while identifier is not None:
            if identifier in seen or identifier not in records or records[identifier].get("type") != "section":
                unsupported("source parent hierarchy is broken or cyclic")
            if identifier == ancestor["id"]:
                return True
            seen.add(identifier)
            identifier = records[identifier].get("parent_id")
        return False

    def readable(record):
        attr = record.get("attribution", {})
        return (record.get("type") in _READABLE and attr.get("author") == "G. W. F. Hegel"
                and attr.get("role") == "main_text")

    chapter_rows = [record for record in records.values() if readable(record) and below(record, chapter)]
    if not chapter_rows or any(type(row.get("order")) is not int for row in chapter_rows):
        unsupported("the chapter has no ordered reader text")
    chapter_rows.sort(key=lambda record: record["order"])
    if any(left["order"] >= right["order"] for left, right in zip(chapter_rows, chapter_rows[1:])):
        unsupported("chapter passages do not have distinct source positions")
    if any(not chapter["order"] < row["order"] < following["order"] for row in chapter_rows):
        unsupported("chapter text crosses its supplied source boundaries")
    for part in (being, nothing, unity, moments, sublation):
        if not any(below(row, part) for row in chapter_rows):
            unsupported(f"{part['title']} has no readable source passages")
    selected = chapter_rows if name == "beginning" else [row for row in chapter_rows
        if being["order"] < row["order"] < remark["order"]]
    if name == "opening":
        groups = {being["id"]: 0, nothing["id"]: 1, unity["id"]: 2}
        if any(row.get("parent_id") not in groups for row in selected):
            unsupported("the opening includes unexpected subdivisions before Remark 1")
        sequence = [groups[row["parent_id"]] for row in selected]
        if set(sequence) != {0, 1, 2} or sequence != sorted(sequence):
            unsupported("the opening does not preserve Being, Nothing, then Unity")
    if not 1 <= len(selected) <= 64:
        unsupported("the complete chosen extent is outside the 1..64 record research budget")

    by_id = {passage.identifier: (index, passage) for index, passage in enumerate(book.passages)}
    if len(by_id) != len(book.passages) or any(row["id"] not in by_id for row in chapter_rows):
        unsupported("the reader projection duplicates or omits chapter passages")
    chapter_indices = [by_id[row["id"]][0] for row in chapter_rows]
    if chapter_indices != list(range(chapter_indices[0], chapter_indices[0] + len(chapter_rows))):
        unsupported("the reader projection is not the contiguous supplied chapter sequence")
    indices = [by_id[row["id"]][0] for row in selected]
    if indices != list(range(indices[0], indices[0] + len(selected))):
        unsupported("the chosen reader extent is not contiguous")
    sample = sample_from_book(book, selected[0]["id"], len(selected))
    if [passage.identifier for passage in sample.passages] != [row["id"] for row in selected]:
        unsupported("reader and canonical source sequences disagree")
    # Existing reader guards validate text/digests/path/pages without changing
    # the sample actions, personal storage, or any canonical record.
    check = ReaderActions(book)
    for passage in sample.passages:
        check.open(passage.identifier)
        if passage.text:
            check.select_span(0, len(passage.text))

    note_ids = {identifier for row in selected for identifier in row.get("note_ids", [])}
    if any(identifier not in records or records[identifier].get("type") != "note" for identifier in note_ids):
        unsupported("a linked source note is unavailable")
    first, last = sample.passages[0], sample.passages[-1]
    snapshot = book.corpus_snapshot
    metadata = {"name": name, "title": "Being, Nothing, Becoming",
                "description": ("Complete first chapter, including its remarks and linked notes."
                                if name == "beginning" else "Opening development before Remark 1; not the complete Becoming section."),
                "source_section_id": chapter["id"], "start": first.identifier, "end": last.identifier,
                "sample_passages": len(sample.passages), "printed_pages": [first.printed_page, last.end_printed_page],
                "pdf_pages": [first.pdf_page, last.end_pdf_page], "linked_notes": len(note_ids),
                "source_review_passages": sum(passage.needs_source_review for passage in sample.passages),
                "includes_remarks": name == "beginning", "corpus_id": book.corpus_manifest.get("corpus_id"),
                "generation": None if snapshot is None else {"manifest_sha256": snapshot.manifest_sha256,
                                                              "index_sha256": snapshot.index_sha256}}
    return ReadingTrial(sample, metadata)
