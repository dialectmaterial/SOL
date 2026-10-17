"""Continuous reading through the ordinary BEING workspace boundary.

Neovim owns screen mechanics only. Each bounded surface is disposable; Python
owns source identity, section transitions, validation and guarded persistence.
No editor buffer or byte column is ever saved as a reading position.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import sys

from sol.reader.actions import ReaderActions
from sol.reader.surface import Sample
from sol.reader.structure import structure_payload
from sol.terminal import neovim
from sol.terminal.text import safe_output


SECTION_BUDGET = 64


@dataclass(frozen=True)
class ReadingSection:
    """Inclusive positions in Book.passages, not a new document identity."""
    first: int
    last: int


def reading_section(book, identifier):
    """Use supplied chapter ancestry, splitting oversized extents into 64 records.

    The current corpus marks chapters at heading level 4. Without such an
    ancestor, use the passage's actual parent section, never a guessed title.
    Search across sections remains a separate workflow from native local search.
    """
    def anchor(passage):
        record = book.canonical_records[passage.identifier]
        parent, seen = record.get("parent_id"), set()
        fallback = parent
        while parent is not None:
            if parent in seen or parent not in book.canonical_records:
                raise ValueError("the reader source hierarchy is broken; reopen a verified corpus")
            seen.add(parent)
            section = book.canonical_records[parent]
            if section.get("type") != "section":
                raise ValueError("a reading parent must be a supplied source section")
            if section.get("level") == 4:
                return parent
            parent = section.get("parent_id")
        return fallback

    passage = book.find_passage(identifier)
    index = next(i for i, item in enumerate(book.passages) if item is passage)
    key = anchor(passage)
    first = last = index
    while first > 0 and anchor(book.passages[first - 1]) == key:
        first -= 1
    while last + 1 < len(book.passages) and anchor(book.passages[last + 1]) == key:
        last += 1
    first += (index - first) // SECTION_BUDGET * SECTION_BUDGET
    return ReadingSection(first, min(last, first + SECTION_BUDGET - 1))


def run_reader(book, workspace_reader=None, *, width=72, emphasis="auto", start_tree=False, tree_depth=2):
    """Resume, read continuously, and accept one verified semantic position.

    The frontend sends data, never executable commands. Explicit actions use
    private inherited pipes; section changes reload the view in the same native
    process. Cursor keys do not send workspace requests.
    """
    executable = neovim.validate_environment(width)
    actions = ReaderActions(book, workspace_reader)
    notice = ""
    if workspace_reader is not None and workspace_reader.store.get_state() is not None:
        _, notice = actions.restore()
    else:
        actions.read((), first=True)
    transient_markers = {}
    mode = "continuous"

    def marker_name(slot):
        return f"sol:reader-marker:{slot}"

    def markers():
        rows = []
        for slot in (1, 2, 3):
            saved = (transient_markers.get(slot) if workspace_reader is None else
                     workspace_reader.store.get_bookmark(marker_name(slot)))
            row = {"slot": slot, "target": None, "resolved": None, "label": "empty"}
            if saved is not None:
                try:
                    passage = book.find_passage(saved["target_id"])
                    snippet = " ".join(passage.text.split())[:64]
                    row.update(target=saved["target_id"], resolved=passage.identifier,
                               label=f"{passage.heading or passage.node.title} | p. {passage.printed_page} | {snippet}")
                except ValueError:
                    row["label"] = "saved paragraph is unavailable; replace or clear this marker"
            rows.append(row)
        return {"persistent": workspace_reader is not None, "slots": rows}

    def prepare():
        state = actions.snapshot()
        extent = reading_section(book, state.current.identifier)
        sample = Sample(book, tuple(book.passages[extent.first:extent.last + 1]), ReaderActions(book))
        requested_ids = {state.current.identifier: state.requested_id}
        restored = {"reference": actions.capture_active_reference(),
                    "selection": None if state.selection is None else asdict(state.selection),
                    "cursor_offset": state.cursor_offset}
        payload = neovim.build_payload(sample, width, restored,
                                      requested_ids=requested_ids, emphasis=emphasis)
        navigation = {"previous": extent.first > 0, "next": extent.last + 1 < len(book.passages)}
        structure = structure_payload(book, state.current)
        structure["depth"] = tree_depth
        if start_tree:
            structure["root"] = "/"
        payload.update(integrated=True, navigation=navigation, notice=notice or "", mode=mode,
                       markers=markers(), structure=structure, tree_only=start_tree)
        neovim._safe_metadata({"notice": payload["notice"], "markers": payload["markers"], "structure": structure})
        return payload, sample, extent

    payload, sample, extent = prepare()

    def handle(request):
        nonlocal payload, sample, extent, mode, start_tree, notice
        operation = request.get("op")
        fields = {"op", "packet", "mode"}
        if operation in ("marker_set", "marker_clear", "marker_open"):
            fields.add("slot")
            if type(request.get("slot")) is not int or request["slot"] not in (1, 2, 3):
                raise ValueError("reader markers have slots 1, 2 and 3")
        elif operation == "node_open":
            fields.add("node")
        elif operation not in ("next", "previous"):
            raise ValueError("unknown reader action")
        if set(request) != fields or request.get("mode") not in ("continuous", "paragraph"):
            raise ValueError("invalid reader action fields or reading mode")
        selected = neovim._check_sample_packet(sample, request["packet"], payload["records"])
        identifier = request["packet"]["reference"]["reference"]["requested_id"]
        if operation in ("marker_set", "marker_clear"):
            slot = request["slot"]
            if workspace_reader is None:
                if operation == "marker_set":
                    transient_markers[slot] = {"target_id": identifier}
                else:
                    transient_markers.pop(slot, None)
            elif operation == "marker_set":
                workspace_reader.save_bookmark(marker_name(slot), actions.session, identifier, replace=True)
            else:
                workspace_reader.remove_bookmark(marker_name(slot))
            return {"markers": markers()}
        if selected is not None:
            raise ValueError("clear the selection before changing reading locations")
        if operation == "marker_open":
            row = markers()["slots"][request["slot"] - 1]
            if row["target"] is None:
                raise ValueError("that marker is empty or its paragraph is unavailable")
            target, offset = row["target"], 0
        elif operation == "node_open":
            if not isinstance(request["node"], str):
                raise ValueError("a displayed tree node is required")
            row = next((row for row in payload["structure"]["nodes"] if row["key"] == request["node"]), None)
            if row is None or row["target"] is None:
                raise ValueError("this tree branch has no readable passage")
            target, offset = row["target"], 0
        else:
            if not payload["navigation"][operation]:
                raise ValueError("no adjacent reading section")
            passage = book.passages[extent.last + 1 if operation == "next" else extent.first - 1]
            target, offset = passage.identifier, 0 if operation == "next" else len(passage.text)
        from sol.core.protocol import capture_reference
        reference = capture_reference(book.corpus_snapshot, target)
        actions.accept_return_position(reference, offset)
        mode, start_tree, notice = request["mode"], False, ""
        payload, sample, extent = prepare()
        return {"payload": payload}

    while True:
        status, result = neovim.launch_payload(payload, executable, on_request=handle)
        if status or result is None:
            # :qa! / interruption / a crashed editor does not save an unchecked
            # current cursor. Earlier successful saves are retained.
            return status
        if (not isinstance(result, dict) or set(result) != {"action", "packet"}
                or not isinstance(result["action"], str)
                or result["action"] not in {"quit", "next", "previous"}):
            raise ValueError("Neovim returned an invalid reader action; position was not saved")
        action, packet = result["action"], result["packet"]
        if action != "quit" and not payload["navigation"][action]:
            raise ValueError("Neovim requested an unavailable reading section; position was not saved")
        selected = neovim._check_sample_packet(sample, packet, payload["records"])
        if action != "quit" and selected is not None:
            raise ValueError("clear the passage-local selection before changing reading sections")
        if action == "quit":
            actions.accept_return_position(packet["reference"], packet["cursor_offset"], selected)
            if workspace_reader is not None and workspace_reader.store.schema_version < 3:
                print("sol: " + safe_output("This older workspace saved the passage only, not the cursor. "
                      "Upgrade a copy to save exact reading positions."), file=sys.stderr)
            return 0
        # Validate the outgoing view before accepting the explicit neighboring
        # source visit. No synthetic combined passage, screen row or byte offset.
        handle({"op": action, "packet": packet, "mode": mode})
