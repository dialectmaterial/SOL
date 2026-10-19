"""Sentence lengths in the English translation, not a model of Hegel's syntax.

Sentences are found by declared, deterministic punctuation rules and measured
in the term study's word tokens. A result stores record IDs, source offsets and
digests, never book text, so it can be checked by recomputation and every
sentence can be reopened at its exact place. It grants no workspace authority.
"""
from __future__ import annotations

import json
import math
import re
import statistics
import unicodedata

from sol.essence.word_inputs import CoreProvider, FileProvider
from sol.essence.tokenization import word_tokens as _tokens
from sol.essence.validation import TermExperimentError, _integer, _json, _json_value, _keys, _validate_binding


MAX_RESULT_BYTES = 1048576
PROVIDER_MAX_RESULT_BYTES = 16 * 1024 * 1024
LONGEST = 12
_TYPES = {"paragraph", "quotation", "list_item"}
_REASONS = ("attribution", "record_type", "review", "reader_path", "scope")
_BINS = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 50), (51, 75), (76, 100), (101, None))
_POSITIONS = ("only", "first", "middle", "last")
# Abbreviations whose period does not end a sentence in this translation.
_ABBREVIATIONS = frozenset({
    "e.g", "i.e", "cf", "p", "pp", "viz", "vol", "vols", "ed", "eds", "trans", "ch", "chap", "art", "sec",
    "loc", "cit", "op", "ibid", "no", "nos", "fig", "mr", "st", "vs", "esp", "approx", "ff",
})
_METHOD = {
    "algorithm": "sentence-length-distribution-v1",
    "unicode_version": unicodedata.unidata_version,
    "segmentation": "punctuation-rules-v1: . ! ? … with closing quotes/brackets, then whitespace and a capital,"
                    " opening quote, bracket, digit or dash; never inside brackets opened within the sentence,"
                    " after a listed abbreviation or inside a chain of initials; a newline always ends a sentence",
    "abbreviations": sorted(_ABBREVIATIONS),
    "tokenization": "unicode-letter-mark-internal-apostrophe-v1",
    "length_unit": "word tokens",
    "selection": "hegel-main-text-no-pending-flags-v1",
    "facsimile": "trailing-converter-image-labels-v1",
    "offsets": "plain-text-codepoints",
    "order": "canonical-corpus-order",
}
_END = re.compile(r"(?:(?:\. ){2,}\.|[.!?…]+)[”’\"')\]]*")
_OPENERS = "“‘\"'([–—"


class SentenceStudyError(TermExperimentError):
    """A typed refusal from the sentence study."""

    def __init__(self, message, *, status="invalid", code="invalid_sentence_study"):
        super().__init__(message, status=status, code=code)


def _starts_sentence(text, position):
    while position < len(text) and text[position] in " \t":
        position += 1
    if position >= len(text):
        return True
    character = text[position]
    return character.isupper() or character.isdigit() or character in _OPENERS


def _initial(text, token, position, end):
    """A capital in a chain of initials ("G. W. F. Hegel"), not a variable ending a sentence ("A is B.")."""
    if len(token) != 1 or not token.isupper():
        return False
    return (re.match(r" [^\W\d_]\.", text[end:end + 3]) is not None
            or re.search(r"(?:^|[\s(])[^\W\d_]\. $", text[max(0, position - 5):position - 1]) is not None)


def segment(text):
    """Half-open sentence spans over ``text``, trimmed of surrounding spaces."""
    # Open brackets, by position: one opened inside the current sentence (a
    # citation or aside) blocks a split; one that opens the sentence does not.
    spans, start, opened, position = [], 0, [], 0

    def close(end):
        nonlocal start
        left, right = start, end
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right - 1].isspace():
            right -= 1
        if left < right:
            spans.append((left, right))
        start = end

    while position < len(text):
        character = text[position]
        if character == "\n":
            close(position)
            opened, position = [], position + 1
            continue
        if character in "([":
            opened.append(position)
        elif character in ")]" and opened:
            opened.pop()
        match = _END.match(text, position) if character in ".!?…" else None
        if match is None:
            position += 1
            continue
        end = match.end()
        for closer in match.group():
            if closer in ")]" and opened:
                opened.pop()
        first = start
        while first < position and text[first].isspace():
            first += 1
        word = re.search(r"([^\W\d_]+(?:\.[^\W\d_]+)*)$", text[start:position])
        token = word.group(1) if word else ""
        followed = end == len(text) or text[end].isspace()
        boundary = (followed and not any(at > first for at in opened) and _starts_sentence(text, end)
                    and not (match.group().startswith(".") and len(match.group().rstrip("”’\"')]")) == 1
                             and ((token.casefold() in _ABBREVIATIONS and (len(token) > 1 or token.islower()))
                                  or _initial(text, token, position, end))))
        if boundary:
            close(end)
        position = end
    close(len(text))
    return spans


