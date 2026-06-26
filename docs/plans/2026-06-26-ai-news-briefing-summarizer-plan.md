# AI News Ranking & Summarization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace flat recency-based article ranking with cross-source clustering + importance scoring, and add zero-dependency AI-generated briefs via Hugging Face Inference API.

**Architecture:** Two new modules (`news_clustering.py`, `news_summarizer.py`) encapsulate pure logic. `server.py` imports them, replaces `compile_mock_briefing()`, and keeps Gemini as optional upgrade. Frontend is minimally affected.

**Tech Stack:** Python 3.14 stdlib only (urllib, json, re, math), Hugging Face Inference API (no SDK needed — plain HTTP POST).

## Global Constraints

- Zero new pip/package dependencies (stdlib only for clustering; HF accessed via urllib)
- No API key required for basic functionality
- All HTTP calls use existing `ssl._create_unverified_context()` pattern
- Fallback chain must never hard-crash the briefing generation
- Brief field per article is 2-4 sentences maximum

---

### Task 1: `news_clustering.py` — Story Clustering & Ranking Module

**Files:**
- Create: `C:\AntiGravity\News App\news_clustering.py`
- Test: Inline verification via `__main__` block (no test framework installed)

**Interfaces:**
- Produces:
  - `normalize_title(title: str) -> tuple[set[str], str]` — returns (token_set, cleaned_title)
  - `jaccard_similarity(a: set, b: set) -> float` — Jaccard index
  - `cluster_articles(articles: list[dict]) -> list[dict]` — returns list of cluster dicts:
    ```python
    {
      "articles": [article_dict, ...],
      "sources": set[str],
      "source_count": int,
      "total_count": int,
      "max_timestamp": str,
      "urgency_score": float,
      "combined_score": float,
      "representative_title": str
    }
    ```
  - `rank_clusters(clusters: list[dict]) -> list[dict]` — returns sorted clusters by combined_score desc

- [ ] **Step 1: Write `normalize_title()`**

```python
import re

STOPWORDS = {'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for',
             'of', 'is', 'it', 'by', 'with', 'from', 'as', 'be', 'has',
             'are', 'was', 'were', 'been', 'its', 'their', 'that', 'this',
             'not', 'no', 'but', 'if', 'so', 'up', 'do', 'just', 'out'}

URGENCY_KEYWORDS = ['breaking', 'crisis', 'emergency', 'confirmed', 'developing',
                    'death', 'deaths', 'attack', 'war', 'crash', 'disaster',
                    'killed', 'injured', 'collapse', 'warning', 'urgent',
                    'explosion', 'strike', 'military', 'nuclear', 'evacuate',
                    'evacuation', 'catastrophe', 'fatal', 'deadly', 'critical']

def normalize_title(title):
    if not title:
        return (set(), "")
    title = title.lower()
    title = re.sub(r'^(breaking|exclusive|urgent|update|developing)\s*[:\-–—]\s*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'[^a-z0-9\s]', '', title)
    tokens = title.split()
    tokens = [t for t in tokens if t not in STOPWORDS]
    tokens = [t for t in tokens if len(t) > 1]
    return (set(tokens), title.strip())
```

- [ ] **Step 2: Write `jaccard_similarity()`**

```python
def jaccard_similarity(a, b):
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return intersection / union
```

- [ ] **Step 3: Write `cluster_articles()`**

