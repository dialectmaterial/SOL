"""Interface-independent bridges between a verified book and a local workspace.

No PDF extraction, canonical edits, host-shell execution, or UI frameworks live
here. Saved references retain their original UUID even when a retirement redirects
them. Missing references are reported, never reconciled by text similarity.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import textwrap
import unicodedata

from sol.workspace.store import Workspace, WorkspaceError


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
class Reference:
    requested_id: str
    target_id: str
    record: dict
    chain: tuple[str, ...]


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


def safe_output(text: str) -> str:
    """Show literal source/user text without terminal control-code injection."""
    result = []
    for character in text:
        if unicodedata.bidirectional(character) in {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}:
            result.append(f"\\u{ord(character):04x}")
        elif character not in "\n\t" and (ord(character) < 32 or 127 <= ord(character) <= 159):
            result.append(f"\\x{ord(character):02x}")
        else:
            result.append(character)
    return "".join(result)


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


class CommandParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


@dataclass
class CommandResult:
    text: str = ""
    open_id: str | None = None


WORKSPACE_COMMANDS = {"workspace", "bookmark", "note", "compare", "review", "relate"}
WORKSPACE_HELP = """workspace                         workspace identity and storage location
workspace export / check          portable JSON / reference health report
workspace export --format markdown [--include-passages]
                                  readable inquiry; current excerpts are optional
workspace backup FILE.sqlite3     create a verified, non-overwriting backup
workspace upgrade FILE.sqlite3    upgrade an older workspace into a separate copy
workspace history --limit N       recent reading checkpoints (default 20)
resume [REVISION]                 latest position / historical position as new visit
bookmark add NAME [ID]             save current passage or explicit record
bookmark set NAME [ID]             explicitly replace a bookmark
bookmark list / open NAME / remove NAME
note add TEXT [--on ID]            attributed personal annotation
note draft [--on ID]               multiline note (enhanced prompt; Ctrl-S saves)
note list [--on ID] / show NOTE_ID
note edit NOTE_ID [TEXT --expect-revision N]
                                  edit own note; omit TEXT for enhanced editor
note history NOTE_ID              inspect preserved note revisions
compare save NAME ID ID... --question TEXT
compare list / show NAME           saved, ordered passage comparison
review show [ID]                   canonical Markdown and source provenance
review record OUTCOME --issue TEXT [--on ID]
review list [--on ID]              version-aware reader review testimony
review queue [--within PATH] --limit N
                                  canonical pending flags, independent of testimony
