"""Private, one-shot local transport around CORE reference envelopes.

Correlation tokens identify an exchange, never a passage or authenticated actor.
The caller selects the corpus independently. No packet supplies a path, command,
workspace, or write authority. Only the explicit return command publishes a file.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
import sys
import tempfile


MAX_HANDOFF_BYTES = 65536 + 4096
_META_FIELDS = {"handoff_version", "session_nonce", "origin_sha256"}
_RETURN_FIELDS = _META_FIELDS | {"reference"}


class HandoffError(ValueError):
    """A refused local exchange must leave reader and personal state untouched."""


def sol_shim_bytes():
    """Fixed trusted runtime wrapper; no corpus or packet text becomes code."""
    package = str(Path(__file__).resolve().parents[2])
    bootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); import sol; raise SystemExit(sol.cli())"
    return ("#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -I -B -c "
            + shlex.quote(bootstrap) + " " + shlex.quote(package) + ' "$@"\n').encode("utf-8")


def _state(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _private_directory(directory):
    path = Path(directory).expanduser()
    if ".." in path.parts:
        raise HandoffError("Handoff paths cannot contain parent traversal")
    path = path.absolute()
    if "sources" in path.parts:
        raise HandoffError("Read-only sources cannot contain handoff transport")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise HandoffError("Handoff paths cannot contain symbolic links")
    try:
        before = path.lstat()
        if (not stat.S_ISDIR(before.st_mode) or before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) != 0o700):
            raise HandoffError("Handoff directory must be owned by this user with mode 0700")
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        opened = os.fstat(descriptor)
        if ((before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
                or opened.st_uid != os.getuid() or stat.S_IMODE(opened.st_mode) != 0o700):
            os.close(descriptor)
            raise HandoffError("Handoff directory changed while opening")
        return path, descriptor
    except OSError as error:
        raise HandoffError(f"Cannot open private handoff directory: {error}") from error


def _read(descriptor, name, maximum):
    try:
        initial = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if (not stat.S_ISREG(initial.st_mode) or initial.st_uid != os.getuid()
                or stat.S_IMODE(initial.st_mode) & 0o077 or initial.st_nlink != 1):
            raise HandoffError("Handoff files must be private, owned, non-linked regular files")
        if initial.st_size > maximum:
            raise HandoffError("Handoff file exceeds its size limit")
        child = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                        | getattr(os, "O_NONBLOCK", 0), dir_fd=descriptor)
        with os.fdopen(child, "rb") as stream:
            before = os.fstat(stream.fileno())
            if _state(initial) != _state(before):
                raise HandoffError("Handoff file changed while opening")
            data = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
        current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if _state(before) != _state(after) or _state(before) != _state(current):
            raise HandoffError("Handoff file changed while reading")
        if len(data) > maximum:
            raise HandoffError("Handoff file exceeds its size limit")
        return data
    except FileNotFoundError:
        raise
    except OSError as error:
        raise HandoffError(f"Cannot read private handoff file: {error}") from error


def _decode(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise HandoffError("Duplicate handoff JSON field")
            result[key] = value
        return result

    def nonfinite(value):
        raise HandoffError("Non-finite handoff JSON number")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
    except (UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, HandoffError):
            raise
        raise HandoffError("Invalid handoff JSON") from error


def _metadata(value, fields=_META_FIELDS):
    if (not isinstance(value, dict) or set(value) != fields
            or type(value.get("handoff_version")) is not int or value["handoff_version"] != 1):
        raise HandoffError("Unsupported handoff metadata fields or version")
    for name in ("session_nonce", "origin_sha256"):
        if not isinstance(value[name], str) or not re.fullmatch(r"[0-9a-f]{64}", value[name]):
            raise HandoffError("Invalid handoff correlation binding")
    return {key: value[key] for key in _META_FIELDS}


def _load(descriptor):
    from sol.core import MAX_REFERENCE_BYTES, decode_reference

    try:
        metadata = _metadata(_decode(_read(descriptor, "session.json", 4096)))
        raw = _read(descriptor, "outgoing.json", MAX_REFERENCE_BYTES)
    except FileNotFoundError as error:
        raise HandoffError("Handoff is absent or incomplete; open a new exchange from BEING") from error
    if hashlib.sha256(raw).hexdigest() != metadata["origin_sha256"]:
        raise HandoffError("Handoff origin fingerprint disagrees with its session")
    return decode_reference(raw), metadata


def load_handoff(directory):
    """Read transport selected by the caller, never from an envelope field."""
    _, descriptor = _private_directory(directory)
    try:
        return _load(descriptor)
    finally:
        os.close(descriptor)


def _publish(descriptor, name, data):
    """Exclusive, atomic publication in an opened private directory."""
    temporary = ".sol-return-building-" + secrets.token_hex(8)
    created = False
    try:
        child = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                        | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=descriptor)
        created = True
        with os.fdopen(child, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, name, src_dir_fd=descriptor, dst_dir_fd=descriptor, follow_symlinks=False)
        os.fsync(descriptor)
    except FileExistsError as error:
        raise HandoffError("A return is already present; nothing was overwritten. Close and reopen for a new exchange") from error
    except OSError as error:
        raise HandoffError(f"Cannot publish private handoff file: {error}") from error
    finally:
        if created:
            os.unlink(temporary, dir_fd=descriptor)


def submit_return(directory, snapshot, identifier=None):
    """Propose one checked reference; never navigate or write personal state."""
    from sol.core import capture_reference, check_reference

    path, descriptor = _private_directory(directory)
    try:
        origin, metadata = _load(descriptor)
        check_reference(snapshot, origin)
        packet = capture_reference(snapshot, identifier if identifier is not None else origin["reference"]["requested_id"])
        wrapper = {**metadata, "reference": packet}
        data = (json.dumps(wrapper, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
                + "\n").encode("utf-8")
        if len(data) > MAX_HANDOFF_BYTES:
            raise HandoffError("Returned handoff exceeds its size limit")
        _, current = _load(descriptor)
        if current != metadata:
            raise HandoffError("Handoff session changed while preparing the return")
        check_reference(snapshot, packet)
        actual = path.lstat()
        opened = os.fstat(descriptor)
        if (actual.st_dev, actual.st_ino) != (opened.st_dev, opened.st_ino):
            raise HandoffError("Handoff directory was replaced before publication")
        _publish(descriptor, "returned.json", data)
        return {"status": "proposed", "session_nonce": metadata["session_nonce"],
                "requested_id": packet["reference"]["requested_id"],
                "target_id": packet["reference"]["target_id"],
                "message": "Return proposed; run essence check or essence return in BEING. No reader state was changed."}
    finally:
        os.close(descriptor)


class HandoffSession:
    """BEING owns one captured origin and transport directory until explicit close."""
    def __init__(self, directory, metadata, identity, bin_identity):
        self.directory = directory
        self.outgoing_file = directory / "outgoing.json"
        self.metadata = metadata
        self._identity = identity
        self._bin_identity = bin_identity
        self.closed = False

    @classmethod
    def create(cls, packet):
        from sol.core import encode_reference

        data = (encode_reference(packet) + "\n").encode("utf-8")
        metadata = {"handoff_version": 1, "session_nonce": secrets.token_hex(32),
                    "origin_sha256": hashlib.sha256(data).hexdigest()}
        directory = Path(tempfile.mkdtemp(prefix="sol-handoff-", dir="/tmp"))
        directory.chmod(0o700)
        _, descriptor = _private_directory(directory)
        try:
            identity = os.fstat(descriptor)
            _publish(descriptor, "outgoing.json", data)
            _publish(descriptor, "session.json", (json.dumps(metadata, sort_keys=True) + "\n").encode())
            os.mkdir("bin", 0o700, dir_fd=descriptor)
            command_directory = os.stat("bin", dir_fd=descriptor, follow_symlinks=False)
            return cls(directory, metadata, (identity.st_dev, identity.st_ino),
                       (command_directory.st_dev, command_directory.st_ino))
        except Exception:
            for name in ("outgoing.json", "session.json"):
                try:
                    os.unlink(name, dir_fd=descriptor)
                except FileNotFoundError:
                    pass
            try:
                os.rmdir("bin", dir_fd=descriptor)
            except FileNotFoundError:
                pass
            directory.rmdir()
            raise
        finally:
            os.close(descriptor)

    def _open(self):
        if self.closed:
            raise HandoffError("This handoff is closed")
        path, descriptor = _private_directory(self.directory)
        value = os.fstat(descriptor)
        if (value.st_dev, value.st_ino) != self._identity:
            os.close(descriptor)
            raise HandoffError("Handoff directory was replaced; refusing ownership")
        return path, descriptor

    def read_return(self):
        from sol.core import decode_reference

        _, descriptor = self._open()
        try:
            _, metadata = _load(descriptor)
            if metadata != self.metadata:
                raise HandoffError("The captured handoff session was altered")
            try:
                wrapper = _decode(_read(descriptor, "returned.json", MAX_HANDOFF_BYTES))
            except FileNotFoundError as error:
                raise HandoffError("No return is ready; run sol reference return in the ESSENCE pane first") from error
            if _metadata(wrapper, _RETURN_FIELDS) != metadata:
                raise HandoffError("Returned reference belongs to another exchange")
            try:
                encoded = json.dumps(wrapper["reference"], ensure_ascii=True, allow_nan=False)
            except (ValueError, TypeError, RecursionError) as error:
                raise HandoffError("Invalid returned reference JSON") from error
            return decode_reference(encoded)
        finally:
            os.close(descriptor)

    def close(self):
        """Remove only reserved transport/shim files; preserve unexpected work."""
        if self.closed:
            return
        path, descriptor = self._open()
        try:
            for name in ("outgoing.json", "session.json", "returned.json"):
                try:
                    os.unlink(name, dir_fd=descriptor)
                except FileNotFoundError:
                    pass
            try:
                child = os.open("bin", os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0), dir_fd=descriptor)
            except FileNotFoundError:
                child = None
            if child is not None:
                try:
                    value = os.fstat(child)
                    if (value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) != 0o700
                            or (value.st_dev, value.st_ino) != self._bin_identity):
                        raise HandoffError("Unexpected/replaced shim directory; its files were retained")
                    try:
                        expected = sol_shim_bytes()
                        actual = _read(child, "sol", max(4096, len(expected)))
                    except FileNotFoundError:
                        pass
                    else:
                        if actual != expected:
                            raise HandoffError("Unexpected command-wrapper content; it was retained")
                        os.unlink("sol", dir_fd=child)
                finally:
                    os.close(child)
                os.rmdir("bin", dir_fd=descriptor)
            current = path.lstat()
            if (current.st_dev, current.st_ino) != self._identity:
                raise HandoffError("Handoff directory was replaced during cleanup; replacement was retained")
            path.rmdir()
            self.closed = True
        except OSError as error:
            raise HandoffError(f"Handoff files cleaned, but unexpected files/directory were retained at {path}: {error}") from error
        finally:
            os.close(descriptor)