def _scope(scope):
    if not isinstance(scope, dict) or scope.get("kind") not in {"corpus", "within", "passages"}:
        raise SentenceStudyError("Scope must be corpus, within PATH, or ordered passage IDs", code="invalid_scope")
    if scope["kind"] == "corpus":
        _keys(scope, {"kind"}, "Corpus scope")
    elif scope["kind"] == "within":
        _keys(scope, {"kind", "path"}, "Path scope")
        path = scope["path"]
        if (not isinstance(path, str) or not path.startswith("/") or "\\" in path or len(path) > 512
                or any(part in {".", ".."} for part in path.split("/"))):
            raise SentenceStudyError("A reader path such as /BEING/... is required", code="invalid_scope")
    else:
        _keys(scope, {"kind", "ids"}, "Passage scope")
        ids = scope["ids"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 4096 or len(set(ids)) != len(ids)
                or not all(isinstance(value, str) for value in ids)):
            raise SentenceStudyError("Passage scope needs 1–4096 distinct record IDs", code="invalid_scope")
    return scope


def _in_scope(record, scope):
    if scope["kind"] == "corpus":
        return True
    if scope["kind"] == "within":
        path, prefix = record.get("reader_path") or "", scope["path"].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return record["id"] in scope["ids"]


def _selection(record, scope):
    from sol.essence.terms import _reader_doctrine

    attribution = record["attribution"]
    if not _in_scope(record, scope):
        return "scope"
    if attribution["author"] != "G. W. F. Hegel" or attribution["role"] != "main_text":
        return "attribution"
    if record["type"] not in _TYPES or record.get("generated_text") is True:
        return "record_type"
    if record.get("transcription_status") in {"needs_review", "needs_visual_review"}:
        return "review"
    if _reader_doctrine(record.get("reader_path")) is None:
        return "reader_path"
    return None


def _summary(lengths):
    if not lengths:
        return {"sentences": 0, "tokens": 0, "mean": None, "median": None, "p10": None, "p90": None, "max": None}
    ordered = sorted(lengths)

    def percentile(fraction):
        # Nearest rank: an observed length, never an interpolated one.
        return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]
    return {"sentences": len(ordered), "tokens": sum(ordered), "mean": round(statistics.fmean(ordered), 6),
            "median": statistics.median_low(ordered), "p10": percentile(0.1), "p90": percentile(0.9),
            "max": ordered[-1]}


def _measure(passages, rows):
    """Shared descriptive statistics over input-row sentence counts and offsets."""
    lengths = [row[3] for row in rows]
    histogram = [{"from": low, "to": high,
                  "sentences": sum(1 for value in lengths if value >= low and (high is None or value <= high))}
                 for low, high in _BINS]
    by_position = {name: [] for name in _POSITIONS}
    first = 0
    for passage in passages:
        own = lengths[first:first + passage["sentences"]]
        for number, value in enumerate(own):
            name = ("only" if len(own) == 1 else "first" if number == 0
                    else "last" if number == len(own) - 1 else "middle")
            by_position[name].append(value)
        first += passage["sentences"]
    longest = sorted(range(len(rows)), key=lambda number: (-rows[number][3], number))[:LONGEST]
    return {"summary": _summary(lengths), "histogram": histogram,
            "by_position": {name: _summary(values) for name, values in by_position.items()}, "longest": longest}


