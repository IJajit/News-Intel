import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from news_summarizer import _structured_fallback, _clean_rss_artifacts

class TestNewsSummarizer(unittest.TestCase):
    def test_structured_fallback_generates_bullets(self):
        sample_text = (
            "European regulators reached a landmark agreement on semiconductor subsidies on Wednesday. "
            "The pact allocates 12 billion euros to domestic fabrication plants over the next five years. "
            "Industry leaders praised the move as essential for securing automotive supply chains. "
            "The strategic move is expected to significantly reduce European reliance on overseas chip foundries."
        )
        result = _structured_fallback(sample_text, title="EU Chip Pact")
        self.assertIn("brief", result)
        self.assertIn("why_it_matters", result)
        self.assertIsInstance(result["brief"], list)
        self.assertIsInstance(result["why_it_matters"], list)
        self.assertGreaterEqual(len(result["brief"]), 1)
        self.assertGreaterEqual(len(result["why_it_matters"]), 1)

    def test_clean_rss_artifacts_removes_bullets_and_branding(self):
        text = "Reuters • Breaking: Technology update. Continue reading"
        cleaned = _clean_rss_artifacts(text)
        self.assertNotIn("•", cleaned)
        self.assertNotIn("Continue reading", cleaned)

if __name__ == '__main__':
    unittest.main()
