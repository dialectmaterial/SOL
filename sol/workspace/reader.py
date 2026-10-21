"""Interface-independent bridges between a verified book and a local workspace.

No PDF extraction, canonical edits, host-shell execution, or UI frameworks live
here. Saved references retain their original UUID even when a retirement redirects
them. Missing references are reported, never reconciled by text similarity.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import textwrap

from sol.core.references import Reference, resolve_reference
from sol.workspace.store import Workspace, WorkspaceError, _position
from sol.terminal.text import safe_output


def workspace_path(name: str, directory: Path | None = None) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("workspace name must contain 1–64 letters, numbers, underscores or hyphens")
    if directory is None:
        configured = os.environ.get("XDG_DATA_HOME")
        if configured and not Path(configured).is_absolute():
            raise ValueError("XDG_DATA_HOME must be an absolute directory")
        directory = (Path(configured) if configured else Path.home() / ".local" / "share") / "sol" / "workspaces"
    return directory.expanduser().resolve() / (name + ".sqlite3")


@dataclass(frozen=True)
class AnnotationEdit:
    """A captured note and source version; not an authority to edit the book."""
    identifier: str
    revision: int
    actor: str
    requested_target: str
    resolved_target: str
    inspected_digest: str
    body: str




def render_review_queue(rows, width=80):
    lines = ["CANONICAL SOURCE-REVIEW QUEUE — loaded snapshot; testimony does not clear flags"]
    if not rows:
        lines.append("(none)")
    for row in rows:
        lines.extend(["", row['id'], f"{row['type']} | {row['transcription_status']}",
                      row['heading'] or "[no title]", row['path'] or "[no reader path]",
                      "Attribution: " + json.dumps(row['attribution'], ensure_ascii=False),
                      "Sources: " + json.dumps(row['sources'], ensure_ascii=False),
                      "Latest reader testimony: " + json.dumps(row['latest_review'], ensure_ascii=False)])
    return safe_output("\n".join(textwrap.fill(line, width=width, break_on_hyphens=False) if line else ""
                                 for line in lines))


class WorkspaceReader:
    def __init__(self, book, store: Workspace, actor: str | None,
                 resolve_path, display_path, render_passage, width=80, plain=False, color=False):
        self.book, self.store, self.actor = book, store, actor
        self.resolve_path, self.display_path = resolve_path, display_path
        self.render_passage = render_passage
        self.width, self.plain, self.color = width, plain, color
        state = store.get_state()
        self.revision = state["revision"] if state else None
        self._saved_state = self._state_values(state) if state else None
        self.resumed_reference: Reference | None = None

    @staticmethod
    def _state_values(state):
        values = {field: state[field] for field in ("cwd", "scope", "current_id", "previous_cwd")}
        if state.get("position") is not None:
            values["position"] = dict(state["position"])
        return values

    def _capture_position(self, session):
        passage = session.current()
        record = self.book.canonical_records.get(passage.identifier)
        if not isinstance(record, dict) or not isinstance(record.get("markdown"), str) or \
                record.get("plain_text") != passage.text:
            raise WorkspaceError("reading position cannot be bound to the current canonical passage")
        if hashlib.sha256(record["markdown"].encode("utf-8")).hexdigest() != record.get("content_sha256"):
            raise WorkspaceError("reading position canonical text fingerprint is inconsistent")
        return _position({
            "target_id": passage.identifier,
            "content_sha256": record["content_sha256"],
            "plain_text_sha256": hashlib.sha256(passage.text.encode("utf-8")).hexdigest(),
            "plain_text_length": len(passage.text),
            "cursor_offset": getattr(session, "cursor_offset", 0),
            "viewport_offset": getattr(session, "viewport_offset", None),
        })

    def _restore_position(self, state, passage, messages):
        position = state.get("position")
        if self.store.schema_version < 3:
            messages.append("This older workspace retains passages, not cursor positions. "
                            "Use sol --workspace NAME --workspace-upgrade FILE.sqlite3 to create a version-3 copy; "
                            "the original is retained.")
            return 0, None, False
        if position is None:
            return 0, None, False
        position = _position(position)
        record = self.book.canonical_records.get(passage.identifier, {})
        current_plain = hashlib.sha256(passage.text.encode("utf-8")).hexdigest()
        if (position["target_id"] != passage.identifier
                or position["content_sha256"] != record.get("content_sha256")
                or position["plain_text_sha256"] != current_plain
                or position["plain_text_length"] != len(passage.text)):
            messages.append("Saved cursor text binding changed; resumed the identified passage "
                            "at its beginning without reusing the old offset.")
            return 0, None, False
        return position["cursor_offset"], position["viewport_offset"], True

    def require_author(self):
        if not self.actor:
            raise ValueError("this authored write requires --actor NAME when starting SOL")
        self.ensure_corpus_current()

    def corpus_freshness(self):
        snapshot = self.book.corpus_snapshot
        if snapshot is None:
            return {"state": "unknown", "reason": "no filesystem generation was retained"}
        from sol.corpus.contract import CorpusError, verify_snapshot_current
        try:
            verify_snapshot_current(snapshot)
        except CorpusError as error:
            return {"state": "changed", "reason": str(error)}
        return {"state": "current", "index_sha256": snapshot.index_sha256}

    def ensure_corpus_current(self):
        freshness = self.corpus_freshness()
        if freshness["state"] == "changed":
            raise WorkspaceError("the loaded corpus changed on disk; the requested record/checkpoint was not written. "
                                 "Reindex if necessary, then reopen SOL before continuing. " + freshness["reason"])

    def health(self):
        from sol.workspace.diagnostics import workspace_health
        report = workspace_health(self.book, self.store.export())
        report["corpus_freshness"] = self.corpus_freshness()
        if report["corpus_freshness"]["state"] == "changed":
            report["status"] = "attention_required"
        return report

    def export_text(self, format='json', *, include_passages=False):
        """One read snapshot, with no checkpoint, source-file or authored writes."""
        if format not in {'json', 'markdown'}:
            raise ValueError('workspace export format must be json or markdown')
        if type(include_passages) is not bool:
            raise ValueError('include-passages must be a boolean')
        if include_passages and format != 'markdown':
            raise ValueError('--include-passages requires a Markdown export')
        snapshot = self.store.export()
        if format == 'json':
            return json.dumps(snapshot, ensure_ascii=False, indent=2)
        from sol.workspace.export import render_workspace_markdown
        return render_workspace_markdown(self.book, snapshot, workspace_name=self.store.path.stem,
                                         include_passages=include_passages, freshness=self.corpus_freshness())

    def render_health(self, report):
        counts = report["counts"]
        lines = ["WORKSPACE REFERENCE HEALTH — not source verification",
                 f"Corpus: {report['corpus_id']}",
                 f"Loaded generation: {report['corpus_freshness']['state']}",
                 "Counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()),
                 "Review binding: text and manifest-declared PDF fingerprints only; record metadata is not bound.",
                 "Basis: one workspace snapshot and the loaded corpus; no repairs are performed."]
        if report["corpus_freshness"].get("reason"):
            lines.append(report["corpus_freshness"]["reason"])
        for issue in report["issues"]:
            lines.extend(["", f"{issue.get('label') or issue['kind']} — {issue['state']}",
                          f"Record: {issue['record_id']}", f"Target: {issue['target_id']}", issue['reason']])
            reference = issue.get("reference")
            if reference and reference.get("state") == "retired":
                lines.append("Redirect: " + " -> ".join(reference['redirect_chain']))
        if not report["issues"]:
            lines.append("No saved-reference issues detected in this snapshot.")
        return safe_output(self.wrap("\n".join(lines)))

    def current_reference(self, session, identifier=None):
        return resolve_reference(self.book, session.current().identifier if identifier is None else identifier)

    def queue(self, within=None, limit=20):
        from sol.workspace.diagnostics import review_queue
        return review_queue(self.book, self.store.export(), within, limit)

    def render_queue(self, rows):
        return render_review_queue(rows, self.width)

    def restore(self, session, historical_revision=None):
        self.ensure_corpus_current()
        latest = self.store.get_state()
        if latest is None:
            raise ValueError("workspace has no saved reading checkpoint; use first, read, or open")
        state = latest if historical_revision is None else self.store.get_history(historical_revision)
        if state is None:
            raise ValueError("no saved checkpoint with that revision")
        current = state["current_id"]
        if current is None:
            raise ValueError("workspace has no saved passage; use first, read, or open")
        # Resolve everything before mutating the live session.
        reference = resolve_reference(self.book, current)
        passage = self.book.find_passage(reference.target_id)
        messages = []
        try:
            _, scope = self.resolve_path(state["scope"], (), self.book.root)
            matches = self.book.selection(scope)
            if passage not in matches:
                raise ValueError("passage is no longer in the saved scope")
        except ValueError:
            scope = passage.path
            matches = self.book.selection(scope)
            messages.append("Saved scope changed; resumed the identified passage in its current file.")
        try:
            node, cwd = self.resolve_path(state["cwd"], (), self.book.root)
            if not node.is_directory:
                raise ValueError("not a directory")
        except ValueError:
            cwd = ()
            messages.append("Saved browsing directory no longer exists; browsing starts at root.")
        previous = None
        if state["previous_cwd"]:
            try:
                node, candidate = self.resolve_path(state["previous_cwd"], (), self.book.root)
                if node.is_directory:
                    previous = candidate
            except ValueError:
                pass
        cursor = next(i for i, item in enumerate(matches) if item.identifier == passage.identifier)
        cursor_offset, viewport_offset, position_valid = self._restore_position(state, passage, messages)
        revision = latest["revision"]
        restored_state = {
            "cwd": self.display_path(cwd), "scope": self.display_path(scope),
            "current_id": reference.requested_id,
            "previous_cwd": self.display_path(previous) if previous is not None else None,
        }
        if position_valid:
            # A historical visit must not carry a stale binding into a new audit
            # entry. Absence after invalidation deliberately means passage start.
            restored_state["position"] = dict(state["position"])
        if historical_revision is not None:
            # A historical visit becomes a new checkpoint, not a rollback of audit
            # history. Save before changing the live cursor; CAS detects races.
            revision = self.store.save_state(restored_state, expected_revision=latest["revision"])
            messages.append(f"Restored checkpoint {historical_revision} as new revision {revision}.")
        session.path, session.cursor = scope, cursor
        session.cursor_offset, session.viewport_offset = cursor_offset, viewport_offset
        self.resumed_reference = reference
        self.revision = revision
        self._saved_state = restored_state if historical_revision is not None else self._state_values(latest)
        if len(reference.chain) > 1:
            messages.append("Retired reference: " + " -> ".join(reference.chain))
        return cwd, previous, passage, "\n".join(messages)

    def _checkpoint_values(self, session, cwd, previous):
        identifier = session.current().identifier
        if self.resumed_reference and self.resumed_reference.target_id == identifier:
            identifier = self.resumed_reference.requested_id
        values = {
            "cwd": self.display_path(cwd), "scope": self.display_path(session.path),
            "current_id": identifier,
            "previous_cwd": self.display_path(previous) if previous is not None else None,
        }
        if self.store.schema_version >= 3:
            values["position"] = self._capture_position(session)
        return values

    def checkpoint(self, session, cwd, previous):
        if session.cursor is None:
            # Browsing alone must not replace an unresolved/absent reading position.
            return
        self.ensure_corpus_current()
        values = self._checkpoint_values(session, cwd, previous)
        self.revision = self.store.save_state(values, expected_revision=self.revision)
        self._saved_state = values
        if self.resumed_reference and self.resumed_reference.target_id != session.current().identifier:
            self.resumed_reference = None

    def save_position(self, session, cwd, previous):
        """Persist changed semantic position only; never write per cursor key."""
        if session.cursor is None:
            return ""
        if self.store.schema_version < 3:
            return ("Cursor position was not saved: this older workspace retains passages only. "
                    "Use sol --workspace NAME --workspace-upgrade FILE.sqlite3 to create a version-3 copy.")
        values = self._checkpoint_values(session, cwd, previous)
        if values == self._saved_state:
            return ""
        self.ensure_corpus_current()
        self.revision = self.store.save_state(values, expected_revision=self.revision)
        self._saved_state = values
        return ""

    def describe(self, identifier):
        if identifier is None:
            return "[no saved passage]"
        try:
            reference = resolve_reference(self.book, identifier)
            record = reference.record
            title = record.get("reader_title") or record.get("title") or record.get("type")
            path = record.get("reader_path") or record.get("path") or "[no reader path]"
            text = f"{identifier}\n  {title} | {path}"
            if len(reference.chain) > 1:
                text += "\n  Retired reference: " + " -> ".join(reference.chain)
            return text
        except ValueError as error:
            return f"{identifier}\n  [unresolved: {error}]"

    def authored(self, record):
        return f"By {record['actor']} | {record['created_at']}"

    def prepare_annotation_edit(self, identifier):
        self.require_author()
        if self.store.schema_version < 2:
            raise ValueError("annotation editing needs workspace version 2. "
                             "Use sol --workspace NAME --workspace-upgrade FILE.sqlite3 to create an upgraded copy; "
                             "the original is retained.")
        record = self.store.get_annotation(identifier)
        if record is None:
            raise ValueError("no annotation with that ID")
        if record['actor'] != self.actor or self.store.actor != self.actor:
            raise ValueError("annotation belongs to another actor; choose its original author to edit it")
        reference = resolve_reference(self.book, record['target_id'])
        return AnnotationEdit(record['id'], record['revision'], self.actor, record['target_id'],
                              reference.target_id, reference.record['content_sha256'], record['body'])

    def save_annotation_edit(self, captured, body, *, expected_revision=None):
        self.require_author()
        if self.actor != captured.actor or self.store.actor != captured.actor:
            raise ValueError("annotation actor changed while editing; nothing was saved")
        reference = resolve_reference(self.book, captured.requested_target)
        if reference.target_id != captured.resolved_target or \
                reference.record['content_sha256'] != captured.inspected_digest:
            raise ValueError("annotation source target changed while editing; nothing was saved")
        # Do not rebind the note's original source digest just because its wording
        # changes. A newly inspected canonical version is not old-note provenance.
        return self.store.update_annotation(captured.identifier, body,
                                            expected_revision=captured.revision if expected_revision is None
                                            else expected_revision)

    def annotation_edit_result(self, before_revision, record):
        label = "Annotation unchanged" if before_revision == record['revision'] else "Personal annotation revised"
        return (f"{label}: {record['id']} | revision {record['revision']}\n"
                f"{self.authored(record)}\nOriginal target and source binding retained.")

    def _list(self, title, lines):
        return title + "\n" + ("\n\n".join(lines) if lines else "(none)")

    def wrap(self, text):
        return "\n".join(textwrap.fill(line, width=self.width, break_on_hyphens=False)
                         if line.strip() else "" for line in text.splitlines())

    def review_view(self, reference):
        record = reference.record
        source = self.book.corpus_manifest.get("source", {})
        attribution = record["attribution"]
        freshness = self.corpus_freshness()
        lines = ["SOURCE REVIEW — inspection only", self.describe(reference.requested_id),
                 f"Loaded canonical generation: {freshness['state']}",
                 "Generation checks cover manifest, index and Markdown; not PDF/image bytes.",
                 f"Document: {record['document']}",
                 f"Attribution: {attribution['author']} | {attribution['role']} | {attribution['status']}",
                 f"Transcription: {record.get('transcription_status', 'not stated')}",
                 f"Content SHA256: {record['content_sha256']}",
                 f"Declared source SHA256: {source.get('sha256', 'not stated')}",
                 "Edition: " + json.dumps(self.book.corpus_manifest.get("edition", {}), ensure_ascii=False, indent=2),
                 "Sources: " + json.dumps(record["sources"], ensure_ascii=False, indent=2),
                 "Note links: " + ", ".join(record.get("note_ids", [])), "", "Canonical Markdown:",
                 record["markdown"], "", "Viewing this record does not verify its PDF transcription."]
        if freshness["state"] == "changed":
            lines.insert(2, "WARNING: the corpus changed on disk; this is the previously loaded record.")
        return "\n".join(lines)

    def save_bookmark(self, name, session, identifier=None, *, replace=False):
        self.ensure_corpus_current()
        ref = self.current_reference(session, identifier)
        self.book.find_passage(ref.target_id)
        self.store.set_bookmark(name, ref.requested_id, replace=replace)
        return ref

    def remove_bookmark(self, name):
        self.ensure_corpus_current()
        self.store.delete_bookmark(name)

    def add_annotation(self, body, session, identifier=None):
        self.require_author()
        ref = self.current_reference(session, identifier)
        return self.store.add_annotation(ref.requested_id, body, ref.record["content_sha256"])
