"""Real, isolated Neovim API proofs over invented, disposable source records.

These are headless editor checks, not a claim of physical-keyboard or sustained
reading acceptance. No user configuration, canonical project corpus, personal
workspace, network, package installation, or terminal emulator is used.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from sol.core.corpus import load_corpus_book
from sol.corpus import contract
from experiments.reader_surfaces.common import sample_from_book, validate_packet
from fixtures_corpus import write_runtime_corpus


_ROOT = Path(__file__).resolve().parents[1]
_ADAPTER = _ROOT / "sol/terminal/neovim.lua"
_GENERATED = {"markdown", "plain_text", "document", "context", "content_sha256"}


def neovim_environment(root):
    """Redirect editor-generated state without changing the user's home."""
    environment = {**os.environ,
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_STATE_HOME": str(root / "state"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "NVIM_LOG_FILE": str(root / "neovim.log"),
        # Note times are shown in local time; fix the zone so text is predictable.
        "TZ": "UTC"}
    for key in tuple(environment):
        if key.startswith(("SOL_", "KITTY_")) or key in {
            "VIMINIT", "EXINIT", "GVIMINIT", "NVIM_APPNAME", "NVIM", "NVIM_LISTEN_ADDRESS"}:
            environment.pop(key)
    return environment


def invented_sample(root, *, controls=False):
    """Create exact source/index bindings without depending on a Markdown parser."""
    corpus = root / "corpus"
    identifier, _ = write_runtime_corpus(corpus)
    records = [json.loads(line) for line in (corpus / "index.jsonl").read_text().splitlines()]
    first = records[1]
    first["markdown"] = "Lead 𝔸 *thought* e\u0301 and **ground**, Greek α, CJK 界.\nNext\tline `code` repeats."
    first["plain_text"] = "Lead 𝔸 thought e\u0301 and ground, Greek α, CJK 界.\nNext\tline code repeats."
    if controls:
        first["markdown"] += " Literal C1 \u0099 and \u008a."
        first["plain_text"] += " Literal C1 \u0099 and \u008a."
    second = deepcopy(first)
    second.update(id="cccccccc-0000-4000-8000-000000000003", order=2,
        markdown="A second invented paragraph has a different identity and a fairly long sequence of ordinary words for soft wrapping.",
        plain_text="A second invented paragraph has a different identity and a fairly long sequence of ordinary words for soft wrapping.")
    third = deepcopy(first)
    third.update(id="dddddddd-0000-4000-8000-000000000004", order=3,
        markdown="An inert `:!touch should-not-exist` is source, not an editor command.",
        plain_text="An inert :!touch should-not-exist is source, not an editor command.",
        transcription_status="needs_review")
    records.extend((second, third))
    markdown = "\n".join(contract.render_record(
        {key: value for key, value in record.items() if key not in _GENERATED},
        record["markdown"]) for record in records)
    (corpus / "sample.md").write_text(markdown, encoding="utf-8")
    for record in records:
        record["content_sha256"] = hashlib.sha256(record["markdown"].encode()).hexdigest()
    index = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")) + "\n" for record in records).encode()
    (corpus / "index.jsonl").write_bytes(index)
    (corpus / "index.meta.json").write_text(json.dumps({
        "contract_version": 1,
        "manifest_sha256": hashlib.sha256((corpus / "corpus.json").read_bytes()).hexdigest(),
        "source_sha256": "0" * 64,
        "documents": {"sample.md": hashlib.sha256(markdown.encode()).hexdigest()},
        "index_sha256": hashlib.sha256(index).hexdigest(), "record_count": len(records)}), encoding="utf-8")
    contract.initialize_corpus_identity(corpus)
    book = load_corpus_book(corpus)
    return corpus, sample_from_book(book, count=3)


