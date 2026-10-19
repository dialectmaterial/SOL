"""Sentence provider CLI; file execution and verification never import CORE."""
from __future__ import annotations

from sol.essence.sentences import SentenceStudyError, analyze_sentences, check_sentence_result, encode_sentence_result
from sol.essence.word_cli import _provider, read_artifact
from sol.essence.word_inputs import FileProvider


def render_sentences(result):
    from sol.essence.cli import _safe, _location

    part, summary = result["input"], result["summary"]
    scope = part["scope"]
    label = (f"characters {scope['start']}–{scope['end']}" if scope["kind"] == "span"
             else "whole file" if scope["kind"] == "file" else scope.get("path", scope["kind"]))
    lines = [f"Sentence lengths: {part['provider']} ({_safe(label)})",
             "Word tokens per sentence; punctuation-rules-v1 on the original text.",
             "Only complete sentences contained in the scope are measured.",
             "Positions are among retained sentences in each input row (one CORE passage or the whole file)."]
    if part["provider"] == "file":
        lines.append("File digest and offsets only; no CORE identity or verified source return.")
    if summary["sentences"]:
        lines += ["", f"{summary['sentences']} sentences, {summary['tokens']} tokens in {len(part['inputs'])} input row(s).",
                  f"Mean {summary['mean']:.1f}, median {summary['median']}, 10th–90th percentile "
                  f"{summary['p10']}–{summary['p90']}, longest {summary['max']}."]
        peak = max(row["sentences"] for row in result["histogram"]) or 1
        lines.append("")
        for row in result["histogram"]:
            span = f"{row['from']}–{row['to']}" if row["to"] is not None else f"{row['from']}+"
            lines.append(f"  {span:>7} {row['sentences']:>6}  " + "█" * round(24 * row["sentences"] / peak))
        lines += ["", "By position in the input row (mean tokens):"]
        for name, values in result["by_position"].items():
            if values["sentences"]:
                lines.append(f"  {name:6} {values['mean']:6.1f}  ({values['sentences']} sentences)")
        lines += ["", "Longest sentences:"]
        for number in result["longest"]:
            index, start, end, tokens = result["sentences"][number]
            row = part["inputs"][index]
            location = (f"{_safe(row['reader_path'])} ({_location(row['sources'])}), {_safe(row['id'])}"
                        if part["provider"] == "core" else "text file")
            lines.append(f"  {tokens:>4} tokens  {location} at {start}–{end}")
    else:
        lines += ["", "No eligible sentences in this scope."]
    excluded = result["exclusions"]
    lines += ["", f"Excluded: {excluded['outside_span']} segments outside/crossing the span; "
                  f"{excluded['empty_segments']} without word tokens; {excluded['masked_segments']} facsimile labels."]
    if part["provider"] == "core":
        lines.append("Excluded records: " + ", ".join(f"{key}={count}" for key, count in excluded["by_reason"].items()))
    return "\n".join(lines)


def run(options, result=None):
    """Read caller-selected sources, preserve v1 receipts, emit v2 for providers."""
    from sol.essence.cli import _json, render_sentences as render

    if result is not None and (options.compare or any(getattr(options, "reference_" + name) is not None
                for name in ("provider", "file", "corpus", "within", "passage", "span"))):
        raise SentenceStudyError("Sentence studies take one input provider, not a reference comparison", code="invalid_input")
    saved = (result["input"] if result["version"] == 2 else {"provider": "core", "scope": result["scope"]}) if result else None
    if result is None and options.input_file is not None and options.reference is not None:
        raise SentenceStudyError("A file study cannot have a CORE reference anchor", code="invalid_origin")
    origin = None
    if result is None and options.reference is not None:
        from sol.core import decode_reference
        origin = decode_reference(read_artifact(options.reference))
    provider = _provider(options, saved=saved)
    result = analyze_sentences(provider, origin=origin) if result is None else check_sentence_result(provider, result)
    if options.action == "check":
        if result["version"] == 1:
            receipt = {"status": "current", "protocol": result["protocol"], "corpus_id": result["corpus"]["id"],
                       "generation": result["generation"], "summary": result["summary"]}
            message = "Verified against the current corpus generation."
        else:
            receipt = {"status": "current", "protocol": result["protocol"], "version": 2,
                       "provider": result["input"]["provider"], "binding": result["input"]["binding"],
                       "summary": result["summary"]}
            message = "Verified against the current file digest." if isinstance(provider, FileProvider) else "Verified against the current corpus generation."
        print(_json(receipt) if options.json else message + "\n\n" + render(result))
    else:
        print(encode_sentence_result(result) if options.json else render(result))
    return 0
