"""Private action pipes service explicit operations on the owning thread."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from sol.being.neovim.channel import run_native


class ReaderChannelTests(unittest.TestCase):
    def run_child(self, scenario, handler):
        program = """
import json, os
writer = os.fdopen(int(os.environ['SOL_NVIM_REQUEST_FD']), 'wb', buffering=0)
reader = os.fdopen(int(os.environ['SOL_NVIM_RESPONSE_FD']), 'rb')
def request(data):
    writer.write(data + b'\\n')
    return json.loads(reader.readline())
""" + scenario
        with tempfile.TemporaryDirectory(prefix="sol-reader-channel-") as temporary:
            return run_native([sys.executable, "-I", "-B", "-c", program], cwd=Path(temporary),
                              env=os.environ, handler=handler)

    def test_requests_execute_on_launching_thread_and_multiple_actions_share_one_process(self):
        owner, observed = threading.get_ident(), []
        def handle(request):
            self.assertEqual(threading.get_ident(), owner)
            observed.append(request)
            return {"echo": request["slot"]}
        status = self.run_child("""
for number in range(1, 4):
    value = request(json.dumps({'id': number, 'op': 'marker_set', 'slot': number}).encode())
    assert value == {'id': number, 'ok': True, 'result': {'echo': number}}
""", handle)
        self.assertEqual(status, 0)
        self.assertEqual(len(observed), 3)

    def test_idle_work_runs_on_the_launching_thread_only_between_requests(self):
        owner, events = threading.get_ident(), []
        def handle(request):
            events.append("request")
            return {"ok": True}
        def idle():
            self.assertEqual(threading.get_ident(), owner)
            events.append("idle")
        handle.idle = idle
        status = self.run_child("""
import time
time.sleep(.35)
assert request(b'{"id":1,"op":"marker_set"}')['ok'] is True
time.sleep(.35)
""", handle)
        self.assertEqual(status, 0)
        self.assertEqual(events.count("request"), 1)
        at = events.index("request")
        self.assertIn("idle", events[:at])
        self.assertIn("idle", events[at + 1:])

    def test_idle_work_waits_for_a_partly_received_request(self):
        events = []
        def handle(request):
            events.append(("request", time.time()))
            return {"ok": True}
        handle.idle = lambda: events.append(("idle", time.time()))
        with tempfile.TemporaryDirectory(prefix="sol-reader-channel-mark-") as directory:
            mark = Path(directory) / "fragment"
            with patch.dict(os.environ, SOL_TEST_FRAGMENT_MARK=str(mark)):
                status = self.run_child("""
import time
writer.write(b'{"id":1,')
open(os.environ['SOL_TEST_FRAGMENT_MARK'], 'w').write(repr(time.time()))
time.sleep(.35)
writer.write(b'"op":"partial"}\\n')
assert json.loads(reader.readline())['ok'] is True
""", handle)
            sent = float(mark.read_text())
        self.assertEqual(status, 0)
        received = next(at for kind, at in events if kind == "request")
        # The first fragment was buffered for about 350 ms; no idle work ran in between.
        self.assertEqual([at for kind, at in events if kind == "idle" and sent + .05 < at < received], [])

    def test_invalid_json_duplicate_fields_and_invalid_ids_never_call_handler(self):
        def refuse(request):
            self.fail("invalid request reached workspace handler")
        scenario = """
for data in (b'not json', b'[]', b'{"id":true}', b'{"id":1,"id":2}', b'{"id":1,"number":NaN}'):
    value = request(data)
    assert value['ok'] is False
"""
        self.assertEqual(self.run_child(scenario, refuse), 0)

    def test_refused_operation_returns_visible_error_without_ending_channel(self):
        def handle(request):
            if request["op"] == "bad":
                raise ValueError("marker slot is unavailable")
            return {"saved": True}
        self.assertEqual(self.run_child("""
value = request(b'{"id":1,"op":"bad"}')
assert value['ok'] is False and 'unavailable' in value['error']
value = request(b'{"id":2,"op":"good"}')
assert value['ok'] is True and value['result']['saved'] is True
""", handle), 0)


if __name__ == "__main__":
    unittest.main()
