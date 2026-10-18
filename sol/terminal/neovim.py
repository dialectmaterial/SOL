"""Native Neovim host over exact, verified SOL records.

This deliberately does not embed Neovim's screen, load a user's configuration,
or open a personal workspace. Buffer bytes are presentation; packets leaving
the editor must pass the existing CORE/ReaderActions source checks again.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata

from sol.reader.typography import map_typography
from sol.terminal.text import emphasis_style
from sol.terminal.runtime import managed_neovim
from sol.terminal.theme import theme_payload

from sol.reader.surface import (CaptureExport, Sample, FOOTNOTE_DEPTH, FOOTNOTE_LINKS,
                                footnote_links, footnote_scope, note_paragraph_ids, record_payload, validate_packet)


MAX_PACKET_BYTES = 1024 * 1024
_STOP_SERVERS = "lua for _, address in ipairs(vim.fn.serverlist()) do vim.fn.serverstop(address) end"
_LOAD_ADAPTER = "lua dofile(vim.env.SOL_NVIM_ADAPTER)"
_READ_ONLY_OPTIONS = "set nomodeline noexrc noswapfile nobackup nowritebackup noundofile"


def _width(width):
    if type(width) is not int or not 20 <= width <= 240:
        raise ValueError("Neovim reading width must be between 20 and 240 columns")


def validate_environment(width=72):
    """Refuse unsuitable hosts before loading a corpus or creating artifacts."""
    _width(width)
    if (not getattr(sys.stdin, "isatty", lambda: False)()
            or not getattr(sys.stdout, "isatty", lambda: False)()
            or os.environ.get("TERM", "").strip() in {"", "dumb"}):
        raise ValueError("the Neovim reader needs interactive terminal input and output with TERM other than dumb")
    private = managed_neovim()
    executable = str(private) if private.is_file() else shutil.which("nvim")
    if executable is None:
        raise ValueError("SOL needs Neovim 0.11 or newer. From the checkout run python3 scripts/install.py "
                         "to complete installation, or install Neovim using your system package manager.")
    try:
        # Even a version probe must not acquire a user's log or state path.
        with tempfile.TemporaryDirectory(prefix="sol-neovim-version-") as temporary:
            root = Path(temporary)
            environment = _isolated_environment(root, root / "unused-input", root / "unused-output")
            result = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                    check=False, timeout=5, cwd=root, env=environment)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Neovim version check timed out; the reader was not launched") from error
    match = re.match(r"NVIM v(\d+)\.(\d+)(?:\.|\b)", result.stdout)
    if result.returncode or match is None or tuple(map(int, match.groups())) < (0, 11):
        raise ValueError("SOL requires Neovim 0.11 or newer. Run python3 scripts/install.py from the checkout.")
    return executable


def _safe_source(text):
    if not isinstance(text, str):
        raise ValueError("Neovim presentation requires exact source strings")
    # Neovim visibly escapes C1 characters with display=uhex. Keep their exact
    # bytes/codepoints in the buffer; do not replace a scalar with four source
    # characters. Unsafe controls/bidi are refused, never silently normalized.
    if any((unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"}
            and char not in {"\n", "\t"} and not 0x80 <= ord(char) <= 0x9f) for char in text):
        raise ValueError("The reader refuses unsafe control/bidi source characters; canonical text was not altered. "
                         "Use sol -r --json to inspect the source and its review status.")


def _safe_metadata(value):
    """Metadata must not become a route for terminal controls either."""
    if isinstance(value, str):
        _safe_source(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            _safe_source(key)
            _safe_metadata(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _safe_metadata(item)


def _styles(markdown, text):
    typography = map_typography(markdown, text)
    spans = [{"start": span.start, "end": span.end, "styles": list(span.styles)}
             for span in typography.spans]
    warning = ([typography.reason or "Semantic typography unavailable; plain text shown."]
               if typography.degraded else [])
    return spans, warning


def _check_sample_packet(sample, packet, records=None):
    """Validate locally, then fence a research packet to this bounded sample."""
    selected = validate_packet(sample.book, packet)
    target = packet["reference"]["reference"]["target_id"]
    if target not in {passage.identifier for passage in sample.passages}:
        raise ValueError("research packet targets a passage outside this Neovim sample")
    if records is not None:
        record = next(record for record in records if record["id"] == target)
        if packet["reference"] != record["reference"]:
            raise ValueError("research packet must use this sample's exact checked reference")
    return selected


def build_footnote_payload(sample: Sample, passage_id: str, trail: list[str]) -> dict:
    """One source-checked book note; opening it never moves or saves a visit."""
    if passage_id not in {passage.identifier for passage in sample.passages}:
        raise ValueError("footnote origin is outside the shown reading section")
    identifiers = footnote_scope(sample.book, passage_id, trail)
    capture = CaptureExport(sample.book, identifiers=identifiers)
    checked = {identifier: capture.capture(identifier) for identifier in identifiers}
    reference, resolved = checked[trail[-1]]
    note = resolved.record
    bodies = note_paragraph_ids(sample.book).get(note["id"], [])
    parts = [checked[identifier][1].record for identifier in bodies] or [note]
    links = []
    linked = footnote_links([note, *parts])
    for identifier in linked[:FOOTNOTE_LINKS]:
        target = capture.records.get(identifier)
        label = str(target.get("label") or "?") if target else "?"
        if target is None or target.get("type") != "note":
            refusal = "Unresolved canonical footnote; source text was not substituted."
        elif identifier in trail:
            refusal = "Cycle: this footnote is already open; use Backspace to return to it."
        elif len(trail) >= FOOTNOTE_DEPTH:
            refusal = f"Footnote nesting is limited to {FOOTNOTE_DEPTH} notes; return before following another."
        else:
            refusal = ""
        links.append({"id": identifier, "label": label, "refusal": refusal})
    labels = {row["id"]: row["label"] for row in links}
    paragraphs = []
    text_bytes = 0
    for part in parts:
        text = part["plain_text"]
        text_bytes += len(text.encode("utf-8"))
        if text_bytes > MAX_PACKET_BYTES:
            raise ValueError("footnote text exceeds the 1 MiB view limit; source is unchanged")
        _safe_source(text)
        styles, warnings = _styles(part["markdown"], text)
        if part.get("transcription_status") in {"needs_review", "needs_visual_review"}:
            warnings.insert(0, "Note transcription needs review.")
        if any(0x80 <= ord(char) <= 0x9f for char in text):
            warnings.append("Nonprinting source characters are shown as hexadecimal markers.")
        callouts = [{"offset": offset, "label": labels.get(identifier, "?")}
                    for offset, identifier in map_typography(part["markdown"], text).callouts]
        paragraphs.append({"id": part["id"], "reference": checked[part["id"]][0],
                           "plain_text": text, "styles": styles, "warnings": warnings,
                           "attribution": deepcopy(part["attribution"]), "callouts": callouts})
    warnings = []
    if note.get("transcription_status") in {"needs_review", "needs_visual_review"}:
        warnings.append("Note transcription needs review.")
    if len(linked) > FOOTNOTE_LINKS:
        warnings.append(f"Only the first {FOOTNOTE_LINKS} linked notes are listed in this view.")
    result = {"id": note["id"], "label": str(note.get("label") or "?"), "reference": reference,
              "attribution": deepcopy(note["attribution"]), "warnings": warnings,
              "paragraphs": paragraphs, "links": links, "trail": list(trail)}
    _safe_metadata(result)
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 4 * MAX_PACKET_BYTES:
        raise ValueError("footnote presentation exceeds the 4 MiB view limit; source is unchanged")
    capture.finish()
    return result


def build_payload(sample: Sample, width=72, restore=None, *, requested_ids=None, emphasis="auto", theme=None):
    """Prepare inert JSON; every selection offset remains a source codepoint.

    Only supplied document headings are projected. No experiment title or
    concatenated canonical record is introduced into the reading surface.
    A theme adds presentation presets only; research samples omit it.
    """
    _width(width)
    if sample.actions.workspace_reader is not None:
        raise ValueError("Neovim reader experiments do not accept a personal workspace")
    if not 1 <= len(sample.passages) <= 64:
        raise ValueError("Neovim reader proof needs between 1 and 64 canonical passages")
    if len({passage.identifier for passage in sample.passages}) != len(sample.passages):
        raise ValueError("Neovim reader proof needs distinct canonical passages")
    if restore is not None:
        _check_sample_packet(sample, restore)
    requested_ids = requested_ids or {}
    if set(requested_ids) - {p.identifier for p in sample.passages}:
        raise ValueError("requested references must belong to the displayed reading section")
    capture = CaptureExport.for_sample(sample, requested_ids)
    bodies = note_paragraph_ids(sample.book)
    records = []
    for passage in sample.passages:
        requested = requested_ids.get(passage.identifier, passage.identifier)
        payload = record_payload(sample, passage, capture=capture, requested_id=requested)
        _, checked = capture.capture(requested)
        record = checked.record
        _safe_source(payload["plain_text"])
        styles, warnings = _styles(record["markdown"], payload["plain_text"])
        if passage.needs_source_review:
            warnings.insert(0, "Source transcription needs review.")
        if any(0x80 <= ord(char) <= 0x9f for char in payload["plain_text"]):
            warnings.append("Nonprinting source characters are shown as hexadecimal markers.")
        context = {"path": "/" + "/".join(passage.path),
                   "printed_pages": [passage.printed_page, passage.end_printed_page],
                   "pdf_pages": [passage.pdf_page, passage.end_pdf_page],
                   "attribution": deepcopy(record["attribution"])}
        heading = passage.heading or passage.node.title
        _safe_metadata({"heading": heading, "context": context, "warnings": warnings})
        notes, labels = [], {}
        for identifier in record.get("note_ids", []):
            reference, checked_note = capture.capture(identifier)
            note = checked_note.record
            if note.get("type") != "note":
                raise ValueError("a referenced canonical note is unavailable")
            # The note record is only a heading; its text is in its body records.
            parts = [capture.capture(body)[1].record for body in bodies.get(note["id"], [])] or [note]
            text, note_styles, note_warnings = "", [], []
            for part in parts:
                offset = len(text) + 2 if text else 0
                text = text + "\n\n" + part["plain_text"] if text else part["plain_text"]
                spans, degraded = _styles(part["markdown"], part["plain_text"])
                note_styles += [{**span, "start": span["start"] + offset, "end": span["end"] + offset} for span in spans]
                note_warnings += [warning for warning in degraded if warning not in note_warnings]
            _safe_source(text)
            if any(part.get("transcription_status") in {"needs_review", "needs_visual_review"} for part in [note, *parts]):
                note_warnings.insert(0, "Note transcription needs review.")
            attribution = deepcopy(note["attribution"])
            label = str(note.get("label") or "")
            labels[identifier] = labels[note["id"]] = label
            _safe_metadata({"attribution": attribution, "warnings": note_warnings, "label": label})
            notes.append({"label": label, "plain_text": text, "attribution": attribution,
                          "styles": note_styles, "warnings": note_warnings, "reference": reference})
        # Callouts outside this record's notes (or unplaced) are not invented.
        callouts = [{"offset": offset, "label": labels[note] or "?"}
                    for offset, note in map_typography(record["markdown"], payload["plain_text"]).callouts
                    if note in labels]
        payload.update(heading=heading, styles=styles, warnings=warnings, context=context, notes=notes,
                       callouts=callouts)
        records.append(payload)
    if restore is not None:
        # Match the browser proof's strict, disposable packet policy; aliases
        # are not silently rewritten into a new requested identity.
        _check_sample_packet(sample, restore, records)
    capture.finish()
    payload = {"records": records, "width": width, "emphasis": emphasis_style(emphasis),
               "restore": deepcopy(restore)}
    if theme is not None:
        payload["theme"] = theme_payload(theme)
    return payload


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate research packet JSON field")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"non-finite research packet JSON value: {value}")


def _read_packet(path):
    """Bound reads, reject duplicate keys and refuse nonregular input files."""
    path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("research packet must be a regular file")
        if metadata.st_size > MAX_PACKET_BYTES:
            raise ValueError("research packet exceeds 1 MiB")
        data = stream.read(MAX_PACKET_BYTES + 1)
    if len(data) > MAX_PACKET_BYTES:
        raise ValueError("research packet exceeds 1 MiB")
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_fields,
                      parse_constant=_reject_constant)


def _check_destination(sample, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite an existing research packet: {output}")
    corpus = sample.book.corpus_directory
    if corpus is not None and (corpus.resolve() == output.resolve()
                               or corpus.resolve() in output.resolve().parents):
        raise ValueError("choose a packet output outside the read-only canonical corpus directory")
    if not output.parent.is_dir():
        raise ValueError("research packet output parent directory must already exist")
    return output


def _write_json(path, value):
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
        stream.write(encoded)


def _isolated_environment(root, input_path, output_path):
    environment = os.environ.copy()
    for key in ("SOL_NVIM_REQUEST_FD", "SOL_NVIM_RESPONSE_FD"):
        environment.pop(key, None)
    for key in tuple(environment):
        if key.startswith("NVIM") or key in {"VIM", "VIMRUNTIME", "VIMINIT", "EXINIT", "GVIMINIT", "MYVIMRC", "LUA_PATH", "LUA_CPATH"}:
            environment.pop(key)
    for variable, name in (("XDG_CONFIG_HOME", "config"), ("XDG_CONFIG_DIRS", "config-dirs"),
                           ("XDG_DATA_HOME", "data"), ("XDG_DATA_DIRS", "data-dirs"),
                           ("XDG_STATE_HOME", "state"), ("XDG_CACHE_HOME", "cache"),
                           ("XDG_RUNTIME_DIR", "runtime"), ("TMPDIR", "tmp")):
        directory = root / name
        directory.mkdir(mode=0o700)
        environment[variable] = str(directory)
    environment.update(SOL_NVIM_INPUT=str(input_path), SOL_NVIM_OUTPUT=str(output_path),
                       SOL_NVIM_ADAPTER=str(Path(__file__).with_name("neovim.lua").resolve()),
                       NVIM_LOG_FILE=str(root / "neovim.log"), NVIM_APPNAME="sol-reader")
    return environment


def launch_payload(payload, executable, *, on_request=None):
    """One native, isolated terminal session; its result is still untrusted."""
    adapter = Path(__file__).with_name("neovim.lua")
    if not adapter.is_file():
        raise RuntimeError("the optional Neovim reader adapter is unavailable; reinstall SOL")
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > 16 * 1024 * 1024:
        raise ValueError("the reading section exceeds Neovim's 16 MiB presentation budget")
    with tempfile.TemporaryDirectory(prefix="sol-neovim-reader-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        input_path, output_path = root / "input.json", root / "result.json"
        environment = _isolated_environment(root, input_path, output_path)
        _write_json(input_path, payload)
        command = [executable, "--clean", "-u", "NONE", "-i", "NONE", "-n", "--noplugin",
                   "--cmd", _READ_ONLY_OPTIONS, "-c", _STOP_SERVERS, "-c", _LOAD_ADAPTER]
        try:
            # Inherit the real terminal: its screen is not embedded or piped.
            # Optional action pipes carry data only, with no shell or listener.
            # Native startup briefly creates its own
            # private RPC socket; the first -c immediately stops every listener.
            if on_request is None:
                code = subprocess.run(command, cwd=root, env=environment, check=False).returncode
            else:
                from sol.terminal.reader_channel import run_native
                code = run_native(command, cwd=root, env=environment, handler=on_request)
        except KeyboardInterrupt:
            return 130, None
        if code:
            return (code if code > 0 else 128 - code), None
        return 0, _read_packet(output_path) if output_path.exists() else None


def run(sample: Sample, width=72, export=None, restore=None):
    """Research entry: validate returned identity before optional private export."""
    executable = validate_environment(width)
    destination = None if export is None else _check_destination(sample, export)
    restored = None if restore is None else _read_packet(restore)
    payload = build_payload(sample, width=width, restore=restored)
    status, packet = launch_payload(payload, executable)
    if status:
        return status
    if packet is None:
        if destination is not None:
            raise ValueError("Neovim exited without a captured packet; use q on source text to export")
        return 0
    _check_sample_packet(sample, packet, payload["records"])
    if destination is not None:
        # The editor may have remained open while the filesystem changed.
        _check_destination(sample, destination)
        _write_json(destination, packet)
        print(f"Created private checked research packet: {destination.resolve()}")
    return 0
