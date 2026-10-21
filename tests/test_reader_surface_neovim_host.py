"""Native Neovim hosting uses disposable invented sources, never user state."""
from __future__ import annotations

from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sol import core
from sol.reader.typography import Typography

from experiments.reader_surfaces import neovim
from experiments.reader_surfaces.common import sample_from_book, selection_packet
import fixtures_corpus as fixtures


class NeovimHostTests(fixtures.CorpusFixture, unittest.TestCase):

    def sample(self, count=1):
        return sample_from_book(self.book, count=count)

    def packet(self):
        return selection_packet(self.book, self.identifier, 3, 14)

    def terminal(self, *, term="xterm-256color", stdin=True, stdout=True, version="NVIM v0.11.6\n"):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(neovim.sys, "stdin", SimpleNamespace(isatty=lambda: stdin)))
        stack.enter_context(patch.object(neovim.sys, "stdout", SimpleNamespace(isatty=lambda: stdout)))
        stack.enter_context(patch.dict(os.environ, TERM=term))
        stack.enter_context(patch.object(neovim.shutil, "which", return_value="/invented/bin/nvim"))
        runner = stack.enter_context(patch.object(neovim.subprocess, "run", return_value=SimpleNamespace(
            returncode=0, stdout=version, stderr="")))
        return runner

    def launch(self, *, packet=None, code=0, operation=None, **options):
        """Run the real host wrapper around a fake native executable."""
        observed = {}

        def native(command, **kwargs):
            observed.update(command=command, **kwargs)
            root = Path(kwargs["cwd"])
            observed["root_mode"] = stat.S_IMODE(root.stat().st_mode)
            input_path = Path(kwargs["env"]["SOL_NVIM_INPUT"])
            observed["input_mode"] = stat.S_IMODE(input_path.stat().st_mode)
            observed["payload"] = json.loads(input_path.read_text(encoding="utf-8"))
            output_path = Path(kwargs["env"]["SOL_NVIM_OUTPUT"])
            self.assertFalse(output_path.exists())
            if packet is not None:
                output_path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
            if operation is not None:
                operation(command, kwargs)
            return SimpleNamespace(returncode=code)

        with patch.object(neovim, "validate_environment", return_value="/invented/bin/nvim"), \
                patch.object(neovim.subprocess, "run", side_effect=native):
            result = neovim.run(self.sample(), **options)
        return result, observed

    def test_payload_exact_unicode_text_and_reference_without_source_mutation(self):
        self.rewrite_body("Greek λ, CJK 界, astral 🙂 and combining e\u0301.\nA\ttab remains exact.")
        before = self.files()
        payload = neovim.build_payload(self.sample())
        row = payload["records"][0]
        self.assertEqual(row["plain_text"], self.body)
        checked = core.check_reference(self.book.corpus_snapshot, row["reference"])
        self.assertEqual(checked.record["plain_text"], self.body)
        self.assertEqual(row["heading"], "Synthetic section")
        self.assertEqual(row["context"]["path"], "/BEING/synthetic.txt")
        self.assertEqual(row["context"]["printed_pages"], [7, 7])
        self.assertEqual(row["context"]["pdf_pages"], [80, 80])
        self.assertIsNone(payload["restore"])
        self.assertEqual(self.files(), before)

    def test_semantic_styles_remain_codepoint_spans_not_ansi_text(self):
        self.rewrite_body("λ 🙂 visible emphasis and strong.", markdown="λ 🙂 visible *emphasis* and **strong**.")
        payload = neovim.build_payload(self.sample())
        row = payload["records"][0]
        self.assertNotIn("\x1b", row["plain_text"])
        self.assertNotIn("*", row["plain_text"])
        if row["styles"]:
            styled = [(self.body[span["start"]:span["end"]], span["styles"]) for span in row["styles"]]
            self.assertIn(("emphasis", ["emphasis"]), styled)
            self.assertIn(("strong", ["strong"]), styled)
        else:
            self.assertTrue(row["warnings"], "missing optional parser must degrade visibly")

    def test_payload_parses_each_record_once_for_styles_and_callouts(self):
        project = neovim.map_typography
        sample = self.sample()
        with patch.object(neovim, "map_typography", wraps=project) as mapped:
            neovim.build_payload(sample)
        self.assertEqual(mapped.call_count, len(sample.passages))

    def test_typography_reuse_follows_exact_values_and_matches_fresh_payload(self):
        from functools import lru_cache
        project = lru_cache(maxsize=256)(neovim.map_typography)
        for markdown, plain in (("A *thought*.", "A thought."),
                                ("A **thought**.", "A thought."),
                                ("A **claim**.", "A claim.")):
            with self.subTest(markdown=markdown):
                self.rewrite_body(plain, markdown=markdown)
                sample = self.sample()
                reused = neovim.build_payload(sample, _typography=project)
                self.assertEqual(reused, neovim.build_payload(sample))
                self.assertEqual(reused, neovim.build_payload(sample, _typography=project))
        self.assertEqual(project.cache_info().misses, 3)
        self.assertEqual(project.cache_info().hits, 3)

    def test_source_safety_scan_preserves_unicode_policy(self):
        import unicodedata
        # Every codepoint in the categories the old scan refused, including
        # supplementary format controls and surrogates; allowed text is exact.
        for codepoint in range(0x110000):
            char = chr(codepoint)
            category = unicodedata.category(char)
            if category not in {"Cc", "Cf", "Cs", "Zl", "Zp"}:
                continue
            text = "A" + char + "界"
            if char in "\n\t" or 0x80 <= codepoint <= 0x9f:
                neovim._safe_source(text)
            else:
                with self.assertRaises(ValueError, msg=f"U+{codepoint:04X}"):
                    neovim._safe_source(text)
        neovim._safe_source("λ 🙂 e\u0301 and 界")

    def test_unknown_terminal_falls_back_to_visible_underline(self):
        for term, expected in (("unknown-basic", "underline"), ("alacritty", "italic"),
                               ("xterm-kitty", "italic")):
            with self.subTest(term=term), patch.dict(os.environ, TERM=term):
                self.assertEqual(neovim.build_payload(self.sample())["emphasis"], expected)

    def test_typography_failure_keeps_exact_text_with_explicit_warning(self):
        with patch.object(neovim, "map_typography", return_value=Typography(degraded=True, reason="Invented parser unavailable")):
            row = neovim.build_payload(self.sample())["records"][0]
        self.assertEqual(row["styles"], [])
        self.assertEqual(row["warnings"], ["Invented parser unavailable"])
        self.assertEqual(row["plain_text"], self.body)

    def test_notes_remain_separately_attributed_and_checked(self):
        note_id = self.add_note()
        before = self.files()
        row = neovim.build_payload(self.sample())["records"][0]
        self.assertEqual(row["plain_text"], self.body)
        self.assertEqual(len(row["notes"]), 1)
        note = row["notes"][0]
        self.assertEqual(note["attribution"]["author"], "Invented translator")
        checked = core.check_reference(self.book.corpus_snapshot, note["reference"])
        self.assertEqual(checked.target_id, note_id)
        self.assertEqual(checked.record["plain_text"], note["plain_text"])
        self.assertEqual(self.files(), before)

    def test_converted_footnote_shows_its_body_paragraphs_not_only_its_heading(self):
        note_id = self.add_note()
        records = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        note = next(row for row in records if row["id"] == note_id)
        note.update(label="7", markdown="#### Note 7", plain_text="Note 7")
        for index, (markdown, text) in enumerate((("A *first* invented body.", "A first invented body."),
                                                  ("A second body.", "A second body."))):
            body = copy.deepcopy(note)
            body.pop("backlinks"); body.pop("label")
            body.update(id=f"cccccccc-0000-4000-8000-00000000001{index}", type="note_paragraph",
                        parent_id=note_id, order=len(records), markdown=markdown, plain_text=text)
            records.append(body)
        self.write_records(records)
        [shown] = neovim.build_payload(self.sample())["records"][0]["notes"]
        self.assertEqual(shown["label"], "7")
        self.assertEqual(shown["plain_text"], "A first invented body.\n\nA second body.")
        if shown["styles"]:
            span = shown["styles"][0]
            self.assertEqual(shown["plain_text"][span["start"]:span["end"]], "first")
        self.assertEqual(core.check_reference(self.book.corpus_snapshot, shown["reference"]).target_id, note_id)

    def test_source_review_warning_is_preserved(self):
        records = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        next(row for row in records if row["id"] == self.identifier)["transcription_status"] = "needs_visual_review"
        self.write_records(records)
        self.assertIn("Source transcription needs review.", neovim.build_payload(self.sample())["records"][0]["warnings"])

    def test_unsafe_control_source_is_refused_not_repaired(self):
        for char in ("\0", "\r", "\x1b", "\u202e", "\u200b", "\u2028"):
            with self.subTest(char=repr(char)):
                self.rewrite_body("An invented " + char + " source.")
                before = self.files()
                with self.assertRaisesRegex(ValueError, "control/bidi"):
                    neovim.build_payload(self.sample())
                self.assertEqual(self.files(), before)

    def test_workspace_binding_and_duplicate_records_are_refused(self):
        sample = self.sample()
        with patch.object(sample.actions, "workspace_reader", object()), self.assertRaisesRegex(ValueError, "workspace"):
            neovim.build_payload(sample)
        from experiments.reader_surfaces.common import Sample
        duplicate = Sample(sample.book, sample.passages * 2, sample.actions)
        with self.assertRaisesRegex(ValueError, "distinct"):
            neovim.build_payload(duplicate)

    def test_source_changed_during_projection_fails_before_any_launch(self):
        project = neovim.map_typography
        def changed(markdown, text):
            result = project(markdown, text)
            source = self.corpus / "sample.md"
            source.write_text(source.read_text() + "\nInvented unindexed edit.\n")
            return result
        with patch.object(neovim, "map_typography", side_effect=changed), self.assertRaises(ValueError):
            neovim.build_payload(self.sample())

    def test_restore_is_deep_copied_and_uses_existing_exact_selection(self):
        packet = self.packet()
        payload = neovim.build_payload(self.sample(), restore=packet)
        self.assertEqual(payload["restore"], packet)
        packet["selection"]["text"] = "Changed caller data"
        self.assertNotEqual(payload["restore"], packet)

    def test_restore_invalid_text_or_nonboundary_cursor_is_refused(self):
        for field, value in (("text", "Wrong selected text"), ("start", 0)):
            packet = self.packet()
            packet["selection"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                neovim.build_payload(self.sample(), restore=packet)
        packet = self.packet()
        packet["cursor_offset"] = 8
        with self.assertRaises(ValueError):
            neovim.build_payload(self.sample(), restore=packet)

    def test_restore_other_readable_record_is_not_silently_substituted(self):
        records = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        second = copy.deepcopy(next(row for row in records if row["id"] == self.identifier))
        second.update(id="cccccccc-0000-4000-8000-000000000003", order=2,
                      markdown="A distinct invented paragraph.", plain_text="A distinct invented paragraph.")
        records.append(second)
        self.write_records(records)
        packet = selection_packet(self.book, second["id"], 0, 5)
        with self.assertRaisesRegex(ValueError, "outside"):
            neovim.build_payload(self.sample(), restore=packet)

    def test_width_is_bounded_integer_not_terminal_pixels(self):
        for width in (True, 19, 241, 72.0, "72", None):
            with self.subTest(width=width), self.assertRaises(ValueError):
                neovim.build_payload(self.sample(), width=width)
        for width in (20, 72, 240):
            with self.subTest(width=width):
                self.assertEqual(neovim.build_payload(self.sample(), width=width)["width"], width)

    def test_preflight_rejects_redirected_or_dumb_terminal_before_version_probe(self):
        for terminal in ({"stdin": False}, {"stdout": False}, {"term": "dumb"}, {"term": ""}):
            with self.subTest(terminal=terminal):
                runner = self.terminal(**terminal)
                with self.assertRaisesRegex(ValueError, "interactive terminal"):
                    neovim.validate_environment()
                runner.assert_not_called()

    def test_preflight_missing_or_unsupported_nvim_has_clear_error(self):
        runner = self.terminal()
        with patch.object(neovim.shutil, "which", return_value=None), self.assertRaisesRegex(ValueError, "0.11"):
            neovim.validate_environment()
        runner.assert_not_called()
        for version in ("NVIM v0.10.4\n", "VIM v9.0\n", ""):
            runner.return_value.stdout = version
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "0.11"):
                neovim.validate_environment()

    def test_version_probe_is_isolated_and_does_not_touch_user_log_or_config(self):
        runner = self.terminal()
        with patch.dict(os.environ, NVIM_LOG_FILE="/unrelated/private/log", VIMINIT="untrusted init", NVIM="/unrelated/server"):
            executable = neovim.validate_environment()
        self.assertEqual(executable, "/invented/bin/nvim")
        command, = runner.call_args.args
        options = runner.call_args.kwargs
        self.assertEqual(command, ["/invented/bin/nvim", "--version"])
        self.assertNotIn("VIMINIT", options["env"])
        self.assertNotIn("NVIM", options["env"])
        self.assertEqual(Path(options["env"]["NVIM_LOG_FILE"]).parent, options["cwd"])
        self.assertFalse(options["cwd"].exists())

    def test_version_timeout_is_a_clean_prelaunch_refusal(self):
        runner = self.terminal()
        runner.side_effect = subprocess.TimeoutExpired("nvim", 5)
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            neovim.validate_environment()

    def test_native_launch_inherits_tty_and_has_isolated_private_files(self):
        before = self.files()
        result, observed = self.launch(packet=self.packet())
        self.assertEqual(result, 0)
        self.assertEqual(observed["root_mode"], 0o700)
        self.assertEqual(observed["input_mode"], 0o600)
        self.assertFalse(Path(observed["cwd"]).exists())
        self.assertNotIn("capture_output", observed)
        self.assertNotIn("shell", observed)
        self.assertNotIn("stdin", observed)
        self.assertNotIn("stdout", observed)
        command = observed["command"]
        self.assertNotIn("--listen", command)
        self.assertNotIn("--remote", command)
        self.assertIn(neovim._STOP_SERVERS, command)
        self.assertIn(neovim._LOAD_ADAPTER, command)
        self.assertIn("NONE", command)
        self.assertIn("-n", command)
        self.assertIn("--noplugin", command)
        self.assertEqual(self.files(), before)

    def test_explicit_export_is_exclusive_owner_only_checked_packet(self):
        output = self.root / "position.json"
        packet = self.packet()
        result, _ = self.launch(packet=packet, export=output)
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.read_text()), packet)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_existing_and_symlink_exports_are_refused_before_native_launch(self):
        target = self.root / "existing.json"
        target.write_text("Invented user-owned content")
        link = self.root / "link.json"
        link.symlink_to(target)
        broken = self.root / "broken.json"
        broken.symlink_to(self.root / "absent.json")
        with patch.object(neovim, "validate_environment", return_value="/invented/bin/nvim"), \
                patch.object(neovim.subprocess, "run") as native:
            for output in (target, link, broken):
                with self.subTest(output=output), self.assertRaises(FileExistsError):
                    neovim.run(self.sample(), export=output)
            native.assert_not_called()
        self.assertEqual(target.read_text(), "Invented user-owned content")

    def test_export_into_corpus_is_refused_before_launch(self):
        with patch.object(neovim, "validate_environment", return_value="/invented/bin/nvim"), \
                patch.object(neovim.subprocess, "run") as native, self.assertRaisesRegex(ValueError, "canonical corpus"):
            neovim.run(self.sample(), export=self.corpus / "position.json")
        native.assert_not_called()

    def test_racing_output_creation_never_overwrites_a_file(self):
        output = self.root / "position.json"
        def create_destination(command, options):
            output.write_text("Invented concurrently created file")
        with self.assertRaises(FileExistsError):
            self.launch(packet=self.packet(), export=output, operation=create_destination)
        self.assertEqual(output.read_text(), "Invented concurrently created file")

    def test_invalid_native_packet_is_not_exported(self):
        output = self.root / "position.json"
        packet = self.packet()
        packet["selection"]["text"] = "Forged native result"
        with self.assertRaises(ValueError):
            self.launch(packet=packet, export=output)
        self.assertFalse(output.exists())

    def test_source_changed_while_editor_open_is_refused_before_export(self):
        output = self.root / "position.json"
        def change_source(command, options):
            source = self.corpus / "sample.md"
            source.write_text(source.read_text() + "\nAn invented source edit while reading.\n")
        with self.assertRaises(ValueError):
            self.launch(packet=self.packet(), export=output, operation=change_source)
        self.assertFalse(output.exists())

    def test_nonzero_native_exit_does_not_export_a_packet(self):
        output = self.root / "position.json"
        result, _ = self.launch(packet=self.packet(), code=1, export=output)
        self.assertEqual(result, 1)
        self.assertFalse(output.exists())

    def test_explicit_quit_without_capture_is_ok_unless_export_requested(self):
        result, _ = self.launch()
        self.assertEqual(result, 0)
        output = self.root / "position.json"
        with self.assertRaisesRegex(ValueError, "without a captured packet"):
            self.launch(export=output)
        self.assertFalse(output.exists())

    def test_strict_packet_reader_refuses_duplicates_nonfinite_and_oversize(self):
        path = self.root / "packet.json"
        for text in ('{"cursor_offset":0,"cursor_offset":1}', '{"nested":{"a":0,"a":1}}', '{"cursor_offset":NaN}'):
            path.write_text(text)
            with self.subTest(text=text), self.assertRaises(ValueError):
                neovim._read_packet(path)
        path.write_bytes(b" " * (neovim.MAX_PACKET_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "1 MiB"):
            neovim._read_packet(path)

    def test_restore_symlink_or_nonregular_file_is_refused(self):
        target = self.root / "packet.json"
        target.write_text(json.dumps(self.packet()))
        link = self.root / "link.json"
        link.symlink_to(target)
        with self.assertRaises(OSError):
            neovim._read_packet(link)
        fifo = self.root / "packet.fifo"
        os.mkfifo(fifo, 0o600)
        with self.assertRaisesRegex(ValueError, "regular file"):
            neovim._read_packet(fifo)

    def test_restore_file_passes_existing_packet_into_isolated_payload(self):
        path = self.root / "packet.json"
        packet = self.packet()
        path.write_text(json.dumps(packet))
        result, observed = self.launch(restore=path)
        self.assertEqual(result, 0)
        self.assertEqual(observed["payload"]["restore"], packet)

    def test_environment_removes_inherited_editor_config_and_remote_channels(self):
        with patch.dict(os.environ, NVIM="/unrelated/server", NVIM_LISTEN_ADDRESS="/unrelated/socket",
                        VIMINIT="untrusted init", EXINIT="untrusted ex", LUA_PATH="untrusted lua"):
            _, observed = self.launch()
        environment = observed["env"]
        for name in ("NVIM", "NVIM_LISTEN_ADDRESS", "VIMINIT", "EXINIT", "LUA_PATH"):
            self.assertNotIn(name, environment)
        root = Path(observed["cwd"])
        for name in ("XDG_CONFIG_HOME", "XDG_CONFIG_DIRS", "XDG_DATA_HOME", "XDG_DATA_DIRS",
                     "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR", "TMPDIR"):
            self.assertEqual(Path(environment[name]).parent, root)
        self.assertEqual(Path(environment["NVIM_LOG_FILE"]).parent, root)


if __name__ == "__main__":
    unittest.main()
