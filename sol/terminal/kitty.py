"""Optional kitty launcher and a private, read-only source-page pane.

The reader and viewer have separate TTYs. Only the reader's startup window
receives a per-window remote-control password, limited to ls/launch/close-window.
Source selections travel through an atomically replaced private JSON mailbox;
neither terminal text nor simulated keyboard input is used as application state.
"""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import secrets
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import tty
import unicodedata


KITTY_PROFILE = """# SOL's private profile; does not modify ~/.config/kitty.
font_family monospace
font_size 13.0
background #181b1f
foreground #d9dce1
selection_background #3b5261
selection_foreground #ffffff
cursor #a2c8cb
cursor_text_color #181b1f
active_border_color #607f89
inactive_border_color #30363d
color0 #181b1f
color1 #cf8b88
color2 #a5bf99
color3 #d1bd8a
color4 #99b2cc
color5 #b3a0c8
color6 #93bdc1
color7 #c5ccd2
color8 #7c8792
color9 #e1a29f
color10 #bcd2ae
color11 #e3cf9e
color12 #b0c9e1
color13 #c9b8dc
color14 #add3d5
color15 #eef1f4
window_padding_width 8
enabled_layouts splits
initial_window_width 140c
initial_window_height 42c
tab_bar_style hidden
map ctrl+alt+left neighboring_window left
map ctrl+alt+right neighboring_window right
map ctrl+shift+left neighboring_window left
map ctrl+shift+right neighboring_window right
map ctrl+shift+plus change_font_size all +1.0
map ctrl+shift+minus change_font_size all -1.0
map ctrl+alt+shift+left resize_window narrower 2
map ctrl+alt+shift+right resize_window wider 2
"""

_CONTROL_ENV = ("KITTY_LISTEN_ON", "KITTY_RC_PASSWORD")
_IMAGE_ID = 47301
_ENTER = "\x1b[?1049h\x1b[?25l"
_LEAVE = "\x1b[?25h\x1b[?1049l"
_DELETE_IMAGE = f"\x1b_Ga=d,d=I,i={_IMAGE_ID},q=2\x1b\\"
_BIDI = {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}


class KittyError(RuntimeError):
    """A failed optional integration must leave ordinary SOL reading usable."""


def _child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in (*_CONTROL_ENV, "SOL_KITTY_SESSION"):
        environment.pop(name, None)
    return environment


def _remote_descriptors() -> tuple[int, ...]:
    # Per-window permission can be delivered through kitty's private socket FD.
    address = os.environ.get("KITTY_LISTEN_ON", "")
    if address.startswith("fd:") and address[3:].isdecimal():
        return (int(address[3:]),)
    return ()


def _number(value: str, label: str) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal() or int(value) < 1:
        raise KittyError(f"Invalid {label}; expected a positive numeric kitty window ID.")
    return int(value)


def _option(arguments: list[str], name: str) -> str | None:
    result = None
    for index, value in enumerate(arguments):
        if value.startswith(name + "="):
            result = value[len(name) + 1:]
        elif value == name and index + 1 < len(arguments):
            result = arguments[index + 1]
    return result


def launcher_arguments(arguments: list[str]) -> list[str]:
    """Pin corpus discovery before kitty starts, while preserving SOL arguments."""
    from sol.core.config import discover_corpus

    if any(not isinstance(value, str) or any(c in value for c in "\r\n\0") for value in arguments):
        raise KittyError("SOL launcher arguments cannot contain line breaks or NUL characters.")
    result = list(arguments)
    if _option(arguments, "--pdf") is None and _option(arguments, "--set-corpus") is None:
        explicit = _option(arguments, "--corpus")
        corpus = discover_corpus(Path(explicit) if explicit is not None else None)
        if corpus is not None:
            result += ["--corpus", str(corpus.expanduser().resolve())]
    return result


