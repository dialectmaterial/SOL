"""Portable references bind existing canonical identity to an inspected generation."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol import core
from sol.corpus import contract
from fixtures_corpus import write_runtime_corpus


RETIRED_A = "cccccccc-0000-4000-8000-000000000003"
RETIRED_B = "dddddddd-0000-4000-8000-000000000004"
_GENERATED = {"markdown", "plain_text", "document", "context", "content_sha256"}


class CoreProtocolTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-protocol-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        self.identifier, self.body = write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.snapshot = core.load_snapshot(self.corpus)
        self.payload = core.capture_reference(self.snapshot, self.identifier)

    def test_batch_preserves_order_and_uses_one_verified_generation(self):
        identifiers = [self.identifier, self.snapshot.records[0]["id"], self.identifier]
        with patch.object(contract, "load_snapshot", wraps=contract.load_snapshot) as load:
            payloads = core.capture_references(self.snapshot, identifiers)
        self.assertLessEqual(load.call_count, 1)
        self.assertEqual([p["reference"]["requested_id"] for p in payloads], identifiers)
        self.assertEqual(payloads[0], self.payload)
        self.assertIsNot(payloads[0], payloads[2])
        with patch.object(contract, "load_snapshot", wraps=contract.load_snapshot) as load:
            refs = core.check_references(self.snapshot, payloads)
        self.assertLessEqual(load.call_count, 1)
        self.assertEqual([r.requested_id for r in refs], identifiers)

    def test_batch_refuses_bad_last_packet_and_generation_changes(self):
        bad = copy.deepcopy(self.payload)
        bad["generation"]["index_sha256"] = "0" * 64
        with self.assertRaises(core.ProtocolError):
            core.check_references(self.snapshot, [self.payload, bad])
        for operation in (lambda: core.capture_references(self.snapshot, [self.identifier] * 3),
                          lambda: core.check_references(self.snapshot, [self.payload] * 3)):
            with patch.object(contract, "verify_snapshot_current",
                              side_effect=contract.CorpusError("Changed during batch")), \
                    self.assertRaises(core.ProtocolError) as caught:
                operation()
            self.assertEqual(caught.exception.code, "generation_changed")

    def test_batch_input_is_bounded_and_not_a_lazy_callback(self):
        for value in ([], "not an ID collection", iter([self.identifier]),
                      [self.identifier] * (core.MAX_REFERENCE_BATCH + 1)):
            with self.subTest(value=type(value).__name__), self.assertRaises(core.ProtocolError) as caught:
                core.capture_references(self.snapshot, value)
            self.assertEqual(caught.exception.code, "batch_limit")

    def rewrite(self, modify):
        """Generate an invented, internally consistent fixture without Markdown extras."""
        manifest = json.loads((self.corpus / "corpus.json").read_text())
        records = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        modify(manifest, records)
        for record in records:
            record["content_sha256"] = hashlib.sha256(record["markdown"].encode()).hexdigest()
        markdown = "\n".join(contract.render_record(
            {key: value for key, value in row.items() if key not in _GENERATED}, row["markdown"])
            for row in records)
        manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode()
        index_bytes = ("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                               + "\n" for row in records)).encode()
        (self.corpus / "corpus.json").write_bytes(manifest_bytes)
        (self.corpus / "sample.md").write_text(markdown, encoding="utf-8")
        (self.corpus / "index.jsonl").write_bytes(index_bytes)
        (self.corpus / "index.meta.json").write_text(json.dumps({
            "contract_version": 1, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "source_sha256": manifest["source"]["sha256"],
            "documents": {"sample.md": hashlib.sha256(markdown.encode()).hexdigest()},
            "index_sha256": hashlib.sha256(index_bytes).hexdigest(), "record_count": len(records),
        }), encoding="utf-8")
        return core.load_snapshot(self.corpus)

    def assert_error(self, payload, status="invalid", code=None, snapshot=None):
        with self.assertRaises(core.ProtocolError) as caught:
            core.check_reference(snapshot or self.snapshot, payload)
        self.assertEqual(caught.exception.status, status)
        if code:
            self.assertEqual(caught.exception.code, code)

    def test_roundtrip_uses_existing_ids_and_returns_full_local_record_without_writes(self):
        before = {path.name: path.read_bytes() for path in self.corpus.iterdir() if path.is_file()}
        data = core.encode_reference(self.payload)
        reference = core.check_reference(self.snapshot, core.decode_reference(data))
        self.assertEqual(core.PROTOCOL_VERSION, 1)
        self.assertEqual(reference.requested_id, self.identifier)
        self.assertEqual(reference.target_id, self.identifier)
        self.assertEqual(reference.chain, (self.identifier,))
        self.assertEqual(reference.record["markdown"], self.body)
        self.assertNotIn(self.body, data)
        self.assertNotIn(str(self.corpus), data)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.corpus.iterdir() if path.is_file()})

    def test_capturing_prefix_emits_full_ids_and_defensive_copies(self):
        payload = core.capture_reference(self.snapshot, "BBBBBBBB")
        self.assertEqual(payload["reference"]["requested_id"], self.identifier)
        payload["reference"]["sources"][0]["printed_page"] = "changed"
        self.assertEqual(self.snapshot.records[1]["sources"][0]["printed_page"], "7")

    def test_complete_retirement_chain_retains_requested_uuid(self):
        def retire(manifest, records):
            for identifier, target in ((RETIRED_A, RETIRED_B), (RETIRED_B, self.identifier)):
                record = copy.deepcopy(records[1])
                record.update(id=identifier, order=len(records), type="retired_record", redirect_id=target,
                              markdown="An invented retired record.", plain_text="An invented retired record.")
                records.append(record)
        snapshot = self.rewrite(retire)
        payload = core.capture_reference(snapshot, RETIRED_A)
        reference = core.check_reference(snapshot, core.decode_reference(core.encode_reference(payload)))
        self.assertEqual(reference.chain, (RETIRED_A, RETIRED_B, self.identifier))
        self.assertEqual(payload["reference"]["requested_id"], RETIRED_A)
        self.assertEqual(payload["reference"]["target_id"], self.identifier)
        self.assertEqual(payload["reference"]["content_sha256"], snapshot.records[1]["content_sha256"])
        tampered = copy.deepcopy(payload)
        tampered["reference"]["chain"] = [RETIRED_A, self.identifier]
        self.assert_error(tampered, "mismatch", "record_mismatch", snapshot)

    def test_generic_editorial_records_and_roman_null_source_labels(self):
        for label in ("xv", None):
            def editorial(manifest, records):
                manifest["page_inventory"][-1]["printed_page"] = label
                for record in records:
                    record["sources"] = [{"pdf_page": 80, "printed_page": label, "bbox": [1, 2, 30.5, 40]}]
                    record["attribution"] = {"author": "Invented editor", "role": "editorial", "status": "declared"}
                records[1]["type"] = "note"
            snapshot = self.rewrite(editorial)
            for row in snapshot.records:
                with self.subTest(label=label, kind=row["type"]):
                    payload = core.capture_reference(snapshot, row["id"])
                    self.assertEqual(payload["reference"]["sources"][0]["printed_page"], label)
                    self.assertEqual(core.check_reference(snapshot, payload).record["type"], row["type"])

    def test_metadata_extras_are_hashed_or_omitted_not_leaked(self):
        def extra(manifest, records):
            manifest["edition"]["private"] = {"path": "/private/edition", "command": "NEVER_EXECUTE"}
            manifest["source"]["private"] = {"actor": "Secret"}
            records[1]["attribution"]["private"] = "Private attribution extra"
            records[1]["sources"][0]["private"] = "Private source extra"
        snapshot = self.rewrite(extra)
        payload = core.capture_reference(snapshot, self.identifier)
        encoded = core.encode_reference(payload)
        for value in ("/private/edition", "NEVER_EXECUTE", "Secret", "Private attribution extra", "Private source extra"):
            self.assertNotIn(value, encoded)
        self.assertNotEqual(payload["corpus"]["edition_sha256"], self.payload["corpus"]["edition_sha256"])
        self.assertEqual(core.check_reference(snapshot, payload).target_id, self.identifier)

    def test_foreign_lineage_edition_and_source_are_distinct_refusals(self):
        changes = [("id", RETIRED_A, "corpus_mismatch"),
                   ("edition_sha256", "0" * 64, "edition_mismatch"),
                   ("source", {"sha256": "1" * 64, "pdf_pages": 80}, "source_mismatch")]
        for key, value, code in changes:
            with self.subTest(key=key):
                payload = copy.deepcopy(self.payload)
                payload["corpus"][key] = value
                self.assert_error(payload, "mismatch", code)

    def test_tampered_record_text_type_provenance_or_attribution_is_rejected(self):
        changes = [("content_sha256", "0" * 64), ("type", "note"),
                   ("sources", [{"pdf_page": 80, "printed_page": "changed"}]),
                   ("attribution", {"author": "Someone else", "role": "main_text", "status": "confirmed"})]
        for key, value in changes:
            with self.subTest(key=key):
                payload = copy.deepcopy(self.payload)
                payload["reference"][key] = value
                self.assert_error(payload, "mismatch", "record_mismatch")

    def test_unrelated_correction_invalidates_old_packet_under_strict_generation_policy(self):
        snapshot = self.rewrite(lambda manifest, rows: rows[0].update(markdown="# A corrected invented title"))
        self.assert_error(self.payload, "stale", "generation_changed", snapshot)
        with self.assertRaises(core.ProtocolError) as caught:
            core.capture_reference(self.snapshot, self.identifier)
        self.assertEqual(caught.exception.code, "generation_changed")

    def test_invalid_disk_generation_and_mutated_memory_are_not_captured(self):
        for mutate in (lambda value: value.records[1].update(markdown="Misleading memory"),
                       lambda value: value.manifest["edition"].update(translator="Wrong translator")):
            snapshot = copy.deepcopy(self.snapshot)
            mutate(snapshot)
            with self.assertRaises(core.ProtocolError) as caught:
                core.capture_reference(snapshot, self.identifier)
            self.assertEqual(caught.exception.code, "snapshot_modified")
        (self.corpus / "sample.md").write_text("Changed without reindexing", encoding="utf-8")
        with self.assertRaises(core.ProtocolError) as caught:
            core.capture_reference(self.snapshot, self.identifier)
        self.assertEqual(caught.exception.status, "stale")

    def test_single_action_compares_memory_once_but_checks_files_on_every_call(self):
        from sol.core.protocol import single_action

        snapshot = copy.deepcopy(self.snapshot)
        with single_action(snapshot):
            core.capture_reference(snapshot, self.identifier)
            # Within the action, an in-memory change is not compared again...
            snapshot.records[1]["markdown"] = "Misleading memory"
            payload = core.capture_reference(snapshot, self.identifier)
            # ...but the result still comes from the verified files, not memory.
            self.assertEqual(payload, self.payload)
            # Another snapshot object inside the same action gets the full comparison.
            other = copy.deepcopy(snapshot)
            with self.assertRaises(core.ProtocolError) as caught:
                core.capture_reference(other, self.identifier)
            self.assertEqual(caught.exception.code, "snapshot_modified")
        # The next action refuses the modified snapshot.
        with single_action(snapshot), self.assertRaises(core.ProtocolError) as caught:
            core.check_reference(snapshot, self.payload)
        self.assertEqual(caught.exception.code, "snapshot_modified")
        # A file changed between two calls of one action is refused at once.
        with single_action(self.snapshot):
            core.capture_reference(self.snapshot, self.identifier)
            (self.corpus / "sample.md").write_text("Changed without reindexing", encoding="utf-8")
            with self.assertRaises(core.ProtocolError) as caught:
                core.check_reference(self.snapshot, self.payload)
            self.assertEqual(caught.exception.code, "generation_changed")

    def test_records_returned_inside_an_action_cannot_change_later_results(self):
        # Reported by Codex's review of PR #16.
        from sol.core.protocol import single_action

        for check in (lambda payload: core.check_reference(self.snapshot, payload),
                      lambda payload: core.check_references(self.snapshot, [payload, payload])[1]):
            with self.subTest(check=check), single_action(self.snapshot):
                returned = check(self.payload)
                returned.record["attribution"]["author"] = "Invented injected author"
                returned.record["sources"].append({"pdf_page": 999})
                later = core.capture_reference(self.snapshot, self.identifier)
                self.assertEqual(later, self.payload)
                self.assertEqual(check(later).record["attribution"], self.snapshot.records[
                    [row["id"] for row in self.snapshot.records].index(self.identifier)]["attribution"])
            self.assertEqual(core.check_reference(self.snapshot, self.payload).record["attribution"]["author"],
                             later["reference"]["attribution"]["author"])

    def test_fast_memory_comparison_refuses_changed_values_and_types(self):
        class Number(int):
            pass

        core.capture_reference(self.snapshot, self.identifier)  # A verified generation is cached.
        index = [row["id"] for row in self.snapshot.records].index(self.identifier)

        def changed(edit):
            snapshot = copy.deepcopy(self.snapshot)
            edit(snapshot.records[index])
            return snapshot

        refused = {
            "text": lambda row: row.update(markdown=row["markdown"] + " "),
            # Equal under ==, different as JSON: 2 versus 2.0 (or 1 versus true).
            "float for int": lambda row: row.update(order=float(row["order"])),
            "bool for int": lambda row: row.update(order=bool(row["order"])) if row["order"] in (0, 1) else
                row.update(order=float(row["order"])),
            "tuple for list": lambda row: row.update(sources=tuple(row["sources"])),
            "number key": lambda row: row.update({7: "x"}),
            "extra field": lambda row: row.update(invented="x"),
            "lone surrogate": lambda row: row.update(markdown="\ud800"),
        }
        for name, edit in refused.items():
            with self.subTest(name=name), self.assertRaises(core.ProtocolError):
                core.capture_reference(changed(edit), self.identifier)
        # Approved on 19 October 2026: an int subclass with an equal value passes.
        snapshot = changed(lambda row: row.update(order=Number(row["order"])))
        self.assertEqual(core.capture_reference(snapshot, self.identifier), self.payload)

    def test_corpus_metadata_nested_beyond_64_levels_is_refused_on_every_call(self):
        # Reported by Codex's review of PR #19.
        def deep(manifest, rows):
            nested = "end"
            for _ in range(70):
                nested = {"next": nested}
            rows[1]["invented_nesting"] = nested

        snapshot = self.rewrite(deep)
        for attempt in range(2):  # The first call loads; the second would use the cache.
            with self.subTest(attempt=attempt), self.assertRaises(core.ProtocolError) as caught:
                core.capture_reference(snapshot, self.identifier)
            self.assertEqual(caught.exception.code, "nesting_limit")

    def test_a_freshly_loaded_book_is_checked_without_reading_the_files_again(self):
        from sol.core import protocol

        protocol._VERIFIED_GENERATIONS.clear()
        book = core.load_corpus_book(self.corpus)
        with patch.object(contract, "load_snapshot", wraps=contract.load_snapshot) as load:
            self.assertEqual(core.capture_reference(book.corpus_snapshot, self.identifier), self.payload)
        self.assertEqual(load.call_count, 0)
        # The cached copy is still a guard: a later change in memory is refused.
        book.corpus_snapshot.records[1]["markdown"] = "Misleading memory"
        with self.assertRaises(core.ProtocolError) as caught:
            core.capture_reference(book.corpus_snapshot, self.identifier)
        self.assertEqual(caught.exception.code, "snapshot_modified")

    def test_a_book_beyond_the_nesting_bound_is_not_cached_and_still_refused(self):
        from sol.core import protocol

        def deep(manifest, rows):
            nested = "end"
            for _ in range(70):
                nested = {"next": nested}
            rows[1]["invented_nesting"] = nested

        self.rewrite(deep)
        protocol._VERIFIED_GENERATIONS.clear()
        snapshot = contract.load_snapshot(self.corpus)
        protocol.remember_verified(snapshot)
        self.assertEqual(protocol._VERIFIED_GENERATIONS, {})
        with self.assertRaises(core.ProtocolError) as caught:
            core.capture_reference(snapshot, self.identifier)
        self.assertEqual(caught.exception.code, "nesting_limit")

    def test_changed_files_during_capture_or_check_are_refused(self):
        with patch.object(contract, "verify_snapshot_current", side_effect=contract.CorpusError("Invented race")):
            for operation in (lambda: core.capture_reference(self.snapshot, self.identifier),
                              lambda: core.check_reference(self.snapshot, self.payload)):
                with self.subTest(operation=operation), self.assertRaises(core.ProtocolError) as caught:
                    operation()
                self.assertEqual(caught.exception.code, "generation_changed")

    def test_missing_identity_is_never_allocated(self):
        snapshot = self.rewrite(lambda manifest, rows: manifest.pop("corpus_id"))
        before = (self.corpus / "corpus.json").read_bytes()
        with self.assertRaises(core.ProtocolError) as caught:
            core.capture_reference(snapshot, self.identifier)
        self.assertEqual(caught.exception.code, "missing_corpus_identity")
        self.assertEqual(before, (self.corpus / "corpus.json").read_bytes())

    def test_unknown_identifier_and_untrusted_capture_strings_are_controlled(self):
        for identifier in ("deadbeef", "\x1b[31mBad", "$(never)", "", None):
            with self.subTest(identifier=identifier), self.assertRaises(core.ProtocolError):
                core.capture_reference(self.snapshot, identifier)

    def test_unknown_fields_are_rejected_at_every_protocol_owned_level(self):
        for subtree in ((), ("corpus",), ("corpus", "source"), ("generation",),
                        ("reference",), ("reference", "attribution")):
            with self.subTest(subtree=subtree):
                payload = copy.deepcopy(self.payload)
                node = payload
                for key in subtree:
                    node = node[key]
                node["command"] = "must never become authority"
                self.assert_error(payload)
        payload = copy.deepcopy(self.payload)
        payload["reference"]["sources"][0]["path"] = "/never/read"
        self.assert_error(payload)

    def test_bool_versions_pages_chain_errors_and_bad_coordinates_are_rejected(self):
        for mutate in (lambda p: p.update(version=True), lambda p: p.update(version=2),
                       lambda p: p["corpus"]["source"].update(pdf_pages=True),
                       lambda p: p["reference"]["sources"][0].update(pdf_page=True),
                       lambda p: p["reference"].update(chain=[]),
                       lambda p: p["reference"].update(chain=[self.identifier, self.identifier]),
                       lambda p: p["reference"]["sources"][0].update(bbox=[0, 0, True, 3]),
                       lambda p: p["reference"]["sources"][0].update(bbox=[0, 0, 10 ** 500, 3])):
            payload = copy.deepcopy(self.payload)
            mutate(payload)
            with self.subTest(payload=repr(payload)[0:100]):
                self.assert_error(payload)

    def test_strict_json_unicode_nonfinite_duplicates_and_depth(self):
        for data in (b"\xff", '{"version":1,"version":1}', '{"x":NaN}', '{"x":Infinity}',
                     '{"x":1e999}', '{"x":"\\ud800"}', "[" * 1500 + "0" + "]" * 1500):
            with self.subTest(data=repr(data)[0:60]), self.assertRaises(core.ProtocolError):
                core.decode_reference(data)
        data = core.encode_reference(self.payload)
        duplicate = data.replace('"author":', '"author": null, "author":', 1)
        with self.assertRaises(core.ProtocolError) as caught:
            core.decode_reference(duplicate)
        self.assertEqual(caught.exception.code, "duplicate_field")

    def test_wire_size_limit_is_bytes_and_accepts_exact_boundary(self):
        data = core.encode_reference(self.payload).encode()
        padded = data + b" " * (core.MAX_REFERENCE_BYTES - len(data))
        self.assertEqual(core.decode_reference(padded), self.payload)
        with self.assertRaises(core.ProtocolError) as caught:
            core.decode_reference(padded + b" ")
        self.assertEqual(caught.exception.code, "size_limit")
        huge = copy.deepcopy(self.payload)
        huge["reference"]["attribution"]["author"] = "α" * core.MAX_REFERENCE_BYTES
        with self.assertRaises(core.ProtocolError):
            core.encode_reference(huge)

    def test_wire_escaping_preserves_unicode_without_active_terminal_controls(self):
        payload = copy.deepcopy(self.payload)
        author = "Invented 漢字 α \x9b31m \u202e"
        payload["reference"]["attribution"]["author"] = author
        encoded = core.encode_reference(payload)
        self.assertTrue(all(ord(character) < 128 for character in encoded))
        self.assertEqual(core.decode_reference(encoded)["reference"]["attribution"]["author"], author)

    def test_protocol_import_and_decode_need_no_io_or_optional_frameworks(self):
        program = '''
import builtins, pathlib, sys
original = builtins.__import__
def guard(name, *args, **kwargs):
    if name.startswith(('sol.reader', 'sol.workspace', 'sol.terminal', 'sol.corpus',
                        'markdown_it', 'prompt_toolkit', 'opendataloader_pdf')):
        raise AssertionError('Protocol import loaded ' + name)
    return original(name, *args, **kwargs)
def no_io(*args, **kwargs):
    raise AssertionError('Import/decode performed data IO')
builtins.__import__ = guard
pathlib.Path.read_bytes = pathlib.Path.read_text = pathlib.Path.mkdir = no_io
from sol.core import PROTOCOL_VERSION, decode_reference, encode_reference
assert PROTOCOL_VERSION == 1
payload = decode_reference(sys.argv[1])
assert decode_reference(encode_reference(payload)) == payload
'''
        result = subprocess.run([sys.executable, "-B", "-c", program, core.encode_reference(self.payload)],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
