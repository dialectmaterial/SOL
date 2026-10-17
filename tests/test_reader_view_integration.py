"""Opt-in real Kitty reading surface; synthetic text and private test settings."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from sol.corpus import contract
from sol.terminal.kitty import KITTY_PROFILE
from fixtures_corpus import write_runtime_corpus


PROGRAM = '''
import asyncio, json, os, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
root = Path(sys.argv[2])
sys.stderr = (root / "errors.txt").open("w")
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.keys import Keys
from experiments.reader_surfaces import baseline as reader
from sol.reader import app

class CheckedView(reader.ReaderView):
    def run(self):
        async def scenario():
            task = asyncio.create_task(self.application.run_async())
            async def wait(condition):
                deadline = asyncio.get_running_loop().time() + 5
                while not condition():
                    if asyncio.get_running_loop().time() >= deadline:
                        raise AssertionError("Reader workflow did not reach its expected state: " + repr({
                            "cursor":self.body.buffer.cursor_position, "semantic":self.actions.cursor_offset,
                            "selection":self.actions.selection, "status":self.status,
                            "focus":self.application.layout.current_control}))
                    await asyncio.sleep(.01)
                await asyncio.sleep(.05)
            def keys(*values):
                self.application.key_processor.feed_multiple([
                    KeyPress(value, value if isinstance(value, str) and len(value) == 1 else "") for value in values])
                self.application.key_processor.process_keys()
                self.application.invalidate()
            try:
                await wait(lambda: self.application.is_running and self.application.renderer.height_is_known)
                address = os.environ.get("KITTY_LISTEN_ON", "")
                descriptors = (int(address[3:]),) if address.startswith("fd:") else ()
                screen = subprocess.run(["kitten", "@", "--password-env=KITTY_RC_PASSWORD",
                        "--use-password=always", "get-text", "--match", "id:" + os.environ["KITTY_WINDOW_ID"]],
                        capture_output=True, text=True, pass_fds=descriptors, timeout=5, check=True).stdout
                assert "p. 7" in screen and "Synthetic section" in screen, screen
                assert "An invented passage" in screen, screen
                assert self.body.window.render_info.window_width <= self.reading_width
                assert not self.typography.degraded
                assert any('emphasis' in span.styles for span in self.typography.spans)
                styled_screen = subprocess.run(["kitten", "@", "--password-env=KITTY_RC_PASSWORD",
                        "--use-password=always", "get-text", "--ansi", "--match", "id:" + os.environ["KITTY_WINDOW_ID"]],
                        capture_output=True, text=True, pass_fds=descriptors, timeout=5, check=True).stdout
                assert re.search(r"\\x1b\\[(?:[0-9]+;)*3(?:;[0-9]+)*m", styled_screen), repr(styled_screen)
                keys("c")
                await wait(lambda: self._context_visible)
                keys("c")
                await wait(lambda: not self._context_visible)
                first = self.actions.snapshot().current.identifier
                keys(Keys.ShiftRight, Keys.ShiftRight, Keys.ShiftRight)
                await wait(lambda: self.actions.selection is not None and self.actions.selection.text == "An ")
                selected = self.actions.selection
                keys("/")
                keys(*"specific", Keys.ControlM)
                await wait(lambda: self.application.layout.has_focus(self.results))
                assert self.actions.snapshot().current.identifier == first
                assert len(self.actions.snapshot().results) == 1
                keys(Keys.ControlM)
                await wait(lambda: self.actions.snapshot().current.identifier != first)
                keys(Keys.Escape, Keys.Left)
                await wait(lambda: self.actions.snapshot().current.identifier == first)
                assert self.actions.selection == selected
                assert self.body.text == self.actions.snapshot().current.text
                assert self.actions.snapshot().search_query == "specific"
                (root / "result.json").write_text(json.dumps({"status":"passed", "selected_text":"An ",
                    "search_return_restored":True, "pages_visible":True}))
            finally:
                if not task.done():
                    self.application.exit(result=0)
                await task
            return 0
        return asyncio.run(scenario())

reader.ReaderView = CheckedView
assert reader.run_reader(app.load_corpus_book(root / "corpus")) == 0
'''


@unittest.skipUnless(os.environ.get("SOL_TEST_LIVE_KITTY") == "1", "real GUI test is explicit opt-in")
@unittest.skipUnless(importlib.util.find_spec("prompt_toolkit"), "optional prompt_toolkit is absent")
class ReaderViewIntegrationTests(unittest.TestCase):
    def test_live_reading_selection_search_and_return_without_identifiers(self):
        if not shutil.which("kitty") or not shutil.which("kitten") or not (
                os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            self.skipTest("Kitty and a desktop display are required")
        with tempfile.TemporaryDirectory(prefix="sol-reader-live-test-") as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            write_runtime_corpus(corpus)
            manifest_bytes = (corpus / "corpus.json").read_bytes()
            manifest = json.loads(manifest_bytes)
            records = [json.loads(line) for line in (corpus / "index.jsonl").read_text().splitlines()]
            records[1]["markdown"] = records[1]["markdown"].replace("invented passage", "*invented passage*")
            records[1]["content_sha256"] = sha256(records[1]["markdown"].encode()).hexdigest()
            second = deepcopy(records[1])
            second.update(id="cccccccc-0000-4000-8000-000000000003", order=2,
                          markdown="A specific invented passage is reached through search, not copied identifiers.",
                          plain_text="A specific invented passage is reached through search, not copied identifiers.")
            second["content_sha256"] = sha256(second["markdown"].encode()).hexdigest()
            records.append(second)
            generated = {"markdown", "plain_text", "document", "context", "content_sha256"}
            markdown = "\n".join(contract.render_record(
                {key: value for key, value in row.items() if key not in generated}, row["markdown"])
                for row in records).encode()
            index = "".join(json.dumps(row) + "\n" for row in records).encode()
            (corpus / "sample.md").write_bytes(markdown)
            (corpus / "index.jsonl").write_bytes(index)
            (corpus / "index.meta.json").write_text(json.dumps({
                "contract_version": 1, "manifest_sha256": sha256(manifest_bytes).hexdigest(),
                "source_sha256": manifest["source"]["sha256"],
                "documents": {"sample.md": sha256(markdown).hexdigest()},
                "index_sha256": sha256(index).hexdigest(), "record_count": len(records)}))
            contract.initialize_corpus_identity(corpus)
            before = {path.name: path.read_bytes() for path in corpus.iterdir()}
            (root / "reader.py").write_text(PROGRAM)
            token = secrets.token_hex(24)
            # This test window can read its own rendered text. Production SOL
            # remains limited to its existing ls/launch/close-window permissions.
            launch = ["launch", "--allow-remote-control", "--remote-control-password=!",
                      "--remote-control-password=" + f'"{token}" get-text',
                      "--env=KITTY_RC_PASSWORD=" + token, "--title=SOL isolated reader test",
                      sys.executable, "-I", "-B", str(root / "reader.py"),
                      str(Path(__file__).resolve().parents[1]), str(root)]
            (root / "session").write_text("layout splits\n" + shlex.join(launch) + "\n")
            (root / "kitty.conf").write_text(KITTY_PROFILE + "\ninitial_window_width 80c\ninitial_window_height 28c\n")
            environment = {**os.environ, "XDG_CONFIG_HOME": str(root / "config"),
                           "XDG_DATA_HOME": str(root / "data"), "XDG_CACHE_HOME": str(root / "cache")}
            for key in tuple(environment):
                if key in {"KITTY_LISTEN_ON", "KITTY_RC_PASSWORD", "SOL_KITTY_SESSION", "SOL_CORPUS"} \
                        or key.startswith(("SOL_ACTOR", "SOL_WORKSPACE")):
                    environment.pop(key)
            completed = subprocess.run(["kitty", "--config", str(root / "kitty.conf"),
                                        "--session", str(root / "session")], cwd=root, env=environment,
                                       capture_output=True, text=True, timeout=30)
            diagnostics = completed.stderr + ((root / "errors.txt").read_text() if (root / "errors.txt").exists() else "")
            self.assertEqual(completed.returncode, 0, diagnostics)
            self.assertTrue((root / "result.json").exists(), diagnostics)
            self.assertEqual(json.loads((root / "result.json").read_text()),
                             {"status":"passed", "selected_text":"An ", "search_return_restored":True, "pages_visible":True})
            self.assertEqual(before, {path.name: path.read_bytes() for path in corpus.iterdir()})
            self.assertFalse((root / "config" / "sol").exists())
            self.assertFalse(list(root.rglob("*.sqlite3")))


if __name__ == "__main__":
    unittest.main()
