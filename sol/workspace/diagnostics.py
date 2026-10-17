"""Pure diagnostics over an already loaded corpus and exported workspace.

Nothing here reads files, opens databases, edits canonical records, or changes
reading position. Source-review testimony binds text and the PDF fingerprint,
not every subsequently editable source-location or attribution field.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from sol.core.references import resolve_reference
from sol.workspace.time import parse_utc_timestamp


_COLLECTIONS = ("bookmarks", "annotations", "comparisons", "reviews", "relations", "history")
_PENDING = {"needs_review", "needs_visual_review"}
_REVIEW_BINDING = "text_and_pdf_fingerprint_only"


def reference_data(book, identifier: str | None) -> dict:
    """Resolve a reference without returning passage text or losing its old UUID."""
    return _reference_data(book, identifier)


def _readable_ids(book) -> set[str] | None:
    passages = getattr(book, "passages", None)
    return None if passages is None else {passage.identifier for passage in passages}


def _reference_data(book, identifier: str | None, readable_ids: set[str] | None = None) -> dict:
    result = {
        "requested_id": identifier, "resolved_id": None, "redirect_chain": [],
        "state": "absent" if identifier is None else "unresolved", "readable": False,
        "type": None, "path": None, "heading": None, "attribution": None,
        "sources": [], "reason": "No saved passage reference." if identifier is None else "",
    }
    if identifier is None:
        return result
    if not isinstance(identifier, str):
        raise ValueError("reference identifier must be a string or null")
    try:
        reference = resolve_reference(book, identifier)
    except ValueError as error:
        result["reason"] = str(error)
        return result
    record = reference.record
    if readable_ids is not None:
        readable = reference.target_id in readable_ids
    else:
        try:
            book.find_passage(reference.target_id)
        except ValueError:
            readable = False
        else:
            readable = True
    retired = len(reference.chain) > 1
    result.update({
        "requested_id": reference.requested_id, "resolved_id": reference.target_id,
        "redirect_chain": list(reference.chain), "state": "retired" if retired else "live",
        "readable": readable, "type": record["type"],
        "path": record.get("reader_path") or record.get("path"),
        "heading": record.get("reader_title") or record.get("heading") or record.get("title"),
        "attribution": deepcopy(record.get("attribution")),
        "sources": deepcopy(record.get("sources", [])),
        "reason": "Canonical record retired; an explicit redirect is retained." if retired else "",
    })
    return result


def _snapshot(snapshot: dict) -> dict[str, list[dict]]:
    if not isinstance(snapshot, dict):
        raise ValueError("workspace snapshot must be a JSON object")
    collections = {}
    for name in _COLLECTIONS:
        values = snapshot.get(name, [])
        if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
            raise ValueError(f"workspace snapshot {name} must be a list of records")
        collections[name] = values
    if snapshot.get("state") is not None and not isinstance(snapshot["state"], dict):
        raise ValueError("workspace checkpoint must be a JSON object or null")
    return collections


def _source_sha(book) -> str | None:
    return book.corpus_manifest.get("source", {}).get("sha256")


def _annotation_version(book, annotation: dict, reference: dict) -> str:
    if reference["state"] in {"unresolved", "absent"}:
        return "unresolved"
    if reference["state"] == "retired":
        return "retired"
    inspected = annotation.get("content_sha256")
    if inspected is None:
        return "unversioned"
    record = book.canonical_records[reference["resolved_id"]]
    return "current_text" if record.get("content_sha256") == inspected else "stale"


def _review_version(book, review: dict, reference: dict) -> str:
    if reference["state"] in {"unresolved", "absent"}:
        return "unresolved"
    if reference["state"] == "retired":
        return "retired"
    inspected, source = review.get("content_sha256"), review.get("source_sha256")
    if inspected is None or source is None or _source_sha(book) is None:
        return "unversioned"
    record = book.canonical_records[reference["resolved_id"]]
    if record.get("content_sha256") != inspected or _source_sha(book) != source:
        return "stale"
    return "current_text_and_pdf"


def workspace_health(book, exported_workspace_snapshot: dict) -> dict:
    """Report referential/version issues from one supplied, consistent export."""
    collections = _snapshot(exported_workspace_snapshot)
    counts = {name: len(values) for name, values in collections.items()}
    counts.update({
        "pending_source_review": sum(record.get("transcription_status") in _PENDING
                                     for record in book.canonical_records.values()),
        "references": 0, "unresolved_references": 0, "retired_references": 0,
        "unreadable_reading_references": 0,
        "absent_references": 0, "stale_annotations": 0, "unversioned_annotations": 0,
        "stale_reviews": 0, "unversioned_reviews": 0,
    })
    issues = []
    readable_ids = _readable_ids(book)

    def inspect(identifier, collection, record_id, label, **details):
        reference = _reference_data(book, identifier, readable_ids)
        counts["references"] += 1
        state = reference["state"]
        if state != "live":
            counts[state + "_references"] += 1
            issues.append({
                "kind": "reference_" + state, "collection": collection,
                "record_id": record_id, "label": label, "target_id": identifier,
                "state": state, "reason": reference["reason"],
                "reference": reference, **details,
            })
        if (collection in {"state", "history", "bookmarks"}
                and state in {"live", "retired"} and not reference["readable"]):
            counts["unreadable_reading_references"] += 1
            issues.append({
                "kind": "unreadable_reading_reference", "collection": collection,
                "record_id": record_id, "label": label, "target_id": identifier,
                "state": "unreadable",
                "reason": "This reading reference resolves to a canonical record outside the readable Hegel passage view.",
                "reference": reference, **details,
            })
        return reference

    identity = book.corpus_manifest.get("corpus_id")
    if exported_workspace_snapshot.get("corpus_id") != identity:
        issues.append({"kind": "corpus_identity_mismatch", "record_id": None,
                       "label": "Workspace corpus identity", "target_id": None,
                       "state": "mismatched", "reason": "Workspace and loaded corpus identities differ."})
    provenance = exported_workspace_snapshot.get("provenance", {})
    if isinstance(provenance, dict):
        source = provenance.get("source", {})
        workspace_sha = provenance.get("source_sha256") or (
            source.get("sha256") if isinstance(source, dict) else None)
        if workspace_sha != _source_sha(book):
            issues.append({"kind": "source_fingerprint_mismatch", "record_id": None,
                           "label": "Workspace source fingerprint", "target_id": None,
                           "state": "mismatched", "reason": "Workspace and loaded PDF fingerprints differ."})
    state = exported_workspace_snapshot.get("state")
    if state is not None:
        inspect(state.get("current_id"), "state", state.get("revision"), "Current checkpoint")
    for row in collections["history"]:
        inspect(row.get("current_id"), "history", row.get("revision"),
                f"Checkpoint revision {row.get('revision')}")
    for row in collections["bookmarks"]:
        inspect(row.get("target_id"), "bookmarks", row.get("name"), row.get("name"))
    for row in collections["comparisons"]:
        targets = row.get("target_ids", [])
        if not isinstance(targets, list):
            raise ValueError("comparison target_ids must be a list")
        for position, identifier in enumerate(targets):
            inspect(identifier, "comparisons", row.get("name"), row.get("name"), position=position)
    for row in collections["relations"]:
        for endpoint in ("source", "target"):
            inspect(row.get(endpoint + "_id"), "relations", row.get("id"), row.get("kind"), endpoint=endpoint)
    for name, version_function in (("annotations", _annotation_version), ("reviews", _review_version)):
        for row in collections[name]:
            reference = inspect(row.get("target_id"), name, row.get("id"),
                                "Personal annotation" if name == "annotations" else "Reader testimony")
            version = version_function(book, row, reference)
            if version in {"stale", "unversioned"}:
                counts[version + "_" + name] += 1
                noun = "annotation" if name == "annotations" else "review"
                if name == "annotations":
                    reason = ("Target Markdown content no longer matches the stored digest." if version == "stale"
                              else "The annotation does not bind a target Markdown version.")
                else:
                    reason = ("Inspected text or PDF fingerprint no longer matches." if version == "stale"
                              else "The review does not bind an inspected text/PDF version.")
                issues.append({
                    "kind": noun + "_" + version, "collection": name,
                    "record_id": row.get("id"), "label": noun.capitalize(),
                    "target_id": row.get("target_id"), "state": version,
                    "reason": reason,
                    "actor": row.get("actor"), "reference": reference,
                    **({"provenance_binding": _REVIEW_BINDING} if name == "reviews" else {}),
                })
    return {
        "format": "sol-workspace-health", "schema_version": 1, "corpus_id": identity,
        "snapshot_basis": "loaded_corpus_and_exported_workspace",
        "status": "attention_required" if issues else "no_workspace_issues_detected",
        "canonical_review_state": "pending" if counts["pending_source_review"] else "no_pending_flags",
        "review_provenance_binding": _REVIEW_BINDING, "counts": counts, "issues": issues,
    }


def _review_time(review: dict) -> datetime:
    value = review.get("created_at")
    if not isinstance(value, str):
        raise ValueError("review creation time must be a UTC timestamp")
    try:
        timestamp = parse_utc_timestamp(value)
    except ValueError as error:
        raise ValueError("review creation time must be a UTC timestamp") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ValueError("review creation time must be a UTC timestamp")
    return timestamp


def review_queue(book, exported_snapshot: dict, within: tuple[str, ...] | None = None,
                 limit: int = 20) -> list[dict]:
    """Canonical pending flags remain queued irrespective of reader testimony."""
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("review queue limit must be an integer between 1 and 1000")
    if within is not None and (not isinstance(within, tuple) or any(
            not isinstance(part, str) or not part or part in {".", ".."} or "/" in part or "\\" in part
            for part in within)):
        raise ValueError("review queue scope must be a tuple of virtual path components")
    collections = _snapshot(exported_snapshot)
    readable_ids = _readable_ids(book)
    testimony: dict[str, list[tuple[datetime, dict, dict]]] = {}
    for review in collections["reviews"]:
        reference = _reference_data(book, review.get("target_id"), readable_ids)
        if reference["resolved_id"] is not None:
            testimony.setdefault(reference["resolved_id"], []).append((_review_time(review), review, reference))
    pending = sorted((record for record in book.canonical_records.values()
                      if record.get("transcription_status") in _PENDING), key=lambda record: record["order"])
    result = []
    for record in pending:
        reader_path = record.get("reader_path")
        if within is not None:
            if not isinstance(reader_path, str) or not reader_path.startswith("/"):
                continue
            parts = tuple(reader_path[1:].split("/"))
            if parts[:len(within)] != within:
                continue
        latest = None
        reviews = testimony.get(record["id"], [])
        if reviews:
            # Workspace.export preserves append order. Wall-clock timestamps can
            # tie or go backwards; neither should resurrect an older decision.
            timestamp, review, reference = reviews[-1]
            latest = {
                "id": review["id"], "target_id": review["target_id"], "actor": review.get("actor"),
                "outcome": review.get("outcome"), "created_at": review["created_at"],
                "version_state": _review_version(book, review, reference),
                "provenance_binding": _REVIEW_BINDING, "chronology_basis": "exported_append_order",
                "chronology_ambiguous": False,
                "timestamp_ambiguous": sum(time == timestamp for time, _, _ in reviews) > 1,
                "timestamps_non_monotonic": any(second[0] < first[0] for first, second in zip(reviews, reviews[1:])),
            }
        result.append({
            "id": record["id"], "type": record["type"], "order": record["order"],
            "path": reader_path or record.get("path"),
            "heading": record.get("reader_title") or record.get("heading") or record.get("title"),
            "attribution": deepcopy(record.get("attribution")), "sources": deepcopy(record.get("sources", [])),
            "transcription_status": record["transcription_status"], "latest_review": latest,
        })
        if len(result) == limit:
            break
    return result
