"""Invented corpora exercise ESSENCE without PDF extraction or optional tools."""
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
from sol.essence import (MAX_RESULT_BYTES, TermExperimentError, analyze_term,
                         check_term_result, decode_term_result, encode_term_result)
from test_packaging import write_runtime_corpus


_GENERATED = {"markdown", "plain_text", "document", "context", "content_sha256"}


class TermExperimentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-term-study-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        self.identifier, _ = write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.snapshot = self.rewrite(lambda manifest, rows: self.add_prose(rows))

    @staticmethod
    def add_prose(rows):
        bodies = [("BEING", "Ground is ground: grounding is not ground."),
                  ("ESSENCE", "An invented ground needs a reason."),
                  ("CONCEPT", "A concept has no foundation here.")]
        template = copy.deepcopy(rows[1])
        rows.pop()
        for number, (doctrine, body) in enumerate(bodies, 1):
            record = copy.deepcopy(template)
            record.update(id=f"bbbbbbbb-0000-4000-8000-{number:012d}", order=number,
                          reader_path=f"/{doctrine}/synthetic.txt", markdown=body, plain_text=body)
            rows.append(record)

    def rewrite(self, modify):
        manifest = json.loads((self.corpus / "corpus.json").read_text())
        rows = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        modify(manifest, rows)
        for row in rows:
            row["content_sha256"] = hashlib.sha256(row["markdown"].encode()).hexdigest()
        markdown = "\n".join(contract.render_record(
            {key: value for key, value in row.items() if key not in _GENERATED}, row["markdown"])
            for row in rows)
        manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode()
        index_bytes = ("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                               + "\n" for row in rows)).encode()
        (self.corpus / "corpus.json").write_bytes(manifest_bytes)
        (self.corpus / "sample.md").write_text(markdown, encoding="utf-8")
        (self.corpus / "index.jsonl").write_bytes(index_bytes)
        (self.corpus / "index.meta.json").write_text(json.dumps({
            "contract_version": 1, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "source_sha256": manifest["source"]["sha256"],
            "documents": {"sample.md": hashlib.sha256(markdown.encode()).hexdigest()},
            "index_sha256": hashlib.sha256(index_bytes).hexdigest(), "record_count": len(rows),
        }), encoding="utf-8")
        return core.load_snapshot(self.corpus)

    def test_full_distribution_normalizes_literal_query_and_denominators(self):
        result = analyze_term(self.snapshot, "GROUND")
        self.assertEqual(result["query"], "ground")
        self.assertEqual(result["totals"], {"passage_count": 3, "token_count": 19,
                                         "matching_passages": 2, "occurrences": 4,
                                         "rate_per_10000_tokens": 2105.263158})
        self.assertEqual([row["doctrine"] for row in result["groups"]], ["BEING", "ESSENCE", "CONCEPT"])
        self.assertEqual([row["occurrences"] for row in result["groups"]], [3, 1, 0])
        self.assertEqual(result["exclusions"]["by_reason"]["record_type"], 1)
        self.assertEqual(result["exclusions"]["input_records"], 4)
        self.assertEqual(result["corpus"], core.capture_reference(self.snapshot, self.snapshot.records[1]["id"])["corpus"])

    def test_limit_changes_examples_not_counts_and_retains_source_order(self):
        full = analyze_term(self.snapshot, "ground")
        short = analyze_term(self.snapshot, "ground", limit=1)
        self.assertEqual(full["totals"], short["totals"])
        self.assertEqual(full["groups"], short["groups"])
        self.assertTrue(short["matches_truncated"])
        self.assertFalse(full["matches_truncated"])
        self.assertEqual(short["matches"], full["matches"][:1])
        self.assertEqual(short["matches"][0]["id"], self.snapshot.records[1]["id"])

    def test_doctrine_selector_keeps_three_groups_and_discloses_scope(self):
        result = analyze_term(self.snapshot, "ground", doctrine="ESSENCE")
        self.assertEqual(result["totals"]["occurrences"], 1)
        self.assertEqual(result["totals"]["passage_count"], 1)
        self.assertEqual(result["exclusions"]["by_reason"]["doctrine"], 2)
        self.assertEqual([row["token_count"] for row in result["groups"]], [0, 6, 0])
        self.assertIsNone(result["groups"][0]["rate_per_10000_tokens"])

    def test_zero_matches_and_zero_tokens_have_explicit_rates(self):
        result = analyze_term(self.snapshot, "absent")
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["totals"]["rate_per_10000_tokens"], 0.0)
        snapshot = self.rewrite(lambda manifest, rows: [row.update(markdown="1234 !!!", plain_text="1234 !!!")
                                                      for row in rows[1:]])
        empty = analyze_term(snapshot, "ground")
        self.assertEqual(empty["totals"]["passage_count"], 3)
        self.assertEqual(empty["totals"]["token_count"], 0)
        self.assertIsNone(empty["totals"]["rate_per_10000_tokens"])
        self.assertEqual(check_term_result(snapshot, decode_term_result(encode_term_result(empty))), empty)

    def test_empty_verified_generation_needs_no_invented_anchor_record(self):
        def empty(manifest, rows):
            rows.clear()
            manifest["page_inventory"][-1].update(disposition="blank", reason="Invented blank page")
        snapshot = self.rewrite(empty)
        result = analyze_term(snapshot, "ground")
        self.assertEqual(result["totals"]["passage_count"], 0)
        self.assertEqual(result["exclusions"]["input_records"], 0)
        self.assertEqual(result["matches"], [])
        self.assertEqual(check_term_result(snapshot, result), result)

    def test_reader_view_requires_clean_absolute_virtual_text_leaf(self):
        for path in ("/BEING", "/BEING/folder", "/BEING//a.txt", "/BEING/../a.txt",
                     "/BEING/./a.txt", "/BEING/folder\\a.txt", "/being/a.txt", "/BEING/a.txt/",
                     "/BEING/chapter.txt/subsection.txt"):
            with self.subTest(path=path):
                snapshot = self.rewrite(lambda manifest, rows: rows[1].update(reader_path=path))
                result = analyze_term(snapshot, "ground")
                self.assertEqual(result["exclusions"]["by_reason"]["reader_path"], 1)
                self.assertEqual(result["totals"]["occurrences"], 1)

    def test_corpus_edition_and_source_bindings_are_independent_of_origin(self):
        result = analyze_term(self.snapshot, "absent")
        for field, value, code in (("id", "eeeeeeee-0000-4000-8000-000000000099", "corpus_mismatch"),
                                   ("edition_sha256", "1" * 64, "edition_mismatch"),
                                   ("source", {"sha256": "1" * 64, "pdf_pages": 80}, "source_mismatch")):
            payload = copy.deepcopy(result)
            payload["corpus"][field] = value
            with self.subTest(field=field), self.assertRaises(TermExperimentError) as caught:
                check_term_result(self.snapshot, payload)
            self.assertEqual(caught.exception.status, "mismatch")
            self.assertEqual(caught.exception.code, code)
        for mutate in (lambda value: value["corpus"].update(id="not a uuid"),
                       lambda value: value["generation"].update(index_sha256="bad hash")):
            payload = copy.deepcopy(result)
            mutate(payload)
            with self.assertRaises(TermExperimentError):
                decode_term_result(json.dumps(payload))

    def test_unicode_normalization_apostrophes_and_raw_offsets(self):
        text = "Préface: CAFE\u0301 café CAFÉ Straße STRASSE l’Idée l'idée. under_score co-ground 4ground4."
        snapshot = self.rewrite(lambda manifest, rows: rows[1].update(markdown=text, plain_text=text))
        for query, count in (("CAFÉ", 3), ("STRASSE", 2), ("l’IDÉE", 2), ("ground", 2)):
            result = analyze_term(snapshot, query, doctrine="BEING")
            self.assertEqual(result["totals"]["occurrences"], count)
            first = result["matches"][0]["first_match"]
            self.assertEqual(first["context"], text[first["context_start"]:first["context_end"]])
        result = analyze_term(snapshot, "café", doctrine="BEING")
        first = result["matches"][0]["first_match"]
        self.assertEqual(text[first["start"]:first["end"]], "CAFE\u0301")
        self.assertEqual(first["end"] - first["start"], 5)

    def test_context_is_bounded_without_rewriting_plain_text(self):
        text = "a " * 100 + "GROUND" + " z" * 100
        snapshot = self.rewrite(lambda manifest, rows: rows[1].update(markdown=text, plain_text=text))
        first = analyze_term(snapshot, "ground", doctrine="BEING")["matches"][0]["first_match"]
        self.assertEqual(first["start"] - first["context_start"], 80)
        self.assertEqual(first["context_end"] - first["end"], 80)
        self.assertEqual(len(first["context"]), 166)

    def test_nonmain_formula_review_and_unlocated_records_are_disclosed(self):
        def modify(manifest, rows):
            template = copy.deepcopy(rows[1])
            changes = [{"type": "formula"}, {"transcription_status": "needs_review"},
                       {"transcription_status": "needs_visual_review"},
                       {"attribution": {"author": "Invented editor", "role": "editorial", "status": "declared"}},
                       {"reader_path": "/INTRODUCTION/synthetic.txt"}, {"generated_text": True}]
            for change in changes:
                row = copy.deepcopy(template)
                row.update(id=f"cccccccc-0000-4000-8000-{len(rows):012d}", order=len(rows), **change)
                rows.append(row)
        snapshot = self.rewrite(modify)
        result = analyze_term(snapshot, "ground")
        self.assertEqual(result["totals"]["occurrences"], 4)
        self.assertEqual(result["exclusions"]["by_reason"],
                         {"attribution": 1, "record_type": 3, "review": 2, "reader_path": 1, "doctrine": 0})

    def test_list_items_and_quotations_are_eligible_but_attribution_is_not_inferred(self):
        def modify(manifest, rows):
            rows[1]["type"] = "list_item"
            rows[2]["type"] = "quotation"
            rows[3]["attribution"]["author"] = None
        snapshot = self.rewrite(modify)
        result = analyze_term(snapshot, "ground")
        self.assertEqual(result["totals"]["passage_count"], 2)
        self.assertEqual([row["type"] for row in result["matches"]], ["list_item", "quotation"])

    def test_generated_trailing_facsimile_labels_are_masked_only_at_exact_offsets(self):
        def modify(manifest, rows):
            row = rows[1]
            label = "Source facsimile, printed page 7"
            prose = f"The prose mentions {label}. Ground remains."
            row.update(markdown=f"{prose}\n\n![{label}](assets/{row['id']}-80.png)",
                       plain_text=f"{prose}\n{label}")
        snapshot = self.rewrite(modify)
        result = analyze_term(snapshot, "facsimile", doctrine="BEING")
        self.assertEqual(result["totals"]["occurrences"], 1)
        self.assertEqual(result["exclusions"]["masked_facsimile_captions"], 1)
        self.assertEqual(result["exclusions"]["masked_facsimile_tokens"], 4)
        first = result["matches"][0]["first_match"]
        self.assertEqual(first["start"], snapshot.records[1]["plain_text"].index("facsimile"))

    def test_ordinary_images_and_wrong_facsimile_filename_are_not_guessed(self):
        def modify(manifest, rows):
            rows[1].update(markdown="![Source facsimile, printed page 7](authored.png)",
                           plain_text="Source facsimile, printed page 7")
        snapshot = self.rewrite(modify)
        result = analyze_term(snapshot, "facsimile", doctrine="BEING")
        self.assertEqual(result["totals"]["occurrences"], 1)
        self.assertEqual(result["exclusions"]["masked_facsimile_captions"], 0)

    def test_origin_is_a_checked_context_not_scope_and_preserves_registered_redirect(self):
        def modify(manifest, rows):
            row = copy.deepcopy(rows[1])
            row.update(id="dddddddd-0000-4000-8000-000000000099", type="retired_record", order=4,
                       redirect_id=rows[2]["id"], markdown="Invented retirement.", plain_text="Invented retirement.")
            rows.append(row)
        snapshot = self.rewrite(modify)
        origin = core.capture_reference(snapshot, "dddddddd")
        result = analyze_term(snapshot, "ground", origin=origin)
        self.assertEqual(result["origin"], origin)
        self.assertEqual(result["totals"]["occurrences"], 4)
        self.assertEqual(result["origin"]["reference"]["requested_id"], "dddddddd-0000-4000-8000-000000000099")

    def test_foreign_or_corrupted_origin_is_refused(self):
        origin = core.capture_reference(self.snapshot, self.snapshot.records[1]["id"])
        for mutate in (lambda value: value["corpus"].update(id="eeeeeeee-0000-4000-8000-000000000099"),
                       lambda value: value["reference"].update(content_sha256="9" * 64)):
            payload = copy.deepcopy(origin)
            mutate(payload)
            with self.assertRaises(TermExperimentError) as caught:
                analyze_term(self.snapshot, "ground", origin=payload)
            self.assertEqual(caught.exception.status, "mismatch")

    def test_roundtrip_recomputes_defensive_result_without_writes_or_local_paths(self):
        before = {path.name: path.read_bytes() for path in self.corpus.iterdir()}
        result = analyze_term(self.snapshot, "ground")
        encoded = encode_term_result(result)
        fresh = check_term_result(self.snapshot, decode_term_result(encoded))
        self.assertEqual(fresh, result)
        self.assertIsNot(fresh, result)
        self.assertNotIn(str(self.corpus), encoded)
        fresh["matches"][0]["sources"][0]["printed_page"] = "Changed output"
        self.assertEqual(self.snapshot.records[1]["sources"][0]["printed_page"], "7")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.corpus.iterdir()})

    def test_metadata_extras_are_not_exported_as_authority(self):
        def modify(manifest, rows):
            rows[1]["sources"][0]["private_path"] = "/never/open"
            rows[1]["attribution"]["command"] = "NEVER_EXECUTE"
            manifest["edition"]["private"] = "private edition context"
        result = analyze_term(self.rewrite(modify), "ground")
        encoded = encode_term_result(result)
        for value in ("/never/open", "NEVER_EXECUTE", "private edition context"):
            self.assertNotIn(value, encoded)

    def test_invalid_queries_selectors_limits_and_snapshot_inputs_are_typed(self):
        for query in ("", "two words", "word-word", "_word", "4word", "word4", "'word", "word’", "\u0301word", None):
            with self.subTest(query=query), self.assertRaises(TermExperimentError):
                analyze_term(self.snapshot, query)
        for doctrine in ("being", "", True, {}, "/BEING"):
            with self.subTest(doctrine=doctrine), self.assertRaises(TermExperimentError):
                analyze_term(self.snapshot, "ground", doctrine=doctrine)
        for limit in (True, 0, -1, 101, 1.0, None):
            with self.subTest(limit=limit), self.assertRaises(TermExperimentError):
                analyze_term(self.snapshot, "ground", limit=limit)
        with self.assertRaises(TermExperimentError) as caught:
            analyze_term(object(), "ground")
        self.assertEqual(caught.exception.code, "unverified_snapshot")

    def test_missing_identity_and_modified_memory_are_not_repaired(self):
        changed = copy.deepcopy(self.snapshot)
        changed.records[1]["plain_text"] = "An invented fake ground ground ground"
        with self.assertRaises(TermExperimentError) as caught:
            analyze_term(changed, "ground")
        self.assertEqual(caught.exception.code, "snapshot_modified")
        snapshot = self.rewrite(lambda manifest, rows: manifest.pop("corpus_id"))
        before = (self.corpus / "corpus.json").read_bytes()
        with self.assertRaises(TermExperimentError) as caught:
            analyze_term(snapshot, "ground")
        self.assertEqual(caught.exception.code, "missing_corpus_identity")
        self.assertEqual(before, (self.corpus / "corpus.json").read_bytes())

    def test_stale_generation_is_refused_even_after_unrelated_heading_correction(self):
        result = analyze_term(self.snapshot, "ground")
        fresh = self.rewrite(lambda manifest, rows: rows[0].update(markdown="# Corrected invented heading"))
        with self.assertRaises(TermExperimentError) as caught:
            check_term_result(fresh, result)
        self.assertEqual(caught.exception.status, "stale")
        with self.assertRaises(TermExperimentError):
            analyze_term(self.snapshot, "ground")
        (self.corpus / "sample.md").write_text("Changed without reindexing")
        with self.assertRaises(TermExperimentError):
            analyze_term(fresh, "ground")

    def test_final_generation_guard_refuses_analysis_and_check_races(self):
        result = analyze_term(self.snapshot, "ground")
        with patch.object(core, "verify_snapshot_current", side_effect=core.CorpusError("Invented race")):
            for operation in (lambda: analyze_term(self.snapshot, "ground"),
                              lambda: check_term_result(self.snapshot, result)):
                with self.assertRaises(TermExperimentError) as caught:
                    operation()
                self.assertEqual(caught.exception.status, "stale")

    def test_modified_valid_counts_or_match_provenance_do_not_pass_recomputation(self):
        result = analyze_term(self.snapshot, "ground")
        for mutate in (lambda value: value["matches"][0]["sources"][0].update(printed_page="wrong"),
                       lambda value: value["matches"][0].update(content_sha256="1" * 64),
                       lambda value: value["matches"][0].update(occurrences=2),
                       lambda value: value.update(matches_truncated=True)):
            payload = copy.deepcopy(result)
            mutate(payload)
            with self.subTest(mutate=mutate), self.assertRaises(TermExperimentError) as caught:
                check_term_result(self.snapshot, payload)
            self.assertEqual(caught.exception.code, "result_mismatch")

    def test_unknown_fields_bool_numbers_and_unsupported_runtime_are_refused(self):
        result = analyze_term(self.snapshot, "ground")
        mutations = [lambda value: value.update(version=True), lambda value: value.update(limit=True),
                     lambda value: value["totals"].update(token_count=True),
                     lambda value: value["groups"][0].update(occurrences=True),
                     lambda value: value["matches"][0]["first_match"].update(start=True),
                     lambda value: value["exclusions"]["by_reason"].update(review=True),
                     lambda value: value["corpus"]["source"].update(pdf_pages=True),
                     lambda value: value["method"].update(unicode_version="0.0.0"),
                     lambda value: value["method"].update(context_codepoints=True),
                     lambda value: value["matches"][0].update(reader_path=""),
                     lambda value: value["matches"][0].update(type=[]),
                     lambda value: value["totals"].update(token_count=10 ** 1000)]
        for mutate in mutations:
            payload = copy.deepcopy(result)
            mutate(payload)
            with self.subTest(mutate=mutate), self.assertRaises(TermExperimentError):
                decode_term_result(json.dumps(payload))
        for path in ((), ("corpus",), ("generation",), ("method",), ("totals",), ("exclusions",),
                     ("matches", 0), ("matches", 0, "first_match"), ("matches", 0, "sources", 0)):
            payload = copy.deepcopy(result)
            node = payload
            for key in path:
                node = node[key]
            node["command"] = "must never become authority"
            with self.subTest(path=path), self.assertRaises(TermExperimentError):
                decode_term_result(json.dumps(payload))

    def test_duplicate_nonfinite_utf8_surrogates_and_deep_json_are_refused(self):
        for data in (b"\xff", '{"version":1,"version":1}', '{"x":NaN}', '{"x":Infinity}',
                     '{"x":1e999}', '{"x":"\\ud800"}', "[" * 1500 + "0" + "]" * 1500):
            with self.subTest(data=repr(data)[:50]), self.assertRaises(TermExperimentError):
                decode_term_result(data)

    def test_wire_size_limit_is_utf8_bytes_and_terminal_controls_are_escaped(self):
        result = analyze_term(self.snapshot, "ground")
        encoded = encode_term_result(result).encode()
        self.assertEqual(decode_term_result(encoded + b" " * (MAX_RESULT_BYTES - len(encoded))), result)
        with self.assertRaises(TermExperimentError) as caught:
            decode_term_result(encoded + b" " * (MAX_RESULT_BYTES + 1 - len(encoded)))
        self.assertEqual(caught.exception.code, "size_limit")
        text = "\x1b[31m\u202e Ground\x9b"
        snapshot = self.rewrite(lambda manifest, rows: rows[1].update(markdown=text, plain_text=text))
        packet = encode_term_result(analyze_term(snapshot, "ground"))
        self.assertTrue(all(ord(character) < 128 for character in packet))
        self.assertNotIn("\x1b", packet)

    def test_import_and_wire_decode_need_no_io_or_optional_frameworks(self):
        packet = encode_term_result(analyze_term(self.snapshot, "ground"))
        program = '''
import builtins, pathlib, sys
original = builtins.__import__
def guard(name, *args, **kwargs):
    if name.startswith(('sol.reader', 'sol.workspace', 'sol.terminal', 'sol.corpus',
                        'markdown_it', 'prompt_toolkit', 'numpy', 'sklearn')):
        raise AssertionError('Experiment import loaded ' + name)
    return original(name, *args, **kwargs)
def no_io(*args, **kwargs):
    raise AssertionError('Import/decode performed data IO')
builtins.__import__ = guard
pathlib.Path.read_bytes = pathlib.Path.read_text = pathlib.Path.mkdir = no_io
from sol.essence import decode_term_result, encode_term_result
payload = decode_term_result(sys.argv[1])
assert decode_term_result(encode_term_result(payload)) == payload
'''
        process = subprocess.run([sys.executable, "-B", "-c", program, packet], text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
