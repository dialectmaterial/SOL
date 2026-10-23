"""Installed continuous reader: invented sources and isolated personal state."""
from copy import deepcopy
from dataclasses import replace
import json
import os
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import UUID

from fixtures_corpus import CorpusFixture
from sol import core
from sol.core.paths import display_path, resolve_path
from sol.app import main as app
from sol.being.actions import ReaderActions
from sol.being.neovim import host as neovim
from sol.being.neovim import reader as neovim_reader
from sol.being.surface import Sample
from sol.presentation.theme import THEMES
from sol.being.workspace.reader import WorkspaceReader
from sol.being.workspace.store import Workspace, WorkspaceConflict


RETIRED = "dddddddd-0000-4000-8000-000000000004"


class NeovimReaderTests(CorpusFixture, unittest.TestCase):
    def test_import_and_essence_launch_do_not_load_the_essence_interface(self):
        program = """
import importlib.abc
from pathlib import Path
import sys
from unittest.mock import patch

class NoEssenceInterface(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'sol.essence.tui' or fullname.startswith('sol.essence.tui.'):
            raise AssertionError('BEING imported ESSENCE interface: ' + fullname)

sys.meta_path.insert(0, NoEssenceInterface())
from sol.being.neovim import reader
assert not any(name == 'sol.essence.tui' or name.startswith('sol.essence.tui.')
               for name in sys.modules)

from sol.core.corpus import load_corpus_book
from sol.interchange.essence import TEXTUAL_HINT, read_context

def native(payload, _, on_request):
    request = {'op': 'essence_open', 'packet': payload['restore'], 'mode': 'continuous'}
    with patch('importlib.util.find_spec', return_value=None) as probe:
        try:
            on_request(request)
        except ValueError as error:
            assert str(error) == TEXTUAL_HINT
        else:
            raise AssertionError('missing Textual was not refused')
        probe.assert_called_once_with('textual')
    with patch('importlib.util.find_spec', return_value=object()) as probe:
        launch = on_request(request)['essence']
        probe.assert_called_once_with('textual')
    assert launch['command'][:4] == [sys.executable, '-m', 'sol.essence.tui', '--context']
    context = Path(launch['command'][4])
    assert read_context(context)['state_file'] is None
    assert context.stat().st_mode & 0o777 == 0o600
    return 0, None

with patch.object(reader.neovim, 'validate_environment', return_value='/invented/nvim'), \\
        patch.object(reader.neovim, 'launch_payload', side_effect=native):
    assert reader.run_reader(load_corpus_book(sys.argv[1])) == 0
assert not any(name == 'sol.essence.tui' or name.startswith('sol.essence.tui.')
               for name in sys.modules)
assert 'textual' not in sys.modules
"""
        result = subprocess.run([sys.executable, "-B", "-c", program, str(self.corpus)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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

    def test_typography_reuse_keeps_payloads_detached_and_source_checks_live(self):
        from sol.being.quality.typography import Typography, TypographySpan
        calls = []
        def project(markdown, text):
            calls.append((markdown, text))
            return Typography((TypographySpan(0, 1, ("emphasis",)),))

        def native(payload, _, on_request):
            request = {"op": "node_open", "node": "/",
                       "packet": payload["restore"], "mode": "paragraph"}
            before = len(calls)
            payload["records"][0]["styles"][0]["styles"].append("strong")
            refreshed = on_request(request)["payload"]
            self.assertEqual(len(calls), before)
            self.assertEqual(refreshed["records"][0]["styles"][0]["styles"], ["emphasis"])
            source = self.corpus / "sample.md"
            source.write_text(source.read_text() + "\nUnindexed edit.\n")
            with self.assertRaises(ValueError):
                on_request({**request, "packet": refreshed["restore"]})
            return 0, None

        with patch.object(neovim, "map_typography", side_effect=project), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)
        self.assertEqual(len(calls), 1)

    def test_adjacent_records_share_one_view_without_changing_canonical_text(self):
        self.extend()
        before = self.files()
        def native(payload, executable, **options):
            self.assertEqual([row["id"] for row in payload["records"]],
                             [p.identifier for p in self.book.passages])
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
                patch("sol.being.workspace.store.Workspace", side_effect=AssertionError("No personal store")):
            self.assertEqual(self.run_view(), 0)
        self.assertEqual(self.files(), before)

    def test_named_landmarks_use_workspace_bookmarks_and_open_their_paragraph(self):
        self.extend(3)
        service = self.service()
        actions = self.position(service)
        service.save_bookmark("An ordinary named bookmark", actions.session)
        def native(payload, _, on_request):
            def request(op, record=0, **fields):
                return on_request({"op": op, "packet": self.reply(payload, record=record)["packet"],
                                   "mode": "continuous", **fields})
            on_request({"op": "marker_set", "slot": 1, "packet": self.reply(payload)["packet"], "mode": "continuous"})
            result = request("landmark_set", record=2, name="  Being and nothing  ")["landmarks"]
            self.assertEqual((result["action"], result["name"], result["persistent"]), ("set", "Being and nothing", True))
            self.assertEqual(service.store.get_bookmark("Being and nothing")["target_id"],
                             self.book.passages[2].identifier)
            listed = request("landmark_list")["landmarks"]["rows"]
            # Shell bookmarks are landmarks too; SOL's marker slots are not.
            self.assertEqual([row["name"] for row in listed], ["An ordinary named bookmark", "Being and nothing"])
            self.assertTrue(all(row["available"] for row in listed))
            shown = request("landmark_open", name="Being and nothing")["payload"]
            self.assertEqual(shown["restore"]["reference"]["reference"]["target_id"], self.book.passages[2].identifier)
            for bad in ("", "sol:reader-marker:1", "x" * 81, "line\nbreak"):
                with self.subTest(name=bad), self.assertRaises(ValueError):
                    request("landmark_set", name=bad)
            with self.assertRaisesRegex(ValueError, "landmark is gone"):
                request("landmark_open", name="Never named")
            cleared = request("landmark_clear", name="Being and nothing")["landmarks"]
            self.assertEqual([row["name"] for row in cleared["rows"]], ["An ordinary named bookmark"])
            self.assertIsNotNone(service.store.get_bookmark("sol:reader-marker:1"))
            return 0, {"action": "quit", "packet": shown["restore"]}
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)

    def test_temporary_landmarks_last_for_the_session_without_a_workspace(self):
        self.extend(3)
        before = self.files()
        def native(payload, _, on_request):
            packet = self.reply(payload, record=1)["packet"]
            result = on_request({"op": "landmark_set", "name": "Quality", "packet": packet, "mode": "paragraph"})
            self.assertFalse(result["landmarks"]["persistent"])
            shown = on_request({"op": "landmark_open", "name": "Quality", "packet": packet,
                                "mode": "paragraph"})["payload"]
            self.assertEqual(shown["restore"]["reference"]["reference"]["target_id"], self.book.passages[1].identifier)
            return 0, {"action": "quit", "packet": shown["restore"]}
        with patch.object(neovim, "launch_payload", side_effect=native), \
                patch("sol.being.workspace.store.Workspace", side_effect=AssertionError("No personal store")):
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
            self.assertEqual(payload["theme"]["active"], "latte")
            packet = self.reply(payload)["packet"]
            shown = on_request({"op": "next", "mode": "continuous", "theme": "mocha", "packet": packet})["payload"]
            self.assertEqual(shown["theme"]["active"], "mocha")
            for invalid in ("sepia", None, ["mocha"]):
                with self.subTest(theme=invalid), self.assertRaisesRegex(ValueError, "theme"):
                    on_request({"op": "next", "mode": "continuous", "theme": invalid, "packet": packet})
            return 0, {"action": "quit", "packet": shown["restore"]}
        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service, theme="latte"), 0)
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
        with patch("sol.core.source.SourceService", Service), \
                patch("sol.core.source.render_region", side_effect=render), \
                patch("sol.being.source_view.open_viewer", return_value="invented-viewer"), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        self.assertEqual(rendered, [0, 1])
        # One verified capture per passage; page changes and refusals reuse it.
        self.assertEqual(captures, [self.identifier])
        after = service.store.export()
        before.pop("exported_at")
        after.pop("exported_at")
        self.assertEqual(after, before)

    def test_source_pdf_opens_the_page_for_the_current_passage(self):
        service = self.service()
        self.position(service, 4)
        captured = {"version": 1, "title": "Synthetic section", "target_id": self.identifier,
                    "source": {"verified_pdf": "/cache/pdf/x.pdf"},
                    "sources": [{"pdf_page": 7, "printed_page": "5"}, {"pdf_page": 8, "printed_page": None}]}
        opened, viewers = [], ["zathura"]
        class Service:
            def __init__(self, book):
                pass
            def capture(self, identifier):
                return captured
        def native(payload, _, on_request):
            packet = self.packet(3, 14)
            result = on_request({"op": "source_pdf", "page": 2, "packet": packet, "mode": "continuous"})["pdf"]
            self.assertEqual(result, {"viewer": "zathura", "pdf_page": 8, "printed_page": "unnumbered"})
            # Without a PDF viewer, the crop of that page is shown instead.
            viewers.append(None)
            crop = on_request({"op": "source_pdf", "page": 2, "packet": packet, "mode": "continuous"})["source"]
            self.assertEqual((crop["shown"], crop["pdf_missing"], crop["image"]), (2, True, "/cache/1.png"))
            with self.assertRaises(ValueError):
                on_request({"op": "source_pdf", "page": 3, "packet": packet, "mode": "continuous"})
            return 0, None
        with patch("sol.core.source.SourceService", Service), \
                patch("sol.being.source_view.open_pdf", side_effect=lambda request, index: opened.append(index) or viewers[-1]), \
                patch("sol.core.source.render_region", return_value=("/cache/1.png", False)), \
                patch("sol.being.source_view.open_viewer", return_value="invented-viewer"), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        self.assertEqual(opened, [1, 1])

    def test_source_follow_turns_only_an_open_zathura_window(self):
        service = self.service()
        self.position(service, 4)
        captured = {"version": 1, "title": "Synthetic section", "target_id": self.identifier,
                    "source": {"verified_pdf": "/cache/pdf/x.pdf"}, "sources": [{"pdf_page": 7, "printed_page": "5"}]}
        answers, followed = [True, False], []
        class Service:
            def __init__(self, book):
                pass
            def capture(self, identifier):
                return captured
        def follow(request, index):
            followed.append((request, index))
            return answers.pop(0)
        def native(payload, _, on_request):
            packet = self.packet(3, 14)
            for expected in (True, False):
                result = on_request({"op": "source_follow", "packet": packet, "mode": "continuous"})
                self.assertEqual(result, {"follow": {"active": expected}})
            with self.assertRaises(ValueError):
                on_request({"op": "source_follow", "page": 1, "packet": packet, "mode": "continuous"})
            return 0, None
        with patch("sol.core.source.SourceService", Service), \
                patch("sol.being.source_view.follow_pdf", side_effect=follow), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        self.assertEqual(followed, [(captured, 0), (captured, 0)])

    def test_stale_source_capture_is_replaced_on_the_next_request(self):
        from sol.core.source import SourceError
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
        with patch("sol.core.source.SourceService", Service), \
                patch("sol.core.source.render_region", side_effect=render), \
                patch("sol.being.source_view.open_viewer", return_value=None), \
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

    def test_note_edit_keeps_identity_and_history_and_refuses_unsafe_edits(self):
        service = self.service()
        self.position(service, 4)
        state = service.store.get_state()
        digest = self.book.canonical_records[self.identifier]["content_sha256"]
        mine = service.store.add_annotation(self.identifier, "First thought", digest)
        older = service.store.add_annotation(self.identifier, "Written on an older text", "0" * 64)
        with Workspace(service.store.path, self.book.corpus_manifest["corpus_id"],
                       {key: self.book.corpus_manifest[key] for key in ("edition", "source")},
                       actor="Another reader") as other:
            theirs = other.add_annotation(self.identifier, "Someone else's note", digest)

        def native(payload, _, on_request):
            packet = payload["restore"]
            listed = {row["id"]: row for row in payload["personal"]["notes"][self.identifier]}
            self.assertEqual((listed[mine["id"]]["revision"], listed[mine["id"]]["edit_refusal"],
                              listed[mine["id"]]["body"], listed[mine["id"]]["changed_source"]),
                             (1, "", "First thought", False))
            self.assertTrue(listed[older["id"]]["changed_source"])
            self.assertEqual(listed[theirs["id"]]["edit_refusal"], "only the note's author can edit it")
            self.assertIsNone(listed[theirs["id"]]["body"])

            def edit(note, revision, body):
                return on_request({"op": "note_edit", "note": note, "revision": revision, "body": body,
                                   "packet": packet, "mode": "continuous"})

            saved = edit(mine["id"], 1, "First thought, revised")
            self.assertEqual(saved["note_saved"], {"id": mine["id"], "revision": 2, "changed": True})
            # Saving the same text again adds no revision.
            self.assertEqual(edit(mine["id"], 2, "First thought, revised")["note_saved"]["changed"], False)
            # A stale revision, another author's note, and an empty body are refused.
            with self.assertRaisesRegex(ValueError, "changed in another session"):
                edit(mine["id"], 1, "Overwriting from an old editor")
            with self.assertRaisesRegex(ValueError, "author"):
                edit(theirs["id"], 1, "Not mine to change")
            for bad in ({"note": str(UUID(int=99)), "revision": 1, "body": "x"},
                        {"note": mine["id"], "revision": 0, "body": "x"},
                        {"note": mine["id"], "revision": 2, "body": "  "}):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    on_request({"op": "note_edit", **bad, "packet": packet, "mode": "continuous"})
            history = on_request({"op": "note_history", "note": mine["id"], "packet": packet,
                                  "mode": "continuous"})["note_history"]
            self.assertEqual([(row["revision"], row["kind"], row["lines"]) for row in history["revisions"]],
                             [(2, "edited", ["First thought, revised"]), (1, "created", ["First thought"])])
            # A corpus changed while editing refuses the save.
            source = self.corpus / "sample.md"
            source.write_text(source.read_text() + "\nAn unindexed edit.\n")
            with self.assertRaises(ValueError):
                edit(mine["id"], 2, "After the corpus changed")
            return 1, None

        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 1)
        note = service.store.get_annotation(mine["id"])
        self.assertEqual((note["body"], note["revision"], note["target_id"], note["content_sha256"]),
                         ("First thought, revised", 2, self.identifier, digest))
        self.assertEqual(service.store.get_annotation(theirs["id"])["body"], "Someone else's note")
        self.assertEqual(service.store.get_state(), state)

    def test_note_with_invisible_characters_is_shown_but_not_editable_in_the_reader(self):
        service = self.service()
        self.position(service, 0)
        digest = self.book.canonical_records[self.identifier]["content_sha256"]
        note = service.store.add_annotation(self.identifier, "Joined‍word", digest)

        def native(payload, _, on_request):
            [row] = payload["personal"]["notes"][self.identifier]
            self.assertEqual((row["lines"], row["body"]), (["Joined\\u200dword"], None))
            self.assertIn("sol --shell", row["edit_refusal"])
            with self.assertRaisesRegex(ValueError, "sol --shell"):
                on_request({"op": "note_edit", "note": note["id"], "revision": 1, "body": "Joined word",
                            "packet": payload["restore"], "mode": "continuous"})
            return 0, None

        with patch.object(neovim, "launch_payload", side_effect=native):
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

    def test_same_passage_occurrences_reuse_view_in_both_modes(self):
        self.extend(3)
        records = self.rows()
        records[1].update(markdown="界 target é target end.", plain_text="界 target é target end.")
        self.write_records(records)
        for mode in ("continuous", "paragraph"):
            with self.subTest(mode=mode):
                service = self.service(self.root / f"fast-{mode}.sqlite3")
                def native(payload, _, on_request):
                    def request(op, packet, **fields):
                        return on_request({"op": op, "packet": packet, "mode": mode, **fields})
                    packet = self.reply(payload, offset=0)["packet"]
                    request("search", packet, query="target")
                    shown = request("search_open", packet, result=1)["payload"]
                    first = shown["restore"]
                    with patch.object(neovim, "build_payload", side_effect=AssertionError("full view rebuilt")):
                        forward = request("search_next", first)
                        self.assertEqual(set(forward), {"position"})
                        second = forward["position"]["restore"]
                        self.assertEqual(second["cursor_offset"], 12)
                        self.assertEqual(forward["position"]["search_marks"]["position"], 2)
                        backward = request("search_previous", second)["position"]
                        self.assertEqual(backward["restore"], first)
                        self.assertEqual(backward["search_marks"]["position"], 1)
                        request("search_next", first)
                    back = request("history_back", second)["payload"]
                    self.assertEqual(back["restore"], first)
                    self.assertEqual(service.store.get_state()["position"]["cursor_offset"], first["cursor_offset"])
                    selected = deepcopy(first)
                    selected["selection"] = {"requested_id": self.identifier, "target_id": self.identifier,
                        "start": 2, "end": 8, "text": "target",
                        "content_sha256": first["reference"]["reference"]["content_sha256"],
                        "plain_text_sha256": shown["records"][0]["plain_text_sha256"]}
                    opened = request("search_next", selected)["position"]["restore"]
                    self.assertIsNone(opened["selection"])
                    back = request("history_back", opened)["payload"]
                    self.assertEqual(back["restore"], selected)
                    return 0, {"action": "quit", "packet": back["restore"]}
                with patch.object(neovim, "launch_payload", side_effect=native):
                    self.assertEqual(self.run_view(service), 0)

    def test_occurrence_from_retired_reference_prepares_canonical_identity(self):
        rows = self.rows()
        rows[1].update(markdown="target and target again", plain_text="target and target again")
        retired = deepcopy(rows[1])
        retired.update(id=RETIRED, type="retired_record", redirect_id=self.identifier, order=2,
                       markdown="An invented retired record.", plain_text="An invented retired record.")
        rows.append(retired)
        self.write_records(rows)
        service = self.service()
        self.position(service, 0, RETIRED)
        def native(payload, _, on_request):
            packet = payload["restore"]
            on_request({"op": "search", "query": "target", "packet": packet, "mode": "continuous"})
            result = on_request({"op": "search_next", "packet": packet, "mode": "continuous"})
            self.assertIn("payload", result)
            opened = result["payload"]["restore"]
            self.assertEqual(opened["reference"]["reference"]["requested_id"], self.identifier)
            self.assertEqual(opened["cursor_offset"], 11)
            return 0, {"action": "quit", "packet": opened}
        with patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)

    def test_same_passage_fast_path_refusals_keep_outgoing_position_and_allow_retry(self):
        self.extend(3)
        records = self.rows()
        records[1].update(markdown="target and target again", plain_text="target and target again")
        self.write_records(records)
        for failure in ("prepare", "save", "generation"):
            with self.subTest(failure=failure):
                service = self.service(self.root / f"fast-refused-{failure}.sqlite3")
                def native(payload, _, on_request):
                    def request(op, packet, **fields):
                        return on_request({"op": op, "packet": packet, "mode": "continuous", **fields})
                    packet = self.reply(payload, offset=0)["packet"]
                    request("search", packet, query="target")
                    shown = request("search_open", packet, result=1)["payload"]
                    origin = shown["restore"]
                    outgoing = deepcopy(origin)
                    outgoing["cursor_offset"] = 1
                    validate = neovim._safe_metadata
                    canonical = self.corpus / "sample.md"
                    original = canonical.read_bytes()
                    save = service.store.save_state
                    calls = []
                    def fail_save(*args, **kwargs):
                        calls.append(True)
                        if len(calls) == 2:
                            raise WorkspaceConflict("injected competing revision")
                        return save(*args, **kwargs)
                    def prepare(value):
                        validate(value)
                        if isinstance(value, dict) and "restore" in value and "search_marks" in value:
                            if failure == "prepare":
                                raise RuntimeError("injected position preparation failure")
                            if failure == "generation":
                                canonical.write_bytes(original + b"\n")
                    try:
                        with patch.object(neovim, "_safe_metadata", side_effect=prepare), \
                                patch.object(service.store, "save_state", side_effect=fail_save if failure == "save" else save):
                            with self.assertRaises((RuntimeError, ValueError)):
                                request("search_next", outgoing)
                    finally:
                        canonical.write_bytes(original)
                    saved = service.store.get_state()
                    self.assertEqual((saved["current_id"], saved["position"]["cursor_offset"]), (self.identifier, 1))
                    result = request("search_next", outgoing)["position"]
                    self.assertEqual(result["restore"]["cursor_offset"], 11)
                    back = request("history_back", result["restore"])["payload"]
                    self.assertEqual(back["restore"], outgoing)
                    return 0, {"action": "quit", "packet": back["restore"]}
                with patch.object(neovim, "launch_payload", side_effect=native):
                    self.assertEqual(self.run_view(service), 0)

    def test_complete_search_counts_and_steps_occurrences_across_sections(self):
        self.extend(25)
        def native(payload, _, on_request):
            def request(op, **fields):
                return on_request({"op": op, "packet": payload["restore"] or self.reply(payload)["packet"],
                                   "mode": "paragraph", **fields})
            result = request("search", query="invented")
            self.assertEqual(len(result["search"]["rows"]), 25)
            self.assertEqual(result["search"]["total"], 25)
            payload = request("search_open", result=25)["payload"]
            self.assertEqual(payload["search_marks"]["position"], 25)
            self.assertEqual(payload["search_marks"]["total"], 25)
            payload = request("search_next")["payload"]
            self.assertEqual(payload["search_marks"]["position"], 1)
            self.assertEqual(payload["restore"]["reference"]["reference"]["target_id"], self.identifier)
            payload = request("search_previous")["payload"]
            self.assertEqual(payload["search_marks"]["position"], 25)
            return 0, {"action": "quit", "packet": payload["restore"]}
        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)

    def test_printed_page_opens_its_first_paragraph_and_refuses_pages_outside_the_book(self):
        self.extend(3)
        passages = self.book.passages
        def native(payload, _, on_request):
            packet = self.reply(payload, record=2)["packet"]
            page = passages[-1].printed_page
            expected = next(row for row in passages if row.end_printed_page >= page)
            result = on_request({"op": "page_open", "page": page, "packet": packet, "mode": "continuous"})
            self.assertEqual(result["payload"]["restore"]["reference"]["reference"]["target_id"], expected.identifier)
            for outside in (passages[0].printed_page - 1, passages[-1].end_printed_page + 1):
                with self.subTest(page=outside), self.assertRaisesRegex(ValueError, "printed pages run from"):
                    on_request({"op": "page_open", "page": outside, "packet": packet, "mode": "continuous"})
            for bad in (0, "7", True, 7.0):
                with self.subTest(page=bad), self.assertRaises(ValueError):
                    on_request({"op": "page_open", "page": bad, "packet": packet, "mode": "continuous"})
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

    def test_refused_destination_view_keeps_the_shown_and_saved_position(self):
        """A destination whose view cannot be prepared is never saved or entered in history."""
        self.extend(3)
        records = self.rows()
        text = "Short one. This sentence is the longest one in the passage, by a clear margin of words."
        records[1].update(markdown=text, plain_text=text)
        self.write_records(records)
        build, adopt = neovim.build_payload, neovim.adopt_restore
        # Each live navigation route, with the request that makes it available first.
        routes = {"next": ({}, None), "previous": ({}, None),
                  "passage_next": ({}, None), "passage_previous": ({}, None),
                  "node_open": ({"node": "/"}, None), "marker_open": ({"slot": 1}, None),
                  "search_open": ({"result": 1}, {"op": "search", "query": "paragraph 2"}),
                  "search_next": ({}, {"op": "search", "query": "paragraph 2"}),
                  "search_previous": ({}, {"op": "search", "query": "paragraph 2"}),
                  "history_forward": ({}, [{"op": "passage_previous"}, {"op": "history_back"}]),
                  "history_back": ({}, {"op": "passage_previous"}),
                  "essence_source": ({"source": {"id": self.book.passages[2].identifier, "start": 0,
                                                 "content_sha256": core.capture_reference(
                                                     self.book.corpus_snapshot, self.book.passages[2].identifier
                                                 )["reference"]["content_sha256"]}}, None)}

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

                # A neighbouring section prepared ahead is adopted, not built.
                def adopt_or_fail(*args, **kwargs):
                    if failing:
                        raise RuntimeError("injected view preparation failure")
                    return adopt(*args, **kwargs)

                def native(payload, _, on_request):
                    shown = payload
                    for step in ([] if setup is None else setup if isinstance(setup, list) else [setup]):
                        shown = on_request({**step, "packet": shown["restore"],
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
                        patch.object(neovim, "adopt_restore", side_effect=adopt_or_fail), \
                        patch.dict(os.environ, XDG_DATA_HOME=str(self.root / "data")), \
                        patch.object(neovim, "launch_payload", side_effect=native):
                    self.assertEqual(self.run_view(service), 0)
                reopened = ReaderActions(self.book, service)
                reopened.restore()
                self.assertEqual(reopened.snapshot().current.identifier, service.store.get_state()["current_id"])
                self.assertEqual(reopened.snapshot().cursor_offset, 6)

    def test_refused_destination_leaves_mode_and_theme_for_the_next_view(self):
        self.extend(3)
        build, adopt = neovim.build_payload, neovim.adopt_restore
        failing, shown = [], []

        def build_or_fail(*args, **kwargs):
            if failing:
                raise RuntimeError("injected view preparation failure")
            return build(*args, **kwargs)

        def adopt_or_fail(*args, **kwargs):
            if failing:
                raise RuntimeError("injected view preparation failure")
            return adopt(*args, **kwargs)

        def native(payload, _, on_request):
            shown.append(payload)
            if len(shown) > 1:
                return 0, {"action": "quit", "packet": payload["restore"]}
            failing.append(True)
            with self.assertRaises(RuntimeError):
                on_request({"op": "passage_next", "packet": payload["restore"], "mode": "paragraph",
                            "focus": True, "theme": "mocha"})
            failing.clear()
            # Leaving the editor for the next section rebuilds the view from the
            # reader's own state, which the refused move must not have changed.
            return 0, {"action": "next", "packet": payload["restore"]}

        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "build_payload", side_effect=build_or_fail), \
                patch.object(neovim, "adopt_restore", side_effect=adopt_or_fail), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)
        first, second = shown
        self.assertEqual((second["mode"], second["focus"], second["theme"]),
                         (first["mode"], first["focus"], first["theme"]))
        self.assertEqual(second["records"][0]["id"], self.book.passages[1].identifier)

    def test_destination_checkpoint_failure_allows_retry_history_and_reopen(self):
        """Fail after projection, when the staged destination reaches storage."""
        self.extend(3)
        destination = self.book.passages[2].identifier
        for failure in (OSError("injected storage failure"), ValueError("injected CORE failure")):
            with self.subTest(failure=type(failure).__name__):
                service = self.service(self.root / f"checkpoint-{type(failure).__name__}.sqlite3")
                self.position(service, 4, self.book.passages[1].identifier)
                attempts = []
                capture = service._capture_position
                save = service.store.save_state

                def capture_position(session):
                    if isinstance(failure, ValueError) and session.current().identifier == destination:
                        attempts.append(destination)
                        raise failure
                    return capture(session)

                def save_state(values, expected_revision=None):
                    if isinstance(failure, OSError) and values["current_id"] == destination:
                        attempts.append(destination)
                        raise failure
                    return save(values, expected_revision=expected_revision)

                def native(payload, _, on_request):
                    origin = deepcopy(payload["restore"])
                    origin["cursor_offset"] = 6
                    request = {"op": "passage_next", "packet": origin, "mode": "continuous"}
                    with patch.object(service, "_capture_position", side_effect=capture_position), \
                            patch.object(service.store, "save_state", side_effect=save_state):
                        with self.assertRaisesRegex(type(failure), "injected"):
                            on_request(deepcopy(request))
                    self.assertEqual(attempts, [destination])
                    state = service.store.get_state()
                    self.assertEqual((state["current_id"], state["position"]["cursor_offset"]),
                                     (self.book.passages[1].identifier, 6))
                    opened = on_request(deepcopy(request))["payload"]["restore"]
                    self.assertEqual(opened["reference"]["reference"]["target_id"], destination)
                    back = on_request({"op": "history_back", "packet": opened,
                                       "mode": "continuous"})["payload"]["restore"]
                    self.assertEqual(back, origin)
                    # Reopen at the accepted destination, rather than only testing quit at origin.
                    again = on_request({"op": "history_forward", "packet": back,
                                        "mode": "continuous"})["payload"]["restore"]
                    self.assertEqual(again, opened)
                    return 0, {"action": "quit", "packet": again}

                with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                        patch.object(neovim, "launch_payload", side_effect=native):
                    self.assertEqual(self.run_view(service), 0)
                reopened = self.service(service.store.path)
                actions = ReaderActions(self.book, reopened)
                actions.restore()
                self.assertEqual(actions.snapshot().current.identifier, destination)
                self.assertEqual(actions.snapshot().cursor_offset, 0)

    def test_neighbouring_sections_are_prepared_ahead_and_equal_a_fresh_build(self):
        """Crossing a section boundary adopts a section prepared while reading, checked as a fresh one."""
        self.extend(4)
        service = self.service()
        self.position(service, 0, self.book.passages[1].identifier)
        build = neovim.build_payload
        calls = []

        def counted(*args, **kwargs):
            calls.append(args[0].passages[0].identifier)
            return build(*args, **kwargs)

        def native(payload, _, on_request):
            def move(op, packet, **fields):
                return on_request({"op": op, "packet": packet, "mode": "continuous", **fields})["payload"]
            # The opening screen prepared both neighbours.
            with patch.object(neovim, "build_payload", side_effect=AssertionError("prepared section rebuilt")):
                moved = move("passage_next", payload["restore"])
            self.assertEqual(moved["records"][0]["id"], self.book.passages[2].identifier)
            sample = Sample(self.book, (self.book.passages[2],), ReaderActions(self.book))
            fresh = build(sample, 72, moved["restore"], requested_ids={self.book.passages[2].identifier:
                                                                        self.book.passages[2].identifier})
            self.assertEqual(moved["records"], fresh["records"])
            self.assertEqual(moved["restore"], fresh["restore"])
            # Idle moments prepare the new neighbours, one section each, then rest.
            with patch.object(neovim, "build_payload", side_effect=counted):
                for _ in range(3):
                    on_request.idle()
            self.assertEqual(sorted(calls), sorted([self.book.passages[3].identifier,
                                                    self.book.passages[1].identifier]))
            with patch.object(neovim, "build_payload", side_effect=AssertionError("prepared section rebuilt")):
                back = move("passage_previous", moved["restore"])
            self.assertEqual(back["records"][0]["id"], self.book.passages[1].identifier)
            # Another theme shapes the view differently, so nothing prepared is reused.
            calls.clear()
            with patch.object(neovim, "build_payload", side_effect=counted):
                move("passage_next", back["restore"], theme="latte")
            self.assertEqual(calls, [self.book.passages[2].identifier])
            return 1, None

        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 1)

    def test_prepared_section_is_rebuilt_when_the_loaded_book_changed(self):
        """Adoption requires every book value a fresh build reads to be unchanged."""
        self.extend(4)

        def changed_text(book):
            book.passages[3] = replace(book.passages[3], text="Changed reader projection")

        def flagged(book):
            book.passages[2] = replace(book.passages[2], transcription_status="needs_review")

        def other_record(book):
            identifier = book.passages[3].identifier
            book.canonical_records[identifier] = {**book.canonical_records[identifier], "markdown": "Changed."}

        for edit, refused in ((changed_text, True), (flagged, False), (other_record, True)):
            with self.subTest(edit=edit.__name__):
                book = core.load_corpus_book(self.corpus)
                outcome = []

                def native(payload, _, on_request):
                    edit(book)
                    request = {"op": "next", "packet": payload["restore"], "mode": "continuous"}
                    if refused:
                        with self.assertRaises(ValueError):
                            on_request(request)
                    else:
                        outcome.append(on_request(request)["payload"])
                    return 1, None

                with patch.object(neovim_reader, "SECTION_BUDGET", 2), \
                        patch.object(neovim, "validate_environment", return_value="/invented/nvim"), \
                        patch.object(neovim, "launch_payload", side_effect=native):
                    self.assertEqual(neovim_reader.run_reader(book, None), 1)
                if not refused:
                    self.assertIn("Source transcription needs review.", outcome[0]["records"][0]["warnings"])

    def test_competing_save_during_destination_preparation_is_not_rolled_back(self):
        self.extend(3)
        service = self.service()
        self.position(service, 4)
        other = self.service(service.store.path)
        build, adopt = neovim.build_payload, neovim.adopt_restore
        competing_state = []

        def competing_save(prepare):
            def run(*args, **kwargs):
                prepared = prepare(*args, **kwargs)
                competing = ReaderActions(self.book, other)
                competing.restore()
                competing.open(self.book.passages[2].identifier)
                competing.set_cursor(9)
                competing.save_position()
                competing_state.append(other.store.get_state())
                return prepared
            return run

        def native(payload, _, on_request):
            request = {"op": "next", "packet": payload["restore"], "mode": "continuous"}
            # The destination view is built now or, prepared ahead, adopted now.
            with patch.object(neovim, "build_payload", side_effect=competing_save(build)), \
                    patch.object(neovim, "adopt_restore", side_effect=competing_save(adopt)):
                with self.assertRaises(WorkspaceConflict):
                    on_request(deepcopy(request))
            self.assertEqual(len(competing_state), 1)
            self.assertEqual(service.store.get_state(), competing_state[0])
            with self.assertRaises(WorkspaceConflict):
                on_request(deepcopy(request))
            self.assertEqual(service.store.get_state(), competing_state[0])
            return 1, None

        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 1)
        reopened = self.service(service.store.path)
        actions = ReaderActions(self.book, reopened)
        actions.restore()
        self.assertEqual(actions.snapshot().current.identifier, self.book.passages[2].identifier)
        self.assertEqual(actions.snapshot().cursor_offset, 9)

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

    def test_corpus_change_during_destination_preparation_refuses_commit(self):
        self.extend(3)
        service = self.service()
        self.position(service, 4)
        build, adopt = neovim.build_payload, neovim.adopt_restore

        def then_change_generation(prepare):
            def run(*args, **kwargs):
                prepared = prepare(*args, **kwargs)
                source = self.corpus / "sample.md"
                source.write_text(source.read_text() + "\nAn unindexed edit.\n")
                return prepared
            return run

        def native(payload, _, on_request):
            origin = deepcopy(payload["restore"])
            origin["cursor_offset"] = 6
            request = {"op": "next", "packet": origin, "mode": "continuous"}
            with patch.object(neovim, "build_payload", side_effect=then_change_generation(build)), \
                    patch.object(neovim, "adopt_restore", side_effect=then_change_generation(adopt)):
                with self.assertRaises(ValueError):
                    on_request(deepcopy(request))
            saved = service.store.get_state()
            self.assertEqual((saved["current_id"], saved["position"]["cursor_offset"]),
                             (self.identifier, 6))
            with self.assertRaises(ValueError):
                on_request(deepcopy(request))
            self.assertEqual(service.store.get_state(), saved)
            # A failed/crashed editor exits without writing a stale packet.
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

    def test_corpus_changed_between_two_requests_is_refused_without_saving(self):
        self.extend(3)
        service = self.service()
        self.position(service, 4)

        def native(payload, _, on_request):
            shown = on_request({"op": "next", "packet": payload["restore"], "mode": "continuous"})["payload"]
            saved = service.store.get_state()
            source = self.corpus / "sample.md"
            source.write_text(source.read_text() + "\nAn unindexed edit.\n")
            for operation in ("next", "previous", "passage_next"):
                with self.subTest(operation=operation), self.assertRaises(ValueError):
                    on_request({"op": operation, "packet": shown["restore"], "mode": "continuous"})
            self.assertEqual(service.store.get_state(), saved)
            return 1, None

        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 1)

    def test_essence_open_writes_a_private_context_without_book_text(self):
        from sol.interchange.essence import read_context

        self.extend(3)
        service = self.service()
        self.position(service, 4)
        state = service.store.get_state()
        state_home = self.root / "state"

        def native(payload, _, on_request):
            packet = self.packet(3, 14)
            launch = on_request({"op": "essence_open", "packet": packet, "mode": "continuous"})["essence"]
            command = launch["command"]
            self.assertEqual(command[:4], [sys.executable, "-m", "sol.essence.tui", "--context"])
            # Neovim's private directories are not ESSENCE's: studies go where the reader's go.
            self.assertEqual(launch["env"]["XDG_STATE_HOME"], str(state_home))
            self.assertEqual(launch["env"]["XDG_DATA_HOME"], os.environ.get("XDG_DATA_HOME", ""))
            self.assertEqual(set(launch["env"]), set(neovim_reader.ESSENCE_ENVIRONMENT))
            path = Path(command[4])
            # ESSENCE opens in the reader's theme.
            self.assertEqual(command[5], "--theme")
            self.assertIn(command[6], THEMES)
            # And follows T through an owner-only file the reader rewrites.
            self.assertEqual(command[7:], ["--theme-file", launch["theme_file"]])
            theme_file = Path(launch["theme_file"])
            self.assertEqual(theme_file.parent, path.parent)
            self.assertEqual(theme_file.read_text(encoding="utf-8"), command[6])
            self.assertEqual(theme_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            context = read_context(path)
            self.assertEqual(context["reference"], packet["reference"])
            self.assertEqual(context["cursor_offset"], packet["cursor_offset"])
            self.assertNotIn("text", context["selection"])
            self.assertEqual(context["selection"]["start"], 3)
            self.assertEqual(context["state_file"], str(state_home / "sol" / "essence" / "investigation.json"))
            self.assertNotIn(self.book.passages[0].text[3:14], path.read_text())
            with patch("sol.interchange.essence.textual_available", return_value=False), \
                    self.assertRaisesRegex(ValueError, "essence"):
                on_request({"op": "essence_open", "packet": packet, "mode": "continuous"})
            return 0, {"action": "quit", "packet": payload["restore"]}

        with patch.dict(os.environ, XDG_STATE_HOME=str(state_home)), \
                patch("sol.interchange.essence.textual_available", return_value=True), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        # Opening ESSENCE moved nothing and saved nothing.
        self.assertEqual(service.store.get_state()["current_id"], state["current_id"])

    def test_essence_source_opens_a_counted_passage_and_history_returns(self):
        self.extend(3)
        service = self.service()
        self.position(service, 4)
        passage = self.book.passages[2]
        counted = core.capture_reference(self.book.corpus_snapshot, passage.identifier)["reference"]["content_sha256"]

        def source(**changes):
            return {"id": passage.identifier, "start": 9, "content_sha256": counted, **changes}

        def native(payload, _, on_request):
            origin = payload["restore"]
            refusals = {"changed after ESSENCE counted": source(content_sha256="0" * 64),
                        "outside its passage": source(start=len(passage.text) + 1),
                        "choose a source passage": {"id": passage.identifier, "start": 9}}
            for message, refused in refusals.items():
                with self.subTest(refusal=message), self.assertRaisesRegex(ValueError, message):
                    on_request({"op": "essence_source", "source": refused, "packet": origin, "mode": "continuous"})
            with self.assertRaises(core.ProtocolError):
                on_request({"op": "essence_source", "source": source(id=str(UUID(int=99))), "packet": origin,
                            "mode": "continuous"})
            # The refusals moved nothing: the next request still starts from the origin.
            opened = on_request({"op": "essence_source", "source": source(), "packet": origin,
                                 "mode": "continuous"})["payload"]
            self.assertEqual(opened["restore"]["reference"]["reference"]["target_id"], passage.identifier)
            self.assertEqual(opened["restore"]["cursor_offset"], 9)
            back = on_request({"op": "history_back", "packet": opened["restore"], "mode": "continuous"})["payload"]
            self.assertEqual(back["restore"]["reference"]["reference"]["target_id"],
                             origin["reference"]["reference"]["target_id"])
            self.assertEqual(back["restore"]["cursor_offset"], origin["cursor_offset"])
            return 0, {"action": "quit", "packet": back["restore"]}

        with patch.object(neovim_reader, "SECTION_BUDGET", 1), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(service), 0)
        self.assertEqual(service.store.get_state()["current_id"], self.book.passages[0].identifier)

    def test_temporary_session_gives_essence_no_state_file(self):
        from sol.interchange.essence import read_context

        def native(payload, _, on_request):
            launch = on_request({"op": "essence_open", "packet": payload["restore"], "mode": "continuous"})
            self.assertIsNone(read_context(launch["essence"]["command"][4])["state_file"])
            self.assertIn("TMPDIR", launch["essence"]["env"])
            return 0, None

        with patch("sol.interchange.essence.textual_available", return_value=True), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(self.run_view(), 0)

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


