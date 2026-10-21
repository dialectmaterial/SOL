#!/usr/bin/env python3
"""Check local Markdown links/anchors and the four-document layout.

No network, Git history, private corpus or terminal is required. External URLs
are not probed; GitHub main/HEAD links to this repository are resolved locally.
Fenced examples are parsed as code, never rewritten or checked as links.
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

AUTHORITIES = {"ARCHITECTURE.md", "BEING.md", "CORE.md", "ESSENCE.md"}
ROOT_DOCUMENTS = ("README.md", "CONTRIBUTING.md", "CHANGELOG.md")
_ANCHOR = re.compile(r'\bid\s*=\s*[\'"]([^\'"]+)[\'"]', re.I)


def markdown_details(text):
    """CommonMark tokens distinguish real links/headings from literal examples."""
    tokens = MarkdownIt("commonmark").parse(text)
    anchors, destinations = set(), []
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            inline = tokens[index + 1]
            title = "".join(child.content for child in inline.children or []
                            if child.type in {"text", "code_inline"})
            slug = re.sub(r"[^\w\s-]", "", html.unescape(title).lower())
            slug = re.sub(r"\s", "-", slug)
            candidate, number = slug, 0
            while candidate in anchors:
                number += 1
                candidate = f"{slug}-{number}"
            anchors.add(candidate)
        if token.type == "html_block":
            anchors.update(_ANCHOR.findall(token.content))
        for child in token.children or []:
            if child.type == "html_inline":
                anchors.update(_ANCHOR.findall(child.content))
            if child.type == "link_open":
                destinations.append(child.attrGet("href"))
            elif child.type == "image":
                destinations.append(child.attrGet("src"))
    return anchors, destinations


def check(root):
    root = Path(root).resolve()
    errors = []
    leading = {path.name for path in (root / "docs").glob("*.md")}
    if leading != AUTHORITIES:
        errors.append(f"Expected only four leading design documents, got {sorted(leading)}")
    documents = [root / name for name in ROOT_DOCUMENTS] + sorted((root / "docs").rglob("*.md"))
    details = {}
    for path in documents:
        try:
            if path.is_symlink():
                errors.append(f"Documentation must not use symlink redirects: {path.relative_to(root)}")
            details[path] = markdown_details(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            errors.append(f"Cannot parse {path.relative_to(root)}: {error}")
    for path, (_, destinations) in list(details.items()):
        for destination in destinations:
            url = urlsplit(destination)
            if url.scheme or url.netloc:
                match = re.fullmatch(r"/dialectmaterial/SOL/(?:blob|tree)/(?:main|HEAD)/(.+)", url.path)
                if url.netloc != "github.com" or match is None:
                    continue
                target = root / unquote(match[1])
            else:
                value = unquote(url.path)
                target = (root / value.lstrip("/") if value.startswith("/")
                          else path.parent / value) if value else path
            target = target.resolve()
            label = f"{path.relative_to(root)}: {destination}"
            if not target.is_relative_to(root) or not target.exists():
                errors.append("Missing/out-of-repository link: " + label)
                continue
            if url.fragment and target.suffix == ".md":
                if target not in details:
                    details[target] = markdown_details(target.read_text(encoding="utf-8"))
                if unquote(url.fragment) not in details[target][0]:
                    errors.append("Missing Markdown anchor: " + label)
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    errors = check(args.root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Documentation OK: four authorities and local links/anchors.")
    print("External URLs were not network-checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
