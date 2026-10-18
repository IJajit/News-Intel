import os
import json
import time
import concurrent.futures
from datetime import datetime, timezone, timedelta
import server
from news_clustering import cluster_into_stories, rank_clusters
from news_summarizer import generate_deep_dive_brief, _structured_fallback

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

    # 1. Slice and rank stories for each section:
    # All / Global: all stories
    all_cats = ['technology', 'geopolitics', 'science', 'culture', 'society', 'sports', 'finance']

    # Homepage: top 20 stories in past 24 hours
    hp_candidates = sorted(ranked_stories, key=lambda s: (s.get('source_count', 1), s.get('combined_score', 0)), reverse=True)[:20]

    # 1-Hour (Latest tab): top 20 stories published in the past 1.0 hour
    cutoff_1h = now_dt - timedelta(hours=1.0)
    candidates_1h = []
    for s in ranked_stories:
        p_str = s.get('primary_source', {}).get('published_at')
        p_dt = server.parse_iso(p_str) or server.parse_date(p_str)
        if p_dt:
            if p_dt.tzinfo is None:
                p_dt = p_dt.replace(tzinfo=timezone.utc)
            if p_dt >= cutoff_1h:
                candidates_1h.append(s)
    candidates_1h = sorted(candidates_1h, key=lambda s: (s.get('source_count', 1), s.get('combined_score', 0)), reverse=True)[:20]

    # Category slices: top 20 for each category
    cat_candidates = {}
    for cat_name in all_cats:
        c_stories = [s for s in ranked_stories if (s.get('category') or '').lower() == cat_name]
        c_sorted = sorted(c_stories, key=lambda s: (s.get('source_count', 1), s.get('combined_score', 0)), reverse=True)[:20]
        cat_candidates[cat_name] = c_sorted

    # Priority stories: EVERY story included in Homepage, 1Hour, or any Category top 20
    priority_story_ids = set()
    for s in hp_candidates:
        priority_story_ids.add(s['story_id'])
    for s in candidates_1h:
        priority_story_ids.add(s['story_id'])
    for cat_name, c_stories in cat_candidates.items():
        for s in c_stories:
            priority_story_ids.add(s['story_id'])

    print(f"Identified {len(priority_story_ids)} high-priority stories across Home, Latest (1h), and Categories for Gemini Deep-Dive briefs.")

    gemini_key = server.os.environ.get('GEMINI_API_KEY', '')

    def get_brief_for_story(story):
        primary_hl = story.get('primary_headline', '')
        # Combine content from all clustered sources so summarizer has maximum context
        all_contents = []
        for s in story.get('sources', []):
            c = (s.get('content') or s.get('headline') or '').strip()
            if c:
                all_contents.append(c)
        combined_content = "\n\n".join(all_contents)
        if not combined_content:
            combined_content = story.get('primary_source', {}).get('content', '') or primary_hl
        story_id = story['story_id']

        # Use Gemini AI for priority stories
        if story_id in priority_story_ids:
            try:
                res = generate_deep_dive_brief(combined_content, title=primary_hl, gemini_key=gemini_key)
                if res and isinstance(res, dict) and res.get('summary'):
                    return story_id, res
            except Exception as e:
                print(f"Gemini brief generation error for {story_id}: {e}")

        # Clean fallback for non-priority/remaining stories
        fb = _structured_fallback(combined_content, title=primary_hl)
        return story_id, fb

    # Parallelize Gemini API calls
    briefs_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        fut_to_story = {executor.submit(get_brief_for_story, s): s for s in ranked_stories}
        for fut in concurrent.futures.as_completed(fut_to_story):
            sid, b_res = fut.result()
            briefs_map[sid] = b_res

    def convert_story_dict(story):
        brief_data = briefs_map.get(story['story_id']) or {}
        b_bullets = brief_data.get('brief', [story.get('primary_headline')])
        w_bullets = brief_data.get('why_it_matters', [])
        summary = brief_data.get('summary', '') or ' '.join(b_bullets)

        return {
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

    story_objects = [convert_story_dict(s) for s in ranked_stories]

    # 1. Global (All category) - past 24 hours, all stories across categories
    global_data = {
        'id': 'latest',
        'category': 'global',
        'timestamp': now_iso,
        'articlesCount': len(story_objects),
        'stories': story_objects
    }

    # 2. Homepage - past 24 hours, top 20 stories
    hp_stories = [convert_story_dict(s) for s in hp_candidates]
    homepage_data = {
        'id': 'latest',
        'category': 'homepage',
        'timestamp': now_iso,
        'articlesCount': len(hp_stories),
        'stories': hp_stories
    }

    # 3. 1hour (Latest tab) - past 1.0 hour, top 20 stories
    stories_1h = [convert_story_dict(s) for s in candidates_1h]
    one_hour_data = {
        'id': 'latest',
        'category': '1hour',
        'timestamp': now_iso,
        'articlesCount': len(stories_1h),
        'stories': stories_1h
    }

    # 4. Individual categories - past 24 hours, top 20 stories
    cat_datasets = {}
    for cat_name in all_cats:
        c_stories = [convert_story_dict(s) for s in cat_candidates[cat_name]]
        cat_datasets[cat_name] = {
            'id': 'latest',
            'category': cat_name,
            'timestamp': now_iso,
            'articlesCount': len(c_stories),
            'stories': c_stories
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