```python
import math
from datetime import datetime, timezone

def _extract_source_id(article):
    return article.get('sourceId', '')

def _calc_urgency_score(title_lower, content_lower):
    text = f"{title_lower} {content_lower}"
    score = 0.0
    for kw in URGENCY_KEYWORDS:
        if kw in text:
            score += 0.15
    return min(score, 1.0)

def cluster_articles(articles):
    if not articles:
        return []

    normalized = []
    for art in articles:
        tokens, cleaned = normalize_title(art.get('title', ''))
        normalized.append((art, tokens, cleaned))

    clusters = []
    assigned = [False] * len(normalized)

    for i in range(len(normalized)):
        if assigned[i]:
            continue
        cluster_articles = [normalized[i][0]]
        assigned[i] = True

        for j in range(i + 1, len(normalized)):
            if assigned[j]:
                continue
            similarity = jaccard_similarity(normalized[i][1], normalized[j][1])
            if similarity >= 0.3:
                cluster_articles.append(normalized[j][0])
                assigned[j] = True

        clusters.append(cluster_articles)

    result = []
    for group in clusters:
        sources = set()
        all_titles = []
        latest = None
        total_content = ""

        for art in group:
            sid = _extract_source_id(art)
            sources.add(sid)
            all_titles.append(art.get('title', ''))
            total_content += " " + (art.get('content', '') or '')

            pub = art.get('pubDate', '')
            if pub:
                try:
                    dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
                    if latest is None or dt > latest:
                        latest = dt
                    elif latest.tzinfo is None:
                        latest = latest.replace(tzinfo=timezone.utc)
                    elif dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt > latest:
                        latest = dt
                except Exception:
                    pass

        best_title = max(all_titles, key=len) if all_titles else "Untitled Story"
        urgency = _calc_urgency_score(best_title.lower(), total_content.lower())
        source_count = len(sources)
        total_count = len(group)

        combined = (source_count * 0.5) + (total_count * 0.3) + (urgency * 0.2)

        result.append({
            "articles": group,
            "sources": sources,
            "source_count": source_count,
            "total_count": total_count,
            "max_timestamp": latest.isoformat() if latest else "",
            "urgency_score": round(urgency, 3),
            "combined_score": round(combined, 3),
            "representative_title": best_title
        })

    return result
```

- [ ] **Step 4: Write `rank_clusters()` and module entry point for verification**

```python
def rank_clusters(clusters):
    return sorted(clusters, key=lambda c: c['combined_score'], reverse=True)


if __name__ == "__main__":
    test_articles = [
        {"sourceId": "bbc", "sourceName": "BBC News", "title": "Earthquake hits Japan, tsunami warning issued", "content": "A powerful earthquake struck Japan...", "pubDate": ""},
        {"sourceId": "cnn", "sourceName": "CNN", "title": "Japan earthquake triggers tsunami warning", "content": "A major earthquake in Japan...", "pubDate": ""},
        {"sourceId": "reuters", "sourceName": "Reuters", "title": "Earthquake in Japan: tsunami alert for coastal areas", "content": "An earthquake...", "pubDate": ""},
        {"sourceId": "bbc", "sourceName": "BBC News", "title": "Stock markets rally after Fed announcement", "content": "Markets surged...", "pubDate": ""},
    ]
    clusters = cluster_articles(test_articles)
    ranked = rank_clusters(clusters)
    print(f"Clusters: {len(ranked)}")
    for c in ranked:
        print(f"  Score: {c['combined_score']}, Sources: {c['source_count']}, Title: {c['representative_title'][:50]}")
    print("All checks passed.")
```

- [ ] **Step 5: Run to verify**

Run: `cd C:\AntiGravity\News App; python news_clustering.py`

Expected output: 2 clusters, first with score ~1.0 (3 sources covering earthquake), second with score ~0.3 (1 source, finance story), "All checks passed."

---

### Task 2: `news_summarizer.py` — AI Summarization with Fallback

**Files:**
- Create: `C:\AntiGravity\News App\news_summarizer.py`

**Interfaces:**
- Consumes: `ssl_context` pattern from server.py (unverified SSL)
- Produces:
  - `summarize_content(content: str, title: str, ssl_ctx, hf_token: str = "") -> str` — returns 2-4 sentence summary
  - `_call_hf_inference(text: str, ssl_ctx, hf_token: str = "") -> str` — HTTP POST to Hugging Face
  - `_extractive_fallback(text: str) -> str` — sentence extraction

- [ ] **Step 1: Write `_extractive_fallback()`**

```python
import re

def _extractive_fallback(text):
    if not text:
        return "No details available for this story."
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if not sentences:
        return text[:200] if len(text) > 200 else text
    if len(sentences) <= 3:
        return " ".join(sentences)
    first = sentences[0]
    last = sentences[-1]
    middle_candidates = sentences[1:-1]
    mid = ""
    if middle_candidates:
        mid_idx = len(middle_candidates) // 2
        mid = middle_candidates[mid_idx] if len(middle_candidates[mid_idx]) > 30 else ""
    parts = [p for p in [first, mid, last] if p]
    result = " ".join(parts)
    return result
```