def _analyze(snapshot, scope, origin):
    from sol import core
    from sol.essence.terms import _binding, _current, _facsimile_spans

    binding = _binding(snapshot)
    if origin is not None:
        try:
            origin = core.decode_reference(_json(_json_value(origin)))
            core.check_reference(snapshot, origin)
        except core.ProtocolError as error:
            raise SentenceStudyError(str(error), status=error.status, code=error.code) from error
    if scope["kind"] == "passages":
        known = {record["id"] for record in snapshot.records}
        if any(value not in known for value in scope["ids"]):
            raise SentenceStudyError("Passage scope names a record outside this corpus", code="invalid_scope")
    exclusions = {"input_records": len(snapshot.records), "excluded_records": 0,
                  "by_reason": dict.fromkeys(_REASONS, 0), "empty_segments": 0}
    passages, rows = [], []
    for record in snapshot.records:
        reason = _selection(record, scope)
        if reason:
            exclusions["excluded_records"] += 1
            exclusions["by_reason"][reason] += 1
            continue
        text, masks = record["plain_text"], _facsimile_spans(record)
        index, count = len(passages), 0
        for start, end in segment(text):
            if any(mask_start <= start and end <= mask_end for mask_start, mask_end in masks):
                continue
            tokens = sum(1 for _, left, right in _tokens(text[start:end]))
            if not tokens:
                exclusions["empty_segments"] += 1
                continue
            rows.append([index, start, end, tokens])
            count += 1
        passages.append({"id": record["id"], "content_sha256": record["content_sha256"],
                         "reader_path": record["reader_path"], "sentences": count,
                         "sources": [{key: value for key, value in source.items()
                                      if key in {"pdf_page", "printed_page"}} for source in record["sources"]]})
    result = {"protocol": "sol.sentence-study", "version": 1, **binding, "method": dict(_METHOD),
              "scope": scope, "origin": origin, **_measure(passages, rows),
              "passages": passages, "sentences": rows, "exclusions": exclusions}
    _validate(result)
    _current(snapshot)
    return result


