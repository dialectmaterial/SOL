"""Opt-in real Kitty/Zsh round trip; never uses a personal corpus or shell rc.

SOL_TEST_LIVE_KITTY=1 python -B -m unittest discover -s tests \
    -p test_kitty_handoff_integration.py
"""
from __future__ import annotations

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


READER = '''
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from sol.reader import app
from sol.reader.actions import ReadingSession
from sol.core.paths import display_path, resolve_path
from sol.essence.terms import check_term_result
from sol.terminal.kitty import EssencePane
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace
from unittest.mock import patch

root = Path(sys.argv[2])
sys.stderr = (root / "reader-errors.txt").open("w")
book = app.load_corpus_book(root / "corpus")
pane = EssencePane()
session = ReadingSession(book)
output = []
steps = iter(["first", "essence", "wait", "essence check", "essence return", "accepted", "essence close"])
provenance = {key: book.corpus_manifest[key] for key in ("edition", "source")}

def emit(value="", end="\\n"):
    output.append(str(value) + end)

with Workspace(root / "test.sqlite3", book.corpus_manifest["corpus_id"], provenance, actor="Invented reader") as store:
    reader = WorkspaceReader(book, store, "Invented reader", resolve_path, display_path, app.render_passage)
    def read(prompt):
        try:
            command = next(steps)
        except StopIteration:
            raise EOFError from None
        if command == "wait":
            deadline = time.monotonic() + 10
            while not (root / "native-done").exists():
                if time.monotonic() > deadline:
                    raise RuntimeError("Native Zsh did not propose its return")
                time.sleep(.05)
            native = json.loads((root / "native-return.json").read_text())
            assert native["status"] == "proposed", native
            checked = json.loads((root / "native-check.json").read_text())
            assert checked["status"] == "current", checked
            study = json.loads((root / "invented.sol-analysis.json").read_text())
            assert check_term_result(book.corpus_snapshot, study) == study
            assert study["origin"]["reference"]["target_id"] == session.current().identifier
            assert study["totals"]["occurrences"] == 1
            assert native["target_id"] == study["matches"][0]["id"]
            receipt = json.loads((root / "native-analysis-check.json").read_text())
            assert receipt["status"] == "current"
            windows = json.loads(pane._remote("ls"))
            identifiers = {window["id"] for instance in windows for tab in instance["tabs"] for window in tab["windows"]}
            assert pane.window_id in identifiers and pane.reader_id in identifiers, identifiers
            assert store.get_state()["revision"] == 1
            assert len(store.list_history()) == 1
            assert (root / "native-control.txt").read_text().strip() == "unset:unset:unset:unset:unset"
            assert Path((root / "handoff-path.txt").read_text().strip()).is_dir()
            return ""
        if command == "accepted":
            assert store.get_state()["revision"] == 2
            assert len(store.list_history()) == 2
            assert pane.window_id is not None
            assert "Return accepted." in "".join(output), "".join(output)
            return ""
        return command
    with patch("sol.reader.shell.ReadingSession", return_value=session):
        result = app.run_shell(book, 80, workspace_reader=reader, read_command=read, write_output=emit, essence_pane=pane)
    assert result == 0
    assert len(store.list_history()) == 2
    assert pane.window_id is None
    assert not Path((root / "handoff-path.txt").read_text().strip()).exists()
(root / "result.json").write_text(json.dumps({"status": "passed", "visits": 2, "owned_pane_closed": True,
                                             "term_study_verified": True}))
'''