- [ ] **Step 2: Write `_call_hf_inference()`**

```python
import json
import urllib.request

HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

def _call_hf_inference(text, ssl_ctx, hf_token=""):
    if not text or len(text.strip()) < 30:
        return None

    payload = {
        "inputs": text,
        "parameters": {
            "max_length": 150,
            "min_length": 40,
            "do_sample": False
        }
    }
    data = json.dumps(payload).encode('utf-8')

    headers = {'Content-Type': 'application/json'}
    if hf_token:
        headers['Authorization'] = f'Bearer {hf_token}'

    req = urllib.request.Request(
        HF_API_URL,
        data=data,
        headers=headers,
        method='POST'
    )

    kwargs = {'timeout': 15}
    if ssl_ctx:
        kwargs['context'] = ssl_ctx

    try:
        with urllib.request.urlopen(req, **kwargs) as response:
            result = json.loads(response.read().decode('utf-8'))
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('summary_text', '')
            elif isinstance(result, dict) and result.get('summary_text'):
                return result['summary_text']
    except urllib.error.HTTPError as e:
        if e.code == 503:
            print(f"HF model loading (503), falling back")
        elif e.code == 429:
            print(f"HF rate limited (429), falling back")
        else:
            print(f"HF HTTP {e.code}, falling back")
    except Exception as e:
        print(f"HF inference error: {e}")

    return None
```

- [ ] **Step 3: Write `summarize_content()` entry point**

```python
def summarize_content(content, title, ssl_ctx, hf_token=""):
    if not content:
        return f"A developing story from recent news. Check the full article for details."

    clean = re.sub(r'\s+', ' ', content).strip()
    word_count = len(clean.split())

    if word_count < 50:
        return clean

    hf_result = _call_hf_inference(clean, ssl_ctx, hf_token)
    if hf_result:
        hf_result = re.sub(r'\s+', ' ', hf_result).strip()
        sentence_count = len(re.findall(r'[.!?]+', hf_result))
        if 1 <= sentence_count <= 5:
            return hf_result

    fallback = _extractive_fallback(clean)
    return fallback
```

- [ ] **Step 4: Run to verify (no network path)**

Run: `cd C:\AntiGravity\News App; python -c "from news_summarizer import _extractive_fallback; print(_extractive_fallback('The quick brown fox jumps over the lazy dog. It was a sunny day. Everyone was happy. The end.'))"`

Expected: "The quick brown fox jumps over the lazy dog. The end."

---

### Task 3: Integrate Clustering & Summarization into `server.py`

**Files:**
- Modify: `C:\AntiGravity\News App\server.py`

- [ ] **Step 1: Add imports at top of `server.py` (after existing `import concurrent.futures`)**

```python
from news_clustering import cluster_articles, rank_clusters
from news_summarizer import summarize_content
```

- [ ] **Step 2: Add after `load_dotenv()` — load HF token**

```python
HF_API_TOKEN = os.environ.get('HF_API_TOKEN', '')
```

- [ ] **Step 3: Replace `compile_mock_briefing()` with new `generate_briefing_text()`**

Delete the entire `compile_mock_briefing()` function (lines 406-550) and replace with:

