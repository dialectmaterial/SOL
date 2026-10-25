"""Headless word-study adapter; ordinary files require neither CORE nor a UI."""
from __future__ import annotations

from pathlib import Path
import sys

from sol.essence.essence_as_reflection_within_itself.word_inputs import CoreProvider, FileProvider, WordStudyError, _read_file
from sol.essence.essence_as_reflection_within_itself.words import MAX_RESULT_BYTES, analyze_words, check_word_result, decode_word_result, encode_word_result


def add_input_arguments(parser, *, words=False, unit="tokens"):
    """Shared provider and target-scope options for words and sentences."""
    parser.add_argument("--provider", choices=("core", "file"), help="default: file with --input-file, otherwise core")
    flags = ("--input-file", "--file") if words else ("--input-file",)
    parser.add_argument(*flags, dest="input_file", type=Path, metavar="TEXT", help="explicit regular UTF-8 target file")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--within", metavar="PATH", help="CORE target reader path")
    target.add_argument("--passage", action="append", metavar="UUID", help="exact CORE target ID; repeat for several")
    parser.add_argument("--span", nargs=2, type=int, metavar=("START", "END"),
                        help=f"half-open codepoints in the file or single --passage; count only whole contained {unit}")


def add_arguments(parser, *, words=False):
    add_input_arguments(parser, words=words)
    parser.add_argument("--compare", action="store_true", help="compare with the whole target source")
    parser.add_argument("--reference-provider", choices=("core", "file"))
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--reference-file", type=Path, metavar="TEXT", help="explicit UTF-8 reference file")
    source.add_argument("--reference-corpus", type=Path, metavar="DIRECTORY", help="independent CORE reference corpus")
    reference = parser.add_mutually_exclusive_group()
    reference.add_argument("--reference-within", metavar="PATH", help="CORE reference reader path")
    reference.add_argument("--reference-passage", action="append", metavar="UUID", help="exact reference ID; repeatable")
    parser.add_argument("--reference-span", nargs=2, type=int, metavar=("START", "END"))


def read_artifact(filename):
    """Bounded transport without importing CORE or following artifact paths."""
    if filename != "-":
        try:
            return _read_file(Path(filename).expanduser(), MAX_RESULT_BYTES)
        except WordStudyError as error:
            # Transport refusals retain the legacy check command's status;
            # freshness refusals belong to the study verifier.
            raise ValueError(str(error)) from error
    if sys.stdin.isatty():
        raise WordStudyError("JSON FILE or piped input is required; interactive stdin is not supported", code="invalid_input")
    stream = getattr(sys.stdin, "buffer", sys.stdin)
    first_limit = 1048576  # Legacy artifacts keep their original first read.
    data = stream.read(first_limit + 1)
    if len(data.encode("utf-8") if isinstance(data, str) else data) > first_limit:
        data += stream.read(MAX_RESULT_BYTES + 1 - len(data))
    if len(data.encode("utf-8") if isinstance(data, str) else data) > MAX_RESULT_BYTES:
        raise WordStudyError("Artifact exceeds 16 MiB", code="size_limit")
    return data


def _provider(options, *, reference=False, saved=None, target=None):
    prefix = "reference_" if reference else ""
    file = getattr(options, "reference_file" if reference else "input_file")
    corpus = options.reference_corpus if reference else options.corpus
    kind = getattr(options, prefix + "provider") or ("file" if file else "core" if corpus else
           saved["provider"] if saved else "file" if reference and isinstance(target, FileProvider) else "core")
    within, passages, span = (getattr(options, prefix + name) for name in ("within", "passage", "span"))
    if file is not None and kind != "file" or corpus is not None and kind != "core":
        raise WordStudyError("Source options disagree with the provider", code="invalid_provider")
    if kind == "file" and (within is not None or passages is not None):
        raise WordStudyError("Reader paths and passage IDs require CORE", code="invalid_scope")
    if span is not None:
        if within is not None or kind == "core" and (passages is None or len(passages) != 1):
            raise WordStudyError("CORE --span requires exactly one --passage and no --within", code="invalid_scope")
        scope = {"kind": "span", "start": span[0], "end": span[1]}
        if kind == "core":
            scope["id"] = passages[0]
    elif within is not None:
        scope = {"kind": "within", "path": within}
    elif passages is not None:
        scope = {"kind": "passages", "ids": passages}
    else:
        scope = saved["scope"] if saved is not None else None
    if kind == "file":
        if file is None:
            # A saved reference always needs explicit sources. An interactive
            # comparison over two spans of one file can reuse the target path.
            file = target.path if reference and isinstance(target, FileProvider) else None
        if file is None:
            raise WordStudyError("File studies require --input-file (and --reference-file for a different reference)", code="missing_file")
        return FileProvider(file, scope)
    from sol import core

    if reference and corpus is None and isinstance(target, CoreProvider):
        snapshot = target.snapshot
    else:
        directory = core.discover_corpus(corpus)
        if directory is None:
            raise WordStudyError("No canonical corpus configured; use --corpus DIRECTORY", code="missing_corpus")
        snapshot = core.load_snapshot(directory)
    return CoreProvider(snapshot, scope)