@unittest.skipUnless(shutil.which("nvim"), "installed Neovim is required; tests never install it")
class ReaderSurfaceNeovimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="sol-neovim-version-")
        cls.addClassCleanup(temporary.cleanup)
        result = subprocess.run([shutil.which("nvim"), "--version"],
            env=neovim_environment(Path(temporary.name)), capture_output=True, text=True, timeout=10)
        version = re.match(r"NVIM v(\d+)\.(\d+)", result.stdout)
        if result.returncode or version is None or tuple(map(int, version.groups())) < (0, 11):
            raise unittest.SkipTest("Neovim 0.11 or newer is required for this experiment")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-neovim-proof-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus, self.sample = invented_sample(self.root)
        self.before = {path.name: path.read_bytes() for path in self.corpus.iterdir()}
        self.environment = neovim_environment(self.root)
        self.input, self.output = self.root / "input.json", self.root / "selection.json"
        self.result = self.root / "report.json"

    def run_lua(self, scenario, *, restore=None, automatic_quit=True, integrated=False, theme=None):
        from experiments.reader_surfaces.neovim import build_payload
        from sol.terminal.theme import theme_payload

        self.payload = build_payload(self.sample, width=72, restore=restore)
        if theme is not None:
            self.payload["theme"] = theme_payload(theme, {"COLORTERM": "truecolor"})
        if integrated:
            self.payload.update(integrated=True, navigation={"next": True, "previous": True}, notice="")
        self.input.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")
        environment = {**self.environment,
            "SOL_NVIM_INPUT": str(self.input), "SOL_NVIM_OUTPUT": str(self.output),
            "SOL_NVIM_ADAPTER": str(_ADAPTER), "SOL_NVIM_TEST_REPORT": str(self.result)}
        program = r'''
local ok, failure = xpcall(function()
  local input = assert(io.open(os.getenv('SOL_NVIM_INPUT'), 'r'))
  local data = vim.json.decode(input:read('*a')); input:close()
  dofile(os.getenv('SOL_NVIM_ADAPTER'))
  local reader = assert(SOLNvimReader, 'adapter API was not exposed')
  local report = {}
  local function refuse(operation)
    local accepted, value = pcall(operation)
    assert(not accepted or value == nil or value == false, 'operation was accepted unexpectedly')
  end
  local function point(id, offset)
    local location = assert(reader.source_point(id, offset))
    return {location.row, location.byte}
  end
  local function write_report()
    vim.fn.writefile({vim.json.encode(report)}, os.getenv('SOL_NVIM_TEST_REPORT'))
  end
''' + scenario + r'''
  write_report()
end, debug.traceback)
if not ok then
  io.stderr:write(tostring(failure) .. '\n')
  vim.cmd('cquit 1')
end
''' + ("vim.cmd('qa!')\n" if automatic_quit else "")
        script = self.root / "scenario.lua"
        script.write_text(program, encoding="utf-8")
        completed = subprocess.run([shutil.which("nvim"), "-u", "NONE", "--noplugin", "-i", "NONE",
            "-n", "--headless", "-l", str(script)], cwd=self.root, env=environment,
            capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(self.before, {path.name: path.read_bytes() for path in self.corpus.iterdir()})
        self.assertFalse(list(self.root.rglob("*.sqlite3")))
        self.assertFalse((self.root / "config" / "sol").exists())
        self.assertFalse((self.root / "should-not-exist").exists())
        return json.loads(self.result.read_text()) if self.result.exists() else {}

    def test_buffer_preserves_exact_multirecord_source_and_native_soft_wrapping(self):
        report = self.run_lua(r'''
  assert(vim.bo[reader.buffer].buftype == 'nofile')
  assert(not vim.bo[reader.buffer].modifiable)
  assert(vim.wo[reader.window].wrap and vim.wo[reader.window].linebreak)
  for _, record in ipairs(data.records) do
    local position = assert(reader.positions[record.id])
    local lines = {}
    for _, row in ipairs(position.rows) do
      table.insert(lines, vim.api.nvim_buf_get_lines(reader.buffer, row.row - 1, row.row, false)[1])
    end
    assert(table.concat(lines, '\n') == record.plain_text)
  end
  report.records = #data.records
  report.has_review_warning = table.concat(vim.api.nvim_buf_get_lines(reader.buffer, 0, -1, false), '\n'):find('review') ~= nil
''')
        self.assertEqual(report["records"], 3)
        self.assertTrue(report["has_review_warning"])

    def test_all_codepoint_positions_roundtrip_without_utf8_or_screen_cell_confusion(self):
        report = self.run_lua(r'''
  local checks = 0
  for _, record in ipairs(data.records) do
    local length = reader.byte_to_codepoint(record.plain_text, #record.plain_text)
    for offset = 0, length do
      local location = assert(reader.source_point(record.id, offset))
      local source = assert(reader.source_location(location.row, location.byte))
      assert(source.id == record.id and source.offset == offset)
      checks = checks + 1
    end
  end
  report.checks = checks
''')
        self.assertEqual(report["checks"], sum(len(passage.text) + 1 for passage in self.sample.passages))

    def test_utf8_conversion_refuses_interior_bytes_and_invalid_offsets(self):
        report = self.run_lua(r'''
  local text = 'α界𝔸é\t\n'
  local boundaries = {}
  local length = reader.byte_to_codepoint(text, #text)
  for offset = 0, length do
    local byte = assert(reader.codepoint_to_byte(text, offset))
    boundaries[byte] = true
    assert(reader.byte_to_codepoint(text, byte) == offset)
  end
  for byte = 0, #text do
    if not boundaries[byte] then refuse(function() return reader.byte_to_codepoint(text, byte) end) end
  end
  for _, invalid in ipairs({-1, length + 1, .5, '1', false}) do
    refuse(function() return reader.codepoint_to_byte(text, invalid) end)
  end
  for _, invalid in ipairs({-1, #text + 1, .5, '1', false}) do
    refuse(function() return reader.byte_to_codepoint(text, invalid) end)
  end
  report.codepoints = length
''')
        self.assertEqual(report["codepoints"], len("α界𝔸é\t\n"))

    @unittest.skipUnless(importlib.util.find_spec("markdown_it"), "semantic Markdown parser is optional")
    def test_semantic_styles_are_extmarks_not_ansi_or_modified_canonical_text(self):
        report = self.run_lua(r'''
  local marks = vim.api.nvim_buf_get_extmarks(reader.buffer, reader.namespace, 0, -1, {details = true})
  local semantic = 0
  for _, mark in ipairs(marks) do
    local details = mark[4]
    if details.hl_group then semantic = semantic + 1 end
  end
  assert(semantic >= 4, 'expected emphasis, strong, and inline-code presentation')
  local all = table.concat(vim.api.nvim_buf_get_lines(reader.buffer, 0, -1, false), '\n')
  assert(not all:find('\27', 1, true))
  assert(not all:find('*thought*', 1, true))
  report.semantic_marks = semantic
''')
        self.assertGreaterEqual(report["semantic_marks"], 4)

    def test_inclusive_forward_and_reverse_visual_selection_share_existing_half_open_identity(self):
        text = self.sample.passages[0].text
        start, end = text.index("𝔸"), text.index("ground") + len("ground")
        report = self.run_lua(r'''
  local record = data.records[1]
  local first = reader.source_point(record.id, ''' + str(start) + r''')
  local last = reader.source_point(record.id, ''' + str(end - 1) + r''')
  local forward = reader.capture('v', first, last)
  local reverse = reader.capture('v', last, first)
  assert(vim.deep_equal(forward.reference, reverse.reference))
  assert(vim.deep_equal(forward.selection, reverse.selection))
  assert(forward.selection.start == ''' + str(start) + r''' and forward.selection['end'] == ''' + str(end) + r''')
  assert(forward.cursor_offset == ''' + str(end) + r''' and reverse.cursor_offset == ''' + str(start) + r''')
  report.forward = forward; report.reverse = reverse
''')
        for name in ("forward", "reverse"):
            selected = validate_packet(self.sample.book, report[name])
            self.assertEqual(selected.text, text[start:end])
            self.assertEqual((selected.start, selected.end), (start, end))

    def test_selection_across_canonical_newline_preserves_newline_and_tab(self):
        text = self.sample.passages[0].text
        start, end = text.index("界"), text.index("code") + 4
        report = self.run_lua(r'''
  local id = data.records[1].id
  report.packet = reader.capture('v', reader.source_point(id, ''' + str(start) + r'''),
      reader.source_point(id, ''' + str(end - 1) + r'''))
''')
        selected = validate_packet(self.sample.book, report["packet"])
        self.assertEqual(selected.text, text[start:end])
        self.assertIn("\n", selected.text)
        self.assertIn("\t", selected.text)

    def test_unsupported_selection_modes_cross_record_and_metadata_are_refused(self):
        report = self.run_lua(r'''
  local first = reader.source_point(data.records[1].id, 0)
  local second = reader.source_point(data.records[2].id, 2)
  refuse(function() return reader.capture('V', first, first) end)
  refuse(function() return reader.capture(string.char(22), first, first) end)
  refuse(function() return reader.capture('v', first, second) end)
  local firstrow = reader.positions[data.records[1].id].first_row
  assert(firstrow > 1, 'expected an unmappable source heading/context row')
  refuse(function() return reader.source_location(firstrow - 1, 0) end)
  refuse(function() return reader.capture('n', nil, {row = firstrow - 1, byte = 0}) end)
  report.refused = true
''')
        self.assertTrue(report["refused"])

    def test_even_forced_buffer_mutation_refuses_capture_before_source_export(self):
        report = self.run_lua(r'''
  local location = reader.source_point(data.records[1].id, 0)
  vim.bo[reader.buffer].modifiable = true
  vim.api.nvim_buf_set_text(reader.buffer, location.row - 1, location.byte,
      location.row - 1, location.byte + 1, {'X'})
  vim.bo[reader.buffer].modifiable = false
  refuse(function() return reader.capture('n', nil, location) end)
  refuse(function() return reader.export() end)
  report.refused = true
''')
        self.assertTrue(report["refused"])
        self.assertFalse(self.output.exists())

    def test_resize_preserves_source_cursor_and_exact_selection_packet(self):
        report = self.run_lua(r'''
  local first = reader.source_point(data.records[1].id, 5)
  local last = reader.source_point(data.records[1].id, 31)
  local packet = reader.capture('v', first, last)
  reader.restore(packet)
  vim.o.columns = 42; vim.o.lines = 22
  vim.api.nvim_exec_autocmds('VimResized', {})
  local narrow = reader.capture()
  assert(vim.deep_equal(narrow, packet), 'narrowing changed semantic selection identity')
  vim.o.columns = 140; vim.o.lines = 40
  vim.api.nvim_exec_autocmds('VimResized', {})
  local wide = reader.capture()
  assert(vim.deep_equal(wide, packet), 'widening changed semantic selection identity')
  report.packet = wide
''')
        self.assertEqual(validate_packet(self.sample.book, report["packet"]).text,
            self.sample.passages[0].text[5:32])

    def test_exported_packet_validates_in_python_and_restores_in_fresh_editor(self):
        text = self.sample.passages[0].text
        start, end = text.index("thought"), text.index("ground") + len("ground")
        report = self.run_lua(r'''
  local id = data.records[1].id
  local packet = reader.capture('v', reader.source_point(id, ''' + str(end - 1) + r'''),
      reader.source_point(id, ''' + str(start) + r'''))
  reader.restore(packet)
  reader.export()
  report.packet = reader.capture()
''')
        packet = json.loads(self.output.read_text())
        self.assertEqual(packet, report["packet"])
        self.assertEqual(validate_packet(self.sample.book, packet).text, text[start:end])
        self.output.unlink()
        restored = self.run_lua("  report.packet = reader.capture()\n", restore=packet)
        self.assertEqual(restored["packet"], packet)

    def test_installed_quit_returns_existing_packet_inside_narrow_action_envelope(self):
        self.run_lua(r'''
  local cp = reader.source_point(data.records[2].id, 11)
  vim.api.nvim_win_set_cursor(reader.window, {cp.row, cp.byte})
  vim.api.nvim_feedkeys(':q\r', 'xt', false)
''', integrated=True)
        result = json.loads(self.output.read_text())
        self.assertEqual(set(result), {"action", "packet"})
        self.assertEqual(result["action"], "quit")
        self.assertEqual(result["packet"]["cursor_offset"], 11)
        self.assertIsNone(validate_packet(self.sample.book, result["packet"]))

    def test_installed_next_section_uses_native_mapped_key(self):
        self.run_lua("  vim.api.nvim_feedkeys(']c', 'xt', false)\n", integrated=True)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["action"], "next")
        self.assertIsNone(validate_packet(self.sample.book, result["packet"]))

    def test_installed_bottom_j_continues_instead_of_stalling_on_separator(self):
        self.run_lua("  vim.api.nvim_feedkeys('Gj', 'xt', false)\n", integrated=True)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["action"], "next")
        self.assertEqual(result["packet"]["reference"]["reference"]["target_id"], self.sample.passages[-1].identifier)
        self.assertEqual(result["packet"]["cursor_offset"], len(self.sample.passages[-1].text))

    def test_installed_top_k_can_return_to_previous_reading_section(self):
        self.run_lua("  vim.api.nvim_feedkeys('ggk', 'xt', false)\n", integrated=True)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["action"], "previous")
        self.assertEqual(result["packet"]["cursor_offset"], 0)

    def test_installed_visual_selection_across_styled_unicode_prose_remains_exact(self):
        self.run_lua(r'''
  local id = data.records[1].id
  local packet = reader.capture('v', reader.source_point(id, 5), reader.source_point(id, 31))
  reader.restore(packet)
  vim.o.columns = 38
  vim.api.nvim_exec_autocmds('VimResized', {})
  assert(vim.deep_equal(reader.capture(), packet))
  vim.api.nvim_feedkeys(':q\r', 'xt', false)
''', integrated=True)
        result = json.loads(self.output.read_text())
        selected = validate_packet(self.sample.book, result["packet"])
        self.assertEqual(selected.text, self.sample.passages[0].text[5:32])

    def test_native_c1_markers_preserve_source_scalars_and_following_offsets(self):
        root = self.root / "with-controls"
        root.mkdir()
        self.corpus, self.sample = invented_sample(root, controls=True)
        self.before = {path.name: path.read_bytes() for path in self.corpus.iterdir()}
        offset = self.sample.passages[0].text.index("\u0099")
        report = self.run_lua(r'''
  assert(vim.o.display:find('uhex', 1, true))
  assert(vim.fn.strtrans('\194\153') == '<99>')
  local id, at = data.records[1].id, ''' + str(offset) + r'''
  local packet = reader.capture('v', reader.source_point(id, at), reader.source_point(id, at))
  assert(packet.selection.start == at and packet.selection['end'] == at + 1)
  reader.restore(packet)
  vim.o.columns = 38
  vim.api.nvim_exec_autocmds('VimResized', {})
  assert(vim.deep_equal(reader.capture(), packet))
  report.packet = reader.capture()
''')
        self.assertEqual(validate_packet(self.sample.book, report["packet"]).text, "\u0099")

    def test_toggle_preserves_source_selection_and_paragraph_mode_contains_motion(self):
        report = self.run_lua(r'''
  local id = data.records[1].id
  local packet = reader.capture('v', reader.source_point(id, 7), reader.source_point(id, 13))
  reader.restore(packet)
  reader.toggle_mode()
  reader = SOLNvimReader
  assert(reader.mode == 'paragraph' and vim.tbl_count(reader.positions) == 1)
  assert(vim.deep_equal(reader.capture(), packet))
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes('<Esc>gg99j99k', true, false, true), 'xt', false)
  assert(reader.capture().reference.reference.target_id == id)
  vim.api.nvim_feedkeys(']p', 'xt', false)
  reader = SOLNvimReader
  assert(reader.mode == 'paragraph')
  assert(reader.capture().reference.reference.target_id == data.records[2].id)
  reader.toggle_mode()
  reader = SOLNvimReader
  assert(reader.mode == 'continuous' and vim.tbl_count(reader.positions) == 3)
  report.packet = reader.capture()
''', integrated=True)
        self.assertEqual(report["packet"]["reference"]["reference"]["target_id"], self.sample.passages[1].identifier)

    def test_yank_calls_clipboard_provider_with_exact_semantic_text(self):
        report = self.run_lua(r'''
  local clip_file = vim.fn.tempname()
  vim.env.SOL_NVIM_CLIPBOARD = vim.json.encode({command = {'sh', '-c', 'cat > "$0"', clip_file}, env = vim.empty_dict()})
  local function clipboard()
    local stream = io.open(clip_file)
    if not stream then return nil end
    local text = stream:read('a'); stream:close(); os.remove(clip_file)
    return text
  end
  local id = data.records[1].id
  local packet = reader.capture('v', reader.source_point(id, 7), reader.source_point(id, 13))
  reader.restore(packet)
  reader.yank()
  report.clipboard = clipboard()
''', integrated=True)
        self.assertEqual(report["clipboard"], "thought")

    def test_outline_keeps_selection_across_resize_and_returns_without_navigation(self):
        from sol.reader.structure import structure_payload
        from unittest.mock import patch
        from sol.terminal import neovim
        original = neovim.build_payload
        def payload(*args, **kwargs):
            value = original(*args, **kwargs)
            value["structure"] = structure_payload(self.sample.book, self.sample.passages[0])
            return value
        with patch.object(neovim, "build_payload", side_effect=payload):
            report = self.run_lua(r'''
  local before = reader.capture()
  local tree = reader.tree()
  assert(tree.state().layout == 'vertical')
  local selected = tree.state().selected
  vim.api.nvim_feedkeys('hl', 'xt', false)
  assert(tree.state().layout == 'vertical')
  selected = tree.state().selected
  vim.o.columns = 42
  vim.api.nvim_exec_autocmds('VimResized', {})
  assert(vim.api.nvim_get_current_win() == tree.window)
  assert(tree.state().selected == selected)
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes('<Esc>', true, false, true), 'xt', false)
  assert(vim.deep_equal(reader.capture(), before))
  report.restored = true
''', integrated=True)
        self.assertTrue(report["restored"])

    def test_missing_clipboard_provider_retains_register_but_refuses_success(self):
        report = self.run_lua(r'''
  local original = vim.fn.has
  vim.fn.has = function(name) if name == 'clipboard' then return 0 end; return original(name) end
  refuse(function() reader.yank() end)
  assert(vim.fn.getreg('"') == data.records[1].plain_text)
  report.register = true
''', integrated=True)
        self.assertTrue(report["register"])

    def test_simple_paragraph_keys_and_focus_retain_semantic_positions(self):
        report = self.run_lua(r'''
  local first, second = data.records[1].id, data.records[2].id
  vim.api.nvim_feedkeys('n', 'xt', false)
  assert(reader.capture().reference.reference.target_id == second)
  assert(reader.capture().cursor_offset == 0)
  vim.api.nvim_feedkeys('b', 'xt', false)
  assert(reader.capture().reference.reference.target_id == first)
  local packet = reader.capture('v', reader.source_point(first, 7), reader.source_point(first, 13))
  reader.restore(packet)
  -- Focus is presentation: styled source selections retain their exact identity.
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes('<Esc>f', true, false, true), 'xt', false)
  reader = SOLNvimReader
  local current = reader.capture()
  local position = current.cursor_offset
  vim.api.nvim_feedkeys('p', 'xt', false)
  reader = SOLNvimReader
  assert(reader.mode == 'paragraph')
  vim.api.nvim_feedkeys('99j99k', 'xt', false)
  assert(reader.capture().reference.reference.target_id == first)
  vim.api.nvim_feedkeys('n', 'xt', false)
  reader = SOLNvimReader
  assert(reader.capture().reference.reference.target_id == second)
  assert(reader.capture().cursor_offset == 0)
  report.simple_keys = true
''', integrated=True)
        self.assertTrue(report["simple_keys"])

    def test_theme_presets_style_only_presentation_and_cycle_in_order(self):
        report = self.run_lua(r'''
  local before = vim.api.nvim_buf_get_lines(reader.buffer, 0, -1, false)
  local packet = reader.capture('v', reader.source_point(data.records[1].id, 5), reader.source_point(data.records[1].id, 12))
  local function normal() return vim.api.nvim_get_hl(0, {name = 'Normal'}) end
  assert(reader.theme() == 'latte' and vim.o.termguicolors and vim.o.background == 'light')
  assert(normal().bg == tonumber('eff1f5', 16), 'latte page color was not applied')
  assert(vim.api.nvim_get_hl(0, {name = 'SOLSourceHeading'}).bold)
  assert(vim.wo[reader.window].winhighlight == 'NormalFloat:Normal')
  assert(vim.o.fillchars:find('lastline: ', 1, true) and vim.o.fillchars:find('eob: ', 1, true))
  local order = {}
  for _ = 1, 5 do order[#order + 1] = reader.cycle_theme() end
  report.order = order
  -- The live cursor keeps its source position through every preset.
  local resting = reader.capture('n', nil, reader.source_point(data.records[1].id, 7))
  reader.restore(resting)
  for _ = 1, 5 do
    vim.api.nvim_feedkeys('T', 'xt', false)
    assert(vim.deep_equal(SOLNvimReader.capture(), resting), 'theme switch moved the reading position')
  end
  -- SOL's Paper declares a light page; Terminal hands foreground, background
  -- and palette back to the host.
  reader.cycle_theme()
  assert(reader.theme() == 'paper' and vim.o.background == 'light' and normal().bg == tonumber('f3f0e6', 16))
  reader.cycle_theme()
  assert(reader.theme() == 'night' and vim.o.background == 'dark')
  reader.cycle_theme()
  assert(reader.theme() == 'terminal' and not vim.o.termguicolors and next(normal()) == nil)
  reader.cycle_theme()
  assert(vim.o.background == 'dark' and normal().bg == tonumber('1e1e2e', 16))
  assert(vim.deep_equal(before, vim.api.nvim_buf_get_lines(reader.buffer, 0, -1, false)))
  reader.verified_projection()
  assert(vim.deep_equal(reader.capture('v', reader.source_point(data.records[1].id, 5),
    reader.source_point(data.records[1].id, 12)), packet))
  -- A host background change resets default groups; the preset returns.
  vim.o.background = 'light'
  vim.wait(100, function() return vim.o.background == 'dark' end)
  assert(vim.o.background == 'dark' and normal().bg == tonumber('1e1e2e', 16))
''', theme="latte")
        self.assertEqual(report["order"], ["paper", "night", "terminal", "mocha", "latte"])

    def test_source_preview_popup_requests_pages_and_returns_to_the_same_position(self):
        report = self.run_lua(r'''
  local sent = {}
  _G.SOLReaderChannel = {serial = 0, pending = {}, incoming = '',
    writer = {write = function(_, line) sent[#sent + 1] = vim.json.decode(line) end}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(vim.deepcopy(data))
  reader = SOLNvimReader
  local resting = reader.capture('n', nil, reader.source_point(data.records[1].id, 7))
  reader.restore(resting)
  vim.api.nvim_feedkeys('s', 'xt', false)
  assert(#sent == 1 and sent[1].op == 'source_preview' and sent[1].page == 1)
  local pages = {{number = 1, pdf_page = 7, printed_page = '5', region = true},
                 {number = 2, pdf_page = 8, printed_page = 'unnumbered', region = false}}
  local function reply(message, fields)
    _G.SOLReaderChannel.pending[message.id]({source = vim.tbl_extend('force', {title = 'Synthetic section',
      record = data.records[1].id, status = 'needs visual review', pages = pages,
      note = 'The printed source is authoritative.'}, fields)})
    return vim.api.nvim_buf_get_lines(0, 0, -1, false)
  end
  report.opened = reply(sent[1], {shown = 1, cropped = true, image = '/cache/0.png', viewer = 'xdg-open'})
  vim.api.nvim_feedkeys('2', 'xt', false)
  assert(#sent == 2 and sent[2].page == 2)
  report.fallback = reply(sent[2], {shown = 2, cropped = false, image = '/cache/1.png', viewer = vim.NIL})
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  assert(vim.api.nvim_get_current_win() == reader.window)
  assert(vim.deep_equal(SOLNvimReader.capture(), resting), 'source preview moved the reading position')
''', integrated=True)
        opened, fallback = "\n".join(report["opened"]), "\n".join(report["fallback"])
        self.assertIn("Recorded region of PDF page 7 (printed page 5), 1 of 2", opened)
        self.assertIn("Transcription: needs visual review", opened)
        self.assertIn("The printed source is authoritative.", opened)
        self.assertIn("Opened in xdg-open", opened)
        self.assertIn("2. PDF page 8, printed page unnumbered (whole page)", opened)
        self.assertIn("Whole PDF page 8 (printed page unnumbered), 2 of 2; no region was recorded", fallback)
        self.assertIn("No graphical image viewer", fallback)
        self.assertIn("/cache/1.png", fallback)

    def test_note_editor_saves_restores_selection_and_protects_drafts(self):
        report = self.run_lua(r'''
  local sent = {}
  _G.SOLReaderChannel = {serial = 0, pending = {}, incoming = '',
    writer = {write = function(_, line) sent[#sent + 1] = vim.json.decode(line) end}}
  local payload = vim.deepcopy(data)
  payload.personal = {persistent = true, notes = vim.empty_dict()}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(payload)
  reader = SOLNvimReader
  local id = data.records[1].id
  local selected = reader.capture('v', reader.source_point(id, 5), reader.source_point(id, 12))
  reader.restore(selected)
  vim.api.nvim_feedkeys('a', 'xt', false)
  local editor = vim.api.nvim_get_current_buf()
  assert(vim.api.nvim_buf_get_name(editor):find('sol://note/', 1, true), 'note editor did not open')
  local marks = vim.api.nvim_buf_get_extmarks(editor, -1, 0, -1, {details = true})
  report.quote = marks[1][4].virt_lines[1][1][1]
  report.title = vim.api.nvim_win_get_config(0).title[1][1]
  vim.api.nvim_buf_set_lines(editor, 0, -1, false, {'A thought', 'on two lines'})
  vim.api.nvim_feedkeys(vim.keycode('<C-s>'), 'xt', false)
  assert(#sent == 1 and sent[1].op == 'note_add', 'save did not request note_add')
  report.body = sent[1].body
  assert(vim.api.nvim_get_current_win() == reader.window)
  assert(vim.deep_equal(SOLNvimReader.capture(), selected), 'saving moved the position or selection')
  -- An unacknowledged save keeps the draft.
  _G.SOLReaderChannel.pending[sent[1].id](nil, 'invented failure')
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  reader.note()
  report.after_failure = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  vim.api.nvim_feedkeys(vim.keycode('<C-s>'), 'xt', false)
  _G.SOLReaderChannel.pending[sent[2].id]({personal = {persistent = true, notes = {[id] = {
    {id = 'n1', author = 'Invented reader', created_at = '2026-10-17T12:00:00Z', revision = 1, edit_refusal = '',
     changed_source = false, retired_target = false, body = 'A thought\non two lines',
     lines = {'A thought', 'on two lines'}}}}}})
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  reader.note()
  report.after_save = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  -- :q! keeps a draft; Ctrl-C discards it.
  vim.api.nvim_buf_set_lines(0, 0, -1, false, {'Half a thought'})
  vim.cmd('stopinsert'); vim.cmd('q!')
  reader.note()
  report.after_quit = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  vim.api.nvim_feedkeys(vim.keycode('<C-c>'), 'xt', false)
  reader.note()
  report.after_discard = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  vim.api.nvim_feedkeys(vim.keycode('<C-c>'), 'xt', false)
  reader.context()
  report.context = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  -- A temporary session explains instead of opening an editor.
  SOLNvimReader.update_personal({persistent = false, notes = vim.empty_dict()})
  report.temporary = select(2, pcall(SOLNvimReader.note))
''', integrated=True)
        text = self.sample.passages[0].text
        self.assertEqual(report["quote"], text[5:13])
        self.assertTrue(report["title"].startswith(" Note on: "))
        self.assertEqual(report["body"], "A thought\non two lines")
        self.assertEqual(report["after_failure"], ["A thought", "on two lines"])
        self.assertEqual(report["after_save"], [""])
        self.assertEqual(report["after_quit"], ["Half a thought"])
        self.assertEqual(report["after_discard"], [""])
        context = "\n".join(report["context"])
        self.assertIn("Your notes   1 · a add · e edit · r versions", context)
        self.assertIn("  Invented reader · 17 Oct 2026, 12:00 · revision 1\n  A thought\n  on two lines", context)
        self.assertIn("notes need a workspace", report["temporary"])

    def test_context_edits_the_note_under_the_cursor_and_shows_its_versions(self):
        report = self.run_lua(r'''
  local sent = {}
  _G.SOLReaderChannel = {serial = 0, pending = {}, incoming = '',
    writer = {write = function(_, line) sent[#sent + 1] = vim.json.decode(line) end}}
  local id = data.records[1].id
  local function item(note, author, refusal, body, changed)
    return {id = note, author = author, created_at = '2026-10-17T12:00:00Z', revision = 1,
      edit_refusal = refusal, changed_source = changed, retired_target = false,
      body = body or vim.NIL, lines = vim.split(body or 'Hidden text', '\n')}
  end
  local payload = vim.deepcopy(data)
  payload.personal = {persistent = true, notes = {[id] = {
    item('mine', 'Invented reader', '', 'My first\nthought', true),
    item('theirs', 'Another reader', "only the note's author can edit it", nil, false)}}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(payload)
  reader = SOLNvimReader
  local function row_of(text)
    for row, line in ipairs(vim.api.nvim_buf_get_lines(0, 0, -1, false)) do
      if line:find(text, 1, true) then return row end
    end
  end
  local errors = {}
  vim.notify = function(message) errors[#errors + 1] = message end
  reader.context()
  report.context = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  -- On the heading, with two notes, nothing is guessed.
  vim.api.nvim_win_set_cursor(0, {1, 0})
  vim.api.nvim_feedkeys('e', 'xt', false)
  report.ambiguous = errors[#errors]
  vim.api.nvim_win_set_cursor(0, {row_of('Another reader'), 0})
  vim.api.nvim_feedkeys('e', 'xt', false)
  report.foreign = errors[#errors]
  vim.api.nvim_win_set_cursor(0, {row_of('thought'), 0})
  vim.api.nvim_feedkeys('e', 'xt', false)
  report.title = vim.api.nvim_win_get_config(0).title[1][1]
  report.opened = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  vim.api.nvim_buf_set_lines(0, 0, -1, false, {'My revised', 'thought'})
  vim.api.nvim_feedkeys(vim.keycode('<C-s>'), 'xt', false)
  report.request = {sent[1].op, sent[1].note, sent[1].revision, sent[1].body}
  -- A refused save keeps the revised draft for the next e.
  _G.SOLReaderChannel.pending[sent[1].id](nil, 'invented conflict')
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  reader.context()
  vim.api.nvim_win_set_cursor(0, {row_of('thought'), 0})
  vim.api.nvim_feedkeys('e', 'xt', false)
  report.after_failure = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  vim.api.nvim_feedkeys(vim.keycode('<C-c>'), 'xt', false)
  reader.context()
  vim.api.nvim_win_set_cursor(0, {row_of('thought'), 0})
  vim.api.nvim_feedkeys('r', 'xt', false)
  report.history_request = {sent[#sent].op, sent[#sent].note}
  _G.SOLReaderChannel.pending[sent[#sent].id]({note_history = {id = 'mine', author = 'Invented reader',
    revisions = {{revision = 2, kind = 'edited', editor = 'Invented reader', recorded_at = '2026-10-18T09:00:00Z',
                  lines = {'My revised', 'thought'}},
                 {revision = 1, kind = 'created', editor = 'Invented reader', recorded_at = '2026-10-17T12:00:00Z',
                  lines = {'My first', 'thought'}}}}})
  report.history = vim.api.nvim_buf_get_lines(0, 0, -1, false)
''', integrated=True)
        context = "\n".join(report["context"])
        self.assertIn("Your notes   2 · a add · e edit · r versions", context)
        self.assertIn("  Invented reader · 17 Oct 2026, 12:00 · revision 1\n"
                      "  the passage has changed since this note was written\n  My first\n  thought", context)
        self.assertIn("  Another reader · 17 Oct 2026, 12:00 · revision 1\n"
                      "  only the note's author can edit it", context)
        self.assertIn("move the cursor onto one of the notes", report["ambiguous"])
        self.assertIn("only the note's author", report["foreign"])
        self.assertEqual(report["title"], " Edit your note (revision 1) ")
        self.assertEqual(report["opened"], ["My first", "thought"])
        self.assertEqual(report["request"], ["note_edit", "mine", 1, "My revised\nthought"])
        self.assertEqual(report["after_failure"], ["My revised", "thought"])
        self.assertEqual(report["history_request"], ["note_history", "mine"])
        history = "\n".join(report["history"])
        self.assertIn("Revision 2 (edited), Invented reader, 2026-10-18T09:00:00Z\n  My revised\n  thought", history)
        self.assertLess(history.index("Revision 2"), history.index("Revision 1"))

    def test_essence_opens_beside_toggles_returns_and_closes_without_moving_the_reader(self):
        stub = self.root / "essence_stub.py"
        stub.write_text("import sys\nprint('ESSENCE STUB READY', flush=True)\nsys.stdin.readline()\n", encoding="utf-8")
        theme_file = self.root / "essence.theme"
        paths = (f"local PYTHON, STUB, THEME = {json.dumps(sys.executable)}, {json.dumps(str(stub))}, "
                 f"{json.dumps(str(theme_file))}\n")
        report = self.run_lua(paths + r'''
  vim.o.columns, vim.o.lines = 140, 40
  local sent = {}
  _G.SOLReaderChannel = {serial = 0, pending = {}, incoming = '',
    writer = {write = function(_, line) sent[#sent + 1] = vim.json.decode(line) end}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(vim.deepcopy(data))
  reader = SOLNvimReader
  local id = data.records[1].id
  reader.restore(reader.capture('n', reader.source_point(id, 9), reader.source_point(id, 9)))
  local before = reader.capture()
  local full_reader = vim.api.nvim_win_get_config(reader.window)
  local function geometry(window)
    local config = vim.api.nvim_win_get_config(window)
    return {col = config.col, width = config.width, hide = config.hide or false}
  end
  vim.api.nvim_feedkeys('E', 'xt', false)
  report.request = sent[1].op
  report.request_target = sent[1].packet.reference.reference.target_id
  _G.SOLReaderChannel.pending[sent[1].id]({essence = {command = {PYTHON, STUB}, theme_file = THEME}})
  local essence = assert(SOLEssence)
  -- ESSENCE learns the reader's theme on opening and on every T.
  local function written() local f = assert(io.open(THEME)); local v = f:read('*a'); f:close(); return v end
  report.themes = {written()}
  reader.cycle_theme()
  report.themes[2] = written()
  for _ = 1, 4 do reader.cycle_theme() end
  report.themes[3] = written()
  assert(vim.wait(5000, function()
    return table.concat(vim.api.nvim_buf_get_lines(essence.buffer, 0, -1, false), '\n'):find('ESSENCE STUB READY') ~= nil
  end, 10), 'ESSENCE did not start in its terminal')
  report.split = {layout = essence.layout, essence = geometry(essence.window), reader = geometry(reader.window),
                  focused = vim.api.nvim_get_current_win() == essence.window, reader_full = full_reader.width}
  local keys = {}
  for _, map in ipairs(vim.api.nvim_buf_get_keymap(essence.buffer, 't')) do keys[#keys + 1] = map.lhs end
  table.sort(keys); report.terminal_keys = keys
  essence.toggle()
  report.full = {layout = essence.layout, essence = geometry(essence.window), reader = geometry(reader.window)}
  essence.back_to_reader()
  report.back = {layout = essence.layout, focused_reader = vim.api.nvim_get_current_win() == reader.window}
  -- A section reload replaces the reader window; ESSENCE keeps its process and place.
  reader.toggle_mode(); reader = SOLNvimReader
  report.after_reload = {alive = vim.api.nvim_win_is_valid(essence.window), reader = geometry(reader.window)}
  vim.api.nvim_feedkeys('E', 'xt', false)
  report.refocus = {requests = #sent, focused = vim.api.nvim_get_current_win() == essence.window}
  local job = essence.job
  vim.fn.chansend(job, 'q\n')
  assert(vim.wait(5000, function() return SOLEssence.window == nil end, 10), 'ESSENCE did not close')
  report.closed = {focused_reader = vim.api.nvim_get_current_win() == SOLNvimReader.window,
                   reader = geometry(SOLNvimReader.window), mode = vim.fn.mode()}
  reader = SOLNvimReader
  reader.toggle_mode(); reader = SOLNvimReader
  report.position_kept = vim.deep_equal(reader.capture().reference, before.reference)
    and reader.capture().cursor_offset == before.cursor_offset
  -- A narrow terminal opens fullscreen; back to the reader hides ESSENCE, E shows it again.
  vim.o.columns = 80
  vim.api.nvim_feedkeys('E', 'xt', false)
  _G.SOLReaderChannel.pending[sent[#sent].id]({essence = {command = {PYTHON, STUB}}})
  report.narrow = {layout = SOLEssence.layout}
  SOLEssence.back_to_reader()
  report.narrow.after_back = SOLEssence.layout
  report.narrow.hidden = geometry(SOLEssence.window).hide
  vim.api.nvim_feedkeys('E', 'xt', false)
  report.narrow.after_e = SOLEssence.layout
  vim.fn.chansend(SOLEssence.job, 'q\n')
  assert(vim.wait(5000, function() return SOLEssence.window == nil end, 10))
  -- A command that cannot start leaves the reader usable and says why.
  local warnings = {}
  vim.notify = function(message) warnings[#warnings + 1] = message end
  vim.api.nvim_feedkeys('E', 'xt', false)
  _G.SOLReaderChannel.pending[sent[#sent].id]({essence = {command = {'/nonexistent/sol-essence'}}})
  report.failure = {warning = warnings[#warnings], window = SOLEssence.window == nil,
                    focused_reader = vim.api.nvim_get_current_win() == SOLNvimReader.window}
''', integrated=True, theme="mocha")
        self.assertEqual(report["request"], "essence_open")
        self.assertEqual(report["themes"], ["mocha", "latte", "mocha"])
        self.assertEqual(report["request_target"], self.sample.passages[0].identifier)
        split = report["split"]
        self.assertEqual(split["layout"], "split")
        self.assertTrue(split["focused"])
        self.assertLess(split["reader"]["col"] + split["reader"]["width"], split["essence"]["col"])
        self.assertEqual(report["terminal_keys"], ["<M-f>", "<M-r>"])
        self.assertEqual((report["full"]["layout"], report["full"]["essence"]["width"]), ("full", 140))
        self.assertEqual(report["back"], {"layout": "split", "focused_reader": True})
        self.assertTrue(report["after_reload"]["alive"])
        self.assertLess(report["after_reload"]["reader"]["col"] + report["after_reload"]["reader"]["width"],
                        split["essence"]["col"])
        self.assertEqual(report["refocus"], {"requests": 1, "focused": True})
        self.assertTrue(report["closed"]["focused_reader"])
        self.assertEqual(report["closed"]["mode"], "n")
        self.assertEqual(report["closed"]["reader"]["width"], split["reader_full"])
        self.assertTrue(report["position_kept"])
        self.assertEqual(report["narrow"], {"layout": "full", "after_back": "hidden", "hidden": True,
                                            "after_e": "full"})
        self.assertIn("could not start", report["failure"]["warning"])
        self.assertTrue(report["failure"]["window"])
        self.assertTrue(report["failure"]["focused_reader"])

    def test_copying_reaches_the_clipboard_from_keys_and_the_mouse(self):
        texts = [passage.text for passage in self.sample.passages]
        report = self.run_lua(r'''
  local clip_file = vim.fn.tempname()
  vim.env.SOL_NVIM_CLIPBOARD = vim.json.encode({command = {'sh', '-c', 'cat > "$0"', clip_file}, env = vim.empty_dict()})
  local function clipboard()
    local stream = io.open(clip_file)
    if not stream then return nil end
    local text = stream:read('a'); stream:close(); os.remove(clip_file)
    return text
  end
  local messages = {}
  local echo = vim.api.nvim_echo
  vim.api.nvim_echo = function(chunks, ...) messages[#messages + 1] = chunks[1][1]; return echo(chunks, ...) end
  local first, second = data.records[1], data.records[2]
  -- Across two paragraphs: exact source text, joined by a blank line.
  local a, b = reader.source_point(first.id, 5), reader.source_point(second.id, 9)
  reader.restore(reader.capture('v', a, a))
  vim.api.nvim_win_set_cursor(reader.window, {b.row, b.byte})
  reader.yank()
  report.across = clipboard()
  report.mode_after = vim.fn.mode(1)
  -- A start on the blank line between paragraphs moves forward to prose.
  local blank = reader.source_point(second.id, 0).row - 1
  vim.api.nvim_win_set_cursor(reader.window, {blank, 0})
  vim.cmd('normal! v')
  local c = reader.source_point(second.id, 4)
  vim.api.nvim_win_set_cursor(reader.window, {c.row, c.byte})
  reader.yank()
  report.snapped = clipboard()
  -- Releasing the mouse on a selection copies it; the mapping is the real one.
  local maps = {}
  for _, map in ipairs(vim.api.nvim_buf_get_keymap(reader.buffer, 'x')) do maps[map.lhs] = true end
  report.mouse_maps = maps['<LeftRelease>'] == true and maps['<2-LeftRelease>'] == true
  reader.restore(reader.capture('v', reader.source_point(first.id, 0), reader.source_point(first.id, 3)))
  vim.api.nvim_feedkeys(vim.keycode('<LeftRelease>'), 'xt', false)
  report.mouse = clipboard()
  report.mouse_option = vim.o.mouse
  -- A program that fails: the terminal is asked instead, and the reader says so.
  vim.env.SOL_NVIM_CLIPBOARD = vim.json.encode({command = {'false'}, env = vim.empty_dict()})
  reader.yank()
  report.fallback = messages[#messages]
  report.register = vim.fn.getreg('"')
''', integrated=True)
        self.assertEqual(report["across"], texts[0][5:] + "\n\n" + texts[1][:10])
        self.assertEqual(report["mode_after"], "n")
        self.assertEqual(report["snapped"], texts[1][:5])
        self.assertTrue(report["mouse_maps"])
        self.assertEqual(report["mouse"], texts[0][:4])
        self.assertEqual(report["mouse_option"], "a")
        self.assertIn("through the terminal", report["fallback"])
        self.assertEqual(report["register"], texts[0])  # no selection: the paragraph under the cursor

    def test_q_does_not_quit_and_qa_bang_leaves_without_saving(self):
        report = self.run_lua(r'''
  local messages = {}
  local echo = vim.api.nvim_echo
  vim.api.nvim_echo = function(chunks, ...) messages[#messages + 1] = chunks[1][1]; return echo(chunks, ...) end
  vim.api.nvim_feedkeys('q', 'xt', false)
  vim.api.nvim_feedkeys(vim.keycode('<C-q>'), 'xt', false)
  report.hint = messages
  report.alive = vim.api.nvim_buf_is_valid(reader.buffer)
  local normal = {}
  for _, map in ipairs(vim.api.nvim_buf_get_keymap(reader.buffer, 'n')) do normal[map.lhs] = true end
  report.study_key = normal['S'] == true
  vim.fn.writefile({vim.json.encode(report)}, os.getenv('SOL_NVIM_TEST_REPORT'))
  vim.api.nvim_feedkeys(':qa!\\r', 'xt', false)
''', integrated=True, automatic_quit=False)
        self.assertEqual(report["hint"], ["Type :q to save your place and quit (:qa! quits without saving)"] * 2)
        self.assertTrue(report["alive"])
        self.assertFalse(report["study_key"])
        self.assertFalse(self.output.exists())

    def test_status_line_says_where_and_how_the_book_is_read(self):
        report = self.run_lua(r'''
  local path = data.records[2].context.path
  local nodes, key = {}, ''
  local names = {'Quality', 'Quality'}  -- a chapter and its section with one title
  local index = 0
  for segment in path:gmatch('[^/]+') do
    key = key .. '/' .. segment; index = index + 1
    nodes[#nodes + 1] = {key = key, title = names[index] or segment}
  end
  local payload = vim.deepcopy(data)
  payload.structure = {nodes = nodes}
  payload.progress = {first = 49, total = 101}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(payload)
  local r = SOLNvimReader
  local at = r.source_point(data.records[2].id, 0)
  vim.api.nvim_win_set_cursor(r.window, {at.row, at.byte})
  report.status = SOLStatus()
  vim.o.columns = 60
  report.narrow = SOLStatus()
  vim.o.columns = 50
  report.tiny = SOLStatus()
  local refused = 0
  for _, bad in ipairs({{first = -1, total = 3}, {first = 3, total = 3}, {first = 0}, 'half'}) do
    local broken = vim.deepcopy(payload); broken.progress = bad
    if not pcall(assert(loadfile(os.getenv('SOL_NVIM_ADAPTER'))), broken) then refused = refused + 1 end
  end
  report.refused = refused
''', integrated=True)
        status = report["status"]
        self.assertTrue(status.startswith(" Quality · p."), status)
        self.assertIn(f"p. {self.sample.passages[1].printed_page}", status)
        self.assertIn("%=   Continuous · 50%% · ? keys · :q quit ", status)  # %% is a literal %
        # Too narrow for both halves: the path gives way from its start, never the gap.
        self.assertTrue(report["tiny"].startswith(" …"), report["tiny"])
        self.assertIn("%=   Continuous", report["tiny"])
        self.assertEqual(report["refused"], 4)

    def test_context_opens_beside_the_page_when_there_is_room(self):
        report = self.run_lua(r'''
  local function geometry(window)
    local config = vim.api.nvim_win_get_config(window)
    return {col = config.col, width = config.width, row = config.row}
  end
  local function popup()
    for _, window in ipairs(vim.api.nvim_list_wins()) do
      if vim.api.nvim_win_get_config(window).zindex == 50 then return window end
    end
  end
  vim.o.columns, vim.o.lines = 160, 40
  vim.api.nvim_exec_autocmds('VimResized', {})
  local centred = geometry(reader.window)
  vim.api.nvim_feedkeys('c', 'xt', false)
  report.wide = {page = geometry(reader.window), panel = geometry(popup()), centred = centred}
  local panel_buffer = vim.api.nvim_win_get_buf(popup())
  local marks = {}
  for _, mark in ipairs(vim.api.nvim_buf_get_extmarks(panel_buffer, -1, 0, -1, {details = true})) do
    marks[mark[4].hl_group] = (marks[mark[4].hl_group] or 0) + 1
  end
  report.marks = marks
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  report.closed = geometry(reader.window)
  vim.o.columns = 100
  vim.api.nvim_exec_autocmds('VimResized', {})
  vim.api.nvim_feedkeys('c', 'xt', false)
  report.narrow = {page = geometry(reader.window), panel = geometry(popup())}
''', integrated=True)
        wide = report["wide"]
        self.assertLess(wide["page"]["col"], wide["centred"]["col"])
        self.assertGreaterEqual(wide["panel"]["col"], wide["page"]["col"] + wide["page"]["width"] + 1)
        self.assertLessEqual(wide["panel"]["col"] + wide["panel"]["width"] + 2, 160)
        self.assertEqual(wide["panel"]["row"], wide["page"]["row"])
        self.assertGreater(report["marks"].get("SOLSourceHeading", 0), 1)
        self.assertGreater(report["marks"].get("NonText", 0), 0)
        self.assertEqual(report["closed"], wide["centred"])
        # Too narrow to share: the panel opens over the page, which stays centred.
        narrow = report["narrow"]
        self.assertEqual(narrow["page"]["col"], (100 - narrow["page"]["width"]) // 2)
        self.assertLess(narrow["panel"]["col"], narrow["page"]["col"] + narrow["page"]["width"])

    def test_note_editor_opens_beside_the_page_when_there_is_room(self):
        report = self.run_lua(r"""
  local function geometry(window)
    local config = vim.api.nvim_win_get_config(window)
    return {col = config.col, width = config.width, row = config.row, height = config.height}
  end
  local function editor()
    for _, window in ipairs(vim.api.nvim_list_wins()) do
      if vim.api.nvim_win_get_config(window).zindex == 50 then return window end
    end
  end
  data.personal = {persistent = true, notes = {}}
  for _, columns in ipairs({160, 100}) do
    vim.o.columns, vim.o.lines = columns, 40
    assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(vim.deepcopy(data))
    local reader = SOLNvimReader
    local centred = geometry(reader.window)
    reader.note()
    report[tostring(columns)] = {page = geometry(reader.window), editor = geometry(editor()), centred = centred,
                                 insert = vim.fn.mode(1)}
    vim.api.nvim_feedkeys(vim.keycode('<C-c>'), 'xt', false)
    report[tostring(columns)].closed = geometry(reader.window)
  end
  -- Reported by Codex's review of #36: :q! left the page shifted.
  -- Drafts live on the reader's channel; a stand-in keeps them here.
  _G.SOLReaderChannel = {serial = 0, pending = {}, incoming = '', writer = {write = function() end}}
  vim.o.columns = 160
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(vim.deepcopy(data))
  local reader = SOLNvimReader
  local before = geometry(reader.window)
  reader.note()
  vim.api.nvim_buf_set_lines(0, 0, -1, false, {'A draft to keep'})
  vim.cmd('stopinsert')
  vim.cmd('q!')
  vim.wait(50)
  report.forced = {before = before, after = geometry(reader.window),
                   focused = vim.api.nvim_get_current_win() == reader.window}
  reader.note()
  report.forced.draft = vim.api.nvim_buf_get_lines(0, 0, -1, false)
""", integrated=True)
        wide, narrow = report["160"], report["100"]
        self.assertLess(wide["page"]["col"], wide["centred"]["col"])
        self.assertGreaterEqual(wide["editor"]["col"], wide["page"]["col"] + wide["page"]["width"] + 1)
        self.assertEqual(wide["editor"]["height"], wide["page"]["height"] - 2)
        self.assertEqual(wide["closed"], wide["centred"])
        # Too narrow: over the page as before, which stays centred.
        self.assertEqual(narrow["page"], narrow["centred"])
        self.assertLess(narrow["editor"]["col"], narrow["page"]["col"] + narrow["page"]["width"])
        forced = report["forced"]
        self.assertEqual(forced["after"], forced["before"])
        self.assertTrue(forced["focused"])
        self.assertEqual(forced["draft"], ["A draft to keep"])

    def test_note_editor_quotes_the_selection_exactly(self):
        text = self.sample.passages[1].text
        report = self.run_lua(r"""
  data.personal = {persistent = true, notes = {}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(vim.deepcopy(data))
  local reader = SOLNvimReader
  local id = data.records[2].id
  reader.restore(reader.capture('v', reader.source_point(id, 0), reader.source_point(id, 29)))
  reader.note()
  local quoted = {}
  for _, mark in ipairs(vim.api.nvim_buf_get_extmarks(0, -1, 0, -1, {details = true})) do
    for _, line in ipairs(mark[4].virt_lines or {}) do quoted[#quoted + 1] = line[1][1] end
  end
  report.quoted = quoted
""", integrated=True)
        self.assertEqual(report["quoted"][0], " ".join(text[:30].split()))
        self.assertIn("s", report["quoted"][0])

    def test_note_times_are_shown_in_local_time(self):
        self.environment = {**self.environment, "TZ": "Europe/Amsterdam"}
        report = self.run_lua(r'''
  data.personal = {persistent = true, notes = {[data.records[1].id] = {{
    id = 'mine', author = 'Invented reader', created_at = '2026-10-17T12:00:00Z', revision = 1,
    edit_refusal = '', changed_source = false, retired_target = false, body = 'x', lines = {'x'}}}}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(vim.deepcopy(data))
  SOLNvimReader.context()
  report.lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
''', integrated=True)
        # 12:00 UTC on 17 October is 14:00 in Amsterdam (summer time).
        self.assertIn("  Invented reader · 17 Oct 2026, 14:00 · revision 1", report["lines"])

    def test_essence_asks_the_reader_to_open_a_source_and_saves_when_the_reader_quits(self):
        # A stand-in for ESSENCE in a raw terminal: on "g" it sends a foreign
        # OSC, a malformed SOL request and a valid one; on Ctrl-Q it saves and leaves.
        saved = self.root / "essence_saved"
        request = {"version": 1, "op": "open_source",
                   "source": {"id": self.sample.passages[1].identifier, "start": 5, "content_sha256": "a" * 64}}
        encoded = base64.b64encode(json.dumps(request).encode()).decode()
        stub = self.root / "essence_stub.py"
        stub.write_text(f"""import os, sys, tty
tty.setraw(0)
print('ESSENCE STUB READY', end='', flush=True)
while True:
    key = os.read(0, 1)
    if key == b'g':
        os.write(1, b'\\x1b]0;a title\\x07\\x1b]5379;sol-essence;not-json\\x07')
        os.write(1, b'\\x1b]5379;sol-essence;{encoded}\\x07')
    elif key in (b'\\x11', b''):
        open({str(saved)!r}, 'w').write('saved ' + os.environ.get('XDG_DATA_HOME', ''))
        break
""", encoding="utf-8")
        paths = f"local PYTHON, STUB = {json.dumps(sys.executable)}, {json.dumps(str(stub))}\n"
        report = self.run_lua(paths + r'''
  vim.o.columns, vim.o.lines = 140, 40
  local sent, warnings = {}, {}
  vim.notify = function(message) warnings[#warnings + 1] = message end
  _G.SOLReaderChannel = {serial = 0, pending = {}, incoming = '',
    writer = {write = function(_, line) sent[#sent + 1] = vim.json.decode(line) end}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(vim.deepcopy(data))
  local reader = SOLNvimReader
  vim.api.nvim_feedkeys('E', 'xt', false)
  _G.SOLReaderChannel.pending[sent[1].id]({essence = {command = {PYTHON, STUB}, env = {XDG_DATA_HOME = '/invented/data'}}})
  local essence = assert(SOLEssence)
  assert(vim.wait(5000, function()
    return table.concat(vim.api.nvim_buf_get_lines(essence.buffer, 0, -1, false), '\n'):find('ESSENCE STUB READY') ~= nil
  end, 10), 'ESSENCE did not start in its terminal')
  essence.toggle()
  report.before = essence.layout
  -- In a real terminal ESSENCE has the keyboard in terminal mode, which ends
  -- only after the request's callback returns; a script cannot stay in it,
  -- so report it, then announce the change as Neovim does.
  local real_mode, terminal = vim.fn.mode, true
  vim.fn.mode = function(...) if terminal then return 't' end return real_mode(...) end
  vim.fn.chansend(essence.job, 'g')
  assert(vim.wait(5000, function() return vim.api.nvim_get_current_win() == SOLNvimReader.window end, 10),
    'the reader was not shown')
  vim.wait(200)
  report.while_terminal = #sent
  terminal = false
  vim.api.nvim_exec_autocmds('ModeChanged', {pattern = 't:n'})
  vim.fn.mode = real_mode
  assert(vim.wait(5000, function() return #sent > 1 end, 10), 'no source request reached the reader')
  vim.wait(200)
  report.requests = {}
  for index = 2, #sent do report.requests[#report.requests + 1] = {op = sent[index].op, source = sent[index].source} end
  report.after = {layout = essence.layout, focused_reader = vim.api.nvim_get_current_win() == SOLNvimReader.window,
                  alive = vim.api.nvim_win_is_valid(essence.window)}
  report.warnings = warnings
  _G.SOLReaderChannel.pending[sent[#sent].id] = nil
  _G.SOLReaderChannel.navigation_pending = nil
  -- Popups keep to the reader's columns while ESSENCE is beside it.
  vim.api.nvim_feedkeys('c', 'xt', false)
  local popup
  for _, window in ipairs(vim.api.nvim_list_wins()) do
    local config = vim.api.nvim_win_get_config(window)
    if config.relative ~= '' and config.zindex == 50 then popup = config end
  end
  local beside = vim.api.nvim_win_get_config(essence.window)
  report.popup = {right = popup.col + popup.width + 2, essence = beside.col}
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes('<Esc>', true, false, true), 'xt', false)
  -- Quitting the reader lets ESSENCE save first.
  report.autocmds = #vim.api.nvim_get_autocmds({group = 'SOLEssence', event = 'VimLeavePre'})
  local job = essence.job
  essence.save_before_exit()
  report.exited = vim.fn.jobwait({job}, 0)[1] ~= -1
''', integrated=True)
        self.assertEqual(report["before"], "full")
        self.assertEqual(report["while_terminal"], 1)  # only E's request: nothing sent from terminal mode
        self.assertEqual(report["requests"], [{"op": "essence_source", "source": request["source"]}])
        self.assertEqual(report["after"], {"layout": "split", "focused_reader": True, "alive": True})
        self.assertEqual(report["warnings"], ["ESSENCE sent an invalid source request"])
        self.assertLessEqual(report["popup"]["right"], report["popup"]["essence"])
        self.assertEqual(report["autocmds"], 1)
        self.assertTrue(report["exited"])
        self.assertEqual(saved.read_text(), "saved /invented/data")

    def test_essence_from_a_selection_returns_to_the_exact_selection(self):
        # Reported by Codex's review of PR #24.
        stub = self.root / "essence_stub.py"
        stub.write_text("import sys\nprint('ESSENCE STUB READY', flush=True)\nsys.stdin.readline()\n", encoding="utf-8")
        text = self.sample.passages[0].text
        start, end = text.index("𝔸"), text.index("ground") + len("ground")
        paths = f"local PYTHON, STUB, FIRST, LAST = {json.dumps(sys.executable)}, {json.dumps(str(stub))}, {start}, {end - 1}\n"
        report = self.run_lua(paths + r'''
  vim.o.columns, vim.o.lines = 140, 40
  local sent = {}
  _G.SOLReaderChannel = {serial = 0, pending = {}, incoming = '',
    writer = {write = function(_, line) sent[#sent + 1] = vim.json.decode(line) end}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(vim.deepcopy(data))
  reader = SOLNvimReader
  local id = data.records[1].id
  report.cases = {}
  for _, direction in ipairs({'forward', 'reverse'}) do
    local a, b = reader.source_point(id, FIRST), reader.source_point(id, LAST)
    if direction == 'reverse' then a, b = b, a end
    local selected = reader.capture('v', a, b)
    reader.restore(selected)
    local case = {mode = vim.fn.mode()}
    vim.api.nvim_feedkeys('E', 'xt', false)
    local request = sent[#sent]
    case.op, case.selection = request.op, request.packet.selection ~= vim.NIL
    case.sent_matches = vim.deep_equal(request.packet, selected)
    request = request.id
    _G.SOLReaderChannel.pending[request]({essence = {command = {PYTHON, STUB}}})
    assert(vim.wait(5000, function() return SOLEssence.job ~= nil end, 10))
    SOLEssence.back_to_reader()
    case.after_back = vim.deep_equal(SOLNvimReader.capture(), selected)
    -- E from the restored selection refocuses ESSENCE without a new request.
    local before = #sent
    vim.api.nvim_feedkeys('E', 'xt', false)
    case.refocused = #sent == before and vim.api.nvim_get_current_win() == SOLEssence.window
    vim.fn.chansend(SOLEssence.job, 'q\n')
    assert(vim.wait(5000, function() return SOLEssence.window == nil end, 10))
    case.after_close = vim.deep_equal(SOLNvimReader.capture(), selected)
    case.cursor = SOLNvimReader.capture().cursor_offset
    report.cases[direction] = case
    vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  end
  -- Reported by Codex's re-review: a refused launch keeps the selection.
  local warnings = {}
  vim.notify = function(message) warnings[#warnings + 1] = message end
  local selected = SOLNvimReader.capture('v', SOLNvimReader.source_point(id, FIRST), SOLNvimReader.source_point(id, LAST))
  SOLNvimReader.restore(selected)
  vim.api.nvim_feedkeys('E', 'xt', false)
  _G.SOLReaderChannel.pending[sent[#sent].id](nil, 'ESSENCE needs Textual')
  report.refused = {mode = vim.fn.mode(), exact = vim.deep_equal(SOLNvimReader.capture(), selected),
                    warning = warnings[#warnings], window = SOLEssence.window == nil}
''', integrated=True)
        for direction, cursor in (("forward", end), ("reverse", start)):
            with self.subTest(direction=direction):
                case = report["cases"][direction]
                self.assertEqual(case["mode"], "v")
                self.assertEqual((case["op"], case["selection"], case["sent_matches"]), ("essence_open", True, True))
                self.assertTrue(case["after_back"])
                self.assertTrue(case["refocused"])
                self.assertTrue(case["after_close"])
                self.assertEqual(case["cursor"], cursor)
        self.assertEqual(report["refused"], {"mode": "v", "exact": True, "warning": "ESSENCE needs Textual",
                                             "window": True})

    def test_footnote_callouts_show_inline_without_changing_source_text(self):
        report = self.run_lua(r'''
  local payload = vim.deepcopy(data)
  payload.records[1].callouts = {{offset = 4, label = '12'}, {offset = 0, label = 'k'}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(payload)
  reader = SOLNvimReader
  local id = data.records[1].id
  report.marks = {}
  for _, mark in ipairs(vim.api.nvim_buf_get_extmarks(reader.buffer, -1, 0, -1, {details = true})) do
    local details = mark[4]
    if details.virt_text_pos == 'inline' then
      report.marks[#report.marks + 1] = {mark[2], mark[3], details.virt_text[1][1]}
    end
  end
  report.expected = {point(id, 0), point(id, 4)}
  report.line = vim.api.nvim_buf_get_lines(reader.buffer, report.expected[1][1] - 1, report.expected[1][1], false)[1]
  local broken = vim.deepcopy(data)
  broken.records[1].callouts = {{offset = data.records[1]._length or 1e9, label = '1'}}
  report.refused = not pcall(loadfile(os.getenv('SOL_NVIM_ADAPTER')), broken)
''')
        text = self.sample.passages[0].text
        self.assertEqual(report["line"], text.split("\n")[0])
        expected = sorted([[report["expected"][0][0] - 1, report["expected"][0][1], "[k]"],
                           [report["expected"][1][0] - 1, report["expected"][1][1], "¹²"]])
        self.assertEqual(sorted(report["marks"]), expected)
        self.assertTrue(report["refused"])

    def prepare_footnote_panels(self):
        from fixtures_footnotes import add_footnote_corpus
        from sol.terminal import neovim
        identifier = self.sample.passages[0].identifier
        notes, _ = add_footnote_corpus(self.corpus, identifier)
        self.sample = sample_from_book(load_corpus_book(self.corpus), count=3)
        panels = {"root": neovim.build_footnote_payload(self.sample, identifier, notes[:1]),
                  "nested": neovim.build_footnote_payload(self.sample, identifier, notes[:2])}
        (self.root / "footnotes.json").write_text(json.dumps(panels, ensure_ascii=False), encoding="utf-8")
        self.before = {path.name: path.read_bytes() for path in self.corpus.iterdir()}

    def test_book_footnotes_keep_styles_nested_links_and_exact_selection_in_both_modes(self):
        self.prepare_footnote_panels()
        report = self.run_lua(r'''
  local file = assert(io.open('footnotes.json')); local panels = vim.json.decode(file:read('*a')); file:close()
  local sent = {}
  _G.SOLReaderChannel = {serial = 0, pending = {}, incoming = '',
    writer = {write = function(_, line) sent[#sent + 1] = vim.json.decode(line) end}}
  local errors = {}
  vim.notify = function(message) errors[#errors + 1] = message end
  local function row_of(text)
    for row, line in ipairs(vim.api.nvim_buf_get_lines(0, 0, -1, false)) do
      if line:find(text, 1, true) then return row end
    end
    error('no panel row: ' .. text)
  end
  local function choose(text)
    vim.api.nvim_win_set_cursor(0, {row_of(text), 0})
    vim.api.nvim_feedkeys(vim.keycode('<CR>'), 'xt', false)
  end
  local function respond(name)
    local last = sent[#sent]
    assert(last.op == 'footnote_open')
    SOLReaderChannel.pending[last.id]({footnote = panels[name]})
  end
  report.checks, report.marks = 0, 0
  for _, width in ipairs({72, 20}) do
    for _, mode in ipairs({'continuous', 'paragraph'}) do
      for _, reverse in ipairs({false, true}) do
        vim.o.columns, vim.o.lines = width + 6, 24
        local payload = vim.deepcopy(data)
        payload.mode, payload.width = mode, width
        assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(payload)
        reader = SOLNvimReader
        local id = data.records[1].id
        local a, b = reader.source_point(id, 5), reader.source_point(id, 36)
        local origin = reader.capture('v', reverse and b or a, reverse and a or b)
        reader.restore(origin)
        -- The actual visual-mode c mapping accepts and remembers the selection.
        vim.api.nvim_feedkeys('c', 'xt', false)
        assert(vim.fn.mode(1) == 'n')
        local listing = table.concat(vim.api.nvim_buf_get_lines(0, 0, -1, false), '\n')
        assert(listing:find('Footnotes', 1, true))
        assert(not listing:find('first thought', 1, true), 'book text should be read in its own panel')
        choose('[12]')
        assert(vim.deep_equal(sent[#sent].packet, origin) and sent[#sent].mode == mode)
        respond('root')
        local root_lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
        assert(root_lines[1] == 'Book footnote [12]')
        local text = table.concat(root_lines, '\n')
        assert(text:find('Invented translator', 1, true) and text:find('Another editor', 1, true))
        assert(text:find('Note transcription needs review.', 1, true))
        assert(text:find('α first thought é.', 1, true))
        local marks = vim.api.nvim_buf_get_extmarks(0, -1, 0, -1, {details = true})
        local styled, callout = {}, false
        for _, mark in ipairs(marks) do
          local detail = mark[4]
          if detail.hl_group and detail.hl_group:find('SOLSemantic_', 1, true) then
            local line = root_lines[mark[2] + 1]
            styled[#styled + 1] = line:sub(mark[3] + 1, detail.end_col)
          elseif detail.virt_text_pos == 'inline' then
            assert(detail.virt_text[1][1] == '⁷')
            callout = true
          end
        end
        assert(vim.deep_equal(styled, {'first', 'second', 'line'}))
        assert(callout)
        report.marks = report.marks + #styled
        choose('[7]'); respond('nested')
        assert(#sent[#sent].trail == 2)
        assert(vim.api.nvim_buf_get_lines(0, 0, 1, false)[1] == 'Book footnote [7]')
        local count = #sent
        choose('[12]')
        assert(#sent == count and errors[#errors]:find('Cycle', 1, true))
        vim.api.nvim_feedkeys(vim.keycode('<BS>'), 'xt', false)
        assert(vim.api.nvim_buf_get_lines(0, 0, 1, false)[1] == 'Book footnote [12]')
        assert(vim.api.nvim_win_get_cursor(0)[1] == row_of('[7]'))
        vim.api.nvim_feedkeys(vim.keycode('<BS>'), 'xt', false)
        assert(vim.api.nvim_win_get_cursor(0)[1] == row_of('[12]'))
        choose('[12]'); respond('root')
        vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
        assert(vim.deep_equal(reader.capture(), origin))
        assert(reader.mode == mode)
        -- The passage's native yank remains exact around the inline callout.
        reader.yank()
        assert(vim.fn.getreg('"') == origin.selection.text)
        report.checks = report.checks + 1
        vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
      end
    end
  end
''', integrated=True)
        self.assertEqual(report["checks"], 8)
        self.assertEqual(report["marks"], 24)

    def test_footnote_failure_late_reply_and_resize_preserve_the_reading_origin(self):
        self.prepare_footnote_panels()
        report = self.run_lua(r'''
  local file = assert(io.open('footnotes.json')); local panels = vim.json.decode(file:read('*a')); file:close()
  local sent = {}
  _G.SOLReaderChannel = {serial = 0, pending = {}, incoming = '',
    writer = {write = function(_, line) sent[#sent + 1] = vim.json.decode(line) end}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(vim.deepcopy(data)); reader = SOLNvimReader
  local id = data.records[1].id
  local origin = reader.capture('v', reader.source_point(id, 5), reader.source_point(id, 13))
  local errors = {}; vim.notify = function(message) errors[#errors + 1] = message end
  local function open()
    reader.restore(origin); reader.context()
    for row, line in ipairs(vim.api.nvim_buf_get_lines(0, 0, -1, false)) do
      if line:find('[12]', 1, true) then vim.api.nvim_win_set_cursor(0, {row, 0}); break end
    end
    vim.api.nvim_feedkeys(vim.keycode('<CR>'), 'xt', false)
  end
  open()
  local panel = vim.api.nvim_get_current_win()
  SOLReaderChannel.pending[sent[#sent].id](nil, 'The canonical corpus changed; reopen it.')
  assert(vim.api.nvim_get_current_win() == panel and errors[#errors]:find('corpus changed', 1, true))
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  assert(vim.deep_equal(reader.capture(), origin))
  open()
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  SOLReaderChannel.pending[sent[#sent].id]({footnote = panels.root})
  assert(vim.api.nvim_get_current_win() == reader.window)
  assert(vim.deep_equal(reader.capture(), origin))
  open(); SOLReaderChannel.pending[sent[#sent].id]({footnote = panels.root})
  vim.o.columns = 26
  vim.api.nvim_exec_autocmds('VimResized', {})
  assert(vim.api.nvim_get_current_win() == reader.window)
  assert(vim.deep_equal(reader.capture(), origin))
  open(); SOLReaderChannel.pending[sent[#sent].id]({footnote = panels.root})
  vim.cmd('q')
  assert(vim.api.nvim_get_current_win() == reader.window)
  assert(vim.deep_equal(reader.capture(), origin))
  -- Native window close must not leave a saved popup packet shadowing motion.
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  vim.api.nvim_win_set_cursor(reader.window, point(id, 20))
  assert(reader.capture().cursor_offset == 20)
  report.ok = true
''', integrated=True)
        self.assertTrue(report["ok"])

    def test_search_marks_highlight_matches_until_escape(self):
        report = self.run_lua(r'''
  local payload = vim.deepcopy(data)
  payload.search_marks = {id = data.records[1].id, spans = {{0, 3}}}
  assert(loadfile(os.getenv('SOL_NVIM_ADAPTER')))(payload)
  reader = SOLNvimReader
  local function count()
    local found = 0
    for _, mark in ipairs(vim.api.nvim_buf_get_extmarks(reader.buffer, -1, 0, -1, {details = true})) do
      if mark[4].hl_group == 'Search' then found = found + 1 end
    end
    return found
  end
  report.before = count()
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  report.after = count()
  local broken = vim.deepcopy(data)
  broken.search_marks = {id = data.records[1].id, spans = {{2, 1}}}
  report.refused = not pcall(loadfile(os.getenv('SOL_NVIM_ADAPTER')), broken)
''', integrated=True)
        self.assertEqual((report["before"], report["after"]), (1, 0))
        self.assertTrue(report["refused"])

    def test_dismissed_search_marks_stay_hidden_until_a_new_result(self):
        report = self.run_lua(r'''
  local adapter = os.getenv('SOL_NVIM_ADAPTER')
  local payload = vim.deepcopy(data)
  payload.search_marks = {id = data.records[1].id, spans = {{0, 4}}}
  assert(loadfile(adapter))(vim.deepcopy(payload))
  reader = SOLNvimReader
  local function count()
    local found = 0
    for _, mark in ipairs(vim.api.nvim_buf_get_extmarks(SOLNvimReader.buffer, -1, 0, -1, {details = true})) do
      if mark[4].hl_group == 'Search' then found = found + 1 end
    end
    return found
  end
  report.counts = {shown = count()}
  vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
  report.counts.escape = count()
  -- Every view rebuilt from the current one keeps the dismissal.
  vim.api.nvim_feedkeys('p', 'xt', false)
  report.counts.paragraph = count()
  vim.api.nvim_feedkeys(']p', 'xt', false)
  vim.api.nvim_feedkeys('[p', 'xt', false)
  report.counts.paragraph_back = count()
  vim.api.nvim_feedkeys('p', 'xt', false)
  report.counts.continuous = count()
  vim.api.nvim_feedkeys('f', 'xt', false)
  report.counts.focus = count()
  vim.o.columns = 50
  vim.api.nvim_exec_autocmds('VimResized', {})
  report.counts.resize = count()
  vim.api.nvim_feedkeys('T', 'xt', false)
  report.counts.theme = count()
  -- A deliberate new result arrives as a new payload and shows its marks.
  assert(loadfile(adapter))(vim.deepcopy(payload))
  report.counts.new_result = count()
''', integrated=True, theme="terminal")
        self.assertEqual(report["counts"], {"shown": 1, "escape": 0, "paragraph": 0, "paragraph_back": 0,
                                            "continuous": 0, "focus": 0, "resize": 0, "theme": 0, "new_result": 1})

    def test_selection_and_yank_are_exact_around_callouts_in_both_modes_and_widths(self):
        text = self.sample.passages[0].text
        start, end = text.index("𝔸"), text.index("ground") + len("ground")
        report = self.run_lua(r'''
  local adapter = os.getenv('SOL_NVIM_ADAPTER')
  local clip_file = vim.fn.tempname()
  vim.env.SOL_NVIM_CLIPBOARD = vim.json.encode({command = {'sh', '-c', 'cat > "$0"', clip_file}, env = vim.empty_dict()})
  local function clipboard()
    local stream = io.open(clip_file)
    if not stream then return nil end
    local text = stream:read('a'); stream:close(); os.remove(clip_file)
    return text
  end
  local payload = vim.deepcopy(data)
  -- Callouts inside the selection, beside a combining mark and at its edge.
  payload.records[1].callouts = {{offset = ''' + str(start) + r''', label = '3'},
    {offset = ''' + str(text.index("é") + 2) + r''', label = 'k'},
    {offset = ''' + str(end) + r''', label = '14'}}
  report.yanks = {}
  for _, width in ipairs({72, 24}) do
    payload.width = width
    assert(loadfile(adapter))(vim.deepcopy(payload))
    for _, mode in ipairs({'continuous', 'paragraph'}) do
      reader = SOLNvimReader
      if reader.mode ~= mode then reader.toggle_mode(); reader = SOLNvimReader end
      local id = data.records[1].id
      local first = reader.source_point(id, ''' + str(start) + r''')
      local last = reader.source_point(id, ''' + str(end - 1) + r''')
      for _, ends in ipairs({{first, last}, {last, first}}) do
        local packet = reader.capture('v', ends[1], ends[2])
        reader.restore(packet)
        reader.yank()
        report.yanks[#report.yanks + 1] = {width, mode, packet.selection.start, packet.selection['end'], clipboard()}
        vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
      end
    end
  end
''', integrated=True)
        self.assertEqual(len(report["yanks"]), 8)
        for width, mode, first, last, copied in report["yanks"]:
            with self.subTest(width=width, mode=mode):
                self.assertEqual((first, last, copied), (start, end, text[start:end]))

    def test_theme_survives_mode_reload_and_invalid_presets_are_refused(self):
        report = self.run_lua(r'''
  reader.cycle_theme()
  vim.api.nvim_feedkeys('p', 'xt', false)
  reader = SOLNvimReader
  assert(reader.mode == 'paragraph' and reader.theme() == 'latte')
  vim.api.nvim_feedkeys('T', 'xt', false)
  assert(SOLNvimReader.theme() == 'paper')
  local adapter = os.getenv('SOL_NVIM_ADAPTER')
  local refused = 0
  for _, change in ipairs({
    function(theme) theme.presets[2].groups.Normal.fg = 'red' end,
    function(theme) theme.presets[2].groups.Normal.ctermfg = 256 end,
    function(theme) theme.presets[2].groups.Normal.link = 'Comment' end,
    function(theme) theme.presets[2].groups.Conceal = {} end,
    function(theme) theme.active = 'sepia' end,
    function(theme) theme.extra = true end,
  }) do
    local payload = vim.deepcopy(data)
    change(payload.theme)
    local accepted = pcall(assert(loadfile(adapter)), payload)
    if not accepted then refused = refused + 1 end
  end
  report.refused = refused
''', theme="mocha", integrated=True)
        self.assertEqual(report["refused"], 6)


if __name__ == "__main__":
    unittest.main()
