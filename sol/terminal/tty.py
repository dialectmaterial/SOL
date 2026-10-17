"""Small POSIX terminal primitives shared by foreground views and hosts."""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import struct
import termios

ENTER = "\x1b[?1049h\x1b[?25l"
LEAVE = "\x1b[?25h\x1b[?1049l"


class TerminalError(RuntimeError):
    """A terminal adapter could not complete its requested operation."""


@dataclass(frozen=True)
class WindowSize:
    columns: int
    rows: int
    pixel_width: int
    pixel_height: int


def window_size(fd: int) -> WindowSize:
    """Use actual terminal geometry, including font/scale changes."""
    try:
        data = fcntl.ioctl(fd, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        rows, columns, pixel_width, pixel_height = struct.unpack("HHHH", data)
    except OSError as error:
        raise TerminalError(f"Cannot inspect the terminal size: {error}") from error
    return WindowSize(columns, rows, pixel_width, pixel_height)


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
