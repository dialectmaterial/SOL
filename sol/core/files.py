"""Resolve canonical Markdown and virtual text selections without a CLI."""
from __future__ import annotations

from pathlib import Path
import posixpath

from sol.core.paths import resolve_path


def _path_argument(book, value):
    """Honor real shell cwd before corpus-relative and virtual compatibility."""
    candidate = Path(value).expanduser()
    if value.lower().endswith(".md") and not candidate.is_absolute():
        if candidate.exists() or candidate.is_symlink():
            return str(candidate.resolve())
    return str(candidate) if candidate.is_absolute() else value


def resolve_file_path(book, value, cwd=()):
    """Select complete ordered canonical text, without reading arbitrary files.

    .txt paths belong to SOL's virtual tree; .md paths are relative to the
    configured corpus or absolute filenames within it. Both resolve to IDs from
    the loaded index. Physical Markdown is never parsed a second time here.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Choose a SOL text path or a canonical Markdown file")
    records = book.canonical_records
    if value.lower().endswith(".md"):
        documents = book.corpus_manifest.get("documents", [])
        candidate = Path(value).expanduser()
        directory = getattr(book, "corpus_directory", None)
        if candidate.is_absolute():
            if directory is None:
                raise ValueError("No canonical corpus directory is configured")
            try:
                document = candidate.resolve().relative_to(Path(directory).resolve()).as_posix()
            except ValueError as error:
                raise ValueError("Choose a Markdown file inside the configured SOL corpus") from error
        else:
            document = posixpath.normpath(value)
            if directory is not None and document.startswith(Path(directory).name + "/"):
                document = document[len(Path(directory).name) + 1:]
        if document not in documents:
            raise ValueError(f"Not a canonical Markdown file: {value}. Use a path from the SOL corpus.")
        selected = [r for r in records.values() if r.get("document") == document
                    and r.get("type") != "retired_record"]
        display = str(Path(directory) / document) if directory is not None else document
        title = next((r.get("title") for r in selected if r.get("type") == "section" and r.get("title")),
                     Path(document).stem.replace("-", " "))
        kind = "markdown_file"
    else:
        node, scope = resolve_path(value, cwd, book.root)
        passage_ids = {p.identifier for p in book.selection(scope)}
        prefix = "/" + "/".join(scope)
        selected = [r for r in records.values() if r["id"] in passage_ids
                    or (r.get("type") == "section" and isinstance(r.get("reader_path"), str)
                        and (r["reader_path"] == prefix or r["reader_path"].startswith(prefix.rstrip("/") + "/")))]
        display, title, kind = prefix, node.title, "reader_path"
    selected.sort(key=lambda r: r["order"])
    if not selected:
        raise ValueError(f"No canonical text in {value}")
    return {"path": display, "display_path": document if kind == "markdown_file" else display,
            "title": title, "kind": kind,
            "target_ids": [r["id"] for r in selected]}