def _validate(result):
    if isinstance(result, dict) and result.get("protocol") == "sol.sentence-study" and result.get("version") == 2:
        from sol.essence.sentence_inputs import validate_result
        return validate_result(result)
    from sol import core
    from sol.essence.terms import _reader_doctrine

    result = _json_value(result)
    _keys(result, {"protocol", "version", "corpus", "generation", "method", "scope", "origin", "summary",
                   "histogram", "by_position", "longest", "passages", "sentences", "exclusions"},
          "Sentence-study envelope")
    if result["protocol"] != "sol.sentence-study" or type(result["version"]) is not int or result["version"] != 1:
        raise SentenceStudyError("Unsupported SOL sentence-study protocol or version", code="unsupported_version")
    if _json(result["method"]) != _json(_METHOD):
        raise SentenceStudyError("Unsupported sentence-study method or runtime Unicode version",
                                 code="unsupported_method")
    _validate_binding(result)
    _scope(result["scope"])
    passages, rows = result["passages"], result["sentences"]
    if not isinstance(passages, list) or not isinstance(rows, list):
        raise SentenceStudyError("Passages and sentences must be lists", code="invalid_rows")
    for passage in passages:
        _keys(passage, {"id", "content_sha256", "reader_path", "sentences", "sources"}, "Passage")
        _integer(passage["sentences"], "passage sentences")
        if (not isinstance(passage["id"], str) or not isinstance(passage["content_sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", passage["content_sha256"])
                or _reader_doctrine(passage["reader_path"]) is None or not isinstance(passage["sources"], list)):
            raise SentenceStudyError("Invalid passage row", code="invalid_rows")
    if sum(passage["sentences"] for passage in passages) != len(rows):
        raise SentenceStudyError("Sentence rows disagree with passage counts", code="invalid_rows")
    previous = None
    for row in rows:
        if not isinstance(row, list) or len(row) != 4:
            raise SentenceStudyError("A sentence row is [passage, start, end, tokens]", code="invalid_rows")
        for value in row:
            _integer(value, "sentence row value")
        index, start, end, tokens = row
        if index >= len(passages) or start >= end or tokens < 1 or (
                previous is not None and (index, start) <= (previous[0], previous[2] - 1)):
            raise SentenceStudyError("Sentence rows must be ordered, nonoverlapping and nonempty", code="invalid_rows")
        previous = row
    longest = result["longest"]
    if (not isinstance(longest, list) or len(longest) > LONGEST
            or any(type(value) is not int or not 0 <= value < len(rows) for value in longest)):
        raise SentenceStudyError("Invalid longest-sentence indexes", code="invalid_rows")
    exclusions = result["exclusions"]
    _keys(exclusions, {"input_records", "excluded_records", "by_reason", "empty_segments"}, "Exclusions")
    _keys(exclusions["by_reason"], _REASONS, "Exclusion reasons")
    for value in [exclusions["input_records"], exclusions["excluded_records"], exclusions["empty_segments"],
                  *exclusions["by_reason"].values()]:
        _integer(value, "exclusion count")
    if (sum(exclusions["by_reason"].values()) != exclusions["excluded_records"]
            or exclusions["input_records"] != exclusions["excluded_records"] + len(passages)):
        raise SentenceStudyError("Exclusion counts are inconsistent", code="invalid_number")
    if result["origin"] is not None:
        try:
            result["origin"] = core.decode_reference(_json(result["origin"]))
        except core.ProtocolError as error:
            raise SentenceStudyError(str(error), status=error.status, code=error.code) from error
    if len(_json(result).encode("utf-8")) > MAX_RESULT_BYTES:
        raise SentenceStudyError("Sentence study exceeds 1 MiB", code="size_limit")
    return result


def analyze_sentences(snapshot, *, scope=None, origin=None):
    """Measure sentences from an explicit provider, or retain the legacy snapshot API.

    Providers carry their own scope and produce v2; bare snapshots preserve v1
    and the reader's S command. File input never imports CORE or the reader.
    """
    if isinstance(snapshot, (CoreProvider, FileProvider)):
        if scope is not None:
            raise SentenceStudyError("Set the sentence scope on the provider", code="invalid_scope")
        from sol.essence.sentence_inputs import analyze_provider
        return analyze_provider(snapshot, origin=origin)
    from sol.essence.terms import _fresh

    scope = _scope({"kind": "corpus"} if scope is None else _json_value(scope))
    return _analyze(_fresh(snapshot), scope, origin)


def check_sentence_result(snapshot, result):
    """Recompute; return fresh data only after exact agreement with explicit inputs."""
    if isinstance(result, dict) and result.get("version") == 2:
        from sol.essence.sentence_inputs import check_provider_result
        return check_provider_result(snapshot, result)
    if isinstance(snapshot, FileProvider):
        raise SentenceStudyError("File providers require a v2 sentence study", code="invalid_provider")
    if isinstance(snapshot, CoreProvider):
        if snapshot.scope is not None and _json(snapshot.scope) != _json(result.get("scope")):
            raise SentenceStudyError("Provider scope differs from the saved study", status="mismatch", code="scope_mismatch")
        snapshot = snapshot.snapshot
    from sol.essence.terms import _binding, _current, _fresh

    result = _validate(result)
    fresh = _fresh(snapshot)
    expected_binding = _binding(fresh)
    if result["corpus"] != expected_binding["corpus"]:
        raise SentenceStudyError("Sentence study belongs to another corpus, edition or source",
                                 status="mismatch", code="corpus_mismatch")
    if result["generation"] != expected_binding["generation"]:
        raise SentenceStudyError("Sentence study belongs to another corpus generation",
                                 status="stale", code="generation_changed")
    expected = _analyze(fresh, result["scope"], result["origin"])
    if _json(result) != _json(expected):
        raise SentenceStudyError("Sentence rows, statistics or provenance disagree with recomputation",
                                 status="mismatch", code="result_mismatch")
    _current(fresh)
    return expected


def decode_sentence_result(data):
    """Decode one bounded UTF-8 result; duplicate/nonfinite fields are refused."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if not isinstance(raw, bytes) or len(raw) > PROVIDER_MAX_RESULT_BYTES:
        raise SentenceStudyError("Sentence study must be UTF-8 JSON of at most 16 MiB (1 MiB for v1)", code="size_limit")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise SentenceStudyError("Duplicate sentence-study JSON field", code="duplicate_field")
            value[key] = item
        return value

    def nonfinite(_):
        raise SentenceStudyError("Sentence-study JSON requires finite numbers", code="invalid_json")
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
    except (UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, SentenceStudyError):
            raise
        raise SentenceStudyError("Invalid sentence-study JSON", code="invalid_json") from error
    if (not isinstance(result, dict) or result.get("version") != 2) and len(raw) > MAX_RESULT_BYTES:
        raise SentenceStudyError("Sentence study must be UTF-8 JSON of at most 1 MiB", code="size_limit")
    return _validate(result)


def encode_sentence_result(result):
    """Inert ASCII JSON; no book text is stored, only IDs, offsets and digests."""
    return json.dumps(_validate(result), ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def save_sentence_result(result, directory=None):
    """Publish a new owner-only artifact under SOL's data directory; never overwrite."""
    import datetime
    import os
    from pathlib import Path

    if directory is None:
        configured = os.environ.get("XDG_DATA_HOME")
        base = Path(configured).expanduser() if configured else Path.home() / ".local" / "share"
        if not base.is_absolute():
            raise SentenceStudyError("XDG_DATA_HOME must be an absolute directory", code="invalid_location")
        directory = base / "sol" / "studies"
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"sentences-{stamp}.sol-analysis.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
        stream.write(encode_sentence_result(result) + "\n")
    return path
