"""Derived inquiry reports over one loaded book and one workspace export.

This module performs no I/O and does not import the reader, SQLite, PDF, or UI
layers. Markdown reports are human-facing, noncanonical views, not backups or
an import format. Personal and optional canonical Markdown remains literal code
inside adaptive fences; it is never interpreted as report structure.
"""
from __future__ import annotations

import json
import re
import unicodedata


FORMAT_VERSION = 1
_COLLECTIONS = ("history", "bookmarks", "annotations", "comparisons", "reviews",
                "relations", "annotation_history")
_BIDI = {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}
_PENDING = {"needs_review", "needs_visual_review"}


def _safe_text(value: str, *, multiline=False) -> str:
    """Neutralize terminal/Bidi controls, leaving valid Unicode prose intact."""
    safe = []
    for character in value:
        code = ord(character)
        if character in "\n\t" and multiline:
            safe.append(character)
        elif character == "\n":
            safe.append(r"\n")
        elif character == "\t":
            safe.append(r"\t")
        elif unicodedata.bidirectional(character) in _BIDI or unicodedata.category(character) == "Cs":
            safe.append(f"\\u{code:04x}")
        elif code < 32 or 127 <= code <= 159:
            safe.append(f"\\x{code:02x}")
        else:
            safe.append(character)
    return "".join(safe)


def _metadata_text(value) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    elif value is None:
        value = "null (not recorded)"
    else:
        value = str(value)
    return _safe_text(value)


def _literal(value) -> str:
    """Escape arbitrary labels, including punctuation used by GFM autolinks."""
    return ''.join('\\' + character if 32 < ord(character) < 127 and not character.isalnum()
                   else character for character in _metadata_text(value))


def _code(value) -> str:
    """Copyable one-line metadata, never an active URL, image, or raw HTML."""
    body = _metadata_text(value)
    if not body:
        return '`"" (empty string)`'
    length = max((len(run) for run in re.findall(r'`+', body)), default=0)
    delimiter = '`' * max(1, length + 1)
    # CommonMark trims one surrounding ASCII space from nonblank code spans.
    # Padding separates edge backticks from the delimiter and preserves spaces.
    padding = ' ' if body.strip(' ') and (body.startswith(('`', ' ')) or body.endswith(('`', ' '))) else ''
    return delimiter + padding + body + padding + delimiter


def _block(body: str) -> str:
    if not isinstance(body, str):
        raise ValueError("saved and canonical Markdown must be strings")
    body = _safe_text(body, multiline=True)
    length = max((len(run) for run in re.findall(r"`+", body)), default=0)
    fence = "`" * max(3, length + 1)
    # The separator before the closing fence is framing, not a body correction.
    return fence + "markdown\n" + body + ("" if body.endswith("\n") else "\n") + fence


def _field(lines: list[str], label: str, value) -> None:
    lines.append("* " + _literal(label) + ": " + _code(value))


def _fields(lines: list[str], row: dict, *, omit=()) -> None:
    for key, value in row.items():
        if key not in omit:
            _field(lines, str(key).replace("_", " "), value)


def _resolve(records: dict, identifier: str) -> dict:
    result = {"requested_id": identifier, "resolved_id": None, "chain": [],
              "status": "unresolved", "reason": "No exact canonical record with this ID.",
              "record": None}
    if not isinstance(identifier, str):
        raise ValueError("workspace reference identifiers must be strings")
    current = identifier
    while current in records:
        if current in result["chain"]:
            result["reason"] = "Invalid retirement redirect: cycle."
            return result
        result["chain"].append(current)
        record = records[current]
        if record.get("type") != "retired_record":
            result.update(resolved_id=current, record=record,
                          status="retired / explicitly redirected" if len(result["chain"]) > 1 else "live",
                          reason="Explicit retirement chain retained." if len(result["chain"]) > 1 else "")
            return result
        target = record.get("redirect_id")
        if not isinstance(target, str):
            result["reason"] = "Invalid retirement redirect: missing target ID."
            return result
        current = target
    if result["chain"]:
        result["chain"].append(current)
        result["reason"] = "Retired reference has an unresolved explicit redirect target."
    return result