relate add ID KIND ID --reason TEXT
relate list [--on ID]              attributed directed relations
Authored writes require an actor chosen at setup or with --actor NAME.
Review outcomes: inspected, correction_needed, verified. No corpus edits occur."""


class WorkspaceReader:
    def __init__(self, book, store: Workspace, actor: str | None,
                 resolve_path, display_path, render_passage, width=80, plain=False, color=False):
        self.book, self.store, self.actor = book, store, actor
        self.resolve_path, self.display_path = resolve_path, display_path
        self.render_passage = render_passage
        self.width, self.plain, self.color = width, plain, color
        state = store.get_state()
        self.revision = state["revision"] if state else None
        self.resumed_reference: Reference | None = None

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
        revision = latest["revision"]
        if historical_revision is not None:
            # A historical visit becomes a new checkpoint, not a rollback of audit
            # history. Save before changing the live cursor; CAS detects races.
            revision = self.store.save_state({
                "cwd": self.display_path(cwd), "scope": self.display_path(scope),
                "current_id": reference.requested_id,
                "previous_cwd": self.display_path(previous) if previous is not None else None,
            }, expected_revision=latest["revision"])
            messages.append(f"Restored checkpoint {historical_revision} as new revision {revision}.")
        session.path, session.cursor = scope, cursor
        self.resumed_reference = reference
        self.revision = revision
        if len(reference.chain) > 1:
            messages.append("Retired reference: " + " -> ".join(reference.chain))
        return cwd, previous, passage, "\n".join(messages)

    def checkpoint(self, session, cwd, previous):
        if session.cursor is None:
            # Browsing alone must not replace an unresolved/absent reading position.
            return
        self.ensure_corpus_current()
        identifier = session.current().identifier
        if self.resumed_reference and self.resumed_reference.target_id == identifier:
            identifier = self.resumed_reference.requested_id
        else:
            self.resumed_reference = None
        self.revision = self.store.save_state({
            "cwd": self.display_path(cwd), "scope": self.display_path(session.path),
            "current_id": identifier,
            "previous_cwd": self.display_path(previous) if previous is not None else None,
        }, expected_revision=self.revision)

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
                             "Use workspace upgrade FILE.sqlite3 to create an upgraded copy; "
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

    def execute(self, verb, arguments, session):
        parser = CommandParser(prog=verb, add_help=False)
        if verb == "workspace":
            parser.add_argument("action", choices=["export", "history", "check", "backup", "upgrade"], nargs="?")
            parser.add_argument("destination", nargs="?", type=Path)
            parser.add_argument("--limit", type=int)
            parser.add_argument("--format", choices=('json', 'markdown'))
            parser.add_argument("--include-passages", action='store_true')
            options = parser.parse_args(arguments)
            if (options.format is not None or options.include_passages) and options.action != 'export':
                raise ValueError('--format and --include-passages are only available for workspace export')
            if options.include_passages and options.format != 'markdown':
                raise ValueError('--include-passages requires workspace export --format markdown')
            if options.action in {"backup", "upgrade"}:
                if options.destination is None or options.limit is not None:
                    raise ValueError(f"workspace {options.action} requires FILE.sqlite3 and does not accept --limit")
                if options.action == "upgrade":
                    self.ensure_corpus_current()
                    requested = options.destination.expanduser().absolute()
                    if requested.name != workspace_path(requested.stem, requested.parent).name:
                        raise ValueError("an upgraded workspace filename must end in lowercase .sqlite3 "
                                         "so reopening its workspace name selects the same file")
                    destination = self.store.upgrade_copy(requested)
                    return CommandResult(f"Verified upgraded copy: {destination}\n"
                                         "Original workspace retained; this session still uses the original.\n"
                                         f"Reopen with --workspace {shlex.quote(destination.stem)} "
                                         f"--workspace-dir {shlex.quote(str(destination.parent))}.")
                return CommandResult(f"Verified workspace backup: {self.store.backup(options.destination)}")
            if options.destination is not None or (options.limit is not None and options.action != "history"):
                raise ValueError("only backup/upgrade accept a destination; only history accepts --limit")
            if options.action == "export":
                return CommandResult(self.export_text(options.format or 'json',
                                                      include_passages=options.include_passages))
            if options.action == "check":
                return CommandResult(self.render_health(self.health()))
            if options.action == "history":
                return CommandResult(self._list("READING CHECKPOINTS — visits, not completion claims", [
                    f"Revision {r['revision']} | {r['created_at']}\n{self.describe(r['current_id'])}\n"
                    f"Scope: {r['scope']} | browsing: {r['cwd']}"
                    for r in self.store.list_history(20 if options.limit is None else options.limit)]))
            return CommandResult(f"Workspace: {self.store.path}\nCorpus ID: {self.store.corpus_id}\n"
                                 f"Storage version: {self.store.schema_version}\n"
                                 f"Actor: {self.actor or '[not set; authored writes disabled]'}\n"
                                 f"Checkpoint revision: {self.revision}")
        actions = parser.add_subparsers(dest="action", required=True)
        if verb == "bookmark":
            for action in ("add", "set"):
                sub = actions.add_parser(action, add_help=False)
                sub.add_argument("name")
                sub.add_argument("identifier", nargs="?")
            actions.add_parser("list", add_help=False)
            for action in ("open", "remove"):
                actions.add_parser(action, add_help=False).add_argument("name")
            options = parser.parse_args(arguments)
            if options.action in {"add", "set"}:
                self.ensure_corpus_current()
                ref = self.current_reference(session, options.identifier)
                self.book.find_passage(ref.target_id)
                self.store.set_bookmark(options.name, ref.requested_id, replace=options.action == "set")
                return CommandResult(f"Bookmark {options.name}:\n{self.describe(ref.requested_id)}")
            if options.action == "open":
                record = self.store.get_bookmark(options.name)
                if record is None:
                    raise ValueError("no bookmark with that name")
                ref = resolve_reference(self.book, record["target_id"])
                return CommandResult(self.describe(ref.requested_id), ref.requested_id)
            if options.action == "remove":
                self.ensure_corpus_current()
                self.store.delete_bookmark(options.name)
                return CommandResult("Bookmark removed.")
            return CommandResult(self._list("BOOKMARKS", [f"{r['name']}\n{self.describe(r['target_id'])}"
                                                         for r in self.store.list_bookmarks()]))
        if verb == "note":
            sub = actions.add_parser("add", add_help=False)
            sub.add_argument("body")
            sub.add_argument("--on", dest="identifier")
            actions.add_parser("list", add_help=False).add_argument("--on", dest="identifier")
            actions.add_parser("show", add_help=False).add_argument("identifier")
            actions.add_parser("history", add_help=False).add_argument("identifier")
            sub = actions.add_parser("edit", add_help=False)
            sub.add_argument("identifier")
            sub.add_argument("body", nargs="?")
            sub.add_argument("--expect-revision", type=int)
            options = parser.parse_args(arguments)
            if options.action == "add":
                self.require_author()
                ref = self.current_reference(session, options.identifier)
                record = self.store.add_annotation(ref.requested_id, options.body, ref.record["content_sha256"])
                return CommandResult(f"Personal annotation saved: {record['id']}\n{self.authored(record)}")
            if options.action == "edit":
                if options.body is None:
                    raise ValueError("note edit NOTE_ID needs the enhanced prompt for multiline editing; "
                                     "otherwise use note edit NOTE_ID \"TEXT\" --expect-revision N")
                if options.expect_revision is None or options.expect_revision < 1:
                    raise ValueError("note edit with TEXT requires --expect-revision N from note show NOTE_ID")
                captured = self.prepare_annotation_edit(options.identifier)
                record = self.save_annotation_edit(captured, options.body,
                                                   expected_revision=options.expect_revision)
                return CommandResult(self.annotation_edit_result(captured.revision, record))
            if options.action == "history":
                record = self.store.get_annotation(options.identifier)
                if record is None:
                    raise ValueError("no annotation with that ID")
                rows = self.store.list_annotation_history(options.identifier)
                if self.store.schema_version < 2:
                    return CommandResult("This version-1 workspace has no annotation revision audit.\n"
                                         "Use workspace upgrade FILE.sqlite3 to preserve a baseline in a separate copy.")
                lines = [self.authored(record), self.describe(record['target_id']),
                         "Original source binding: " + str(record['content_sha256'])]
                for row in rows:
                    label = "Baseline from version 1; earlier edits and editor are unknown" \
                        if row['kind'] == 'legacy_baseline' else row['kind']
                    lines.extend(["", f"Revision {row['revision']} | {label}",
                                  f"Recorded: {row['recorded_at']} | Editor: {row['editor'] or '[unknown]'}",
                                  self.wrap(row['body'])])
                return CommandResult("ANNOTATION HISTORY — preserved personal prose\n" + "\n".join(lines))
            if options.action == "show":
                record = self.store.get_annotation(options.identifier)
                if record is None:
                    raise ValueError("no annotation with that ID")
                records = [record]
            else:
                target = self.current_reference(session, options.identifier).requested_id if options.identifier is not None else None
                records = self.store.list_annotations(target)
            lines = []
            for record in records:
                try:
                    changed = resolve_reference(self.book, record['target_id']).record['content_sha256'] != record['content_sha256']
                    status = "[target text changed since annotation]" if changed else ""
                except ValueError:
                    status = "[unresolved target]"
                revision = f"revision {record['revision']}" if record['revision'] is not None else "legacy; no revision audit"
                lines.append(f"{record['id']} | personal_note | {revision} {status}\n{self.authored(record)}\n"
                             f"{self.describe(record['target_id'])}\n\n{self.wrap(record['body'])}")
            return CommandResult(self._list("READER ANNOTATIONS — not edition notes", lines))
        if verb == "compare":
            sub = actions.add_parser("save", add_help=False)
            sub.add_argument("name")
            sub.add_argument("identifiers", nargs="+")
            sub.add_argument("--question", required=True)
            actions.add_parser("list", add_help=False)
            actions.add_parser("show", add_help=False).add_argument("name")
            options = parser.parse_args(arguments)
            if options.action == "save":
                self.require_author()
                if not options.question.strip():
                    raise ValueError("comparison requires a nonempty question")
                refs = [resolve_reference(self.book, value) for value in options.identifiers]
                self.store.save_comparison(options.name, [r.requested_id for r in refs], options.question)
                return CommandResult(f"Comparison saved: {options.name}")
            if options.action == "list":
                return CommandResult(self._list("COMPARISONS", [f"{r['name']} | {self.authored(r)}\n{r['question']}"
                                                               for r in self.store.list_comparisons()]))
            comparison = self.store.get_comparison(options.name)
            if comparison is None:
                raise ValueError("no comparison with that name")
            lines = [f"COMPARISON: {comparison['name']}", self.authored(comparison), comparison['question']]
            for identifier in comparison['target_ids']:
                lines.extend(["", self.describe(identifier)])
                try:
                    ref = resolve_reference(self.book, identifier)
                    passage = self.book.find_passage(ref.target_id)
                    lines.append(self.render_passage(passage, self.width, self.plain, False))
                except ValueError:
                    # Canonical notes/editorial records may also be compared.
                    try:
                        lines.append(resolve_reference(self.book, identifier).record['markdown'])
                    except ValueError:
                        pass
            return CommandResult("\n".join(lines))
        if verb == "review":
            actions.add_parser("show", add_help=False).add_argument("identifier", nargs="?")
            sub = actions.add_parser("record", add_help=False)
            sub.add_argument("outcome", choices=["inspected", "correction_needed", "verified"])
            sub.add_argument("--issue", required=True)
            sub.add_argument("--on", dest="identifier")
            actions.add_parser("list", add_help=False).add_argument("--on", dest="identifier")
            sub = actions.add_parser("queue", add_help=False)
            sub.add_argument("--within")
            sub.add_argument("--limit", type=int, default=20)
            options = parser.parse_args(arguments)
            if options.action == "queue":
                within = None
                if options.within is not None:
                    _, within = self.resolve_path(options.within, (), self.book.root)
                return CommandResult(self.render_queue(self.queue(within, options.limit)))
            if options.action == "show":
                return CommandResult(self.review_view(self.current_reference(session, options.identifier)))
            if options.action == "record":
                self.require_author()
                if not options.issue.strip():
                    raise ValueError("review testimony requires a nonempty issue or inspection description")
                ref = self.current_reference(session, options.identifier)
                source_sha = self.book.corpus_manifest['source']['sha256']
                record = self.store.add_review(ref.requested_id, options.outcome, options.issue,
                                               ref.record['content_sha256'], source_sha)
                return CommandResult(f"Reader review recorded: {record['id']}\n{self.authored(record)}\n"
                                     "Canonical transcription status and random eligibility are unchanged.")
            target = self.current_reference(session, options.identifier).requested_id if options.identifier is not None else None
            lines = []
            for record in self.store.list_reviews(target):
                try:
                    ref = resolve_reference(self.book, record['target_id'])
                    current = (len(ref.chain) == 1 and
                               ref.record['content_sha256'] == record['content_sha256'] and
                               self.book.corpus_manifest['source']['sha256'] == record['source_sha256'])
                    status = ("same text/PDF fingerprints; PDF hash is manifest-declared; record metadata is not bound" if current else
                              "STALE: source/text version or target changed")
                except ValueError:
                    status = "UNRESOLVED target"
                lines.append(f"{record['id']} | {record['outcome']} | {status}\n{self.authored(record)}\n"
                             f"{self.describe(record['target_id'])}\n{record['issue']}")
            return CommandResult(self._list("READER REVIEW TESTIMONY — not canonical verification", lines))
        if verb == "relate":
            sub = actions.add_parser("add", add_help=False)
            sub.add_argument("source")
            sub.add_argument("kind")
            sub.add_argument("target")
            sub.add_argument("--reason", required=True)
            actions.add_parser("list", add_help=False).add_argument("--on", dest="identifier")
            options = parser.parse_args(arguments)
            if options.action == "add":
                self.require_author()
                if not options.reason.strip():
                    raise ValueError("a reader-asserted relation requires a nonempty reason")
                source, target = resolve_reference(self.book, options.source), resolve_reference(self.book, options.target)
                record = self.store.add_relation(source.requested_id, target.requested_id, options.kind, options.reason)
                return CommandResult(f"Reader-asserted relation saved: {record['id']}\n{self.authored(record)}")
            target = self.current_reference(session, options.identifier).requested_id if options.identifier is not None else None
            return CommandResult(self._list("READER-ASSERTED RELATIONS — outside the published tree", [
                f"{r['id']} | {r['kind']}\n{self.authored(r)}\n{self.describe(r['source_id'])}\n"
                f"  -> {self.describe(r['target_id'])}\n{r['rationale']}" for r in self.store.list_relations(target)]))
        raise ValueError("unknown workspace command")
