#!/usr/bin/env python3
"""SOL's canonical Markdown records and generated, PDF-independent JSONL index.

Markdown is parsed as CommonMark with markdown-it-py when generating an index,
not stripped with regular expressions. The original Markdown is always preserved.

Public API: new_id(), render_record(metadata, markdown), parse_document(text),
reindex(corpus_dir), load_index(corpus_dir), and plain_text(markdown). Editing text,
titles, or order never creates IDs: IDs belong to the canonical record markers.
Loading and verifying an existing index uses only Python's standard library;
reindexing additionally requires markdown-it-py. Nothing opens the source PDF.
"""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any
from urllib.parse import urlsplit
import uuid


CONTRACT_VERSION = 1
MANIFEST_FILENAME = "corpus.json"
INDEX_FILENAME = "index.jsonl"
INDEX_META_FILENAME = "index.meta.json"
_OPEN = re.compile(r"^<!-- sol:(.+) -->$")
_ANCHOR = re.compile(r'^<a id="([0-9a-f-]+)"></a>$')
_RESERVED = {"markdown", "plain_text", "document", "context", "content_sha256"}
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class CorpusError(ValueError):
    """Canonical content or its generated index fails the corpus contract."""


def new_id() -> str:
    """Allocate an opaque permanent ID once, when a canonical record is created."""
    return str(uuid.uuid4())


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CorpusError(f"Not valid JSON-compatible metadata: {exc}") from exc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise CorpusError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _decode_json(text: str, label: str) -> Any:
    def invalid_constant(value: str) -> None:
        raise CorpusError(f"Non-JSON numeric constant: {value}")

    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=invalid_constant)
    except (json.JSONDecodeError, CorpusError) as exc:
        raise CorpusError(f"Invalid JSON in {label}: {exc}") from exc


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_id(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _UUID.fullmatch(value):
        raise CorpusError(f"{label} must be a canonical lower-case UUID")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except ValueError as exc:
        raise CorpusError(f"{label} is not a valid UUID") from exc


def _validate_metadata(metadata: Any) -> None:
    if not isinstance(metadata, dict):
        raise CorpusError("Record metadata must be a JSON object")
    missing = {"id", "type", "parent_id", "order", "sources", "attribution"} - metadata.keys()
    if missing:
        raise CorpusError(f"Record is missing fields: {', '.join(sorted(missing))}")
    if _RESERVED & metadata.keys():
        raise CorpusError("Generated index fields may not appear in canonical metadata")
    _valid_id(metadata["id"], "Record id")
    if metadata["parent_id"] is not None:
        _valid_id(metadata["parent_id"], "parent_id")
    if not isinstance(metadata["type"], str) or not re.fullmatch(r"[a-z][a-z0-9_]*", metadata["type"]):
        raise CorpusError("Record type must be a lower-case extensible type name")
    if metadata["type"] == "retired_record" and "redirect_id" not in metadata:
        raise CorpusError("retired_record requires a canonical UUID redirect_id")
    if "redirect_id" in metadata:
        _valid_id(metadata["redirect_id"], "redirect_id")
    if not _is_int(metadata["order"]) or metadata["order"] < 0:
        raise CorpusError("Record order must be a nonnegative integer")
    if "random_eligible" in metadata and not isinstance(metadata["random_eligible"], bool):
        raise CorpusError("random_eligible must be a boolean")
    for field in ("title", "label", "path"):
        if field in metadata and not isinstance(metadata[field], str):
            raise CorpusError(f"{field} must be a string")
    attribution = metadata["attribution"]
    if not isinstance(attribution, dict) or not {"author", "status", "role"} <= attribution.keys():
        raise CorpusError("attribution requires author, status, and role")
    if attribution["author"] is not None and not isinstance(attribution["author"], str):
        raise CorpusError("attribution.author must be a string or null")
    if not all(isinstance(attribution[k], str) and attribution[k].strip() for k in ("status", "role")):
        raise CorpusError("attribution.status and attribution.role must be nonempty strings")
    sources = metadata["sources"]
    if not isinstance(sources, list) or not sources:
        raise CorpusError("Each record must have at least one source reference")
    seen_pages: set[int] = set()
    for source in sources:
        if not isinstance(source, dict) or not {"pdf_page", "printed_page"} <= source.keys():
            raise CorpusError("Each source reference requires pdf_page and printed_page")
        page = source["pdf_page"]
        if not _is_int(page) or page < 1:
            raise CorpusError("pdf_page must be a positive integer")
        if page in seen_pages:
            raise CorpusError("Duplicate PDF page within a record's source references")
        seen_pages.add(page)
        if source["printed_page"] is not None and not isinstance(source["printed_page"], str):
            raise CorpusError("printed_page must be a string or null (Roman labels remain strings)")
        if "bbox" in source:
            box = source["bbox"]
            if not isinstance(box, list) or len(box) != 4 or not all(
                isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) for n in box
            ):
                raise CorpusError("bbox must contain four finite PDF-point coordinates")
            if box[0] < 0 or box[1] < 0 or box[2] < box[0] or box[3] < box[1]:
                raise CorpusError("bbox coordinates must form a nonnegative rectangle")
    if [s["pdf_page"] for s in sources] != sorted(seen_pages):
        raise CorpusError("Source references must be in PDF-page order")
    for field in ("note_ids", "backlinks"):
        if field in metadata:
            if not isinstance(metadata[field], list):
                raise CorpusError(f"{field} must be a list of distinct IDs")
            for linked in metadata[field]:
                _valid_id(linked, field)
            if len(metadata[field]) != len(set(metadata[field])):
                raise CorpusError(f"{field} must be a list of distinct IDs")


