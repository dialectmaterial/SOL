"""Continuous reading through the ordinary BEING workspace boundary.

Neovim owns screen mechanics only. Each bounded surface is disposable; Python
owns source identity, section transitions, validation and guarded persistence.
No editor buffer or byte column is ever saved as a reading position.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import sys
import unicodedata

from sol.reader.actions import ReaderActions
from sol.reader.surface import Sample
from sol.reader.structure import structure_payload
from sol.terminal import neovim
from sol.terminal.text import safe_label, safe_output
from sol.terminal.theme import DEFAULT_THEME, THEMES


SECTION_BUDGET = 64
NOTE_LIMIT = 20000
REVIEW_NOTES = {
    "needs_visual_review": "The typed text is an unreviewed transcription and may be wrong. "
                           "The printed source is authoritative.",
    "needs_review": "The typed text needs review. Compare it with the printed source.",
}


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


def display_line(text):
    """Escape what the Neovim payload refuses; a note is the reader's words, not source."""
    return "".join(f"\\u{ord(c):04x}" if unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} else c
                   for c in text.replace("\t", "    "))


def source_preview(request, page):
    """Render one source page of a captured record and offer it to a viewer.

    The crop comes from the verified PDF snapshot, never from a corpus image
    or a generated transcription. No reading position or workspace changes.
    """
    from sol.terminal.source import open_viewer, render_region

    if not 1 <= page <= len(request["sources"]):
        raise ValueError(f"this passage has {len(request['sources'])} source page(s)")
    image, cropped = render_region(request, page - 1)
    status = request.get("transcription_status") or ""
    return {"title": safe_label(request["title"]), "record": request["target_id"],
            "status": safe_label(status.replace("_", " ") or "not flagged for review"),
            "note": REVIEW_NOTES.get(status, ""),
            "pages": [{"number": i, "pdf_page": row["pdf_page"],
                       "printed_page": safe_label(row.get("printed_page") or "unnumbered"),
                       "region": "bbox" in row}
                      for i, row in enumerate(request["sources"], 1)],
            "shown": page, "cropped": cropped, "image": safe_label(image),
            "viewer": open_viewer(image)}


