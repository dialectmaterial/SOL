"""Bounded, stable JSON transport input without interpreting application data."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import sys


def read_json_input(filename: str, maximum: int) -> bytes | str:
    """Read a regular file or noninteractive stdin; the caller owns decoding.

    No payload-selected paths, special-file opens, or implicit corpus discovery.
    The bound applies to UTF-8 bytes even for injected text streams in clients.
    """
    if type(maximum) is not int or maximum < 1:
        raise ValueError("JSON input needs a positive byte limit")

    def state(value):
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns

    if filename == "-":
        if sys.stdin.isatty():
            raise ValueError("JSON FILE or piped input is required; interactive stdin is not supported")
        content = getattr(sys.stdin, "buffer", sys.stdin).read(maximum + 1)
    else:
        path = Path(filename).expanduser()
        initial = path.lstat()
        if not stat.S_ISREG(initial.st_mode):
            raise ValueError("JSON input must be a regular file, not a symlink or special file")
        if initial.st_size > maximum:
            raise ValueError(f"JSON input exceeds {maximum} bytes")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or state(initial) != state(opened):
                raise ValueError("JSON input changed while opening; retry with a stable regular file")
            if opened.st_size > maximum:
                raise ValueError(f"JSON input exceeds {maximum} bytes")
            content = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
            current = path.lstat()
            if not stat.S_ISREG(current.st_mode) or state(opened) != state(after) or state(opened) != state(current):
                raise ValueError("JSON input changed while reading; retry with a stable regular file")
    size = len(content.encode("utf-8")) if isinstance(content, str) else len(content)
    if size > maximum:
        raise ValueError(f"JSON input exceeds {maximum} bytes")
    return content
