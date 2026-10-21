"""Sentence lengths from the interface: choices in, the v2 study out.

The study is Experiment A's sentence-length half (`sol.essence.sentences`,
`punctuation-rules-v1`), run through the same CORE/file providers as word
frequencies. This module holds no Textual code and keeps no book text: the
beginnings shown for the longest sentences are read at display time and never
saved. The engine is imported lazily, like the word engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sol.essence.tui import words

ROW_LIMIT = 12  # the study keeps its twelve longest sentences
BAR = 24  # columns of the widest histogram bar
POSITIONS = (("first", "First in paragraph"), ("middle", "Middle"), ("last", "Last"),
             ("only", "Only sentence"))
# A file is one input row: places are among its retained sentences, not paragraphs.
FILE_POSITIONS = (("first", "First"), ("middle", "Middle"), ("last", "Last"), ("only", "Only sentence"))


@dataclass
class SentenceCount:
    """One sentence study, its provider, and passage texts kept for display only."""

    study: dict
    target: object
    texts: dict = field(default_factory=dict, repr=False)
    labels: dict = field(default_factory=dict, repr=False)
    book: object = field(default=None, repr=False)  # display only: names the section


def engine():
    try:
        from sol.essence import sentences
    except ImportError as error:
        raise words.EngineMissing("Sentence lengths need the ESSENCE sentence engine, which is not installed.") \
            from error
    return sentences


def run(context, target_choice, *, target_file=None, loader=None):
    """Measure the sentences of the chosen target; returns a SentenceCount."""
    sentences = engine()
    _, inputs = words.engine()
    book = snapshot = None
    if target_choice != "file":
        if not context["corpus"]:
            raise ValueError("This reader session has no CORE corpus; choose a text file instead.")
        from sol import core
        load = loader or (lambda directory: core.load_corpus_book(Path(directory)))
        book = load(context["corpus"])
        snapshot = book.corpus_snapshot
        # As for words: a corpus changed since the reader opened is refused.
        core.check_reference(snapshot, context["reference"])
    target = words.provider(target_choice, context, book=book, snapshot=snapshot, path=target_file, inputs=inputs)
    study = sentences.analyze_sentences(target)
    texts, labels = {}, {}
    for item in study["input"]["inputs"]:
        if "id" in item and book is not None:
            passage = book.find_passage(item["id"])
            texts[item["id"]] = passage.text
            labels[item["id"]] = f"{passage.heading or passage.node.title} | p. {passage.printed_page}"
    if target_choice == "file":
        texts[None] = words.verified_file_text(target.path, study["input"]["binding"]["sha256"])
    return SentenceCount(study, target, texts, labels, book)


def summary(count):
    """Plain lines: totals, the length distribution as bars, means by place."""
    study = count.study
    totals = study["summary"]
    part = study["input"]
    where = words.scope_name(count.book, part)
    if not totals["sentences"]:
        lines = [f"No sentences to measure ({part['provider']}, {where})."]
    else:
        lines = [f"{_count(totals['sentences'], 'sentence')}, {_count(totals['tokens'], 'word')}, "
                 f"{_count(len(part['inputs']), 'input')} ({part['provider']}, {where})",
                 f"Words per sentence: mean {totals['mean']:.1f}, median {totals['median']}, "
                 f"middle 80% {totals['p10']}–{totals['p90']}, longest {totals['max']}", ""]
        peak = max(1, *(row["sentences"] for row in study["histogram"]))
        for row in study["histogram"]:
            span = f"{row['from']}–{row['to']}" if row["to"] is not None else f"{row['from']}+"
            bar = "█" * round(BAR * row["sentences"] / peak)
            lines.append(f"{span:>8} words {row['sentences']:>6,}  {bar}")
        lines.append("")
        file = part["provider"] == "file"
        means = [f"{label} {study['by_position'][key]['mean']:.1f}" for key, label in
                 (FILE_POSITIONS if file else POSITIONS) if study["by_position"][key]["mean"] is not None]
        lines.append(("Mean words by place among the file's retained sentences (the file is one input): "
                      if file else "Mean words by place in the paragraph: ") + ", ".join(means))
    excluded = study["exclusions"]
    review = excluded["by_reason"].get("review", 0)
    if review:
        lines.append(f"{review:,} passages awaiting source review were left out.")
    if excluded["outside_span"]:
        lines.append(f"{excluded['outside_span']:,} sentences cut by the span were left out.")
    if part["provider"] == "file":
        lines.append("Sentences end by declared punctuation rules (punctuation-rules-v1, written for the "
                     "Cambridge translation of the Logic) and are counted in SOL's word tokens.")
    else:
        lines.append("Sentences end by declared punctuation rules (punctuation-rules-v1) and are counted "
                     "in the English translation's words; this describes the translation, not Hegel's German.")
    return lines


def _beginning(text, limit=60):
    """The sentence's first words, cut at a word with an ellipsis rather than mid-word."""
    words = " ".join(text.split())
    if len(words) <= limit:
        return words
    head = words[:limit + 1]
    cut = head.rsplit(" ", 1)[0] if " " in head else words[:limit]
    return cut.rstrip(" ,;:") + "…"


def rows(count, limit=ROW_LIMIT):
    """The longest sentences: words, how each begins, and where."""
    study, table = count.study, []
    for index in study["longest"][:limit]:
        input_index, start, end, tokens = study["sentences"][index]
        item = study["input"]["inputs"][input_index]
        text = count.texts.get(item.get("id"))
        beginning = _beginning(text[start:end]) if text is not None else ""
        table.append((str(tokens), beginning, count.labels.get(item.get("id")) or _where(item)))
    return table


def source(count, row):
    """What the reader needs to open row `row`, or None for a text file."""
    study = count.study
    input_index, start, _, _ = study["sentences"][study["longest"][row]]
    item = study["input"]["inputs"][input_index]
    if "id" not in item:
        return None
    return {"id": item["id"], "start": start, "content_sha256": item["content_sha256"]}


def _count(number, noun):
    return f"{number:,} {noun}" + ("" if number == 1 else "s")


def _where(item):
    if "reader_path" not in item:
        return "text file"
    pages = item["sources"][0]["printed_page"] if item["sources"] else None
    return f"{item['reader_path']} | p. {pages}" if pages else item["reader_path"]


def save(count, *, data_home=None):
    """Save the v2 artifact owner-only beside the other studies; never overwrite."""
    data = (engine().encode_sentence_result(count.study) + "\n").encode("utf-8")
    return words._create(data, ".sol-analysis.json", data_home, prefix="sentences")