class ClipboardCommandTests(unittest.TestCase):
    """The program the reader copies with, chosen from the real session."""

    @staticmethod
    def which(*available):
        return lambda name: f"/usr/bin/{name}" if name in available else None

    def test_the_session_decides_the_program_and_what_it_needs(self):
        wayland = {"WAYLAND_DISPLAY": "wayland-1", "XDG_RUNTIME_DIR": "/run/user/1000", "DISPLAY": ":0"}
        cases = {
            "wayland": (wayland, ("wl-copy", "xclip"), "linux",
                        {"command": ["/usr/bin/wl-copy", "--type", "text/plain"],
                         "env": {"WAYLAND_DISPLAY": "wayland-1", "XDG_RUNTIME_DIR": "/run/user/1000"}}),
            "x11 xclip": ({"DISPLAY": ":0", "XAUTHORITY": "/home/x/.Xauthority"}, ("xclip", "xsel"), "linux",
                          {"command": ["/usr/bin/xclip", "-selection", "clipboard"],
                           "env": {"DISPLAY": ":0", "XAUTHORITY": "/home/x/.Xauthority"}}),
            "x11 xsel": ({"DISPLAY": ":0"}, ("xsel",), "linux",
                         {"command": ["/usr/bin/xsel", "--clipboard", "--input"], "env": {"DISPLAY": ":0"}}),
            "wayland without wl-copy": (wayland, ("xclip",), "linux",
                                        {"command": ["/usr/bin/xclip", "-selection", "clipboard"],
                                         "env": {"DISPLAY": ":0"}}),
            "macos": ({}, ("pbcopy",), "darwin", {"command": ["/usr/bin/pbcopy"], "env": {}}),
            # No program: the reader falls back to the terminal (OSC 52).
            "ssh or console": ({}, ("wl-copy", "xclip"), "linux", None),
        }
        for name, (environment, available, platform, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(neovim.clipboard_command(environment, self.which(*available), platform), expected)

    def test_neovim_gets_the_choice_although_its_own_directories_are_private(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary, \
                patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1", "XDG_RUNTIME_DIR": "/run/user/1000"}), \
                patch.object(neovim.shutil, "which", self.which("wl-copy")):
            root = Path(temporary)
            environment = neovim._isolated_environment(root, root / "input", root / "output")
        self.assertEqual(environment["XDG_RUNTIME_DIR"], str(root / "runtime"))
        chosen = json.loads(environment["SOL_NVIM_CLIPBOARD"])
        self.assertEqual(chosen["env"]["XDG_RUNTIME_DIR"], "/run/user/1000")