def _binding(reference: dict, row: dict, source_sha: str, *, review=False) -> str:
    record = reference["record"]
    if record is None:
        return "UNRESOLVED target; no current-version comparison possible"
    if len(reference["chain"]) > 1:
        return "RETIRED target; redirected current text is not the inspected source snapshot"
    digest = row.get("content_sha256")
    if not digest or (review and not row.get("source_sha256")):
        return "UNVERSIONED; inspected source digest was not recorded"
    current_digest = record.get("content_sha256")
    same_text = isinstance(current_digest, str) and digest.lower() == current_digest.lower()
    same_source = not review or (isinstance(row.get("source_sha256"), str)
                                 and row["source_sha256"].lower() == source_sha.lower())
    if not same_text or not same_source:
        return "STALE; loaded text or declared PDF fingerprint differs from inspected version"
    if review:
        return "Same text/PDF fingerprints only; PDF hash is manifest-declared, metadata is not bound"
    return "Same loaded Markdown digest only; source-location and attribution metadata is not bound"


def _validate(book, snapshot: dict) -> tuple[dict, dict]:
    if not isinstance(snapshot, dict) or snapshot.get("format") != "sol-workspace":
        raise ValueError("a single SOL workspace export snapshot is required")
    manifest = getattr(book, "corpus_manifest", None)
    records = getattr(book, "canonical_records", None)
    if not isinstance(manifest, dict) or not isinstance(records, dict):
        raise ValueError("a loaded canonical book is required")
    corpus_id = manifest.get("corpus_id")
    if not isinstance(corpus_id, str) or not corpus_id or snapshot.get("corpus_id") != corpus_id:
        raise ValueError("workspace and loaded book corpus identities do not match")
    provenance = snapshot.get("provenance")
    source = manifest.get("source")
    if not isinstance(provenance, dict) or not isinstance(source, dict):
        raise ValueError("workspace and book require source provenance")
    saved_source = provenance.get("source")
    digest = source.get("sha256")
    nested_digest = saved_source.get("sha256") if isinstance(saved_source, dict) else None
    direct_digest = provenance.get("source_sha256")
    def fingerprint(value):
        return value.lower() if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) else None
    saved_digest = direct_digest if direct_digest is not None else nested_digest
    if (fingerprint(digest) is None or fingerprint(saved_digest) != fingerprint(digest)
            or (nested_digest is not None and fingerprint(nested_digest) != fingerprint(digest))):
        raise ValueError("workspace and loaded book source fingerprints do not match")
    if snapshot.get("schema_version") not in (1, 2) or type(snapshot.get("schema_version")) is not int:
        raise ValueError("unsupported workspace snapshot schema version")
    for name in _COLLECTIONS:
        values = snapshot.get(name, [])
        if not isinstance(values, list) or not all(isinstance(row, dict) for row in values):
            raise ValueError(f"workspace {name} must be a list of records")
    if snapshot.get("state") is not None and not isinstance(snapshot["state"], dict):
        raise ValueError("workspace state must be a record or null")
    if snapshot["schema_version"] == 1 and snapshot.get("annotation_history"):
        raise ValueError("version-1 workspaces do not have audited annotation history")
    return manifest, records


