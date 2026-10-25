"""The private launch exchange from BEING to ESSENCE, without either interface.

The reader writes one small JSON file per opening: a checked CORE reference,
codepoint cursor and optional selection, a label, and an optional path for
ESSENCE's own investigation state. It holds IDs, offsets and a heading, never
passage text. The reader owns the private directory and removes it at exit;
reading the file does not consume it. Investigation-state persistence stays
with ESSENCE, beyond this transient exchange.

Only the standard library is needed, including the optional-runtime probe.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

CONTEXT_VERSION = 1
MAX_CONTEXT_BYTES = 256 * 1024
_FIELDS = {"version", "reference", "cursor_offset", "selection", "label", "corpus", "state_file"}


def _encode_context(context):
    try:
        return json.dumps(context, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as error:
        raise ValueError("ESSENCE context must be finite UTF-8 JSON") from error


def write_context(directory, *, reference, cursor_offset, selection, label, corpus, state_file):
    """Create a new owner-only context file in a private directory."""
    context = {"version": CONTEXT_VERSION, "reference": reference, "cursor_offset": cursor_offset,
               "selection": selection, "label": label, "corpus": corpus,
               "state_file": None if state_file is None else str(state_file)}
    check_context(context)
    data = _encode_context(context)
    if len(data) > MAX_CONTEXT_BYTES:
        raise ValueError("ESSENCE context must be a small regular file")
    directory = Path(directory)
    for number in range(1000):
        path = directory / f"context-{os.getpid()}-{number}.json"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            continue
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path
    raise ValueError("could not create a private ESSENCE context file")


def check_context(context):
    if (not isinstance(context, dict) or set(context) != _FIELDS
            or type(context["version"]) is not int or context["version"] != CONTEXT_VERSION):
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
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CONTEXT_BYTES:
            raise ValueError("ESSENCE context must be a small regular file")
        data = stream.read(MAX_CONTEXT_BYTES + 1)
    if len(data) > MAX_CONTEXT_BYTES:
        raise ValueError("ESSENCE context must be a small regular file")
    try:
        context = json.loads(data.decode("utf-8"))
    except RecursionError as error:
        raise ValueError("ESSENCE context JSON is too deeply nested") from error
    context = check_context(context)
    # A read must not admit NaN, overflowed floats or escaped surrogates that
    # the writer cannot represent as finite UTF-8 JSON.
    _encode_context(context)
    return context


TEXTUAL_HINT = ("ESSENCE needs Textual, from the essence extra: "
                "pip install 'sol-organizes-logic[essence]' (or: pipx inject sol-organizes-logic textual).")


def textual_available():
    from importlib.util import find_spec
    return find_spec("textual") is not None
