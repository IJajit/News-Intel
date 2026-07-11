import re
import uuid
from datetime import datetime, timezone

STOPWORDS = {'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for',
             'of', 'is', 'it', 'by', 'with', 'from', 'as', 'be', 'has',
             'are', 'was', 'were', 'been', 'its', 'their', 'that', 'this',
             'not', 'no', 'but', 'if', 'so', 'up', 'do', 'just', 'out'}

URGENCY_KEYWORDS = ['breaking', 'crisis', 'emergency', 'confirmed', 'developing',
                    'death', 'deaths', 'attack', 'war', 'crash', 'disaster',
                    'killed', 'injured', 'collapse', 'warning', 'urgent',
                    'explosion', 'strike', 'military', 'nuclear', 'evacuate',
                    'evacuation', 'catastrophe', 'fatal', 'deadly', 'critical']

# Source authority rankings for primary headline selection (lower = more authoritative)
STORY_SOURCE_AUTHORITY = {
    'reuters': 1, 'ap-news': 1, 'bbc': 2, 'nytimes': 2, 'washington-post': 2,
    'bloomberg': 2, 'the-guardian': 3, 'cnn': 3, 'npr': 3, 'al-jazeera': 3,
    'wired': 3, 'ars-technica': 3, 'techcrunch': 3, 'vox': 3,
    'indian-express': 3, 'the-hindu': 3, 'ndtv': 3, 'deccan-herald': 3,
    'the-print': 4, 'scroll': 4, 'sky-sports': 4, 'hacker-news': 4
}

SUBCATEGORY_KEYWORDS = {
    "Business, Markets & Economy": ['stock', 'stocks', 'market', 'markets', 'economy', 'economic', 'rate', 'rates', 'inflation', 'gdp', 'm&a', 'merger', 'earnings', 'fed', 'layoff', 'crypto', 'shares', 'gold', 'oil', 'billion', 'deal', 'finance'],
    "Technology & Innovation": ['tech', 'technology', 'ai', 'artificial intelligence', 'openai', 'microsoft', 'google', 'quantum', 'chip', 'nvidia', 'robot', 'cybersecurity', 'software', 'apple', 'meta', 'amazon'],
    "Geopolitics & World News": ['treaty', 'summit', 'diplomacy', 'military', 'defense', 'election', 'border', 'nato', 'conflict', 'war', 'putin', 'biden', 'sanctions'],
    "Domestic Politics & Governance": ['law', 'tax', 'policy', 'vote', 'court', 'parliament', 'government', 'bill', 'supreme court', 'police', 'arrest'],
    "Science, Health & Environment": ['climate', 'fda', 'healthcare', 'nasa', 'science', 'earthquake', 'tsunami', 'virus', 'biology', 'medicine', 'vaccine', 'research', 'scientific'],
    "Sports": ['match', 'world cup', 'score', 'cricket', 'football', 'player', 'tennis', 'olympics', 'championship', 'tournament'],
    "Culture, Entertainment & Arts": ['film', 'movie', 'box office', 'award', 'album', 'music', 'gaming'],
    "Lifestyle & Society": ['travel', 'real estate', 'labor', 'union', 'housing', 'crash', 'accident', 'aviation', 'airport', 'weather', 'rain', 'flood', 'storm', 'cyclone', 'monsoon']
}

SUBCATEGORY_NAMES = list(SUBCATEGORY_KEYWORDS.keys())

SUBCATEGORY_TO_CATEGORY = {
    "Technology & Innovation": "Technology",
    "Geopolitics & World News": "Geopolitics",
    "Domestic Politics & Governance": "Geopolitics",
    "Science, Health & Environment": "Science",
    "Culture, Entertainment & Arts": "Culture",
    "Lifestyle & Society": "Society",
    "Sports": "Sports",
    "Business, Markets & Economy": "Finance"
}


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


