import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'vpn_check.py'
spec = importlib.util.spec_from_file_location('vpn_check', PATH) if PATH.exists() else None
vc = importlib.util.module_from_spec(spec) if spec else None
if spec:
    spec.loader.exec_module(vc)

class MetricsTests(unittest.TestCase):
    def test_tool_exists(self):
        self.assertIsNotNone(vc, 'VPN check tool is not implemented yet')

    @unittest.skipIf(vc is None, 'tool not implemented')
    def test_failures_and_http_rejections_are_separate(self):
        rows = [vc.parse_probe('200|0.01|0.03|0.1|0.2|0.3|100|333', 0),
                vc.parse_probe('403|0.01|0.03|0.1|0.2|0.3|100|333', 0),
                vc.parse_probe('000|0.01|0|0|0|8|0|0', 28)]
        s = vc.summarize(rows)
        self.assertEqual(s['samples'], 3)
        self.assertEqual(s['transport_failures'], 1)
        self.assertEqual(s['http_rejections'], 1)
        self.assertEqual(s['successes'], 1)
        self.assertEqual(s['median_ttfb_ms'], 200)
        self.assertNotIn('packet_loss', s)

    @unittest.skipIf(vc is None, 'tool not implemented')
    def test_no_success_is_not_zero_latency(self):
        s = vc.summarize([vc.parse_probe('', 7)])
        self.assertIsNone(s['median_ttfb_ms'])
        self.assertIsNone(s['variation_ms'])

    @unittest.skipIf(vc is None, 'tool not implemented')
    def test_variation_only_between_adjacent_successes(self):
        rows = [vc.parse_probe(f'200|0|0|0|{t}|{t}|0|0', 0) for t in [0.1, 0.3, 0.4]]
        self.assertEqual(vc.summarize(rows)['variation_ms'], 150)
        rows.insert(1, vc.parse_probe('', 28))
        self.assertEqual(vc.summarize(rows)['variation_ms'], 100)

    @unittest.skipIf(vc is None, 'tool not implemented')
    def test_speed_requires_complete_expected_body(self):
        row = vc.parse_probe('200|0|0.01|0.1|0.2|1|1048576|1048576', 0)
        self.assertAlmostEqual(vc.download_mbps(row, 1048576), 8.388608)
        self.assertIsNone(vc.download_mbps(row, 2 * 1048576))
        row['exit_code'] = 28
        self.assertIsNone(vc.download_mbps(row, 1048576))

    @unittest.skipIf(vc is None, 'tool not implemented')
    def test_proxy_explicitly_overrides_no_proxy(self):
        args = vc.curl_args('https://example.org/', 'http://127.0.0.1:7897', 8)
        self.assertEqual(args[args.index('--noproxy') + 1], '')
        self.assertIn('--proxy', args)
        self.assertEqual(args[1], '-q')
        direct = vc.curl_args('https://example.org/', None, 8)
        self.assertEqual(direct[direct.index('--noproxy') + 1], '*')

if __name__ == '__main__':
    unittest.main()
