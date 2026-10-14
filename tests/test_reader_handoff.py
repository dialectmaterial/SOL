"""Explicit reader acceptance, using invented indexed text and private workspaces."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol import core
from sol.corpus import contract
from sol.core.paths import display_path, resolve_path
from sol.reader import app
from sol.reader.actions import ReaderActions, ReadingSession
from sol.terminal.handoff import submit_return
from sol.terminal.prompt import CompletionCatalog
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace, WorkspaceConflict
from test_packaging import write_runtime_corpus


SECOND = "cccccccc-0000-4000-8000-000000000003"
RETIRED = "dddddddd-0000-4000-8000-000000000004"
NOTE = "eeeeeeee-0000-4000-8000-000000000005"
GENERATED = {"markdown", "plain_text", "document", "context", "content_sha256"}


class FakePane:
    def __init__(self, failure=None):
        self.failure = failure
        self.directory = None
        self.corpus = None
        self.closed = 0
        self.cleaned = 0

    def show(self, directory, corpus):
        self.directory, self.corpus = directory, corpus
        if self.failure is not None:
            raise self.failure
        return 43

    def close(self):
        self.closed += 1

    def cleanup(self):
        self.cleaned += 1


class ReaderHandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-reader-handoff-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        self.first, _ = write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)

        def extend(manifest, records):
            for identifier, kind, body in (
                (SECOND, "paragraph", "A second invented passage supplies another position for deliberate reading."),
                (RETIRED, "retired_record", "An invented retired passage retains its original identifier."),
                (NOTE, "note", "An invented editorial note is canonical but not a main-text reader passage."),
            ):
                record = deepcopy(records[1])
                record.update(id=identifier, type=kind, order=len(records), markdown=body, plain_text=body)
                if kind == "retired_record":
                    record["redirect_id"] = self.first
                if kind == "note":
                    record["attribution"] = {"author": "Invented editor", "role": "editorial", "status": "declared"}
                records.append(record)

        self.rewrite(extend)
        self.book = app.load_corpus_book(self.corpus)
        self.snapshot = self.book.corpus_snapshot
        self.session = ReadingSession(self.book)
        self.actions = ReaderActions(self.book, session=self.session)
        self.actions.open(self.first)
        self.packet = core.capture_reference(self.snapshot, SECOND)
        self.path = self.root / "workspace.sqlite3"
        self.provenance = {key: self.book.corpus_manifest[key] for key in ("edition", "source")}

    def rewrite(self, change):
        manifest = json.loads((self.corpus / "corpus.json").read_text())
        records = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        change(manifest, records)
        for record in records:
            record["content_sha256"] = sha256(record["markdown"].encode()).hexdigest()
        markdown = "\n".join(contract.render_record(
            {key: value for key, value in row.items() if key not in GENERATED}, row["markdown"])
            for row in records).encode()
        manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode()
        index_bytes = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records).encode()
        (self.corpus / "sample.md").write_bytes(markdown)
        (self.corpus / "corpus.json").write_bytes(manifest_bytes)
        (self.corpus / "index.jsonl").write_bytes(index_bytes)
        (self.corpus / "index.meta.json").write_text(json.dumps({
            "contract_version": 1, "manifest_sha256": sha256(manifest_bytes).hexdigest(),
            "source_sha256": manifest["source"]["sha256"],
            "documents": {"sample.md": sha256(markdown).hexdigest()},
            "index_sha256": sha256(index_bytes).hexdigest(), "record_count": len(records),
        }), encoding="utf-8")

    def workspace(self):
        store = Workspace(self.path, self.book.corpus_manifest["corpus_id"], self.provenance, actor="Ada")
        self.addCleanup(store.close)
        reader = WorkspaceReader(self.book, store, "Ada", resolve_path, display_path, app.render_passage)
        return store, reader

    def state(self, actions=None):
        actions = actions or self.actions
        return (actions.cwd, actions.previous_cwd, actions.session.path, actions.session.cursor,
                actions.current_reference_id(), tuple(actions.results))

    def shell(self, steps, reader=None, pane=None):
        pane = pane or FakePane()
        output = StringIO()
        session = ReadingSession(self.book)
        iterator = iter(steps)

        def read(prompt):
            try:
                step = next(iterator)
            except StopIteration:
                raise EOFError from None
            if callable(step):
                step(session, pane)
                return ""
            return step

        def emit(value="", end="\n"):
            output.write(str(value) + end)

        with patch.object(app, "ReadingSession", return_value=session):
            status = app.run_shell(self.book, 80, workspace_reader=reader,
                                   read_command=read, write_output=emit, essence_pane=pane)
        self.assertEqual(status, 0)
        return output.getvalue(), session, pane

    def propose(self, identifier=SECOND):
        return lambda session, pane: submit_return(pane.directory, self.snapshot, identifier)

    def test_capture_and_inspection_never_checkpoint_or_navigate(self):
        store, reader = self.workspace()
        actions = ReaderActions(self.book, reader)
        actions.open(self.first)
        before, saved = self.state(actions), store.get_state()
        actions.search("invented")
        before = self.state(actions)
        self.assertEqual(actions.capture_active_reference()["reference"]["requested_id"], self.first)
        self.assertEqual(actions.check_return_reference(self.packet).target_id, SECOND)
        self.assertEqual(self.state(actions), before)
        self.assertEqual(store.get_state(), saved)
        self.assertEqual(len(store.list_history()), 1)

    def test_acceptance_is_one_ordinary_guarded_checkpoint(self):
        store, reader = self.workspace()
        actions = ReaderActions(self.book, reader)
        actions.open(self.first)
        self.assertEqual(actions.accept_return_reference(self.packet).identifier, SECOND)
        self.assertEqual(store.get_state()["current_id"], SECOND)
        self.assertEqual(len(store.list_history()), 2)

    def test_concurrent_workspace_change_rolls_back_cursor_and_requested_reference(self):
        store, reader = self.workspace()
        actions = ReaderActions(self.book, reader)
        actions.open(RETIRED)
        before = self.state(actions)
        with Workspace(self.path, self.book.corpus_manifest["corpus_id"], self.provenance, actor="Other") as other:
            newer = other.get_state()
            newer["current_id"] = SECOND
            other.save_state(newer, newer["revision"])
            with self.assertRaises(WorkspaceConflict):
                actions.accept_return_reference(self.packet)
            self.assertEqual(self.state(actions), before)
            self.assertEqual(store.get_state()["current_id"], SECOND)
            self.assertEqual(len(store.list_history()), 2)
            self.assertEqual(reader.resumed_reference.requested_id, RETIRED)

    def test_stale_generation_cannot_be_accepted_and_creates_no_visit(self):
        store, reader = self.workspace()
        actions = ReaderActions(self.book, reader)
        actions.open(self.first)
        before, saved = self.state(actions), store.get_state()
        self.rewrite(lambda manifest, rows: rows[0].update(markdown="# Corrected synthetic section"))
        with self.assertRaises(core.ProtocolError):
            actions.accept_return_reference(self.packet)
        self.assertEqual(self.state(actions), before)
        self.assertEqual(store.get_state(), saved)

    def test_foreign_corpus_or_forged_provenance_never_changes_position(self):
        for mutate in (lambda packet: packet["corpus"].update(id=RETIRED),
                       lambda packet: packet["reference"]["sources"][0].update(printed_page="8")):
            packet = deepcopy(self.packet)
            mutate(packet)
            before = self.state()
            with self.assertRaises(core.ProtocolError):
                self.actions.accept_return_reference(packet)
            self.assertEqual(self.state(), before)

    def test_editorial_record_is_valid_core_data_but_not_a_reader_destination(self):
        packet = core.capture_reference(self.snapshot, NOTE)
        self.assertEqual(core.check_reference(self.snapshot, packet).target_id, NOTE)
        before = self.state()
        with self.assertRaisesRegex(ValueError, "no passage"):
            self.actions.accept_return_reference(packet)
        self.assertEqual(self.state(), before)

    def test_corrupted_reader_projection_is_refused_even_with_a_valid_packet(self):
        original = self.book.passages[1]
        for changes in ({"text": "Not the canonical text"}, {"kind": "formula"},
                        {"path": ("ESSENCE", "synthetic.txt")}, {"pdf_page": 1}, {"printed_page": 8}):
            with self.subTest(changes=changes):
                self.book.passages[1] = replace(original, **changes)
                with self.assertRaisesRegex(ValueError, "projection disagrees"):
                    self.actions.check_return_reference(self.packet)
                self.assertEqual(self.actions.session.current().identifier, self.first)
        self.book.passages[1] = original

    def test_retired_requested_id_is_preserved_without_a_workspace(self):
        self.actions.open(RETIRED[:8])
        self.assertEqual(self.actions.current_reference_id(), RETIRED)
        packet = self.actions.capture_active_reference()
        self.assertEqual(packet["reference"]["chain"], [RETIRED, self.first])
        self.actions.accept_return_reference(packet)
        self.assertEqual(self.actions.current_reference_id(), RETIRED)
        self.actions.move(1)
        self.assertEqual(self.actions.current_reference_id(), SECOND)
        self.assertFalse(self.path.exists())

    def test_legacy_reader_cannot_silently_create_a_corpus_for_handoff(self):
        self.book.corpus_snapshot = None
        with self.assertRaisesRegex(ValueError, "verified canonical corpus"):
            self.actions.capture_active_reference()
        self.assertFalse(self.path.exists())

    def test_ready_return_is_not_automatically_accepted(self):
        store, reader = self.workspace()
        output, session, pane = self.shell(["first", "essence", self.propose(), "essence check"], reader)
        self.assertEqual(session.current().identifier, self.first)
        self.assertEqual(store.get_state()["current_id"], self.first)
        self.assertEqual(len(store.list_history()), 1)
        self.assertIn('"status": "ready"', output)
        self.assertIn("Inspection only", output)
        self.assertEqual(pane.cleaned, 1)
        self.assertFalse(pane.directory.exists())

    def test_shell_accepts_once_then_leaves_native_pane_open_until_explicit_close(self):
        store, reader = self.workspace()

        def accepted(session, pane):
            self.assertEqual(session.current().identifier, SECOND)
            self.assertEqual(store.get_state()["current_id"], SECOND)
            self.assertEqual(len(store.list_history()), 2)
            self.assertEqual(pane.closed, 0)
            self.assertTrue(pane.directory.exists())

        def closed(session, pane):
            self.assertEqual(pane.closed, 1)
            self.assertFalse(pane.directory.exists())
            self.assertEqual(len(store.list_history()), 2)

        output, _, _ = self.shell(["first", "essence open", self.propose(), "essence return", accepted,
                                  "essence return", "essence check", "essence close", closed], reader)
        self.assertIn("already accepted", output)
        self.assertIn('"status": "accepted"', output)
        self.assertIn("Already accepted; finish native work", output)

    def test_local_movement_requires_a_separate_deliberate_acceptance(self):
        def still_second(session, pane):
            self.assertEqual(session.current().identifier, SECOND)

        output, session, _ = self.shell(["first", "essence", self.propose(self.first), "next",
                                        "essence return", still_second, "essence return --accept-move"])
        self.assertIn("reading position changed", output)
        self.assertEqual(session.current().identifier, self.first)
        self.assertFalse(self.path.exists())

    def test_accept_move_cannot_override_a_workspace_conflict(self):
        store, reader = self.workspace()

        def concurrent(session, pane):
            with Workspace(self.path, self.book.corpus_manifest["corpus_id"], self.provenance, actor="Other") as other:
                newer = other.get_state()
                newer["current_id"] = SECOND
                other.save_state(newer, newer["revision"])

        output, session, _ = self.shell(["first", "essence", self.propose(), concurrent,
                                        "essence return --accept-move"], reader)
        self.assertEqual(session.current().identifier, self.first)
        self.assertEqual(store.get_state()["current_id"], SECOND)
        self.assertEqual(len(store.list_history()), 2)
        self.assertIn("sol:", output)
        self.assertNotIn("Return accepted.", output)

    def test_accept_move_cannot_override_changed_canonical_generation(self):
        def changed(session, pane):
            self.rewrite(lambda manifest, rows: rows[0].update(markdown="# Corrected synthetic section"))

        output, session, _ = self.shell(["first", "essence", self.propose(), changed,
                                        "essence return --accept-move"])
        self.assertEqual(session.current().identifier, self.first)
        self.assertIn("sol:", output)
        self.assertNotIn("Return accepted.", output)

    def test_missing_passage_or_pending_return_never_launches_or_navigates(self):
        output, session, pane = self.shell(["essence", "first", "essence", "essence return", "essence check"])
        self.assertIn("no current paragraph", output)
        self.assertIn("No return is ready", output)
        self.assertEqual(session.current().identifier, self.first)
        self.assertFalse(pane.directory.exists())

    def test_invalid_syntax_and_second_exchange_are_controlled(self):
        output, session, pane = self.shell(["essence launch", "essence close --accept-move", "first",
                                          "essence", "essence open", "essence return --unknown"])
        self.assertIn("use essence open", output)
        self.assertIn("unexpected arguments", output)
        self.assertIn("exchange is already active", output)
        self.assertEqual(session.current().identifier, self.first)
        self.assertFalse(pane.directory.exists())

    def test_failed_pane_launch_cleans_its_private_exchange_without_a_visit(self):
        store, reader = self.workspace()
        pane = FakePane(ValueError("Invented missing Kitty session"))
        output, session, _ = self.shell(["first", "essence"], reader, pane)
        self.assertIn("Invented missing Kitty session", output)
        self.assertEqual(session.current().identifier, self.first)
        self.assertEqual(len(store.list_history()), 1)
        self.assertFalse(pane.directory.exists())

    def test_close_and_reopen_creates_another_exchange_not_another_visit(self):
        store, reader = self.workspace()
        origins = []

        def remember(session, pane):
            origins.append(pane.directory)

        output, _, pane = self.shell(["first", "essence", remember, "essence close",
                                     "essence", remember, "essence close"], reader)
        self.assertEqual(len(store.list_history()), 1)
        self.assertNotEqual(origins[0], origins[1])
        self.assertTrue(all(not directory.exists() for directory in origins))
        self.assertEqual(pane.closed, 2)
        self.assertNotIn("sol:", output)

    def test_cleanup_reports_where_unexpected_native_work_was_retained(self):
        retained = []

        def save_work(session, pane):
            work = pane.directory / "personal.txt"
            work.write_text("Invented native work must be preserved")
            retained.append(work)

        try:
            output, _, pane = self.shell(["first", "essence", save_work, "essence close"])
            self.assertIn(str(pane.directory), output)
            self.assertIn("data retained", output)
            self.assertEqual(retained[0].read_text(), "Invented native work must be preserved")
        finally:
            if retained:
                retained[0].rename(self.root / "retained.txt")
                retained[0].parent.rmdir()

    def test_completion_works_without_a_workspace_and_exposes_only_explicit_override(self):
        catalog = CompletionCatalog(self.book)
        self.assertIn("essence", dict(catalog.suggestions("es")))
        self.assertEqual(set(dict(catalog.suggestions("essence "))), {"open", "check", "return", "close"})
        self.assertEqual(set(dict(catalog.suggestions("essence return --"))), {"--accept-move"})
        self.assertEqual(catalog.suggestions("essence check --"), [])


if __name__ == "__main__":
    unittest.main()