@unittest.skipUnless(os.environ.get("SOL_TEST_LIVE_KITTY") == "1", "real GUI smoke test is explicit opt-in")
class KittyHandoffIntegrationTests(unittest.TestCase):
    def test_actual_reader_native_reference_and_explicit_return(self):
        kitty, kitten, zsh = (shutil.which(name) for name in ("kitty", "kitten", "zsh"))
        if not all((kitty, kitten, zsh)) or not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            self.skipTest("Kitty, kitten, Zsh and a desktop display are required")
        with tempfile.TemporaryDirectory(prefix="sol-live-handoff-test-") as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            write_runtime_corpus(corpus)
            contract.initialize_corpus_identity(corpus)
            originals = {path.name: path.read_bytes() for path in corpus.iterdir()}
            (root / "reader.py").write_text(READER, encoding="utf-8")
            select = "import json,sys; print(json.load(open(sys.argv[1]))['matches'][0]['id'])"
            selector = shlex.join([sys.executable, "-I", "-B", "-c", select])
            (root / ".zshrc").write_text(
                'sol reference check "$SOL_REFERENCE_FILE" >"$SOL_TEST_ROOT/native-check.json" 2>>"$SOL_TEST_ROOT/native-errors.txt"\n'
                'sol analyze term invented --reference "$SOL_REFERENCE_FILE" --json '
                '>"$SOL_TEST_ROOT/invented.sol-analysis.json" 2>>"$SOL_TEST_ROOT/native-errors.txt"\n'
                'sol analyze check "$SOL_TEST_ROOT/invented.sol-analysis.json" --json '
                '>"$SOL_TEST_ROOT/native-analysis-check.json" 2>>"$SOL_TEST_ROOT/native-errors.txt"\n'
                'selected="$(' + selector + ' "$SOL_TEST_ROOT/invented.sol-analysis.json")"\n'
                'sol reference return "$selected" >"$SOL_TEST_ROOT/native-return.json" 2>>"$SOL_TEST_ROOT/native-errors.txt"\n'
                'print -r -- "$SOL_HANDOFF_DIR" >"$SOL_TEST_ROOT/handoff-path.txt"\n'
                'print -r -- "${KITTY_LISTEN_ON-unset}:${KITTY_RC_PASSWORD-unset}:${SOL_KITTY_SESSION-unset}:'
                '${SOL_ACTOR-unset}:${SOL_WORKSPACE-unset}" >"$SOL_TEST_ROOT/native-control.txt"\n'
                'print -r -- done >"$SOL_TEST_ROOT/native-done"\n', encoding="utf-8")
            password = secrets.token_hex(24)
            repository = str(Path(__file__).resolve().parents[1])
            launch = ["launch", "--allow-remote-control", "--remote-control-password=!",
                      "--remote-control-password=" + f'"{password}" ls launch close-window',
                      "--env=SOL_KITTY_SESSION=1", "--env=KITTY_RC_PASSWORD=" + password,
                      "--title=SOL isolated handoff test", sys.executable, "-I", "-B", str(root / "reader.py"),
                      repository, str(root)]
            (root / "session").write_text("layout splits\n" + shlex.join(launch) + "\n", encoding="utf-8")
            (root / "kitty.conf").write_text(KITTY_PROFILE, encoding="utf-8")
            environment = {**os.environ, "ZDOTDIR": str(root), "SOL_TEST_ROOT": str(root),
                           "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"),
                           "XDG_CACHE_HOME": str(root / "cache"), "PYTHONDONTWRITEBYTECODE": "1"}
            for key in tuple(environment):
                if key in {"KITTY_LISTEN_ON", "KITTY_RC_PASSWORD", "SOL_KITTY_SESSION", "SOL_HANDOFF_DIR", "SOL_CORPUS"} \
                        or key.startswith(("SOL_ACTOR", "SOL_WORKSPACE")):
                    environment.pop(key)
            try:
                completed = subprocess.run([kitty, "--config", str(root / "kitty.conf"),
                                            "--session", str(root / "session")], cwd=root,
                                           env=environment, capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired as error:
                self.fail(f"The isolated Kitty session did not finish: {error}")
            diagnostics = completed.stderr + "\n" + "\n".join(
                path.read_text() for path in (root / "reader-errors.txt", root / "native-errors.txt") if path.is_file())
            self.assertEqual(completed.returncode, 0, diagnostics)
            self.assertTrue((root / "result.json").is_file(), diagnostics)
            self.assertEqual(json.loads((root / "result.json").read_text()),
                             {"status": "passed", "visits": 2, "owned_pane_closed": True, "term_study_verified": True})
            self.assertEqual(originals, {path.name: path.read_bytes() for path in corpus.iterdir()})
            self.assertFalse((root / "config" / "SOL").exists())


if __name__ == "__main__":
    unittest.main()
