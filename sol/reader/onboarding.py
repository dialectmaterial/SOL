"""One-time interactive import. Ordinary reading never opens the source PDF."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile

from sol.core.config import save_corpus
from sol.core.corpus import load_corpus_book


def data_directory() -> Path:
    value = os.environ.get("XDG_DATA_HOME")
    root = Path(value).expanduser() if value else Path.home() / ".local" / "share"
    if not root.is_absolute():
        raise ValueError("XDG_DATA_HOME must be an absolute directory")
    return root / "sol"


def prepare_first_corpus():
    """Ask only on a TTY; publish a validated new corpus, never overwrite one."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("No corpus configured. Run sol interactively to import your PDF, "
                         "or use sol --set-corpus DIRECTORY for an existing corpus.")
    from sol.corpus.convert import AUDITED_SOURCE_SHA256, convert

    missing = [name for name in ("pdftotext", "pdftohtml", "pdftoppm", "git") if not shutil.which(name)]
    if missing:
        raise ValueError("PDF import needs " + ", ".join(missing) +
                         ". Run python3 scripts/install.py from the SOL checkout to complete installation.")
    print("Welcome to SOL — SOL Organizes Logic.\n"
          "Choose your local Science of Logic PDF (Cambridge, George di Giovanni, 2010).\n"
          "SOL converts the supported source once and keeps the corpus on this computer.\n"
          "An existing corpus can instead be selected with sol --set-corpus DIRECTORY.\n"
          "Press Ctrl-C to leave without importing.")
    while True:
        raw = input("PDF location: ").strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            raw = raw[1:-1]
        source = Path(raw).expanduser()
        if not raw or not source.is_file():
            print("That is not a readable PDF file. Enter its full path.")
            continue
        try:
            digest = hashlib.sha256()
            with source.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        except OSError as error:
            print(f"Cannot read that file: {error}")
            continue
        if digest.hexdigest() != AUDITED_SOURCE_SHA256:
            print("This file does not match the source audited by SOL's importer.\n"
                  "Other editions, scans and differently encoded copies are not yet supported.\n"
                  "No corpus was created; choose the supported PDF or press Ctrl-C to leave.")
            continue
        break

    home = data_directory()
    destination = home / "corpora" / AUDITED_SOURCE_SHA256
    if not destination.exists():
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        print("Importing PDF into local Markdown and building the index. This can take a few minutes…",
              flush=True)
        # Extraction evidence is scratch data, not another canonical corpus.
        with tempfile.TemporaryDirectory(prefix="sol-import-") as temporary:
            convert(source, destination, Path(temporary))
    # A completed earlier import can be reused after interruption before setup.
    # An invalid destination is reported, never replaced or silently reconverted.
    book = load_corpus_book(destination)
    if book.corpus_manifest["source"]["sha256"] != AUDITED_SOURCE_SHA256:
        raise ValueError("The existing import destination belongs to another source; it was not replaced.")
    save_corpus(destination)
    print(f"Corpus ready: {destination}")
    # Source previews render from this same verified PDF; remembering it is a
    # convenience, so a failure here never undoes the finished import.
    from sol.terminal.source import SourceError, SourceService
    try:
        SourceService(book).set_pdf(source)
        print("Source PDF remembered for printed-source previews (s in the reader).\n")
    except SourceError as error:
        print(f"Source previews need the PDF later: {error}\n"
              "Use sol --set-source-pdf PATH when it is available.\n")
    return book