def launch_reader(arguments: list[str]) -> int:
    """Keep the private session/profile alive until foreground kitty exits."""
    executable = shutil.which("kitty")
    if executable is None or shutil.which("kitten") is None:
        raise KittyError("kitty and its standalone kitten command are required for sol-kitty.")
    forwarded = launcher_arguments(arguments)
    password = secrets.token_hex(24)
    reader = ["launch", "--allow-remote-control", "--remote-control-password=!",
              "--remote-control-password=" + f'"{password}" ls launch close-window',
              "--env=SOL_KITTY_SESSION=1", "--env=KITTY_RC_PASSWORD=" + password,
              "--title=SOL", sys.executable, "-m", "sol", *forwarded]
    with tempfile.TemporaryDirectory(prefix="sol-kitty-") as directory:
        root = Path(directory)
        profile, session = root / "kitty.conf", root / "reader.session"
        profile.write_text(KITTY_PROFILE, encoding="utf-8")
        session.write_text("layout splits\n" + shlex.join(reader) + "\n", encoding="utf-8")
        profile.chmod(0o600)
        session.chmod(0o600)
        try:
            completed = subprocess.run(
                [executable, "--config", str(profile), "--session", str(session)],
                cwd=str(Path.cwd()), env=_child_environment(), check=False,
            )
        except OSError as error:
            raise KittyError(f"Could not start kitty: {error}") from error
        return completed.returncode


def launch_zsh(arguments: list[str]) -> int:
    """Open a normal interactive shell with a verified corpus as its directory."""
    import argparse
    from sol.core.config import discover_corpus
    from sol.core.corpus import load_corpus_book

    class NativeParser(argparse.ArgumentParser):
        def error(self, message):
            raise KittyError(message)

    parser = NativeParser(prog="sol-kitty --zsh", add_help=False,
                          description="Open normal zsh in SOL's private kitty profile.")
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--corpus", type=Path, metavar="DIRECTORY")
    parser.add_argument("--directory", type=Path, metavar="DIRECTORY",
                        help="initial shell directory (default: selected corpus)")
    if any(not isinstance(value, str) or any(c in value for c in "\r\n\0") for value in arguments):
        raise KittyError("SOL launcher arguments cannot contain line breaks or NUL characters.")
    options = parser.parse_args(arguments)
    if options.help:
        print(parser.format_help())
        return 0
    executable, shell = shutil.which("kitty"), shutil.which("zsh")
    if executable is None or shell is None:
        raise KittyError("kitty and zsh are required for sol-kitty --zsh.")
    corpus = discover_corpus(options.corpus)
    if corpus is None:
        raise KittyError("No local Markdown corpus found; choose --corpus DIRECTORY or sol --set-corpus DIRECTORY.")
    corpus = corpus.expanduser().resolve()
    load_corpus_book(corpus)
    directory = options.directory.expanduser().resolve() if options.directory else corpus
    if not directory.is_dir():
        raise KittyError(f"Shell directory not found: {directory}")
    sol_command = shutil.which("sol")
    if sol_command is None:
        sibling = Path(sys.executable).parent / "sol"
        sol_command = str(sibling) if sibling.is_file() and os.access(sibling, os.X_OK) else None
    if sol_command is None:
        raise KittyError("The sol command must be installed or on PATH before opening native zsh.")
    environment = _child_environment()
    environment["SOL_CORPUS"] = str(corpus)
    command_directory = str(Path(sol_command).absolute().parent)
    environment["PATH"] = os.pathsep.join([command_directory, *[
        value for value in environment.get("PATH", "").split(os.pathsep) if value != command_directory
    ]])
    launch = ["launch", "--title=SOL zsh", "--env=SOL_CORPUS=" + str(corpus), shell, "-i"]
    if any(any(c in value for c in "\r\n\0") for value in launch):
        raise KittyError("SOL launch paths cannot contain line breaks or NUL characters.")
    with tempfile.TemporaryDirectory(prefix="sol-zsh-") as temporary:
        root = Path(temporary)
        profile, session = root / "kitty.conf", root / "shell.session"
        profile.write_text(KITTY_PROFILE, encoding="utf-8")
        session.write_text("layout splits\n" + shlex.join(launch) + "\n", encoding="utf-8")
        profile.chmod(0o600)
        session.chmod(0o600)
        try:
            completed = subprocess.run(
                [executable, "--config", str(profile), "--session", str(session)],
                cwd=str(directory), env=environment, check=False,
            )
        except OSError as error:
            raise KittyError(f"Could not start kitty: {error}") from error
        return completed.returncode


