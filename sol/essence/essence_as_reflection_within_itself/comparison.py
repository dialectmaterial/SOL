"""Descriptive lexical comparisons over verified word-frequency studies.

This is a derived view, not a change to sol.word-frequencies v1. Public entry
points always read/check caller-selected providers; an artifact alone is never
authority to export measurements. No significance or conceptual claim is made.
"""
from __future__ import annotations

import csv
from hashlib import sha256
from io import StringIO
import json
import math

from sol.essence.essence_as_reflection_within_itself.word_inputs import CoreProvider, FileProvider, WordStudyError
from sol.essence.essence_as_reflection_within_itself.words import analyze_words, check_word_result, encode_word_result


_METHOD = {
    "algorithm": "word-rate-comparison-v1",
    "rate_difference": "10000*(target_count/target_denominator-reference_count/reference_denominator)",
    "log2_rate_ratio": "log2((target_count*reference_denominator)/(reference_count*target_denominator))",
    "zero_policy": "no smoothing; undefined values are null with an explicit status",
    "rounding_decimal_places": 6,
    "order": "unchanged word-frequency study order",
}
_WARNING = ("These are descriptive lexical effect sizes, not significance tests, confidence estimates "
            "or evidence of conceptual similarity. Overlapping scopes are permitted.")
EXPORT_FIELDS = (
    "word", "target_count", "target_denominator", "target_rate_per_10000_tokens",
    "reference_count", "reference_denominator", "reference_rate_per_10000_tokens",
    "rate_difference_per_10000_tokens", "rate_difference_status", "log2_rate_ratio", "log2_ratio_status",
    "comparison_method", "study_sha256", "target_provider", "target_binding", "target_scope_sha256",
    "reference_provider", "reference_binding", "reference_scope_sha256", "warnings",
)


def compare_words(
    target: CoreProvider | FileProvider, *, reference: CoreProvider | FileProvider,
    result: dict | None = None,
) -> dict:
    """Return a fresh comparison view, optionally checking an existing v1 study.

    Providers include their independent scopes, as in analyze_words. When result
    is supplied, every input binding/count is strictly recomputed before use.
    Output: method, study (unchanged v1 shape), study_sha256, rows, warnings.
    Rows include word, the two existing frequency cells, two measures and their
    statuses. Zero denominators make both measures undefined; a zero occurrence
    count only makes the unsmoothed log ratio undefined. No infinity is emitted.
    """
    if reference is None:
        raise WordStudyError("A word comparison requires an explicit reference provider", code="missing_reference")
    study = (analyze_words(target, reference=reference) if result is None else
             check_word_result(target, result, reference=reference))
    rows = []
    for frequency in study["frequencies"]:
        left, right = frequency["target"], frequency["reference"]
        a, nt, b, nr = left["count"], left["denominator"], right["count"], right["denominator"]
        empty = "empty_both" if not nt and not nr else "empty_target" if not nt else "empty_reference" if not nr else None
        difference = round(10000 * (a / nt - b / nr), 6) if empty is None else None
        ratio_status = empty or ("zero_target_count" if not a else "zero_reference_count" if not b else "defined")
        # Integer products retain exact count ratios before the logarithm. The
        # v1 63-bit count bound keeps this finite without pseudocounts/clipping.
        ratio = round(math.log2((a * nr) / (b * nt)), 6) if ratio_status == "defined" else None
        rows.append({"word": frequency["word"], "target": left, "reference": right,
                     "rate_difference_per_10000_tokens": difference,
                     "rate_difference_status": empty or "defined",
                     "log2_rate_ratio": ratio, "log2_ratio_status": ratio_status})
    return {"method": dict(_METHOD), "study": study,
            "study_sha256": sha256(encode_word_result(study).encode("utf-8")).hexdigest(),
            "rows": rows, "warnings": [*study["warnings"], _WARNING]}


def export_word_comparison(
    target: CoreProvider | FileProvider, *, reference: CoreProvider | FileProvider,
    result: dict | None = None, format: str = "csv",
) -> str:
    """Verify sources and return a UTF-8-ready CSV/TSV table, never write files.

    Undefined numeric cells are empty, with a separate explicit status. Each
    word row retains source bindings, scope digests and the canonical v1 study's
    SHA-256 (encoded JSON without a newline). An empty union has a header only;
    keep the source artifact for its empty-scope summaries and provenance.
    """
    if format not in ("csv", "tsv"):
        raise WordStudyError("Word comparison export format must be csv or tsv", code="invalid_format")
    comparison = compare_words(target, reference=reference, result=result)
    study = comparison["study"]
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS, delimiter="," if format == "csv" else "\t",
                            lineterminator="\n")
    writer.writeheader()
    binding = {"comparison_method": _METHOD["algorithm"], "study_sha256": comparison["study_sha256"],
               "warnings": json.dumps(comparison["warnings"], ensure_ascii=True, separators=(",", ":"))}
    for name in ("target", "reference"):
        binding[name + "_provider"] = study[name]["provider"]
        binding[name + "_binding"] = json.dumps(study[name]["binding"], ensure_ascii=True, sort_keys=True,
                                                  separators=(",", ":"), allow_nan=False)
        scope = json.dumps(study[name]["scope"], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        binding[name + "_scope_sha256"] = sha256(scope.encode("utf-8")).hexdigest()
    for row in comparison["rows"]:
        values = {"word": row["word"], **binding}
        for name in ("target", "reference"):
            for field in ("count", "denominator", "rate_per_10000_tokens"):
                values[name + "_" + field] = row[name][field]
        for field in ("rate_difference_per_10000_tokens", "rate_difference_status", "log2_rate_ratio", "log2_ratio_status"):
            values[field] = row[field]
        writer.writerow(values)
    return output.getvalue()
