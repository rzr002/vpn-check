from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_server as web

class DemoTests(unittest.TestCase):
    def test_demo_is_explicit_and_cannot_start_measurements(self):
        self.assertTrue(hasattr(web, 'DemoManager'), 'A no-network demo is required for public previews')
        if not hasattr(web, 'DemoManager'):
            return
        manager = web.DemoManager()
        state = manager.state()
        self.assertTrue(state['demo'])
        self.assertTrue(state['data']['synthetic'])
        self.assertIn('演示', state['message'])
        self.assertEqual(manager.network()['clash']['mode'], 'global')
        with self.assertRaises(ValueError):
            manager.start('quick')
        self.assertEqual(manager.history(), [])
        self.assertNotIn('reports', str(state['report_id']))

if __name__ == '__main__':
    unittest.main()