class SourcePane:
    """The reader owns one specific kitty window and one private mailbox."""

    pane_name = "source"
    pane_title = "SOL source"
    viewer_option = "--viewer"

    def __init__(self):
        self.window_id: int | None = None
        self.reader_id: int | None = None
        self.mailbox: Path | None = None
        self._temporary = None
        self._sequence = 0

    def _require_session(self) -> None:
        if os.environ.get("SOL_KITTY_SESSION") != "1" or not os.environ.get("KITTY_RC_PASSWORD"):
            raise KittyError(f"Open this reader with sol-kitty to use its {self.pane_name} pane.")
        self.reader_id = _number(os.environ.get("KITTY_WINDOW_ID", ""), "reader window")
        if shutil.which("kitten") is None:
            raise KittyError(f"The standalone kitten command is required for the {self.pane_name} pane.")

    def _remote(self, *arguments: str) -> str:
        try:
            completed = subprocess.run(
                ["kitten", "@", "--password-env=KITTY_RC_PASSWORD", "--use-password=always", *arguments],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=10, check=False, pass_fds=_remote_descriptors(),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise KittyError(f"Cannot reach this SOL kitty session: {error}") from error
        if completed.returncode:
            detail = completed.stderr.strip() or "remote control was refused"
            raise KittyError(f"{self.pane_name.capitalize()} pane action failed: {detail}")
        return completed.stdout

    def _is_open(self) -> bool:
        if self.window_id is None:
            return False
        try:
            windows = json.loads(self._remote("ls", "--match", f"id:{self.window_id}"))
            return any(window.get("id") == self.window_id
                       for os_window in windows for tab in os_window.get("tabs", [])
                       for window in tab.get("windows", []))
        except (TypeError, ValueError, AttributeError) as error:
            raise KittyError(f"kitty returned an invalid {self.pane_name} pane inventory.") from error

    def _forget(self) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
        self._temporary = self.mailbox = self.window_id = None

    def show(self, request: dict) -> int:
        self._require_session()
        # Validate/serialize before changing the visible pane or existing mailbox.
        self._sequence += 1
        try:
            payload = json.dumps({"sequence": self._sequence, "request": request},
                                 ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise KittyError(f"Invalid {self.pane_name} selection: {error}") from error
        if self.window_id is not None and not self._is_open():
            self._forget()
        if self._temporary is None:
            self._temporary = tempfile.TemporaryDirectory(prefix=f"sol-{self.pane_name}-pane-")
            self.mailbox = Path(self._temporary.name) / "selection.json"
        temporary = self.mailbox.with_suffix(".tmp")
        try:
            temporary.write_text(payload + "\n", encoding="utf-8")
            temporary.chmod(0o600)
            temporary.replace(self.mailbox)
            if self.window_id is None:
                response = self._remote(
                    "launch", "--match", f"window_id:{self.reader_id}",
                    "--source-window", f"id:{self.reader_id}", "--next-to", f"id:{self.reader_id}",
                    "--location", "vsplit", "--dont-take-focus", "--title", self.pane_title,
                    "--env=KITTY_LISTEN_ON", "--env=KITTY_RC_PASSWORD", "--env=SOL_KITTY_SESSION",
                    sys.executable, "-m", "sol.terminal.kitty", self.viewer_option, str(self.mailbox),
                )
                identifier = _number(response.strip(), f"{self.pane_name} window")
                if identifier == self.reader_id:
                    raise KittyError(f"kitty returned the reader window as the {self.pane_name} pane; refusing ownership.")
                self.window_id = identifier
        except OSError as error:
            if self.window_id is None:
                self._forget()
            raise KittyError(f"Could not update the {self.pane_name} pane selection: {error}") from error
        except KittyError:
            if self.window_id is None:
                self._forget()
            raise
        return self.window_id

    def close(self) -> None:
        if self.window_id is not None:
            self._require_session()
            if self.window_id == self.reader_id:
                raise KittyError(f"Refusing to close the reader as a {self.pane_name} pane.")
            self._remote("close-window", "--match", f"id:{self.window_id}", "--ignore-no-match")
        self._forget()

    def cleanup(self) -> None:
        try:
            self.close()
        except KittyError:
            # Removing the mailbox also tells an independently alive viewer to exit.
            self._forget()


class ComparisonPane(SourcePane):
    """A second auxiliary pane, using the same reader-owned lifecycle."""

    pane_name = "comparison"
    pane_title = "SOL comparison"
    viewer_option = "--comparison-viewer"


@dataclass(frozen=True)
class WindowSize:
    columns: int
    rows: int
    pixel_width: int
    pixel_height: int


def window_size(fd: int) -> WindowSize:
    """Use actual kitty pane geometry, including font/scale changes."""
    try:
        data = fcntl.ioctl(fd, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        rows, columns, pixel_width, pixel_height = struct.unpack("HHHH", data)
    except OSError as error:
        raise KittyError(f"Cannot inspect the source pane size: {error}") from error
    return WindowSize(columns, rows, pixel_width, pixel_height)


def _safe(value) -> str:
    return "".join(f"\\u{ord(c):04x}" if unicodedata.category(c) in {"Cc", "Cs"}
                   or unicodedata.bidirectional(c) in _BIDI else c for c in str(value))


def _fit_line(value: str, columns: int) -> str:
    available, out = max(0, columns - 1), []
    for character in _safe(value):
        width = 0 if unicodedata.combining(character) else (2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1)
        if width > available:
            break
        out.append(character)
        available -= width
    return "".join(out)


def viewer_labels(request: dict, page_index: int) -> tuple[str, str, str]:
    sources = request["sources"]
    source = sources[page_index]
    printed = source.get("printed_page")
    label = "not labelled" if printed is None else printed
    return ("SOURCE | " + str(request.get("title") or "Canonical passage"),
            f"Printed {label} | PDF {source['pdf_page']} | source {page_index + 1}/{len(sources)}",
            "Passage " + str(request["target_id"]))


def _image_rectangle(size: WindowSize) -> str:
    if size.columns < 12 or size.rows < 6:
        raise KittyError("Enlarge the source pane to display its full page.")
    if size.pixel_width < 1 or size.pixel_height < 1:
        raise KittyError("kitty did not report pixel dimensions; resize the source pane and retry.")
    return f"{size.columns}x{size.rows - 4}@0x3"


def icat_command(image: Path, size: WindowSize) -> list[str]:
    return ["kitten", "icat", "--stdin=no", "--transfer-mode=file", "--passthrough=none",
            "--use-window-size", f"{size.columns},{size.rows},{size.pixel_width},{size.pixel_height}",
            "--place", _image_rectangle(size), "--image-id", str(_IMAGE_ID), str(image)]


def draw_view(output, request: dict, page_index: int, size: WindowSize,
              image: Path | None = None, message: str = "") -> None:
    """All TTY output is owned by this process; icat produces escapes only."""
    output.write(_DELETE_IMAGE + "\x1b[2J\x1b[H")
    for row, label in enumerate(viewer_labels(request, page_index), 1):
        if row >= size.rows:
            break
        output.write(f"\x1b[{row};1H" + _fit_line(label, size.columns))
    if image is not None:
        try:
            completed = subprocess.run(
                icat_command(image, size), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                env=_child_environment(), check=False,
            )
            if completed.returncode:
                detail = completed.stderr.decode("utf-8", errors="replace").strip()
                raise KittyError(detail or "kitty image display failed")
            output.write(completed.stdout.decode("utf-8"))
        except (OSError, subprocess.TimeoutExpired, UnicodeError, KittyError) as error:
            message = f"Source display: {error}"
    if message and size.rows > 4:
        output.write("\x1b[4;1H" + _fit_line(message, size.columns))
    if size.rows:
        footer = "n/p: pages | r: refresh | q: close | pinned"
        output.write(f"\x1b[{size.rows};1H" + _fit_line(footer, size.columns))
    output.flush()


def read_selection(mailbox: Path) -> tuple[int, dict]:
    try:
        envelope = json.loads(mailbox.read_text(encoding="utf-8"))
        sequence, request = envelope["sequence"], envelope["request"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("invalid selection sequence")
        if not isinstance(request, dict) or request.get("version") != 1:
            raise ValueError("unsupported source selection")
        if not isinstance(request.get("target_id"), str):
            raise ValueError("source selection lacks its canonical passage ID")
        sources = request.get("sources")
        if not isinstance(sources, list) or not sources or any(
            not isinstance(source, dict) or isinstance(source.get("pdf_page"), bool)
            or not isinstance(source.get("pdf_page"), int) or source["pdf_page"] < 1 for source in sources
        ):
            raise ValueError("source selection lacks its ordered PDF pages")
        return sequence, request
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise KittyError(f"Cannot read the source selection: {error}") from error


def _key_action(data: bytes) -> str | None:
    if data in {b"q", b"Q", b"\x03", b"\x04"}:
        return "close"
    if data in {b"r", b"R"}:
        return "refresh"
    if data in {b"n", b"j", b"l", b" ", b"\x1b[C", b"\x1b[B", b"\x1b[6~"}:
        return "next"
    if data in {b"p", b"k", b"h", b"\x1b[D", b"\x1b[A", b"\x1b[5~"}:
        return "previous"
    return None


def consume_keys(buffer: bytes, key_action=None) -> tuple[list[str], bytes]:
    """Consume batched/split keys and ignore terminal protocol replies."""
    actions = []
    key_action = key_action or _key_action
    sequences = (b"\x1b[C", b"\x1b[B", b"\x1b[D", b"\x1b[A", b"\x1b[5~", b"\x1b[6~",
                 b"\x1b[H", b"\x1b[F", b"\x1b[1~", b"\x1b[4~")
    while buffer:
        if buffer[0] != 27:
            action = key_action(buffer[:1])
            if action:
                actions.append(action)
            buffer = buffer[1:]
            continue
        known = next((key for key in sequences if buffer.startswith(key)), None)
        if known:
            action = key_action(known)
            if action:
                actions.append(action)
            buffer = buffer[len(known):]
            continue
        if any(key.startswith(buffer) for key in sequences):
            break
        if buffer.startswith(b"\x1b["):
            end = next((i for i, value in enumerate(buffer[2:], 2) if 64 <= value <= 126), None)
            if end is None:
                break
            buffer = buffer[end + 1:]
        elif buffer[:2] in {b"\x1b_", b"\x1bP", b"\x1b]"}:
            end = buffer.find(b"\x1b\\", 2)
            if end < 0:
                break
            buffer = buffer[end + 2:]
        elif len(buffer) < 2:
            break
        else:
            buffer = buffer[2:]
    # A broken/unsupported escape sequence cannot grow memory indefinitely.
    return actions, buffer if len(buffer) < 8192 else b""


class _RenderWorker:
    """One cancellable child; obsolete requests never reach the TTY."""

    def __init__(self):
        self.process = None
        self.token = None

    def request(self, token, request, page_index) -> None:
        if self.process is not None and self.token == token:
            return
        self.close()
        self.token = token
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-m", "sol.terminal.kitty", "--render-page", str(page_index)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=_child_environment(), start_new_session=True,
            )
            self.process.stdin.write(json.dumps(request, ensure_ascii=False, allow_nan=False))
            self.process.stdin.close()
            self.process.stdin = None
        except (OSError, ValueError) as error:
            self.close()
            raise KittyError(f"Cannot start the source renderer: {error}") from error

    def result(self, expected):
        if self.process is None or self.process.poll() is None:
            return None
        process, token = self.process, self.token
        self.process = self.token = None
        stdout, stderr = process.communicate()
        if token != expected:
            return None
        if process.returncode:
            return None, "Source rendering: " + (stderr.strip() or "renderer failed")
        try:
            image = json.loads(stdout)
            if not isinstance(image, str) or not Path(image).is_absolute():
                raise ValueError("renderer did not return an absolute image path")
            return Path(image), ""
        except (ValueError, TypeError) as error:
            return None, f"Source rendering: {error}"

    def close(self):
        if self.process is not None:
            process = self.process
            self.process = self.token = None
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=.5)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=2)
            process.communicate()


def viewer_main(mailbox: Path) -> int:
    """An explicit source snapshot; navigation here never moves the reader."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise KittyError("The source viewer requires its own interactive kitty pane.")
    for name in (*_CONTROL_ENV, "SOL_KITTY_SESSION"):
        os.environ.pop(name, None)
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    worker = _RenderWorker()
    sequence, request = read_selection(mailbox)
    page_index, revision = 0, 0
    image, message, dirty = None, "Rendering source page…", True
    old_size = None
    old_signature = None
    pending_keys = b""
    terminating = False
    previous_handlers = {}

    def stop(_signum, _frame):
        nonlocal terminating
        terminating = True

    try:
        for signum in (signal.SIGTERM, signal.SIGHUP):
            previous_handlers[signum] = signal.signal(signum, stop)
        tty.setraw(fd)
        sys.stdout.write(_ENTER)
        sys.stdout.flush()
        while not terminating:
            try:
                stat = mailbox.stat()
            except FileNotFoundError:
                break
            signature = (stat.st_ino, stat.st_mtime_ns, stat.st_size)
            if signature != old_signature:
                old_signature = signature
                try:
                    new_sequence, new_request = read_selection(mailbox)
                    if new_sequence != sequence:
                        sequence, request, page_index = new_sequence, new_request, 0
                        revision += 1
                        image, message, dirty = None, "Rendering source page…", True
                except (OSError, KittyError) as error:
                    image, message, dirty = None, str(error), True
            token = (sequence, page_index, revision)
            result = worker.result(token)
            if result is not None:
                image, message = result
                dirty = True
            if image is None and not message.startswith(("Source rendering:", "Cannot read")):
                try:
                    worker.request(token, request, page_index)
                except KittyError as error:
                    message, dirty = "Source rendering: " + str(error), True
            size = window_size(fd)
            if size != old_size:
                old_size, dirty = size, True
            if dirty:
                draw_view(sys.stdout, request, page_index, size, image, message)
                dirty = False
            readable, _, _ = select.select([fd], [], [], .15)
            if readable:
                data = os.read(fd, 64)
                if not data:
                    break
                pending_keys += data
                actions, pending_keys = consume_keys(pending_keys)
                for action in actions:
                    if action == "close":
                        terminating = True
                        break
                    new_index = page_index
                    if action == "next":
                        new_index = min(len(request["sources"]) - 1, page_index + 1)
                    elif action == "previous":
                        new_index = max(0, page_index - 1)
                    if new_index != page_index or action == "refresh":
                        page_index = new_index
                        revision += 1
                        image, message, dirty = None, "Rendering source page…", True
    finally:
        try:
            worker.close()
        finally:
            try:
                sys.stdout.write(_DELETE_IMAGE + _LEAVE)
                sys.stdout.flush()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, original)
                for signum, handler in previous_handlers.items():
                    signal.signal(signum, handler)
    return 0


def render_child(page_index: int) -> int:
    """Cancellation unwinds SourceService's temporary PDF/page contexts."""
    from sol.terminal.source import render_page

    for name in (*_CONTROL_ENV, "SOL_KITTY_SESSION"):
        os.environ.pop(name, None)
    previous_handlers = {}

    def cancel(signum, _frame):
        raise SystemExit(128 + signum)

    try:
        for signum in (signal.SIGTERM, signal.SIGHUP):
            previous_handlers[signum] = signal.signal(signum, cancel)
        request = json.load(sys.stdin)
        image = render_page(request, page_index)
        print(json.dumps(str(image)))
        return 0
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments and arguments[0] == "--zsh":
            return launch_zsh(arguments[1:])
        if arguments and arguments[0] == "--comparison-viewer":
            if len(arguments) != 2:
                raise KittyError("Internal comparison usage: --comparison-viewer SELECTION_MAILBOX")
            from sol.terminal.comparison import viewer_main as comparison_viewer
            return comparison_viewer(Path(arguments[1]))
        if arguments and arguments[0] == "--render-page":
            if len(arguments) != 2 or not arguments[1].isdecimal():
                raise KittyError("Internal rendering usage: --render-page PAGE_INDEX")
            return render_child(int(arguments[1]))
        if arguments and arguments[0] == "--viewer":
            if len(arguments) != 2:
                raise KittyError("Internal viewer usage: --viewer SELECTION_MAILBOX")
            return viewer_main(Path(arguments[1]))
        if arguments in (["-h"], ["--help"]):
            from sol.reader.options import build_parser
            print("Usage: sol-kitty [SOL options]\n"
                  "       sol-kitty --zsh [--corpus DIRECTORY] [--directory DIRECTORY]\n\n"
                  "Use --zsh for normal shell commands and pipelines.\n"
                  "Open SOL in its private kitty profile. "
                  "Use source show in the reader to open the verified source pane.\n"
                  "Ctrl+Alt+Left/Right switches panes; add Shift to resize.\n"
                  "The profile leaves SOL's Ctrl+S and Ctrl+C editing keys unchanged.\n")
            print(build_parser().format_help())
            return 0
        if arguments == ["--version"]:
            from sol import __version__ as VERSION
            print(f"sol-kitty {VERSION}")
            return 0
        return launch_reader(arguments)
    except (KittyError, OSError, ValueError) as error:
        print(f"sol-kitty: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
