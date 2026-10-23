"""Private inherited JSON pipes for explicit native-reader actions.

No network listener, daemon, shell, worker thread or SQLite sharing. Requests
are serviced on the launching thread, where the existing workspace is owned.
"""
from contextlib import ExitStack
import json
import os
import selectors
import subprocess


MAX_REQUEST = 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate reader action field")
        value[key] = item
    return value


def _constant(value):
    raise ValueError("non-finite reader action value")


def run_native(command, *, cwd, env, handler):
    """Keep native terminal I/O inherited while servicing bounded data requests."""
    with ExitStack() as stack:
        owned = set()
        def close(fd):
            if fd in owned:
                owned.remove(fd)
                os.close(fd)
        def pipe():
            pair = os.pipe()
            for fd in pair:
                owned.add(fd)
                stack.callback(close, fd)
            return pair
        requests, request_writer = pipe()
        response_reader, responses = pipe()
        environment = dict(env, SOL_NVIM_REQUEST_FD=str(request_writer), SOL_NVIM_RESPONSE_FD=str(response_reader))
        process = subprocess.Popen(command, cwd=cwd, env=environment,
                                   pass_fds=(request_writer, response_reader))
        close(request_writer)
        close(response_reader)
        selector = stack.enter_context(selectors.DefaultSelector())
        os.set_blocking(requests, False)
        os.set_blocking(responses, False)
        selector.register(requests, selectors.EVENT_READ)
        incoming, outgoing = b"", b""
        # A handler may offer idle(): one bounded unit of work, run only when no
        # request is waiting or partly received and every response is written.
        idle = getattr(handler, "idle", None)
        try:
            while process.poll() is None:
                events = selector.select(.1)
                if not events and not incoming and not outgoing and idle is not None:
                    idle()
                for key, _ in events:
                    if key.fd == responses:
                        try:
                            outgoing = outgoing[os.write(responses, outgoing):]
                        except BrokenPipeError:
                            selector.unregister(responses)
                            outgoing = b""
                        if not outgoing and responses in selector.get_map():
                            selector.unregister(responses)
                        continue
                    data = os.read(requests, 65536)
                    if not data:
                        selector.unregister(requests)
                        continue
                    incoming += data
                    if len(incoming) > MAX_REQUEST:
                        raise ValueError("reader action exceeds the 1 MiB request budget")
                    while b"\n" in incoming:
                        line, incoming = incoming.split(b"\n", 1)
                        request_id = None
                        try:
                            request = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
                            if (not isinstance(request, dict) or type(request.get("id")) is not int
                                    or not 0 < request["id"] < 2**31):
                                raise ValueError("invalid reader request envelope")
                            request_id = request.pop("id")
                            result = {"id": request_id, "ok": True, "result": handler(request)}
                        except (ValueError, RuntimeError, OSError) as error:
                            result = {"id": request_id, "ok": False, "error": str(error)[:2048]}
                        encoded = json.dumps(result, ensure_ascii=True, allow_nan=False).encode() + b"\n"
                        if len(encoded) + len(outgoing) > MAX_RESPONSE:
                            raise ValueError("reader action exceeds the 16 MiB response budget")
                        outgoing += encoded
                        if responses not in selector.get_map():
                            selector.register(responses, selectors.EVENT_WRITE)
            return process.wait()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
