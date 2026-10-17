"""Private action pipes service explicit operations on the owning thread."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from sol.terminal.reader_channel import run_native


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
