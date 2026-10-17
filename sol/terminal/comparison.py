"""Read-only comparison cards rendered from a captured JSON snapshot.

This module never opens a workspace, corpus, or PDF. The reader captures the
question, canonical records and attributed annotations; this independent TTY
only presents that immutable selection until the reader explicitly replaces it.
"""
from __future__ import annotations

from bisect import bisect_right
from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import select
import shlex
import signal
import sys
import termios
import tty
import unicodedata

from sol.terminal import tty as terminal
from sol.terminal.text import safe_label


_MODES = ("passages", "annotations", "question")


@dataclass(frozen=True)
class WrappedLine:
    text: str
    anchor: int


def cell_width(text: str) -> int:
    return sum(0 if unicodedata.combining(c) or unicodedata.category(c) in {"Mn", "Me", "Cf"}
               else 2 if unicodedata.east_asian_width(c) in {"W", "F"} else 1 for c in text)


def _clusters(text: str):
    """Keep combining marks attached to their base when splitting a long line."""
    current, start = "", 0
    for index, character in enumerate(text):
        zero_width = cell_width(character) == 0
        if current and not zero_width:
            yield start, current
            current, start = "", index
        if not current:
            start = index
        current += character
    if current:
        yield start, current


def wrap_text(value: str, width: int) -> list[WrappedLine]:
    """Preserve all text/paragraph boundaries and escape TTY control metadata."""
    width = max(2, width)
    result, offset = [], 0
    # Line breaks are formatting; other control characters remain literal escapes.
    for original in str(value).replace("\r\n", "\n").split("\n"):
        text = safe_label(original)
        clusters = list(_clusters(text))
        if not clusters:
            result.append(WrappedLine("", offset))
        index = 0
        while index < len(clusters):
            stop, occupied = index, 0
            while stop < len(clusters) and occupied + cell_width(clusters[stop][1]) <= width:
                occupied += cell_width(clusters[stop][1])
                stop += 1
            if stop == index:
                stop += 1
            # Prefer a nearby word boundary; preserve its whitespace in the output.
            if stop < len(clusters):
                spaces = [i + 1 for i in range(index, stop) if clusters[i][1].isspace()]
                if spaces and spaces[-1] > index + (stop - index) // 2:
                    stop = spaces[-1]
            result.append(WrappedLine("".join(c for _, c in clusters[index:stop]), offset + clusters[index][0]))
            index = stop
        offset += len(text) + 1
    return result


def _wrap(value: str, width: int) -> list[str]:
    return [line.text for line in wrap_text(value, width)]


def _clip(value, width: int) -> str:
    text = safe_label(value)
    if cell_width(text) <= width:
        return text
    out, occupied = [], 0
    for _, cluster in _clusters(text):
        if occupied + cell_width(cluster) > max(0, width - 1):
            break
        out.append(cluster)
        occupied += cell_width(cluster)
    return "".join(out) + ("…" if width else "")


