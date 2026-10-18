"""Version-1 cross-process references, without navigation or execution authority.

The recipient supplies a local verified corpus. A packet never supplies a path,
command, actor, workspace, or replacement text. Fingerprints establish agreement
with that corpus generation, not authorship, authentication, or PDF accuracy.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math
import re
import uuid

from sol.core.references import resolve_record_reference


PROTOCOL_VERSION = 1
MAX_REFERENCE_BYTES = 65536
MAX_REFERENCE_BATCH = 1024
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


# The last few verified disk generations, kept only as immutable JSON text. A
# match on every fingerprint means the files hold the same bytes that were fully
# loaded and validated, so a reload would parse the same records. Each call still
# gets new dictionaries, and still compares the caller's snapshot in full.
_VERIFIED_GENERATIONS = {}
_VERIFIED_LIMIT = 4


def _generation_key(snapshot):
    return (str(snapshot.corpus_directory), str(snapshot.index_file), snapshot.manifest_sha256,
            snapshot.index_sha256, snapshot.index_metadata_sha256,
            json.dumps(snapshot.documents, sort_keys=True, ensure_ascii=True))


def _load_fresh(snapshot):
    from sol.corpus.contract import CorpusError, CorpusSnapshot, load_snapshot, verify_snapshot_current

    key = _generation_key(snapshot)
    cached = _VERIFIED_GENERATIONS.get(key)
    if cached is None:
        try:
            fresh = load_snapshot(snapshot.corpus_directory, index=snapshot.index_file)
        except CorpusError as error:
            raise ProtocolError("The selected corpus generation is no longer valid; reopen after correcting/reindexing it",
                                status="stale", code="generation_changed") from error
        if _generation_key(fresh) == key:
            manifest_text = json.dumps(fresh.manifest, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            records_text = json.dumps(fresh.records, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            # The parsed copies serve only comparisons; they are never returned.
            cached = (manifest_text, records_text, _json(fresh.manifest), _json(fresh.records),
                      json.loads(manifest_text), json.loads(records_text))
            while len(_VERIFIED_GENERATIONS) >= _VERIFIED_LIMIT:
                _VERIFIED_GENERATIONS.pop(next(iter(_VERIFIED_GENERATIONS)))
            _VERIFIED_GENERATIONS[key] = cached
            return fresh, cached[2:]
        return fresh, None
    manifest_text, records_text = cached[:2]
    fresh = CorpusSnapshot(
        corpus_directory=snapshot.corpus_directory, manifest=json.loads(manifest_text),
        records=json.loads(records_text), manifest_sha256=snapshot.manifest_sha256,
        index_sha256=snapshot.index_sha256, documents=dict(snapshot.documents),
        index_file=snapshot.index_file, index_metadata_sha256=snapshot.index_metadata_sha256)
    # The fingerprints are checked against the cached manifest, not the
    # caller's possibly modified one; any change in the files refuses.
    try:
        verify_snapshot_current(fresh)
    except CorpusError as error:
        _VERIFIED_GENERATIONS.pop(key, None)
        raise ProtocolError("The loaded corpus generation changed; reopen before transferring a reference",
                            status="stale", code="generation_changed") from error
    return fresh, cached[2:]


def _unmodified(value, canonical, verified):
    """Whether caller data equals the verified generation.

    Canonical JSON text catches changed values and JSON types (true versus 1);
    structural equality with a private parsed copy catches tuples for lists and
    non-string keys. It accepts an int or float subclass with an equal value,
    as approved by the maintainer on 19 October 2026 (CORE §6).
    """
    if verified is None:
        return _json(_json_value(value)) == canonical
    return _json(value) == canonical and value == verified


# One reader action: the snapshot it was entered for, and its verified copy.
_ACTION = ContextVar("sol_reference_action", default=None)


@contextmanager
def single_action(snapshot):
    """Compare the caller's in-memory snapshot in full once for one user action.

    Inside the block, every capture or check still verifies the corpus files'
    fingerprints, but the full comparison of the caller's snapshot and the
    disk-verified copy run once, at the first call, and that copy is reused.
    A modification of the in-memory snapshot during the block is refused by the
    next action. Approved by the maintainer on 19 October 2026 (CORE §5).
    """
    token = _ACTION.set({"snapshot": snapshot, "fresh": None})
    try:
        yield
    finally:
        _ACTION.reset(token)


def _fresh_snapshot(snapshot):
    from sol.corpus.contract import CorpusError, CorpusSnapshot, verify_snapshot_current

    if not isinstance(snapshot, CorpusSnapshot):
        raise ProtocolError("References require a verified canonical CorpusSnapshot", code="unverified_snapshot")
    action = _ACTION.get()
    if action is not None and action["snapshot"] is snapshot and action["fresh"] is not None:
        try:
            verify_snapshot_current(action["fresh"])
        except CorpusError as error:
            raise ProtocolError("The loaded corpus generation changed; reopen before transferring a reference",
                                status="stale", code="generation_changed") from error
        return action["fresh"]
    fresh, verified = _load_fresh(snapshot)
    if verified is None:
        verified = (_json(fresh.manifest), _json(fresh.records), None, None)
    if (fresh.manifest_sha256 != snapshot.manifest_sha256 or fresh.index_sha256 != snapshot.index_sha256
            or fresh.index_metadata_sha256 != snapshot.index_metadata_sha256 or fresh.documents != snapshot.documents):
        raise ProtocolError("The loaded corpus generation changed; reopen before transferring a reference",
                            status="stale", code="generation_changed")
    # A frozen snapshot still contains mutable dictionaries. Do not describe
    # caller-modified records using the original disk-generation fingerprints.
    manifest_canonical, records_canonical, manifest_verified, records_verified = verified
    if (not _unmodified(snapshot.manifest, manifest_canonical, manifest_verified)
            or not _unmodified(snapshot.records, records_canonical, records_verified)):
        raise ProtocolError("The in-memory corpus snapshot was modified; reload canonical data",
                            status="stale", code="snapshot_modified")
    if fresh.corpus_id is None:
        raise ProtocolError("The corpus needs an explicitly initialized permanent identity; "
                            "use sol-corpus-check DIRECTORY --initialize-identity (never reconvert it)",
                            code="missing_corpus_identity")
    if action is not None and action["snapshot"] is snapshot:
        action["fresh"] = fresh
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


def _resolve(snapshot, identifier, records=None):
    if (not isinstance(identifier, str) or not 1 <= len(identifier.strip()) <= 36
            or not re.fullmatch(r"[0-9a-fA-F-]+", identifier.strip())):
        raise ProtocolError("A canonical record identifier is required", code="invalid_identifier")
    try:
        return resolve_record_reference(
            records if records is not None else {record["id"]: record for record in snapshot.records}, identifier)
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
    return capture_references(snapshot, [identifier])[0]


def _batch(items):
    if type(items) not in (list, tuple) or not 1 <= len(items) <= MAX_REFERENCE_BATCH:
        raise ProtocolError(f"Reference batch requires a list or tuple of 1–{MAX_REFERENCE_BATCH} items",
                            code="batch_limit")
    return tuple(items)


def capture_references(snapshot, identifiers):
    """Capture an ordered bounded batch against one freshly verified generation.

    Results are released only after a final disk check. There is no reusable
    trust cache, and each result is an ordinary version-1 reference envelope.
    """
    identifiers = _batch(identifiers)
    fresh = _fresh_snapshot(snapshot)
    records = {record["id"]: record for record in fresh.records}
    payloads = [_validate(_project(fresh, _resolve(fresh, identifier, records)))
                for identifier in identifiers]
    _still_current(fresh)
    return payloads


def check_reference(snapshot, payload):
    """Return the canonical Reference only after exact local-generation agreement."""
    return check_references(snapshot, [payload])[0]


def check_references(snapshot, payloads):
    """Check a whole batch before releasing any resolved record to the caller."""
    payloads = [_validate(payload) for payload in _batch(payloads)]
    fresh = _fresh_snapshot(snapshot)
    records = {record["id"]: record for record in fresh.records}
    references = [_check_on_snapshot(fresh, payload, records) for payload in payloads]
    _still_current(fresh)
    # The verified graph may serve the rest of a single action; a caller gets
    # its own copy of each record, so changing it cannot alter later checks.
    return [replace(reference, record=deepcopy(reference.record)) for reference in references]


def _check_on_snapshot(fresh, payload, records):
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
    reference = _resolve(fresh, payload["reference"]["requested_id"], records)
    expected = _validate(_project(fresh, reference))["reference"]
    if _json(payload["reference"]) != _json(expected):
        raise ProtocolError("Reference target, chain, content or provenance disagrees with the canonical record",
                            status="mismatch", code="record_mismatch")
    return reference
