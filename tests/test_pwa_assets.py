import os
import unittest
import json

class TestPwaAssets(unittest.TestCase):
    def test_manifest_is_valid_json(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'manifest.json')
        self.assertTrue(os.path.exists(path), "manifest.json does not exist")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data.get("name"), "News Intel")
        self.assertEqual(data.get("display"), "standalone")
        self.assertEqual(data.get("theme_color"), "#1e1e1e")

    def test_service_worker_has_push_and_click_listeners(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'sw.js')
        self.assertTrue(os.path.exists(path), "sw.js does not exist")
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("addEventListener('push'", content)
        self.assertIn("addEventListener('notificationclick'", content)
        self.assertIn("tab=latest", content)

    def test_header_has_notification_web_icon(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('id="notifToggleBtn"', content)
        self.assertIn('id="notifIcon"', content)
        self.assertIn('notifications', content)

if __name__ == '__main__':
    unittest.main()
