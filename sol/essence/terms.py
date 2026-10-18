"""A literal word distribution, not a conceptual model or interpretive verdict.

One checked generation supplies all denominators. Results name existing records,
never create identities, mutate a corpus, or inherit actor/workspace authority.
The optional CORE reference is context only; it never restricts the study's scope.
"""
from __future__ import annotations

import hashlib
import json
import math
import posixpath
import re
import unicodedata
import uuid

from sol import core
from sol.essence.tokenization import word_tokens as _tokens


MAX_RESULT_BYTES = 1048576
_DOCTRINES = ("BEING", "ESSENCE", "CONCEPT")
_TYPES = {"paragraph", "quotation", "list_item"}
_REASONS = ("attribution", "record_type", "review", "reader_path", "doctrine")
_STATS = {"passage_count", "token_count", "matching_passages", "occurrences", "rate_per_10000_tokens"}
_METHOD = {
    "algorithm": "literal-term-distribution-v1",
    "unicode_version": unicodedata.unidata_version,
    "normalization": "NFC+casefold+curly-apostrophe-to-straight",
    "tokenization": "unicode-letter-mark-internal-apostrophe-v1",
    "selection": "hegel-main-text-no-pending-flags-three-doctrines-v1",
    "order": "canonical-corpus-order",
    "context_codepoints": 80,
    "offsets": "plain-text-codepoints",
    "facsimile": "trailing-converter-image-labels-v1",
}


class TermExperimentError(ValueError):
    """A typed refusal, not permission to repair or reinterpret a result."""

    def __init__(self, message, *, status="invalid", code="invalid_term_study"):
        super().__init__(message)
        self.status = status
        self.code = code


def _json(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError) as error:
        raise TermExperimentError("Term study requires finite JSON values", code="invalid_json") from error


