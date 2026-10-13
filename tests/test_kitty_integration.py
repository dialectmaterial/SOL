"""kitty integration contracts, without launching a GUI or reading a real PDF."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shlex
import signal
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

import sol.terminal.kitty as sol_kitty


ID = "aaaaaaaa-0000-4000-8000-000000000001"


def selection(title="An invented passage"):
    return {
        "version": 1, "requested_id": ID, "target_id": ID, "title": title,
        "sources": [{"pdf_page": 11, "printed_page": "iv"},
                    {"pdf_page": 14, "printed_page": None}],
        "source": {"sha256": "a" * 64}, "corpus": {"id": "b" * 36},
    }


SESSION = {"SOL_KITTY_SESSION": "1", "KITTY_RC_PASSWORD": "private-token", "KITTY_WINDOW_ID": "19"}


class LauncherTests(unittest.TestCase):
    def test_profile_session_lifetime_quoting_environment_and_corpus(self):
        args = ["--actor", 'A "quoted" name', "--source-pdf", "source `literal` $(text).pdf",
                "--search", "one's $literal\\word"]
        observed = {}

        def run(command, **options):
            profile = Path(command[command.index("--config") + 1])
            session = Path(command[command.index("--session") + 1])
            observed.update(profile=profile, session=session)
            self.assertTrue(profile.is_file())
            self.assertEqual(session.stat().st_mode & 0o777, 0o600)
            profile_text = profile.read_text()
            self.assertNotIn("allow_remote_control yes", profile_text)
            self.assertNotIn("map ctrl+s ", profile_text)
            self.assertNotIn("map ctrl+c ", profile_text)
            self.assertIn("map ctrl+shift+left neighboring_window left", profile_text)
            self.assertNotIn("--listen-on", command)
            lines = session.read_text().splitlines()
            self.assertEqual(lines[0], "layout splits")
            launch = shlex.split(lines[1])
            start = launch.index("-m")
            self.assertEqual(launch[start + 1:], ["sol", *args, "--corpus", "/tmp/corpus with spaces"])
            self.assertIn("--allow-remote-control", launch)
            self.assertTrue(any(value.endswith(" ls launch close-window") for value in launch))
            self.assertEqual(options["cwd"], str(Path.cwd()))
            self.assertNotIn("shell", options)
            self.assertNotIn("KITTY_LISTEN_ON", options["env"])
            self.assertNotIn("KITTY_RC_PASSWORD", options["env"])
            return SimpleNamespace(returncode=17)

        with patch.dict(os.environ, {"KITTY_LISTEN_ON": "fd:9", "KITTY_RC_PASSWORD": "ambient"}), \
                patch("sol.core.config.discover_corpus", return_value=Path("/tmp/corpus with spaces")), \
                patch("sol.terminal.kitty.shutil.which", side_effect=lambda command: "/usr/bin/" + command), \
                patch("sol.terminal.kitty.subprocess.run", side_effect=run):
            self.assertEqual(sol_kitty.launch_reader(args), 17)
        self.assertFalse(observed["session"].exists())
        self.assertFalse(observed["profile"].exists())

    def test_legacy_pdf_does_not_gain_corpus_option(self):
        with patch("sol.core.config.discover_corpus") as discover:
            args = ["--pdf", "a file.pdf", "-n"]
            self.assertEqual(sol_kitty.launcher_arguments(args), args)
            discover.assert_not_called()

    def test_corpus_setup_can_repair_a_broken_existing_pointer(self):
        with patch("sol.core.config.discover_corpus", side_effect=ValueError("broken saved pointer")) as discover:
            args = ["--set-corpus", "/new/corpus"]
            self.assertEqual(sol_kitty.launcher_arguments(args), args)
            discover.assert_not_called()

    def test_launcher_refuses_multiline_session_injection(self):
        with self.assertRaisesRegex(sol_kitty.KittyError, "line breaks"):
            sol_kitty.launcher_arguments(["--actor", "Name\nlaunch dangerous"])

    def test_missing_kitty_produces_actionable_error(self):
        with patch("sol.terminal.kitty.shutil.which", return_value=None), \
                patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(sol_kitty.main([]), 1)
            self.assertIn("standalone kitten", output.getvalue())


class PaneTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, SESSION)
        self.environment.start()
        self.which = patch("sol.terminal.kitty.shutil.which", return_value="/usr/bin/kitten")
        self.which.start()
        self.pane = sol_kitty.SourcePane()

    def tearDown(self):
        self.pane._forget()
        self.which.stop()
        self.environment.stop()

    def test_launch_reuse_atomic_selection_and_close_specific_window(self):
        inventory = json.dumps([{"tabs": [{"windows": [{"id": 71}]}]}])
        with patch.object(self.pane, "_remote", side_effect=["71\n", inventory, ""]) as remote:
            self.assertEqual(self.pane.show(selection()), 71)
            mailbox = self.pane.mailbox
            self.assertEqual(mailbox.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(mailbox.read_text())["sequence"], 1)
            self.assertEqual(self.pane.show(selection("Second selection")), 71)
            self.assertEqual(json.loads(mailbox.read_text())["request"]["title"], "Second selection")
            self.assertEqual(len(list(mailbox.parent.iterdir())), 1)
            calls = remote.call_args_list
            launch = calls[0].args
            self.assertEqual(launch[0], "launch")
            self.assertIn("window_id:19", launch)
            self.assertEqual(launch[launch.index("--source-window") + 1], "id:19")
            self.assertEqual(launch[launch.index("--next-to") + 1], "id:19")
            self.assertIn("--dont-take-focus", launch)
            self.assertIn("--env=KITTY_LISTEN_ON", launch)
            self.assertIn("--env=KITTY_RC_PASSWORD", launch)
            self.assertNotIn("--allow-remote-control", launch)
            self.assertEqual(calls[1].args, ("ls", "--match", "id:71"))
            self.pane.close()
            self.assertEqual(remote.call_args.args, ("close-window", "--match", "id:71", "--ignore-no-match"))
            self.assertFalse(mailbox.exists())
            self.assertIsNone(self.pane.window_id)

    def test_manual_close_reopens_new_mailbox_and_window(self):
        with patch.object(self.pane, "_remote", side_effect=["71", "[]", "84"]):
            self.pane.show(selection())
            old = self.pane.mailbox
            self.assertEqual(self.pane.show(selection("Again")), 84)
            self.assertNotEqual(self.pane.mailbox, old)
            self.assertFalse(old.exists())

    def test_launch_cannot_claim_reader_or_nonnumeric_window(self):
        for answer in ("19", "-1", "all", "title:reader"):
            with self.subTest(answer=answer), patch.object(self.pane, "_remote", return_value=answer):
                with self.assertRaises(sol_kitty.KittyError):
                    self.pane.show(selection())
                self.assertIsNone(self.pane.window_id)
                self.assertIsNone(self.pane.mailbox)

    def test_close_failure_is_reported_and_cleanup_removes_mailbox(self):
        with patch.object(self.pane, "_remote", return_value="71"):
            self.pane.show(selection())
        mailbox = self.pane.mailbox
        with patch.object(self.pane, "_remote", side_effect=sol_kitty.KittyError("denied")):
            with self.assertRaisesRegex(sol_kitty.KittyError, "denied"):
                self.pane.close()
            self.assertTrue(mailbox.exists())
            self.pane.cleanup()
        self.assertFalse(mailbox.exists())

    def test_remote_socket_descriptor_is_inherited_by_kitten_only(self):
        with patch.dict(os.environ, {"KITTY_LISTEN_ON": "fd:37"}), \
                patch("sol.terminal.kitty.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="[]", stderr="")) as run:
            self.assertEqual(self.pane._remote("ls", "--match", "id:19"), "[]")
        self.assertEqual(run.call_args.kwargs["pass_fds"], (37,))
        self.assertEqual(run.call_args.args[0][:2], ["kitten", "@"])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_plain_terminal_cannot_control_an_arbitrary_kitty(self):
        with patch.dict(os.environ, {"SOL_KITTY_SESSION": "0"}), patch.object(self.pane, "_remote") as remote:
            with self.assertRaisesRegex(sol_kitty.KittyError, "sol-kitty"):
                self.pane.show(selection())
            remote.assert_not_called()


class ViewerTests(unittest.TestCase):
    def test_labels_use_exact_ordered_pages_roman_and_missing_printed_labels(self):
        labels = sol_kitty.viewer_labels(selection(), 0)
        self.assertIn("Printed iv | PDF 11 | source 1/2", labels[1])
        self.assertIn("Printed not labelled | PDF 14 | source 2/2", sol_kitty.viewer_labels(selection(), 1)[1])
        self.assertIn(ID, labels[2])

    def test_icat_backend_reserves_labels_and_uses_real_pixels(self):
        size = sol_kitty.WindowSize(70, 31, 700, 620)
        command = sol_kitty.icat_command(Path("/tmp/image with quotes ' $.png"), size)
        self.assertEqual(command[:2], ["kitten", "icat"])
        self.assertIn("--stdin=no", command)
        self.assertIn("--transfer-mode=file", command)
        self.assertEqual(command[command.index("--use-window-size") + 1], "70,31,700,620")
        self.assertEqual(command[command.index("--place") + 1], "70x27@0x3")
        self.assertEqual(command[-1], "/tmp/image with quotes ' $.png")
        with self.assertRaisesRegex(sol_kitty.KittyError, "pixel dimensions"):
            sol_kitty.icat_command(Path("/tmp/i.png"), sol_kitty.WindowSize(70, 31, 0, 0))

    def test_draw_sanitizes_metadata_and_never_passes_control_credentials(self):
        output = io.StringIO()
        request = selection("Unsafe\x1b]2;title\x07 and \u202e text")
        with patch.dict(os.environ, {"KITTY_RC_PASSWORD": "secret", "KITTY_LISTEN_ON": "fd:8"}), \
                patch("sol.terminal.kitty.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"IMAGE", stderr=b"")) as run:
            sol_kitty.draw_view(output, request, 0, sol_kitty.WindowSize(90, 40, 900, 800), Path("/tmp/i.png"))
        text = output.getvalue()
        self.assertNotIn("\x1b]2;title", text)
        self.assertIn("\\u001b", text)
        self.assertIn("\\u202e", text)
        self.assertIn("IMAGE", text)
        self.assertIn(sol_kitty._DELETE_IMAGE, text)
        self.assertNotIn("KITTY_RC_PASSWORD", run.call_args.kwargs["env"])
        self.assertNotIn("KITTY_LISTEN_ON", run.call_args.kwargs["env"])

    def test_batched_and_fragmented_keys_and_protocol_replies(self):
        actions, remaining = sol_kitty.consume_keys(b"n\x1b[6~p\x1b[5")
        self.assertEqual(actions, ["next", "next", "previous"])
        self.assertEqual(remaining, b"\x1b[5")
        self.assertEqual(sol_kitty.consume_keys(remaining + b"~q"), (["previous", "close"], b""))
        self.assertEqual(sol_kitty.consume_keys(b"\x1b_Gi=2;q;OK\x1b\\r"), (["refresh"], b""))

    def test_pixel_only_resize_does_not_rerender_or_change_selected_page(self):
        worker = Mock()
        worker.result.side_effect = [None, (Path("/tmp/page.png"), ""), None]
        sizes = [sol_kitty.WindowSize(80, 24, 800, 480), sol_kitty.WindowSize(80, 24, 960, 576),
                 sol_kitty.WindowSize(80, 24, 960, 576)]
        with tempfile.TemporaryDirectory() as directory:
            mailbox = Path(directory) / "selection.json"
            mailbox.write_text(json.dumps({"sequence": 1, "request": selection()}))
            input_stream = Mock()
            input_stream.isatty.return_value = True
            input_stream.fileno.return_value = 5
            output_stream = Mock()
            output_stream.isatty.return_value = True
            with patch("sol.terminal.kitty._RenderWorker", return_value=worker), \
                    patch("sys.stdin", input_stream), patch("sys.stdout", output_stream), \
                    patch("sol.terminal.kitty.termios.tcgetattr", return_value=["original"]), \
                    patch("sol.terminal.kitty.termios.tcsetattr") as restore, patch("sol.terminal.kitty.tty.setraw"), \
                    patch("sol.terminal.kitty.signal.signal", return_value=signal.SIG_DFL), \
                    patch("sol.terminal.kitty.window_size", side_effect=sizes), \
                    patch("sol.terminal.kitty.select.select", side_effect=[([], [], []), ([], [], []), ([5], [], [])]), \
                    patch("sol.terminal.kitty.os.read", return_value=b"q"), patch("sol.terminal.kitty.draw_view") as draw:
                self.assertEqual(sol_kitty.viewer_main(mailbox), 0)
            self.assertEqual(worker.request.call_count, 1)
            self.assertEqual(draw.call_count, 2)
            self.assertEqual(draw.call_args_list[1].args[2], 0)
            self.assertEqual(draw.call_args_list[1].args[3].pixel_width, 960)
            restore.assert_called_once_with(5, sol_kitty.termios.TCSADRAIN, ["original"])
            worker.close.assert_called_once()

    def test_new_mailbox_request_is_explicit_and_resets_source_page(self):
        worker = Mock()
        worker.result.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            mailbox = Path(directory) / "selection.json"
            mailbox.write_text(json.dumps({"sequence": 1, "request": selection()}))
            calls = 0

            def poll(*_args):
                nonlocal calls
                calls += 1
                if calls == 1:
                    mailbox.write_text(json.dumps({"sequence": 2, "request": selection("Explicit second request")}))
                    return [], [], []
                return [5], [], []

            input_stream = Mock()
            input_stream.isatty.return_value = True
            input_stream.fileno.return_value = 5
            output_stream = Mock()
            output_stream.isatty.return_value = True
            with patch("sol.terminal.kitty._RenderWorker", return_value=worker), \
                    patch("sys.stdin", input_stream), patch("sys.stdout", output_stream), \
                    patch("sol.terminal.kitty.termios.tcgetattr", return_value=[]), patch("sol.terminal.kitty.termios.tcsetattr"), \
                    patch("sol.terminal.kitty.tty.setraw"), patch("sol.terminal.kitty.signal.signal", return_value=signal.SIG_DFL), \
                    patch("sol.terminal.kitty.window_size", return_value=sol_kitty.WindowSize(80, 24, 800, 480)), \
                    patch("sol.terminal.kitty.select.select", side_effect=poll), patch("sol.terminal.kitty.os.read", return_value=b"q"), \
                    patch("sol.terminal.kitty.draw_view") as draw:
                sol_kitty.viewer_main(mailbox)
            self.assertEqual(draw.call_args_list[0].args[1]["title"], "An invented passage")
            self.assertEqual(draw.call_args_list[1].args[1]["title"], "Explicit second request")
            self.assertEqual(draw.call_args_list[1].args[2], 0)


class RenderWorkerTests(unittest.TestCase):
    def process(self, *, running=False, path="/tmp/source.png"):
        process = Mock()
        process.pid = 901
        process.stdin = io.StringIO()
        process.returncode = 0
        process.poll.return_value = None if running else 0
        process.communicate.return_value = (json.dumps(path), "")
        return process

    def test_obsolete_render_is_cancelled_in_its_owned_process_group(self):
        first, second = self.process(running=True), self.process()
        with patch.dict(os.environ, {"KITTY_LISTEN_ON": "fd:8", "KITTY_RC_PASSWORD": "secret"}), \
                patch("sol.terminal.kitty.subprocess.Popen", side_effect=[first, second]) as popen, \
                patch("sol.terminal.kitty.os.killpg") as kill:
            worker = sol_kitty._RenderWorker()
            worker.request((1, 0), selection(), 0)
            worker.request((1, 1), selection(), 1)
            kill.assert_called_once_with(901, signal.SIGTERM)
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            self.assertNotIn("KITTY_RC_PASSWORD", popen.call_args.kwargs["env"])
            self.assertNotIn("KITTY_LISTEN_ON", popen.call_args.kwargs["env"])
            self.assertEqual(worker.result((1, 1)), (Path("/tmp/source.png"), ""))
            worker.close()

    def test_result_for_an_obsolete_selection_is_discarded(self):
        with patch("sol.terminal.kitty.subprocess.Popen", return_value=self.process()):
            worker = sol_kitty._RenderWorker()
            worker.request((1, 0), selection(), 0)
            self.assertIsNone(worker.result((2, 0)))
            worker.close()

    def test_renderer_error_is_visible_and_not_an_image(self):
        process = self.process()
        process.returncode = 1
        process.communicate.return_value = ("", "PDF fingerprint mismatch")
        with patch("sol.terminal.kitty.subprocess.Popen", return_value=process):
            worker = sol_kitty._RenderWorker()
            worker.request((1, 0), selection(), 0)
            image, message = worker.result((1, 0))
            self.assertIsNone(image)
            self.assertIn("PDF fingerprint mismatch", message)

    def test_render_child_termination_unwinds_intermediate_copy(self):
        observed = {}

        def render(_request, _page):
            with tempfile.TemporaryDirectory(prefix="cancelled-source-") as directory:
                copy = Path(directory) / "temporary.pdf"
                copy.write_bytes(b"invented intermediate PDF copy")
                observed["copy"] = copy
                self.assertTrue(copy.exists())
                # Invoke the installed signal handler without signalling the test runner.
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

        original = signal.getsignal(signal.SIGTERM)
        with patch("sol.terminal.source.render_page", side_effect=render), \
                patch("sys.stdin", io.StringIO(json.dumps(selection()))):
            with self.assertRaises(SystemExit) as cancelled:
                sol_kitty.render_child(0)
        self.assertEqual(cancelled.exception.code, 128 + signal.SIGTERM)
        self.assertFalse(observed["copy"].exists())
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)


if __name__ == "__main__":
    unittest.main()
