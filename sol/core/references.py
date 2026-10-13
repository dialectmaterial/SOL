"""Canonical record resolution without reader, workspace, or interface imports.

Saved references keep their requested identifier while explicit retirement
redirects resolve to a current target. Missing references are never inferred
from textual similarity.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reference:
    requested_id: str
    target_id: str
    record: dict
    chain: tuple[str, ...]


def resolve_reference(book, identifier: str) -> Reference:
    key = identifier.strip().lower()
    records = book.canonical_records
    if not key:
        raise ValueError("a canonical record ID is required")
    if key in records:
        requested = key
    else:
        matches = [value for value in records if value.startswith(key)]
        if len(matches) == 1:
            requested = matches[0]
        elif len(matches) > 1:
            raise ValueError("ambiguous record ID; supply more of its UUID")
        else:
            raise ValueError(f"unresolved canonical record: {identifier}")
    chain = [requested]
    while records[chain[-1]]["type"] == "retired_record":
        target = records[chain[-1]]["redirect_id"]
        if target not in records or target in chain:
            raise ValueError("invalid canonical retirement redirect")
        chain.append(target)
    return Reference(requested, chain[-1], records[chain[-1]], tuple(chain))
