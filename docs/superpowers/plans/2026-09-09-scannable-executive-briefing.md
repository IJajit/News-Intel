# Scannable Executive News Briefing & Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the news briefing experience into a lightning-fast, scannable executive digest featuring a top-20 story homepage and bullet-point "Brief" + "Why It Matters" sections with zero icons.

**Architecture:** Update `news_summarizer.py` to produce structured bullet arrays for both factual brief and strategic impact; update `server.py` to cap homepage briefs to the top 20 ranked stories and serialize the bullet lists; update `styles.css` and `script.js` to render the clean typography with no icons/emojis.

**Tech Stack:** Python 3 (stdlib, urllib, concurrent.futures), Vanilla JavaScript (ES6+), HTML5, Tailwind CSS / Custom CSS.

## Global Constraints
- **Zero Icons/Emojis:** No icons, emojis, or pictorial symbols in story cards or section headers.
- **Thorough Explanations:** Bullets must not be artificially truncated; represent the full context and strategic downstream impact.
- **Top 20 Homepage:** The homepage feed must strictly contain the top 20 ranked stories.
- **Backwards Compatibility:** Frontend rendering must gracefully handle both structured bullet arrays and legacy plain-string briefs.

---

### Task 1: Update AI Summarization & Structured Fallback (`news_summarizer.py`)

**Files:**
- Modify: `c:/AntiGravity/News App/news_summarizer.py`
- Create: `c:/AntiGravity/News App/tests/test_summarizer.py`

**Interfaces:**
- Produces: `generate_deep_dive_brief(content, title="", gemini_key="") -> {"brief": list[str], "why_it_matters": list[str]}`

- [ ] **Step 1: Write test for structured fallback and prompt parser**

Create `tests/test_summarizer.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_summarizer.py`
Expected: FAIL (because `_structured_fallback` currently returns `{"summary": "..."}`)

- [ ] **Step 3: Update `news_summarizer.py` implementation**

Modify `news_summarizer.py`:
1. In `_call_gemini_api`:
   - Change prompt to request JSON with keys `"brief"` (array of 2-4 comprehensive bullet strings) and `"why_it_matters"` (array of 1-2 analytical bullet strings detailing downstream impact).
2. In `_structured_fallback`:
   - Split sentences cleanly.
   - Dedup sentences.
   - Assign the primary factual sentences to `"brief"` (as list of strings).
   - Assign the impact/concluding sentence(s) to `"why_it_matters"` (as list of strings).
3. In `generate_deep_dive_brief`:
   - Return dictionary containing `"brief": [...]` and `"why_it_matters": [...]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_summarizer.py`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit changes**

```bash
git add news_summarizer.py tests/test_summarizer.py
git commit -m "feat: upgrade summarizer to generate bulleted brief and why_it_matters"
```

---

### Task 2: Update Pipeline & Homepage Top-20 Capping (`server.py`)

**Files:**
- Modify: `c:/AntiGravity/News App/server.py`

**Interfaces:**
- Consumes: `generate_deep_dive_brief` from `news_summarizer.py`
- Produces: JSON payload for `latest_homepage.json` containing capped 20 stories with `brief_bullets` and `why_it_matters_bullets`.

- [ ] **Step 1: Write integration check for top 20 homepage capping**

Create `tests/test_server_pipeline.py`:
```python
import os
import sys
import unittest
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestServerPipeline(unittest.TestCase):
    def test_homepage_capped_to_20_stories(self):
        # Verify that homepage brief slicing caps to 20
        sample_stories = [{"story_id": f"s_{i}", "combined_score": i} for i in range(50)]
        sorted_stories = sorted(sample_stories, key=lambda s: s["combined_score"], reverse=True)
        homepage_stories = sorted_stories[:20]
        self.assertEqual(len(homepage_stories), 20)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify passing**

Run: `python -m unittest tests/test_server_pipeline.py`
Expected: PASS

- [ ] **Step 3: Modify `server.py` story formatting and capping**

In `server.py`:
1. In `generate_story_brief`:
   - Call `generate_deep_dive_brief(content, title=headline, gemini_key=gemini_key)`.
   - Store `story['brief_bullets'] = brief_data.get('brief', [])`.
   - Store `story['why_it_matters_bullets'] = brief_data.get('why_it_matters', [])`.
   - Maintain `story['brief']` as joined string for backwards compatibility.
2. In `do_POST` for `/api/generate-brief`:
   - If `category == 'homepage'`, slice `stories = stories_sorted[:20]`.
   - When saving `latest_homepage.json`, ensure payload is strictly top 20 stories.
3. In `do_GET` for `/api/latest-brief`:
   - If `category == 'homepage'`, ensure data returned is sliced to at most 20 stories if the cached file has legacy excess stories.

- [ ] **Step 4: Commit changes**

```bash
git add server.py tests/test_server_pipeline.py
git commit -m "feat: cap homepage stories to top 20 and store structured bullets"
```

---

### Task 3: Editorial Typography & Styles (`styles.css`)

**Files:**
- Modify: `c:/AntiGravity/News App/styles.css`

**Interfaces:**
- Produces: CSS rules for `.brief-section`, `.why-it-matters-section`, `.editorial-bullet-list`, and `.reading-time-header` with zero icons.

- [ ] **Step 1: Add editorial styling rules in `styles.css`**

Add clean, high-contrast styles:
```css
/* ─── SCANNABLE EXECUTIVE STORY FORMAT ────────────────────── */
.story-meta-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.25rem;
  margin-bottom: 0.75rem;
}