```python
def generate_briefing_text(category, articles, grounded_time_str):
    parsed_gdt = parse_iso(grounded_time_str)
    if parsed_gdt:
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        parsed_gdt_ist = parsed_gdt.astimezone(ist_tz)
        formatted_date = parsed_gdt_ist.strftime('%A, %B %d, %Y, %I:%M:%S %p IST')
    else:
        formatted_date = grounded_time_str

    if not articles:
        return f"""Live Briefing for: {formatted_date}

# The Headline

- **No Breaking News:** No stories met the strict 12-hour recency filter for sector: {category.upper()} at this time.

# Today's Top Stories

- **Summarizer Standby**
  The summarizer is scanning all {len(SOURCES)} verified feeds.
  *Why it matters:* Feed updates are continuously monitored.

# Category Breakdown

### SYSTEM STATUS
- Sector {category.upper()} is active but no stories passed the 12-hour filter.

# Quick Hits
- Scan completed. Feeds active."""

    clusters = cluster_articles(articles)
    ranked = rank_clusters(clusters)

    all_ranked_articles = []
    for cluster in ranked:
        for art in cluster["articles"]:
            all_ranked_articles.append(art)

    already_seen_urls = set()
    ranked_deduped = []
    for art in all_ranked_articles:
        key = art.get('link') or art.get('title', '')
        if key not in already_seen_urls:
            already_seen_urls.add(key)
            ranked_deduped.append(art)

    headline_articles = []
    top_story_articles = []

    if ranked:
        headline_cluster = ranked[0]
        headline_articles = headline_cluster["articles"]

        if len(ranked) >= 2:
            for cluster in ranked[1:]:
                if len(top_story_articles) < 3:
                    top_story_articles.extend(cluster["articles"])

    if not top_story_articles and len(ranked_deduped) > 1:
        top_story_articles = ranked_deduped[1:4]

    remaining = [a for a in ranked_deduped if a not in headline_articles[:1] and a not in top_story_articles[:3]]

    def make_article_bullet(art, detail_level="brief"):
        brief = summarize_content(art.get('content', ''), art.get('title', ''), ssl_context, HF_API_TOKEN)
        link = art.get('link', '')
        source = art.get('sourceName', '')
        if detail_level == "brief":
            return f"- **{art.get('title', '')}** ([{source}]({link}))\n  {brief}"
        else:
            return f"- **{art.get('title', '')}** ([{source}]({link}))\n  {brief}\n  *Why it matters:* This story from {source} is significant because it reflects a major development covered by multiple news sources."

    headline_bullets = []
    for a in headline_articles[:4]:
        headline_bullets.append(make_article_bullet(a, "brief"))
    headline_text = "\n\n".join(headline_bullets) if headline_bullets else "- No critical headlines at this moment."

    top_bullets = []
    for a in top_story_articles[:3]:
        top_bullets.append(make_article_bullet(a, "detailed"))
    top_stories_text = "\n\n".join(top_bullets) if top_bullets else "- No top stories identified for this session."

    cat_names = [
        "Business, Markets & Economy", "Technology & Innovation",
        "Geopolitics & World News", "Domestic Politics & Governance",
        "Science, Health & Environment", "Sports",
        "Culture, Entertainment & Arts", "Lifestyle & Society"
    ]

    cat_keywords = {
        "Business, Markets & Economy": ['stock', 'stocks', 'market', 'markets', 'economy', 'economic', 'rate', 'rates', 'inflation', 'gdp', 'm&a', 'merger', 'earnings', 'fed', 'layoff', 'crypto', 'shares', 'gold', 'oil', 'billion', 'deal', 'finance'],
        "Technology & Innovation": ['tech', 'technology', 'ai', 'artificial intelligence', 'openai', 'microsoft', 'google', 'quantum', 'chip', 'nvidia', 'robot', 'cybersecurity', 'software', 'apple', 'meta', 'amazon'],
        "Geopolitics & World News": ['treaty', 'summit', 'diplomacy', 'military', 'defense', 'election', 'border', 'nato', 'conflict', 'war', 'putin', 'biden', 'sanctions'],
        "Domestic Politics & Governance": ['law', 'tax', 'policy', 'vote', 'court', 'parliament', 'government', 'bill', 'supreme court', 'police', 'arrest'],
        "Science, Health & Environment": ['weather', 'rain', 'flood', 'storm', 'cyclone', 'climate', 'fda', 'healthcare', 'nasa', 'science', 'earthquake', 'tsunami', 'virus'],
        "Sports": ['match', 'world cup', 'score', 'cricket', 'football', 'player', 'tennis', 'olympics', 'championship', 'tournament'],
        "Culture, Entertainment & Arts": ['film', 'movie', 'box office', 'award', 'album', 'music', 'gaming'],
        "Lifestyle & Society": ['travel', 'real estate', 'labor', 'union', 'housing', 'crash', 'accident', 'aviation', 'airport']
    }

    cat_grouped = {name: [] for name in cat_names}
    for a in remaining:
        text = (a.get('title', '') + " " + (a.get('content', '') or '')).lower()
        matched = False
        for cat_name in cat_names:
            kws = cat_keywords.get(cat_name, [])
            if contains_word_boundary(text, kws):
                cat_grouped[cat_name].append(a)
                matched = True
                break
        if not matched:
            cat_grouped["Lifestyle & Society"].append(a)

    breakdown_bullets = []
    for cat_name in cat_names:
        arts = cat_grouped[cat_name]
        if arts:
            breakdown_bullets.append(f"### {cat_name}")
            list_items = []
            for a in arts[:8]:
                list_items.append(make_article_bullet(a, "brief"))
            breakdown_bullets.append("\n\n".join(list_items))

    breakdown_text = "\n\n".join(breakdown_bullets) if breakdown_bullets else "### SYSTEM STATUS\n- All sectors active and scanned."

    quick_hits = []
    quick_source = remaining[-6:] if len(remaining) > 6 else remaining
    for a in quick_source:
        link = a.get('link', '')
        source = a.get('sourceName', '')
        quick_hits.append(f"- **{a.get('title', '')}** ([{source}]({link}))")
    quick_hits_text = "\n".join(quick_hits) if quick_hits else "- No additional stories in this cycle."

    return f"""Live Briefing for: {formatted_date}

# The Headline

{headline_text}

# Today's Top Stories

{top_stories_text}

# Category Breakdown

{breakdown_text}

# Quick Hits

{quick_hits_text}"""
```

