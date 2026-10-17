"""Reusable invented corpora and source inspectors; no TestCase inheritance."""
from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile

from sol import core
from sol.core.corpus import load_corpus_book
from sol.corpus import contract
from sol.reader.actions import ReaderActions

_GENERATED = {"markdown", "plain_text", "document", "context", "content_sha256"}


def write_runtime_corpus(directory, *, pending_review=False):
    """Create a valid tiny index using stdlib only, without a source PDF."""
    import sol.corpus.contract as contract

    directory.mkdir(parents=True)
    section_id = "aaaaaaaa-0000-4000-8000-000000000001"
    passage_id = "bbbbbbbb-0000-4000-8000-000000000002"
    body = "An invented passage makes this installed research reader useful without extracting any PDF."
    common = {
        "sources": [{"pdf_page": 80, "printed_page": "7"}],
        "attribution": {"author": "G. W. F. Hegel", "role": "main_text", "status": "confirmed"},
        "reader_path": "/BEING/synthetic.txt", "reader_title": "Synthetic section",
    }
    section = {**common, "id": section_id, "type": "section", "parent_id": None,
               "order": 0, "title": "Synthetic section", "path": "/synthetic"}
    paragraph = {**common, "id": passage_id, "type": "paragraph",
                 "parent_id": section_id, "order": 1}
    if pending_review:
        paragraph["transcription_status"] = "needs_review"
    markdown = "\n".join((
        contract.render_record(section, "# Synthetic section"),
        contract.render_record(paragraph, body),
    ))
    (directory / "sample.md").write_text(markdown, encoding="utf-8")
    manifest = {
        "contract_version": 1, "edition": {"title": "Synthetic installed reader edition"},
        "source": {"filename": "absent.pdf", "sha256": "0" * 64, "pdf_pages": 80},
        "documents": ["sample.md"],
        "page_inventory": [
            {"pdf_page": page, "printed_page": None, "disposition": "blank",
             "reason": "Invented blank page"}
            for page in range(1, 80)
        ] + [{"pdf_page": 80, "printed_page": "7", "disposition": "records"}],
    }
    encoded_manifest = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    (directory / "corpus.json").write_bytes(encoded_manifest)
    records = [
        {**section, "document": "sample.md", "markdown": "# Synthetic section",
         "plain_text": "Synthetic section", "context": []},
        {**paragraph, "document": "sample.md", "markdown": body, "plain_text": body,
         "context": [{"id": section_id, "type": "section", "title": "Synthetic section",
                      "path": "/synthetic"}]},
    ]
    for record in records:
        record["content_sha256"] = hashlib.sha256(record["markdown"].encode("utf-8")).hexdigest()
    payload = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                      for record in records).encode("utf-8")
    (directory / "index.jsonl").write_bytes(payload)
    metadata = {
        "contract_version": 1,
        "manifest_sha256": hashlib.sha256(encoded_manifest).hexdigest(),
        "source_sha256": "0" * 64,
        "documents": {"sample.md": hashlib.sha256(markdown.encode("utf-8")).hexdigest()},
        "index_sha256": hashlib.sha256(payload).hexdigest(),
        "record_count": len(records),
    }
    (directory / "index.meta.json").write_text(json.dumps(metadata), encoding="utf-8")
    return passage_id, body


class _Document(HTMLParser):
    """Inspect generated syntax without interpreting corpus text as markup."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.blocks = []
        self.text = []
        self._active = None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        self.elements.append((tag, attributes))
        if tag in {"script", "style"}:
            self._active = [tag, attributes, ""]

    def handle_endtag(self, tag):
        if self._active is not None and self._active[0] == tag:
            self.blocks.append(tuple(self._active))
            self._active = None

    def handle_data(self, text):
        if self._active is not None:
            self._active[2] += text
        else:
            self.text.append(text)


class CorpusFixture:
    """Mix into a TestCase to obtain a disposable, verified local corpus."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-typeset-contract-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        self.identifier, self.body = write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.book = load_corpus_book(self.corpus)


    def rewrite_body(self, text, *, markdown=None):
        """Rebuild an internally exact tiny generation without optional parsers."""
        records = [json.loads(line) for line in
                   (self.corpus / "index.jsonl").read_text(encoding="utf-8").split("\n") if line.strip()]
        paragraph = next(row for row in records if row["id"] == self.identifier)
        paragraph.update(markdown=text if markdown is None else markdown, plain_text=text)
        self.body = text
        return self.write_records(records)


    def write_records(self, records):
        manifest_path = self.corpus / "corpus.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for record in records:
            record["content_sha256"] = hashlib.sha256(record["markdown"].encode()).hexdigest()
        document = "\n".join(contract.render_record(
            {key: value for key, value in row.items() if key not in _GENERATED}, row["markdown"])
            for row in records)
        (self.corpus / "sample.md").write_text(document, encoding="utf-8")
        index = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")) + "\n" for row in records).encode()
        (self.corpus / "index.jsonl").write_bytes(index)
        (self.corpus / "index.meta.json").write_text(json.dumps({
            "contract_version": 1,
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "source_sha256": manifest["source"]["sha256"],
            "documents": {"sample.md": hashlib.sha256(document.encode()).hexdigest()},
            "index_sha256": hashlib.sha256(index).hexdigest(), "record_count": len(records),
        }), encoding="utf-8")
        self.book = load_corpus_book(self.corpus)
        return self.book


    def add_note(self):
        """Retain a separately attributed note with an explicit reciprocal link."""
        records = [json.loads(line) for line in
                   (self.corpus / "index.jsonl").read_text(encoding="utf-8").split("\n") if line.strip()]
        paragraph = next(row for row in records if row["id"] == self.identifier)
        note_id = "cccccccc-0000-4000-8000-000000000003"
        paragraph["note_ids"] = [note_id]
        note = copy.deepcopy(paragraph)
        note.pop("note_ids")
        note.update(id=note_id, type="note", order=len(records), backlinks=[self.identifier],
                    attribution={"author": "Invented translator", "role": "editorial_note", "status": "confirmed"},
                    markdown="An invented note remains distinct from the philosophical prose.",
                    plain_text="An invented note remains distinct from the philosophical prose.")
        records.append(note)
        self.write_records(records)
        return note_id


    def packet(self, start=3, end=14, *, cursor=None):
        actions = ReaderActions(self.book)
        actions.open(self.identifier)
        selected = actions.select_span(start, end)
        return {"reference": core.capture_reference(self.book.corpus_snapshot, self.identifier),
                "selection": asdict(selected),
                "cursor_offset": end if cursor is None else cursor}


    def files(self):
        return {path.relative_to(self.root): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}


    def detach_reader_graph(self):
        """Keep snapshot/disk intact while replacing the mutable convenience view."""
        from dataclasses import replace
        self.book.canonical_records = copy.deepcopy(self.book.canonical_records)
        text = "A detached invented replacement not present in the verified source."
        record = self.book.canonical_records[self.identifier]
        record.update(markdown=text, plain_text=text,
                      content_sha256=hashlib.sha256(text.encode()).hexdigest())
        self.book.passages[0] = replace(self.book.passages[0], text=text)
