import re
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
    print("All checks passed.")
