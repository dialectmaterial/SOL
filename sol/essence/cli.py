"""Analysis inputs, experiments and private review over a selected local corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import textwrap
import unicodedata


def build_parser() -> argparse.ArgumentParser:
    """Build help without importing analysis or opening any local data."""
    parser = argparse.ArgumentParser(
        prog="sol analyze", description="Run and verify transparent, read-only corpus experiments.")
    commands = parser.add_subparsers(dest="action", required=True)
    term = commands.add_parser("term", help="measure exact lexical occurrences, not conceptual similarity")
    term.add_argument("word", metavar="WORD", help="one lexical token to count (Unicode-aware, case-insensitive)")
    term.add_argument("--reference", metavar="FILE|-", help="optional CORE reference anchor; it does not restrict the scope")
    term.add_argument("--doctrine", choices=("being", "essence", "concept"),
                      help="explicitly restrict the experiment to one doctrine")
    term.add_argument("--limit", type=int, default=10, metavar="N",
                      help="maximum representative passages (default: 10)")
    sentences = commands.add_parser("sentences", help="measure sentence lengths in the English translation")
    sentences.add_argument("--within", metavar="PATH",
                           help="only passages under this reader path, e.g. /BEING/i-determinateness-quality")
    sentences.add_argument("--reference", metavar="FILE|-", help="optional CORE reference anchor; it does not restrict the scope")
    check = commands.add_parser("check", help="recompute and verify a saved experiment against the local corpus")
    check.add_argument("file", metavar="FILE|-", help="saved result JSON, or - for piped input")
    prose = commands.add_parser("prose", help="prepare prose-only analysis input, retaining headings as metadata")
    sample = commands.add_parser("segmentation-sample", help="prepare a blind private sample for human sentence marking")
    sample.add_argument("--per-doctrine", type=int, required=True, metavar="N", help="explicit number of whole passages from each doctrine")
    sample.add_argument("--seed", type=int, required=True, help="explicit reproducible sampling seed")
    sample.add_argument("--output", type=Path, required=True, metavar="FILE", help="new private JSON file outside every Git checkout")
    review = commands.add_parser("segmentation-check", help="measure false splits and misses against human-marked sentences")
    review.add_argument("file", metavar="FILE|-", help="completed private review JSON, or - for piped input")
    for command in (term, sentences, check, prose, sample, review):
        command.add_argument("--corpus", type=Path, metavar="DIRECTORY",
                             help="use this local canonical corpus instead of discovery")
        command.add_argument("--json", action="store_true", help="print machine-readable JSON instead of a human summary")
    return parser


def _safe(value: object) -> str:
    """Keep source controls, bidi overrides and surrogate characters inert."""
    output = []
    for character in str(value):
        code = ord(character)
        if code < 32 or 127 <= code <= 159 or unicodedata.category(character) in {"Cf", "Cs", "Zl", "Zp"}:
            output.append(f"\\u{code:04x}" if code <= 65535 else f"\\U{code:08x}")
        else:
            output.append(character)
    return "".join(output)


def _json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def verification_receipt(result: dict) -> dict:
    """A verification receipt is deliberately not another experiment envelope."""
    return {"status": "current", "query": result["query"],
            "corpus_id": result["corpus"]["id"], "generation": result["generation"],
            "totals": result["totals"], "matched_ids": [match["id"] for match in result["matches"]]}


def _location(sources: list[dict]) -> str:
    def page(source):
        label = source["printed_page"]
        return f"printed {_safe(label) if label is not None else '?'} / PDF {source['pdf_page']}"
    first = page(sources[0])
    return first if len(sources) == 1 else first + " to " + page(sources[-1])


def render_result(result: dict) -> str:
    """Present validated data minimally; every source-derived string is escaped."""
    totals = result["totals"]
    scope = result["doctrine"] or "BEING, ESSENCE, CONCEPT"
    lines = [f"Term: {_safe(result['query'])}",
             "Exact lexical occurrences; not conceptual similarity.",
             f"Scope: {_safe(scope)}", "",
             f"{totals['occurrences']} occurrences in {totals['matching_passages']} matching passages; "
             f"{totals['token_count']} tokens across {totals['passage_count']} included passages.",
             "Occurrences per 10,000 tokens:"]
    for group in result["groups"]:
        rate = group["rate_per_10000_tokens"]
        formatted_rate = f"{rate:.3f} / 10,000" if rate is not None else "n/a (no included tokens)"
        lines.append(f"  {_safe(group['doctrine']):7}  {group['occurrences']:>5} occurrences  "
                     + formatted_rate)
    excluded = result["exclusions"]
    review = excluded["by_reason"]["review"]
    lines.append(f"Excluded: {excluded['excluded_records']} records, including "
                 f"{review} pending/unreviewed transcriptions.")
    if excluded["masked_facsimile_captions"]:
        lines.append(f"Ignored facsimile image labels: {excluded['masked_facsimile_captions']} "
                     f"({excluded['masked_facsimile_tokens']} non-prose tokens).")
    if result["origin"] is not None:
        lines.append(f"Anchor: {_safe(result['origin']['reference']['requested_id'])} "
                     "(context only; does not restrict scope).")
    matches = result["matches"]
    width = max(40, min(88, shutil.get_terminal_size(fallback=(80, 24)).columns))
    lines += ["", f"Representative passages: {len(matches)} of {totals['matching_passages']}."]
    for match in matches:
        first = match["first_match"]
        start, end = first["start"] - first["context_start"], first["end"] - first["context_start"]
        context = first["context"]
        marked = context[:start] + "[" + context[start:end] + "]" + context[end:]
        folded = textwrap.fill(_safe(marked), width=width, initial_indent="  ", subsequent_indent="  ",
                               break_on_hyphens=False)
        lines += ["", f"{_safe(match['reader_path'])}  ({_location(match['sources'])})",
                  f"{_safe(match['id'])}  {match['occurrences']} occurrence(s)", folded]
    if result["matches_truncated"]:
        lines += ["", "More matching passages exist; increase --limit to include more representatives."]
    return "\n".join(lines)


def render_sentences(result: dict) -> str:
    """Summarize a sentence study; locations only, never stored book text."""
    summary = result["summary"]
    scope = result["scope"]
    label = {"corpus": "whole corpus", "within": scope.get("path"), "passages": f"{len(scope.get('ids', []))} chosen passages"}
    lines = [f"Sentence lengths: {_safe(label[scope['kind']])}",
             "Word tokens per sentence in the English translation; punctuation-rule segmentation.", ""]
    if not summary["sentences"]:
        return "\n".join(lines + ["No eligible sentences in this scope."])
    lines.append(f"{summary['sentences']} sentences, {summary['tokens']} tokens in {len(result['passages'])} passages.")
    lines.append(f"Mean {summary['mean']:.1f}, median {summary['median']}, 10th–90th percentile "
                 f"{summary['p10']}–{summary['p90']}, longest {summary['max']}.")
    peak = max(row["sentences"] for row in result["histogram"]) or 1
    lines.append("")
    for row in result["histogram"]:
        span = f"{row['from']}–{row['to']}" if row["to"] is not None else f"{row['from']}+"
        lines.append(f"  {span:>7} {row['sentences']:>6}  " + "█" * round(24 * row["sentences"] / peak))
    lines += ["", "By position in the paragraph (mean tokens):"]
    for name, values in result["by_position"].items():
        if values["sentences"]:
            lines.append(f"  {name:6} {values['mean']:6.1f}  ({values['sentences']} sentences)")
    excluded = result["exclusions"]
    review = excluded["by_reason"]["review"]
    other = excluded["excluded_records"] - review - excluded["by_reason"]["scope"]
    lines += ["", f"Excluded in scope: {review} passage{'s' * (review != 1)} awaiting source review, "
                  f"{other} non-Hegel or non-prose record{'s' * (other != 1)}."]
    lines += ["", "Longest sentences:"]
    for number in result["longest"]:
        index, start, end, tokens = result["sentences"][number]
        passage = result["passages"][index]
        lines.append(f"  {tokens:>4} tokens  {_safe(passage['reader_path'])}  ({_location(passage['sources'])})")
        lines.append(f"        {_safe(passage['id'])} at {start}–{end}")
    return "\n".join(lines)


def main(arguments: list[str] | None = None) -> int:
    """Analyze or verify without opening BEING, a workspace, or a source PDF."""
    options = build_parser().parse_args(arguments)
    try:
        from sol.core import MAX_REFERENCE_BYTES, decode_reference, discover_corpus, load_snapshot
        from sol.core.wire import read_json_input
        from sol.essence.terms import (
            MAX_RESULT_BYTES, analyze_term, check_term_result,
            decode_term_result, encode_term_result,
        )

        from sol.essence import sentences as sentence_study

        origin = result = None
        # Reject unsafe input before inspecting corpus/configuration data.
        if options.action == "segmentation-check":
            from sol.essence.segmentation_check import MAX_REVIEW_BYTES, decode_sample
            result = decode_sample(read_json_input(options.file, MAX_REVIEW_BYTES))
        elif options.action == "check":
            raw = read_json_input(options.file, MAX_RESULT_BYTES)
            data = raw.encode("utf-8") if isinstance(raw, str) else raw
            decode = (sentence_study.decode_sentence_result if b'"sol.sentence-study"' in data
                      else decode_term_result)
            result = decode(data)
        elif options.action in ("term", "sentences") and options.reference is not None:
            origin = decode_reference(read_json_input(options.reference, MAX_REFERENCE_BYTES))
        directory = discover_corpus(options.corpus)
        if directory is None:
            raise ValueError("No canonical corpus configured; use --corpus DIRECTORY or sol --set-corpus DIRECTORY")
        snapshot = load_snapshot(directory)
        if options.action == "segmentation-sample":
            from sol.essence.segmentation_check import prepare_sample, write_sample
            sample = prepare_sample(snapshot, per_doctrine=options.per_doctrine, seed=options.seed)
            path = write_sample(sample, options.output)
            receipt = {"sample": str(path), "passages": len(sample["passages"]), "status": "unmarked"}
            print(_json(receipt) if options.json else
                  f"Created private blind sample: {_safe(path)}\n"
                  f"{receipt['passages']} passages; human marking is required before scoring.")
        elif options.action == "segmentation-check":
            from sol.essence.segmentation_check import compare_sample
            report = compare_sample(snapshot, result)
            if options.json:
                print(_json(report))
            else:
                counts = report["summary"]
                def rate(value):
                    return "undefined (no boundaries)" if value is None else f"{100 * value:.2f}%"
                print(f"Sentence segmentation against marks by {_safe(report['reviewer'])}\n"
                      f"{counts['passages']} scored passages; {len(report['excluded_passages'])} explicitly excluded.\n"
                      f"{counts['gold_boundaries']} gold internal boundaries; "
                      f"{counts['false_splits']} false splits, {counts['misses']} misses.\n"
                      f"Precision {rate(counts['precision'])}; recall {rate(counts['recall'])}; "
                      f"F1 {rate(counts['f1'])}.\n"
                      "Final passage ends are excluded. This scores declared marks, not proof of human review.\n"
                      "Use --json for per-doctrine counts and exact error offsets.")
        elif options.action == "prose":
            from sol.essence.prose import export_prose
            result = export_prose(snapshot)
            print(_json(result) if options.json else (
                f"{len(result['passages'])} prose passages ready for analysis; "
                f"{result['exclusions']['excluded_records']} records excluded.\n"
                "Vector input: passages[].text (headings and image labels excluded).\n"
                "Canonical ancestry, headings and source references remain in metadata.\n"
                "Use sol analyze prose --json to export the complete input."))
        elif options.action == "sentences":
            scope = {"kind": "within", "path": options.within} if options.within else None
            result = sentence_study.analyze_sentences(snapshot, scope=scope, origin=origin)
            print(sentence_study.encode_sentence_result(result) if options.json else render_sentences(result))
        elif options.action == "term":
            result = analyze_term(snapshot, options.word, origin=origin,
                                  doctrine=options.doctrine.upper() if options.doctrine else None,
                                  limit=options.limit)
            print(encode_term_result(result) if options.json else render_result(result))
        elif result["protocol"] == "sol.sentence-study":
            result = sentence_study.check_sentence_result(snapshot, result)
            print(_json({"status": "current", "protocol": result["protocol"], "corpus_id": result["corpus"]["id"],
                         "generation": result["generation"], "summary": result["summary"]}) if options.json
                  else "Verified against the current corpus generation.\n\n" + render_sentences(result))
        else:
            result = check_term_result(snapshot, result)
            print(_json(verification_receipt(result)) if options.json
                  else "Verified against the current corpus generation.\n\n" + render_result(result))
        return 0
    except (ValueError, OSError) as error:
        message = _safe(error)
        if options.json:
            print(_json({"status": _safe(getattr(error, "status", "invalid")),
                         "code": _safe(getattr(error, "code", "invalid_input")),
                         "error": message}))
        print(f"sol: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
