"""Continuous reading through the ordinary BEING workspace boundary.

Neovim owns screen mechanics only. Each bounded surface is disposable; Python
owns source identity, section transitions, validation and guarded persistence.
No editor buffer or byte column is ever saved as a reading position.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import os
import sys
import unicodedata

from sol.core.protocol import capture_reference, single_action
from sol.reader.actions import ReaderActions
from sol.reader.surface import Sample
from sol.reader.structure import structure_payload
from sol.terminal import neovim
from sol.presentation.text import safe_label, safe_output
from sol.presentation.theme import DEFAULT_THEME, THEMES


SECTION_BUDGET = 64
# The reader's own values of what Neovim's isolation replaces, given back to ESSENCE.
ESSENCE_ENVIRONMENT = ("XDG_CONFIG_HOME", "XDG_CONFIG_DIRS", "XDG_DATA_HOME", "XDG_DATA_DIRS",
                       "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR", "TMPDIR")
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
    from sol.being.source_view import open_viewer
    from sol.core.source import render_region

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


def source_pdf(request, page):
    """Open the verified PDF at one source page of a captured record, for zooming in context."""
    from sol.being.source_view import open_pdf

    if not 1 <= page <= len(request["sources"]):
        raise ValueError(f"this passage has {len(request['sources'])} source page(s)")
    row = request["sources"][page - 1]
    return {"viewer": open_pdf(request, page - 1), "pdf_page": row["pdf_page"],
            "printed_page": safe_label(row.get("printed_page") or "unnumbered")}


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
    transient_markers, transient_landmarks = {}, {}
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

    def landmark_name(name):
        # A reader's own words; SOL's internal "sol:" names stay out of reach.
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or name.strip().startswith("sol:") \
                or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in name):
            raise ValueError("a landmark name is 1–80 characters of ordinary text")
        return name.strip()

    def landmark_rows():
        saved = (dict(transient_landmarks) if workspace_reader is None else
                 {row["name"]: row for row in workspace_reader.store.list_bookmarks()
                  if not row["name"].startswith("sol:")})
        rows = []
        for name in sorted(saved, key=str.casefold):
            row = {"name": safe_label(name), "target": None, "label": "saved paragraph is unavailable"}
            try:
                passage = book.find_passage(saved[name]["target_id"])
                snippet = " ".join(passage.text.split())[:64]
                row.update(target=saved[name]["target_id"],
                           label=f"{passage.heading or passage.node.title} | p. {passage.printed_page} | {snippet}")
            except ValueError:
                pass
            rows.append(row)
        return rows

    def landmarks(action, name=None):
        return {"landmarks": {"persistent": workspace_reader is not None, "action": action,
                              "name": safe_label(name or ""), "rows": [
                                  {key: row[key] for key in ("name", "label")} | {"available": row["target"] is not None}
                                  for row in landmark_rows()]}}

    def personal_notes(shown):
        """The workspace's notes on the shown passages, following retired IDs.

        Each note says whether this reader may edit it and whether its passage
        changed since it was written; the note keeps its original binding.
        """
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
                if record["revision"] is None:
                    refusal = "editing needs workspace version 2; upgrade a copy with sol --workspace NAME --workspace-upgrade FILE.sqlite3"
                elif record["actor"] != workspace_reader.actor:
                    refusal = "only the note's author can edit it"
                elif any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} and c not in "\n\t"
                         for c in record["body"]):
                    refusal = "this note has invisible control characters; edit it with sol --shell"
                else:
                    refusal = ""
                notes.setdefault(target, []).append({
                    "id": record["id"], "author": display_line(record["actor"]),
                    "created_at": display_line(record["created_at"]),
                    "revision": record["revision"], "edit_refusal": refusal,
                    "changed_source": record["content_sha256"] != book.canonical_records[target]["content_sha256"],
                    "retired_target": record["target_id"] != target,
                    # The exact text goes to the editor only when it is safe to show raw.
                    "body": None if refusal else record["body"],
                    "lines": [display_line(line) for line in record["body"].split("\n")]})
        return {"persistent": True, "notes": notes}

    # Cache only immutable typography by its exact two input strings, bounded
    # to this reader. Every payload still captures/checks/finishes its source
    # export; neither references nor source trust are retained here.
    typography = lru_cache(maxsize=256)(neovim.map_typography)

    def prepare():
        state = actions.snapshot()
        extent = reading_section(book, state.current.identifier)
        sample = Sample(book, tuple(book.passages[extent.first:extent.last + 1]), ReaderActions(book))
        requested_ids = {state.current.identifier: state.requested_id}
        # build_payload checks this reference against the exact reader projection
        # and requested identity; capture_active_reference would check it twice.
        restored = {"reference": capture_reference(book.corpus_snapshot, state.requested_id),
                    "selection": None if state.selection is None else asdict(state.selection),
                    "cursor_offset": state.cursor_offset}
        payload = neovim.build_payload(sample, width, restored,
                                      requested_ids=requested_ids, emphasis=emphasis, theme=theme,
                                      _typography=typography)
        navigation = {"previous": extent.first > 0, "next": extent.last + 1 < len(book.passages)}
        structure = structure_payload(book, state.current)
        structure["depth"] = tree_depth
        if start_tree:
            structure["root"] = "/"
        progress = {"first": extent.first, "total": len(book.passages)}
        payload.update(navigation=navigation, progress=progress, notice=notice or "", mode=mode, focus=focused,
                       markers=markers(), structure=structure, tree_only=start_tree,
                       personal=personal_notes(sample), search_marks=search_marks)
        neovim._safe_metadata({"notice": payload["notice"], "markers": payload["markers"], "structure": structure,
                               "theme": payload["theme"], "personal": payload["personal"]})
        return payload, sample, extent

    def prepare_position():
        # Reuse only the presentation already on screen. Checking its exact
        # packet still verifies CORE and the reader projection on every move.
        state = actions.snapshot()
        row = next(row for row in payload["records"] if row["id"] == state.current.identifier)
        restored = {"reference": row["reference"], "cursor_offset": state.cursor_offset,
                    "selection": None if state.selection is None else asdict(state.selection)}
        if row["reference"]["reference"]["requested_id"] != state.requested_id:
            raise ValueError("shown reference disagrees with the destination identity")
        neovim._check_sample_packet(sample, restored, payload["records"])
        position = {"restore": restored, "notice": notice, "search_marks": search_marks}
        neovim._safe_metadata(position)
        return position

    with single_action(book.corpus_snapshot):
        payload, sample, extent = prepare()

    # Each action's extra fields, their checks and the refusals shown in Neovim.
    # Actions without an entry take no extra field.
    note_body = ("body", lambda body: isinstance(body, str) and 1 <= len(body.strip()) and len(body) <= NOTE_LIMIT,
                 f"a note needs 1–{NOTE_LIMIT} characters")
    note_id = ("note", lambda note: isinstance(note, str), "choose one of your notes on this passage")
    extra_fields = {
        "marker_set": [("slot", lambda slot: type(slot) is int and slot in (1, 2, 3),
                        "reader markers have slots 1, 2 and 3")],
        "node_open": [("node", lambda node: True, "")],
        "landmark_set": [("name", lambda name: isinstance(name, str), "name the landmark")],
        "landmark_open": [("name", lambda name: isinstance(name, str), "choose a listed landmark")],
        "page_open": [("page", lambda page: type(page) is int and 1 <= page <= 100000,
                       "type a printed page number")],
        "source_preview": [("page", lambda page: type(page) is int, "choose a source page by number")],
        "source_pdf": [("page", lambda page: type(page) is int, "choose a source page by number")],
        "source_follow": [],
        "search": [("query", lambda query: isinstance(query, str) and 1 <= len(query.strip()) <= 256,
                    "search needs 1–256 characters")],
        "search_open": [("result", lambda result: type(result) is int and 1 <= result <= len(actions.results),
                         "choose a displayed search result")],
        "note_add": [note_body],
        "note_edit": [note_id, ("revision", lambda revision: type(revision) is int and revision >= 1,
                                "the note's revision is required"), note_body],
        "note_history": [note_id],
        "footnote_open": [("trail", lambda trail: isinstance(trail, list), "choose a linked book footnote")],
        "essence_source": [("source", lambda source: isinstance(source, dict)
                            and set(source) == {"id", "start", "content_sha256"}
                            and isinstance(source["id"], str) and isinstance(source["content_sha256"], str)
                            and type(source["start"]) is int and source["start"] >= 0,
                            "choose a source passage listed in ESSENCE")],
    }
    extra_fields["marker_clear"] = extra_fields["marker_open"] = extra_fields["marker_set"]
    extra_fields["landmark_clear"] = extra_fields["landmark_set"]
    navigation_actions = {"next", "previous", "passage_next", "passage_previous", "node_open", "page_open",
                          "landmark_open", "marker_open", "search_open", "search_next", "search_previous",
                          "history_back", "history_forward", "essence_source"}

    def search_panel(request, identifier):
        # Searching does not move the cursor, save a visit or erase a selection.
        rows = actions.search(request["query"], path=(), limit=None)
        return {"search": {"query": safe_label(request["query"]), "total": actions.search_position()[1], "rows": [
            {"number": i, "label": safe_label(f"{row.heading or row.node.title} | p. {row.printed_page}"),
             "snippet": safe_label(" ".join(row.text.split())[:150])}
            for i, row in enumerate(rows, 1)]}}

    def source_panel(request, identifier):
        # Viewing evidence keeps the cursor, selection and saved position.
        nonlocal source_service
        from sol.core.source import SourceError, SourceService
        target = request["packet"]["reference"]["reference"]["target_id"]
        if source_service is None:
            source_service = SourceService(book)
        if target not in source_requests:
            source_requests[target] = source_service.capture(target)
        try:
            if request["op"] == "source_follow":
                # Turns only a Zathura window S opened; never opens one or moves the reader.
                from sol.being.source_view import follow_pdf
                return {"follow": {"active": follow_pdf(source_requests[target], 0)}}
            if request["op"] == "source_pdf":
                opened = source_pdf(source_requests[target], request["page"])
                if opened["viewer"] is not None:
                    return {"pdf": opened}
                # No PDF viewer: the crop is still the printed evidence.
                return {"source": {**source_preview(source_requests[target], request["page"]), "pdf_missing": True}}
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

    def landmark_panel(request, identifier):
        operation = request["op"]
        if operation == "landmark_list":
            return landmarks("list")
        name = landmark_name(request["name"])
        if operation == "landmark_set":
            if workspace_reader is None:
                transient_landmarks[name] = {"target_id": identifier}
            else:
                workspace_reader.save_bookmark(name, actions.session, identifier, replace=True)
            return landmarks("set", name)
        if workspace_reader is None:
            transient_landmarks.pop(name, None)
        else:
            workspace_reader.remove_bookmark(name)
        return landmarks("cleared", name)

    def note_panel(request, identifier):
        # The note binds the requested passage and its content digest through
        # the shell's own service; a selection is context only, never stored.
        if workspace_reader is None:
            raise ValueError("notes need a workspace; this temporary -n session saves nothing")
        workspace_reader.ensure_corpus_current()
        workspace_reader.add_annotation(request["body"], actions.session, identifier)
        return {"personal": personal_notes(sample)}

    def shown_note(request, identifier):
        """A note listed under the passage the editor sent, never an arbitrary ID."""
        if workspace_reader is None:
            raise ValueError("notes need a workspace; this temporary -n session saves nothing")
        target = request["packet"]["reference"]["reference"]["target_id"]
        listed = personal_notes(sample)["notes"].get(target, [])
        row = next((row for row in listed if row["id"] == request["note"]), None)
        if row is None:
            raise ValueError("that note is not on this passage; open c on its passage")
        return row

    def note_edit_panel(request, identifier):
        # Only the note's author edits it, from the revision they opened; the
        # note keeps its ID, target and original source digest. A save that
        # changes nothing adds no revision.
        row = shown_note(request, identifier)
        if row["edit_refusal"]:
            raise ValueError(row["edit_refusal"])
        captured = workspace_reader.prepare_annotation_edit(row["id"])
        if captured.revision != request["revision"]:
            raise ValueError("this note changed in another session since you opened it; "
                             "your draft is kept, reopen c to see the newer text")
        saved = workspace_reader.save_annotation_edit(captured, request["body"], expected_revision=request["revision"])
        return {"personal": personal_notes(sample),
                "note_saved": {"id": saved["id"], "revision": saved["revision"],
                               "changed": saved["revision"] != captured.revision}}

    def note_history_panel(request, identifier):
        row = shown_note(request, identifier)
        revisions = [] if row["revision"] is None else workspace_reader.store.list_annotation_history(row["id"])
        return {"note_history": {"id": row["id"], "author": row["author"], "revisions": [
            {"revision": item["revision"], "kind": display_line(item["kind"]),
             "editor": display_line(item["editor"] or item["actor"]),
             "recorded_at": display_line(item["recorded_at"]),
             "lines": [display_line(line) for line in item["body"].split("\n")]}
            for item in reversed(revisions)]}}

    def footnote_panel(request, identifier):
        target = request["packet"]["reference"]["reference"]["target_id"]
        return {"footnote": neovim.build_footnote_payload(sample, target, request["trail"])}

    essence_directory = None

    def essence_panel(request, identifier):
        # ESSENCE opens beside the reader with where the reader is: a checked
        # reference, cursor and selection. The context file holds no book text;
        # nothing here moves the cursor or writes the workspace.
        nonlocal essence_directory
        from sol.essence.tui import TEXTUAL_HINT, textual_available
        from sol.essence.tui.context import write_context
        if not textual_available():
            raise ValueError(TEXTUAL_HINT)
        origin = request["packet"]["reference"]
        actions.check_return_reference(origin)
        passage = book.find_passage(origin["reference"]["target_id"])
        if essence_directory is None:
            import atexit
            import shutil
            import tempfile
            essence_directory = tempfile.mkdtemp(prefix="sol-essence-")
            atexit.register(shutil.rmtree, essence_directory, True)
        state_file = None
        if workspace_reader is not None:
            from pathlib import Path
            state_home = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
            state_file = Path(state_home) / "sol" / "essence" / "investigation.json"
        selection = request["packet"]["selection"]
        context = write_context(
            essence_directory, reference=origin, cursor_offset=request["packet"]["cursor_offset"],
            selection=None if selection is None else {key: value for key, value in selection.items() if key != "text"},
            label=safe_label(f"{passage.heading or passage.node.title} | p. {passage.printed_page}"),
            corpus=str(book.corpus_directory or ""), state_file=state_file)
        # Neovim runs with private XDG and temporary directories; ESSENCE is a
        # SOL program and saves studies where the reader does, so it gets the
        # reader's own values back (empty means unset, as XDG treats it).
        environment = {name: os.environ.get(name, "") for name in ESSENCE_ENVIRONMENT}
        # ESSENCE opens in the reader's theme and follows T through a small
        # owner-only file beside the context, which the reader rewrites.
        theme_file = context.with_suffix(".theme")
        descriptor = os.open(theme_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(theme)
        return {"essence": {"command": [sys.executable, "-m", "sol.essence.tui", "--context", str(context),
                                        "--theme", theme, "--theme-file", str(theme_file)],
                            "theme_file": str(theme_file),
                            "env": environment}}

    panels = {"search": search_panel, "source_preview": source_panel, "source_pdf": source_panel,
              "source_follow": source_panel,
              "marker_set": marker_panel, "marker_clear": marker_panel, "landmark_list": landmark_panel,
              "landmark_set": landmark_panel, "landmark_clear": landmark_panel, "note_add": note_panel,
              "note_edit": note_edit_panel, "note_history": note_history_panel, "footnote_open": footnote_panel, "essence_open": essence_panel}

    def handle(request):
        # One editor request is one user action: CORE compares the in-memory
        # corpus once for it and still checks the files on every reference.
        with single_action(book.corpus_snapshot):
            return handle_action(request)

    def handle_action(request):
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
        for name, valid, refusal in extra_fields.get(operation, ()):
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
        elif operation == "landmark_open":
            name = landmark_name(request["name"])
            row = next((row for row in landmark_rows() if row["name"] == name), None)
            if row is None or row["target"] is None:
                raise ValueError("that landmark is gone or its paragraph is unavailable")
            target, offset = row["target"], 0
        elif operation == "page_open":
            # The first paragraph printed on that page, or running onto it.
            wanted = request["page"]
            passage = next((row for row in book.passages if row.end_printed_page >= wanted), None)
            if passage is None or wanted < book.passages[0].printed_page:
                raise ValueError(f"printed pages run from {book.passages[0].printed_page} "
                                 f"to {book.passages[-1].end_printed_page}")
            target, offset = passage.identifier, 0
        elif operation.startswith("passage_"):
            at = next(i for i, row in enumerate(book.passages) if row.identifier ==
                      request["packet"]["reference"]["reference"]["target_id"])
            at += 1 if operation == "passage_next" else -1
            if not 0 <= at < len(book.passages):
                raise ValueError("no adjacent paragraph")
            target, offset = book.passages[at].identifier, 0
        elif operation == "essence_source":
            # A word's source from an ESSENCE result: CORE captures the record
            # below, and the passage must still be the text that was counted.
            source = request["source"]
            target, offset = source["id"], source["start"]
        elif operation in ("search_open", "search_next", "search_previous", "history_back", "history_forward"):
            target = None
        else:
            if not payload["navigation"][operation]:
                raise ValueError("no adjacent reading section")
            passage = book.passages[extent.last + 1 if operation == "next" else extent.first - 1]
            target, offset = passage.identifier, 0 if operation == "next" else len(passage.text)
        if target is not None:
            from sol.core.protocol import capture_reference
            reference = capture_reference(book.corpus_snapshot, target)
            if operation == "essence_source":
                if (reference["reference"]["target_id"] != target
                        or reference["reference"]["content_sha256"] != request["source"]["content_sha256"]):
                    raise ValueError("this passage changed after ESSENCE counted it; count again")
                if offset > len(book.find_passage(target).text):
                    raise ValueError("this source position is outside its passage")
        # Retain the actual outgoing semantic location first, not Python's last
        # loaded cursor or Neovim's disposable buffer jumplist. The editor shows
        # it, so it may be saved even if the move below is refused.
        actions.accept_return_position(request["packet"]["reference"], request["packet"]["cursor_offset"], selected)
        shown = mode, start_tree, notice, search_marks, focused, theme
        cursor_update = None
        try:
            # The destination is saved only once its view is ready; a failure
            # leaves the shown view, the saved position and history as they were.
            with actions.staged():
                if operation == "search_open":
                    actions.open_result(request["result"])
                elif operation.startswith("search_"):
                    actions.search_next(reverse=operation == "search_previous")
                elif operation.startswith("history_"):
                    getattr(actions, operation)()
                else:
                    actions.accept_return_position(reference, offset, history_locations=True)
                mode, start_tree, notice, search_marks = request["mode"], False, "", None
                if operation in ("search_open", "search_next", "search_previous"):
                    projection = actions.search_highlights()
                    position, total = actions.search_position()
                    notice = projection.reason or ""
                    search_marks = {"id": actions.snapshot().current.identifier,
                                    "position": position, "total": total,
                                    "spans": [[start, end] for start, end in projection.spans]}
                focused = request.get("focus", focused)
                theme = request.get("theme", theme)
                state = actions.snapshot()
                if (operation in ("search_next", "search_previous")
                        and state.current.identifier == request["packet"]["reference"]["reference"]["target_id"]
                        and state.requested_id == request["packet"]["reference"]["reference"]["requested_id"]
                        and (mode, focused, theme) == (shown[0], shown[4], shown[5])
                        and notice == payload["notice"] and not shown[1]):
                    cursor_update = prepare_position()
                    prepared = ({**payload, **cursor_update}, sample, extent)
                else:
                    prepared = prepare()
        except BaseException:
            mode, start_tree, notice, search_marks, focused, theme = shown
            raise
        payload, sample, extent = prepared
        return {"position": cursor_update} if cursor_update is not None else {"payload": payload}

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