def render_record(metadata: dict, markdown: str) -> str:
    """Serialize one record without allocating or modifying its permanent ID."""
    _validate_metadata(metadata)
    if not isinstance(markdown, str) or not markdown.strip():
        raise CorpusError("Record Markdown must be nonempty")
    if any(line == "<!-- /sol -->" or _OPEN.fullmatch(line) for line in markdown.splitlines()):
        raise CorpusError("Record Markdown may not contain nested SOL record delimiters")
    if metadata["type"] == "section" and not re.match(r"^#{1,6} +\S", markdown):
        raise CorpusError("Section Markdown must start with an ATX heading")
    # HTML comment delimiters must never be introduced by a metadata string.
    marker = _json(metadata).replace("--", r"\u002d\u002d")
    return f'<!-- sol:{marker} -->\n<a id="{metadata["id"]}"></a>\n\n{markdown.rstrip()}\n<!-- /sol -->\n'


class _VisibleHTML(HTMLParser):
    """Extract HTML's visible data without leaking anchors, tags, or comments."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0
        self.sup_hidden: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag == "sup":
            identifier = dict(attrs).get("data-sol-note")
            hide = isinstance(identifier, str) and _UUID.fullmatch(identifier) is not None
            self.sup_hidden.append(hide)
            if hide:
                self.hidden += 1
        if self.hidden:
            return
        if tag in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" ")
        elif tag == "img":
            self.parts.append(dict(attrs).get("alt") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        elif tag == "sup" and self.sup_hidden:
            if self.sup_hidden.pop():
                self.hidden -= 1
        elif not self.hidden and tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _html_plain(markup: str) -> str:
    parser = _VisibleHTML()
    parser.feed(markup)
    parser.close()
    return "".join(parser.parts)


def _commonmark_tokens(markdown: str) -> list:
    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:
        raise CorpusError("Reindexing requires markdown-it-py; install it with python3 -m pip install markdown-it-py") from exc
    return MarkdownIt("commonmark").parse(markdown)


def _note_annotations(tokens: list) -> set[str]:
    class Attributes(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.ids: set[str] = set()
            self.linked: set[str] = set()
            self.sup_ids: list[str | None] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = dict(attrs)
            if tag == "sup":
                identifier = values.get("data-sol-note")
                if "data-sol-note" in values:
                    _valid_id(identifier, "data-sol-note")
                    self.ids.add(identifier)
                self.sup_ids.append(identifier)

        def handle_endtag(self, tag: str) -> None:
            if tag == "sup" and self.sup_ids:
                self.sup_ids.pop()

    parser = Attributes()
    for token in tokens:
        if token.type in {"html_inline", "html_block"}:
            parser.feed(token.content)
        elif token.type == "inline":
            for child in token.children or []:
                if child.type == "html_inline":
                    parser.feed(child.content)
                elif child.type == "link_open":
                    active = next((identifier for identifier in reversed(parser.sup_ids) if identifier is not None), None)
                    if active is not None:
                        if urlsplit(child.attrGet("href") or "").fragment != active:
                            raise CorpusError(f"Annotated note {active} has a mismatched link destination")
                        parser.linked.add(active)
    parser.close()
    if any(identifier is not None for identifier in parser.sup_ids):
        raise CorpusError("Unclosed SOL-annotated note superscript")
    if parser.ids - parser.linked:
        raise CorpusError(f"Annotated note callouts require matching CommonMark links: {sorted(parser.ids - parser.linked)}")
    return parser.ids


def _plain_tokens(parsed_tokens: list) -> str:

    def inline(tokens: list) -> str:
        parts: list[str] = []
        markup = _VisibleHTML()
        for token in tokens:
            if token.type in {"text", "code_inline"}:
                if not markup.hidden:
                    parts.append(token.content)
            elif token.type in {"softbreak", "hardbreak"}:
                if not markup.hidden:
                    parts.append("\n")
            elif token.type == "image":
                if not markup.hidden:
                    parts.append(inline(token.children or []))
            elif token.type == "html_inline":
                markup.feed(token.content)
                parts.extend(markup.parts)
                markup.parts.clear()
        return "".join(parts)

    parts: list[str] = []
    for token in parsed_tokens:
        if token.type == "inline":
            parts.append(inline(token.children or []))
        elif token.type in {"fence", "code_block"}:
            parts.append(token.content.rstrip("\n") + "\n")
        elif token.type == "html_block":
            parts.append(_html_plain(token.content).strip("\n") + "\n")
        elif token.type in {"paragraph_close", "heading_close", "list_item_close"}:
            parts.append("\n")
    return re.sub(r"\n{3,}", "\n\n", "".join(parts)).strip()


def plain_text(markdown: str) -> str:
    """CommonMark visible text, omitting only SOL-annotated note callouts.

    Paragraph/list/quotation boundaries remain newlines, code remains literal,
    and presentational emphasis does not become artificial classifier tokens.
    Ordinary mathematical superscripts remain visible.
    """
    return _plain_tokens(_commonmark_tokens(markdown))


def parse_document(text: str, document: str = "") -> list[dict]:
    """Read canonical record markers; reject unindexed or malformed content."""
    records: list[dict] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        opened = _OPEN.fullmatch(lines[index])
        if not opened:
            raise CorpusError(f"{document or 'Markdown'}:{index+1}: content outside a SOL record")
        metadata = _decode_json(opened[1], f"{document}:{index+1}")
        _validate_metadata(metadata)
        index += 1
        if index >= len(lines) or not _ANCHOR.fullmatch(lines[index]):
            raise CorpusError(f"Record {metadata['id']} requires its visible UUID anchor")
        if _ANCHOR.fullmatch(lines[index])[1] != metadata["id"]:
            raise CorpusError(f"Record {metadata['id']} has a mismatched visible anchor")
        index += 1
        body: list[str] = []
        while index < len(lines) and lines[index] != "<!-- /sol -->":
            if _OPEN.fullmatch(lines[index]):
                raise CorpusError(f"Nested record or missing closing marker for {metadata['id']}")
            body.append(lines[index])
            index += 1
        if index == len(lines):
            raise CorpusError(f"Missing closing marker for {metadata['id']}")
        markdown = "\n".join(body).strip("\n")
        if not markdown.strip():
            raise CorpusError(f"Empty record {metadata['id']}")
        if metadata["type"] == "section" and not re.match(r"^#{1,6} +\S", markdown):
            raise CorpusError(f"Section {metadata['id']} must start with an ATX heading")
        tokens = _commonmark_tokens(markdown)
        unregistered = _note_annotations(tokens) - set(metadata.get("note_ids", []))
        if unregistered:
            raise CorpusError(f"Record {metadata['id']} has annotated note callouts absent from note_ids: {sorted(unregistered)}")
        records.append({**metadata, "markdown": markdown, "plain_text": _plain_tokens(tokens), "document": document})
        index += 1
    return records


def _safe_file(root: Path, relative: str, suffix: str | None = None) -> Path:
    if not isinstance(relative, str) or "\\" in relative:
        raise CorpusError("Document paths must be relative POSIX strings")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or not parts.parts or any(p in ("..", ".") for p in relative.split("/")):
        raise CorpusError(f"Unsafe corpus path: {relative!r}")
    if suffix and parts.suffix != suffix:
        raise CorpusError(f"Document path must end in {suffix}: {relative!r}")
    path = root.joinpath(*parts.parts)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise CorpusError(f"Corpus path escapes its directory: {relative!r}") from exc
    if path.is_symlink():
        raise CorpusError(f"Canonical documents may not be symlinks: {relative!r}")
    return path


def _read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CorpusError(f"Cannot read UTF-8 corpus file {path}: {exc}") from exc


def read_manifest(corpus_dir: Path | str) -> dict:
    """Read and validate the declared edition, document list, and page inventory."""
    root = Path(corpus_dir)
    manifest = _decode_json(_read_utf8(root / MANIFEST_FILENAME), MANIFEST_FILENAME)
    if not isinstance(manifest, dict) or not _is_int(manifest.get("contract_version")) or manifest["contract_version"] != CONTRACT_VERSION:
        raise CorpusError(f"Unsupported corpus contract; expected version {CONTRACT_VERSION}")
    if not isinstance(manifest.get("edition"), dict) or not manifest["edition"]:
        raise CorpusError("Manifest requires nonempty edition metadata")
    source = manifest.get("source")
    if not isinstance(source, dict) or not {"filename", "sha256", "pdf_pages"} <= source.keys():
        raise CorpusError("Manifest source requires filename, sha256, and pdf_pages")
    if not isinstance(source["filename"], str) or not source["filename"]:
        raise CorpusError("Manifest source filename must be nonempty")
    if not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
        raise CorpusError("Manifest source sha256 must be a lowercase SHA-256 fingerprint")
    if not _is_int(source["pdf_pages"]) or source["pdf_pages"] < 1:
        raise CorpusError("Manifest source pdf_pages must be a positive integer")
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents or not all(isinstance(d, str) for d in documents):
        raise CorpusError("Manifest documents must be a nonempty list of relative Markdown paths")
    if len(set(documents)) != len(documents):
        raise CorpusError("Manifest repeats a document path")
    for document in documents:
        _safe_file(root, document, ".md")
    inventory = manifest.get("page_inventory")
    if not isinstance(inventory, list) or len(inventory) != source["pdf_pages"]:
        raise CorpusError("page_inventory must account for every source PDF page")
    pages: set[int] = set()
    for entry in inventory:
        if not isinstance(entry, dict) or not {"pdf_page", "printed_page", "disposition"} <= entry.keys():
            raise CorpusError("Inventory entries require pdf_page, printed_page, and disposition")
        page = entry["pdf_page"]
        if not _is_int(page) or page < 1 or page > source["pdf_pages"] or page in pages:
            raise CorpusError("page_inventory contains an invalid or duplicate PDF page")
        pages.add(page)
        if entry["printed_page"] is not None and not isinstance(entry["printed_page"], str):
            raise CorpusError("Inventory printed_page must be a string or null")
        if entry["disposition"] not in {"records", "blank", "excluded"}:
            raise CorpusError("Inventory disposition must be records, blank, or excluded")
        if entry["disposition"] != "records" and not isinstance(entry.get("reason"), str):
            raise CorpusError("Blank/excluded inventory pages require a reason")
    return manifest


def validate_records(records: list[dict], manifest: dict) -> None:
    """Validate relationships and exact source coverage before indexing."""
    by_id: dict[str, dict] = {}
    orders: set[int] = set()
    inventory = {entry["pdf_page"]: entry for entry in manifest["page_inventory"]}
    covered: set[int] = set()
    document_orders: dict[str, int] = {}
    for record in records:
        metadata = {k: v for k, v in record.items() if k not in _RESERVED}
        _validate_metadata(metadata)
        if record["id"] in by_id:
            raise CorpusError(f"Duplicate permanent ID: {record['id']}")
        by_id[record["id"]] = record
        if record["order"] in orders:
            raise CorpusError(f"Duplicate global order: {record['order']}")
        orders.add(record["order"])
        document = record.get("document", "")
        if record["order"] <= document_orders.get(document, -1):
            raise CorpusError(f"Records in {document} are not in increasing source order")
        document_orders[document] = record["order"]
        for source in record["sources"]:
            page = source["pdf_page"]
            if page not in inventory or inventory[page]["disposition"] != "records":
                raise CorpusError(f"Record {record['id']} cites an absent, blank, or excluded page {page}")
            if source["printed_page"] != inventory[page]["printed_page"]:
                raise CorpusError(f"Printed-page provenance disagrees with inventory on PDF page {page}")
            covered.add(page)
    missing = {p for p, entry in inventory.items() if entry["disposition"] == "records"} - covered
    if missing:
        raise CorpusError(f"Source pages declared as records have no content: {sorted(missing)}")
    for record in records:
        parent = record["parent_id"]
        if parent is not None and parent not in by_id:
            raise CorpusError(f"Missing parent {parent} for record {record['id']}")
        visited = {record["id"]}
        ancestor = parent
        while ancestor is not None:
            if ancestor in visited:
                raise CorpusError(f"Parent cycle involving {record['id']}")
            visited.add(ancestor)
            ancestor = by_id[ancestor]["parent_id"]
            if ancestor is not None and ancestor not in by_id:
                raise CorpusError(f"Missing ancestor {ancestor}")
        if parent is not None and by_id[parent]["order"] >= record["order"]:
            raise CorpusError(f"Parent must precede child in source order: {record['id']}")
        redirected = record.get("redirect_id")
        seen_redirects = {record["id"]}
        while redirected is not None:
            if redirected not in by_id:
                raise CorpusError(f"Missing redirect target {redirected} on record {record['id']}")
            if redirected in seen_redirects:
                raise CorpusError(f"Redirect cycle or self-redirect involving {record['id']}")
            seen_redirects.add(redirected)
            redirected = by_id[redirected].get("redirect_id")
        for linked in record.get("note_ids", []):
            if linked not in by_id or by_id[linked]["type"] != "note":
                raise CorpusError(f"Broken note link {linked} on record {record['id']}")
            if record["id"] not in by_id[linked].get("backlinks", []):
                raise CorpusError(f"Note {linked} is missing backlink to {record['id']}")
        for backlink in record.get("backlinks", []):
            if backlink not in by_id or record["id"] not in by_id[backlink].get("note_ids", []):
                raise CorpusError(f"Broken reciprocal backlink {backlink} on {record['id']}")


def _canonical_files(root: Path, manifest: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Read declared documents and hashes without needing a Markdown dependency."""
    documents = set(manifest["documents"])
    # Removing a file from the manifest must not silently remove canonical content.
    for path in root.rglob("*.md"):
        relative = path.relative_to(root).as_posix()
        if relative not in documents and re.search(r"^<!-- sol:", _read_utf8(_safe_file(root, relative, ".md")), re.M):
            raise CorpusError(f"Canonical Markdown is missing from manifest: {relative}")
    fingerprints: dict[str, str] = {}
    contents: dict[str, str] = {}
    for document in manifest["documents"]:
        path = _safe_file(root, document, ".md")
        content = _read_utf8(path)
        fingerprints[document] = _sha(content.encode("utf-8"))
        contents[document] = content
    return contents, fingerprints


