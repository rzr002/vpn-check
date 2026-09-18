import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_server as web


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.manager = web.CheckManager(self.root)

    def tearDown(self):
        self.manager.stop()
        self.tmp.cleanup()

    def wait_finished(self):
        deadline = time.monotonic() + 4
        while self.manager.state()['status'] in ('running', 'stopping') and time.monotonic() < deadline:
            time.sleep(.02)
        return self.manager.state()

    def test_progress_and_completion_from_real_child(self):
        (self.root / 'vpn_check.py').write_text("import json\nprint(json.dumps({'event':'progress','data':{'probes':{}},'progress':50,'message':'检测中'}),flush=True)\nprint(json.dumps({'event':'complete','data':{'probes':{}},'report_id':'20260918-160000-123456'}),flush=True)\n")
        self.manager.start('quick')
        state = self.wait_finished()
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['progress'], 100)
        self.assertEqual(state['report_id'], '20260918-160000-123456')

    def test_stop_prevents_overlap_and_can_restart(self):
        (self.root / 'vpn_check.py').write_text('import time\ntime.sleep(10)\n')
        self.manager.start('quick')
        with self.assertRaises(web.BusyError):
            self.manager.start('quick')
        self.manager.stop()
        self.assertEqual(self.wait_finished()['status'], 'cancelled')
        self.manager.start('stability')
        self.assertEqual(self.manager.state()['status'], 'running')

    def test_incomplete_child_is_failure_not_success(self):
        (self.root / 'vpn_check.py').write_text('print("no complete event")\n')
        self.manager.start('quick')
        self.assertEqual(self.wait_finished()['status'], 'failed')

    def test_report_paths_cannot_escape_and_bad_history_is_skipped(self):
        with self.assertRaises(ValueError):
            self.manager.report('../../README')
        folder = self.root / 'reports' / '20260918-160000-123456'
        folder.mkdir(parents=True)
        (folder / 'report.json').write_text('{bad json')
        self.assertEqual(self.manager.history(), [])

    def test_http_rejects_foreign_origins_and_missing_token(self):
        server = web.make_server(0, self.manager)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        opener = build_opener(ProxyHandler({}))
        base = f'http://127.0.0.1:{port}'
        try:
            with opener.open(base + '/api/state') as response:
                state = json.load(response)
            self.assertIn('token', state)
            for headers in ({'Origin':'http://evil.example'}, {'Host':'evil.example'}, {}):
                headers = {'Content-Type':'application/json', **headers}
                request = Request(base + '/api/start', b'{"mode":"quick"}', headers, method='POST')
                with self.assertRaises(HTTPError) as caught:
                    opener.open(request)
                self.assertEqual(caught.exception.code, 403)
            request = Request(base + '/api/start', b'{"mode":"invalid"}',
                {'Content-Type':'application/json','X-VPN-Token':state['token']}, method='POST')
            with self.assertRaises(HTTPError) as caught:
                opener.open(request)
            self.assertEqual(caught.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()

if __name__ == '__main__':
    unittest.main()
