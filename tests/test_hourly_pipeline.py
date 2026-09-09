import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server import filter_articles_by_hours

class TestHourlyPipeline(unittest.TestCase):
    def test_filter_articles_within_one_hour(self):
        now = datetime.now(timezone.utc)
        articles = [
            {'title': 'Breaking 20m ago', 'published_at': (now - timedelta(minutes=20)).isoformat()},
            {'title': 'Breaking 55m ago', 'published_at': (now - timedelta(minutes=55)).isoformat()},
            {'title': 'Old 75m ago', 'published_at': (now - timedelta(minutes=75)).isoformat()},
            {'title': 'Yesterday news', 'published_at': (now - timedelta(hours=24)).isoformat()},
        ]
        filtered = filter_articles_by_hours(articles, max_hours=1.0, current_time=now)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]['title'], 'Breaking 20m ago')
        self.assertEqual(filtered[1]['title'], 'Breaking 55m ago')

if __name__ == '__main__':
    unittest.main()
