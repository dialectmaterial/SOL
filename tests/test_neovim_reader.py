"""Installed continuous reader: invented sources and isolated personal state."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
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
        def native(payload, executable, **options):
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
        def native(payload, _, **options):
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
        def native(payload, _, **options):
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
                with patch.object(neovim, "launch_payload", side_effect=lambda p, _, **kw: (0, self.reply(p, offset=bad))), \
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
        def native(payload, _, **options):
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
            def native(payload, _, **options):
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
        def native(payload, _, **options):
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

    def test_three_markers_save_immediately_even_if_editor_later_quits_without_cursor_save(self):
        self.extend(3)
        service = self.service()
        self.position(service, 4)
        before = service.store.get_state()
        def native(payload, _, on_request):
            for slot, index in ((1, 0), (2, 1), (3, 2)):
                result = on_request({"op": "marker_set", "slot": slot, "mode": "continuous",
                                     "packet": self.reply(payload, record=index)["packet"]})
                self.assertTrue(result["markers"]["persistent"])
                self.assertEqual(service.store.get_bookmark(f"sol:reader-marker:{slot}")["target_id"],
                                 self.book.passages[index].identifier)
            return 0, None
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        self.assertEqual(service.store.get_state(), before)
        def reopened(payload, _, **kwargs):
            self.assertEqual([row["target"] for row in payload["markers"]["slots"]],
                             [row.identifier for row in self.book.passages])
            return 0, self.reply(payload)
        with patch.object(neovim, "launch_payload", side_effect=reopened):
            self.assertEqual(self.run_view(service), 0)

    def test_marker_clear_preserves_other_slots_and_ordinary_bookmarks(self):
        service = self.service()
        actions = self.position(service)
        service.save_bookmark("An ordinary named bookmark", actions.session)
        def native(payload, _, on_request):
            packet = self.reply(payload)["packet"]
            for slot in (1, 2):
                on_request({"op": "marker_set", "slot": slot, "packet": packet, "mode": "paragraph"})
            result = on_request({"op": "marker_clear", "slot": 1, "packet": packet, "mode": "paragraph"})
            self.assertIsNone(result["markers"]["slots"][0]["target"])
            self.assertEqual(result["markers"]["slots"][1]["target"], self.identifier)
            self.assertIsNotNone(service.store.get_bookmark("An ordinary named bookmark"))
            return 0, self.reply(payload)
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)

    def test_temporary_markers_can_jump_without_opening_any_workspace(self):
        self.extend(3)
        before = self.files()
        def native(payload, _, on_request):
            packet = self.reply(payload, record=2)["packet"]
            result = on_request({"op": "marker_set", "slot": 1, "packet": packet, "mode": "paragraph"})
            self.assertFalse(result["markers"]["persistent"])
            result = on_request({"op": "marker_open", "slot": 1, "packet": packet, "mode": "paragraph"})
            shown = result["payload"]
            self.assertEqual(shown["mode"], "paragraph")
            self.assertEqual(shown["restore"]["reference"]["reference"]["target_id"], self.book.passages[2].identifier)
            return 0, {"action": "quit", "packet": shown["restore"]}
        with patch.object(neovim, "launch_payload", side_effect=native), \
                patch("sol.workspace.store.Workspace", side_effect=AssertionError("No personal store")):
            self.assertEqual(self.run_view(), 0)
        self.assertEqual(self.files(), before)

    def test_live_section_transition_does_not_restart_the_native_process(self):
        self.extend(3)
        def native(payload, _, on_request):
            packet = self.reply(payload)["packet"]
            result = on_request({"op": "next", "mode": "paragraph", "packet": packet})
            shown = result["payload"]
            self.assertEqual(shown["mode"], "paragraph")
            self.assertEqual(shown["records"][0]["id"], self.book.passages[1].identifier)
            return 0, {"action": "quit", "packet": shown["restore"]}
        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native) as launch:
            self.assertEqual(self.run_view(), 0)
        launch.assert_called_once()

    def test_session_theme_survives_section_reload_without_being_saved(self):
        self.extend(3)
        service = self.service()
        def native(payload, _, on_request):
            self.assertEqual(payload["theme"]["active"], "paper")
            packet = self.reply(payload)["packet"]
            shown = on_request({"op": "next", "mode": "continuous", "theme": "dark", "packet": packet})["payload"]
            self.assertEqual(shown["theme"]["active"], "dark")
            for invalid in ("sepia", None, ["dark"]):
                with self.subTest(theme=invalid), self.assertRaisesRegex(ValueError, "theme"):
                    on_request({"op": "next", "mode": "continuous", "theme": invalid, "packet": packet})
            return 0, {"action": "quit", "packet": shown["restore"]}
        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service, theme="paper"), 0)
        self.assertNotIn("theme", json.dumps(service.store.export()))
        with self.assertRaisesRegex(ValueError, "theme"):
            self.run_view(theme="sepia")

    def test_invalid_live_requests_do_not_write_markers_or_positions(self):
        service = self.service()
        self.position(service, 4)
        before = service.store.export()
        def native(payload, _, on_request):
            packet = self.reply(payload)["packet"]
            requests = [
                {"op": "marker_set", "slot": slot, "packet": packet, "mode": "continuous"}
                for slot in (True, 0, 4, "1")]
            requests += [{"op": "node_open", "node": [], "packet": packet, "mode": "continuous"},
                         {"op": "node_open", "node": "/nonexistent", "packet": packet, "mode": "continuous"},
                         {"op": "execute", "packet": packet, "mode": "continuous"}]
            for request in requests:
                with self.subTest(request=request), self.assertRaises(ValueError):
                    on_request(request)
            return 0, None
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        after = service.store.export()
        before.pop("exported_at")
        after.pop("exported_at")
        self.assertEqual(after, before)

    def test_source_preview_shows_evidence_without_moving_or_saving(self):
        service = self.service()
        self.position(service, 4)
        before = service.store.export()
        captured = {"version": 1, "title": "Synthetic section", "target_id": self.identifier,
                    "transcription_status": "needs_visual_review",
                    "sources": [{"pdf_page": 7, "printed_page": "5", "bbox": [1, 2, 3, 4]},
                                {"pdf_page": 8, "printed_page": None}]}
        captures, rendered = [], []
        class Service:
            def __init__(self, book):
                pass
            def capture(self, identifier):
                captures.append(identifier)
                return captured
        def render(request, index):
            rendered.append(index)
            return f"/cache/{index}.png", "bbox" in request["sources"][index]
        def native(payload, _, on_request):
            # A selection may stay active: viewing evidence is not navigation.
            packet = self.packet(3, 14)
            first = on_request({"op": "source_preview", "page": 1, "packet": packet, "mode": "continuous"})["source"]
            self.assertEqual((first["shown"], first["cropped"], first["image"], first["viewer"]),
                             (1, True, "/cache/0.png", "invented-viewer"))
            self.assertEqual(first["status"], "needs visual review")
            self.assertIn("printed source is authoritative", first["note"])
            self.assertEqual([row["printed_page"] for row in first["pages"]], ["5", "unnumbered"])
            second = on_request({"op": "source_preview", "page": 2, "packet": packet, "mode": "continuous"})["source"]
            self.assertFalse(second["cropped"])
            for bad in (0, 3, True, "1"):
                with self.subTest(page=bad), self.assertRaises(ValueError):
                    on_request({"op": "source_preview", "page": bad, "packet": packet, "mode": "continuous"})
            return 0, None
        with patch("sol.terminal.source.SourceService", Service), \
                patch("sol.terminal.source.render_region", side_effect=render), \
                patch("sol.terminal.source.open_viewer", return_value="invented-viewer"), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        self.assertEqual(rendered, [0, 1])
        # One verified capture per passage; page changes and refusals reuse it.
        self.assertEqual(captures, [self.identifier])
        after = service.store.export()
        before.pop("exported_at")
        after.pop("exported_at")
        self.assertEqual(after, before)

    def test_stale_source_capture_is_replaced_on_the_next_request(self):
        from sol.terminal.source import SourceError
        captures = []
        class Service:
            def __init__(self, book):
                pass
            def capture(self, identifier):
                captures.append(identifier)
                return {"title": "Synthetic", "target_id": identifier, "sources": [{"pdf_page": 1}]}
        outcomes = [SourceError("Verified PDF snapshot changed"), ("/cache/0.png", False)]
        def render(request, index):
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        def native(payload, _, on_request):
            packet = self.reply(payload)["packet"]
            request = {"op": "source_preview", "page": 1, "packet": packet, "mode": "continuous"}
            with self.assertRaisesRegex(ValueError, "snapshot changed"):
                on_request(dict(request))
            self.assertEqual(on_request(dict(request))["source"]["image"], "/cache/0.png")
            return 0, None
        with patch("sol.terminal.source.SourceService", Service), \
                patch("sol.terminal.source.render_region", side_effect=render), \
                patch("sol.terminal.source.open_viewer", return_value=None), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)
        self.assertEqual(len(captures), 2)

    def test_note_binds_the_passage_and_keeps_position_and_selection(self):
        service = self.service()
        self.position(service, 4)
        state = service.store.get_state()
        def native(payload, _, on_request):
            self.assertEqual(payload["personal"], {"persistent": True, "notes": {}})
            # A selection is context: it may stay active and is not stored.
            packet = self.packet(3, 14)
            result = on_request({"op": "note_add", "body": "First line\n\tindented", "packet": packet,
                                 "mode": "continuous"})
            shown = result["personal"]["notes"][self.identifier]
            self.assertEqual(shown[0]["lines"], ["First line", "    indented"])
            self.assertEqual(shown[0]["author"], "Invented reader")
            for body in ("", "   ", None, 7, "x" * (neovim_reader.NOTE_LIMIT + 1)):
                with self.subTest(body=body), self.assertRaises(ValueError):
                    on_request({"op": "note_add", "body": body, "packet": packet, "mode": "continuous"})
            with self.assertRaisesRegex(ValueError, "unsafe control"):
                on_request({"op": "note_add", "body": "hidden \u202e reversal", "packet": packet,
                            "mode": "continuous"})
            return 0, None
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        [note] = service.store.list_annotations()
        self.assertEqual((note["target_id"], note["body"], note["actor"]),
                         (self.identifier, "First line\n\tindented", "Invented reader"))
        self.assertEqual(note["content_sha256"], self.book.canonical_records[self.identifier]["content_sha256"])
        self.assertEqual(service.store.get_state(), state)
        # Reopening shows the saved note with the passage.
        def reopened(payload, _, on_request):
            self.assertEqual(len(payload["personal"]["notes"][self.identifier]), 1)
            return 0, None
        with patch.object(neovim, "launch_payload", side_effect=reopened):
            self.assertEqual(self.run_view(service), 0)

    def test_temporary_session_refuses_notes_and_writes_nothing(self):
        before = self.files()
        def native(payload, _, on_request):
            self.assertEqual(payload["personal"], {"persistent": False, "notes": {}})
            with self.assertRaisesRegex(ValueError, "notes need a workspace"):
                on_request({"op": "note_add", "body": "Kept nowhere", "packet": self.reply(payload)["packet"],
                            "mode": "continuous"})
            return 0, None
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)
        self.assertEqual(self.files(), before)

    def test_notes_on_a_retired_identity_and_unsafe_display_text_are_shown_safely(self):
        rows = self.rows()
        retired = deepcopy(rows[1])
        retired.update(id=RETIRED, type="retired_record", redirect_id=self.identifier, order=2,
                       markdown="An invented retired record.", plain_text="An invented retired record.")
        rows.append(retired)
        self.write_records(rows)
        service = self.service()
        self.position(service, 0)
        digest = self.book.canonical_records[self.identifier]["content_sha256"]
        service.store.add_annotation(RETIRED, "Older note\u200don the retired ID", digest)
        def native(payload, _, on_request):
            [shown] = payload["personal"]["notes"][self.identifier]
            self.assertEqual(shown["lines"], ["Older note\\u200don the retired ID"])
            return 0, None
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)

    def test_tree_selection_resolves_display_path_to_existing_source_identity(self):
        self.extend(3)
        def native(payload, _, on_request):
            tree = payload["structure"]
            row = next(row for row in tree["nodes"] if row["key"] == tree["current"])
            self.assertEqual(row["title"], "Synthetic section")
            packet = self.reply(payload, record=2)["packet"]
            result = on_request({"op": "node_open", "node": row["key"], "packet": packet, "mode": "continuous"})
            self.assertEqual(result["payload"]["restore"]["reference"]["reference"]["target_id"], self.identifier)
            return 0, {"action": "quit", "packet": result["payload"]["restore"]}
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)

    def test_search_crosses_loaded_sections_and_history_restores_exact_selection(self):
        self.extend(3)
        service = self.service()
        self.position(service, 4)
        def native(payload, _, on_request):
            packet = self.packet(3, 14)
            result = on_request({"op": "search", "query": "paragraph 2", "packet": packet, "mode": "paragraph"})
            self.assertEqual(len(result["search"]["rows"]), 1)
            shown = on_request({"op": "search_open", "result": 1, "packet": packet, "mode": "paragraph"})["payload"]
            self.assertEqual(shown["records"][0]["id"], self.book.passages[2].identifier)
            marks = shown["search_marks"]
            self.assertEqual(marks["id"], self.book.passages[2].identifier)
            text = shown["records"][0]["plain_text"]
            self.assertEqual([text[start:end].lower() for start, end in marks["spans"]], ["paragraph 2"])
            returned = on_request({"op": "history_back", "packet": shown["restore"], "mode": "paragraph"})["payload"]
            self.assertIsNone(returned["search_marks"])
            self.assertEqual(returned["restore"]["cursor_offset"], packet["cursor_offset"])
            self.assertEqual(returned["restore"]["selection"], packet["selection"])
            return 0, {"action": "quit", "packet": returned["restore"]}
        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)

    def test_sentence_study_opens_its_longest_sentence_and_returns_to_the_origin(self):
        self.extend(3)
        records = self.rows()
        text = ("Short one. This second sentence is clearly the longest one in the whole invented section, "
                "because it keeps going well past every other sentence here.")
        records[-1].update(markdown=text, plain_text=text)
        self.write_records(records)
        service = self.service()
        self.position(service, 4)
        data_home = self.root / "data"
        def native(payload, _, on_request):
            origin = payload["restore"]
            study = on_request({"op": "sentence_study", "packet": origin, "mode": "continuous"})["study"]
            self.assertEqual(study["rows"][0]["tokens"], 23)
            self.assertTrue(study["rows"][0]["snippet"].startswith("This second sentence"))
            saved = Path(study["saved"])
            self.assertEqual(saved.parent, data_home / "sol" / "studies")
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(saved.read_text())["origin"]["reference"]["target_id"],
                             origin["reference"]["reference"]["target_id"])
            opened = on_request({"op": "study_open", "row": 1, "packet": origin, "mode": "continuous"})["payload"]
            self.assertEqual(opened["restore"]["reference"]["reference"]["target_id"], records[-1]["id"])
            self.assertEqual(opened["restore"]["cursor_offset"], text.index("This"))
            back = on_request({"op": "history_back", "packet": opened["restore"], "mode": "continuous"})["payload"]
            self.assertEqual(back["restore"]["reference"]["reference"]["target_id"],
                             origin["reference"]["reference"]["target_id"])
            self.assertEqual(back["restore"]["cursor_offset"], origin["cursor_offset"])
            with self.assertRaisesRegex(ValueError, "choose a displayed sentence"):
                on_request({"op": "study_open", "row": 99, "packet": back["restore"], "mode": "continuous"})
            return 0, {"action": "quit", "packet": back["restore"]}
        with patch.dict(os.environ, XDG_DATA_HOME=str(data_home)), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)

    def test_refused_destination_view_keeps_the_shown_and_saved_position(self):
        """A destination whose view cannot be prepared is never saved or entered in history."""
        self.extend(3)
        records = self.rows()
        text = "Short one. This sentence is the longest one in the passage, by a clear margin of words."
        records[1].update(markdown=text, plain_text=text)
        self.write_records(records)
        build = neovim.build_payload
        # Each live navigation route, with the request that makes it available first.
        routes = {"next": ({}, None), "passage_next": ({}, None), "marker_open": ({"slot": 1}, None),
                  "search_open": ({"result": 1}, {"op": "search", "query": "paragraph 2"}),
                  "search_next": ({}, {"op": "search", "query": "paragraph 2"}),
                  "history_back": ({}, {"op": "passage_previous"}),
                  "study_open": ({"row": 1}, {"op": "sentence_study"})}

        def saved_at(service):
            state = service.store.get_state()
            return state["current_id"], state["position"]["cursor_offset"]

        for operation, (extra, setup) in routes.items():
            with self.subTest(operation=operation):
                service = self.service(self.root / f"refused-{operation}.sqlite3")
                self.position(service, 4, self.book.passages[1].identifier)
                service.save_bookmark("sol:reader-marker:1", ReaderActions(self.book, service).session,
                                      self.book.passages[2].identifier, replace=True)
                failing = []

                def build_or_fail(*args, **kwargs):
                    if failing:
                        raise RuntimeError("injected view preparation failure")
                    return build(*args, **kwargs)

                def native(payload, _, on_request):
                    shown = payload
                    if setup is not None:
                        shown = on_request({**setup, "packet": shown["restore"],
                                            "mode": "continuous"}).get("payload", shown)
                    origin = deepcopy(shown["restore"])
                    origin["cursor_offset"] = 6
                    here = origin["reference"]["reference"]["target_id"], 6
                    request = {"op": operation, **extra, "packet": origin, "mode": "continuous"}
                    failing.append(True)
                    with self.assertRaisesRegex(RuntimeError, "injected"):
                        on_request(deepcopy(request))
                    failing.clear()
                    # The outgoing position the editor showed may be saved; the destination is not.
                    self.assertEqual(saved_at(service), here)
                    # The same request succeeds on retry, and history returns once to the origin.
                    opened = on_request(deepcopy(request))["payload"]["restore"]
                    there = opened["reference"]["reference"]["target_id"], opened["cursor_offset"]
                    self.assertNotEqual(there, here)
                    self.assertEqual(saved_at(service), there)
                    returning = "history_forward" if operation == "history_back" else "history_back"
                    back = on_request({"op": returning, "packet": opened, "mode": "continuous"})["payload"]
                    self.assertEqual(back["restore"]["reference"], origin["reference"])
                    self.assertEqual(back["restore"]["cursor_offset"], 6)
                    return 0, {"action": "quit", "packet": back["restore"]}

                with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                        patch.object(neovim, "build_payload", side_effect=build_or_fail), \
                        patch.dict(os.environ, XDG_DATA_HOME=str(self.root / "data")), \
                        patch.object(neovim, "launch_payload", side_effect=native):
                    self.assertEqual(self.run_view(service), 0)
                reopened = ReaderActions(self.book, service)
                reopened.restore()
                self.assertEqual(reopened.snapshot().cursor_offset, 6)

    def test_refused_destination_leaves_mode_and_theme_for_the_next_view(self):
        self.extend(3)
        build = neovim.build_payload
        failing, shown = [], []

        def build_or_fail(*args, **kwargs):
            if failing:
                raise RuntimeError("injected view preparation failure")
            return build(*args, **kwargs)

        def native(payload, _, on_request):
            shown.append(payload)
            if len(shown) > 1:
                return 0, {"action": "quit", "packet": payload["restore"]}
            failing.append(True)
            with self.assertRaises(RuntimeError):
                on_request({"op": "passage_next", "packet": payload["restore"], "mode": "paragraph",
                            "focus": True, "theme": "dark"})
            failing.clear()
            # Leaving the editor for the next section rebuilds the view from the
            # reader's own state, which the refused move must not have changed.
            return 0, {"action": "next", "packet": payload["restore"]}

        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "build_payload", side_effect=build_or_fail), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)
        first, second = shown
        self.assertEqual((second["mode"], second["focus"], second["theme"]),
                         (first["mode"], first["focus"], first["theme"]))
        self.assertEqual(second["records"][0]["id"], self.book.passages[1].identifier)

    def test_competing_save_refuses_navigation_without_moving_this_reader(self):
        self.extend(3)
        service = self.service()
        self.position(service, 4)
        other = self.service(service.store.path)

        def native(payload, _, on_request):
            competing = ReaderActions(self.book, other)
            competing.restore()
            competing.set_cursor(9)
            competing.save_position()
            saved = other.store.get_state()
            with self.assertRaises(WorkspaceConflict):
                on_request({"op": "next", "packet": payload["restore"], "mode": "continuous"})
            self.assertEqual(service.store.get_state(), saved)
            # Retrying cannot overwrite the other session's work either.
            with self.assertRaises(WorkspaceConflict):
                on_request({"op": "passage_next", "packet": payload["restore"], "mode": "continuous"})
            self.assertEqual(service.store.get_state(), saved)
            return 1, None

        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 1)

    def test_changed_corpus_refuses_live_navigation_without_saving(self):
        self.extend(3)
        service = self.service()
        self.position(service, 4)
        before = service.store.get_state()

        def native(payload, _, on_request):
            source = self.corpus / "sample.md"
            source.write_text(source.read_text() + "\nAn unindexed edit.\n")
            with self.assertRaises(ValueError):
                on_request({"op": "next", "packet": payload["restore"], "mode": "continuous"})
            self.assertEqual(service.store.get_state(), before)
            return 1, None

        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 1)

    def test_cross_section_paragraph_previous_lands_at_beginning_and_keeps_focus(self):
        self.extend(3)
        def native(payload, _, on_request):
            shown = on_request({"op": "passage_next", "packet": payload["restore"],
                                "mode": "paragraph", "focus": True})["payload"]
            self.assertTrue(shown["focus"])
            returned = on_request({"op": "passage_previous", "packet": shown["restore"],
                                   "mode": "paragraph", "focus": True})["payload"]
            self.assertEqual(returned["restore"]["cursor_offset"], 0)
            self.assertEqual(returned["restore"]["reference"]["reference"]["target_id"], self.identifier)
            return 0, {"action": "quit", "packet": returned["restore"]}
        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)


if __name__ == "__main__":
    unittest.main()
