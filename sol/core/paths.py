"""Resolve SOL's virtual book paths against a caller-supplied tree.

These paths do not access the host filesystem. The shared resolver deliberately
has no edition-specific default root or reader-interface dependency.
"""

from __future__ import annotations

import re

from sol.core.models import Node, node_path


def display_path(path: tuple[str, ...]) -> str:
    return "/" + "/".join(path)


def alias(name: str) -> str:
    name = name.removesuffix(".txt").casefold()
    return re.sub(r"^(?:\d+|[a-d]|[ivxlcdm]+|[αβγ])-", "", name)


def child_by_name(node: Node, name: str) -> Node | None:
    exact = [child for child in node.children if child.name == name]
    if exact:
        return exact[0]
    matches = [child for child in node.children if
               child.name.casefold().removesuffix(".txt") == name.casefold().removesuffix(".txt")
               or alias(child.name) == alias(name)]
    if len(matches) > 1:
        raise ValueError(f"ambiguous name: {name}; use its full listed name")
    return matches[0] if matches else None


def resolve_path(value: str | None, cwd: tuple[str, ...], root: Node) -> tuple[Node, tuple[str, ...]]:
    node = root
    if not value or not value.startswith("/"):
        for piece in cwd:
            child = child_by_name(node, piece)
            if child is None:
                raise ValueError("the current path no longer exists")
            node = child
    for piece in (value or "").split("/"):
        if piece in ("", "."):
            continue
        if not node.is_directory:
            raise ValueError(f"not a directory: {node.name}")
        if piece == "..":
            node = node.parent or root
            continue
        child = child_by_name(node, piece)
        if child is None:
            raise ValueError(f"no such path: {value}")
        node = child
    return node, node_path(node)
