"""Deterministic, interface-independent word frequencies and strict artifacts.

Artifacts contain a vocabulary and aggregate counts, never passage text, token
sequences or contexts. Locations retain only the first occurrence per input row.
"""
from __future__ import annotations

from collections import Counter
import json
import math
import re
import unicodedata
import uuid

from sol.essence.tokenization import NORMALIZATION, TOKENIZATION, word_tokens
from sol.essence.word_inputs import CoreProvider, FileProvider, WordStudyError, _scope, load_input


MAX_RESULT_BYTES = 16 * 1024 * 1024
_METHOD = {
    "algorithm": "word-frequencies-v1", "tokenization": TOKENIZATION,
    "normalization": NORMALIZATION, "unicode_version": unicodedata.unidata_version,
    "core_projection": "hegel-main-text-no-pending-flags-three-doctrines-v1",
    "facsimile": "trailing-converter-image-labels-v1",
    "file_projection": "verbatim-utf8-v1",
    "scope_policy": "whole-tokens-contained-in-half-open-codepoint-span-v1",
    "locations": "input-index,count,first-start,first-end",
    "order": "descending-target-count-then-normalized-word",
    "rate": "per-10000-tokens-rounded-to-6-decimals;null-if-denominator-zero",
}


def _json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise WordStudyError("Unexpected word-study fields", code="invalid_fields")


def _integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= 2 ** 63 - 1:
        raise WordStudyError("Invalid word-study count or offset", code="invalid_number")


def _digest(value):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise WordStudyError("Expected a lowercase SHA-256 digest", code="invalid_digest")


def _json_value(value, depth=0):
    if depth > 64:
        raise WordStudyError("Word-study JSON exceeds 64 nesting levels", code="nesting_limit")
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise WordStudyError("Word-study strings must be valid UTF-8", code="invalid_utf8") from error
    elif value is None or type(value) in (bool, int):
        pass
    elif type(value) is float and math.isfinite(value):
        pass
    elif isinstance(value, list):
        for item in value:
            _json_value(item, depth + 1)
    elif isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for key, item in value.items():
            _json_value(key, depth + 1)
            _json_value(item, depth + 1)
    else:
        raise WordStudyError("Word study requires finite JSON values", code="invalid_json")


