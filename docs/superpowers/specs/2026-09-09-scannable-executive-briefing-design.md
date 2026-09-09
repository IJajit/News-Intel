# Design Spec: Scannable Executive News Briefing & Performance Optimization

**Date:** 2026-09-09  
**Status:** Validated & Approved  
**Target:** News App (`c:\AntiGravity\News App`)

---

## 1. Problem Statement & Motivation

1. **Slow Initial Page Load:**
   - The homepage loads a single unpaginated JSON file (`latest_homepage.json`) containing **965 stories** totaling **1.76 MB**.
   - The client-side DOM freezes during startup while creating and inserting thousands of DOM nodes across the reader, articles feed, and right sidebar.
   - Synchronous fallback generation on cache miss can block the backend for 30+ seconds.

2. **Reading Fatigue ("Long Read"):**
   - Every story currently renders dense, multi-sentence narrative paragraphs with identical visual weight.
   - There is no visual hierarchy, no bulleted structure, and no executive "Why It Matters" analytical takeaway.
   - Readers face a wall of text without a clear sense of the whole picture or what is truly important.

---

## 2. Goals & Success Criteria

1. **Instant Homepage Performance:**
   - Cap the homepage feed to the **top 20 most important stories** (ranked by multi-source verification and urgency scoring).
   - Reduce initial JSON payload from **1.76 MB down to < 40 KB** (~98% reduction).
   - Ensure initial DOM paint completes in under 150ms without main-thread blocking.

2. **Scannable & Thorough Editorial Layout:**
   - **Zero icons or emojis:** Strictly clean, high-contrast typography adhering to an executive briefing aesthetic.
   - **Bullet-Point Brief:** 2 to 4 detailed, fact-first bullet points that fully represent the core events, figures, and statements without artificial truncation.
   - **Self-Contained "Why It Matters":** 1 to 2 comprehensive bullet points explaining the strategic impact, downstream implications, and broader significance.
   - **Consistent Experience Across Views:** Both Homepage and Category views follow the identical Brief + Why It Matters bullet format.
   - **Dedicated Category Loading:** Category tabs display news for that category on demand, keeping memory and rendering lightweight.

---

## 3. Visual & Component Architecture

### 3.1 Story Card Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Global Semiconductor Alliance Finalizes Cross-Border Pact       │
│ Reuters · +3 other sources · 2h ago                             │
│                                                                 │
│ BRIEF                                                           │
│ • Key semiconductor manufacturers and European trade officials  │
│   concluded negotiations in Brussels to establish a joint       │
│   contingency reserve for critical minerals and silicon wafers. │
│ • The agreement eliminates tariff barriers on advanced chip     │
│   tooling exports between signatory nations starting next       │
│   quarter.                                                      │
│ • Participating nations pledged $12B in shared infrastructure   │
│   subsidies to accelerate local packaging and testing plants.   │
│                                                                 │
│ WHY IT MATTERS                                                  │
│ • Mitigates critical vulnerability points across global auto    │
│   and computing supply chains by decentralizing fabrication.    │
│ • Establishes legally binding supply quotas during shortages,   │
│   preventing the unilateral export bans seen during previous    │
│   crises.                                                       │
│                                                                 │
│ Also reported by ▶                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Typography & Styling Contract
- **Headline:** `font-headline-md font-semibold text-base leading-snug`
- **Section Headers:** Clean text labels (`BRIEF`, `WHY IT MATTERS`) in uppercase small caps (`font-label-caps text-[11px] tracking-wider font-bold`), with zero emojis or icon prefixes.
- **Bullets:** Unordered list with clean bullet markers (`list-disc pl-5 space-y-1.5`), line-height set for comfortable executive reading (`leading-relaxed text-sm`).
- **Why It Matters Container:** Subtle boundary separation (e.g. left border line or gentle surface container background) to give visual distinction without visual clutter.

---

## 4. Backend & AI Summarization Pipeline

### 4.1 Schema Definition
Every story object in the generated briefings will contain:
```json
{
  "story_id": "cluster_123",
  "category": "Technology",
  "primary_headline": "...",
  "primary_source": { ... },
  "sources": [ ... ],
  "source_count": 4,
  "brief_bullets": [
    "Fact-first bullet 1 covering context, primary actors, and core action...",
    "Fact-first bullet 2 covering specific figures, policy changes, and details...",
    "Fact-first bullet 3 covering additional key reactions or developments..."
  ],
  "why_it_matters_bullets": [
    "Full analytical explanation of the strategic significance and downstream consequences...",
    "Broader industry/geopolitical implications and what to watch next..."
  ]
}
```

### 4.2 Summarizer Prompting (`news_summarizer.py`)
- The Gemini prompt will instruct the model to produce:
  - `brief`: 3 to 4 comprehensive, non-truncated bullet points.
  - `why_it_matters`: 1 to 2 self-contained, analytical bullet points detailing why the story is significant.
- Response format enforced as structured JSON.

### 4.3 Deterministic Fallback Logic (`_structured_fallback`)
- When Gemini API is unavailable or rate-limited:
  - Extract and clean coherent sentences from the full article text and cluster sources.
  - Distribute descriptive and factual sentences into the `brief_bullets`.
  - Synthesize strategic/impact sentences into `why_it_matters_bullets`.
  - Maintain identical structured output schema so client rendering never degrades or changes format.

### 4.4 Feed & Payload Slicing (`server.py`)
- In `server.py`:
  - When saving or serving `latest_homepage.json`, filter and rank stories, outputting the **top 20 stories**.
  - Provide individual category briefs (e.g. `latest_technology.json`, `latest_geopolitics.json`) capped at a sensible batch (e.g. 20-30 stories per category) to prevent runaway payload sizes.

---

## 5. Frontend Implementation (`script.js` & `index.html`)

1. **`renderHomepageView`:**
   - Renders the top 20 stories cleanly.
   - Includes reading time estimate at top (e.g. "Top 20 Executive Stories · 5 Min Read").
   - Renders each story with the new `brief_bullets` and `why_it_matters_bullets`.

2. **`renderReaderView` & Category Navigation:**
   - When a user selects a category (e.g. Technology), loads the category-specific brief.
   - Renders stories using the exact same bullet-point Brief + Why It Matters format.

3. **Performance Safeguards:**
   - Guard against missing fields with backwards-compatible parsing (if a cached item only has old plain string `brief`, gracefully convert into bullets).
   - Sidebar article list caps to the top 15 most recent headlines instead of looping through hundreds.

---

## 6. Verification Plan

### 6.1 Automated / Scripted Checks
- Test `news_summarizer.py` with mock news articles to verify valid JSON generation with `brief_bullets` and `why_it_matters_bullets`.
- Verify fallback mode produces clean bullet lists without external API dependency.
- Validate `latest_homepage.json` payload size is under 50 KB.

### 6.2 Manual UI Verification
- Start local server (`python server.py 8000`).
- Verify homepage loads instantly (<200ms) with 20 top stories.
- Verify typography has zero emojis or icons.
- Verify "Brief" and "Why It Matters" sections are thorough, informative, and formatted in clean bullet points.
- Switch between categories (Technology, Geopolitics, Finance) and verify seamless category loading.
