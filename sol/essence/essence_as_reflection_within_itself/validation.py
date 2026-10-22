"""Shared inert study validation; importing it needs no CORE or interface."""
from __future__ import annotations

import json
import math
import re
import uuid


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


