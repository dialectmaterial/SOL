"""Private native return commands and a validated, ordinary ESSENCE zsh."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol import core
from sol.corpus import contract
from sol.terminal import essence, reference
from sol.terminal.handoff import HandoffSession
from fixtures_corpus import write_runtime_corpus


class HandoffCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-handoff-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus with spaces"
        self.identifier, self.body = write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.env = {**os.environ, "SOL_CORPUS": str(self.corpus),
                    "XDG_CONFIG_HOME": str(self.root / "config"),
                    "XDG_DATA_HOME": str(self.root / "data"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
        self.env.pop("SOL_HANDOFF_DIR", None)

    def session(self, identifier=None):
        snapshot = core.load_snapshot(self.corpus)
        session = HandoffSession.create(core.capture_reference(snapshot, identifier or self.identifier))
        self.addCleanup(session.close)
        return session

    def run_return(self, session=None, identifier=None, extra=(), env=None):
        arguments = ["reference", "return"]
        if identifier is not None:
            arguments.append(identifier)
        if session is not None:
            arguments += ["--handoff-dir", str(session.directory)]
        return subprocess.run([sys.executable, "-B", "-m", "sol", *arguments, *extra],
                              cwd=self.root, env=env or self.env, input=b"do not read stdin",
                              capture_output=True, timeout=10)

    def corpus_files(self):
        return {path.relative_to(self.corpus): path.read_bytes()
                for path in self.corpus.rglob("*") if path.is_file()}

    def rewrite(self, change):
        manifest = json.loads((self.corpus / "corpus.json").read_text())
        records = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        change(manifest, records)
        for record in records:
            record["content_sha256"] = sha256(record["markdown"].encode()).hexdigest()
        generated = {"markdown", "plain_text", "document", "context", "content_sha256"}
        markdown = "\n".join(contract.render_record(
            {key: value for key, value in row.items() if key not in generated}, row["markdown"])
            for row in records).encode()
        manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode()
        index_bytes = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records).encode()
        (self.corpus / "sample.md").write_bytes(markdown)
        (self.corpus / "corpus.json").write_bytes(manifest_bytes)
        (self.corpus / "index.jsonl").write_bytes(index_bytes)
        (self.corpus / "index.meta.json").write_text(json.dumps({
            "contract_version": 1, "manifest_sha256": sha256(manifest_bytes).hexdigest(),
            "source_sha256": manifest["source"]["sha256"],
            "documents": {"sample.md": sha256(markdown).hexdigest()},
            "index_sha256": sha256(index_bytes).hexdigest(), "record_count": len(records),
        }), encoding="utf-8")

    def bootstrap(self, session, which="/usr/bin/zsh", arguments=(), environment=None):
        output, error = StringIO(), StringIO()
        with patch.dict(os.environ, environment or self.env, clear=True), \
                redirect_stdout(output), redirect_stderr(error), \
                patch("sol.terminal.essence.shutil.which", return_value=which), \
                patch("sol.terminal.essence.os.execve") as execute, \
                patch("sol.terminal.essence.os.chdir") as change_directory:
            status = essence.main(["--handoff-dir", str(session.directory),
                                   "--corpus", str(self.corpus), *arguments])
        return status, output.getvalue(), error.getvalue(), execute, change_directory

    def restore_file(self, path):
        content, mode = path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
        def restore():
            if path.is_symlink():
                path.unlink()
            path.write_bytes(content)
            path.chmod(mode)
        self.addCleanup(restore)

    def test_two_process_default_return_is_correlated_and_changes_only_private_response(self):
        session = self.session()
        before = self.corpus_files()
        outgoing = session.outgoing_file.read_bytes()
        metadata = (session.directory / "session.json").read_bytes()
        result = self.run_return(session)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "proposed")
        returned = session.read_return()
        self.assertEqual(returned["reference"]["requested_id"], self.identifier)
        self.assertEqual(core.check_reference(core.load_snapshot(self.corpus), returned).target_id, self.identifier)
        self.assertEqual(session.outgoing_file.read_bytes(), outgoing)
        self.assertEqual((session.directory / "session.json").read_bytes(), metadata)
        self.assertEqual(self.corpus_files(), before)
        self.assertFalse((self.root / "config").exists())
        self.assertFalse((self.root / "data").exists())

    def test_environment_selects_session_but_explicit_directory_overrides_it(self):
        first = self.session()
        env = {**self.env, "SOL_HANDOFF_DIR": str(first.directory)}
        result = self.run_return(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(first.read_return()["reference"]["target_id"], self.identifier)
        second = self.session()
        result = self.run_return(second, env={**self.env, "SOL_HANDOFF_DIR": str(self.root / "missing")})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(second.read_return()["reference"]["target_id"], self.identifier)

    def test_explicit_new_record_return_preserves_existing_canonical_ids(self):
        session = self.session()
        section = core.load_snapshot(self.corpus).records[0]["id"]
        result = self.run_return(session, "aaaaaaaa")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = session.read_return()
        self.assertEqual(packet["reference"]["requested_id"], section)
        self.assertEqual(packet["reference"]["type"], "section")

    def test_retired_origin_default_return_keeps_requested_uuid_and_redirect_chain(self):
        retired = "cccccccc-0000-4000-8000-000000000003"
        def change(manifest, records):
            record = deepcopy(records[1])
            record.update(id=retired, type="retired_record", order=2,
                          redirect_id=self.identifier, markdown="Invented retired reference.",
                          plain_text="Invented retired reference.")
            records.append(record)
        self.rewrite(change)
        session = self.session(retired)
        result = self.run_return(session)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(session.read_return()["reference"]["chain"], [retired, self.identifier])

    def test_missing_session_and_unresolved_record_are_nonzero_without_reading_stdin(self):
        output, error, stream = StringIO(), StringIO(), StringIO("unread")
        with patch.dict(os.environ, self.env, clear=True), patch.object(sys, "stdin", stream), \
                patch.object(stream, "read", side_effect=AssertionError("Return must not read stdin")), \
                redirect_stdout(output), redirect_stderr(error):
            status = reference.main(["return"])
        self.assertNotEqual(status, 0)
        self.assertIn("SOL_HANDOFF_DIR", error.getvalue())
        self.assertEqual(json.loads(output.getvalue())["status"], "invalid")
        session = self.session()
        result = self.run_return(session, "eeeeeeee")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((session.directory / "returned.json").exists())

    def test_second_return_cannot_replace_the_first_response(self):
        session = self.session()
        self.assertEqual(self.run_return(session).returncode, 0)
        original = (session.directory / "returned.json").read_bytes()
        result = self.run_return(session, "aaaaaaaa")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((session.directory / "returned.json").read_bytes(), original)

    def test_return_refuses_wrong_lineage_stale_generation_and_uninitialized_identity(self):
        for change in ("lineage", "generation", "identity"):
            session = self.session()
            paths = [self.corpus / name for name in ("sample.md", "corpus.json", "index.jsonl", "index.meta.json")]
            original = {path: path.read_bytes() for path in paths}
            def mutate(manifest, records):
                if change == "lineage":
                    manifest["corpus_id"] = "dddddddd-0000-4000-8000-000000000004"
                elif change == "generation":
                    records[1]["markdown"] = records[1]["plain_text"] = "A corrected invented passage."
                else:
                    manifest.pop("corpus_id")
            self.rewrite(mutate)
            before = self.corpus_files()
            with self.subTest(change=change):
                result = self.run_return(session)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(json.loads(result.stdout)["status"], {"invalid", "stale", "mismatch"})
                self.assertFalse((session.directory / "returned.json").exists())
                self.assertEqual(self.corpus_files(), before)
            for path, content in original.items():
                path.write_bytes(content)

    def test_private_directory_and_file_permissions_are_required(self):
        for target in ("directory", "session.json", "outgoing.json"):
            session = self.session()
            path = session.directory if target == "directory" else session.directory / target
            original = stat.S_IMODE(path.stat().st_mode)
            self.addCleanup(path.chmod, original)
            path.chmod(0o755 if target == "directory" else 0o644)
            with self.subTest(target=target):
                result = self.run_return(session)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((session.directory / "returned.json").exists())
            path.chmod(original)

    def test_metadata_cannot_add_routing_authority_or_forge_origin_digest(self):
        for field, value in (("path", "/private/other"), ("command", "touch /tmp/not-a-command"),
                             ("actor", "Invented"), ("workspace", "foreign"),
                             ("origin_sha256", "0" * 64), ("session_nonce", "invalid-nonce")):
            session = self.session()
            path = session.directory / "session.json"
            self.restore_file(path)
            metadata = json.loads(path.read_text())
            metadata[field] = value
            path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.subTest(field=field):
                result = self.run_return(session)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((session.directory / "returned.json").exists())

    def test_symlink_packet_is_refused_without_following_it(self):
        session = self.session()
        self.restore_file(session.outgoing_file)
        external = self.root / "packet.json"
        external.write_bytes(session.outgoing_file.read_bytes())
        session.outgoing_file.unlink()
        session.outgoing_file.symlink_to(external)
        result = self.run_return(session)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((session.directory / "returned.json").exists())

    def test_bootstrap_executes_literal_interactive_zsh_with_pinned_private_environment(self):
        session = self.session()
        environment = {**self.env, "KITTY_RC_PASSWORD": "secret", "KITTYRC_PASSWORD": "secret",
                       "KITTY_LISTEN_ON": "fd:9", "LISTEN_ON": "unix:ambient", "SOL_KITTY_SESSION": "1",
                       "SOL_ACTOR": "Actor", "SOL_WORKSPACE": "reading", "SOL_WORKSPACE_DIR": "/private/workspaces",
                       "SOL_REFERENCE_FILE": "/wrong/file", "SOL_HANDOFF_DIR": "/wrong/directory",
                       "ZDOTDIR": str(self.root / "normal-rc"), "PYTHONPATH": "/user/ml-libraries"}
        status, output, error, execute, change = self.bootstrap(session, environment=environment)
        self.assertEqual(status, 0, error)
        execute.assert_called_once()
        shell, arguments, child = execute.call_args.args
        self.assertEqual(shell, "/usr/bin/zsh")
        self.assertEqual(arguments, ["/usr/bin/zsh", "-i"])
        self.assertFalse(execute.call_args.kwargs)
        self.assertEqual(change.call_args_list[0].args, (self.corpus.resolve(),))
        self.assertEqual(child["SOL_CORPUS"], str(self.corpus.resolve()))
        self.assertEqual(child["SOL_HANDOFF_DIR"], str(session.directory))
        self.assertEqual(child["SOL_REFERENCE_FILE"], str(session.outgoing_file))
        self.assertEqual(child["PATH"].split(os.pathsep)[0], str(session.directory / "bin"))
        self.assertEqual(child["ZDOTDIR"], environment["ZDOTDIR"])
        self.assertEqual(child["PYTHONPATH"], environment["PYTHONPATH"])
        for key in environment:
            if key.startswith(("KITTY", "SOL_ACTOR", "SOL_WORKSPACE")) or key == "LISTEN_ON":
                self.assertNotIn(key, child)
        self.assertIn(self.identifier, output)
        self.assertIn('sol reference check "$SOL_REFERENCE_FILE"', output)
        self.assertIn("sol reference return [ID]", output)
        self.assertIn("essence check, then essence return", output)
        self.assertNotIn(self.body, output)

    def test_bootstrap_requires_zsh_and_valid_origin_before_writing_a_wrapper(self):
        session = self.session()
        status, output, error, execute, change = self.bootstrap(session, which=None)
        self.assertNotEqual(status, 0)
        self.assertIn("zsh", error)
        execute.assert_not_called()
        change.assert_not_called()
        self.assertFalse((session.directory / "bin" / "sol").exists())
        self.rewrite(lambda manifest, records: manifest.update(corpus_id="dddddddd-0000-4000-8000-000000000004"))
        status, output, error, execute, change = self.bootstrap(session)
        self.assertNotEqual(status, 0)
        execute.assert_not_called()
        self.assertFalse((session.directory / "bin" / "sol").exists())

    def test_bootstrap_refuses_stale_origin_and_private_mode_failures_before_exec(self):
        session = self.session()
        self.rewrite(lambda manifest, records: records[1].update(markdown="A revised invented passage.",
                                                               plain_text="A revised invented passage."))
        status, output, error, execute, change = self.bootstrap(session)
        self.assertNotEqual(status, 0)
        execute.assert_not_called()
        self.assertFalse((session.directory / "bin" / "sol").exists())
        current = self.session()
        current.directory.chmod(0o755)
        self.addCleanup(current.directory.chmod, 0o700)
        status, output, error, execute, change = self.bootstrap(current)
        self.assertNotEqual(status, 0)
        execute.assert_not_called()
        self.assertFalse((current.directory / "bin" / "sol").exists())

    def test_command_wrapper_is_private_fixed_and_idempotent(self):
        from sol.terminal.handoff import sol_shim_bytes

        session = self.session()
        self.assertEqual(self.bootstrap(session)[0], 0)
        wrapper = session.directory / "bin" / "sol"
        content = wrapper.read_bytes()
        self.assertEqual(content, sol_shim_bytes())
        self.assertEqual(stat.S_IMODE(wrapper.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(wrapper.parent.stat().st_mode), 0o700)
        arguments = shlex.split(content.decode().splitlines()[1])
        self.assertEqual(arguments[:5], ["exec", sys.executable, "-I", "-B", "-c"])
        self.assertIn("sys.path.insert(0, sys.argv.pop(1))", arguments[5])
        self.assertEqual(arguments[6], str(Path(__file__).resolve().parents[1]))
        self.assertEqual(self.bootstrap(session)[0], 0)
        self.assertEqual(wrapper.read_bytes(), content)

    def test_existing_command_wrapper_is_never_overwritten(self):
        session = self.session()
        self.assertEqual(self.bootstrap(session)[0], 0)
        wrapper = session.directory / "bin" / "sol"
        self.restore_file(wrapper)
        wrapper.write_text("#!/bin/sh\nprintf untrusted\\n\n", encoding="utf-8")
        original = wrapper.read_bytes()
        status, output, error, execute, change = self.bootstrap(session)
        self.assertNotEqual(status, 0)
        execute.assert_not_called()
        self.assertEqual(wrapper.read_bytes(), original)

    def test_private_wrapper_ignores_corpus_and_pythonpath_module_shadowing(self):
        session = self.session()
        self.assertEqual(self.bootstrap(session)[0], 0)
        marker = self.root / "shadow-executed"
        evil = "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\nraise SystemExit(99)\n"
        (self.corpus / "sol.py").write_text(evil, encoding="utf-8")
        shadow = self.root / "shadow"
        shadow.mkdir()
        (shadow / "sol.py").write_text(evil, encoding="utf-8")
        result = subprocess.run([str(session.directory / "bin" / "sol"), "reference", "check",
                                 str(session.outgoing_file), "--corpus", str(self.corpus)],
                                cwd=self.corpus, env={**self.env, "PYTHONPATH": str(shadow)},
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "current")
        self.assertFalse(marker.exists())

    def test_bootstrap_failure_restores_working_directory(self):
        session = self.session()
        output, error = StringIO(), StringIO()
        previous = Path.cwd()
        with patch.dict(os.environ, self.env, clear=True), redirect_stdout(output), redirect_stderr(error), \
                patch("sol.terminal.essence.shutil.which", return_value="/usr/bin/zsh"), \
                patch("sol.terminal.essence.os.execve", side_effect=OSError("Invented exec failure")):
            status = essence.main(["--handoff-dir", str(session.directory), "--corpus", str(self.corpus)])
        self.assertNotEqual(status, 0)
        self.assertEqual(Path.cwd(), previous)
        self.assertIn("Invented exec failure", error.getvalue())

    def test_handoff_root_replacement_during_load_or_shim_is_refused(self):
        from sol.terminal import handoff

        for stage in ("load", "shim"):
            session, replacement = self.session(), self.session()
            previous = self.root / ("previous-session-" + stage)
            swapped = False

            def swap_root():
                nonlocal swapped
                session.directory.rename(previous)
                replacement.directory.rename(session.directory)
                swapped = True

            def restore_root():
                if swapped:
                    session.directory.rename(replacement.directory)
                    previous.rename(session.directory)
            self.addCleanup(restore_root)

            original_load, original_shim = handoff.load_handoff, essence._sol_shim
            def load_then_swap(directory):
                loaded = original_load(directory)
                swap_root()
                return loaded
            def swap_then_shim(directory, expected_root, expected_bin):
                swap_root()
                return original_shim(directory, expected_root, expected_bin)

            target = "sol.terminal.handoff.load_handoff" if stage == "load" else "sol.terminal.essence._sol_shim"
            effect = load_then_swap if stage == "load" else swap_then_shim
            with self.subTest(stage=stage), patch(target, side_effect=effect):
                status, output, error, execute, change = self.bootstrap(session)
            self.assertNotEqual(status, 0)
            self.assertIn("replaced", error)
            execute.assert_not_called()
            self.assertFalse((session.directory / "bin" / "sol").exists())
            restore_root()
            swapped = False

    def test_command_directory_replacement_between_stat_and_open_is_refused(self):
        session = self.session()
        previous = self.root / "previous-bin"
        directory = session.directory / "bin"
        swapped = False
        original_open = os.open

        def raced_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == "bin" and not swapped:
                directory.rename(previous)
                directory.mkdir(mode=0o700)
                swapped = True
            return original_open(path, flags, *args, **kwargs)

        def restore_bin():
            if swapped:
                directory.rmdir()
                previous.rename(directory)
        self.addCleanup(restore_bin)
        with patch("sol.terminal.essence.os.open", side_effect=raced_open):
            status, output, error, execute, change = self.bootstrap(session)
        self.assertNotEqual(status, 0)
        self.assertIn("changed while opening", error)
        execute.assert_not_called()
        self.assertFalse((directory / "sol").exists())

    def test_packet_metadata_or_generation_changed_after_shim_refuses_exec(self):
        from sol.terminal import handoff

        for mutation in ("packet", "metadata", "generation"):
            session = self.session()
            self.restore_file(session.directory / "session.json")
            self.restore_file(session.outgoing_file)
            original_shim = essence._sol_shim
            prepared = False

            def mutate_after_shim(directory, expected_root, expected_bin):
                nonlocal prepared
                result = original_shim(directory, expected_root, expected_bin)
                if not prepared:
                    prepared = True
                    if mutation == "generation":
                        self.rewrite(lambda manifest, records: records[1].update(
                            markdown="A later corrected invented passage.", plain_text="A later corrected invented passage."))
                    else:
                        metadata_path = session.directory / "session.json"
                        metadata = json.loads(metadata_path.read_text())
                        if mutation == "metadata":
                            metadata["session_nonce"] = "0" * 64
                        else:
                            snapshot = core.load_snapshot(self.corpus)
                            packet = core.capture_reference(snapshot, snapshot.records[0]["id"])
                            raw = (core.encode_reference(packet) + "\n").encode()
                            session.outgoing_file.write_bytes(raw)
                            metadata["origin_sha256"] = sha256(raw).hexdigest()
                        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
                return result

            with self.subTest(mutation=mutation), patch("sol.terminal.essence._sol_shim", side_effect=mutate_after_shim):
                status, output, error, execute, change = self.bootstrap(session)
            self.assertNotEqual(status, 0)
            self.assertTrue(error)
            execute.assert_not_called()

    def test_preexisting_custom_command_is_preserved_when_session_closes(self):
        from sol.terminal.handoff import sol_shim_bytes

        session = self.session()
        wrapper = session.directory / "bin" / "sol"
        content = b"#!/bin/sh\nprintf 'user-owned command\\n'\n"
        wrapper.write_bytes(content)
        wrapper.chmod(0o700)
        status, output, error, execute, change = self.bootstrap(session)
        self.assertNotEqual(status, 0)
        execute.assert_not_called()
        with self.assertRaises(ValueError):
            session.close()
        self.assertEqual(wrapper.read_bytes(), content)
        # Restore only this test's fixed reserved file so normal cleanup can finish.
        wrapper.write_bytes(sol_shim_bytes())

    def test_return_and_bootstrap_help_read_no_application_data(self):
        for entry, args in ((reference.main, ["return", "--help"]), (essence.main, ["--help"])):
            output = StringIO()
            with self.subTest(entry=entry), redirect_stdout(output), \
                    patch("sol.core.discover_corpus", side_effect=AssertionError("No discovery for help")), \
                    patch("sol.core.load_snapshot", side_effect=AssertionError("No corpus for help")), \
                    patch("sol.terminal.handoff.load_handoff", side_effect=AssertionError("No IPC for help")), \
                    patch.object(Path, "mkdir", side_effect=AssertionError("No writes for help")):
                with self.assertRaises(SystemExit) as result:
                    entry(args)
                self.assertEqual(result.exception.code, 0)
                self.assertIn("usage:", output.getvalue())

    def test_fresh_bootstrap_help_needs_no_optional_interface_or_ipc_import(self):
        script = """
import builtins, pathlib, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(('sol.terminal.handoff', 'sol.terminal.kitty', 'sol.workspace',
                        'markdown_it', 'prompt_toolkit', 'textual', 'rich', 'opendataloader')):
        raise AssertionError('Unexpected bootstrap help import: ' + name)
    return original(name, *args, **kwargs)
def no_io(*args, **kwargs):
    raise AssertionError('Bootstrap help must not read or write application data')
builtins.__import__ = guarded
pathlib.Path.read_text = no_io
pathlib.Path.read_bytes = no_io
pathlib.Path.mkdir = no_io
from sol.terminal.essence import main
raise SystemExit(main(['--help']))
"""
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=self.root,
                                env=self.env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