def _short_path(value: str, width: int) -> str:
    """Retain the distinguishing file/section name when its prefix is long."""
    text = safe_label(value)
    if cell_width(text) <= width:
        return text
    components = text.rstrip("/").split("/")
    suffix = components[-1]
    for component in reversed(components[:-1]):
        candidate = component + "/" + suffix
        if cell_width(candidate) + 2 > width:
            break
        suffix = candidate
    if cell_width(suffix) + 2 <= width:
        return "…/" + suffix
    # An unusually long basename still keeps its beginning and extension/end.
    clusters = [cluster for _, cluster in _clusters(suffix)]
    left, right = [], []
    occupied = 0
    for cluster in clusters:
        if occupied + cell_width(cluster) > max(0, (width - 1) // 2):
            break
        left.append(cluster)
        occupied += cell_width(cluster)
    occupied = 0
    for cluster in reversed(clusters[len(left):]):
        if occupied + cell_width(cluster) > max(0, width - 1 - cell_width("".join(left))):
            break
        right.append(cluster)
        occupied += cell_width(cluster)
    return "".join(left) + ("…" if width else "") + "".join(reversed(right))


def validate_snapshot(snapshot: dict) -> None:
    if (not isinstance(snapshot, dict) or type(snapshot.get("version")) is not int
            or snapshot["version"] != 1 or snapshot.get("kind") != "comparison"):
        raise terminal.TerminalError("Unsupported comparison snapshot.")
    comparison = snapshot.get("comparison")
    if not isinstance(comparison, dict) or any(not isinstance(comparison.get(k), str) for k in ("name", "question", "actor")):
        raise terminal.TerminalError("Comparison snapshot lacks its saved question and author.")
    records = snapshot.get("records")
    if not isinstance(records, list) or not records:
        raise terminal.TerminalError("Comparison snapshot lacks its identified passages.")
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("requested_id"), str):
            raise terminal.TerminalError("Comparison snapshot contains an unidentified passage.")
        if record.get("state") not in {"live", "retired", "unresolved"}:
            raise terminal.TerminalError("Comparison snapshot contains an invalid passage state.")
        if not isinstance(record.get("plain_text", ""), str):
            raise terminal.TerminalError("Comparison snapshot passage text must be a string.")
        if "presentation_text" in record and not isinstance(record["presentation_text"], str):
            raise terminal.TerminalError("Comparison snapshot display text must be a string.")
        notes = record.get("notes", [])
        if not isinstance(notes, list) or any(not isinstance(note, dict) or not isinstance(note.get("body"), str) for note in notes):
            raise terminal.TerminalError("Comparison snapshot contains invalid annotations.")