def _read_canonical(root: Path) -> tuple[dict, list[dict], dict[str, str]]:
    manifest = read_manifest(root)
    contents, fingerprints = _canonical_files(root, manifest)
    records: list[dict] = []
    for document, content in contents.items():
        parsed = parse_document(content, document)
        if not parsed:
            raise CorpusError(f"Declared canonical document is empty: {document}")
        records.extend(parsed)
    validate_records(records, manifest)
    records.sort(key=lambda item: item["order"])
    by_id = {record["id"]: record for record in records}
    for record in records:
        ancestors: list[dict] = []
        parent = record["parent_id"]
        while parent is not None:
            ancestors.append(by_id[parent])
            parent = by_id[parent]["parent_id"]
        ancestors.reverse()
        record["context"] = [
            {"id": ancestor["id"], "type": ancestor["type"], "title": ancestor.get("title"), "path": ancestor.get("path")}
            for ancestor in ancestors
        ]
        record["content_sha256"] = _sha(record["markdown"].encode("utf-8"))
    return manifest, records, fingerprints


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def reindex(corpus_dir: Path | str, output: Path | str | None = None) -> dict:
    """Validate canonical Markdown and atomically regenerate the JSONL index.

    This never reads the PDF. The companion metadata is committed last; an interrupted
    pair of writes is detected by load_index's digest check rather than used silently.
    """
    root = Path(corpus_dir)
    manifest, records, fingerprints = _read_canonical(root)
    target = Path(output) if output is not None else root / INDEX_FILENAME
    if target.suffix != ".jsonl":
        raise CorpusError("Index output must have a .jsonl extension")
    metadata_target = target.with_suffix(".meta.json")
    payload = "".join(_json(record) + "\n" for record in records).encode("utf-8")
    metadata = {
        "contract_version": CONTRACT_VERSION,
        "manifest_sha256": _sha((root / MANIFEST_FILENAME).read_bytes()),
        "source_sha256": manifest["source"]["sha256"],
        "documents": fingerprints,
        "index_sha256": _sha(payload),
        "record_count": len(records),
    }
    _atomic_write(target, payload)
    _atomic_write(metadata_target, (_json(metadata) + "\n").encode("utf-8"))
    return {"records": len(records), "documents": len(fingerprints), "index": str(target), "metadata": str(metadata_target)}


