"""Book-shell syntax and presentation over the workspace service API."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shlex

from sol.core.references import resolve_reference


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
compare PATH_A PATH_B              compare complete files; Tab completes paths
compare open / close              refresh the last desk / close it
compare open NAME                 open a saved passage comparison
review show [ID]                   canonical Markdown and source provenance
review record OUTCOME --issue TEXT [--on ID]
review list [--on ID]              version-aware reader review testimony
review queue [--within PATH] --limit N
                                  canonical pending flags, independent of testimony
relate add ID KIND ID --reason TEXT
relate list [--on ID]              attributed directed relations
Authored writes require an actor chosen at setup or with --actor NAME.
Review outcomes: inspected, correction_needed, verified. No corpus edits occur."""


def execute(reader, verb, arguments, session):
    from sol.workspace.reader import workspace_path

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
                reader.ensure_corpus_current()
                requested = options.destination.expanduser().absolute()
                if requested.name != workspace_path(requested.stem, requested.parent).name:
                    raise ValueError("an upgraded workspace filename must end in lowercase .sqlite3 "
                                     "so reopening its workspace name selects the same file")
                destination = reader.store.upgrade_copy(requested)
                return CommandResult(f"Verified upgraded copy: {destination}\n"
                                     "Original workspace retained; this session still uses the original.\n"
                                     f"Reopen with --workspace {shlex.quote(destination.stem)} "
                                     f"--workspace-dir {shlex.quote(str(destination.parent))}.")
            return CommandResult(f"Verified workspace backup: {reader.store.backup(options.destination)}")
        if options.destination is not None or (options.limit is not None and options.action != "history"):
            raise ValueError("only backup/upgrade accept a destination; only history accepts --limit")
        if options.action == "export":
            return CommandResult(reader.export_text(options.format or 'json',
                                                  include_passages=options.include_passages))
        if options.action == "check":
            return CommandResult(reader.render_health(reader.health()))
        if options.action == "history":
            return CommandResult(reader._list("READING CHECKPOINTS — visits, not completion claims", [
                f"Revision {r['revision']} | {r['created_at']}\n{reader.describe(r['current_id'])}\n"
                f"Scope: {r['scope']} | browsing: {r['cwd']}"
                for r in reader.store.list_history(20 if options.limit is None else options.limit)]))
        return CommandResult(f"Workspace: {reader.store.path}\nCorpus ID: {reader.store.corpus_id}\n"
                             f"Storage version: {reader.store.schema_version}\n"
                             f"Actor: {reader.actor or '[not set; authored writes disabled]'}\n"
                             f"Checkpoint revision: {reader.revision}")
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
            ref = reader.save_bookmark(options.name, session, options.identifier,
                                       replace=options.action == "set")
            return CommandResult(f"Bookmark {options.name}:\n{reader.describe(ref.requested_id)}")
        if options.action == "open":
            record = reader.store.get_bookmark(options.name)
            if record is None:
                raise ValueError("no bookmark with that name")
            ref = resolve_reference(reader.book, record["target_id"])
            return CommandResult(reader.describe(ref.requested_id), ref.requested_id)
        if options.action == "remove":
            reader.remove_bookmark(options.name)
            return CommandResult("Bookmark removed.")
        return CommandResult(reader._list("BOOKMARKS", [f"{r['name']}\n{reader.describe(r['target_id'])}"
                                                     for r in reader.store.list_bookmarks()]))
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
            record = reader.add_annotation(options.body, session, options.identifier)
            return CommandResult(f"Personal annotation saved: {record['id']}\n{reader.authored(record)}")
        if options.action == "edit":
            if options.body is None:
                raise ValueError("note edit NOTE_ID needs the enhanced prompt for multiline editing; "
                                 "otherwise use note edit NOTE_ID \"TEXT\" --expect-revision N")
            if options.expect_revision is None or options.expect_revision < 1:
                raise ValueError("note edit with TEXT requires --expect-revision N from note show NOTE_ID")
            captured = reader.prepare_annotation_edit(options.identifier)
            record = reader.save_annotation_edit(captured, options.body,
                                               expected_revision=options.expect_revision)
            return CommandResult(reader.annotation_edit_result(captured.revision, record))
        if options.action == "history":
            record = reader.store.get_annotation(options.identifier)
            if record is None:
                raise ValueError("no annotation with that ID")
            rows = reader.store.list_annotation_history(options.identifier)
            if reader.store.schema_version < 2:
                return CommandResult("This version-1 workspace has no annotation revision audit.\n"
                                     "Use workspace upgrade FILE.sqlite3 to preserve a baseline in a separate copy.")
            lines = [reader.authored(record), reader.describe(record['target_id']),
                     "Original source binding: " + str(record['content_sha256'])]
            for row in rows:
                label = "Baseline from version 1; earlier edits and editor are unknown" \
                    if row['kind'] == 'legacy_baseline' else row['kind']
                lines.extend(["", f"Revision {row['revision']} | {label}",
                              f"Recorded: {row['recorded_at']} | Editor: {row['editor'] or '[unknown]'}",
                              reader.wrap(row['body'])])
            return CommandResult("ANNOTATION HISTORY — preserved personal prose\n" + "\n".join(lines))
        if options.action == "show":
            record = reader.store.get_annotation(options.identifier)
            if record is None:
                raise ValueError("no annotation with that ID")
            records = [record]
        else:
            target = reader.current_reference(session, options.identifier).requested_id if options.identifier is not None else None
            records = reader.store.list_annotations(target)
        lines = []
        for record in records:
            try:
                changed = resolve_reference(reader.book, record['target_id']).record['content_sha256'] != record['content_sha256']
                status = "[target text changed since annotation]" if changed else ""
            except ValueError:
                status = "[unresolved target]"
            revision = f"revision {record['revision']}" if record['revision'] is not None else "legacy; no revision audit"
            lines.append(f"{record['id']} | personal_note | {revision} {status}\n{reader.authored(record)}\n"
                         f"{reader.describe(record['target_id'])}\n\n{reader.wrap(record['body'])}")
        return CommandResult(reader._list("READER ANNOTATIONS — not edition notes", lines))
    if verb == "compare":
        sub = actions.add_parser("save", add_help=False)
        sub.add_argument("name")
        sub.add_argument("identifiers", nargs="+")
        sub.add_argument("--question", required=True)
        actions.add_parser("list", add_help=False)
        actions.add_parser("show", add_help=False).add_argument("name")
        options = parser.parse_args(arguments)
        if options.action == "save":
            reader.save_comparison(options.name, options.identifiers, options.question)
            return CommandResult(f"Comparison saved: {options.name}")
        if options.action == "list":
            return CommandResult(reader._list("COMPARISONS", [f"{r['name']} | {reader.authored(r)}\n{r['question']}"
                                                           for r in reader.store.list_comparisons()]))
        comparison = reader.store.get_comparison(options.name)
        if comparison is None:
            raise ValueError("no comparison with that name")
        lines = [f"COMPARISON: {comparison['name']}", reader.authored(comparison), comparison['question']]
        for identifier in comparison['target_ids']:
            lines.extend(["", reader.describe(identifier)])
            try:
                ref = resolve_reference(reader.book, identifier)
                passage = reader.book.find_passage(ref.target_id)
                lines.append(reader.render_passage(passage, reader.width, reader.plain, False))
            except ValueError:
                # Canonical notes/editorial records may also be compared.
                try:
                    lines.append(resolve_reference(reader.book, identifier).record['markdown'])
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
                _, within = reader.resolve_path(options.within, (), reader.book.root)
            return CommandResult(reader.render_queue(reader.queue(within, options.limit)))
        if options.action == "show":
            return CommandResult(reader.review_view(reader.current_reference(session, options.identifier)))
        if options.action == "record":
            record = reader.record_review(options.outcome, options.issue, session, options.identifier)
            return CommandResult(f"Reader review recorded: {record['id']}\n{reader.authored(record)}\n"
                                 "Canonical transcription status and random eligibility are unchanged.")
        target = reader.current_reference(session, options.identifier).requested_id if options.identifier is not None else None
        lines = []
        for record in reader.store.list_reviews(target):
            try:
                ref = resolve_reference(reader.book, record['target_id'])
                current = (len(ref.chain) == 1 and
                           ref.record['content_sha256'] == record['content_sha256'] and
                           reader.book.corpus_manifest['source']['sha256'] == record['source_sha256'])
                status = ("same text/PDF fingerprints; PDF hash is manifest-declared; record metadata is not bound" if current else
                          "STALE: source/text version or target changed")
            except ValueError:
                status = "UNRESOLVED target"
            lines.append(f"{record['id']} | {record['outcome']} | {status}\n{reader.authored(record)}\n"
                         f"{reader.describe(record['target_id'])}\n{record['issue']}")
        return CommandResult(reader._list("READER REVIEW TESTIMONY — not canonical verification", lines))
    if verb == "relate":
        sub = actions.add_parser("add", add_help=False)
        sub.add_argument("source")
        sub.add_argument("kind")
        sub.add_argument("target")
        sub.add_argument("--reason", required=True)
        actions.add_parser("list", add_help=False).add_argument("--on", dest="identifier")
        options = parser.parse_args(arguments)
        if options.action == "add":
            record = reader.add_relation(options.source, options.kind, options.target, options.reason)
            return CommandResult(f"Reader-asserted relation saved: {record['id']}\n{reader.authored(record)}")
        target = reader.current_reference(session, options.identifier).requested_id if options.identifier is not None else None
        return CommandResult(reader._list("READER-ASSERTED RELATIONS — outside the published tree", [
            f"{r['id']} | {r['kind']}\n{reader.authored(r)}\n{reader.describe(r['source_id'])}\n"
            f"  -> {reader.describe(r['target_id'])}\n{r['rationale']}" for r in reader.store.list_relations(target)]))
    raise ValueError("unknown workspace command")