def _validate_input(value):
    _keys(value, {"provider", "binding", "scope", "inputs", "summary", "exclusions"})
    provider = value["provider"]
    if provider not in ("core", "file"):
        raise WordStudyError("Unsupported word-study provider", code="invalid_provider")
    _scope(value["scope"], provider)
    binding = value["binding"]
    if provider == "file":
        _keys(binding, {"sha256", "bytes"})
        _digest(binding["sha256"])
        _integer(binding["bytes"])
    else:
        _keys(binding, {"corpus", "generation"})
        corpus = binding["corpus"]
        _keys(corpus, {"id", "edition_sha256", "source"})
        try:
            valid = isinstance(corpus["id"], str) and str(uuid.UUID(corpus["id"])) == corpus["id"]
        except ValueError:
            valid = False
        if not valid:
            raise WordStudyError("CORE binding requires a canonical UUID", code="invalid_identifier")
        _digest(corpus["edition_sha256"])
        _keys(corpus["source"], {"sha256", "pdf_pages"})
        _digest(corpus["source"]["sha256"])
        _integer(corpus["source"]["pdf_pages"], 1)
        _keys(binding["generation"], {"manifest_sha256", "index_sha256"})
        for digest in binding["generation"].values():
            _digest(digest)
    _keys(value["summary"], {"token_count", "type_count", "input_count"})
    for count in value["summary"].values():
        _integer(count)
    inputs = value["inputs"]
    if not isinstance(inputs, list) or value["summary"]["input_count"] != len(inputs):
        raise WordStudyError("Invalid input rows", code="invalid_inputs")
    for row in inputs:
        fields = {"span", "text_sha256", "token_count"}
        _keys(row, fields | ({"id", "content_sha256", "reader_path", "sources", "attribution"}
                             if provider == "core" else set()))
        _digest(row["text_sha256"])
        span = row["span"]
        if not isinstance(span, list) or len(span) != 2:
            raise WordStudyError("Invalid input span", code="invalid_inputs")
        for offset in span:
            _integer(offset)
        if span[0] > span[1]:
            raise WordStudyError("Reversed input span", code="invalid_inputs")
        _integer(row["token_count"])
        if provider == "core":
            _digest(row["content_sha256"])
            if not isinstance(row["id"], str) or not isinstance(row["reader_path"], str):
                raise WordStudyError("Invalid source identity", code="invalid_inputs")
            if not isinstance(row["sources"], list):
                raise WordStudyError("Invalid source pages", code="invalid_inputs")
            for source in row["sources"]:
                if not isinstance(source, dict) or not {"pdf_page", "printed_page"} <= source.keys() or source.keys() - {"pdf_page", "printed_page", "bbox"}:
                    raise WordStudyError("Invalid source page fields", code="invalid_inputs")
                _integer(source["pdf_page"], 1)
                if source["printed_page"] is not None and not isinstance(source["printed_page"], str):
                    raise WordStudyError("Invalid printed page", code="invalid_inputs")
                if "bbox" in source and (not isinstance(source["bbox"], list) or len(source["bbox"]) != 4
                        or any(type(number) not in (int, float) for number in source["bbox"])):
                    raise WordStudyError("Invalid source crop", code="invalid_inputs")
            _keys(row["attribution"], {"author", "role", "status"})
            if not all(isinstance(item, str) for item in row["attribution"].values()):
                raise WordStudyError("Invalid attribution", code="invalid_inputs")
    _keys(value["exclusions"], {"by_reason", "masked_tokens"})
    reasons = value["exclusions"]["by_reason"]
    _keys(reasons, {"scope", "attribution", "record_type", "review", "reader_path"} if provider == "core" else set())
    for count in [*reasons.values(), value["exclusions"]["masked_tokens"]]:
        _integer(count)
    if sum(row["token_count"] for row in inputs) != value["summary"]["token_count"]:
        raise WordStudyError("Input counts disagree with the denominator", code="invalid_number")