def run_reader(book, workspace_reader=None, *, width=72, emphasis="auto", start_tree=False, tree_depth=2,
               theme=DEFAULT_THEME):
    """Resume, read continuously, and accept one verified semantic position.

    The frontend sends data, never executable commands. Explicit actions use
    private inherited pipes; section changes reload the view in the same native
    process. Cursor keys do not send workspace requests. A theme switched in
    the reader lasts for this session only; it is never saved implicitly.
    """
    executable = neovim.validate_environment(width)
    actions = ReaderActions(book, workspace_reader)
    notice = ""
    # Match spans for the passage a search action just opened; other actions clear them.
    search_marks = None
    if workspace_reader is not None and workspace_reader.store.get_state() is not None:
        _, notice = actions.restore()
    else:
        actions.read((), first=True)
    transient_markers = {}
    source_service, source_requests = None, {}
    mode = "continuous"
    focused = False
    if theme not in THEMES:
        raise ValueError(f"reader theme must be one of: {', '.join(THEMES)}")

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

    def personal_notes(shown):
        """The workspace's notes on the shown passages, following retired IDs."""
        if workspace_reader is None:
            return {"persistent": False, "notes": {}}
        shown_ids = {passage.identifier for passage in shown.passages}
        notes = {}
        for record in workspace_reader.store.list_annotations():
            target, seen = record["target_id"], set()
            while target in book.redirects and target not in seen:
                seen.add(target)
                target = book.redirects[target]
            if target in shown_ids:
                notes.setdefault(target, []).append({
                    "id": record["id"], "author": display_line(record["actor"]),
                    "created_at": display_line(record["created_at"]),
                    "lines": [display_line(line) for line in record["body"].split("\n")]})
        return {"persistent": True, "notes": notes}

    def prepare():
        state = actions.snapshot()
        extent = reading_section(book, state.current.identifier)
        sample = Sample(book, tuple(book.passages[extent.first:extent.last + 1]), ReaderActions(book))
        requested_ids = {state.current.identifier: state.requested_id}
        restored = {"reference": actions.capture_active_reference(),
                    "selection": None if state.selection is None else asdict(state.selection),
                    "cursor_offset": state.cursor_offset}
        payload = neovim.build_payload(sample, width, restored,
                                      requested_ids=requested_ids, emphasis=emphasis, theme=theme)
        navigation = {"previous": extent.first > 0, "next": extent.last + 1 < len(book.passages)}
        structure = structure_payload(book, state.current)
        structure["depth"] = tree_depth
        if start_tree:
            structure["root"] = "/"
        payload.update(integrated=True, navigation=navigation, notice=notice or "", mode=mode, focus=focused,
                       markers=markers(), structure=structure, tree_only=start_tree,
                       personal=personal_notes(sample), search_marks=search_marks)
        neovim._safe_metadata({"notice": payload["notice"], "markers": payload["markers"], "structure": structure,
                               "theme": payload["theme"], "personal": payload["personal"]})
        return payload, sample, extent

    payload, sample, extent = prepare()

    # Each action's one extra field, its check and the refusal shown in Neovim.
    # Actions without an entry take no extra field.
    extra_fields = {
        "marker_set": ("slot", lambda slot: type(slot) is int and slot in (1, 2, 3),
                       "reader markers have slots 1, 2 and 3"),
        "node_open": ("node", lambda node: True, ""),
        "source_preview": ("page", lambda page: type(page) is int, "choose a source page by number"),
        "search": ("query", lambda query: isinstance(query, str) and 1 <= len(query.strip()) <= 256,
                   "search needs 1–256 characters"),
        "search_open": ("result", lambda result: type(result) is int and 1 <= result <= len(actions.results),
                        "choose a displayed search result"),
        "note_add": ("body", lambda body: isinstance(body, str) and 1 <= len(body.strip()) and len(body) <= NOTE_LIMIT,
                     f"a note needs 1–{NOTE_LIMIT} characters"),
    }
    extra_fields["marker_clear"] = extra_fields["marker_open"] = extra_fields["marker_set"]
    navigation_actions = {"next", "previous", "passage_next", "passage_previous", "node_open", "marker_open",
                          "search_open", "search_next", "search_previous", "history_back", "history_forward"}

    def search_panel(request, identifier):
        # Searching does not move the cursor, save a visit or erase a selection.
        rows = actions.search(request["query"], path=(), limit=20)
        return {"search": {"query": safe_label(request["query"]), "limit": 20, "rows": [
            {"number": i, "label": safe_label(f"{row.heading or row.node.title} | p. {row.printed_page}"),
             "snippet": safe_label(" ".join(row.text.split())[:150])}
            for i, row in enumerate(rows, 1)]}}

    def source_panel(request, identifier):
        # Viewing evidence keeps the cursor, selection and saved position.
        nonlocal source_service
        from sol.terminal.source import SourceError, SourceService
        target = request["packet"]["reference"]["reference"]["target_id"]
        if source_service is None:
            source_service = SourceService(book)
        if target not in source_requests:
            source_requests[target] = source_service.capture(target)
        try:
            return {"source": source_preview(source_requests[target], request["page"])}
        except SourceError:
            # A changed corpus or PDF snapshot needs a fresh capture next time.
            source_requests.pop(target, None)
            raise

    def marker_panel(request, identifier):
        slot = request["slot"]
        if workspace_reader is None:
            if request["op"] == "marker_set":
                transient_markers[slot] = {"target_id": identifier}
            else:
                transient_markers.pop(slot, None)
        elif request["op"] == "marker_set":
            workspace_reader.save_bookmark(marker_name(slot), actions.session, identifier, replace=True)
        else:
            workspace_reader.remove_bookmark(marker_name(slot))
        return {"markers": markers()}

    def note_panel(request, identifier):
        # The note binds the requested passage and its content digest through
        # the shell's own service; a selection is context only, never stored.
        if workspace_reader is None:
            raise ValueError("notes need a workspace; this temporary -n session saves nothing")
        workspace_reader.ensure_corpus_current()
        workspace_reader.add_annotation(request["body"], actions.session, identifier)
        return {"personal": personal_notes(sample)}

    panels = {"search": search_panel, "source_preview": source_panel, "marker_set": marker_panel,
              "marker_clear": marker_panel, "note_add": note_panel}

    def handle(request):
        nonlocal payload, sample, extent, mode, start_tree, notice, focused, theme, search_marks
        operation = request.get("op")
        fields = {"op", "packet", "mode"}
        if "focus" in request:
            fields.add("focus")
            if type(request["focus"]) is not bool:
                raise ValueError("reader focus must be a boolean")
        if "theme" in request:
            fields.add("theme")
            if request["theme"] not in THEMES:
                raise ValueError("unknown reader theme")
        if operation not in panels and operation not in navigation_actions:
            raise ValueError("unknown reader action")
        if operation in extra_fields:
            name, valid, refusal = extra_fields[operation]
            fields.add(name)
            if not valid(request.get(name)):
                raise ValueError(refusal)
        if set(request) != fields or request.get("mode") not in ("continuous", "paragraph"):
            raise ValueError("invalid reader action fields or reading mode")
        selected = neovim._check_sample_packet(sample, request["packet"], payload["records"])
        identifier = request["packet"]["reference"]["reference"]["requested_id"]
        if operation in panels:
            return panels[operation](request, identifier)
        if selected is not None and operation not in ("search_open", "search_next", "search_previous",
                                                      "history_back", "history_forward"):
            raise ValueError("clear the selection before changing reading locations")
        if operation in ("search_next", "search_previous") and not actions.results:
            raise ValueError("search the book first with /")
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
        elif operation.startswith("passage_"):
            at = next(i for i, row in enumerate(book.passages) if row.identifier ==
                      request["packet"]["reference"]["reference"]["target_id"])
            at += 1 if operation == "passage_next" else -1
            if not 0 <= at < len(book.passages):
                raise ValueError("no adjacent paragraph")
            target, offset = book.passages[at].identifier, 0
        elif operation in ("search_open", "search_next", "search_previous", "history_back", "history_forward"):
            # First retain the actual outgoing semantic location, not Python's
            # last loaded cursor or Neovim's disposable buffer jumplist.
            actions.accept_return_position(request["packet"]["reference"], request["packet"]["cursor_offset"], selected)
            if operation == "search_open":
                actions.open_result(request["result"])
            elif operation.startswith("search_"):
                actions.search_next(reverse=operation == "search_previous")
            else:
                getattr(actions, operation)()
            target, offset = actions.current_reference_id(), actions.cursor_offset
        else:
            if not payload["navigation"][operation]:
                raise ValueError("no adjacent reading section")
            passage = book.passages[extent.last + 1 if operation == "next" else extent.first - 1]
            target, offset = passage.identifier, 0 if operation == "next" else len(passage.text)
        from sol.core.protocol import capture_reference
        reference = capture_reference(book.corpus_snapshot, target)
        if operation not in ("search_open", "search_next", "search_previous", "history_back", "history_forward"):
            actions.accept_return_position(request["packet"]["reference"], request["packet"]["cursor_offset"])
            actions.accept_return_position(reference, offset)
        mode, start_tree, notice, search_marks = request["mode"], False, "", None
        if operation in ("search_open", "search_next", "search_previous"):
            projection = actions.search_highlights()
            notice = projection.reason or ""
            search_marks = {"id": actions.snapshot().current.identifier,
                            "spans": [[start, end] for start, end in projection.spans]}
        focused = request.get("focus", focused)
        theme = request.get("theme", theme)
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
