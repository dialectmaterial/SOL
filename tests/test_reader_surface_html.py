"""Isolated typeset experiments keep canonical identity and local text inert.

These tests use only invented prose and a disposable, verified corpus. They do
not promote the transient experiment packet to a new CORE protocol or write a
workspace, installation, browser profile, or canonical project corpus.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import asdict
import hashlib
import json
import unittest
from unittest.mock import patch

from sol import core
from sol.core.corpus import load_corpus_book
from sol.corpus import contract
from sol.reader.actions import ReaderActions
from sol.reader.typography import Typography
from fixtures_corpus import CorpusFixture, _Document

from experiments.reader_surfaces.common import sample_from_book, selection_packet, validate_packet
from experiments.reader_surfaces.html import render_html, write_html


class ReaderSurfaceHTMLTests(CorpusFixture, unittest.TestCase):
    def test_packet_roundtrip_reuses_existing_textselection_without_writes(self):
        packet = self.packet()
        before = self.files()
        selected = validate_packet(self.book, json.loads(json.dumps(packet)))
        self.assertEqual(asdict(selected), packet["selection"])
        self.assertEqual(selected.text, self.body[3:14])
        self.assertEqual(self.files(), before)
        self.assertNotIn("protocol", {key for key in packet if key != "reference"})

    def test_position_only_packet_accepts_start_and_end_boundaries(self):
        packet = self.packet()
        packet["selection"] = None
        for offset in (0, len(self.body)):
            with self.subTest(offset=offset):
                packet["cursor_offset"] = offset
                self.assertIsNone(validate_packet(self.book, packet))

    def test_cursor_is_a_bounded_integer_codepoint_position(self):
        for offset in (True, False, 1.0, "1", None, -1, len(self.body) + 1):
            packet = self.packet()
            packet["cursor_offset"] = offset
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                validate_packet(self.book, packet)

    def test_packet_and_selection_shapes_are_exact_not_authority_containers(self):
        for level in ("packet", "selection"):
            for mode in ("missing", "unknown"):
                packet = self.packet()
                node = packet if level == "packet" else packet["selection"]
                if mode == "missing":
                    node.pop("cursor_offset" if level == "packet" else "text")
                else:
                    node["command"] = "must never be interpreted"
                with self.subTest(level=level, mode=mode), self.assertRaises(ValueError):
                    validate_packet(self.book, packet)
        for packet in (None, [], "not a packet", {"reference": {}}):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                validate_packet(self.book, packet)

    def test_selection_offsets_are_nonempty_bounded_integer_codepoints(self):
        for start, end in ((True, 5), (0, False), (1.0, 5), (0, "5"),
                           (-1, 5), (0, 0), (6, 5), (0, len(self.body) + 1)):
            packet = self.packet()
            packet["selection"].update(start=start, end=end)
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                validate_packet(self.book, packet)

    def test_selection_text_must_equal_the_exact_slice_not_a_repeated_match(self):
        self.rewrite_body("Repeated repeated and Repeated repeated.")
        packet = self.packet(0, 8)
        packet["selection"]["text"] = "repeated"
        with self.assertRaises(ValueError):
            validate_packet(self.book, packet)
        packet = self.packet(0, 8)
        packet["selection"].update(start=9, end=17)
        with self.assertRaises(ValueError):
            validate_packet(self.book, packet)

    def test_unicode_ranges_preserve_astral_and_combining_codepoints(self):
        self.rewrite_body("A🙂 e\u0301界 and repeated repeated.")
        for start, end, expected in ((1, 2, "🙂"), (3, 5, "e\u0301"),
                                      (4, 5, "\u0301"), (1, 6, "🙂 e\u0301界")):
            with self.subTest(start=start, end=end):
                selected = validate_packet(self.book, self.packet(start, end))
                self.assertEqual(selected.text, expected)
                self.assertEqual((selected.start, selected.end), (start, end))

    def test_normalizing_a_selected_slice_is_not_allowed(self):
        self.rewrite_body("A🙂 e\u0301界 and a tail.")
        packet = self.packet(3, 5)
        packet["selection"]["text"] = "é"
        with self.assertRaises(ValueError):
            validate_packet(self.book, packet)

    def test_selection_uuid_or_fingerprint_spoof_is_refused(self):
        changes = (("requested_id", "aaaaaaaa-0000-4000-8000-000000000001"),
                   ("target_id", "aaaaaaaa-0000-4000-8000-000000000001"),
                   ("requested_id", self.identifier.upper()),
                   ("content_sha256", "0" * 64), ("plain_text_sha256", "0" * 64))
        for key, value in changes:
            packet = self.packet()
            packet["selection"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_packet(self.book, packet)

    def test_reference_from_other_corpus_or_source_is_not_accepted(self):
        for key, value in (("id", "cccccccc-0000-4000-8000-000000000003"),
                           ("edition_sha256", "0" * 64),
                           ("source", {"sha256": "1" * 64, "pdf_pages": 80})):
            packet = self.packet()
            packet["reference"]["corpus"][key] = value
            with self.subTest(key=key), self.assertRaises(core.ProtocolError):
                validate_packet(self.book, packet)

    def test_stale_generation_is_refused_even_when_the_selected_text_survives(self):
        packet = self.packet()
        self.rewrite_body(self.body + " An unrelated tail was corrected.")
        with self.assertRaises(core.ProtocolError) as caught:
            validate_packet(self.book, packet)
        self.assertEqual(caught.exception.code, "generation_changed")

    def test_unindexed_disk_edits_are_refused_without_repair_or_workspace_writes(self):
        packet = self.packet()
        (self.corpus / "sample.md").write_text("Unindexed text", encoding="utf-8")
        before = self.files()
        with self.assertRaises(core.ProtocolError):
            validate_packet(self.book, packet)
        self.assertEqual(self.files(), before)

    def test_loaded_projection_mismatch_is_never_fuzzy_repaired(self):
        packet = self.packet()
        from dataclasses import replace
        self.book.passages[0] = replace(self.book.passages[0], text="Invented but wrong text")
        with self.assertRaises(ValueError):
            validate_packet(self.book, packet)

    def test_changed_display_provenance_is_refused_even_when_text_is_unchanged(self):
        from dataclasses import replace
        packet = self.packet()
        self.book.passages[0] = replace(self.book.passages[0], pdf_page=1)
        with self.assertRaises(ValueError):
            validate_packet(self.book, {**packet, "selection": None})
        with self.assertRaises(ValueError):
            render_html(sample_from_book(self.book, count=1))


    def test_detached_reader_graph_cannot_override_core_packet_source(self):
        self.detach_reader_graph()
        packet = self.packet()
        self.assertNotEqual(packet["reference"]["reference"]["content_sha256"],
                            packet["selection"]["content_sha256"])
        with self.assertRaises(ValueError):
            validate_packet(self.book, packet)

    def test_detached_reader_graph_cannot_be_exported_under_original_core_reference(self):
        self.detach_reader_graph()
        with self.assertRaises(ValueError):
            render_html(sample_from_book(self.book, count=1))

    def test_detached_reader_graph_cannot_generate_selected_span_packets(self):
        self.detach_reader_graph()
        with self.assertRaises(ValueError):
            selection_packet(self.book, self.identifier, 3, 14)

    def test_detached_reader_graph_cannot_validate_position_only_packets(self):
        packet = self.packet()
        packet["selection"], packet["cursor_offset"] = None, 0
        self.detach_reader_graph()
        with self.assertRaises(ValueError):
            validate_packet(self.book, packet)

    def test_linked_canonical_note_retains_attribution_and_stays_outside_passage(self):
        note_id = self.add_note()
        before = self.files()
        sample = sample_from_book(self.book, count=1)
        document = _Document(render_html(sample))
        visible = "".join(document.text)
        self.assertIn(self.book.canonical_records[note_id]["plain_text"], visible)
        self.assertIn("editorial_note: Invented translator", visible)
        self.assertIn("Canonical notes (outside selectable passage text)", visible)
        self.assertEqual(sample.passages[0].text, self.body)
        self.assertNotIn(self.book.canonical_records[note_id]["plain_text"], sample.passages[0].text)
        data = next(text for tag, attrs, text in document.blocks if attrs.get("id") == "sol-data")
        self.assertEqual([row["id"] for row in json.loads(data)["records"]], [self.identifier])
        self.assertEqual(self.files(), before)

    def test_detached_note_only_corruption_cannot_be_called_canonical(self):
        note_id = self.add_note()
        self.book.canonical_records = copy.deepcopy(self.book.canonical_records)
        text = "A detached note falsely claiming canonical provenance."
        self.book.canonical_records[note_id].update(
            markdown=text, plain_text=text,
            content_sha256=hashlib.sha256(text.encode()).hexdigest(),
            attribution={"author": "Wrong author", "role": "editorial_note", "status": "confirmed"})
        with self.assertRaises(ValueError):
            render_html(sample_from_book(self.book, count=1))

    def test_note_only_typography_disagreement_has_a_visible_plaintext_warning(self):
        note_id = self.add_note()
        note_text = self.book.canonical_records[note_id]["plain_text"]
        reason = "Invented note-only projection disagreement; plain note text shown."

        def project(markdown, plain_text):
            return Typography(degraded=True, reason=reason) if plain_text == note_text else Typography()

        with patch("experiments.reader_surfaces.html.map_typography", side_effect=project):
            document = _Document(render_html(sample_from_book(self.book, count=1)))
        visible = "".join(document.text)
        self.assertIn(reason, visible)
        self.assertIn(note_text, visible)
        self.assertEqual(visible.count(reason), 1)

    def test_html_rendering_and_packet_validation_do_not_change_reader_state(self):
        sample = sample_from_book(self.book, count=1)
        sample.actions.set_cursor(10)
        sample.actions.select_span(5, 10)
        before_state = sample.actions.snapshot()
        before_files = self.files()
        output = render_html(sample)
        self.assertIn("<!doctype html", output.lower())
        self.assertEqual(sample.actions.snapshot(), before_state)
        self.assertEqual(self.files(), before_files)

    def test_script_shaped_source_stays_text_not_active_markup(self):
        text = '<script>alert("invented")</script> & <img src="https://invalid.test/x" onerror="alert(1)">'
        self.rewrite_body(text, markdown="`" + text + "`")
        document = _Document(render_html(sample_from_book(self.book, count=1)))
        for tag, attributes in document.elements:
            self.assertNotIn(tag, {"img", "iframe", "object", "embed", "base", "form"})
            self.assertFalse(any(key.lower().startswith("on") for key in attributes))
            self.assertNotIn("src", attributes)
        executable = [text for tag, attrs, text in document.blocks if tag == "script"
                      and attrs.get("type", "").lower() != "application/json"]
        self.assertTrue(executable)
        self.assertTrue(all('alert("invented")' not in text for text in executable))

    def test_csp_is_early_and_fixed_executable_blocks_are_hash_authorized(self):
        document = _Document(render_html(sample_from_book(self.book, count=1)))
        policies = [(index, attrs["content"]) for index, (tag, attrs) in enumerate(document.elements)
                    if tag == "meta" and attrs.get("http-equiv", "").lower() == "content-security-policy"]
        self.assertEqual(len(policies), 1)
        index, policy = policies[0]
        for directive in ("default-src 'none'", "connect-src 'none'", "base-uri 'none'",
                          "form-action 'none'", "object-src 'none'"):
            self.assertIn(directive, policy)
        self.assertNotIn("unsafe-inline", policy)
        self.assertNotIn("unsafe-eval", policy)
        self.assertLess(index, next(i for i, item in enumerate(document.elements) if item[0] == "script"))
        for tag, attrs, text in document.blocks:
            if attrs.get("type", "").lower() == "application/json":
                continue
            digest = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
            self.assertIn("'sha256-" + digest + "'", policy, tag)

    def test_generated_document_contains_no_automatic_remote_resources(self):
        document = _Document(render_html(sample_from_book(self.book, count=1)))
        for tag, attrs in document.elements:
            for name in ("src", "srcset", "poster", "action", "ping"):
                self.assertNotIn(name, attrs, (tag, name))
            if tag == "link":
                self.assertNotIn("href", attrs)
        source = "\n".join(text for tag, attrs, text in document.blocks if tag in {"script", "style"})
        for value in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "serviceWorker", "@import", "url("):
            self.assertNotIn(value, source)

    def test_html_controls_are_refused_not_silently_deleted_or_replaced(self):
        # CR cannot survive the canonical Markdown reader's existing universal
        # newline handling, so exercise controls that are valid indexed text.
        for control in ("\x00", "\x1b", "\x0b", "\u202e"):
            self.rewrite_body("Before" + control + "after.")
            before = self.files()
            with self.subTest(control=repr(control)), self.assertRaises(ValueError):
                render_html(sample_from_book(self.book, count=1))
            self.assertEqual(self.files(), before)

    def test_writing_is_explicit_and_existing_files_are_never_overwritten(self):
        sample = sample_from_book(self.book, count=1)
        output = self.root / "reader.html"
        write_html(sample, output)
        self.assertEqual(output.read_text(encoding="utf-8"), render_html(sample))
        output.write_text("A user's existing file", encoding="utf-8")
        with self.assertRaises((ValueError, FileExistsError)):
            write_html(sample, output)
        self.assertEqual(output.read_text(encoding="utf-8"), "A user's existing file")

    def test_existing_output_symlink_is_not_followed(self):
        target = self.root / "user.txt"
        target.write_text("Keep this", encoding="utf-8")
        output = self.root / "reader.html"
        output.symlink_to(target)
        with self.assertRaises((ValueError, FileExistsError)):
            write_html(sample_from_book(self.book, count=1), output)
        self.assertEqual(target.read_text(encoding="utf-8"), "Keep this")
        self.assertTrue(output.is_symlink())


if __name__ == "__main__":
    unittest.main()
