import os
import unittest
import re

class TestLatestUI(unittest.TestCase):
    def test_latest_button_is_before_home_button(self):
        html_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        latest_match = re.search(r'id=["\']tabLatestBtn["\']', content)
        home_match = re.search(r'id=["\']tabHomepageBtn["\']', content)

        self.assertIsNotNone(latest_match, "tabLatestBtn not found in index.html")
        self.assertIsNotNone(home_match, "tabHomepageBtn not found in index.html")
        self.assertLess(latest_match.start(), home_match.start(), "tabLatestBtn MUST be placed before tabHomepageBtn")

    def test_view_latest_container_exists(self):
        html_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('id="viewLatest"', content)
        self.assertIn('id="latestContent"', content)

    def test_latest_button_is_default_active(self):
        html_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        match = re.search(r'id=["\']tabLatestBtn["\'][^>]*class=["\']([^"\']+)["\']', content)
        self.assertIsNotNone(match)
        self.assertIn('active', match.group(1), "tabLatestBtn must have 'active' class by default")

if __name__ == '__main__':
    unittest.main()
