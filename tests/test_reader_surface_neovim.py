"""Real, isolated Neovim API proofs over invented, disposable source records.

These are headless editor checks, not a claim of physical-keyboard or sustained
reading acceptance. No user configuration, canonical project corpus, personal
workspace, network, package installation, or terminal emulator is used.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from sol.core.corpus import load_corpus_book
from sol.corpus import contract
from experiments.reader_surfaces.common import sample_from_book, validate_packet
from test_packaging import write_runtime_corpus


_ROOT = Path(__file__).resolve().parents[1]
_ADAPTER = _ROOT / "experiments/reader_surfaces/neovim.lua"
_GENERATED = {"markdown", "plain_text", "document", "context", "content_sha256"}


def neovim_environment(root):
    """Redirect editor-generated state without changing the user's home."""
    environment = {**os.environ,
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_STATE_HOME": str(root / "state"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "NVIM_LOG_FILE": str(root / "neovim.log")}
    for key in tuple(environment):
        if key.startswith(("SOL_", "KITTY_")) or key in {
            "VIMINIT", "EXINIT", "GVIMINIT", "NVIM_APPNAME", "NVIM", "NVIM_LISTEN_ADDRESS"}:
            environment.pop(key)
    return environment


def invented_sample(root):
    """Create exact source/index bindings without depending on a Markdown parser."""
    corpus = root / "corpus"
    identifier, _ = write_runtime_corpus(corpus)
    records = [json.loads(line) for line in (corpus / "index.jsonl").read_text().splitlines()]
    first = records[1]
    first["markdown"] = "Lead 𝔸 *thought* e\u0301 and **ground**, Greek α, CJK 界.\nNext\tline `code` repeats."
    first["plain_text"] = "Lead 𝔸 thought e\u0301 and ground, Greek α, CJK 界.\nNext\tline code repeats."
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

    def run_lua(self, scenario, *, restore=None, automatic_quit=True):
        from experiments.reader_surfaces.neovim import build_payload

        self.payload = build_payload(self.sample, width=72, restore=restore)
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


if __name__ == "__main__":
    unittest.main()
