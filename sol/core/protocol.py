"""Version-1 cross-process references, without navigation or execution authority.

The recipient supplies a local verified corpus. A packet never supplies a path,
command, actor, workspace, or replacement text. Fingerprints establish agreement
with that corpus generation, not authorship, authentication, or PDF accuracy.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import uuid

from sol.core.references import resolve_record_reference


PROTOCOL_VERSION = 1
MAX_REFERENCE_BYTES = 65536
_PROTOCOL = "sol.reference"


class ProtocolError(ValueError):
    """A machine-readable refusal; never permission to repair or follow a hint."""
    def __init__(self, message, *, status="invalid", code="invalid_reference"):
        super().__init__(message)
        self.status = status
        self.code = code


def _json_value(value, depth=0):
    if depth > 64:
        raise ProtocolError("Reference JSON nesting exceeds 64 levels", code="nesting_limit")
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise ProtocolError("Reference strings must be valid UTF-8", code="invalid_utf8") from error
        return value
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, list):
        return [_json_value(item, depth + 1) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {_json_value(key, depth + 1): _json_value(item, depth + 1) for key, item in value.items()}
    raise ProtocolError("References require finite JSON values", code="invalid_json")


def _json(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError) as error:
        raise ProtocolError("Cannot serialize reference JSON", code="invalid_json") from error


def _sha(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ProtocolError(f"{label} requires exactly: {', '.join(sorted(expected))}", code="invalid_fields")


def _uuid(value, label):
    try:
        valid = isinstance(value, str) and str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        valid = False
    if not valid:
        raise ProtocolError(f"{label} must be a full canonical lowercase UUID", code="invalid_identifier")


def _digest(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ProtocolError(f"{label} must be a lowercase SHA-256", code="invalid_digest")


def _finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _validate(payload):
    payload = _json_value(payload)
    _keys(payload, {"protocol", "version", "corpus", "generation", "reference"}, "Reference envelope")
    if payload["protocol"] != _PROTOCOL or type(payload["version"]) is not int or payload["version"] != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported SOL reference protocol or version", code="unsupported_version")
    corpus, generation, reference = payload["corpus"], payload["generation"], payload["reference"]
    _keys(corpus, {"id", "edition_sha256", "source"}, "Corpus binding")
    _uuid(corpus["id"], "Corpus ID")
    _digest(corpus["edition_sha256"], "Edition fingerprint")
    _keys(corpus["source"], {"sha256", "pdf_pages"}, "Source binding")
    _digest(corpus["source"]["sha256"], "Source fingerprint")
    pages = corpus["source"]["pdf_pages"]
    if type(pages) is not int or pages < 1:
        raise ProtocolError("Source page count must be a positive integer", code="invalid_source")
    _keys(generation, {"manifest_sha256", "index_sha256"}, "Generation binding")
    for field, value in generation.items():
        _digest(value, field)
    _keys(reference, {"requested_id", "target_id", "chain", "content_sha256", "type", "sources", "attribution"},
          "Record binding")
    for field in ("requested_id", "target_id"):
        _uuid(reference[field], field)
    _digest(reference["content_sha256"], "Record content fingerprint")
    chain = reference["chain"]
    if not isinstance(chain, list) or not chain:
        raise ProtocolError("Reference chain must be a nonempty UUID list", code="invalid_chain")
    for item in chain:
        _uuid(item, "Chain entry")
    if (len(set(chain)) != len(chain) or chain[0] != reference["requested_id"]
            or chain[-1] != reference["target_id"]):
        raise ProtocolError("Reference chain endpoints or distinct identities disagree", code="invalid_chain")
    kind = reference["type"]
    if not isinstance(kind, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", kind) or kind == "retired_record":
        raise ProtocolError("Reference type must identify a resolved canonical record", code="invalid_record_type")
    attribution = reference["attribution"]
    _keys(attribution, {"author", "role", "status"}, "Attribution")
    if (attribution["author"] is not None and not isinstance(attribution["author"], str)
            or any(not isinstance(attribution[key], str) or not attribution[key].strip() for key in ("role", "status"))):
        raise ProtocolError("Invalid canonical attribution", code="invalid_attribution")
    sources = reference["sources"]
    if not isinstance(sources, list) or not sources:
        raise ProtocolError("Reference requires source-page evidence", code="invalid_sources")
    previous = 0
    for source in sources:
        if (not isinstance(source, dict) or not {"pdf_page", "printed_page"} <= source.keys()
                or set(source) - {"pdf_page", "printed_page", "bbox"}):
            raise ProtocolError("Source entries require PDF/printed pages and optional bbox only", code="invalid_sources")
        page = source["pdf_page"]
        if type(page) is not int or not previous < page <= pages:
            raise ProtocolError("Source pages must be distinct, ordered and within the PDF", code="invalid_sources")
        previous = page
        label = source["printed_page"]
        if label is not None and not isinstance(label, str):
            raise ProtocolError("Printed-page labels must be strings or null", code="invalid_sources")
        if "bbox" in source:
            box = source["bbox"]
            if (not isinstance(box, list) or len(box) != 4 or not all(_finite_number(item) for item in box)
                    or box[0] < 0 or box[1] < 0 or box[0] > box[2] or box[1] > box[3]):
                raise ProtocolError("Invalid canonical source rectangle", code="invalid_sources")
    if len(_json(payload).encode("utf-8")) > MAX_REFERENCE_BYTES:
        raise ProtocolError("Reference exceeds 64 KiB", code="size_limit")
    return payload


def decode_reference(data):
    """Decode one bounded UTF-8 JSON envelope; duplicates are never overwritten."""
    try:
        raw = data.encode("utf-8") if isinstance(data, str) else data
        if not isinstance(raw, bytes):
            raise ProtocolError("Reference input must be UTF-8 bytes or text", code="invalid_json")
        if len(raw) > MAX_REFERENCE_BYTES:
            raise ProtocolError("Reference exceeds 64 KiB", code="size_limit")
        text = raw.decode("utf-8")
    except UnicodeError as error:
        raise ProtocolError("Reference input is not valid UTF-8", code="invalid_utf8") from error

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolError("Duplicate reference JSON field", code="duplicate_field")
            result[key] = value
        return result

    def nonfinite(value):
        raise ProtocolError("Reference JSON must contain finite numbers", code="invalid_json")

    try:
        payload = json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, RecursionError) as error:
        if isinstance(error, ProtocolError):
            raise
        raise ProtocolError("Invalid reference JSON", code="invalid_json") from error
    return _validate(payload)


def encode_reference(payload):
    """Serialize a validated envelope, leaving room for the CLI's final newline."""
    # JSON escapes preserve Unicode while keeping terminal control/bidi data
    # inert when a user inspects a packet directly in the shell.
    text = json.dumps(_validate(payload), ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)
    if len(text.encode("utf-8")) + 1 > MAX_REFERENCE_BYTES:
        raise ProtocolError("Formatted reference exceeds 64 KiB", code="size_limit")
    return text