def _validate(result):
    _json_value(result)
    _keys(result, {"protocol", "version", "method", "target", "reference", "frequencies", "warnings"})
    if result["protocol"] != "sol.word-frequencies" or type(result["version"]) is not int or result["version"] != 1:
        raise WordStudyError("Unsupported word-frequency artifact version", code="unsupported_version")
    if _json(result["method"]) != _json(_METHOD):
        raise WordStudyError("Unsupported tokenizer, method or Unicode runtime", code="unsupported_method")
    _validate_input(result["target"])
    if result["reference"] is not None:
        _validate_input(result["reference"])
    if not isinstance(result["warnings"], list) or not all(isinstance(warning, str) for warning in result["warnings"]):
        raise WordStudyError("Invalid warnings", code="invalid_fields")
    frequencies = result["frequencies"]
    if not isinstance(frequencies, list):
        raise WordStudyError("Invalid frequency table", code="invalid_fields")
    words = set()
    totals, types = Counter(), Counter()
    row_totals = {name: Counter() for name in ("target", "reference")}
    for row in frequencies:
        _keys(row, {"word", "target", "reference"})
        word = row["word"]
        if (not isinstance(word, str) or list(word_tokens(word)) != [(word, 0, len(word))] or word in words):
            raise WordStudyError("Frequency words must be distinct normalized tokens", code="invalid_word")
        words.add(word)
        for name in ("target", "reference"):
            source, cell = result[name], row[name]
            if source is None:
                if cell is not None:
                    raise WordStudyError("Unexpected reference counts", code="invalid_fields")
                continue
            _keys(cell, {"count", "denominator", "rate_per_10000_tokens", "locations"})
            _integer(cell["count"])
            _integer(cell["denominator"])
            denominator = source["summary"]["token_count"]
            rate = round(cell["count"] * 10000 / denominator, 6) if denominator else None
            if (cell["denominator"] != denominator or cell["count"] > denominator
                    or _json(cell["rate_per_10000_tokens"]) != _json(rate)):
                raise WordStudyError("Frequency rate disagrees with its denominator", code="invalid_number")
            if not isinstance(cell["locations"], list):
                raise WordStudyError("Invalid word locations", code="invalid_inputs")
            count, previous = 0, -1
            for location in cell["locations"]:
                if not isinstance(location, list) or len(location) != 4:
                    raise WordStudyError("Invalid word location", code="invalid_inputs")
                for number in location:
                    _integer(number)
                index, occurrences, start, end = location
                if (not previous < index < len(source["inputs"]) or occurrences < 1
                        or not source["inputs"][index]["span"][0] <= start < end <= source["inputs"][index]["span"][1]):
                    raise WordStudyError("Word location falls outside its input span", code="invalid_inputs")
                previous, count = index, count + occurrences
                row_totals[name][index] += occurrences
            if count != cell["count"]:
                raise WordStudyError("Location counts disagree", code="invalid_number")
            totals[name] += count
            types[name] += bool(count)
        if not row["target"]["count"] and not (row["reference"] and row["reference"]["count"]):
            raise WordStudyError("Frequency row has no occurrences", code="invalid_number")
    for name in ("target", "reference"):
        source = result[name]
        if source is not None and (source["summary"]["token_count"] != totals[name]
                or source["summary"]["type_count"] != types[name]
                or any(row["token_count"] != row_totals[name][index] for index, row in enumerate(source["inputs"]))):
            raise WordStudyError("Frequency totals disagree", code="invalid_number")
    if frequencies != sorted(frequencies, key=lambda row: (-row["target"]["count"], row["word"])):
        raise WordStudyError("Frequency rows are out of order", code="invalid_inputs")
    if len(_json(result).encode()) + 1 > MAX_RESULT_BYTES:
        raise WordStudyError("Word study exceeds 16 MiB", code="size_limit")
    return result


def _count(loaded):
    totals, locations, inputs = Counter(), {}, []
    for index, row in enumerate(loaded.rows):
        counts, first = Counter(), {}
        for word, start, end in word_tokens(row["text"]):
            if not row["span"][0] <= start < end <= row["span"][1]:
                continue
            if any(left <= start and end <= right for left, right in row["masks"]):
                loaded.exclusions["masked_tokens"] += 1
                continue
            counts[word] += 1
            first.setdefault(word, (start, end))
        totals.update(counts)
        for word, count in counts.items():
            locations.setdefault(word, []).append([index, count, *first[word]])
        inputs.append({key: value for key, value in row.items() if key not in {"text", "masks"}}
                      | {"token_count": sum(counts.values())})
    return {"provider": loaded.provider, "binding": loaded.binding, "scope": loaded.scope,
            "inputs": inputs, "summary": {"token_count": sum(totals.values()), "type_count": len(totals),
                                          "input_count": len(inputs)}, "exclusions": loaded.exclusions}, totals, locations