def jaccard_similarity(a, b):
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return intersection / union


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
            if similarity >= 0.35:
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
            sid = art.get('sourceId', '')
            sources.add(sid)
            all_titles.append(art.get('title', ''))
            total_content += " " + (art.get('content', '') or '')

            pub = art.get('pubDate', '')
            if pub:
                try:
                    dt_str = pub.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(dt_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if latest is None or dt > latest:
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


def rank_clusters(clusters):
    return sorted(clusters, key=lambda c: c['combined_score'], reverse=True)


def contains_word_boundary(text, keywords):
    for kw in keywords:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _assign_subcategory_from_text(text):
    text_lower = text.lower()
    for name in SUBCATEGORY_NAMES:
        kws = SUBCATEGORY_KEYWORDS.get(name, [])
        if contains_word_boundary(text_lower, kws):
            return name
    return "Lifestyle & Society"


def _parse_article_date(art):
    pub = art.get('pubDate', '')
    if not pub:
        return None
    try:
        dt_str = pub.replace('Z', '+00:00')
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def cluster_into_stories(articles, max_sources_per_story=5):
    if not articles:
        return []

    clusters = cluster_articles(articles)
    ranked = rank_clusters(clusters)

    stories = []
    for idx, cluster in enumerate(ranked):
        cluster_arts = cluster["articles"]

        # Sort sources by recency (newest first) for primary selection tiebreaker
        dated_arts = []
        for art in cluster_arts:
            dt = _parse_article_date(art)
            dated_arts.append((art, dt))
        dated_arts.sort(key=lambda x: x[1].timestamp() if x[1] else 0)

        # Pick primary source: earliest among most reputable
        # Sort by authority (lower rank = more authoritative), then by publish time (earliest first)
        def primary_key(item):
            art, dt = item
            sid = art.get('sourceId', '')
            authority = STORY_SOURCE_AUTHORITY.get(sid, 5)
            pub_ts = dt.timestamp() if dt else float('inf')
            return (authority, pub_ts)

        dated_arts.sort(key=primary_key)
        primary_art = dated_arts[0][0] if dated_arts else cluster_arts[0]

        primary_headline = primary_art.get('title', cluster.get('representative_title', 'Untitled Story'))

        # Sort all sources by recency (newest first) for the sources array
        dated_arts_recent = sorted(dated_arts, key=lambda x: x[1].timestamp() if x[1] else 0, reverse=True)
        selected = dated_arts_recent[:max_sources_per_story]

        sources = []
        for art, dt in selected:
            sources.append({
                "source_name": art.get('sourceName', ''),
                "headline": art.get('title', ''),
                "published_at": art.get('pubDate', ''),
                "url": art.get('link', ''),
                "content": art.get('content', '') or ''
            })

        # Derive category from majority subcategory keyword match
        subcat_votes = {}
        for art in cluster_arts:
            text = (art.get('title', '') or '') + ' ' + (art.get('content', '') or '')
            subcat = _assign_subcategory_from_text(text)
            subcat_votes[subcat] = subcat_votes.get(subcat, 0) + 1

        majority_subcat = max(subcat_votes, key=subcat_votes.get) if subcat_votes else "Lifestyle & Society"
        category = SUBCATEGORY_TO_CATEGORY.get(majority_subcat, "Society")

        story = {
            "story_id": f"story-{idx + 1}",
            "category": category,
            "primary_headline": primary_headline,
            "primary_source": {
                "source_name": primary_art.get('sourceName', ''),
                "headline": primary_art.get('title', ''),
                "published_at": primary_art.get('pubDate', ''),
                "url": primary_art.get('link', ''),
                "content": primary_art.get('content', '') or ''
            },
            "sources": sources,
            "source_count": cluster["source_count"],
            "total_count": cluster["total_count"],
            "combined_score": cluster["combined_score"]
        }

        stories.append(story)

    return stories


if __name__ == "__main__":
    test_articles = [
        {"sourceId": "bbc", "sourceName": "BBC News", "title": "Earthquake hits Japan, tsunami warning issued", "content": "A powerful earthquake struck Japan...", "pubDate": "2026-06-26T10:00:00Z"},
        {"sourceId": "cnn", "sourceName": "CNN", "title": "Japan earthquake triggers tsunami warning", "content": "A major earthquake in Japan...", "pubDate": "2026-06-26T10:05:00Z"},
        {"sourceId": "reuters", "sourceName": "Reuters", "title": "Earthquake in Japan: tsunami alert for coastal areas", "content": "An earthquake...", "pubDate": "2026-06-26T10:10:00Z"},
        {"sourceId": "bbc", "sourceName": "BBC News", "title": "Stock markets rally after Fed announcement", "content": "Markets surged...", "pubDate": "2026-06-26T11:00:00Z"},
    ]
    clusters = cluster_articles(test_articles)
    ranked = rank_clusters(clusters)
    print(f"Clusters: {len(ranked)}")
    for c in ranked:
        print(f"  Score: {c['combined_score']}, Sources: {c['source_count']}, Title: {c['representative_title'][:50]}")

    stories = cluster_into_stories(test_articles)
    print(f"\nStories: {len(stories)}")
    for s in stories:
        print(f"  ID: {s['story_id']}, Cat: {s['category']}, Primary: {s['primary_headline'][:50]}, Sources: {s['source_count']}")

    print("All checks passed.")