def _fresh_snapshot(snapshot):
    from sol.corpus.contract import CorpusError, CorpusSnapshot, load_snapshot

    if not isinstance(snapshot, CorpusSnapshot):
        raise ProtocolError("References require a verified canonical CorpusSnapshot", code="unverified_snapshot")
    try:
        fresh = load_snapshot(snapshot.corpus_directory, index=snapshot.index_file)
    except CorpusError as error:
        raise ProtocolError("The selected corpus generation is no longer valid; reopen after correcting/reindexing it",
                            status="stale", code="generation_changed") from error
    if (fresh.manifest_sha256 != snapshot.manifest_sha256 or fresh.index_sha256 != snapshot.index_sha256
            or fresh.index_metadata_sha256 != snapshot.index_metadata_sha256 or fresh.documents != snapshot.documents):
        raise ProtocolError("The loaded corpus generation changed; reopen before transferring a reference",
                            status="stale", code="generation_changed")
    # A frozen snapshot still contains mutable dictionaries. Do not describe
    # caller-modified records using the original disk-generation fingerprints.
    if (_json(_json_value(snapshot.manifest)) != _json(fresh.manifest)
            or _json(_json_value(snapshot.records)) != _json(fresh.records)):
        raise ProtocolError("The in-memory corpus snapshot was modified; reload canonical data",
                            status="stale", code="snapshot_modified")
    if fresh.corpus_id is None:
        raise ProtocolError("The corpus needs an explicitly initialized permanent identity; "
                            "use sol-corpus-check DIRECTORY --initialize-identity (never reconvert it)",
                            code="missing_corpus_identity")
    return fresh


