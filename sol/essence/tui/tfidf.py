"""TF-IDF study adapter; passage labels are display-only, never persisted."""
from dataclasses import dataclass, field
from pathlib import Path

from sol.essence.tui import words


@dataclass
class TfidfCount:
    study: dict
    target: object
    labels: dict = field(default_factory=dict, repr=False)


def run(context, target_choice, *, target_file=None, top_n=20, loader=None):
    from sol.essence import analyze_tfidf

    _, inputs = words.engine()
    book = snapshot = None
    if target_choice != "file":
        if not context["corpus"]:
            raise ValueError("This reader session has no CORE corpus; choose a text file instead.")
        from sol import core
        book = (loader or (lambda directory: core.load_corpus_book(Path(directory))))(context["corpus"])
        snapshot = book.corpus_snapshot
        core.check_reference(snapshot, context["reference"])
    target = words.provider(target_choice, context, book=book, snapshot=snapshot, path=target_file, inputs=inputs)
    study = analyze_tfidf(target, top_n=top_n)
    labels = {}
    if book is not None:
        for item in study["word_study"]["target"]["inputs"]:
            passage = book.find_passage(item["id"])
            labels[item["id"]] = f"{passage.heading or passage.node.title}\np. {passage.printed_page}"
    return TfidfCount(study, target, labels)


def rows(count):
    inputs = count.study["word_study"]["target"]["inputs"]
    return [(count.labels.get(inputs[row["input_index"]].get("id"), "Text file"),
             " · ".join(f"{term['word']} {term['score']:.4f}" for term in row["top_terms"]) or "No included words")
            for row in count.study["documents"]]


def summary(count):
    part = count.study["word_study"]["target"]
    total = part["summary"]
    n = total["input_count"]
    return [f"TF-IDF · {n:,} {'passage' if part['provider'] == 'core' else 'file'}{'s' if n != 1 else ''} · "
            f"{total['token_count']:,} tokens · top {count.study['top_n']} terms each",
            "Passages in reading order, then overall mean weights. Enter opens a passage in the reader.",
            "Raw-count TF · smoothed IDF · L2 per passage · no stop-word removal.",
            *count.study["word_study"]["warnings"]]


def source(count, row):
    if not 0 <= row < len(count.study["documents"]):
        return None
    document = count.study["documents"][row]
    item = count.study["word_study"]["target"]["inputs"][document["input_index"]]
    if "id" not in item:
        return None
    return {"id": item["id"], "start": item["span"][0], "content_sha256": item["content_sha256"]}


def save(count, *, data_home=None):
    from sol.essence import encode_tfidf_result
    return words._create((encode_tfidf_result(count.study) + "\n").encode("utf-8"),
                         ".sol-analysis.json", data_home, prefix="tfidf")