def render_workspace_markdown(book, snapshot, *, workspace_name,
                              include_passages=False, freshness=None) -> str:
    """Render a deterministic, nonmutating inquiry report without any I/O.

    `freshness` is a caller-supplied diagnostic, not a verification performed by
    this renderer. Optional excerpts use only CURRENT loaded canonical Markdown.
    They do not reconstruct historical text from saved content digests.
    """
    manifest, records = _validate(book, snapshot)
    if type(include_passages) is not bool:
        raise ValueError("include_passages must be a boolean")
    if freshness is not None and not isinstance(freshness, dict):
        raise ValueError("freshness must be a supplied diagnostic object or null")
    source_sha = manifest["source"]["sha256"]
    references = {}

    def remember(identifier):
        if identifier is None:
            return None
        if identifier not in references:
            references[identifier] = _resolve(records, identifier)
        return references[identifier]

    lines = ["# SOL inquiry report", "", "Derived, noncanonical, human-readable report. "
             "Not re-importable and not a backup. The portable JSON workspace export remains "
             "the authoritative machine-readable representation.", "",
             "Private inquiry: this report contains actor labels and personal work. "
             "Review its contents before sharing.", "", "## Snapshot basis", ""]
    _field(lines, "Report format", "sol-workspace-markdown")
    _field(lines, "Report format version", FORMAT_VERSION)
    _field(lines, "Workspace", workspace_name)
    _field(lines, "Workspace schema version", snapshot["schema_version"])
    _field(lines, "Workspace created", snapshot.get("created_at"))
    _field(lines, "Workspace exported", snapshot.get("exported_at"))
    _field(lines, "Corpus ID", manifest["corpus_id"])
    _field(lines, "Loaded edition metadata", manifest.get("edition"))
    _field(lines, "Loaded source metadata", manifest["source"])
    _field(lines, "Saved workspace provenance", snapshot["provenance"])
    loaded_snapshot = getattr(book, "corpus_snapshot", None)
    if loaded_snapshot is not None:
        for name in ("manifest_sha256", "index_sha256", "index_metadata_sha256"):
            value = getattr(loaded_snapshot, name, None)
            if value is not None:
                _field(lines, "Loaded " + name.replace("_", " "), value)
        documents = getattr(loaded_snapshot, 'documents', None)
        if isinstance(documents, dict):
            _field(lines, 'Loaded corpus document count', len(documents))
    _field(lines, "Supplied corpus freshness diagnostic", freshness or {"state": "unknown"})
    if freshness and freshness.get("state") == "changed":
        lines.extend(["", "WARNING: the supplied diagnostic reports corpus-file drift. "
                      "This report still describes the already loaded corpus snapshot; reopen "
                      "SOL after reviewing and reindexing changes."])
    lines.extend(["", "Basis: one workspace export at its recorded export time, plus the already "
                  "loaded canonical corpus. This renderer reads no files. PDF bytes are NOT "
                  "verified; the source fingerprint is manifest-declared. A supplied current "
                  "freshness diagnostic concerns corpus/index files, not PDF verification.", "",
                  "Personal and optional canonical Markdown is shown literally in fenced blocks. "
                  "Fences are presentation framing; content is not rendered, executed, corrected, "
                  "or interpreted as report structure. Valid Unicode and meaningful line breaks "
                  "are retained; terminal and bidirectional controls are shown as literal escapes.",
                  "", "## Reading continuity", ""])
    state = snapshot.get("state")
    if state is None:
        lines.append("No saved reading position.")
    else:
        _fields(lines, state)
        remember(state.get("current_id"))
    lines.extend(["", "### Saved checkpoint history", ""])
    for index, row in enumerate(snapshot.get("history", []), 1):
        lines.extend([f"#### Checkpoint {index}", ""])
        _fields(lines, row)
        remember(row.get("current_id"))
        lines.append("")
    if not snapshot.get("history"):
        lines.append("No saved checkpoints.")

    lines.extend(["", "## Bookmarks", ""])
    for index, row in enumerate(snapshot.get("bookmarks", []), 1):
        lines.extend([f"### Bookmark {index}", ""])
        _fields(lines, row)
        remember(row.get("target_id"))
        lines.append("")
    if not snapshot.get("bookmarks"):
        lines.append("No bookmarks.")

    lines.extend(["", "## Personal annotations", "",
                  "Authorship below is the original personal-note attribution, not Hegel's prose. "
                  "A text-digest match does not certify current source coordinates or attribution.", ""])
    histories = snapshot.get("annotation_history", [])
    for index, row in enumerate(snapshot.get("annotations", []), 1):
        lines.extend([f"### Annotation {index}", ""])
        _fields(lines, row, omit=("body",))
        reference = remember(row.get("target_id"))
        if reference:
            _field(lines, "Original source binding status", _binding(reference, row, source_sha))
        lines.extend(["", "Current saved personal body:", "", _block(row.get("body", "")), ""])
        if snapshot["schema_version"] == 1:
            lines.append("Version-1 workspace: no audited revision history exists; none is invented.")
        else:
            revisions = [revision for revision in histories if revision.get("annotation_id") == row.get("id")]
            for revision in revisions:
                lines.extend(["", "#### Stored personal revision", ""])
                _fields(lines, revision, omit=("body",))
                remember(revision.get("target_id"))
                lines.extend(["", _block(revision.get("body", "")), ""])
            if not revisions:
                lines.append("No stored revision snapshots were supplied for this annotation.")
    # Valid Workspace exports have no orphans; preserve any supplied audit rows
    # rather than silently losing them in an independently constructed snapshot.
    annotation_ids = {row.get("id") for row in snapshot.get("annotations", [])}
    for revision in histories:
        if revision.get("annotation_id") not in annotation_ids:
            lines.extend(["", "### Unmatched stored personal revision", ""])
            _fields(lines, revision, omit=("body",))
            remember(revision.get("target_id"))
            lines.extend(["", _block(revision.get("body", "")), ""])
    if not snapshot.get("annotations") and not histories:
        lines.append("No personal annotations.")

    lines.extend(["", "## Ordered comparisons", ""])
    for index, row in enumerate(snapshot.get("comparisons", []), 1):
        lines.extend([f"### Comparison {index}", ""])
        _fields(lines, row, omit=("question", "target_ids"))
        targets = row.get("target_ids", [])
        if not isinstance(targets, list):
            raise ValueError("comparison target_ids must be an ordered list")
        for position, identifier in enumerate(targets, 1):
            _field(lines, f"Passage {position}", identifier)
            remember(identifier)
        lines.extend(["", "Personal question:", "", _block(row.get("question", "")), ""])
    if not snapshot.get("comparisons"):
        lines.append("No comparisons.")

    lines.extend(["", "## Append-only reader review testimony", "",
                  "Reader testimony is not canonical verification. Its limited binding covers "
                  "the inspected Markdown digest and manifest-declared PDF fingerprint only. "
                  "It does not bind source coordinates, attribution, headings, or the full corpus, "
                  "and never clears canonical pending-review flags.", ""])
    for index, row in enumerate(snapshot.get("reviews", []), 1):
        lines.extend([f"### Testimony {index}", ""])
        _fields(lines, row, omit=("issue",))
        reference = remember(row.get("target_id"))
        if reference:
            _field(lines, "Limited binding status", _binding(reference, row, source_sha, review=True))
        lines.extend(["", "Personal inspection testimony:", "", _block(row.get("issue", "")), ""])
    if not snapshot.get("reviews"):
        lines.append("No reader testimony.")

    lines.extend(["", "## Directed reader-asserted relations", "",
                  "These attributed assertions are outside the published book tree; direction "
                  "and rationale are preserved, not inferred philosophical equivalences.", ""])
    for index, row in enumerate(snapshot.get("relations", []), 1):
        lines.extend([f"### Relation {index}", ""])
        _fields(lines, row, omit=("rationale",))
        remember(row.get("source_id"))
        remember(row.get("target_id"))
        lines.extend(["", "Personal rationale:", "", _block(row.get("rationale", "")), ""])
    if not snapshot.get("relations"):
        lines.append("No reader-asserted relations.")

    lines.extend(["", "## Referenced-record appendix", "",
                  "Deduplicated by the full requested ID, in first-reference order. No prefix, "
                  "similarity, or fuzzy repair is attempted. Metadata describes the CURRENT "
                  "loaded record, not a historical source snapshot.", ""])
    excerpted = set()
    for index, reference in enumerate(references.values(), 1):
        lines.extend([f"### Reference {index}", ""])
        _field(lines, "Requested ID", reference["requested_id"])
        _field(lines, "Resolved ID", reference["resolved_id"])
        _field(lines, "Redirect chain", reference["chain"])
        _field(lines, "Reference status", reference["status"])
        if reference["reason"]:
            _field(lines, "Resolution note", reference["reason"])
        record = reference["record"]
        if record is None:
            lines.extend(["", "No canonical excerpt is available for this unresolved reference.", ""])
            continue
        _field(lines, "Record type", record.get("type"))
        _field(lines, "Heading", record.get("reader_title") or record.get("heading") or record.get("title"))
        _field(lines, "Virtual path", record.get("reader_path") or record.get("path"))
        _field(lines, "Current attribution", record.get("attribution"))
        _field(lines, "All source references (printed/PDF pages)", record.get("sources", []))
        _field(lines, "Current Markdown SHA256", record.get("content_sha256"))
        status = record.get("transcription_status")
        _field(lines, "Canonical transcription status", status)
        _field(lines, "Canonical pending review", status in _PENDING)
        _field(lines, "Canonical document", record.get("document"))
        documents = getattr(loaded_snapshot, 'documents', None)
        if isinstance(documents, dict):
            _field(lines, 'Loaded canonical document SHA256', documents.get(record.get('document')))
        for name in ("parent_id", "order", "random_eligible", "note_ids", "backlinks"):
            if name in record:
                _field(lines, name.replace("_", " "), record[name])
        if include_passages:
            if reference["resolved_id"] in excerpted:
                lines.extend(["", "Current canonical Markdown is included once under an earlier "
                              "reference resolving to this same ID."])
            elif isinstance(record.get("markdown"), str):
                excerpted.add(reference["resolved_id"])
                _field(lines, "Requested IDs resolving to this excerpt", [item["requested_id"] for item in references.values()
                                                                        if item["resolved_id"] == reference["resolved_id"]])
                lines.extend(["", "CURRENT loaded canonical Markdown, with the attribution above. "
                              "Not the historically inspected text; personal binding statuses remain separate.",
                              "", _block(record["markdown"])])
            else:
                lines.extend(["", "This canonical record has no supplied Markdown excerpt."])
        lines.append("")
    if not references:
        lines.append("No saved canonical references.")
    if not include_passages:
        lines.extend(["", "Canonical passage bodies were not included. Enable include-passages "
                      "explicitly to include only the referenced current records, never the full book."])
    return "\n".join(lines).rstrip("\n") + "\n"
