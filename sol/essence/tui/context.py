"""ESSENCE-owned investigation state; launch context is in sol.interchange.essence."""
from __future__ import annotations

import json
import os
from pathlib import Path


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
