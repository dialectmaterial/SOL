"""Offline typeset proof: exact escaped source text plus semantic style ranges."""
from __future__ import annotations

import base64
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import unicodedata

from sol.reader.typography import map_typography
from .common import CaptureExport, Sample, record_payload


CSS = """html{color-scheme:light dark}body{margin:0;background:#f8f5ee;color:#292721;
font-family:Georgia,'Liberation Serif',serif;font-size:20px;line-height:1.62}
main{max-width:66ch;margin:4rem auto;padding:0 1.4rem 5rem}header{margin-bottom:2.5rem}
h1{font-size:1.5em;line-height:1.25}h2{font-size:1.1em}p{margin:0 0 1.1em}
.source{white-space:pre-wrap;overflow-wrap:anywhere;tab-size:4;margin:0 0 1.1em}
.source:focus{outline:1px dotted #888;outline-offset:.3rem}article{margin:1.2em 0}
.quotation{border-left:2px solid #aaa;padding-left:1em}.code{font-family:monospace;font-size:.9em}
.heading{font-weight:bold}.warning{border-left:3px solid #a65e20;padding:.5em .8em}
.meta,summary,button,label{font:14px/1.5 system-ui,sans-serif;color:#686359}
details{margin:.6em 0}summary,button{cursor:pointer}button,input{font:inherit}
.provenance{display:none}.show-context .provenance{display:block}
nav{display:flex;gap:.5em;flex-wrap:wrap}#notice{font:14px/1.5 system-ui,sans-serif;min-height:1.5em}
aside{font-size:.85em;border-left:1px solid #bbb;padding-left:1em;margin-bottom:1.5em}
aside .note-text{white-space:pre-wrap}pre{white-space:pre-wrap;overflow-wrap:anywhere}
@media(max-width:600px){main{margin-top:2rem}body{font-size:18px}}
@media(prefers-color-scheme:dark){body{background:#1d201f;color:#e6e2d7}.meta,summary,button,label{color:#bfbbae}}
"""


def _safe_source(text: str) -> None:
    # HTML parsers normalize CR and drop NUL; invisible bidi/control content is
    # not suitable for this first proof. Refuse it rather than repair the source.
    if any((unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"}
            and char not in {"\n", "\t"}) for char in text):
        raise ValueError("typeset proof refuses control/bidi source characters; canonical text was not altered")


def _styled(text: str, typography) -> str:
    boundaries = sorted({0, len(text), *(span.start for span in typography.spans),
                         *(span.end for span in typography.spans)})
    parts = []
    for start, end in zip(boundaries, boundaries[1:]):
        styles = {style for span in typography.spans if span.start <= start < span.end for style in span.styles}
        value = escape(text[start:end])
        for style in ("code", "strong", "emphasis"):
            if style in styles:
                tag = {"code": "code", "strong": "strong", "emphasis": "em"}[style]
                value = f"<{tag}>{value}</{tag}>"
        classes = " ".join(style for style in ("quotation", "heading", "code") if style in styles)
        if classes:
            value = f'<span class="{classes}">{value}</span>'
        parts.append(value)
    return "".join(parts)


def _hash(value: str) -> str:
    return base64.b64encode(sha256(value.encode("utf-8")).digest()).decode("ascii")