- [ ] **Step 4: Update `do_POST` in `NewsBriefingHandler`**

Find the line `brief_text = compile_mock_briefing(category, filtered_articles, grounded_time)` (line 815) and replace it and the Gemini branch with:

Replace lines 814-837:

```python
                if not api_key:
                    brief_text = generate_briefing_text(category, filtered_articles, grounded_time)
                else:
                    try:
                        articles_text_list = []
                        for idx, art in enumerate(filtered_articles):
                            articles_text_list.append(
                                f"[Article #{idx+1}]\n"
                                f"Source: {art['sourceName']}\n"
                                f"Title: {art['title']}\n"
                                f"Published: {art['pubDate']}\n"
                                f"Link: {art['link']}\n"
                                f"Summary: {art['content']}\n"
                                f"------------------"
                            )
                        articles_text = "\n\n".join(articles_text_list)
                        system_prompt = get_system_prompt(formatted_date, category)
                        prompt = f"Here are the articles fetched from the news sources. Summarize them strictly according to the formatting rules:\n\n{articles_text}"
                        brief_text = call_gemini(api_key, system_prompt, prompt)
                    except Exception as gemini_err:
                        print(f"Gemini API failed: {gemini_err}. Falling back to clustering + HF pipeline.")
                        brief_text = generate_briefing_text(category, filtered_articles, grounded_time)
```

- [ ] **Step 5: Run server to verify it starts without errors**

Run: `cd C:\AntiGravity\News App; python server.py`

Expected: "Serving news app at http://localhost:5001" (port may need to be different if already running)

---

### Task 4: Verify End-to-End Briefing on the Running Server

- [ ] **Step 1: Restart the server**

Stop the existing server and start the updated one.

- [ ] **Step 2: Generate a briefing without API key**

Open `http://localhost:5001/`, leave API key empty, click GENERATE BRIEF.

Expected: Briefing loads with clustered headlines, top 3 stories from cross-source coverage, and 2-4 line briefs per article.

- [ ] **Step 3: Check FILTERED FEED tab**

Verify the article count and list shows correctly.

- [ ] **Step 4: Check RAW MARKDOWN tab**

Verify markdown renders correctly with all sections.

---

### Task 5: Edge Case — No API Key, No HF Access

- [ ] **Step 1: Simulate HF failure**

Run: `cd C:\AntiGravity\News App; python -c "from news_summarizer import _extractive_fallback; print(_extractive_fallback('A massive earthquake struck the coast of Japan early this morning. The Japan Meteorological Agency issued a tsunami warning for several coastal prefectures. Residents were urged to evacuate to higher ground immediately. The earthquake registered a magnitude of 7.8, according to the US Geological Survey.'))"`

Expected: Extractive summary of ~3 sentences (first, middle, last).

- [ ] **Step 2: Verify server still generates briefing with no external calls**

If HF is down, the fallback chain produces a readable (non-empty) briefing.