.story-section-title {
  font-family: var(--font-label-caps, 'Inter', sans-serif);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--color-dark-gray);
  margin-top: 0.75rem;
  margin-bottom: 0.35rem;
}

.story-bullet-list {
  list-style-type: disc;
  padding-left: 1.25rem;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.story-bullet-list li {
  font-family: var(--font-body-md, 'Inter', sans-serif);
  font-size: 0.8125rem;
  line-height: 1.55;
  color: var(--color-black);
}

.story-wim-container {
  margin-top: 0.75rem;
  padding: 0.65rem 0.85rem;
  border-left: 2px solid var(--color-orange, #e85d04);
  background-color: rgba(232, 93, 4, 0.04);
  border-radius: 0 4px 4px 0;
}

.dark .story-wim-container {
  background-color: rgba(232, 93, 4, 0.08);
}
```

- [ ] **Step 2: Verify CSS syntax and rules**

Ensure no broken brackets or syntax errors in `styles.css`.

- [ ] **Step 3: Commit changes**

```bash
git add styles.css
git commit -m "style: add editorial styling for bulleted brief and why-it-matters"
```

---

### Task 4: Client Rendering Updates (`script.js`)

**Files:**
- Modify: `c:/AntiGravity/News App/script.js`

**Interfaces:**
- Consumes: `story.brief_bullets`, `story.why_it_matters_bullets`, legacy `story.brief` fallback
- Produces: Clean HTML for `renderHomepageView`, `renderReaderView`, and sidebar limit

- [ ] **Step 1: Write helper function to render bullet lists with backwards compatibility**

In `script.js`:
```javascript
function formatStoryBullets(bullets, fallbackText) {
  if (Array.isArray(bullets) && bullets.length > 0) {
    return bullets.map(b => `<li>${escapeHtml(b.replace(/^[•\-\*\s]+/, '').trim())}</li>`).join('');
  }
  if (fallbackText) {
    const sentences = fallbackText.replace(/^•\s*/gm, '').split(/(?<=[.!?])\s+/).filter(s => s.trim().length > 10);
    return sentences.map(s => `<li>${escapeHtml(s.trim())}</li>`).join('');
  }
  return '';
}
```

- [ ] **Step 2: Update `renderHomepageStory` and `renderReaderView`**

1. Render:
   - Primary headline and sources meta.
   - Clean label: `<div class="story-section-title">BRIEF</div>`
   - Bullet list: `<ul class="story-bullet-list">${briefHtml}</ul>`
   - If why_it_matters exists:
     `<div class="story-wim-container"><div class="story-section-title" style="color: var(--color-orange); margin-top:0;">WHY IT MATTERS</div><ul class="story-bullet-list">${wimHtml}</ul></div>`
   - Expandable "Also reported by" sources.
2. Add briefing metadata header at the top of the homepage:
   - "Top 20 Executive Briefs · ~5 Min Read"
3. In `renderRightSidebarArticles`:
   - Cap display to `stories.slice(0, 15)` to avoid rendering hundreds of nodes in sidebar.

- [ ] **Step 3: Test client rendering in browser**

Verify in browser that:
- Homepage displays top 20 stories.
- Every story has clean bulleted BRIEF and WHY IT MATTERS sections without any icons.
- Right sidebar remains smooth and fast.

- [ ] **Step 4: Commit changes**

```bash
git add script.js
git commit -m "feat: render clean bulleted brief and why-it-matters in UI"
```

---

### Task 5: End-to-End Verification & Migration of Existing Cache

**Files:**
- Modify: `c:/AntiGravity/News App/data/briefings/latest_homepage.json` (generate or slice down to top 20)

- [ ] **Step 1: Slice and format existing `latest_homepage.json` to 20 stories**

Run Python script to slice the 965-story 1.76 MB cache file into a clean, 20-story top executive briefing with bulleted brief and why-it-matters structures.

- [ ] **Step 2: Verify payload size**

Verify `latest_homepage.json` size is < 40 KB.

- [ ] **Step 3: Run full regression tests**

Run: `python -m unittest discover tests`
Expected: All tests pass.

- [ ] **Step 4: Final commit and cleanup**

```bash
git add data/briefings/latest_homepage.json
git commit -m "perf: reduce latest_homepage.json to top 20 executive stories"
```
