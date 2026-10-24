"""Analysis inputs and experiments over a selected local corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import unicodedata


def build_parser() -> argparse.ArgumentParser:
    """Build help without importing analysis or opening any local data."""
    parser = argparse.ArgumentParser(
        prog="sol essence", description="Run and verify transparent, read-only corpus experiments.")
    commands = parser.add_subparsers(dest="action", required=True)
    sentences = commands.add_parser("sentences", help="measure sentence lengths in the English translation")
    from sol.essence.word_cli import add_input_arguments
    add_input_arguments(sentences, words=True, unit="sentences")
    sentences.add_argument("--reference", metavar="FILE|-", help="optional CORE reference anchor; it does not restrict the scope")
    sentences.add_argument("--segmentation", choices=("punctuation-rules-v1", "punctuation-rules-v2"),
                           help="sentence method (default: punctuation-rules-v1; explicit choice uses providers)")
    words = commands.add_parser("words", help="count normalized words with explicit target/reference denominators")
    from sol.essence.word_cli import add_arguments
    add_arguments(words, words=True)
    tfidf = commands.add_parser("tfidf", help="rank lexical terms per provider document and overall")
    add_input_arguments(tfidf, words=True)
    tfidf.add_argument("--top-n", type=int, default=20, metavar="N", help="terms per document and overall, 1–1000 (default: 20)")
    check = commands.add_parser("check", help="recompute and verify a saved experiment against the local corpus")
    check.add_argument("file", metavar="FILE|-", help="saved result JSON, or - for piped input")
    add_arguments(check)
    word_export = commands.add_parser("words-export", help="verify a saved target/reference study and export CSV or TSV")
    word_export.add_argument("file", metavar="FILE|-", help="saved sol.word-frequencies v1 JSON, or piped input")
    word_export.add_argument("--format", choices=("csv", "tsv"), default="csv", help="table format (default: csv)")
    word_export.add_argument("--corpus", type=Path, metavar="DIRECTORY", help="explicit CORE target corpus")
    word_export.set_defaults(json=False)
    add_arguments(word_export)
    prose = commands.add_parser("prose", help="prepare prose-only analysis input, retaining headings as metadata")
    for command in (sentences, words, tfidf, check, prose):
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


def _location(sources: list[dict]) -> str:
    def page(source):
        label = source["printed_page"]
        return f"printed {_safe(label) if label is not None else '?'} / PDF {source['pdf_page']}"
    first = page(sources[0])
    return first if len(sources) == 1 else first + " to " + page(sources[-1])


def render_sentences(result: dict) -> str:
    """Summarize a sentence study; locations only, never stored book text."""
    if result.get("version") == 2:
        from sol.essence.sentence_cli import render_sentences as render_provider_sentences
        return render_provider_sentences(result)
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
        if options.action == "tfidf":
            from sol.essence.tfidf_cli import run
            return run(options)
        if options.action == "words-export":
            from sol.essence.word_cli import run_export
            return run_export(options)
        if options.action == "words":
            from sol.essence.word_cli import run
            return run(options)
        if options.action == "sentences" and (options.segmentation is not None
                                               or options.input_file is not None or options.provider is not None
                                               or options.passage is not None or options.span is not None):
            from sol.essence.sentence_cli import run
            return run(options)
        if options.action == "check":
            from sol.essence.word_cli import read_artifact, run
            from sol.essence.essence_as_reflection_within_itself.words import decode_word_result
            raw = read_artifact(options.file)
            data = raw.encode("utf-8") if isinstance(raw, str) else raw
            # Decode JSON for dispatch: whitespace and escaped protocol names
            # must not route a word artifact through a corpus-only study.
            try:
                header = json.loads(data)
            except (ValueError, UnicodeError, RecursionError):
                header = None
            if isinstance(header, dict) and header.get("protocol") == "sol.tfidf":
                from sol.essence.essence_as_reflection_within_itself.tfidf import decode_tfidf_result
                from sol.essence.tfidf_cli import run as run_tfidf
                return run_tfidf(options, decode_tfidf_result(data))
            if isinstance(header, dict) and header.get("protocol") == "sol.word-frequencies":
                return run(options, decode_word_result(data))
            if isinstance(header, dict) and header.get("protocol") == "sol.sentence-study":
                from sol.essence.essence_as_reflection_within_itself.sentences import decode_sentence_result
                from sol.essence.sentence_cli import run as run_sentences
                return run_sentences(options, decode_sentence_result(data))
            raise ValueError("Unsupported ESSENCE artifact protocol")
        from sol.core import MAX_REFERENCE_BYTES, decode_reference, discover_corpus, load_snapshot
        from sol.core.wire import read_json_input
        from sol.essence.essence_as_reflection_within_itself import sentences as sentence_study

        origin = None
        # Reject unsafe references before discovery.
        if options.action == "sentences" and options.reference is not None:
            origin = decode_reference(read_json_input(options.reference, MAX_REFERENCE_BYTES))
        directory = discover_corpus(options.corpus)
        if directory is None:
            raise ValueError("No canonical corpus configured; use --corpus DIRECTORY or sol --set-corpus DIRECTORY")
        snapshot = load_snapshot(directory)
        if options.action == "prose":
            from sol.essence.essence_as_reflection_within_itself.prose import export_prose
            result = export_prose(snapshot)
            print(_json(result) if options.json else (
                f"{len(result['passages'])} prose passages ready for analysis; "
                f"{result['exclusions']['excluded_records']} records excluded.\n"
                "Vector input: passages[].text (headings and image labels excluded).\n"
                "Canonical ancestry, headings and source references remain in metadata.\n"
                "Use sol essence prose --json to export the complete input."))
        elif options.action == "sentences":
            scope = {"kind": "within", "path": options.within} if options.within is not None else None
            if scope is not None:
                sentence_study._scope(scope)
                if not any(sentence_study._in_scope(record, scope) for record in snapshot.records):
                    raise sentence_study.SentenceStudyError("Reader path names no records", code="invalid_scope")
            result = sentence_study.analyze_sentences(snapshot, scope=scope, origin=origin)
            print(sentence_study.encode_sentence_result(result) if options.json else render_sentences(result))
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
