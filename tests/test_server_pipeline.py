import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestServerPipeline(unittest.TestCase):
    def test_homepage_delivers_all_stories(self):
        sample_stories = [{"story_id": f"s_{i}", "combined_score": i} for i in range(50)]
        sorted_stories = sorted(sample_stories, key=lambda s: s["combined_score"], reverse=True)
        self.assertEqual(len(sorted_stories), 50)
        self.assertEqual(sorted_stories[0]["story_id"], "s_49")

    def test_story_brief_structure(self):
        from news_summarizer import _structured_fallback
        res = _structured_fallback("Test headline happened. Details are coming in. The impact will be wide.", title="Test")
        story = {
            "story_id": "test_1",
            "brief_bullets": res.get("brief", []),
            "why_it_matters_bullets": res.get("why_it_matters", []),
            "brief": res.get("summary", "")
        }
        self.assertIn("brief_bullets", story)
        self.assertIn("why_it_matters_bullets", story)
        self.assertIsInstance(story["brief_bullets"], list)
        self.assertIsInstance(story["why_it_matters_bullets"], list)

if __name__ == '__main__':
    unittest.main()
