"""Dependency-free, versioned TF-IDF over the word providers' input rows."""
from __future__ import annotations

import math

from sol.essence.word_inputs import CoreProvider, FileProvider, WordStudyError
from sol.essence.words import (MAX_RESULT_BYTES, _decode_result, _integer, _json,
                               _json_value, _keys, _validate as validate_words,
                               analyze_words, check_word_result)


_METHOD = {
    "algorithm": "tfidf-v1",
    "documents": "one per word-provider input row; include zero-token rows in N",
    "tf": "raw included token count c(t,d); no sublinear scaling",
    "idf": "natural log((1+N)/(1+df(t)))+1; df counts documents containing t",
    "smoothing": "add one to N and df, then add one outside the logarithm",
    "normalization": "L2 per document over all terms before truncation; empty vector stays empty",
    "overall": "sum of L2-normalized document weights divided by N; empty if N=0",
    "precision": "round final document and overall scores to 12 decimal places",
    "order": "descending rounded score, then normalized word; take top_n",
    "lexical_policy": "embedded sol.word-frequencies v1 method; no stemming or stop-word removal",
}


def _top_n(value):
    _integer(value, 1)
    if value > 1000:
        raise WordStudyError("top_n must be between 1 and 1000", code="invalid_number")


def _derive(words, top_n):
    """Compute sparse weights from counts, retaining the complete word receipt."""
    n = words["target"]["summary"]["input_count"]
    vectors = [{} for _ in range(n)]
    for row in words["frequencies"]:
        locations = row["target"]["locations"]
        idf = math.log((1 + n) / (1 + len(locations))) + 1
        for index, count, _start, _end in locations:
            vectors[index][row["word"]] = count * idf
    overall = {}

    def ranked(weights):
        rows = [{"word": word, "score": round(score, 12)} for word, score in weights.items()]
        return sorted(rows, key=lambda row: (-row["score"], row["word"]))[:top_n]

    documents = []
    for index, vector in enumerate(vectors):
        norm = math.sqrt(math.fsum(weight * weight for weight in vector.values()))
        normalized = {word: weight / norm for word, weight in vector.items()} if norm else {}
        for word, weight in normalized.items():
            overall[word] = overall.get(word, 0.0) + weight / n
        documents.append({"input_index": index, "top_terms": ranked(normalized)})
    return {"protocol": "sol.tfidf", "version": 1, "method": dict(_METHOD),
            "top_n": top_n, "word_study": words, "documents": documents,
            "overall": ranked(overall)}


def _validate(result):
    _json_value(result)
    _keys(result, {"protocol", "version", "method", "top_n", "word_study", "documents", "overall"})
    if result["protocol"] != "sol.tfidf" or type(result["version"]) is not int or result["version"] != 1:
        raise WordStudyError("Unsupported TF-IDF artifact version", code="unsupported_version")
    if _json(result["method"]) != _json(_METHOD):
        raise WordStudyError("Unsupported TF-IDF method", code="unsupported_method")
    _top_n(result["top_n"])
    words = validate_words(result["word_study"])
    if words["reference"] is not None:
        raise WordStudyError("TF-IDF takes one provider, without a reference", code="invalid_input")
    if _json(result) != _json(_derive(words, result["top_n"])):
        raise WordStudyError("TF-IDF weights disagree with word counts", status="mismatch", code="result_mismatch")
    if len(_json(result).encode()) + 1 > MAX_RESULT_BYTES:
        raise WordStudyError("TF-IDF study exceeds 16 MiB", code="size_limit")
    return result


def analyze_tfidf(target: CoreProvider | FileProvider, *, top_n: int = 20) -> dict:
    """Return sol.tfidf v1: top terms per document and overall, plus provenance.

    Documents index word_study.target.inputs (CORE passages, or one whole file).
    All terms determine normalization and overall means before top_n truncation.
    No persistence, interface startup or source mutation occurs.
    """
    _top_n(top_n)
    return _validate(_derive(analyze_words(target), top_n))


def check_tfidf_result(target: CoreProvider | FileProvider, result: dict) -> dict:
    """Validate weights and recompute from explicitly supplied current sources."""
    _validate(result)
    words = check_word_result(target, result["word_study"])
    return _validate(_derive(words, result["top_n"]))


def decode_tfidf_result(data: bytes | str) -> dict:
    """Decode strict, bounded UTF-8 JSON before opening any sources."""
    return _decode_result(data, _validate)


def encode_tfidf_result(result: dict) -> str:
    """Encode deterministic text-free provenance and lexical weights."""
    return _json(_validate(result))
