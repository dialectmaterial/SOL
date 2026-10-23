#!/usr/bin/env python3
"""Reselect the Experiment A audit sample and score private offset annotations.

Read-only CORE input; stdout contains aggregates/digests, never source prose,
record IDs or paths. Gold annotations stay outside Git. See SENTENCE_AUDIT.md.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import random
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sol import core
from sol.essence.essence_as_reflection_within_itself.sentences import _selection, segment, segment_v2

SEED = 20261023
SIZE = 60


def sample_records(snapshot, size=SIZE, seed=SEED):
    """Sample without replacement from canonical-order v1-eligible records."""
    eligible = [row for row in snapshot.records if _selection(row, {"kind": "corpus"}) is None]
    return len(eligible), random.Random(seed).sample(eligible, size)


def score(sample, annotations, splitter):
    """Exact internal end offsets; exclude forced passage-final boundaries.

    Count raw segmenter boundaries, including numeral-only/fragment segments;
    the downstream word-token filter is a different question.
    """
    if len(annotations) != len(sample):
        raise ValueError("Gold annotation count differs from the sample")
    counts = Counter(tp=0, fp=0, fn=0, passages_with_errors=0)
    for row, gold in zip(sample, annotations):
        text = row["plain_text"]
        if gold["id"] != row["id"] or gold["text_sha256"] != sha256(text.encode("utf-8")).hexdigest():
            raise ValueError("Gold sample identity or text digest differs")
        ends = gold["ends"]
        if (not isinstance(ends, list) or any(type(end) is not int or not 0 < end < len(text) for end in ends)
                or sorted(set(ends)) != ends):
            raise ValueError("Gold needs sorted unique internal codepoint end offsets")
        predicted = {end for _, end in splitter(text) if end < len(text)}
        actual = set(ends)
        counts.update(tp=len(predicted & actual), fp=len(predicted - actual), fn=len(actual - predicted),
                      passages_with_errors=int(predicted != actual))
    tp, fp, fn = (counts[name] for name in ("tp", "fp", "fn"))
    return {**counts, "predicted": tp + fp, "gold": tp + fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, help="private JSON: ordered id, text_sha256, ends rows")
    options = parser.parse_args()
    snapshot = core.load_snapshot(options.corpus)
    population, sample = sample_records(snapshot)
    # Hash IDs and text digests in draw order, independently of JSON formatting.
    sample_digest = sha256("".join(row["id"] + ":" + sha256(row["plain_text"].encode()).hexdigest() + "\n"
                                   for row in sample).encode()).hexdigest()
    texts = [row["plain_text"] for row in sample]
    report = {"seed": SEED, "size": SIZE, "eligible": population, "sample_sha256": sample_digest,
              "generation": {"manifest_sha256": snapshot.manifest_sha256, "index_sha256": snapshot.index_sha256},
              "characters": sum(map(len, texts)),
              "features": {"semicolons": sum(text.count(";") for text in texts),
                           "colons": sum(text.count(":") for text in texts),
                           "newlines": sum(text.count("\n") for text in texts),
                           "opening_round_brackets": sum(text.count("(") for text in texts),
                           "opening_square_brackets": sum(text.count("[") for text in texts),
                           "curly_double_quote_pairs": sum(text.count("“") for text in texts),
                           "ellipsis_runs": sum(len(re.findall(r"…|\.(?:\s*\.){2,}", text)) for text in texts)},
              "abbreviations": dict(Counter(m.group() for text in texts for m in re.finditer(
                  r"\b(?:e\.g\.|i\.e\.|cf\.|pp?\.|etc\.|Geom\.|Lib\.|Prop\.|schol\.)", text)))}
    if options.annotations:
        raw = options.annotations.read_bytes()
        annotations = json.loads(raw)
        report["annotations_sha256"] = sha256(raw).hexdigest()
        report["methods"] = {name: score(sample, annotations, splitter) for name, splitter in
                             (("punctuation-rules-v1", segment), ("punctuation-rules-v2", segment_v2))}
    core.verify_snapshot_current(snapshot)
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
