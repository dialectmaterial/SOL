"""Verified canonical corpus access, without a reader or terminal interface."""

from __future__ import annotations

from pathlib import Path
import re
import shlex
import sys

from .models import Book, Node, Passage


def load_corpus_book(corpus: Path) -> Book:
    """Load the three-doctrine reader view without opening or parsing the PDF.

    The canonical corpus retains its richer edition/volume hierarchy. Its
    explicitly supplied reader_path metadata defines this convenient view;
    it is not reconstructed from heading spellings or assigned new IDs.
    """
    from sol.corpus.contract import CorpusError, load_snapshot

    try:
        snapshot = load_snapshot(corpus)
        records = snapshot.records
    except CorpusError as error:
        if not (corpus / "corpus.json").is_file():
            raise ValueError(
                f"Cannot use local corpus {corpus}: corpus.json not found.\n"
                "Select its actual location with sol --set-corpus DIRECTORY or --corpus DIRECTORY.\n"
                "If SOL_CORPUS is set, update or unset that environment override."
            ) from error
        instruction = f"{shlex.quote(sys.executable)} -m sol.corpus.contract {shlex.quote(str(corpus))}"
        raise ValueError(
            f"Cannot use local corpus {corpus}: {error}\n"
            f"After correcting canonical Markdown if necessary, rebuild the index with:\n{instruction}"
        ) from error

    root = Node("", "The Science of Logic", 7)
    nodes: dict[tuple[str, ...], Node] = {(): root}
    children: dict[tuple[str, ...], list[Node]] = {(): []}
    node_orders: dict[tuple[str, ...], int] = {}
    # Reader-facing names are intentionally shorter than the edition outline.
    for name, title, start in (
        ("BEING", "Doctrine of Being (Book One)", 7),
        ("ESSENCE", "Doctrine of Essence (Book Two)", 337),
        ("CONCEPT", "Doctrine of the Concept", 507),
    ):
        node = Node(name, title, start, parent=root)
        nodes[(name,)] = node
        children[()] += [node]
        children[(name,)] = []

    def reader_path(record: dict) -> tuple[str, ...]:
        value = record.get("reader_path")
        if not isinstance(value, str) or not value.startswith("/"):
            raise ValueError(f"Corpus record {record['id']} requires an absolute reader_path")
        parts = tuple(value[1:].split("/"))
        if not parts or parts[0] not in {"BEING", "ESSENCE", "CONCEPT"} or any(
            part in {"", ".", ".."} or "\\" in part for part in parts
        ):
            raise ValueError(f"Invalid corpus reader_path on {record['id']}: {value}")
        if any(part.endswith(".txt") for part in parts[:-1]):
            raise ValueError(f"Corpus reader_path descends through a virtual file: {value}")
        return parts

    def printed(source: dict, identifier: str) -> int:
        value = source["printed_page"]
        if not isinstance(value, str) or not re.fullmatch(r"\d+", value):
            raise ValueError(f"Main Hegel reader record {identifier} needs an Arabic printed-page label")
        return int(value)

    def ensure_node(path: tuple[str, ...], title: str, start: int, order: int, label: str = "") -> Node:
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Corpus reader title must be a nonempty string: /{'/'.join(path)}")
        for length in range(1, len(path) + 1):
            prefix = path[:length]
            node_orders[prefix] = min(node_orders.get(prefix, order), order)
            if prefix not in nodes:
                parent_path = prefix[:-1]
                name = prefix[-1]
                descriptive = name.removesuffix(".txt").replace("-", " ")
                node = Node(name, descriptive, start, parent=nodes[parent_path])
                nodes[prefix] = node
                children.setdefault(parent_path, []).append(node)
                children[prefix] = []
        node = nodes[path]
        node.title = title
        node.start_page = min(node.start_page, start)
        if label:
            node.label = label
        return node

    # Section metadata establishes titles, labels, and source order before leaf
    # passage files are attached. Editorial sections without reader_path belong
    # to the canonical corpus, not to this default Hegel-only convenience view.
    for record in records:
        if record["type"] == "section" and "reader_path" in record:
            path = reader_path(record)
            first = record["sources"][0]
            ensure_node(path, record.get("reader_title", record.get("title", record["plain_text"])),
                        printed(first, record["id"]), record["order"], record.get("label", ""))

    passages: list[Passage] = []
    for record in records:
        attribution = record["attribution"]
        if record["type"] not in {"paragraph", "list_item", "quotation", "formula"} or (
            attribution["author"] != "G. W. F. Hegel" or attribution["role"] != "main_text"
        ):
            continue
        path = reader_path(record)
        eligible = record.get("random_eligible", True)
        if not isinstance(eligible, bool):
            raise ValueError(f"Corpus random_eligible must be boolean: {record['id']}")
        if not path[-1].endswith(".txt"):
            raise ValueError(f"Main-text reader_path must identify a virtual .txt file: /{'/'.join(path)}")
        first, last = record["sources"][0], record["sources"][-1]
        title = record.get("reader_title", record.get("heading", path[-1].removesuffix(".txt")))
        node = ensure_node(path, title, printed(first, record["id"]), record["order"])
        # The first source paragraph determines the file's displayed start page.
        node.start_page = min(node.start_page, printed(first, record["id"]))
        passages.append(Passage(
            record["plain_text"], first["pdf_page"], printed(first, record["id"]),
            node, path, last["pdf_page"], printed(last, record["id"]),
            record["id"], record.get("heading", title), record["type"], eligible,
            record.get("transcription_status", ""),
            tuple(re.findall(r"(?m)^!\[(Source facsimile, printed page [0-9ivxlcdm]+)\]"
                             r"\((?:\.\./)*assets/[^\s)]+\.png\)\s*$", record.get("markdown", ""))),
        ))

    for path, node in nodes.items():
        node.children = tuple(children[path])
        if node.children and node.name.endswith(".txt"):
            raise ValueError(f"Corpus maps both file and directory to /{'/'.join(path)}")
        # Put a directory's own introductory text before its subdivisions.
        node.children = tuple(sorted(node.children, key=lambda child: (
            child.name != "00-introduction.txt", node_orders.get(path + (child.name,), float("inf"))
        )))
    if not passages:
        raise ValueError("The local corpus contains no indexed Hegel main-text paragraphs for the reader")
    redirects = {record["id"]: record["redirect_id"] for record in records
                 if record["type"] == "retired_record"}
    # Keep the complete verified record graph beside the convenient reader view.
    # Markdown, attribution, notes, source rectangles and retirement history must
    # not disappear merely because the terminal presents Hegel's prose as text.
    return Book(root, passages, redirects,
                {record["id"]: record for record in records}, snapshot.corpus_directory,
                snapshot.manifest, snapshot)
