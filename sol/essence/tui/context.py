"""The private handoff from the BEING reader to the ESSENCE interface.

The reader writes one small JSON file per opening: where the reader is (a
checked CORE reference, codepoint cursor and optional selection), a label to
show, and where ESSENCE may keep its investigation state. It holds IDs,
offsets and a heading, never passage text. This module must not import
Textual: the reader uses it whether or not the essence extra is installed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

CONTEXT_VERSION = 1
MAX_CONTEXT_BYTES = 256 * 1024
_FIELDS = {"version", "reference", "cursor_offset", "selection", "label", "corpus", "state_file"}


def write_context(directory, *, reference, cursor_offset, selection, label, corpus, state_file):
    """Create a new owner-only context file in a private directory."""
    context = {"version": CONTEXT_VERSION, "reference": reference, "cursor_offset": cursor_offset,
               "selection": selection, "label": label, "corpus": corpus,
               "state_file": None if state_file is None else str(state_file)}
    check_context(context)
    data = json.dumps(context, ensure_ascii=False, allow_nan=False).encode("utf-8")
    directory = Path(directory)
    for number in range(1000):
        path = directory / f"context-{os.getpid()}-{number}.json"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            continue
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        return path
    raise ValueError("could not create a private ESSENCE context file")


def check_context(context):
    if not isinstance(context, dict) or set(context) != _FIELDS or context["version"] != CONTEXT_VERSION:
        raise ValueError("unsupported ESSENCE context")
    reference = context["reference"]
    if (not isinstance(reference, dict) or not isinstance(reference.get("reference"), dict)
            or not isinstance(reference["reference"].get("target_id"), str)):
        raise ValueError("ESSENCE context needs a CORE reference")
    if type(context["cursor_offset"]) is not int or context["cursor_offset"] < 0:
        raise ValueError("ESSENCE context needs a codepoint cursor")
    if context["selection"] is not None and not isinstance(context["selection"], dict):
        raise ValueError("ESSENCE context selection must be an object or null")
    for key in ("label", "corpus"):
        if not isinstance(context[key], str):
            raise ValueError(f"ESSENCE context {key} must be text")
    if context["state_file"] is not None and not isinstance(context["state_file"], str):
        raise ValueError("ESSENCE state file must be a path or null")
    return context


def read_context(path):
    path = Path(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CONTEXT_BYTES:
            raise ValueError("ESSENCE context must be a small regular file")
        data = stream.read(MAX_CONTEXT_BYTES + 1)
    return check_context(json.loads(data.decode("utf-8")))


def save_state(path, state):
    """Replace the investigation state atomically, owner-only."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(state, stream, ensure_ascii=False, allow_nan=False)
    os.replace(temporary, path)


def load_state(path):
    """The saved investigation state, or an empty one if absent or unreadable."""
    try:
        with open(path, encoding="utf-8") as stream:
            state = json.load(stream)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}
