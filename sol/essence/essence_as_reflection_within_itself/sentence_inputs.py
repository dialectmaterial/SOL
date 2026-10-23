"""Provider-based sentence studies; original v1 snapshot studies stay unchanged.

Segment the original text before applying a scope. Only complete sentence spans
contained in that scope are measured; offsets always address the original text.
Files have one input row, so positional statistics describe that row, not inferred
paragraphs. No text or local path is serialized and no saved path is opened.
"""
from __future__ import annotations

import re
import uuid

import json

from sol.essence.essence_as_reflection_within_itself.sentences import PROVIDER_MAX_RESULT_BYTES, SentenceStudyError, _METHOD, _measure, segment, segment_v2
from sol.essence.essence_as_reflection_within_itself.tokenization import word_tokens
from sol.essence.essence_as_reflection_within_itself.validation import _integer, _json, _json_value, _keys, _validate_binding
from sol.essence.essence_as_reflection_within_itself.word_inputs import CoreProvider, FileProvider, WordStudyError, _scope, load_input


METHOD = {**_METHOD, "algorithm": "sentence-length-distribution-providers-v1",
          "selection": "word-study-core-file-providers-v1",
          "core_projection": "hegel-main-text-no-pending-flags-three-doctrines-v1",
          "file_projection": "verbatim-utf8-v1",
          "order": "provider-input-order",
          "scope_policy": "whole-sentences-contained-in-half-open-codepoint-span-v1",
          "position_unit": "retained sentences in each input row; one row per CORE record or whole file"}
# Artifact protocol v2 is independent of the punctuation-method version.
METHOD_V2 = {**METHOD, "algorithm": "sentence-length-distribution-providers-v2",
             "segmentation": "punctuation-rules-v2: v1 except line-leading Arabic integer-plus-period list markers"
                             " stay with their item; attached bare, square-bracketed or superscript numeric"
                             " footnote callouts stay with preceding punctuation (never after a decimal point)"}
_METHODS = {"punctuation-rules-v1": METHOD, "punctuation-rules-v2": METHOD_V2}


def _segmentation(method):
    for name, declared in _METHODS.items():
        if _json(method) == _json(declared):
            return name
    raise SentenceStudyError("Unsupported sentence-study method or Unicode runtime", code="unsupported_method")


_CORE_FIELDS = {"id", "content_sha256", "reader_path", "sources", "attribution"}
_REASONS = {"scope", "attribution", "record_type", "review", "reader_path"}


def _refusal(error):
    return SentenceStudyError(str(error), status=error.status, code=error.code)


def _origin(provider, origin):
    if origin is None:
        return None
    if not isinstance(provider, CoreProvider):
        raise SentenceStudyError("A file study cannot have a CORE reference anchor", code="invalid_origin")
    from sol import core

    try:
        origin = core.decode_reference(_json(_json_value(origin)))
        core.check_reference(provider.snapshot, origin)
        return origin
    except core.ProtocolError as error:
        raise _refusal(error) from error


def _analyze(loaded, origin, segmentation="punctuation-rules-v1"):
    splitter = segment if segmentation == "punctuation-rules-v1" else segment_v2
    inputs, rows = [], []
    exclusions = {"by_reason": loaded.exclusions["by_reason"], "empty_segments": 0,
                  "outside_span": 0, "masked_segments": 0}
    for item in loaded.rows:
        index = len(inputs)
        metadata = {key: value for key, value in item.items() if key not in {"text", "masks"}}
        metadata["sentences"] = 0
        for start, end in splitter(item["text"]):
            if any(left <= start and end <= right for left, right in item["masks"]):
                exclusions["masked_segments"] += 1
                continue
            if start < item["span"][0] or end > item["span"][1]:
                exclusions["outside_span"] += 1
                continue
            tokens = sum(1 for _ in word_tokens(item["text"][start:end]))
            if not tokens:
                exclusions["empty_segments"] += 1
                continue
            rows.append([index, start, end, tokens])
            metadata["sentences"] += 1
        inputs.append(metadata)
    result = {"protocol": "sol.sentence-study", "version": 2, "method": _METHODS[segmentation],
              "input": {"provider": loaded.provider, "binding": loaded.binding,
                        "scope": loaded.scope, "inputs": inputs}, "origin": origin,
              **_measure(inputs, rows), "sentences": rows, "exclusions": exclusions}
    result = validate_result(result)
    loaded.verify_current()
    return result