def render_html(sample: Sample, *, trial=None) -> str:
    if sample.actions.workspace_reader is not None:
        raise ValueError("reader experiments do not accept a personal workspace")
    trial_info = None
    if trial is not None:
        from .trials import ReadingTrial
        if not isinstance(trial, ReadingTrial) or trial.sample is not sample:
            raise ValueError("reading trial must describe this same sample")
        trial_info = trial.metadata
        if (trial_info["start"] != sample.passages[0].identifier
                or trial_info["end"] != sample.passages[-1].identifier
                or trial_info["sample_passages"] != len(sample.passages)):
            raise ValueError("reading trial extent no longer matches its sample")
    script = Path(__file__).with_name("browser.js").read_text(encoding="utf-8")
    capture = CaptureExport(sample.book)
    records, articles = [], []
    previous_heading = None
    for passage in sample.passages:
        payload = record_payload(sample, passage, capture=capture)
        records.append(payload)
        _, checked = capture.capture(passage.identifier)
        record = checked.record
        _safe_source(passage.text)
        typography = map_typography(record["markdown"], passage.text)
        warning = ("Source transcription needs review. " if passage.needs_source_review else "")
        if typography.degraded:
            warning += typography.reason or "Semantic typography unavailable; plain text shown."
        heading = passage.heading or passage.node.title
        context = f"{heading} · printed {passage.printed_page}–{passage.end_printed_page} · PDF {passage.pdf_page}–{passage.end_pdf_page}"
        body = _styled(passage.text, typography)
        notes = []
        for identifier in record.get("note_ids", []):
            _, checked_note = capture.capture(identifier)
            note = checked_note.record
            if note.get("type") != "note":
                raise ValueError("a referenced canonical note is unavailable")
            text = note["plain_text"]
            _safe_source(text)
            attr = note.get("attribution", {})
            label = f"{attr.get('role', 'note')}: {attr.get('author') or 'unresolved attribution'}"
            note_typography = map_typography(note["markdown"], text)
            styled_note = _styled(text, note_typography)
            note_warning = (f'<p class="warning">{escape(note_typography.reason or "Note typography unavailable; plain text shown.")}</p>'
                            if note_typography.degraded else "")
            notes.append(f'<details><summary>{escape(label)}</summary>{note_warning}<div class="note-text">{styled_note}</div></details>')
        heading_html = f'<h2>{escape(heading)}</h2>' if heading != previous_heading else ""
        previous_heading = heading
        articles.append(
            '<article>' + heading_html + (f'<p class="warning" role="alert">{escape(warning)}</p>' if warning else "")
            + f'<details class="provenance"><summary>{escape(context)}</summary><pre>{escape("/" + "/".join(passage.path))}\n{escape(passage.identifier)}\n{escape(json.dumps(record.get("attribution", {}), ensure_ascii=False))}</pre></details>'
            + f'<div class="source" tabindex="0" data-record-id="{escape(passage.identifier, quote=True)}">{body}</div>'
            + ('<aside><span class="meta">Canonical notes (outside selectable passage text)</span>' + "".join(notes) + '</aside>' if notes else "")
            + '</article>')
    payload = {"records": records}
    trial_heading = ""
    if trial_info is not None:
        payload["trial"] = trial_info
        summary = (f"{trial_info['name']} · {trial_info['sample_passages']} passages · "
                   f"printed {trial_info['printed_pages'][0]}–{trial_info['printed_pages'][1]} · "
                   f"PDF {trial_info['pdf_pages'][0]}–{trial_info['pdf_pages'][1]} · "
                   f"{trial_info['linked_notes']} linked notes")
        trial_heading = (f'<p class="meta" id="trial-extent">{escape(summary)}<br>'
                         f'{escape(trial_info["description"])}</p>')
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    policy = f"default-src 'none'; script-src 'sha256-{_hash(script)}'; style-src 'sha256-{_hash(CSS)}'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
    evidence = json.dumps({"corpus_id": capture.manifest.get("corpus_id"),
                           "edition": capture.manifest.get("edition", {}),
                           "source": capture.manifest.get("source", {})}, ensure_ascii=False, indent=2)
    rendered = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            + f'<meta http-equiv="Content-Security-Policy" content="{escape(policy, quote=True)}">'
            + '<meta name="viewport" content="width=device-width,initial-scale=1"><title>SOL · typeset reading experiment</title>'
            + f'<style>{CSS}</style></head><body><main><header><h1>SOL · typeset reading experiment</h1>'
            + trial_heading
            + '<p class="meta">Offline, bounded, read-only projection. No workspace is opened or saved. Source controls are on demand; notes remain separately attributed.</p>'
            + '<nav><button id="export-selection">Export selected span</button><button id="export-position">Export clicked position</button>'
            + '<button id="context" aria-pressed="false">Source context</button>'
            + '<label>Restore exported packet <input id="restore" type="file" accept="application/json,.json"></label></nav>'
            + '<p id="notice" role="status">Select within one passage, or click text before exporting a position. Validate exported packets with the Python experiment command.</p></header>'
            + '<details class="provenance"><summary>Edition and source evidence</summary><pre>' + escape(evidence) + '</pre></details>'
            + "".join(articles) + f'</main><script id="sol-data" type="application/json">{data}</script><script>{script}</script></body></html>')
    capture.finish()
    return rendered


def write_html(sample: Sample, output: Path, *, trial=None) -> None:
    """Create one owner-only artifact; never overwrite or follow an existing link."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite an existing artifact: {output}")
    corpus = sample.book.corpus_directory
    if corpus is not None and corpus.resolve() in output.resolve().parents:
        raise ValueError("choose an output outside the read-only canonical corpus directory")
    rendered = render_html(sample, trial=trial)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
        stream.write(rendered)
