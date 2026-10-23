"""Open and follow verified source captures in detached image/PDF viewers."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import threading
import time

from sol.core.source import SourceError, _request_current, _verify_file, _verify_snapshot_current


def open_viewer(path):
    """Hand one rendered PNG to a separate image viewer and return its name.

    The reader keeps the terminal: the viewer inherits no standard streams and
    runs in its own session. SOL_IMAGE_VIEWER names another command, to which
    the image path is appended. Without a graphical display, xdg-open may pick
    a text-mode browser that would draw over Neovim, so None is returned and
    the caller shows the file path instead.
    """
    configured = os.environ.get("SOL_IMAGE_VIEWER", "").strip()
    if configured:
        command = shlex.split(configured)
    elif sys.platform == "darwin":
        command = ["open"]
    elif os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        command = ["xdg-open"]
    else:
        return None
    program = shutil.which(command[0])
    if not program:
        return None
    try:
        subprocess.Popen([program, *command[1:], str(path)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        raise SourceError(f"Cannot start image viewer {command[0]}: {error}") from error
    return Path(command[0]).name


# PDF viewers that open a file at a physical page (1-based), in order of preference.
_PDF_VIEWERS = (
    ("zathura", lambda page, path: [f"--page={page}", path]),
    ("sioyek", lambda page, path: ["--page", str(page), path]),
    ("okular", lambda page, path: ["--page", str(page), path]),
    ("evince", lambda page, path: [f"--page-index={page}", path]),
    ("mupdf", lambda page, path: [path, str(page)]),
)
# The Zathura window SOL opened: later pages are sent to it instead of opening another.
_companion = None


def open_pdf(request, page_index):
    """Show one source page in a PDF viewer, where it can be zoomed in context.

    The viewer reads the private, fingerprint-checked snapshot, never the
    user's file. SOL_PDF_VIEWER names another command; `{page}` and `{file}`
    in it are replaced, and without `{file}` the path is appended. Zathura is
    preferred, and a Zathura window SOL opened is turned to the new page over
    D-Bus rather than duplicated. Returns the viewer's name, or None when no
    graphical viewer is available.
    """
    global _companion
    snapshot = _request_current(request)
    if type(page_index) is not int or not 0 <= page_index < len(request["sources"]):
        raise SourceError("Choose a source page index within this record's captured page list")
    page = request["sources"][page_index]["pdf_page"]
    pdf = Path(request["source"]["verified_pdf"])
    _verify_file(pdf, request["source"]["sha256"])
    _verify_snapshot_current(snapshot)
    configured = os.environ.get("SOL_PDF_VIEWER", "").strip()
    if configured:
        command = [part.replace("{page}", str(page)).replace("{file}", str(pdf)) for part in shlex.split(configured)]
        if "{file}" not in configured:
            command.append(str(pdf))
    elif sys.platform == "darwin":
        command = ["open", str(pdf)]  # Preview cannot be told the page from the command line
    elif os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        found = next(((name, arguments) for name, arguments in _PDF_VIEWERS if shutil.which(name)), None)
        if found is None:
            return None
        name, arguments = found
        if name == "zathura" and _show_on_companion(request, page_index):
            return name
        command = [name, *arguments(page, str(pdf))]
    else:
        return None
    program = shutil.which(command[0])
    if not program:
        return None
    try:
        process = subprocess.Popen([program, *command[1:]], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        raise SourceError(f"Cannot start PDF viewer {command[0]}: {error}") from error
    name = Path(command[0]).name
    _companion = (process, pdf) if name == "zathura" else None
    if _companion is not None:
        # A new window registers on D-Bus only once the PDF is loaded.
        threading.Thread(target=_highlight_when_ready, args=(process, request, page_index),
                         name="sol-pdf-highlight", daemon=True).start()
    return name


def follow_pdf(request, page_index=0):
    """Turn SOL's open Zathura window to this passage; False when there is none.

    Following never opens a window: it only moves one the reader opened with S.
    """
    snapshot = _request_current(request)
    if type(page_index) is not int or not 0 <= page_index < len(request["sources"]):
        raise SourceError("Choose a source page index within this record's captured page list")
    _verify_file(Path(request["source"]["verified_pdf"]), request["source"]["sha256"])
    _verify_snapshot_current(snapshot)
    return _show_on_companion(request, page_index)


def _show_on_companion(request, page_index):
    """Turn the Zathura window SOL opened on this PDF to the passage; False if there is none."""
    global _companion
    if _companion is None:
        return False
    process, shown = _companion
    if shown != Path(request["source"]["verified_pdf"]) or process.poll() is not None or not shutil.which("gdbus"):
        _companion = None
        return False
    return _show(process, request, page_index)


def _show(process, request, page_index):
    page = request["sources"][page_index]["pdf_page"]
    if not _zathura_call(process, "GotoPage", str(page - 1)):
        return False
    highlight = _highlight_arguments(request, page_index)
    if highlight is not None:
        _zathura_call(process, "HighlightRects", *highlight)
    return True


def _highlight_when_ready(process, request, page_index, attempts=40, pause=0.25):
    for _ in range(attempts):
        if process.poll() is not None:
            return
        if _show(process, request, page_index):
            return
        time.sleep(pause)


def _highlight_arguments(request, page_index):
    """HighlightRects arguments: the recorded box on the shown page, and on the passage's other pages.

    Boxes are PDF points from the page's top-left corner, which is what Zathura
    expects; pages are zero-based. None when the passage has no recorded box.
    """
    rows = request["sources"]
    def numbers(box):
        return ", ".join(repr(float(value)) for value in box)
    primary = [f"({numbers(rows[page_index]['bbox'])})"] if "bbox" in rows[page_index] else []
    secondary = [f"(uint32 {row['pdf_page'] - 1}, {numbers(row['bbox'])})"
                 for index, row in enumerate(rows) if index != page_index and "bbox" in row]
    if not primary and not secondary:
        return None
    return [str(rows[page_index]["pdf_page"] - 1), "@a(dddd) [" + ", ".join(primary) + "]",
            "@a(udddd) [" + ", ".join(secondary) + "]"]


def _zathura_call(process, method, *arguments):
    gdbus = shutil.which("gdbus")
    if not gdbus:
        return False
    try:
        result = subprocess.run([gdbus, "call", "--session", "--dest", f"org.pwmt.zathura.PID-{process.pid}",
                                 "--object-path", "/org/pwmt/zathura", "--method", f"org.pwmt.zathura.{method}",
                                 *arguments], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and b"true" in result.stdout