def _project(snapshot, reference):
    manifest, record = snapshot.manifest, reference.record
    return {
        "protocol": _PROTOCOL, "version": PROTOCOL_VERSION,
        "corpus": {"id": snapshot.corpus_id, "edition_sha256": _sha(_json_value(manifest["edition"])),
                   "source": {key: manifest["source"][key] for key in ("sha256", "pdf_pages")}},
        "generation": {"manifest_sha256": snapshot.manifest_sha256, "index_sha256": snapshot.index_sha256},
        "reference": {"requested_id": reference.requested_id, "target_id": reference.target_id,
                      "chain": list(reference.chain), "content_sha256": record["content_sha256"],
                      "type": record["type"],
                      "sources": [{key: value for key, value in source.items()
                                   if key in {"pdf_page", "printed_page", "bbox"}} for source in record["sources"]],
                      "attribution": {key: record["attribution"][key] for key in ("author", "status", "role")}},
    }


def _resolve(snapshot, identifier):
    if (not isinstance(identifier, str) or not 1 <= len(identifier.strip()) <= 36
            or not re.fullmatch(r"[0-9a-fA-F-]+", identifier.strip())):
        raise ProtocolError("A canonical record identifier is required", code="invalid_identifier")
    try:
        return resolve_record_reference({record["id"]: record for record in snapshot.records}, identifier)
    except ValueError as error:
        raise ProtocolError(str(error), status="unresolved", code="unresolved_reference") from error


def _still_current(snapshot):
    from sol.corpus.contract import CorpusError, verify_snapshot_current

    try:
        verify_snapshot_current(snapshot)
    except CorpusError as error:
        raise ProtocolError("The corpus changed while checking the reference; reopen and retry",
                            status="stale", code="generation_changed") from error


def capture_reference(snapshot, identifier):
    """Capture a canonical record, including notes/editorial text and retirements."""
    fresh = _fresh_snapshot(snapshot)
    reference = _resolve(fresh, identifier)
    payload = _validate(_project(fresh, reference))
    _still_current(fresh)
    return payload


def check_reference(snapshot, payload):
    """Return the canonical Reference only after exact local-generation agreement."""
    payload = _validate(payload)
    fresh = _fresh_snapshot(snapshot)
    corpus = payload["corpus"]
    if corpus["id"] != fresh.corpus_id:
        raise ProtocolError("Reference belongs to another corpus", status="mismatch", code="corpus_mismatch")
    if corpus["edition_sha256"] != _sha(_json_value(fresh.manifest["edition"])):
        raise ProtocolError("Reference belongs to another edition", status="mismatch", code="edition_mismatch")
    if corpus["source"] != {key: fresh.manifest["source"][key] for key in ("sha256", "pdf_pages")}:
        raise ProtocolError("Reference has a different source binding", status="mismatch", code="source_mismatch")
    generation = {"manifest_sha256": fresh.manifest_sha256, "index_sha256": fresh.index_sha256}
    if payload["generation"] != generation:
        raise ProtocolError("Reference was captured from another corpus generation; recapture deliberately",
                            status="stale", code="generation_changed")
    reference = _resolve(fresh, payload["reference"]["requested_id"])
    expected = _validate(_project(fresh, reference))["reference"]
    if _json(payload["reference"]) != _json(expected):
        raise ProtocolError("Reference target, chain, content or provenance disagrees with the canonical record",
                            status="mismatch", code="record_mismatch")
    _still_current(fresh)
    return reference
