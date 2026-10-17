"""Installed continuous reader: invented sources and isolated personal state."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
from uuid import UUID

from fixtures_corpus import CorpusFixture
from sol import core
from sol.core.paths import display_path, resolve_path
from sol.reader import app
from sol.reader.actions import ReaderActions
from sol.terminal import neovim, neovim_reader
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace, WorkspaceConflict


RETIRED = "dddddddd-0000-4000-8000-000000000004"


class NeovimReaderTests(CorpusFixture, unittest.TestCase):
    def rows(self):
        return [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().split("\n") if line]

    def extend(self, count=3):
        records = self.rows()
        original = records[1]
        for index in range(1, count):
            row = deepcopy(original)
            row.update(id=str(UUID(int=index)), order=len(records),
                       markdown=f"Invented paragraph {index} has enough words for sustained reading.",
                       plain_text=f"Invented paragraph {index} has enough words for sustained reading.")
            records.append(row)
        self.write_records(records)

    def service(self, path=None):
        store = Workspace(path or self.root / "reader.sqlite3", self.book.corpus_manifest["corpus_id"],
                          {key: self.book.corpus_manifest[key] for key in ("edition", "source")}, actor="Invented reader")
        self.addCleanup(store.close)
        return WorkspaceReader(self.book, store, "Invented reader", resolve_path, display_path,
                               app.render_passage, 72, False, False)

    def position(self, service, offset=0, identifier=None):
        actions = ReaderActions(self.book, service)
        actions.read((), first=True)
        if identifier is not None:
            actions.open(identifier)
        actions.set_cursor(offset)
        actions.save_position()
        return actions

    @staticmethod
    def reply(payload, *, action="quit", record=0, offset=7):
        row = payload["records"][record]
        return {"action": action, "packet": {"reference": deepcopy(row["reference"]),
                                              "selection": None, "cursor_offset": offset}}

    def run_view(self, service=None, **kwargs):
        with patch.object(neovim, "validate_environment", return_value="/invented/nvim"):
            return neovim_reader.run_reader(self.book, service, **kwargs)

    def test_adjacent_records_share_one_view_without_changing_canonical_text(self):
        self.extend()
        before = self.files()
        def native(payload, executable):
            self.assertEqual([row["id"] for row in payload["records"]],
                             [p.identifier for p in self.book.passages])
            self.assertTrue(payload["integrated"])
            self.assertEqual(payload["navigation"], {"previous": False, "next": False})
            self.assertEqual(executable, "/invented/nvim")
            return 0, self.reply(payload, record=2)
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)
        self.assertEqual(before, self.files())

    def test_quit_and_reopen_share_existing_workspace_positions_across_widths(self):
        self.extend()
        service = self.service()
        self.position(service, 9)
        observed = []
        def native(payload, _):
            observed.append((payload["width"], payload["restore"]["cursor_offset"]))
            return 0, self.reply(payload, record=1, offset=17)
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service, width=72), 0)
            self.assertEqual(self.run_view(service, width=38), 0)
        self.assertEqual(observed, [(72, 9), (38, 17)])
        restored = ReaderActions(self.book, service)
        restored.restore()
        self.assertEqual(restored.snapshot().current.identifier, self.book.passages[1].identifier)
        self.assertEqual(restored.cursor_offset, 17)
        self.assertIsNone(restored.snapshot().viewport_offset)

    def test_existing_requested_retirement_identity_survives_native_round_trip(self):
        rows = self.rows()
        retired = deepcopy(rows[1])
        retired.update(id=RETIRED, type="retired_record", redirect_id=self.identifier, order=2,
                       markdown="An invented retired record.", plain_text="An invented retired record.")
        rows.append(retired)
        self.write_records(rows)
        service = self.service()
        self.position(service, 5, RETIRED)
        def native(payload, _):
            self.assertEqual(payload["restore"]["reference"]["reference"]["requested_id"], RETIRED)
            self.assertEqual(payload["records"][0]["reference"]["reference"]["requested_id"], RETIRED)
            return 0, self.reply(payload, offset=11)
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        self.assertEqual(service.store.get_state()["current_id"], RETIRED)

    def test_selection_uses_existing_type_and_does_not_create_annotation(self):
        service = self.service()
        self.position(service)
        packet = self.packet(3, 14)
        with patch.object(neovim, "launch_payload", return_value=(0, {"action": "quit", "packet": packet})):
            self.assertEqual(self.run_view(service), 0)
        actions = ReaderActions(self.book, service)
        actions.restore()
        self.assertEqual(actions.cursor_offset, 14)
        self.assertIsNone(actions.selection)
        self.assertEqual(service.store.export()["annotations"], [])

    def test_invalid_return_cannot_overwrite_saved_position(self):
        for bad in (True, -1, len(self.body) + 1, "7"):
            with self.subTest(offset=bad):
                service = self.service(self.root / f"invalid-{str(bad)}.sqlite3")
                self.position(service, 4)
                before = service.store.get_state()
                with patch.object(neovim, "launch_payload", side_effect=lambda p, _: (0, self.reply(p, offset=bad))), \
                        self.assertRaises(ValueError):
                    self.run_view(service)
                self.assertEqual(service.store.get_state(), before)

    def test_missing_packet_and_failed_process_do_not_save_a_cursor(self):
        service = self.service()
        self.position(service, 4)
        before = service.store.get_state()
        for status in (0, 130, 1):
            with patch.object(neovim, "launch_payload", return_value=(status, None)):
                self.assertEqual(self.run_view(service), status)
            self.assertEqual(service.store.get_state(), before)

    def test_changed_source_while_reader_open_is_refused(self):
        service = self.service()
        self.position(service, 4)
        before = service.store.get_state()
        def native(payload, _):
            source = self.corpus / "sample.md"
            source.write_text(source.read_text() + "\nAn unindexed edit.\n")
            return 0, self.reply(payload)
        with patch.object(neovim, "launch_payload", side_effect=native), self.assertRaises(ValueError):
            self.run_view(service)
        self.assertEqual(service.store.get_state(), before)

    def test_unavailable_and_malformed_navigation_are_refused_without_saving(self):
        service = self.service()
        self.position(service, 4)
        before = service.store.get_state()
        for action in ("next", "previous", "execute", None, []):
            def native(payload, _):
                return 0, self.reply(payload, action=action)
            with self.subTest(action=action), patch.object(neovim, "launch_payload", side_effect=native), \
                    self.assertRaises(ValueError):
                self.run_view(service)
            self.assertEqual(service.store.get_state(), before)

    def test_large_reading_extent_has_bounded_source_ordered_sections(self):
        self.extend(6)
        with patch.object(neovim_reader, "SECTION_BUDGET", 2):
            for index, first, last in ((0, 0, 1), (1, 0, 1), (2, 2, 3), (5, 4, 5)):
                self.assertEqual(neovim_reader.reading_section(self.book, self.book.passages[index].identifier),
                                 neovim_reader.ReadingSection(first, last))

    def test_supplied_chapter_boundary_is_not_merged_with_the_next_chapter(self):
        self.extend(3)
        rows = self.rows()
        rows[0]["level"] = 4
        section = deepcopy(rows[0])
        section.update(id="eeeeeeee-0000-4000-8000-000000000005", order=len(rows),
                       title="Another supplied chapter", markdown="## Another supplied chapter",
                       plain_text="Another supplied chapter", path="/another-chapter",
                       reader_path="/BEING/another-chapter.txt", reader_title="Another supplied chapter")
        rows.append(section)
        paragraph = deepcopy(rows[1])
        paragraph.update(id="ffffffff-0000-4000-8000-000000000006", order=len(rows),
                         parent_id=section["id"], reader_path=section["reader_path"],
                         reader_title=section["title"], context=[{
                             "id": section["id"], "type": "section", "title": section["title"], "path": section["path"]}])
        rows.append(paragraph)
        self.write_records(rows)
        self.assertEqual(neovim_reader.reading_section(self.book, self.identifier),
                         neovim_reader.ReadingSection(0, 2))
        self.assertEqual(neovim_reader.reading_section(self.book, paragraph["id"]),
                         neovim_reader.ReadingSection(3, 3))

    def test_section_transitions_continue_forward_and_backward_then_save(self):
        self.extend(5)
        service = self.service()
        self.position(service, 4)
        seen = []
        def native(payload, _):
            seen.append([r["id"] for r in payload["records"]])
            if len(seen) == 1:
                self.assertTrue(payload["navigation"]["next"])
                return 0, self.reply(payload, action="next")
            if len(seen) == 2:
                self.assertEqual(payload["restore"]["cursor_offset"], 0)
                return 0, self.reply(payload, action="previous")
            self.assertEqual(payload["restore"]["cursor_offset"], len(self.book.passages[1].text))
            return 0, self.reply(payload, record=1, offset=10)
        with patch.object(neovim_reader, "SECTION_BUDGET", 2), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        self.assertEqual(seen, [[p.identifier for p in self.book.passages[:2]],
                                [p.identifier for p in self.book.passages[2:4]],
                                [p.identifier for p in self.book.passages[:2]]])

    def test_selection_cannot_trigger_section_transition(self):
        self.extend(3)
        service = self.service()
        self.position(service)
        before = service.store.get_state()
        result = {"action": "next", "packet": self.packet()}
        with patch.object(neovim_reader, "SECTION_BUDGET", 2), \
                patch.object(neovim, "launch_payload", return_value=(0, result)), self.assertRaises(ValueError):
            self.run_view(service)
        self.assertEqual(service.store.get_state(), before)

    def test_atomic_position_acceptance_rolls_back_session_on_workspace_conflict(self):
        self.extend()
        service = self.service()
        actions = self.position(service, 4)
        other = self.service(service.store.path)
        competing = ReaderActions(self.book, other)
        competing.restore()
        competing.set_cursor(8)
        competing.save_position()
        before, saved = actions.snapshot(), other.store.get_state()
        reference = core.capture_reference(self.book.corpus_snapshot, self.book.passages[1].identifier)
        with self.assertRaises(WorkspaceConflict):
            actions.accept_return_position(reference, 9)
        self.assertEqual(actions.snapshot(), before)
        self.assertEqual(service.store.get_state(), saved)

    def test_atomic_position_acceptance_rejects_a_forged_selection(self):
        actions = ReaderActions(self.book)
        actions.read((), first=True)
        selection = actions.select_span(3, 14)
        before = actions.snapshot()
        reference = core.capture_reference(self.book.corpus_snapshot, self.identifier)
        for changes in ({"text": "A forged selection"}, {"start": True}, {"end": None},
                        {"end": []}, {"plain_text_sha256": "0" * 64}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                actions.accept_return_position(reference, 14, replace(selection, **changes))
            self.assertEqual(actions.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