def load_index(corpus_dir: Path | str, verify: bool = True, index: Path | str | None = None) -> list[dict]:
    """Load derived JSONL, refusing stale/tampered indexes by default (no PDF I/O)."""
    root = Path(corpus_dir)
    target = Path(index) if index is not None else root / INDEX_FILENAME
    content = _read_utf8(target)
    records = [_decode_json(line, f"{target}:{i+1}") for i, line in enumerate(content.splitlines()) if line.strip()]
    if verify:
        metadata = _decode_json(_read_utf8(target.with_suffix(".meta.json")), "index metadata")
        if not isinstance(metadata, dict) or metadata.get("contract_version") != CONTRACT_VERSION:
            raise CorpusError("Unsupported generated-index metadata")
        if metadata.get("index_sha256") != _sha(content.encode("utf-8")):
            raise CorpusError("Generated index was changed or incompletely written; reindex required")
        manifest = read_manifest(root)
        _, fingerprints = _canonical_files(root, manifest)
        if metadata.get("manifest_sha256") != _sha((root / MANIFEST_FILENAME).read_bytes()):
            raise CorpusError("Corpus manifest changed; reindex required")
        if metadata.get("source_sha256") != manifest["source"]["sha256"] or metadata.get("documents") != fingerprints:
            raise CorpusError("Canonical Markdown or source fingerprint changed; reindex required")
        if metadata.get("record_count") != len(records):
            raise CorpusError("Generated index record count disagrees with canonical content")
        if not all(isinstance(record, dict) for record in records):
            raise CorpusError("Generated index records must be JSON objects")
        validate_records(records, manifest)
        if [record["order"] for record in records] != sorted(record["order"] for record in records):
            raise CorpusError("Generated index is not in source order")
        for record in records:
            if not isinstance(record.get("markdown"), str) or not isinstance(record.get("plain_text"), str):
                raise CorpusError("Generated records require Markdown and plain text")
            if record.get("content_sha256") != _sha(record["markdown"].encode("utf-8")):
                raise CorpusError("Generated record content digest is invalid")
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SOL canonical Markdown and rebuild its PDF-independent JSONL index.")
    parser.add_argument("corpus", type=Path, help="directory containing corpus.json and canonical Markdown")
    parser.add_argument("--check", action="store_true", help="validate the existing index without modifying it")
    args = parser.parse_args(argv)
    try:
        if args.check:
            records = load_index(args.corpus)
            print(f"Validated {len(records)} indexed records.")
        else:
            summary = reindex(args.corpus)
            print(f"Indexed {summary['records']} records from {summary['documents']} Markdown documents.")
    except CorpusError as exc:
        parser.exit(2, f"sol corpus: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
