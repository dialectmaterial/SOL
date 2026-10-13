"""Pinned comparison cards from one coherent, read-only workspace export.

The result is a disposable presentation snapshot, not a new comparison format or
workspace backup. It never changes a cursor, annotation, review, or canonical
record. Missing references stay visible; explicit retirement chains stay intact.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import posixpath
import shlex
from types import SimpleNamespace

from sol.corpus.contract import CorpusSnapshot, verify_snapshot_current
from sol.core.paths import resolve_path as resolve_book_path
from sol.core.references import resolve_reference
from sol.workspace.store import _source_fingerprint


class ComparisonError(ValueError):
    """A comparison cannot be captured coherently from the selected inquiry."""


def _metadata_digest(record):
    metadata = {key: value for key, value in record.items()
                if key not in {"markdown", "plain_text"}}
    payload = json.dumps(metadata, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _guard(reader):
    reader.ensure_corpus_current()
    snapshot = getattr(reader.book, "corpus_snapshot", None)
    if isinstance(snapshot, CorpusSnapshot):
        # Do not depend on a particular interface's freshness implementation.
        # The contract guard also protects captures made by other adapters.
        verify_snapshot_current(snapshot)


def _corpus_info(book):
    manifest = getattr(book, "corpus_manifest", {})
    snapshot = getattr(book, "corpus_snapshot", None)
    if isinstance(snapshot, CorpusSnapshot):
        generation = {
            "state": "current", "manifest_sha256": snapshot.manifest_sha256,
            "index_sha256": snapshot.index_sha256,
            "index_metadata_sha256": snapshot.index_metadata_sha256,
            "documents": deepcopy(snapshot.documents),
        }
    else:
        generation = {"state": "unknown", "manifest_sha256": None,
                      "index_sha256": None, "index_metadata_sha256": None,
                      "documents": {}, "reason": "No verified filesystem generation was retained."}
    directory = getattr(book, "corpus_directory", None)
    return {"id": manifest.get("corpus_id"), "edition": deepcopy(manifest.get("edition", {})),
            "source": deepcopy(manifest.get("source", {})),
            "source_verification": "manifest_declared_only",
            "directory": str(directory) if directory is not None else None,
            "generation": generation}


def _known_chain(book, identifier):
    """Retain only explicit known redirect steps when normal resolution failed."""
    chain, current = [], identifier
    while isinstance(current, str) and current not in chain:
        chain.append(current)
        record = book.canonical_records.get(current)
        if not isinstance(record, dict) or record.get("type") != "retired_record":
            break
        target = record.get("redirect_id")
        if target in chain:
            chain.append(target)
            break
        current = target
    return chain


def _card(book, identifier, position):
    card = {
        "position": position, "requested_id": identifier, "target_id": None,
        "redirect_chain": [], "state": "unresolved", "reason": "",
        "title": "Unresolved canonical reference", "path": None, "type": None,
        "document": None, "plain_text": "", "markdown": "", "attribution": None,
        "sources": [], "content_sha256": None, "metadata_sha256": None,
        "transcription_status": None, "notes": [],
        "text_basis": "loaded_canonical_record_at_capture",
    }
    try:
        reference = resolve_reference(book, identifier)
    except (ValueError, KeyError, TypeError) as error:
        card["reason"] = str(error)
        card["redirect_chain"] = _known_chain(book, identifier)
        return card
    record = reference.record
    retired = len(reference.chain) > 1
    card.update({
        "requested_id": reference.requested_id, "target_id": reference.target_id,
        "redirect_chain": list(reference.chain), "state": "retired" if retired else "live",
        "reason": "Canonical reference retired; its explicit redirect is retained." if retired else "",
        "title": record.get("reader_title") or record.get("heading") or record.get("title") or record["type"],
        "path": record.get("reader_path") or record.get("path"), "type": record["type"],
        "document": record.get("document"), "plain_text": record.get("plain_text", ""),
        "markdown": record.get("markdown", ""), "attribution": deepcopy(record.get("attribution")),
        "sources": deepcopy(record.get("sources", [])), "content_sha256": record.get("content_sha256"),
        "metadata_sha256": _metadata_digest(record),
        "transcription_status": record.get("transcription_status"),
    })
    return card


def _note(book, annotation):
    note = deepcopy(annotation)
    note.update({"resolved_target_id": None, "redirect_chain": [],
                 "revision": annotation.get("revision"),
                 "revision_audit": "legacy" if annotation.get("revision") is None else "audited",
                 "status": "unresolved", "status_reason": "", "reference_state": "unresolved"})
    try:
        reference = resolve_reference(book, annotation["target_id"])
    except (ValueError, KeyError, TypeError) as error:
        note["status_reason"] = str(error)
        note["redirect_chain"] = _known_chain(book, annotation.get("target_id"))
        return note
    note["resolved_target_id"] = reference.target_id
    note["redirect_chain"] = list(reference.chain)
    note["reference_state"] = "retired" if len(reference.chain) > 1 else "live"
    if len(reference.chain) > 1:
        note.update(status="stale", status_reason="Original annotation target was retired; its binding is not transferred to the redirect.")
    elif annotation.get("content_sha256") is None:
        note.update(status="legacy", status_reason="No inspected text digest was retained for this annotation.")
    elif annotation["content_sha256"] == reference.record.get("content_sha256"):
        note.update(status="matching", status_reason="Inspected Markdown digest matches; page metadata and PDF bytes are not bound by this annotation.")
    else:
        note.update(status="stale", status_reason="Inspected Markdown digest differs from the captured canonical text.")
    return note


def capture_comparison(workspace_reader, name):
    """Return independent JSON cards; perform exactly one workspace read export."""
    if not isinstance(name, str) or not name.strip():
        raise ComparisonError("A saved comparison name is required")
    _guard(workspace_reader)
    exported = workspace_reader.store.export()
    exported["workspace_name"] = Path(workspace_reader.store.path).stem
    comparisons = exported.get("comparisons", [])
    if not isinstance(comparisons, list) or not all(isinstance(row, dict) for row in comparisons):
        raise ComparisonError("Workspace export has an invalid comparison collection")
    matches = [row for row in comparisons if row.get("name") == name]
    if not matches:
        raise ComparisonError("No comparison with that name; inspect compare list or save a comparison first")
    if len(matches) != 1:
        raise ComparisonError("Workspace export contains duplicate comparison names")
    comparison = deepcopy(matches[0])
    targets = comparison.get("target_ids")
    if (not isinstance(targets, list) or not targets
            or not all(isinstance(identifier, str) for identifier in targets)):
        raise ComparisonError("Saved comparison requires an ordered set of canonical record IDs")
    result = _capture_records(workspace_reader.book, exported, comparison)
    _guard(workspace_reader)
    return result


def _capture_records(live_book, exported, comparison):
    targets = comparison["target_ids"]
    annotations = exported.get("annotations", [])
    if not isinstance(annotations, list) or not all(isinstance(row, dict) for row in annotations):
        raise ComparisonError("Workspace export has an invalid annotation collection")

    # All cards and note bindings resolve against the same independent in-memory
    # generation. The surrounding guards refuse any canonical on-disk changes.
    book = SimpleNamespace(canonical_records=deepcopy(live_book.canonical_records))
    corpus = _corpus_info(live_book)
    if exported.get("corpus_id") != corpus["id"]:
        raise ComparisonError("Comparison workspace belongs to a different canonical corpus")
    provenance = exported.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ComparisonError("Comparison workspace has invalid source provenance")
    expected_source = corpus["source"].get("sha256")
    declared_source = _source_fingerprint(provenance)
    if declared_source is not None and declared_source != expected_source:
        raise ComparisonError("Comparison workspace declares a different source PDF fingerprint")

    cards = [_card(book, identifier, position) for position, identifier in enumerate(targets)]
    notes = [_note(book, annotation) for annotation in annotations]
    for card in cards:
        card["notes"] = [deepcopy(note) for note in notes
                         if note.get("target_id") == card["requested_id"]
                         or (card["target_id"] is not None
                             and note["resolved_target_id"] == card["target_id"])]
    result = {
        "version": 1, "kind": "comparison",
        "text_basis": "loaded_canonical_generation_at_capture_not_comparison_save_time",
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspace": {"name": exported.get("workspace_name", ""),
                      "schema_version": exported.get("schema_version"),
                      "corpus_id": exported.get("corpus_id"), "exported_at": exported.get("exported_at")},
        "comparison": comparison, "corpus": corpus, "records": cards,
    }
    # Enforce a serializable, independently owned boundary before handing any
    # content to a renderer. Canonical and personal Markdown stay literal strings.
    return json.loads(json.dumps(result, ensure_ascii=True, allow_nan=False))


def resolve_comparison_path(book, value, cwd, resolve_path=resolve_book_path):
    """Select complete ordered canonical text, without reading arbitrary files.

    .txt paths belong to SOL's virtual tree; .md paths are relative to the
    configured corpus or absolute filenames within it. Both resolve to IDs from
    the loaded index. Physical Markdown is never parsed a second time here.
    """
    if not isinstance(value, str) or not value.strip():
        raise ComparisonError("Choose a SOL text path or a canonical Markdown file")
    records = book.canonical_records
    if value.lower().endswith(".md"):
        documents = book.corpus_manifest.get("documents", [])
        candidate = Path(value).expanduser()
        directory = getattr(book, "corpus_directory", None)
        if candidate.is_absolute():
            if directory is None:
                raise ComparisonError("No canonical corpus directory is configured")
            try:
                document = candidate.resolve().relative_to(Path(directory).resolve()).as_posix()
            except ValueError as error:
                raise ComparisonError("Choose a Markdown file inside the configured SOL corpus") from error
        else:
            document = posixpath.normpath(value)
            if directory is not None and document.startswith(Path(directory).name + "/"):
                document = document[len(Path(directory).name) + 1:]
        if document not in documents:
            raise ComparisonError(f"Not a canonical Markdown file: {value}. Use a path from the SOL corpus.")
        selected = [r for r in records.values() if r.get("document") == document
                    and r.get("type") != "retired_record"]
        display = str(Path(directory) / document) if directory is not None else document
        title = next((r.get("title") for r in selected if r.get("type") == "section" and r.get("title")),
                     Path(document).stem.replace("-", " "))
        kind = "markdown_file"
    else:
        node, scope = resolve_path(value, cwd, book.root)
        passage_ids = {p.identifier for p in book.selection(scope)}
        prefix = "/" + "/".join(scope)
        selected = [r for r in records.values() if r["id"] in passage_ids
                    or (r.get("type") == "section" and isinstance(r.get("reader_path"), str)
                        and (r["reader_path"] == prefix or r["reader_path"].startswith(prefix.rstrip("/") + "/")))]
        display, title, kind = prefix, node.title, "reader_path"
    selected.sort(key=lambda r: r["order"])
    if not selected:
        raise ComparisonError(f"No canonical text in {value}")
    return {"path": display, "display_path": document if kind == "markdown_file" else display,
            "title": title, "kind": kind,
            "target_ids": [r["id"] for r in selected]}


def _file_card(selection, members, position):
    sources = []
    seen_sources = set()
    notes = []
    for member in members:
        for source in member["sources"]:
            key = json.dumps(source, sort_keys=True)
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append(deepcopy(source))
        for note in member["notes"]:
            if not any(existing["id"] == note["id"] for existing in notes):
                notes.append({**deepcopy(note), "target_heading": member["title"],
                              "target_path": member["path"] or member["document"]})
    attributions = [m["attribution"] or {} for m in members]
    attribution_keys = [(a.get("author"), a.get("role")) for a in attributions]
    mixed = len(set(attribution_keys)) > 1
    attribution = attributions[0] if not mixed else {
        "author": None, "role": "mixed_attribution", "status": "see_individual_records"}
    flags = {m["transcription_status"] for m in members if m["transcription_status"]}
    presentation, previous_attribution = [], None
    for member, key in zip(members, attribution_keys):
        if mixed and key != previous_attribution:
            author, role = key
            presentation.append("[Text by " + (author or "unattributed edition contributor")
                                + (" | " + role.replace("_", " ") if role and role != "main_text" else "") + "]")
        if member["transcription_status"] in {"needs_review", "needs_visual_review"}:
            presentation.append("[Transcription needs source review]")
        presentation.append(member["plain_text"])
        previous_attribution = key
    return {"position": position, "requested_id": selection["path"], "target_id": None,
            "redirect_chain": [], "state": "live", "reason": "",
            "title": selection["title"], "path": selection["path"],
            "display_path": selection["display_path"],
            "type": "file_selection", "selection_kind": selection["kind"],
            "document": None, "plain_text": "\n\n".join(m["plain_text"] for m in members),
            "markdown": "\n\n".join(m["markdown"] for m in members),
            "presentation_text": "\n\n".join(presentation),
            "attribution": deepcopy(attribution), "sources": sources,
            "content_sha256": None, "metadata_sha256": None,
            "transcription_status": ", ".join(sorted(flags)) or None,
            "notes": notes, "members": members,
            "text_basis": "loaded_canonical_records_at_capture"}


def capture_paths(book, paths, *, cwd=(), resolve_path=resolve_book_path, workspace_reader=None, question=""):
    """Capture each chosen path as one side; never save or move the reader."""
    if len(paths) != 2:
        raise ComparisonError("Choose two paths: compare PATH_A PATH_B")
    if not isinstance(question, str):
        raise ComparisonError("The comparison question must be text")
    if workspace_reader is not None:
        _guard(workspace_reader)
    elif isinstance(getattr(book, "corpus_snapshot", None), CorpusSnapshot):
        verify_snapshot_current(book.corpus_snapshot)
    selections = [resolve_comparison_path(book, value, cwd, resolve_path) for value in paths]
    if workspace_reader is not None:
        exported = workspace_reader.store.export()
        exported["workspace_name"] = Path(workspace_reader.store.path).stem
    else:
        exported = {"annotations": [], "corpus_id": book.corpus_manifest.get("corpus_id"),
                    "provenance": {}, "workspace_name": ""}
    comparison = {"name": "File comparison", "question": question,
                  "actor": (workspace_reader.actor or "") if workspace_reader is not None else "",
                  "selection_kind": "paths", "target_ids": [identifier for selection in selections
                                                            for identifier in selection["target_ids"]]}
    result = _capture_records(book, exported, comparison)
    groups, start = [], 0
    for position, selection in enumerate(selections):
        stop = start + len(selection["target_ids"])
        groups.append(_file_card(selection, result["records"][start:stop], position))
        start = stop
    result["records"] = groups
    result["selections"] = selections
    result["refresh_command"] = "compare open"
    result["reopen_command"] = "compare open " + " ".join(shlex.quote(s["path"]) for s in selections)
    if question:
        result["reopen_command"] += " --question " + shlex.quote(question)
    if workspace_reader is not None:
        _guard(workspace_reader)
    elif isinstance(getattr(book, "corpus_snapshot", None), CorpusSnapshot):
        verify_snapshot_current(book.corpus_snapshot)
    return result