def render_words(result):
    from sol.essence.cli import _safe

    lines = ["Word frequencies (literal normalized words)."]
    for name in ("target", "reference"):
        source = result[name]
        if source is None:
            continue
        counts = source["summary"]
        lines.append(f"{name.capitalize()} ({source['provider']}): {counts['token_count']} tokens (rate denominator), "
                     f"{counts['type_count']} types, {counts['input_count']} input rows.")
        exclusions = source["exclusions"]
        lines.append(f"  Excluded records: {sum(exclusions['by_reason'].values())}; "
                     f"masked facsimile tokens: {exclusions['masked_tokens']}.")
    lines += [_safe(warning) for warning in result["warnings"]]
    lines += ["", "Word  target count / denominator  per 10,000" +
              ("  | reference count / denominator  per 10,000" if result["reference"] is not None else "")]
    for row in result["frequencies"]:
        cells = []
        for name in ("target", "reference"):
            cell = row[name]
            if cell is not None:
                rate = "n/a" if cell["rate_per_10000_tokens"] is None else f"{cell['rate_per_10000_tokens']:.6f}"
                cells.append(f"{cell['count']} / {cell['denominator']}  {rate}")
        lines.append(_safe(row["word"]) + "  " + "  | ".join(cells))
    lines.append("Use --json for every input ID, page, digest and first-occurrence codepoint span.")
    return "\n".join(lines)


def _providers(options, result=None):
    """Explicit sources and optional saved scopes, shared with verified export."""
    target = _provider(options, saved=result["target"] if result else None)
    requested = options.compare or any(getattr(options, "reference_" + name) is not None
                                      for name in ("provider", "file", "corpus", "within", "passage", "span"))
    saved_reference = result["reference"] if result else None
    # Reuse the target path only for the same saved file-byte binding.
    if (saved_reference is not None and saved_reference["provider"] == "file"
            and options.reference_file is None and options.reference_provider in (None, "file")
            and options.reference_corpus is None and saved_reference["binding"] != result["target"]["binding"]):
        raise WordStudyError("Independent file references require --reference-file", code="missing_file")
    reference = _provider(options, reference=True, saved=saved_reference, target=target) if requested or saved_reference is not None else None
    return target, reference


def run_export(options):
    """Decode before opening sources, then strictly verify before tabular output."""
    from sol.essence.essence_as_reflection_within_itself.comparison import export_word_comparison

    result = decode_word_result(read_artifact(options.file))
    target, reference = _providers(options, result)
    output = export_word_comparison(target, reference=reference, result=result, format=options.format)
    sys.stdout.write(output)
    return 0


def run(options, result=None):
    """Both CLI execution and verification use the public engine function."""
    target, reference = _providers(options, result)
    result = analyze_words(target, reference=reference) if result is None else check_word_result(target, result, reference=reference)
    if options.json:
        if options.action == "check":
            from sol.essence.cli import _json
            print(_json({"status": "current", "protocol": result["protocol"], "version": result["version"],
                         "target": {key: result["target"][key] for key in ("provider", "binding", "summary")},
                         "reference": {key: result["reference"][key] for key in ("provider", "binding", "summary")}
                         if result["reference"] is not None else None}))
        else:
            print(encode_word_result(result))
    else:
        print(("Verified against the current source bindings.\n\n" if options.action == "check" else "") + render_words(result))
    return 0
