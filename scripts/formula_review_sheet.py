#!/usr/bin/env python3
"""Private printed-formula review aid, run from a checkout; never applies reviews.

create writes an offline HTML sheet, source-bound JSON and an empty verdict log.
review prompts through pending items; record appends one attributed verdict.
check validates the sheet/log, optionally against the current corpus generation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sol import core
from sol.corpus.contract import verify_snapshot_current
from sol.terminal import source


FORMAT = "sol.formula-review-sheet"
MAX_BYTES = 16 * 1024 * 1024
VERDICTS = ("confirmed", "needs_correction")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _outside_git(path):
    path = Path(path).expanduser()
    if path.is_symlink():
        raise ValueError("review paths must not be symbolic links")
    path = path.resolve()
    for directory in (path, *path.parents):
        if ((directory / ".git").is_file() or (directory / ".git" / "HEAD").is_file()
                or ((directory / "HEAD").is_file() and (directory / "objects").is_dir())):
            raise ValueError("book text, crops and verdicts must stay outside every Git checkout")
    return path


def _write(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600), "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _read(path):
    if path.is_symlink():
        raise ValueError("review files must not be symbolic links")
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError("review metadata must be a regular file of at most 16 MiB")
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("review metadata exceeds 16 MiB")
    return data


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON field in review metadata")
        result[key] = value
    return result


def _decode(data):
    def invalid(value):
        raise ValueError(f"invalid JSON constant: {value}")
    return json.loads(data, object_pairs_hook=_pairs, parse_constant=invalid)


def _binding(snapshot):
    return {"id": snapshot.corpus_id, "manifest_sha256": snapshot.manifest_sha256,
            "index_sha256": snapshot.index_sha256, "index_metadata_sha256": snapshot.index_metadata_sha256,
            "documents": snapshot.documents}


def _html(sheet, destination):
    items = []
    for number, row in enumerate(sheet["records"], 1):
        pages = []
        for page in row["pages"]:
            label = page["printed_page"] if page["printed_page"] is not None else "not recorded"
            caption = f'PDF page {page["pdf_page"]} · printed page {label} · '
            caption += "recorded crop" if page["cropped"] else "whole page (no recorded bounding box)"
            pages.append(f'<figure><a href="{escape(page["image"], quote=True)}">'
                         f'<img loading="lazy" src="{escape(page["image"], quote=True)}" '
                         f'alt="{escape(caption, quote=True)}"></a><figcaption>{escape(caption)}</figcaption></figure>')
        attribution = row["attribution"]
        credit = " · ".join(str(attribution[key]) for key in ("role", "status", "author") if attribution.get(key) is not None)
        items.append(f'<article id="item-{number}"><h2>{number}. {escape(row["id"])}</h2>'
                     f'<p>{escape(row["type"])} · {escape(credit)}</p>'
                     '<p class="warning">Needs visual review. Compare every symbol with the printed source.</p>'
                     f'<div class="comparison"><section><h3>Typed text</h3><pre>{escape(row["plain_text"])}</pre>'
                     f'<details><summary>Canonical Markdown</summary><pre>{escape(row["markdown"])}</pre></details>'
                     f'</section><section><h3>Printed source</h3>{"".join(pages)}</section></div></article>')
    command = ".venv/bin/python scripts/formula_review_sheet.py review --sheet " + shlex.quote(str(destination)) + ' --reviewer "Your name"'
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' file:; '
            'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            '<title>SOL formula review sheet</title><style>'
            'body{margin:0 auto;padding:2rem;max-width:100rem;background:#faf8f2;color:#222;font:17px/1.6 system-ui,sans-serif}'
            'h1,h2,h3{line-height:1.3}h2{font-size:1.1rem;overflow-wrap:anywhere}article{border-top:1px solid #bbb;padding:2rem 0}'
            '.comparison{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.5fr);gap:2rem}'
            'pre,code{white-space:pre-wrap;overflow-wrap:anywhere;font:1rem/1.7 ui-monospace,monospace}'
            'img{max-width:100%;height:auto}figure{margin:0 0 2rem}figcaption{color:#444;font-size:.9rem}'
            '.warning{color:#703d00}a{color:#234d7b}@media(max-width:800px){body{padding:1rem}.comparison{display:block}}'
            '@media print{article{break-before:page}details{display:none}}'
            '</style><h1>Formula review sheet</h1>'
            f'<p>{len(sheet["records"])} source records · private, offline review copy.</p>'
            '<p>Read the typed text beside every source crop; click an image to inspect it at full size. '
            'Record <strong>confirmed</strong> or <strong>needs correction</strong> with a note. '
            'No verdict has been inferred. A confirmed verdict does not change canonical transcription status.</p>'
            '<p>With this sheet open, run the following from the checkout to record verdicts in the private '
            '<code>verdicts.jsonl</code> beside it. Skip or quit to resume later; earlier verdicts are retained.</p>'
            f'<pre>{escape(command)}</pre><p>The HTML remains a fixed source copy; the command reports saved progress.</p>'
            + "".join(items) + '</html>')


def create_sheet(corpus, destination, *, pdf=None, identifiers=None):
    destination = _outside_git(destination)
    if destination.exists():
        raise FileExistsError("review sheet already exists; choose a new output directory")
    if not destination.parent.is_dir():
        raise ValueError("the output directory's parent must already exist")
    book = core.load_corpus_book(Path(corpus).expanduser().resolve())
    corpus_path = Path(book.corpus_directory).resolve()
    if destination == corpus_path or corpus_path in destination.parents:
        raise ValueError("review output must be outside the canonical corpus")
    selected = [row for row in book.canonical_records.values()
                if row.get("contains_math") is True and row.get("transcription_status") == "needs_visual_review"]
    if identifiers is not None:
        wanted = set(identifiers)
        eligible = {row["id"] for row in selected}
        if not wanted or len(wanted) != len(identifiers) or wanted - eligible:
            raise ValueError("--record IDs must be distinct full IDs of math records needing visual review")
        selected = [row for row in selected if row["id"] in wanted]
    selected.sort(key=lambda row: row["order"])
    if not selected:
        raise ValueError("no math records need visual review in this corpus")
    # A failed render leaves neither a completed sheet nor a copied private PDF.
    with tempfile.TemporaryDirectory(prefix=".sol-formula-sheet-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        (stage / "assets").mkdir(mode=0o700)
        rows = []
        with tempfile.TemporaryDirectory(prefix="source-", dir=stage) as cache:
            service = source.SourceService(book, source_pdf=pdf, cache_dir=cache)
            for row in selected:
                request = service.capture(row["id"])
                if request["target_id"] != row["id"] or request["content_sha256"] != row["content_sha256"]:
                    raise ValueError("formula review requires a current record's own text, not a retired identity")
                pages = []
                for index, page in enumerate(request["sources"]):
                    image, cropped = source.render_region(request, index, cache_dir=cache)
                    name = f'assets/{row["id"]}-{index + 1}.png'
                    data = image.read_bytes()
                    _write(stage / name, data)
                    pages.append({**page, "image": name, "image_sha256": _sha(data), "cropped": cropped})
                rows.append({"id": row["id"], "type": row["type"], "order": row["order"],
                             "contains_math": True, "transcription_status": "needs_visual_review",
                             "content_sha256": request["content_sha256"], "metadata_sha256": request["metadata_sha256"],
                             "plain_text": row["plain_text"], "markdown": row["markdown"],
                             "attribution": row["attribution"], "pages": pages})
        verify_snapshot_current(book.corpus_snapshot)
        sheet = {"format": FORMAT, "version": 1, "corpus": _binding(book.corpus_snapshot),
                 "source": {key: book.corpus_manifest["source"][key] for key in ("sha256", "pdf_pages")}, "records": rows}
        html = _html(sheet, destination).encode("utf-8")
        sheet["html_sha256"] = _sha(html)
        metadata = _json(sheet) + b"\n"
        if len(metadata) > MAX_BYTES:
            raise ValueError("review sheet metadata exceeds 16 MiB; select fewer records")
        _write(stage / "sheet.json", metadata)
        _write(stage / "verdicts.jsonl", b"")
        _write(stage / "review.html", html)
        # Exclusive mkdir prevents replacement of any existing output, even if
        # another process created it during rendering. Only our files are moved.
        destination.mkdir(mode=0o700)
        for name in ("assets", "sheet.json", "verdicts.jsonl", "review.html"):
            path = stage / name
            path.rename(destination / path.name)
    return destination


def load_sheet(directory):
    directory = _outside_git(directory)
    if not directory.is_dir() or stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise ValueError("review directory must be private (mode 700)")
    raw = _read(directory / "sheet.json")
    sheet = _decode(raw)
    if (not isinstance(sheet, dict) or sheet.get("format") != FORMAT or type(sheet.get("version")) is not int
            or sheet["version"] != 1 or not isinstance(sheet.get("records"), list) or not sheet["records"]
            or not isinstance(sheet.get("corpus"), dict) or not isinstance(sheet.get("source"), dict)
            or sheet.get("html_sha256") != _sha(_read(directory / "review.html"))):
        raise ValueError("unrecognized formula review sheet")
    seen = set()
    for row in sheet["records"]:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str) or row.get("id") in seen
                or row.get("contains_math") is not True or row.get("transcription_status") != "needs_visual_review"
                or not isinstance(row.get("markdown"), str) or not isinstance(row.get("plain_text"), str)
                or row.get("content_sha256") != _sha(row["markdown"].encode("utf-8"))
                or not isinstance(row.get("pages"), list) or not row["pages"]):
            raise ValueError("formula sheet has invalid or duplicated record bindings")
        if str(UUID(row["id"])) != row["id"]:
            raise ValueError("formula sheet IDs must be canonical full UUIDs")
        seen.add(row["id"])
        for index, page in enumerate(row["pages"], 1):
            expected = f'assets/{row["id"]}-{index}.png'
            if (not isinstance(page, dict) or page.get("image") != expected
                    or Path(expected).parts != ("assets", f'{row["id"]}-{index}.png')
                    or (directory / "assets").is_symlink()
                    or _sha(_read(directory / expected)) != page.get("image_sha256")):
                raise ValueError("a formula sheet crop changed or is unavailable")
    return directory, sheet, _sha(raw)


def _events(directory, sheet, fingerprint):
    by_id = {row["id"]: row for row in sheet["records"]}
    events = []
    data = _read(directory / "verdicts.jsonl")
    if data and not data.endswith(b"\n"):
        raise ValueError("verdict history has an incomplete final line; no verdict was appended")
    for line in data.splitlines():
        event = _decode(line)
        row = by_id.get(event["id"]) if isinstance(event, dict) and isinstance(event.get("id"), str) else None
        if (row is None or set(event) != {"format", "version", "sheet_sha256", "id", "content_sha256", "metadata_sha256",
                                         "verdict", "note", "reviewer", "recorded_at"}
                or event["format"] != FORMAT + ".verdict" or type(event["version"]) is not int or event["version"] != 1
                or event["sheet_sha256"] != fingerprint or event["content_sha256"] != row["content_sha256"]
                or event["metadata_sha256"] != row["metadata_sha256"] or event["verdict"] not in VERDICTS
                or not isinstance(event["note"], str) or len(event["note"]) > 20000
                or not isinstance(event["reviewer"], str) or not event["reviewer"].strip()
                or not isinstance(event["recorded_at"], str)
                or (event["verdict"] == "needs_correction" and not event["note"].strip())):
            raise ValueError("invalid verdict or source binding in private history")
        events.append(event)
    return events


@contextmanager
def _verdict_lock(directory):
    path = directory / ".verdicts.lock"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValueError("another verdict writer holds the lock; retry after it finishes") from error
    os.close(fd)
    try:
        yield
    finally:
        path.unlink()


def record_verdict(directory, identifier, verdict, note, reviewer):
    directory, sheet, fingerprint = load_sheet(directory)
    if (verdict not in VERDICTS or not isinstance(note, str) or len(note) > 20000
            or (verdict == "needs_correction" and not note.strip()) or not isinstance(reviewer, str)
            or not 1 <= len(reviewer.strip()) <= 200):
        raise ValueError("choose a verdict, name the reviewer, and add a note for needs correction (at most 20,000 characters)")
    rows = sheet["records"]
    if identifier.isdigit() and 1 <= int(identifier) <= len(rows):
        row = rows[int(identifier) - 1]
    else:
        row = next((row for row in rows if row["id"] == identifier), None)
    if row is None:
        raise ValueError("choose a sheet item number or its full canonical record ID")
    event = {"format": FORMAT + ".verdict", "version": 1, "sheet_sha256": fingerprint, "id": row["id"],
             "content_sha256": row["content_sha256"], "metadata_sha256": row["metadata_sha256"],
             "verdict": verdict, "note": note, "reviewer": reviewer.strip(),
             "recorded_at": datetime.now(timezone.utc).isoformat()}
    with _verdict_lock(directory):
        _events(directory, sheet, fingerprint)
        path = directory / "verdicts.jsonl"
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)), "ab") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("verdict history must be a regular file")
            stream.write(_json(event) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    return event


def check_sheet(directory, corpus=None):
    directory, sheet, fingerprint = load_sheet(directory)
    events = _events(directory, sheet, fingerprint)
    if corpus is not None:
        snapshot = core.load_snapshot(Path(corpus).expanduser().resolve())
        if _binding(snapshot) != sheet["corpus"]:
            raise ValueError("the corpus generation differs from the sheet; keep these verdicts as historical testimony")
    latest = {event["id"]: event for event in events}
    counts = Counter(event["verdict"] for event in latest.values())
    return {"items": len(sheet["records"]), "events": len(events), "confirmed": counts["confirmed"],
            "needs_correction": counts["needs_correction"], "pending": len(sheet["records"]) - len(latest)}


def review_sheet(directory, reviewer):
    if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 200:
        raise ValueError("name the reviewer (1–200 characters)")
    directory, sheet, fingerprint = load_sheet(directory)
    latest = {event["id"]: event for event in _events(directory, sheet, fingerprint)}
    for number, row in enumerate(sheet["records"], 1):
        if row["id"] in latest:
            continue
        print(f'Item {number}/{len(sheet["records"])}: {row["id"]} (see review.html#item-{number})')
        while True:
            choice = input("[c] confirmed, [n] needs correction, [s] skip, [q] quit: ").strip().lower()
            if choice in ("s", "q"):
                break
            if choice in ("c", "n"):
                note = input("Correction note: " if choice == "n" else "Note (optional): ")
                try:
                    record_verdict(directory, str(number), "confirmed" if choice == "c" else "needs_correction", note, reviewer)
                    break
                except ValueError as error:
                    print(str(error), file=sys.stderr)
        if choice == "q":
            break
    return check_sheet(directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="write a new private offline sheet; never overwrite")
    create.add_argument("--corpus", type=Path, required=True)
    create.add_argument("--pdf", type=Path, help="original PDF; otherwise use existing source discovery")
    create.add_argument("--output", type=Path, required=True, help="new directory outside Git and the corpus")
    create.add_argument("--record", action="append", help="optional exact eligible ID, repeat to select a subset")
    for name in ("record", "review", "check"):
        command = commands.add_parser(name)
        command.add_argument("--sheet", type=Path, required=True)
        if name in ("record", "review"):
            command.add_argument("--reviewer", required=True)
        if name == "record":
            command.add_argument("--record", required=True, help="sheet item number or full record ID")
            command.add_argument("--verdict", choices=("confirmed", "needs-correction"), required=True)
            command.add_argument("--note", default="")
        if name == "check":
            command.add_argument("--corpus", type=Path, help="also check the exact current corpus generation")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            directory = create_sheet(args.corpus, args.output, pdf=args.pdf, identifiers=args.record)
            print(f"Private formula sheet: {directory / 'review.html'}")
            print(json.dumps(check_sheet(directory), sort_keys=True))
        elif args.command == "record":
            event = record_verdict(args.sheet, args.record, args.verdict.replace("-", "_"), args.note, args.reviewer)
            print(f'Saved human verdict: {event["id"]} · {event["verdict"]}; canonical text unchanged.')
        else:
            counts = review_sheet(args.sheet, args.reviewer) if args.command == "review" else check_sheet(args.sheet, args.corpus)
            print(json.dumps(counts, sort_keys=True))
        return 0
    except (OSError, ValueError, EOFError, KeyboardInterrupt) as error:
        print(f"formula review: {error or 'stopped; previously recorded verdicts are retained'}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
