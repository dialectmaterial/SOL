"""Validate a private reference handoff, then open the user's ordinary zsh."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sol.terminal.essence",
        description="Open ESSENCE's native shell for one verified local reference handoff.",
    )
    parser.add_argument("--handoff-dir", required=True, type=Path, metavar="DIRECTORY",
                        help="explicit private handoff session directory")
    parser.add_argument("--corpus", type=Path, metavar="DIRECTORY",
                        help="independently select the local canonical corpus")
    return parser


def _private(value, kind, mode):
    if (not kind(value.st_mode) or value.st_uid != os.getuid()
            or stat.S_IMODE(value.st_mode) != mode):
        raise ValueError("ESSENCE's command wrapper needs an owned private directory and executable")


def _identity(value):
    return value.st_dev, value.st_ino


def _directory_identity(directory: Path, expected=None):
    value = directory.lstat()
    _private(value, stat.S_ISDIR, 0o700)
    identity = _identity(value)
    if expected is not None and identity != expected:
        raise ValueError("ESSENCE's handoff directory was replaced while preparing the shell")
    return identity


def _sol_shim(directory: Path, expected_root, expected_bin) -> Path:
    """Create only a fixed current-interpreter shim; never replace existing data."""
    from sol.terminal.handoff import sol_shim_bytes

    content = sol_shim_bytes()
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    parent = os.open(directory, flags)
    command_directory = None
    try:
        opened_root = os.fstat(parent)
        _private(opened_root, stat.S_ISDIR, 0o700)
        if _identity(opened_root) != expected_root:
            raise ValueError("ESSENCE's handoff directory was replaced before creating the wrapper")
        before_bin = os.stat("bin", dir_fd=parent, follow_symlinks=False)
        _private(before_bin, stat.S_ISDIR, 0o700)
        if _identity(before_bin) != expected_bin:
            raise ValueError("ESSENCE's command directory was replaced before opening it")
        command_directory = os.open("bin", flags, dir_fd=parent)
        opened_bin = os.fstat(command_directory)
        _private(opened_bin, stat.S_ISDIR, 0o700)
        if _identity(before_bin) != _identity(opened_bin):
            raise ValueError("ESSENCE's command directory changed while opening it")
        if set(os.listdir(command_directory)) - {"sol"}:
            raise ValueError("ESSENCE's private command directory contains unexpected files")
        try:
            descriptor = os.open("sol", os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                                 0o700, dir_fd=command_directory)
        except FileExistsError:
            descriptor = os.open("sol", os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                                 | getattr(os, "O_NONBLOCK", 0), dir_fd=command_directory)
            with os.fdopen(descriptor, "rb") as existing:
                before = os.fstat(existing.fileno())
                _private(before, stat.S_ISREG, 0o700)
                if before.st_nlink != 1 or before.st_size != len(content) or existing.read(len(content) + 1) != content:
                    raise ValueError("ESSENCE will not overwrite an existing command wrapper")
                after = os.fstat(existing.fileno())
                current = os.stat("sol", dir_fd=command_directory, follow_symlinks=False)
                state = lambda value: (value.st_dev, value.st_ino, value.st_size,
                                       value.st_mtime_ns, value.st_ctime_ns, value.st_mode)
                if state(before) != state(after) or state(before) != state(current):
                    raise ValueError("ESSENCE's command wrapper changed while checking it")
        else:
            with os.fdopen(descriptor, "wb") as created:
                os.fchmod(created.fileno(), 0o700)
                created.write(content)
                created.flush()
                os.fsync(created.fileno())
        current_bin = os.stat("bin", dir_fd=parent, follow_symlinks=False)
        _private(current_bin, stat.S_ISDIR, 0o700)
        if _identity(current_bin) != expected_bin:
            raise ValueError("ESSENCE's command directory changed while preparing the wrapper")
        _directory_identity(directory, expected_root)
    finally:
        if command_directory is not None:
            os.close(command_directory)
        os.close(parent)
    return directory / "bin" / "sol"


def _environment(directory: Path, corpus: Path, command: Path) -> dict[str, str]:
    environment = dict(os.environ)
    for name in tuple(environment):
        if (name in {"KITTY_RC_PASSWORD", "KITTYRC_PASSWORD", "KITTY_LISTEN_ON", "LISTEN_ON", "SOL_KITTY_SESSION"}
                or name.startswith(("SOL_ACTOR", "SOL_WORKSPACE"))):
            environment.pop(name)
    environment["SOL_CORPUS"] = str(corpus)
    environment["SOL_HANDOFF_DIR"] = str(directory)
    environment["SOL_REFERENCE_FILE"] = str(directory / "outgoing.json")
    commands = str(command.parent)
    environment["PATH"] = os.pathsep.join([commands, *[
        item for item in environment.get("PATH", "").split(os.pathsep) if item != commands
    ]])
    return environment


def _welcome(packet):
    record = packet["reference"]
    source = record["sources"][0]
    # Printed labels may contain arbitrary Unicode; keep control characters inert.
    printed = json.dumps(source["printed_page"], ensure_ascii=True)
    return "\n".join((
        "ESSENCE | canonical reference " + record["target_id"],
        f"Source: printed page {printed}; PDF page {source['pdf_page']}.",
        'Check: sol reference check "$SOL_REFERENCE_FILE"',
        "Return: sol reference return [ID] (omit ID to return the original reference)",
        "Back in BEING: essence check, then essence return.",
    ))


def main(arguments: list[str] | None = None) -> int:
    options = build_parser().parse_args(arguments)
    previous_directory = None
    try:
        from sol.core import check_reference, discover_corpus, load_snapshot
        from sol.terminal.handoff import load_handoff

        selected = discover_corpus(options.corpus)
        if selected is None:
            raise ValueError("No canonical corpus configured; choose --corpus DIRECTORY")
        snapshot = load_snapshot(selected)
        handoff = options.handoff_dir.expanduser().absolute()
        expected_root = _directory_identity(handoff)
        packet, metadata = load_handoff(handoff)
        _directory_identity(handoff, expected_root)
        check_reference(snapshot, packet)
        shell = shutil.which("zsh")
        if shell is None:
            raise ValueError("ESSENCE needs zsh on PATH; install or select an existing zsh before opening it")
        expected_bin = _directory_identity(handoff / "bin")
        command = _sol_shim(handoff, expected_root, expected_bin)
        environment = _environment(handoff, snapshot.corpus_directory, command)
        previous_directory = Path.cwd()
        os.chdir(snapshot.corpus_directory)
        _directory_identity(handoff, expected_root)
        current_packet, current_metadata = load_handoff(handoff)
        _directory_identity(handoff, expected_root)
        if current_packet != packet or current_metadata != metadata:
            raise ValueError("ESSENCE's handoff changed while preparing the shell")
        check_reference(snapshot, current_packet)
        _sol_shim(handoff, expected_root, expected_bin)
        _directory_identity(handoff, expected_root)
        print(_welcome(packet), flush=True)
        os.execve(shell, [shell, "-i"], environment)
        return 0
    except (ValueError, OSError) as error:
        print(f"sol ESSENCE: {error}", file=sys.stderr)
        return 2
    finally:
        # execve replaces this process. This path runs only on failure or in tests.
        if previous_directory is not None:
            os.chdir(previous_directory)


if __name__ == "__main__":
    raise SystemExit(main())
