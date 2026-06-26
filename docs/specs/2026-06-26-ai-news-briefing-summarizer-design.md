# Executive Briefing Summarizer — AI News Ranking & Summarization

**Date:** 2026-06-26
**Project:** News App (`C:\AntiGravity\News App`)

## Problem

The current briefing ranks articles by recency only. The top headline and top 3 stories are simply the first N articles from the feed — not the most globally significant ones. Descriptions use raw RSS content rather than concise AI-generated briefs, and the AI summarization is gated behind a Gemini API key.

## Goals

1. **Headline** — The single most globally urgent, important story right now
2. **Top 3 Stories** — The 3 most essential stories, determined by cross-source coverage density
3. **AI-generated briefs (2-4 lines)** — For every headline/story, without requiring any API key

## Approach

### Story Clustering & Importance Ranking

A pipeline that runs after fetching articles, before formatting the briefing:

**Normalization:**
- Lowercase titles, strip prefixes ("BREAKING:", "EXCLUSIVE:", etc.), remove punctuation
- Tokenize into word sets, remove common stopwords

**Clustering via Jaccard similarity:**
- Compare each article's title token set against every other article
- If Jaccard similarity > threshold (0.3), group into a cluster
- Each cluster tracks: source IDs, earliest/most recent timestamp, combined title keywords, total article count

**Scoring each cluster:**
- **Source diversity (weight: 0.5):** Number of unique news sources covering the story
- **Total article count (weight: 0.3):** More articles in cluster = more coverage
- **Urgency signal (weight: 0.2):** Keywords like "breaking", "crisis", "emergency", "confirmed", "developing", "death", "attack", "war", "crash", "disaster"

**Ranking output:**
- Highest-scoring cluster → **The Headline**
- Next 3 highest-scoring clusters/individual articles → **Today's Top Stories**
- Remaining → **Category Breakdown** and **Quick Hits**

Single articles that didn't cluster still participate but only beat multi-source clusters if they have very strong urgency signals.

### AI-Generated Briefs via Hugging Face

**Summarization flow:**
1. Take article `content` (cleaned RSS description)
2. If content < 50 words, use as-is (already concise)
3. Otherwise, call Hugging Face Inference API (`facebook/bart-large-cnn`)
4. Request 2-4 sentence summary

**Fallback chain (no API key required):**
1. Hugging Face Inference API (anonymous free tier)
2. If rate-limited/fails → extractive summary (first 2-3 coherent sentences)
3. If content too short → original content
4. If Gemini key present in header → use Gemini instead (higher quality)

**Caching:** Per-article URL summaries cached in-memory during a single briefing run.

**Config:**
- `.env` — optional `HF_API_TOKEN` for higher HF rate limits
- Existing `GEMINI_API_KEY` — if present, overrides HF for summarization

### Code Changes

**`server.py`:**
- Add `cluster_articles(articles)` — returns ranked clusters
- Add `summarize_article(content)` — HF + fallback
- Add `generate_brief_text(articles, category, formatted_date)` — orchestrates clustering + summarization
- Modify `compile_mock_briefing` → replaced by new pipeline (both the "no key" and "with key" paths produce the same structured output)
- Keep Gemini path as optional upgrade in `call_gemini`

**`script.js` / `index.html`:** Minimal
- API response will include `brief` field per article
- INTEL READER renderer already handles the markdown format — brief content flows into existing list item structure
- No layout or styling changes needed

**`styles.css`:** No changes

**`.env`:**
- Add optional `HF_API_TOKEN=`

### Error Handling

- **No articles in 12hr window:** Show "No critical stories" state, list any available articles
- **HF API rate-limited:** Per-article fallback to extractive summary
- **Single-source story:** Still scored individually, appears in Category Breakdown
- **HF API unreachable:** Full graceful degradation to extractive mode
- **Empty RSS content:** Informative fallback text

### Non-Goals

- No UI redesign (look and feel stays the same)
- No new frontend dependencies
- No database or persistence beyond the existing JSON cache
- No user accounts or personalization