def read_selection(mailbox: Path) -> tuple[int, dict]:
    try:
        envelope = json.loads(mailbox.read_text(encoding="utf-8"))
        sequence, snapshot = envelope["sequence"], envelope["request"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("invalid comparison selection sequence")
        validate_snapshot(snapshot)
        return sequence, snapshot
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise terminal.TerminalError(f"Cannot read the comparison selection: {error}") from error


def _source_label(record: dict) -> str:
    if record.get("type") == "file_selection":
        sources = record.get("sources") or [source for member in record.get("members", [])
                                            for source in member.get("sources", [])]
        pages = sorted({source["pdf_page"] for source in sources if isinstance(source.get("pdf_page"), int)})
        printed = list(dict.fromkeys(str(source["printed_page"]) for source in sources
                                     if source.get("printed_page") is not None))
        if pages:
            label = "PDF " + _page_ranges(pages)
            if printed:
                label += " | printed " + _page_ranges(printed)
            return label
        return "No canonical page references available"
    sources = []
    for source in record.get("sources", []):
        printed = source.get("printed_page")
        printed = "unlabelled" if printed is None else str(printed)
        sources.append(f"PDF {source.get('pdf_page', '?')} (printed {printed})")
    return "; ".join(sources) or "No canonical page references available"


def _page_ranges(pages: list) -> str:
    """Keep a whole chapter's contiguous references readable in a short pane."""
    if not pages:
        return ""
    if not all(str(page).isascii() and str(page).isdigit() for page in pages):
        return ", ".join(map(str, pages))
    numbers = sorted({int(page) for page in pages})
    ranges, start, end = [], numbers[0], numbers[0]
    for page in numbers[1:]:
        if page == end + 1:
            end = page
        else:
            ranges.append(str(start) if start == end else f"{start}–{end}")
            start = end = page
    ranges.append(str(start) if start == end else f"{start}–{end}")
    return ", ".join(ranges)


def _note_text(note: dict) -> str:
    actor = note.get("actor") or "unattributed"
    status = str(note.get("status", "unknown")).upper()
    lines = [f"Note {note.get('id', 'unidentified')}",
             f"By {actor} | revision {note.get('revision', '?')} | binding {status}",
             f"Original target {note.get('target_id', 'unknown')}"]
    if note.get("target_heading"):
        lines.insert(0, "Passage: " + str(note["target_heading"]))
    if note.get("target_path"):
        lines.insert(1, "File: " + str(note["target_path"]))
    if note.get("redirect_chain"):
        lines.append("Redirects " + " -> ".join(note["redirect_chain"]))
    if note.get("reference_state") or note.get("revision_audit"):
        lines.append(f"Reference {note.get('reference_state', 'unknown')} | revision history {note.get('revision_audit', 'unknown')}")
    resolved = note.get("resolved_target_id")
    if resolved and resolved != note.get("target_id"):
        lines.append(f"Resolved target {resolved}")
    if note.get("status_reason"):
        lines.append(f"{status}: {note['status_reason']}")
    lines += ["", note["body"]]
    return "\n".join(str(line) for line in lines)


def _reference_details(record: dict) -> str:
    lines = [str(record.get("title") or "Canonical passage"),
             "Requested UUID " + record["requested_id"],
             "Resolved UUID " + str(record.get("target_id") or "unresolved"),
             "Reference state " + record["state"].upper()]
    if record.get("redirect_chain"):
        lines.append("Redirects " + " -> ".join(record["redirect_chain"]))
    if record.get("reason"):
        lines.append(str(record["reason"]))
    attribution = record.get("attribution") or {}
    author = _author_label(attribution)
    lines.append(author)
    if attribution.get("role"):
        lines.append("Attribution role " + str(attribution["role"]))
    lines.append("Location " + str(record.get("path") or record.get("document") or "unavailable"))
    lines.append(_source_label(record))
    lines.append("Transcription " + str(record.get("transcription_status") or "not stated"))
    for field, label in (("content_sha256", "Text SHA256"), ("metadata_sha256", "Metadata SHA256")):
        if record.get(field):
            lines.append(label + " " + str(record[field]))
    return "\n".join(lines)


def card_text(record: dict, mode: str) -> str:
    """Start with readable prose; keep full source identities in the details."""
    file_selection = record.get("type") == "file_selection"
    attribution = record.get("attribution") or {}
    if not attribution and file_selection and record.get("members"):
        attribution = record["members"][0].get("attribution") or {}
    author = ("Multiple contributors; authors identified below"
              if record.get("mixed_attribution") or attribution.get("role") == "mixed_attribution"
              else _author_label(attribution))
    if file_selection:
        metadata = (f"File {record.get('path') or record['requested_id']}\n"
                    f"{len(record.get('members', []))} canonical records in corpus order\n"
                    f"Reference state {record['state'].upper()}\n" + _source_label(record))
        metadata += "\n\n" + "\n\n".join(_reference_details(member) for member in record.get("members", []))
    else:
        metadata = _reference_details(record)
    if mode == "annotations":
        notes = record.get("notes", [])
        if notes:
            content = "\n\n".join(_note_text(note) for note in notes)
        else:
            content = "No saved annotations for this passage."
        return content + "\n\nCanonical reference details\n" + metadata
    else:
        text = (record.get("presentation_text") or record.get("plain_text")
                or "Canonical text unavailable; inspect its reference details below.")
        return author + "\n" + _source_label(record) + "\n\n" + text + "\n\nCanonical reference details\n" + metadata


def _author_label(attribution: dict) -> str:
    author = attribution.get("author") or "unknown"
    if attribution.get("role") in {None, "main_text"}:
        return f"Text by {author}"
    return f"Text by {author} | {attribution['role']}"


def _note_preview(record: dict, width: int) -> list[str]:
    notes = record.get("notes", [])
    if not notes:
        return []
    flagged = [note for note in notes if note.get("status") != "matching"]
    note = flagged[0] if flagged else notes[0]
    count = f"Notes {len(notes)}"
    if flagged:
        count += f" | {len(flagged)} flagged"
    count += " | " + str(note.get("target_heading") or f"by {note.get('actor') or 'unattributed'}")
    body = note["body"].replace("\n", " ")
    if flagged:
        body = str(note.get("status", "unknown")).upper() + ": " + body
    return [_clip(count, width), _clip(body, width)]


class ComparisonView:
    """Presentation state only: pairs, view modes, and per-card scroll anchors."""

    def __init__(self, snapshot: dict):
        validate_snapshot(snapshot)
        self.snapshot = deepcopy(snapshot)
        self.mode = "passages"
        self.pair = 0
        self.focus = 0
        self.offsets: dict[tuple, int] = {}
        self.capacities: dict[tuple, int] = {}
        self._wrapped: dict[tuple, tuple[int, list[WrappedLine]]] = {}
        self._cache: dict[tuple, list[WrappedLine]] = {}
        self._visible: list[tuple] = []

    @property
    def pair_count(self) -> int:
        return (len(self.snapshot["records"]) + 1) // 2

    def _header(self, position: int, width: int) -> list[str]:
        record = self.snapshot["records"][position]
        letter = "A" if position % 2 == 0 else "B"
        title = record.get("title") or "Unavailable passage"
        marker = ">" if position % 2 == self.focus else " "
        if record.get("type") == "file_selection":
            return [_clip(f"{marker} {letter} | {len(record.get('members', []))} records | {title}", width),
                    _short_path(record.get("display_path") or record.get("path") or record["requested_id"], width)]
        return [_clip(f"{marker} {letter} | {record['state'].upper()} | {title}", width),
                *_wrap("UUID " + str(record.get("target_id") or record["requested_id"]), width)]

    def _lines(self, key: tuple, width: int, text: str) -> list[WrappedLine]:
        cached_key = (*key, width)
        if cached_key not in self._cache:
            self._cache[cached_key] = wrap_text(text, width)
        lines = self._cache[cached_key]
        previous = self._wrapped.get(key)
        if previous and previous[0] != width:
            old_lines = previous[1]
            old_offset = min(self.offsets.get(key, 0), len(old_lines) - 1)
            anchor = old_lines[max(0, old_offset)].anchor
            self.offsets[key] = max(0, bisect_right([line.anchor for line in lines], anchor) - 1)
        self._wrapped[key] = width, lines
        return lines

    def _body(self, key: tuple, lines: list[WrappedLine], height: int) -> list[str]:
        self._visible.append(key)
        self.capacities[key] = max(1, height)
        limit = max(0, len(lines) - max(1, height))
        offset = min(limit, max(0, self.offsets.get(key, 0)))
        self.offsets[key] = offset
        text = [line.text for line in lines[offset:offset + height]]
        return text + [""] * max(0, height - len(text))

    def _card(self, position: int, width: int, height: int, header_height: int | None = None,
              show_preview: bool = True) -> list[str]:
        record = self.snapshot["records"][position]
        header = self._header(position, width)
        if header_height is not None:
            header += [""] * (header_height - len(header))
        preview = _note_preview(record, width) if self.mode == "passages" and show_preview else []
        key = (self.mode, self.pair, position)
        text = card_text(record, self.mode)
        if self.snapshot.get("reopen_command"):
            text += "\n\nReopen in reader: " + self.snapshot["reopen_command"]
        body = self._lines(key, width, text)
        content_height = max(0, height - len(header) - len(preview))
        return header + self._body(key, body, content_height) + preview

    def _stacked_minimum(self, position: int, width: int) -> int:
        record = self.snapshot["records"][position]
        if self.mode == "passages":
            # Author/page lines, initial heading and spacing should not consume
            # the whole card: leave enough lines to begin the actual argument.
            introduction = card_text(record, self.mode).split("\n\n", 1)[0] + "\n"
            body = len(wrap_text(introduction, width)) + 6
            preview = len(_note_preview(record, width))
        else:
            body, preview = 8, 0
        return len(self._header(position, width)) + preview + body

    def _focused_cards(self, positions: list[int], width: int, height: int) -> list[str]:
        selected = positions[self.focus]
        other = positions[1 - self.focus]
        record = self.snapshot["records"][other]
        letter = "A" if other % 2 == 0 else "B"
        ending = f" | {letter.lower()} to read"
        identity = record.get("display_path") or record.get("path") or record.get("title") or record["requested_id"]
        other_header = letter + ": " + _short_path(str(identity), max(1, width - 3 - cell_width(ending))) + ending
        if height < len(self._header(selected, width)) + 3:
            return [_clip("Enlarge this pane to read the selected passage.", width)]
        # Notes remain one Tab away; suppress their preview to give the focused
        # text the available height in a short, narrow pane.
        return [_clip(other_header, width)] + self._card(selected, width, height - 1, show_preview=False)

    def frame(self, columns: int, rows: int, error: str = "") -> list[str]:
        width = max(0, columns - 1)
        self._visible = []
        if columns < 24 or rows < 16:
            return [_clip("Enlarge the comparison pane; q closes.", width)] + [""] * max(0, rows - 1)
        comparison = self.snapshot["comparison"]
        name, question = comparison["name"], comparison["question"]
        workspace = self.snapshot.get("workspace", {}).get("name", "unknown")
        heading = f"COMPARISON {name}"
        if comparison["actor"]:
            heading += f" | by {comparison['actor']}"
        if workspace:
            heading += f" | workspace {workspace}"
        header = [_clip(heading, width)]
        if question:
            question_lines = _wrap("Question: " + question, width)
            header += question_lines[:2]
            if len(question_lines) > 2:
                header.append("Tab: full saved question")
        header.append(_clip(f"Pair {self.pair + 1}/{self.pair_count} | {self.mode} | {'AB'[self.focus]} selected", width))
        if error:
            header += _wrap("Refresh failed: " + error, width)[:2]
        refresh_command = self.snapshot.get("refresh_command") or "compare open " + shlex.quote(name)
        footer = _wrap("a/b select | arrows scroll | PgUp/PgDn | n/p pair | Tab view | q close", width)
        footer += _wrap("q returns to your shell; rerun sol compare to refresh" if self.snapshot.get("terminal_mode") == "foreground"
                        else "Refresh in reader: " + refresh_command, width)
        positions = list(range(self.pair * 2, min(len(self.snapshot["records"]), self.pair * 2 + 2)))
        available = rows - len(header) - len(footer)
        wide = len(positions) == 2 and columns >= 72
        if self.mode == "question":
            identities = []
            for position in positions:
                identities += self._header(position, width)
            content_height = available - len(identities)
            if content_height < 2:
                content = [_clip("Enlarge this pane to read the comparison.", width)]
            else:
                basis = ("Text basis: current canonical text at capture; file paths select canonical records, not historical excerpts."
                         if any(record.get('type') == 'file_selection' for record in self.snapshot['records'])
                         else "Text basis: current canonical text at capture; the saved comparison stores UUIDs, not historical excerpts.")
                question_heading = f"Question by {comparison['actor']}" if comparison['actor'] else "Question"
                text = (f"{question_heading}\n\n{question}\n\n"
                        f"Comparison {name}\nWorkspace {workspace}\nCaptured {self.snapshot.get('captured_at', 'unknown')}\n"
                        f"{basis}\n"
                        f"Refresh in reader: {refresh_command}\n"
                        f"Reopen: {self.snapshot.get('reopen_command') or refresh_command}")
                key = ("question", -1, -1)
                lines = self._lines(key, width, text)
                content = identities + self._body(key, lines, content_height)
        elif wide:
            left_width = (width - 3) // 2
            right_width = width - 3 - left_width
            header_height = max(len(self._header(positions[0], left_width)), len(self._header(positions[1], right_width)))
            previews = [_note_preview(self.snapshot['records'][position], card_width) if self.mode == 'passages' else []
                        for position, card_width in zip(positions, (left_width, right_width))]
            needed = header_height + max(map(len, previews)) + 2
            if available < needed:
                content = [_clip("Enlarge this pane to read both passages.", width)]
            else:
                left = self._card(positions[0], left_width, available, header_height)
                right = self._card(positions[1], right_width, available, header_height)
                content = [a + " " * (left_width - cell_width(a)) + " │ " + b for a, b in zip(left, right)]
        elif len(positions) == 2:
            heights = [(available - 1) // 2, available - 1 - (available - 1) // 2]
            needed = [self._stacked_minimum(position, width) for position in positions]
            if any(height < minimum for height, minimum in zip(heights, needed)):
                content = self._focused_cards(positions, width, available)
            else:
                content = self._card(positions[0], width, heights[0]) + ["─" * width] + self._card(positions[1], width, heights[1])
        else:
            position = positions[0]
            needed = len(self._header(position, width)) + (len(_note_preview(self.snapshot['records'][position], width))
                     if self.mode == "passages" else 0) + 2
            if available < needed:
                content = [_clip("Enlarge this pane to read the passage.", width)]
            else:
                content = self._card(position, width, available)
        content += [""] * max(0, available - len(content))
        return (header + content[:max(0, available)] + footer)[:rows]

    def action(self, action: str) -> bool:
        if action == "toggle":
            modes = _MODES if self.snapshot['comparison']['question'] else _MODES[:2]
            self.mode = modes[(modes.index(self.mode) + 1) % len(modes)]
            return True
        if action in {'select_a', 'select_b'}:
            candidate = 0 if action == 'select_a' else 1
            if self.pair * 2 + candidate < len(self.snapshot['records']):
                self.focus = candidate
            return True
        if action in {"next", "previous"}:
            self.pair = min(self.pair_count - 1, max(0, self.pair + (1 if action == "next" else -1)))
            if self.pair * 2 + self.focus >= len(self.snapshot['records']):
                self.focus = 0
            return True
        if action in {"up", "down", "page_up", "page_down", "home", "end"}:
            for key in self._visible:
                if key[0] != 'question' and key[2] % 2 != self.focus:
                    continue
                if action == "home":
                    self.offsets[key] = 0
                elif action == "end":
                    self.offsets[key] = len(self._wrapped[key][1])
                else:
                    step = max(1, self.capacities.get(key, 1) - 1) if action.startswith("page_") else 1
                    direction = -1 if action in {"up", "page_up"} else 1
                    self.offsets[key] = max(0, self.offsets.get(key, 0) + direction * step)
            return True
        return False


def key_action(data: bytes) -> str | None:
    keys = {
        b"q": "close", b"Q": "close", b"\x03": "close", b"\x04": "close",
        b"\t": "toggle", b"n": "next", b"p": "previous", b"\x1b[C": "next", b"\x1b[D": "previous",
        b"a": "select_a", b"A": "select_a", b"b": "select_b", b"B": "select_b",
        b"j": "down", b"k": "up", b"\x1b[B": "down", b"\x1b[A": "up",
        b"\x1b[6~": "page_down", b"\x1b[5~": "page_up", b" ": "page_down",
        b"g": "home", b"G": "end", b"\x1b[H": "home", b"\x1b[F": "end",
        b"\x1b[1~": "home", b"\x1b[4~": "end",
    }
    return keys.get(data)


def draw_frame(output, frame: list[str]) -> None:
    output.write("\x1b[2J\x1b[H")
    for row, line in enumerate(frame, 1):
        output.write(f"\x1b[{row};1H" + line)
    output.flush()


def viewer_main(mailbox: Path) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise terminal.TerminalError("The comparison viewer requires an interactive terminal.")
    for name in ("KITTY_LISTEN_ON", "KITTY_RC_PASSWORD", "SOL_KITTY_SESSION"):
        os.environ.pop(name, None)
    sequence, snapshot = read_selection(mailbox)
    view = ComparisonView(snapshot)
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    previous_handlers = {}
    terminating = False
    pending_keys = b""
    signature = None
    old_size = None
    dirty, error = True, ""

    def stop(_signum, _frame):
        nonlocal terminating
        terminating = True

    try:
        for signum in (signal.SIGTERM, signal.SIGHUP):
            previous_handlers[signum] = signal.signal(signum, stop)
        tty.setraw(fd)
        sys.stdout.write(terminal.ENTER)
        sys.stdout.flush()
        while not terminating:
            try:
                stat = mailbox.stat()
            except FileNotFoundError:
                break
            current_signature = (stat.st_ino, stat.st_mtime_ns, stat.st_size)
            if current_signature != signature:
                signature = current_signature
                try:
                    next_sequence, next_snapshot = read_selection(mailbox)
                    if next_sequence != sequence:
                        sequence, view = next_sequence, ComparisonView(next_snapshot)
                        error, dirty = "", True
                except (OSError, terminal.TerminalError) as failure:
                    error, dirty = str(failure), True
            size = terminal.window_size(fd)
            if size != old_size:
                old_size, dirty = size, True
            if dirty:
                draw_frame(sys.stdout, view.frame(size.columns, size.rows, error))
                dirty = False
            readable, _, _ = select.select([fd], [], [], .15)
            if readable:
                data = os.read(fd, 64)
                if not data:
                    break
                actions, pending_keys = terminal.consume_keys(pending_keys + data, key_action)
                for action in actions:
                    if action == "close":
                        terminating = True
                        break
                    dirty = view.action(action) or dirty
    finally:
        try:
            sys.stdout.write("\x1b[0m" + terminal.LEAVE)
            sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, original)
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
    return 0
