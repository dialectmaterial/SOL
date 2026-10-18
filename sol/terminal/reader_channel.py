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


class NativeChannel:
    """A started native process whose requests are served later, on this thread.

    Starting first lets the editor draw while Python finishes its own work;
    its requests wait in the pipe until serve() runs.
    """

    def __init__(self, command, *, cwd, env):
        self._stack = ExitStack()
        self._owned = set()
        try:
            requests, request_writer = self._pipe()
            response_reader, responses = self._pipe()
            environment = dict(env, SOL_NVIM_REQUEST_FD=str(request_writer),
                               SOL_NVIM_RESPONSE_FD=str(response_reader))
            self.process = subprocess.Popen(command, cwd=cwd, env=environment,
                                            pass_fds=(request_writer, response_reader))
            self._stack.callback(self._stop)
            self._close(request_writer)
            self._close(response_reader)
            self._requests, self._responses = requests, responses
        except BaseException:
            self._stack.close()
            raise

    def _close(self, fd):
        if fd in self._owned:
            self._owned.remove(fd)
            os.close(fd)

    def _pipe(self):
        pair = os.pipe()
        for fd in pair:
            self._owned.add(fd)
            self._stack.callback(self._close, fd)
        return pair

    def _stop(self):
        process = self.process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    def serve(self, handler):
        """Answer requests until the process exits; returns its exit code."""
        with self._stack:
            requests, responses, process = self._requests, self._responses, self.process
            selector = self._stack.enter_context(selectors.DefaultSelector())
            os.set_blocking(requests, False)
            os.set_blocking(responses, False)
            selector.register(requests, selectors.EVENT_READ)
            incoming, outgoing = b"", b""
            while process.poll() is None:
                for key, _ in selector.select(.1):
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

    def abort(self):
        self._stack.close()


def run_native(command, *, cwd, env, handler):
    """Keep native terminal I/O inherited while servicing bounded data requests."""
    return NativeChannel(command, cwd=cwd, env=env).serve(handler)
