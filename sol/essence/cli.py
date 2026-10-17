"""Read-only analysis inputs and experiments over a selected local corpus."""

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
    check = commands.add_parser("check", help="recompute and verify a saved experiment against the local corpus")
    check.add_argument("file", metavar="FILE|-", help="saved result JSON, or - for piped input")
    prose = commands.add_parser("prose", help="prepare prose-only analysis input, retaining headings as metadata")
    for command in (term, check, prose):
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

        origin = result = None
        # Reject unsafe input before inspecting corpus/configuration data.
        if options.action == "check":
            result = decode_term_result(read_json_input(options.file, MAX_RESULT_BYTES))
        elif options.action == "term" and options.reference is not None:
            origin = decode_reference(read_json_input(options.reference, MAX_REFERENCE_BYTES))
        directory = discover_corpus(options.corpus)
        if directory is None:
            raise ValueError("No canonical corpus configured; use --corpus DIRECTORY or sol --set-corpus DIRECTORY")
        snapshot = load_snapshot(directory)
        if options.action == "prose":
            from sol.essence.prose import export_prose
            result = export_prose(snapshot)
            print(_json(result) if options.json else (
                f"{len(result['passages'])} prose passages ready for analysis; "
                f"{result['exclusions']['excluded_records']} records excluded.\n"
                "Vector input: passages[].text (headings and image labels excluded).\n"
                "Canonical ancestry, headings and source references remain in metadata.\n"
                "Use sol analyze prose --json to export the complete input."))
        elif options.action == "term":
            result = analyze_term(snapshot, options.word, origin=origin,
                                  doctrine=options.doctrine.upper() if options.doctrine else None,
                                  limit=options.limit)
            print(encode_term_result(result) if options.json else render_result(result))
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
