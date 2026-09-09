import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server import format_hourly_push_payload

class TestCronHourly(unittest.TestCase):
    def test_format_push_payload_with_stories(self):
        stories = [
            {"primary_headline": "Global Leaders Agree on Climate Framework", "category": "geopolitics"},
            {"primary_headline": "New Battery Tech Doubles Electric Vehicle Range", "category": "technology"},
            {"primary_headline": "Central Banks Announce Joint Currency Stability Plan", "category": "finance"}
        ]
        payload = format_hourly_push_payload(stories)
        self.assertIn("News Intel · Past Hour Update", payload["title"])
        self.assertIn("Global Leaders Agree on Climate Framework", payload["body"])
        self.assertIn("+ 2 more in", payload["body"])
        self.assertEqual(payload["url"], "/?tab=latest")

    def test_format_push_payload_empty_stories(self):
        payload = format_hourly_push_payload([])
        self.assertIn("News Intel · Hourly Update", payload["title"])
        self.assertIn("No major breaking stories", payload["body"])
        self.assertEqual(payload["url"], "/?tab=latest")

if __name__ == '__main__':
    unittest.main()