def analyze_provider(provider, *, origin=None, segmentation="punctuation-rules-v1"):
    """Return a v2 study from the word engine's CoreProvider or FileProvider."""
    try:
        # Reject a foreign anchor before opening any file.
        origin = _origin(provider, origin)
        return _analyze(load_input(provider), origin, segmentation)
    except WordStudyError as error:
        raise _refusal(error) from error


def _digest(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise SentenceStudyError("Expected a lowercase SHA-256 digest", code="invalid_digest")


def _uuid(value):
    try:
        valid = isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise SentenceStudyError("Expected a canonical record UUID", code="invalid_identifier")


def validate_result(result):
    """Validate inert v2 data without opening sources or importing CORE for files."""
    result = _json_value(result)
    _keys(result, {"protocol", "version", "method", "input", "origin", "summary", "histogram",
                   "by_position", "longest", "sentences", "exclusions"}, "Provider sentence study")
    if result["protocol"] != "sol.sentence-study" or type(result["version"]) is not int or result["version"] != 2:
        raise SentenceStudyError("Unsupported provider sentence-study version", code="unsupported_version")
    _segmentation(result["method"])
    part = result["input"]
    _keys(part, {"provider", "binding", "scope", "inputs"}, "Sentence input")
    provider = part["provider"]
    if provider not in ("core", "file"):
        raise SentenceStudyError("Unknown sentence input provider", code="invalid_provider")
    try:
        _scope(part["scope"], provider)
    except WordStudyError as error:
        raise _refusal(error) from error
    if provider == "core":
        _keys(part["binding"], {"corpus", "generation"}, "CORE binding")
        _validate_binding(part["binding"])
    else:
        _keys(part["binding"], {"sha256", "bytes"}, "File binding")
        _digest(part["binding"]["sha256"])
        _integer(part["binding"]["bytes"], "file byte count")
        if result["origin"] is not None:
            raise SentenceStudyError("A file study cannot have a CORE reference anchor", code="invalid_origin")
    inputs, rows = part["inputs"], result["sentences"]
    if not isinstance(inputs, list) or not isinstance(rows, list) or provider == "file" and len(inputs) != 1:
        raise SentenceStudyError("Invalid sentence input rows", code="invalid_rows")
    ids = set()
    for item in inputs:
        _keys(item, {"span", "text_sha256", "sentences"} | (_CORE_FIELDS if provider == "core" else set()),
              "Sentence input row")
        _digest(item["text_sha256"])
        _integer(item["sentences"], "input sentence count")
        span = item["span"]
        if not isinstance(span, list) or len(span) != 2:
            raise SentenceStudyError("Expected a half-open codepoint span", code="invalid_scope")
        for value in span:
            _integer(value, "span codepoint")
        if span[0] > span[1]:
            raise SentenceStudyError("Reversed sentence scope", code="invalid_scope")
        if provider == "core":
            _uuid(item["id"])
            if item["id"] in ids:
                raise SentenceStudyError("Duplicate sentence input ID", code="invalid_rows")
            ids.add(item["id"])
            _digest(item["content_sha256"])
            if not isinstance(item["reader_path"], str) or not isinstance(item["sources"], list):
                raise SentenceStudyError("Invalid CORE source locations", code="invalid_rows")
            for source in item["sources"]:
                if (not isinstance(source, dict) or not {"pdf_page", "printed_page"} <= source.keys()
                        or source.keys() - {"pdf_page", "printed_page", "bbox"}):
                    raise SentenceStudyError("Invalid CORE source page fields", code="invalid_rows")
                _integer(source["pdf_page"], "PDF page", 1)
                if source["printed_page"] is not None and not isinstance(source["printed_page"], str):
                    raise SentenceStudyError("Invalid printed page", code="invalid_rows")
                if "bbox" in source and (not isinstance(source["bbox"], list) or len(source["bbox"]) != 4
                        or any(type(number) not in (int, float) for number in source["bbox"])):
                    raise SentenceStudyError("Invalid source crop", code="invalid_rows")
            _keys(item["attribution"], {"author", "role", "status"}, "Attribution")
            if not all(isinstance(value, str) for value in item["attribution"].values()):
                raise SentenceStudyError("Invalid source attribution", code="invalid_rows")
    counts = [0] * len(inputs)
    previous = None
    for row in rows:
        if not isinstance(row, list) or len(row) != 4:
            raise SentenceStudyError("A sentence row is [input, start, end, tokens]", code="invalid_rows")
        for value in row:
            _integer(value, "sentence row value")
        index, start, end, tokens = row
        if (index >= len(inputs) or not inputs[index]["span"][0] <= start < end <= inputs[index]["span"][1]
                or tokens < 1 or previous is not None and (index, start) <= (previous[0], previous[2] - 1)):
            raise SentenceStudyError("Sentence rows must be ordered, contained and nonempty", code="invalid_rows")
        counts[index] += 1
        previous = row
    if counts != [item["sentences"] for item in inputs]:
        raise SentenceStudyError("Sentence counts disagree with input rows", code="invalid_rows")
    for key, expected in _measure(inputs, rows).items():
        if _json(result[key]) != _json(expected):
            raise SentenceStudyError("Sentence statistics disagree with their rows", code="invalid_statistics")
    excluded = result["exclusions"]
    _keys(excluded, {"by_reason", "empty_segments", "outside_span", "masked_segments"}, "Sentence exclusions")
    _keys(excluded["by_reason"], _REASONS if provider == "core" else set(), "Excluded records")
    for count in [*excluded["by_reason"].values(), excluded["empty_segments"], excluded["outside_span"], excluded["masked_segments"]]:
        _integer(count, "excluded count")
    if result["origin"] is not None:
        from sol import core
        try:
            result["origin"] = core.decode_reference(_json(result["origin"]))
        except core.ProtocolError as error:
            raise _refusal(error) from error
    if len(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)) > PROVIDER_MAX_RESULT_BYTES:
        raise SentenceStudyError("Provider sentence study exceeds 16 MiB", code="size_limit")
    return result


def check_provider_result(provider, result):
    """Recompute using the caller's provider; artifact metadata grants no access."""
    result = validate_result(result)
    try:
        loaded = load_input(provider)
        part = result["input"]
        if loaded.provider != part["provider"]:
            raise SentenceStudyError("The sentence input provider differs", status="mismatch", code="provider_mismatch")
        if loaded.binding != part["binding"]:
            file = loaded.provider == "file"
            corpus_changed = not file and loaded.binding["corpus"] != part["binding"]["corpus"]
            raise SentenceStudyError("The sentence input changed or belongs to another source",
                                     status="mismatch" if corpus_changed else "stale",
                                     code="file_changed" if file else "corpus_mismatch" if corpus_changed else "generation_changed")
        if loaded.scope != part["scope"]:
            raise SentenceStudyError("The sentence input scope differs", status="mismatch", code="scope_mismatch")
        expected = _analyze(loaded, _origin(provider, result["origin"]), _segmentation(result["method"]))
        if _json(result) != _json(expected):
            raise SentenceStudyError("Sentence rows, statistics or provenance disagree with recomputation",
                                     status="mismatch", code="result_mismatch")
        return expected
    except WordStudyError as error:
        raise _refusal(error) from error