def analyze_words(target: CoreProvider | FileProvider, *, reference: CoreProvider | FileProvider | None = None) -> dict:
    """Count target and optional independent reference through the same tokenizer.

    Returns the sol.word-frequencies v1 artifact: method, target/reference
    bindings, scopes, text-free inputs and summaries, union frequency rows and
    warnings. A cell's locations are [input_index, count, first_start, first_end].
    No persistence, interface, corpus or workspace mutation occurs.
    """
    target_input = load_input(target)
    reference_input = load_input(reference) if reference is not None else None
    target_result, counts, locations = _count(target_input)
    reference_result, other, other_locations = _count(reference_input) if reference_input is not None else (None, Counter(), {})

    def cell(word, summary, counts, locations):
        denominator = summary["summary"]["token_count"]
        count = counts[word]
        return {"count": count, "denominator": denominator,
                "rate_per_10000_tokens": round(count * 10000 / denominator, 6) if denominator else None,
                "locations": locations.get(word, [])}

    warnings = []
    if reference_result is not None:
        warnings.append("Lexical rates describe these inputs; they do not establish conceptual similarity or statistical significance.")
        if target_result["summary"]["token_count"] != reference_result["summary"]["token_count"]:
            warnings.append("Unequal token denominators: raw counts are not directly comparable; use the displayed rates.")
        if target_result["provider"] != reference_result["provider"]:
            warnings.append("CORE filters eligible Hegel prose; file input is verbatim. These projections differ.")
        elif target_result["binding"] != reference_result["binding"]:
            warnings.append("Different source bindings: check edition, language and translation before interpreting rates.")
    for name, summary in (("target", target_result), ("reference", reference_result)):
        if summary is not None and not summary["summary"]["token_count"]:
            warnings.append(f"The {name} has zero tokens; its rates are undefined (null).")
    frequencies = [{"word": word, "target": cell(word, target_result, counts, locations),
                    "reference": cell(word, reference_result, other, other_locations) if reference_result is not None else None}
                   for word in sorted(counts.keys() | other.keys(), key=lambda word: (-counts[word], word))]
    result = _validate({"protocol": "sol.word-frequencies", "version": 1, "method": dict(_METHOD),
                        "target": target_result, "reference": reference_result,
                        "frequencies": frequencies, "warnings": warnings})
    target_input.verify_current()
    if reference_input is not None:
        reference_input.verify_current()
    return result


def check_word_result(target: CoreProvider | FileProvider, result: dict, *, reference: CoreProvider | FileProvider | None = None) -> dict:
    """Strict recomputation with caller-supplied sources; never open artifact paths.

    Provider scopes must agree with the artifact. Changed unselected CORE text
    or file bytes invalidate the full binding, even when counts are unchanged.
    """
    _validate(result)
    expected = analyze_words(target, reference=reference)
    for name in ("target", "reference"):
        old, new = result[name], expected[name]
        if (old is None) != (new is None) or old is not None and old["provider"] != new["provider"]:
            raise WordStudyError("Study providers disagree", status="mismatch", code="provider_mismatch")
        if old is not None and old["binding"] != new["binding"]:
            raise WordStudyError("Word study belongs to changed source bytes or another corpus generation",
                                 status="stale", code="file_changed" if old["provider"] == "file" else "generation_changed")
    if _json(result) != _json(expected):
        raise WordStudyError("Word study disagrees with exact recomputation", status="mismatch", code="result_mismatch")
    return expected


def decode_word_result(data: bytes | str) -> dict:
    """Decode bounded, strict UTF-8 JSON without importing CORE."""
    try:
        raw = data.encode("utf-8") if isinstance(data, str) else data
        if not isinstance(raw, bytes):
            raise WordStudyError("Expected UTF-8 bytes or text", code="invalid_json")
        if len(raw) > MAX_RESULT_BYTES:
            raise WordStudyError("Word study exceeds 16 MiB", code="size_limit")
        text = raw.decode("utf-8")
    except UnicodeError as error:
        raise WordStudyError("Word-study input must be UTF-8", code="invalid_utf8") from error

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise WordStudyError("Duplicate word-study JSON field", code="duplicate_field")
            result[key] = value
        return result

    def nonfinite(value):
        raise WordStudyError("Word study requires finite numbers", code="invalid_json")

    try:
        result = json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, RecursionError) as error:
        if isinstance(error, WordStudyError):
            raise
        raise WordStudyError("Invalid word-study JSON", code="invalid_json") from error
    return _validate(result)


def encode_word_result(result: dict) -> str:
    """Return inert deterministic JSON, bounded including the final newline."""
    return _json(_validate(result))
