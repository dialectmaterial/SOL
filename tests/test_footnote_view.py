"""Book-note projections and controller requests over disposable source data."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from fixtures_corpus import CorpusFixture
from fixtures_footnotes import footnote_records
from sol import core
from sol.reader.surface import FOOTNOTE_DEPTH, footnote_scope, sample_from_book
from sol.terminal import neovim, neovim_reader
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace
from sol.core.paths import display_path, resolve_path
from sol.reader import app


class FootnoteViewTests(CorpusFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        rows = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        rows, self.notes, self.bodies = footnote_records(rows, self.identifier)
        self.write_records(rows)
        # A caller-owned mapping need not iterate in canonical reading order.
        self.book.canonical_records = dict(reversed(list(self.book.canonical_records.items())))
        self.sample = sample_from_book(self.book)

    def panel(self, trail=None):
        return neovim.build_footnote_payload(self.sample, self.identifier, trail or self.notes[:1])

    def test_body_order_styles_ids_attribution_warnings_and_callouts(self):
        before = self.files()
        panel = self.panel()
        self.assertEqual((panel["id"], panel["label"], panel["trail"]), (self.notes[0], "12", self.notes[:1]))
        self.assertEqual([row["id"] for row in panel["paragraphs"]], self.bodies)
        first, second = panel["paragraphs"]
        self.assertEqual((first["plain_text"], second["plain_text"]),
                         ("α first thought é.", "A second body.\nAnother line."))
        for row in panel["paragraphs"]:
            resolved = core.check_reference(self.book.corpus_snapshot, row["reference"])
            self.assertEqual((resolved.target_id, resolved.record["plain_text"]), (row["id"], row["plain_text"]))
        self.assertEqual(first["plain_text"][first["styles"][0]["start"]:first["styles"][0]["end"]], "first")
        self.assertEqual([second["plain_text"][span["start"]:span["end"]] for span in second["styles"]],
                         ["second", "line"])
        self.assertEqual(first["callouts"], [{"offset": len("α first thought"), "label": "7"}])
        self.assertEqual(panel["attribution"]["author"], "Invented translator")
        self.assertEqual(second["attribution"]["author"], "Another editor")
        self.assertEqual(second["warnings"], ["Note transcription needs review."])
        self.assertEqual(panel["links"], [{"id": self.notes[1], "label": "7", "refusal": ""}])
        self.assertEqual(before, self.files())

    def test_nested_cycles_depth_unlinked_and_unresolved_paths_are_explicit(self):
        nested = self.panel(self.notes[:2])
        cycle = next(link for link in nested["links"] if link["id"] == self.notes[0])
        self.assertIn("Cycle", cycle["refusal"])
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.panel(self.notes[:2] + self.notes[:1])
        for trail in ([], self.notes[:FOOTNOTE_DEPTH + 1], [1], "not a path"):
            with self.subTest(trail=trail), self.assertRaisesRegex(ValueError, "path"):
                neovim.build_footnote_payload(self.sample, self.identifier, trail)
        with self.assertRaisesRegex(ValueError, "not linked"):
            self.panel([self.notes[-1]])
        bound = self.panel(self.notes[:FOOTNOTE_DEPTH])
        self.assertIn("limited to 8", bound["links"][0]["refusal"])
        # A corrupt caller graph cannot turn an absent note into supplied prose.
        with patch.dict(self.book.canonical_records, clear=False):
            del self.book.canonical_records[self.notes[0]]
            with self.assertRaisesRegex(ValueError, "unresolved canonical footnote"):
                footnote_scope(self.book, self.identifier, self.notes[:1])

    def test_changed_source_and_detached_graph_never_supply_a_panel(self):
        self.book.canonical_records = deepcopy(self.book.canonical_records)
        original = deepcopy(self.book.canonical_records[self.bodies[0]])
        self.book.canonical_records[self.bodies[0]]["attribution"]["author"] = "An invented replacement"
        with self.assertRaises(ValueError):
            self.panel()
        self.book.canonical_records[self.bodies[0]] = original
        source = self.corpus / "sample.md"
        source.write_text(source.read_text() + "\nAn unindexed change.\n")
        with self.assertRaises(ValueError):
            self.panel()

    def test_source_changed_during_projection_is_refused_before_returning_text(self):
        original_styles = neovim._styles
        source = self.corpus / "sample.md"
        def changed(markdown, text):
            source.write_text(source.read_text() + "\nAn edit during projection.\n")
            return original_styles(markdown, text)
        with patch.object(neovim, "_styles", side_effect=changed), self.assertRaises(ValueError):
            self.panel()

    def test_body_and_text_budgets_refuse_without_truncating_source(self):
        from sol.reader import surface
        with patch.object(surface, "FOOTNOTE_PARAGRAPHS", 1), self.assertRaisesRegex(ValueError, "body paragraphs"):
            self.panel()
        with patch.object(neovim, "MAX_PACKET_BYTES", 4), self.assertRaisesRegex(ValueError, "view limit"):
            self.panel()
        with patch.object(neovim, "MAX_PACKET_BYTES", 64), self.assertRaisesRegex(ValueError, "presentation exceeds"):
            self.panel()
        with patch.object(neovim, "FOOTNOTE_LINKS", 0):
            panel = self.panel()
        self.assertEqual(panel["links"], [])
        self.assertIn("first 0 linked notes", panel["warnings"][0])
        self.assertEqual(panel["paragraphs"][0]["plain_text"], "α first thought é.")

    def test_controller_keeps_selected_origin_state_and_refuses_changed_corpus(self):
        store = Workspace(self.root / "reader.sqlite3", self.book.corpus_manifest["corpus_id"],
                          {key: self.book.corpus_manifest[key] for key in ("edition", "source")}, actor="Invented reader")
        self.addCleanup(store.close)
        service = WorkspaceReader(self.book, store, "Invented reader", resolve_path, display_path,
                                  app.render_passage, 72, False, False)
        from sol.reader.actions import ReaderActions
        actions = ReaderActions(self.book, service)
        actions.read((), first=True)
        actions.select_span(3, 14)
        actions.save_position()
        state = store.get_state()
        before = self.files()

        def native(payload, _, on_request):
            packet = payload["restore"]
            for trail in (self.notes[:1], self.notes[:2]):
                result = on_request({"op": "footnote_open", "trail": trail, "packet": packet, "mode": "paragraph"})
                self.assertEqual(result["footnote"]["id"], trail[-1])
                self.assertEqual(store.get_state(), state)
                self.assertEqual(payload["restore"], packet)
            for trail in ([self.notes[-1]], self.notes[:2] + self.notes[:1], self.notes[:9]):
                with self.assertRaises(ValueError):
                    on_request({"op": "footnote_open", "trail": trail, "packet": packet, "mode": "paragraph"})
            source = self.corpus / "sample.md"
            original = source.read_bytes()
            source.write_bytes(original + b"\nAn unindexed edit.\n")
            with self.assertRaises(ValueError):
                on_request({"op": "footnote_open", "trail": self.notes[:1], "packet": packet, "mode": "paragraph"})
            source.write_bytes(original)
            self.assertEqual(store.get_state(), state)
            return 1, None

        with patch.object(neovim, "validate_environment", return_value="/invented/nvim"), \
                patch.object(neovim, "launch_payload", side_effect=native):
            self.assertEqual(neovim_reader.run_reader(self.book, service), 1)
        self.assertEqual(before, self.files())
