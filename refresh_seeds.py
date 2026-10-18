import os
import json
import time
from datetime import datetime, timezone, timedelta
import server
from news_clustering import cluster_into_stories, rank_clusters
from news_summarizer import _structured_fallback

def run():
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    print("Running briefing generation at:", now_iso)

    t0 = time.time()
    articles_24h = server.get_filtered_articles(now_iso, max_hours=24.0)
    print(f"Fetched {len(articles_24h)} articles in {time.time()-t0:.2f}s")

    t1 = time.time()
    clusters = cluster_into_stories(articles_24h)
    ranked_stories = rank_clusters(clusters)
    print(f"Clustered into {len(ranked_stories)} stories in {time.time()-t1:.2f}s")

    story_objects = []
    for story in ranked_stories:
        fb = _structured_fallback(story.get('primary_source', {}).get('content', ''), title=story.get('primary_headline', ''))
        b_bullets = fb.get('brief', [story.get('primary_headline')])
        w_bullets = fb.get('why_it_matters', [])
        summary = fb.get('summary', '') or ' '.join(b_bullets)

        story_obj = {
            'story_id': story['story_id'],
            'category': story['category'],
            'primary_headline': story['primary_headline'],
            'primary_source': story['primary_source'],
            'sources': [
                {
                    'source_name': s['source_name'],
                    'headline': s['headline'],
                    'published_at': s['published_at'],
                    'url': s['url']
                }
                for s in story['sources']
            ],
            'source_count': story['source_count'],
            'total_count': story['total_count'],
            'combined_score': story['combined_score'],
            'brief_bullets': b_bullets,
            'why_it_matters_bullets': w_bullets,
            'brief': summary,
            'brief_word_count': len(summary.split())
        }
        story_objects.append(story_obj)

    # 1. Global (All category) - past 24 hours, all stories across categories
    global_data = {
        'id': 'latest',
        'category': 'global',
        'timestamp': now_iso,
        'articlesCount': len(story_objects),
        'stories': story_objects
    }

    # 2. Homepage - past 24 hours, top 20 stories
    hp_stories = list(story_objects)
    hp_stories.sort(key=lambda s: (s.get('source_count', 1), s.get('combined_score', 0)), reverse=True)
    homepage_data = {
        'id': 'latest',
        'category': 'homepage',
        'timestamp': now_iso,
        'articlesCount': min(len(hp_stories), 20),
        'stories': hp_stories[:20]
    }

    # 3. 1hour (Latest tab) - past 1.0 hour, top 20 stories
    cutoff_1h = now_dt - timedelta(hours=1.0)
    stories_1h = []
    for s in story_objects:
        p_str = s.get('primary_source', {}).get('published_at')
        p_dt = server.parse_iso(p_str) or server.parse_date(p_str)
        if p_dt:
            if p_dt.tzinfo is None:
                p_dt = p_dt.replace(tzinfo=timezone.utc)
            if p_dt >= cutoff_1h:
                stories_1h.append(s)

    stories_1h.sort(key=lambda s: (s.get('source_count', 1), s.get('combined_score', 0)), reverse=True)
    one_hour_data = {
        'id': 'latest',
        'category': '1hour',
        'timestamp': now_iso,
        'articlesCount': min(len(stories_1h), 20),
        'stories': stories_1h[:20]
    }

    # 4. Individual categories - past 24 hours, top 20 stories
    cat_datasets = {}
    all_cats = ['technology', 'geopolitics', 'science', 'culture', 'society', 'sports', 'finance']
    for cat_name in all_cats:
        cat_st = [s for s in story_objects if (s.get('category') or '').lower() == cat_name]
        cat_st.sort(key=lambda s: (s.get('source_count', 1), s.get('combined_score', 0)), reverse=True)
        cat_datasets[cat_name] = {
            'id': 'latest',
            'category': cat_name,
            'timestamp': now_iso,
            'articlesCount': min(len(cat_st), 20),
            'stories': cat_st[:20]
        }

    # Save all datasets to both data/briefings and briefings_seed
    dirs = [server.BRIEFINGS_DIR, server.SEED_DIR]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'latest_global.json'), 'w', encoding='utf-8') as f:
            json.dump(global_data, f, ensure_ascii=False, indent=2)
        with open(os.path.join(d, 'latest_homepage.json'), 'w', encoding='utf-8') as f:
            json.dump(homepage_data, f, ensure_ascii=False, indent=2)
        with open(os.path.join(d, 'latest_1hour.json'), 'w', encoding='utf-8') as f:
            json.dump(one_hour_data, f, ensure_ascii=False, indent=2)
        for cat_name, cdata in cat_datasets.items():
            with open(os.path.join(d, f'latest_{cat_name}.json'), 'w', encoding='utf-8') as f:
                json.dump(cdata, f, ensure_ascii=False, indent=2)

    print("Successfully generated and updated all briefing seed files!")
    print(f"  Global stories: {len(global_data['stories'])}")
    print(f"  Homepage stories: {len(homepage_data['stories'])}")
    print(f"  1-Hour stories: {len(one_hour_data['stories'])}")
    for c, d in cat_datasets.items():
        print(f"  {c.capitalize()}: {len(d['stories'])} stories")

if __name__ == '__main__':
    run()