def _json_value(value, depth=0):
    if depth > 64:
        raise TermExperimentError("Term-study JSON nesting exceeds 64 levels", code="nesting_limit")
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise TermExperimentError("Term-study strings must be valid UTF-8", code="invalid_utf8") from error
        return value
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, list):
        return [_json_value(item, depth + 1) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {_json_value(key, depth + 1): _json_value(item, depth + 1) for key, item in value.items()}
    raise TermExperimentError("Term study requires finite JSON values", code="invalid_json")


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise TermExperimentError(f"{label} requires exactly: {', '.join(sorted(expected))}", code="invalid_fields")


def _integer(value, label, minimum=0, maximum=2 ** 63 - 1):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise TermExperimentError(f"Invalid integer for {label}", code="invalid_number")


def _validate_binding(result):
    corpus, generation = result["corpus"], result["generation"]
    _keys(corpus, {"id", "edition_sha256", "source"}, "Corpus binding")
    try:
        identifier = corpus["id"]
        valid = isinstance(identifier, str) and str(uuid.UUID(identifier)) == identifier
    except (ValueError, AttributeError):
        valid = False
    if not valid:
        raise TermExperimentError("Corpus ID must be a full canonical lowercase UUID", code="invalid_identifier")
    _keys(corpus["source"], {"sha256", "pdf_pages"}, "Source binding")
    _integer(corpus["source"]["pdf_pages"], "source page count", 1)
    _keys(generation, {"manifest_sha256", "index_sha256"}, "Generation binding")
    for value in [corpus["edition_sha256"], corpus["source"]["sha256"], *generation.values()]:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise TermExperimentError("Term-study fingerprints must be lowercase SHA-256", code="invalid_digest")


def _query(value):
    if not isinstance(value, str):
        raise TermExperimentError("Query must be one literal word", code="invalid_query")
    _json_value(value)
    if len(value.encode("utf-8")) > MAX_RESULT_BYTES:
        raise TermExperimentError("Query exceeds the term-study byte limit", code="size_limit")
    tokens = list(_tokens(value))
    if len(tokens) != 1 or tokens[0][1:] != (0, len(value)):
        raise TermExperimentError("Query must be one Unicode letter word with optional internal apostrophes",
                                  code="invalid_query")
    return tokens[0][0]


def _options(query, doctrine, limit):
    normalized = _query(query)
    if doctrine is not None and (not isinstance(doctrine, str) or doctrine not in _DOCTRINES):
        raise TermExperimentError("Doctrine must be BEING, ESSENCE, CONCEPT or null", code="invalid_doctrine")
    _integer(limit, "limit", 1, 100)
    return normalized


def _fresh(snapshot):
    if not isinstance(snapshot, core.CorpusSnapshot):
        raise TermExperimentError("A verified canonical CorpusSnapshot is required", code="unverified_snapshot")
    try:
        fresh = core.load_snapshot(snapshot.corpus_directory, index=snapshot.index_file)
    except core.CorpusError as error:
        raise TermExperimentError("The selected corpus generation is no longer valid; reopen after reindexing",
                                  status="stale", code="generation_changed") from error
    if (fresh.manifest_sha256 != snapshot.manifest_sha256 or fresh.index_sha256 != snapshot.index_sha256
            or fresh.index_metadata_sha256 != snapshot.index_metadata_sha256 or fresh.documents != snapshot.documents):
        raise TermExperimentError("The corpus generation changed; reopen before studying it",
                                  status="stale", code="generation_changed")
    if (_json(_json_value(snapshot.manifest)) != _json(fresh.manifest)
            or _json(_json_value(snapshot.records)) != _json(fresh.records)):
        raise TermExperimentError("The in-memory corpus snapshot was modified; reload canonical data",
                                  status="stale", code="snapshot_modified")
    if fresh.corpus_id is None:
        raise TermExperimentError("The corpus needs an explicitly initialized permanent identity",
                                  code="missing_corpus_identity")
    return fresh


def _current(snapshot):
    try:
        core.verify_snapshot_current(snapshot)
    except core.CorpusError as error:
        raise TermExperimentError("The corpus changed during the study; reopen and retry",
                                  status="stale", code="generation_changed") from error


def _binding(snapshot):
    return {
        "corpus": {"id": snapshot.corpus_id,
                   "edition_sha256": hashlib.sha256(_json(snapshot.manifest["edition"]).encode("utf-8")).hexdigest(),
                   "source": {key: snapshot.manifest["source"][key] for key in ("sha256", "pdf_pages")}},
        "generation": {"manifest_sha256": snapshot.manifest_sha256, "index_sha256": snapshot.index_sha256},
    }


def _core_error(error):
    return TermExperimentError(str(error), status=error.status, code=error.code)


def _reference_packet(result, match):
    return {"protocol": "sol.reference", "version": 1,
            "corpus": result["corpus"], "generation": result["generation"],
            "reference": {"requested_id": match["id"], "target_id": match["id"], "chain": [match["id"]],
                          **{key: match[key] for key in ("content_sha256", "type", "sources", "attribution")}}}


def _reader_doctrine(value):
    if not isinstance(value, str) or not value.startswith("/") or "\\" in value:
        return None
    parts = value.split("/")[1:]
    if (len(parts) < 2 or parts[0] not in _DOCTRINES or not parts[-1].endswith(".txt")
            or any(part in {"", ".", ".."} for part in parts)
            or any(part.endswith(".txt") for part in parts[:-1])):
        return None
    return parts[0]


def _stats(value, label):
    _keys(value, _STATS, label)
    for field in _STATS - {"rate_per_10000_tokens"}:
        _integer(value[field], field)
    rate = value["rate_per_10000_tokens"]
    expected = round(value["occurrences"] * 10000 / value["token_count"], 6) if value["token_count"] else None
    if ((expected is None and rate is not None) or (expected is not None
            and (type(rate) is not float or not math.isfinite(rate) or rate != expected))):
        raise TermExperimentError("Term-study rate disagrees with its counts", code="invalid_number")
    if value["matching_passages"] > value["passage_count"] or value["occurrences"] > value["token_count"]:
        raise TermExperimentError("Term-study counts are inconsistent", code="invalid_number")


def _validate(result):
    result = _json_value(result)
    _keys(result, {"protocol", "version", "corpus", "generation", "method", "query", "doctrine", "limit",
                   "origin", "totals", "groups", "exclusions", "matches", "matches_truncated"}, "Term-study envelope")
    if result["protocol"] != "sol.term-study" or type(result["version"]) is not int or result["version"] != 1:
        raise TermExperimentError("Unsupported SOL term-study protocol or version", code="unsupported_version")
    _keys(result["method"], _METHOD, "Method")
    if _json(result["method"]) != _json(_METHOD):
        raise TermExperimentError("Unsupported term-study method or runtime Unicode version", code="unsupported_method")
    if _options(result["query"], result["doctrine"], result["limit"]) != result["query"]:
        raise TermExperimentError("Stored query must already be normalized", code="invalid_query")
    _validate_binding(result)
    _stats(result["totals"], "Totals")
    groups = result["groups"]
    if not isinstance(groups, list) or len(groups) != 3:
        raise TermExperimentError("Term study needs three ordered doctrine groups", code="invalid_groups")
    for doctrine, group in zip(_DOCTRINES, groups):
        _keys(group, _STATS | {"doctrine"}, "Doctrine group")
        if group["doctrine"] != doctrine:
            raise TermExperimentError("Doctrine groups must be ordered BEING, ESSENCE, CONCEPT", code="invalid_groups")
        _stats({key: group[key] for key in _STATS}, "Doctrine counts")
    exclusions = result["exclusions"]
    _keys(exclusions, {"input_records", "excluded_records", "by_reason", "masked_facsimile_captions",
                       "masked_facsimile_tokens"}, "Exclusions")
    for field in ("input_records", "excluded_records", "masked_facsimile_captions", "masked_facsimile_tokens"):
        _integer(exclusions[field], field)
    _keys(exclusions["by_reason"], _REASONS, "Exclusion reasons")
    for reason, count in exclusions["by_reason"].items():
        _integer(count, reason)
    if (sum(exclusions["by_reason"].values()) != exclusions["excluded_records"]
            or exclusions["input_records"] != exclusions["excluded_records"] + result["totals"]["passage_count"]):
        raise TermExperimentError("Exclusion counts are inconsistent", code="invalid_number")
    matches = result["matches"]
    if not isinstance(matches, list) or len(matches) > result["limit"] or type(result["matches_truncated"]) is not bool:
        raise TermExperimentError("Invalid bounded matches", code="invalid_matches")
    seen = set()
    for match in matches:
        _keys(match, {"id", "content_sha256", "type", "reader_path", "sources", "attribution", "occurrences",
                      "first_match"}, "Match")
        _integer(match["occurrences"], "match occurrences", 1)
        if (not isinstance(match["type"], str) or match["type"] not in _TYPES
                or _reader_doctrine(match["reader_path"]) is None):
            raise TermExperimentError("Match is not in the selected main-text reader view", code="invalid_matches")
        try:
            core.decode_reference(_json(_reference_packet(result, match)))
        except core.ProtocolError as error:
            raise _core_error(error) from error
        if match["id"] in seen:
            raise TermExperimentError("Match IDs must be distinct", code="invalid_matches")
        seen.add(match["id"])
        first = match["first_match"]
        _keys(first, {"start", "end", "context_start", "context_end", "context"}, "First match")
        for field in ("start", "end", "context_start", "context_end"):
            _integer(first[field], field)
        if (not isinstance(first["context"], str) or not first["context_start"] <= first["start"] < first["end"] <= first["context_end"]
                or first["start"] - first["context_start"] > 80 or first["context_end"] - first["end"] > 80
                or len(first["context"]) != first["context_end"] - first["context_start"]
                or _query(first["context"][first["start"] - first["context_start"]:first["end"] - first["context_start"]]) != result["query"]):
            raise TermExperimentError("Invalid first-match context or offsets", code="invalid_matches")
    if result["origin"] is not None:
        try:
            result["origin"] = core.decode_reference(_json(result["origin"]))
        except core.ProtocolError as error:
            raise _core_error(error) from error
    if len(_json(result).encode("utf-8")) > MAX_RESULT_BYTES:
        raise TermExperimentError("Term study exceeds 1 MiB", code="size_limit")
    return result


def _facsimile_spans(record):
    """Mask only exact trailing labels produced by this corpus's converter.

    This is not Markdown parsing: ordinary images, inline labels, and earlier
    identical prose are retained. Unsupported image layouts are not guessed at.
    """
    markdown = record["markdown"].rstrip()
    plain = record["plain_text"]
    end = len(plain)
    spans = []
    source_labels = {(str(source["printed_page"]), f"{record['id']}-{source['pdf_page']}.png")
                     for source in record["sources"]}
    while True:
        image = re.search(r"(?:^|\n)\!\[(Source facsimile, printed page ([^\]\r\n]*))\]\(([^)\r\n]*)\)$", markdown)
        if not image:
            break
        if (image[2], posixpath.basename(image[3])) not in source_labels:
            break
        end = len(plain[:end].rstrip())
        label = image[1]
        start = end - len(label)
        if start < 0 or plain[start:end] != label or (start > 0 and plain[start - 1] != "\n"):
            break
        spans.append((start, end))
        end = start
        markdown = markdown[:image.start()].rstrip()
    return spans


def _selection(record, doctrine):
    attribution = record["attribution"]
    if attribution["author"] != "G. W. F. Hegel" or attribution["role"] != "main_text":
        return None, "attribution"
    if record["type"] not in _TYPES or record.get("generated_text") is True:
        return None, "record_type"
    if record.get("transcription_status") in {"needs_review", "needs_visual_review"}:
        return None, "review"
    name = _reader_doctrine(record.get("reader_path"))
    if name is None:
        return None, "reader_path"
    if doctrine is not None and name != doctrine:
        return None, "doctrine"
    return name, None


def _empty_stats():
    return {"passage_count": 0, "token_count": 0, "matching_passages": 0,
            "occurrences": 0, "rate_per_10000_tokens": None}


def _analyze(snapshot, query, origin, doctrine, limit):
    binding = _binding(snapshot)
    if origin is not None:
        try:
            origin = core.decode_reference(_json(_json_value(origin)))
            core.check_reference(snapshot, origin)
        except core.ProtocolError as error:
            raise _core_error(error) from error
    groups = [{"doctrine": name, **_empty_stats()} for name in _DOCTRINES]
    by_doctrine = {group["doctrine"]: group for group in groups}
    exclusions = {"input_records": len(snapshot.records), "excluded_records": 0,
                  "by_reason": {reason: 0 for reason in _REASONS},
                  "masked_facsimile_captions": 0, "masked_facsimile_tokens": 0}
    matches = []
    for record in snapshot.records:
        name, reason = _selection(record, doctrine)
        if reason:
            exclusions["excluded_records"] += 1
            exclusions["by_reason"][reason] += 1
            continue
        group = by_doctrine[name]
        group["passage_count"] += 1
        masks = _facsimile_spans(record)
        exclusions["masked_facsimile_captions"] += len(masks)
        occurrences = 0
        first = None
        for token, start, end in _tokens(record["plain_text"]):
            if any(mask_start <= start and end <= mask_end for mask_start, mask_end in masks):
                exclusions["masked_facsimile_tokens"] += 1
                continue
            group["token_count"] += 1
            if token == query:
                occurrences += 1
                if first is None:
                    left, right = max(0, start - 80), min(len(record["plain_text"]), end + 80)
                    first = {"start": start, "end": end, "context_start": left, "context_end": right,
                             "context": record["plain_text"][left:right]}
        group["occurrences"] += occurrences
        if occurrences:
            group["matching_passages"] += 1
            if len(matches) < limit:
                matches.append({"id": record["id"], "content_sha256": record["content_sha256"],
                                "type": record["type"], "reader_path": record["reader_path"],
                                "sources": [{key: value for key, value in source.items()
                                             if key in {"pdf_page", "printed_page", "bbox"}} for source in record["sources"]],
                                "attribution": {key: record["attribution"][key] for key in ("author", "role", "status")},
                                "occurrences": occurrences, "first_match": first})
    totals = _empty_stats()
    for field in _STATS - {"rate_per_10000_tokens"}:
        totals[field] = sum(group[field] for group in groups)
    for counts in [totals, *groups]:
        if counts["token_count"]:
            counts["rate_per_10000_tokens"] = round(counts["occurrences"] * 10000 / counts["token_count"], 6)
    result = _validate({"protocol": "sol.term-study", "version": 1, **binding, "method": dict(_METHOD),
                        "query": query, "doctrine": doctrine, "limit": limit, "origin": origin,
                        "totals": totals, "groups": groups, "exclusions": exclusions, "matches": matches,
                        "matches_truncated": totals["matching_passages"] > len(matches)})
    _current(snapshot)
    return result


def analyze_term(snapshot, query, *, origin=None, doctrine=None, limit=10):
    """Count one literal normalized word, with bounded representative matches."""
    normalized = _options(query, doctrine, limit)
    return _analyze(_fresh(snapshot), normalized, origin, doctrine, limit)


def check_term_result(snapshot, result):
    """Recompute; return fresh data only after exact typed/schema agreement."""
    result = _validate(result)
    fresh = _fresh(snapshot)
    expected_binding = _binding(fresh)
    for field, code in (("id", "corpus_mismatch"), ("edition_sha256", "edition_mismatch"), ("source", "source_mismatch")):
        if result["corpus"][field] != expected_binding["corpus"][field]:
            raise TermExperimentError("Term study belongs to another corpus, edition or source",
                                      status="mismatch", code=code)
    if result["generation"] != expected_binding["generation"]:
        raise TermExperimentError("Term study belongs to another corpus generation",
                                  status="stale", code="generation_changed")
    expected = _analyze(fresh, result["query"], result["origin"], result["doctrine"], result["limit"])
    if _json(result) != _json(expected):
        raise TermExperimentError("Term-study counts, examples or provenance disagree with recomputation",
                                  status="mismatch", code="result_mismatch")
    _current(fresh)
    return expected


def decode_term_result(data):
    """Decode one bounded UTF-8 result; duplicate/nonfinite fields are refused."""
    try:
        raw = data.encode("utf-8") if isinstance(data, str) else data
        if not isinstance(raw, bytes):
            raise TermExperimentError("Term-study input must be UTF-8 bytes or text", code="invalid_json")
        if len(raw) > MAX_RESULT_BYTES:
            raise TermExperimentError("Term study exceeds 1 MiB", code="size_limit")
        text = raw.decode("utf-8")
    except UnicodeError as error:
        raise TermExperimentError("Term-study input is not valid UTF-8", code="invalid_utf8") from error

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise TermExperimentError("Duplicate term-study JSON field", code="duplicate_field")
            result[key] = value
        return result

    def nonfinite(value):
        raise TermExperimentError("Term-study JSON requires finite numbers", code="invalid_json")

    try:
        result = json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, RecursionError) as error:
        if isinstance(error, TermExperimentError):
            raise
        raise TermExperimentError("Invalid term-study JSON", code="invalid_json") from error
    return _validate(result)


def encode_term_result(result):
    """Produce inert ASCII JSON, bounded including a caller's final newline."""
    text = json.dumps(_validate(result), ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)
    if len(text.encode("utf-8")) + 1 > MAX_RESULT_BYTES:
        raise TermExperimentError("Formatted term study exceeds 1 MiB", code="size_limit")
    return text
