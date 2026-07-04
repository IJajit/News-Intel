import http.server
import socketserver
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import os
import re
import base64
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import html
import ssl
import concurrent.futures

from news_clustering import cluster_articles, rank_clusters, jaccard_similarity, normalize_title
from news_summarizer import summarize_content, extract_why_it_matters

# Manually load environment variables from .env file
# This is done to avoid external dependencies like python-dotenv
DOTENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(DOTENV_PATH):
    with open(DOTENV_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value.strip('"\'')
# Global SSL context to handle potential SSL certification issues, especially on Windows.
# Disables SSL certificate verification, which is not recommended for production in sensitive applications.
ssl_context = ssl._create_unverified_context()

# Set working directory to this file's folder to ensure static files and data are found
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def load_dotenv():
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key_val = line.split('=', 1)
                    if len(key_val) == 2:
                        k, v = key_val
                        v = v.strip().strip("'\"")
                        os.environ[k.strip()] = v

# Load local environment variables from .env if present
load_dotenv()

HF_API_TOKEN = os.environ.get('HF_API_TOKEN', '')

def is_valid_api_key(key):
    if not key:
        return False
    key = key.strip()
    if not key:
        return False
    if ' ' in key or '\n' in key or '\r' in key:
        return False
    if 'Live Briefing' in key:
        return False
    if all(c == '•' or c == '*' for c in key):
        return False
    if len(key) < 10:
        return False
    return True

# Create an unverified SSL context to bypass SSL certification errors on RSS feeds
try:
    ssl_context = ssl._create_unverified_context()
except AttributeError:
    ssl_context = None




PORT = 5001

SOURCES = [
  { "id": "bbc", "name": "BBC News", "url": "https://feeds.bbci.co.uk/news/rss.xml", "siteUrl": "https://www.bbc.com/" },

  { "id": "indian-express", "name": "The Indian Express", "url": "https://indianexpress.com/feed/", "siteUrl": "https://indianexpress.com/" },
  { "id": "the-guardian", "name": "The Guardian", "url": "https://www.theguardian.com/international/rss", "siteUrl": "https://www.theguardian.com/international" },
  { "id": "techcrunch", "name": "TechCrunch", "url": "https://techcrunch.com/feed/", "siteUrl": "https://techcrunch.com/" },
  { "id": "deccan-herald", "name": "Deccan Herald", "url": "https://www.deccanherald.com/feed/", "siteUrl": "https://www.deccanherald.com/" },
  { "id": "bloomberg", "name": "Bloomberg", "url": "https://feeds.bloomberg.com/markets/news.rss", "siteUrl": "https://www.bloomberg.com/asia" },
  { "id": "ft", "name": "Financial Times", "url": "https://www.ft.com/rss/home", "siteUrl": "https://www.ft.com/" },
  { "id": "the-verge", "name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "siteUrl": "https://www.theverge.com/" },
  { "id": "pti", "name": "Press Trust of India", "url": "https://news.google.com/rss/search?q=site:ptinews.com", "siteUrl": "https://www.ptinews.com/" },
  { "id": "ap-news", "name": "AP News", "url": "https://news.google.com/rss/search?q=site:apnews.com", "siteUrl": "https://apnews.com/" }
]

CATEGORIES = [
  { "id": "global",     "name": "Global",     "label": "ALL REGIONS",        "icon": "" },
  { "id": "indian",     "name": "India",       "label": "DOMESTIC",           "icon": "" },
  { "id": "technology", "name": "Technology",  "label": "TECH & INNOVATION",  "icon": "" },
  { "id": "sports",     "name": "Sports",      "label": "LIVE SCORES",        "icon": "" },
  { "id": "finance",    "name": "Finance",     "label": "MARKETS & ECONOMY",  "icon": "" },
]

def decode_google_news_url(url):
    try:
        match = re.search(r'news\.google\.com/(?:rss/)?articles/([^?#/]+)', url)
        if not match:
            return url
        encoded_str = match.group(1)
        # Replace URL-safe base64 characters and ensure correct padding
        encoded_str = encoded_str.replace('-', '+').replace('_', '/')
        padding = len(encoded_str) % 4
        if padding:
            encoded_str += '=' * (4 - padding)
        decoded_bytes = base64.b64decode(encoded_str)
        decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
        http_match = re.search(r'(https?://[^\s\x00-\x1f\x7f-\xff]+)', decoded_str)
        if http_match:
            return http_match.group(1)
    except Exception as e:
        print(f"Error decoding base64 link {url}: {e}")
    return url


# Use /tmp for writing data on Vercel as the deployment root is read-only
if os.environ.get('VERCEL') or not os.access(os.getcwd(), os.W_OK):
    DATA_DIR = '/tmp'
else:
    DATA_DIR = os.path.join(os.getcwd(), 'data')

BRIEFINGS_DIR = os.path.join(DATA_DIR, 'briefings')
os.makedirs(BRIEFINGS_DIR, exist_ok=True)


def parse_iso(iso_str):
    if not iso_str:
        return None
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(iso_str)
    except Exception:
        return None

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    try:
        return parse_iso(date_str)
    except Exception:
        pass
    return None

def fetch_feed(source):
    try:
        req = urllib.request.Request(
            source['url'],
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive'
            }
        )
        
        # Use unverified SSL context to bypass SSL certification errors on Windows
        kwargs = {'timeout': 12}
        if ssl_context:
            kwargs['context'] = ssl_context
            
        with urllib.request.urlopen(req, **kwargs) as response:
            xml_data = response.read()

        xml_str = xml_data.decode('utf-8', errors='ignore')
        xml_str = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#[xX][0-9a-fA-F]+;)', '&amp;', xml_str)

        root = ET.fromstring(xml_str)
        items = []

        # Detect Atom vs RSS
        is_atom = root.tag.endswith('feed')
        ns = {'atom': 'http://www.w3.org/2005/Atom'} if is_atom else {}

        if is_atom:
            entries = root.findall('.//atom:entry', ns)
        else:
            entries = root.findall('.//item')

        for entry in entries:
            if is_atom:
                title_el = entry.find('atom:title', ns)
                link_el = entry.find('atom:link', ns)
                pub_date_el = entry.find('atom:published', ns)
                desc_el = entry.find('atom:summary', ns)
                if desc_el is None:
                    desc_el = entry.find('atom:content', ns)
                link_text = link_el.get('href', '').strip() if link_el is not None else ''
            else:
                title_el = entry.find('title')
                link_el = entry.find('link')
                pub_date_el = entry.find('pubDate')
                desc_el = entry.find('description')
                link_text = (link_el.text if (link_el is not None and link_el.text is not None) else "").strip()

            title_text = (title_el.text if (title_el is not None and title_el.text is not None) else "").strip()
            pub_date_text = (pub_date_el.text if (pub_date_el is not None and pub_date_el.text is not None) else "").strip()
            desc_text = (desc_el.text if (desc_el is not None and desc_el.text is not None) else "").strip()

            desc_clean = re.sub('<[^<]+?>', '', desc_text)

            if "news.google.com/rss/articles/" in link_text or "news.google.com/articles/" in link_text:
                link_text = decode_google_news_url(link_text)

            is_feed_url = False
            if not link_text:
                is_feed_url = True
            elif link_text == source['url']:
                is_feed_url = True
            elif link_text.endswith('/feed') or link_text.endswith('/feed/') or link_text.endswith('/rss.xml') or link_text.endswith('/rss'):
                is_feed_url = True

            if is_feed_url:
                link_text = source['siteUrl']

            items.append({
                'sourceId': source['id'],
                'sourceName': source['name'],
                'title': title_text,
                'link': link_text,
                'pubDate': pub_date_text,
                'content': desc_clean
            })
        return items
    except Exception as e:
        print(f"Error fetching feed {source['name']} ({source['url']}): {e}")
        return []

def scrape_article_description(art):
    url = art.get('link')
    if not url:
        return art
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive'
            }
        )
        kwargs = {'timeout': 6}
        if ssl_context:
            kwargs['context'] = ssl_context
        with urllib.request.urlopen(req, **kwargs) as response:
            html_bytes = response.read(100000)
            html_str = html_bytes.decode('utf-8', errors='ignore')

            desc = None
            match = re.search(r'<meta\s+[^>]*name=["\']description["\']\s+content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
            if not match:
                match = re.search(r'<meta\s+[^>]*content=["\']([^"\']+)["\']\s+name=["\']description["\']', html_str, re.IGNORECASE)
            if not match:
                match = re.search(r'<meta\s+[^>]*property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
            if not match:
                match = re.search(r'<meta\s+[^>]*content=["\']([^"\']+)["\']\s+property=["\']og:description["\']', html_str, re.IGNORECASE)
            if match:
                desc = html.unescape(match.group(1).strip())

            if desc and len(desc.split()) >= 8:
                art['content'] = desc
                return art

            paragraphs = []
            p_matches = re.findall(r'<p[^>]*>(.*?)</p>', html_str, re.IGNORECASE | re.DOTALL)
            for p in p_matches[:6]:
                p_text = re.sub(r'<[^>]+>', ' ', p)
                p_text = html.unescape(p_text).strip()
                p_text = re.sub(r'\s+', ' ', p_text)
                p_text = re.sub(r'\bContinue\s+reading\b.*$', '', p_text, flags=re.IGNORECASE).strip()
                if len(p_text.split()) > 8:
                    paragraphs.append(p_text)

            if paragraphs:
                art['content'] = ' '.join(paragraphs)
            elif desc:
                art['content'] = desc
    except Exception as e:
        print(f"Error scraping content for {url}: {e}")
    return art

def get_filtered_articles(grounded_time_str):
    grounded_dt = parse_iso(grounded_time_str)
    if not grounded_dt:
        grounded_dt = datetime.now(timezone.utc)
    elif grounded_dt.tzinfo is None:
        grounded_dt = grounded_dt.replace(tzinfo=timezone.utc)

    all_articles = []
    # Fetch RSS feeds concurrently to prevent slow sequential timeouts
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SOURCES)) as executor:
        future_to_src = {executor.submit(fetch_feed, src): src for src in SOURCES}
        for future in concurrent.futures.as_completed(future_to_src):
            try:
                all_articles.extend(future.result())
            except Exception as e:
                src = future_to_src[future]
                print(f"Error in parallel fetch of {src['name']}: {e}")

    filtered = []
    seen_keys = set()

    for art in all_articles:
        key = art['link'] or art['title']
        if key in seen_keys:
            continue

        pub_dt = parse_date(art['pubDate'])
        if not pub_dt:
            continue

        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)

        diff = grounded_dt - pub_dt
        diff_hours = diff.total_seconds() / 3600.0

        if -1.0 <= diff_hours <= 24.0:
            seen_keys.add(key)
            filtered.append(art)

    def _has_title_only_content(content, title):
        if not content:
            return True
        clean = re.sub(r'\s+', ' ', content.lower()).strip().rstrip('.')
        title_clean = re.sub(r'\s+', ' ', title.lower()).strip().rstrip('.')
        return title_clean in clean or clean in title_clean

    articles_to_scrape = [art for art in filtered
                          if not art.get('content') or _has_title_only_content(art.get('content'), art.get('title', ''))]
    if articles_to_scrape:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(articles_to_scrape), 10)) as executor:
            list(executor.map(scrape_article_description, articles_to_scrape))

    def get_pub_time(a):
        dt = parse_date(a['pubDate'])
        return dt.timestamp() if dt else 0

    filtered.sort(key=get_pub_time, reverse=True)
    return filtered

def contains_word_boundary(text, keywords):
    for kw in keywords:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def is_sentence_boundary(text, match_start, match_end):
    # Get the word before the punctuation
    preceding_text = text[:match_start]
    word_match = re.search(r'\b([a-zA-Z0-9.\u0080-\uffff]+)$', preceding_text)
    if not word_match:
        return True
    word = word_match.group(1).lower().strip('.')
    
    # List of common abbreviations (lowercase, without dots)
    abbreviations = {
        'us', 'uk', 'vs', 'dr', 'mr', 'ms', 'mrs', 'co', 'inc', 'ltd', 'corp', 
        'am', 'pm', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 
        'oct', 'nov', 'dec', 'org', 'gov', 'edu', 'st', 'ave', 'rd', 'prof', 
        'gen', 'col', 'sen', 'rep', 'approx', 'etc', 'al', 'ie', 'eg'
    }
    
    if word in abbreviations:
        return False
        
    # If the preceding word is a single uppercase letter (initial)
    last_word = word_match.group(1)
    if len(last_word) == 1 and last_word.isupper():
        return False
        
    # If it has dots inside it like "u.s"
    if '.' in last_word.strip('.'):
        return False
        
    return True

def clean_content(text):
    """Strip RSS artifacts: 'Continue reading', trailing ellipsis,
       leftover HTML tags, excessive whitespace, and ensure complete sentences."""
    if not text:
        return ''
    
    # Unescape HTML entities (like &nbsp;, &amp;, etc.)
    text = html.unescape(text)
    
    # Strip any HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove 'Continue reading' in all forms, including trailing dots/spaces
    text = re.sub(r'\bContinue\s+reading\b.*$', '', text, flags=re.IGNORECASE).strip()
    
    # Remove trailing ellipses and dots
    text = re.sub(r'\.{2,}\s*$', '', text).strip()
    text = re.sub(r'\u2026\s*$', '', text).strip()
    
    # Ensure it ends in complete sentences by truncating to the last valid punctuation mark (. ! ?)
    matches = list(re.finditer(r'[.!?]["”\'’]?(\s|$)', text))
    valid_end = -1
    for m in reversed(matches):
        if is_sentence_boundary(text, m.start(), m.end()):
            valid_end = m.end()
            break
            
    if valid_end != -1:
        text = text[:valid_end].strip()
    else:
        # If no valid sentence boundary is found, check if the string itself ends with a punctuation mark
        if not text.endswith(('.', '!', '?', '"', '”', "'", '’')):
            text = text + '.'
            
    # Final cleanup
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def filter_by_category(articles, category):
    if category == 'global':
        return articles

    filtered = []

    indian_sources = {'the indian express', 'deccan herald'}
    tech_sources = {'techcrunch'}

    indian_kws = [
        'india', 'indian', 'indians', 'delhi', 'mumbai', 'bengaluru', 'bangalore',
        'kolkata', 'chennai', 'hyderabad', 'pune', 'kerala', 'karnataka', 'maharashtra',
        'haryana', 'punjab', 'up', 'himachal', 'lucknow', 'modi', 'gandhi', 'bjp', 'congress',
        'aap', 'rss', 'sena', 'tmc', 'birla', 'tata', 'ambani', 'reliance', 'isro',
        'sebi', 'rbi', 'rupee', 'rupees', 'lok sabha', 'rajya sabha'
    ]

    tech_kws = [
        'tech', 'technology', 'ai', 'artificial intelligence', 'openai', 'microsoft', 'google',
        'quantum', 'chip', 'chips', 'semiconductor', 'broadcom', 'nvidia', 'robot', 'robotics',
        'robotaxi', 'zoox', 'security', 'breach', 'cyber', 'cybersecurity', 'software', 'hardware',
        'launch', 'phone', 'specs', 'developer', 'gadget', 'gadgets', 'app', 'apps', 'startup',
        'startups', 'apple', 'meta', 'amazon'
    ]

    sports_kws = [
        'match', 'world cup', 'score', 'game', 'games', 'stokes', 'root', 'england', 'cricket',
        'football', 'soccer', 'player', 'players', 'transfer', 'injury', 'havertz', 'brazil',
        'panama', 'wicket', 'wickets', 'league', 'tennis', 'olympics', 'olympic', 'athlete',
        'athletes', 'championship', 'tournament', 'wimbledon', 'euro 2026', 'final', 'semi-final',
        'win', 'won', 'defeat', 'lost', 'cup'
    ]

    finance_kws = [
        'stock', 'stocks', 'market', 'markets', 'economy', 'economic', 'rate', 'rates',
        'inflation', 'gdp', 'm&a', 'merger', 'mergers', 'earnings', 'fed', 'layoff', 'layoffs',
        'funding', 'ipo', 'crypto', 'shares', 'gold', 'oil', 'price', 'prices', 'billion',
        'million', 'deal', 'finance', 'fiscal', 'revenue', 'profit', 'losses', 'securities',
        'dividend'
    ]

    for art in articles:
        source_lower = art['sourceName'].lower()
        title_lower = art['title'].lower()
        content_lower = art['content'].lower()
        text = title_lower + " " + content_lower

        if category == 'indian':
            if source_lower in indian_sources or contains_word_boundary(text, indian_kws):
                filtered.append(art)
        elif category == 'technology':
            if source_lower in tech_sources or contains_word_boundary(text, tech_kws):
                filtered.append(art)
        elif category == 'sports':
            if contains_word_boundary(text, sports_kws):
                filtered.append(art)
        elif category == 'finance':
            if contains_word_boundary(text, finance_kws):
                filtered.append(art)

    return filtered


def get_pub_time(art):
    dt = parse_date(art.get('pubDate', ''))
    return dt.timestamp() if dt else 0


def _dedup_articles_by_similarity(articles, threshold=0.4):
    if not articles:
        return []
    deduped = []
    seen_tokens = []
    for art in articles:
        tokens, _ = normalize_title(art.get('title', ''))
        is_dup = False
        for existing in seen_tokens:
            if jaccard_similarity(tokens, existing) >= threshold:
                is_dup = True
                break
        if not is_dup:
            seen_tokens.append(tokens)
            deduped.append(art)
    return deduped


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

- **No Breaking News:** No stories met the strict 24-hour recency filter for sector: {category.upper()} at this time.

# Today's Top Stories

- **Summarizer Standby**
  The summarizer is scanning all {len(SOURCES)} verified feeds.
  *Why it matters:* Feed updates are continuously monitored.

# Category Breakdown

### SYSTEM STATUS
- Sector {category.upper()} is active but no stories passed the 24-hour filter.

# Quick Hits
- Scan completed. Feeds active."""

    clusters = cluster_articles(articles)
    ranked = rank_clusters(clusters)

    def _pick_latest(cluster):
        best = None
        best_time = None
        for art in cluster["articles"]:
            pub = parse_date(art.get('pubDate', ''))
            if pub and (best_time is None or pub > best_time):
                best_time = pub
                best = art
        return best

    unique_articles = []
    for cluster in ranked:
        rep = _pick_latest(cluster)
        if rep:
            unique_articles.append(rep)

    unique_articles.sort(key=get_pub_time, reverse=True)

    # Headlines: latest 3 distinct stories (one per cluster)
    headline_articles = unique_articles[:3]
    headline_ids = set(id(a) for a in headline_articles)

    # Top Stories: highest-ranked clusters, no overlap with headlines
    top_candidates = []
    for cluster in ranked:
        rep = _pick_latest(cluster)
        if rep and id(rep) not in headline_ids:
            top_candidates.append(rep)
            if len(top_candidates) >= 3:
                break

    top_story_articles = top_candidates[:3]
    top_ids = set(id(a) for a in top_story_articles)

    remaining = [a for a in unique_articles if id(a) not in headline_ids and id(a) not in top_ids]

    def make_article_bullet(art, detail_level="brief"):
        raw_content = art.get('content', '') or ''
        cleaned = clean_content(raw_content)
        brief = summarize_content(cleaned, art.get('title', ''), ssl_context, HF_API_TOKEN)
        link = art.get('link', '')
        source = art.get('sourceName', '')
        if detail_level == "brief":
            return f"- **{art.get('title', '')}** ([{source}]({link}))\n  {brief}"
        else:
            why = extract_why_it_matters(raw_content, art.get('title', ''), brief)
            if why:
                return f"- **{art.get('title', '')}** ([{source}]({link}))\n  {brief}\n  *Why it matters:* {why}"
            else:
                return f"- **{art.get('title', '')}** ([{source}]({link}))\n  {brief}"

    headline_bullets = []
    for a in headline_articles[:3]:
        headline_bullets.append(make_article_bullet(a, "brief"))
    headline_text = "\n\n".join(headline_bullets) if headline_bullets else "- No critical headlines at this moment."

    top_bullets = []
    for a in top_story_articles[:3]:
        top_bullets.append(make_article_bullet(a, "detailed"))
    top_stories_text = "\n\n".join(top_bullets) if top_bullets else "- No top stories identified for this session."

    cat_names = [
        "Business, Markets & Economy",
        "Technology & Innovation",
        "Geopolitics & World News",
        "Domestic Politics & Governance",
        "Science, Health & Environment",
        "Sports",
        "Culture, Entertainment & Arts",
        "Lifestyle & Society"
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

    for cat_name in cat_names:
        cat_grouped[cat_name] = _dedup_articles_by_similarity(cat_grouped[cat_name])

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

def call_gemini(api_key, system_prompt, articles_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{
            "parts": [{
                "text": f"{system_prompt}\n\n{articles_text}"
            }]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192
        }
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        brief_text = res_data['candidates'][0]['content']['parts'][0]['text']
        return brief_text

def get_system_prompt(formatted_date, category):
    return f"""You are my executive daily news summarizer. Your job is to extract the absolute latest, breaking updates from today from the provided source articles and present them in a highly scannable, zero-fluff briefing.

Grounded Timestamp (Source of Truth): {formatted_date}
Category Focus: {category.upper()}

=== STEP 1 — RECENCY FILTER (mechanical, not interpretive) ===
For every candidate story, identify its explicit published timestamp from the source. Compare it against the grounded time above.
- Discard any story whose timestamp is more than 24 hours before the grounded time.
- If a source does not show a clear timestamp, do not include it.
- This 24-hour rule applies uniformly.

=== STEP 2 — CATEGORY CLASSIFICATION SCOPES (follow strictly) ===
When categorizing stories, organize them according to these exact scopes to ensure accuracy:
1. **Business, Markets & Economy**: Stock markets, currencies, global finance, macroeconomic indicators (inflation, GDP), mergers & acquisitions, corporate deals, earnings reports, layoffs.
2. **Technology & Innovation**: Consumer technology, software updates, artificial intelligence (AI), semiconductor chips, hardware specifications, app releases, startup funding. (Do NOT place military/airspace breaches or public physical safety inspections here).
3. **Geopolitics & World News**: International conflicts, military actions, airspace incursions, border breaches, foreign policy, international summits, treaties, global diplomatic relations, major international disasters.
4. **Domestic Politics & Governance**: Local/national government directives, elections, legislation, judicial court rulings, official safety inspections, regulatory safety compliance enforcement (e.g. sealing non-compliant buildings, ordering audits).
5. **Science, Health & Environment**: Earthquakes, extreme weather events (floods, cyclones, heatwaves), medical/clinical research, space exploration, ecological developments, public health warnings.
6. **Sports**: Athletic matches, tournament results, player transfers, sports league news.
7. **Culture, Entertainment & Arts**: Movies, music releases, gaming news, art events, book reviews.
8. **Lifestyle & Society**: Public transit issues, travel disruptions, aviation incidents (e.g. taxiway near-misses, runway incursions), infrastructure accidents (e.g. building/warehouse collapses), real estate, labor strikes.

=== STEP 3 — FORMATTING RULES (follow exactly) ===
Structure the daily briefing EXACTLY as follows. You must separate all headers and items with double newlines. Do NOT merge headers and list items into a single line.

Live Briefing for: {formatted_date}


# The Headline

For each of the 5 to 8 biggest breaking stories from the last 24 hours, write a bullet with:
- The headline in bold, followed by a markdown hyperlink to the source in parentheses.
- A detailed 2-to-3 sentence summary providing context, key figures, and immediate consequences.
- No emojis anywhere in the output.

Format (use exactly double newlines around header, and start list items with "- "):
- **[Story Headline]** ([Source Name](article URL))
  [2-3 sentence elaboration: what happened, who is involved, what it means, key numbers or quotes if available]


# Today's Top Stories

Identify the 3 single most important stories from the last 24 hours. For each:
- Lead with the headline in bold, followed by a hyperlink to the source.
- Write 3-4 sentences of analysis covering the core facts, context, and stakes.
- Explicitly state "Why it matters:" with a substantive analytical paragraph (2-3 sentences).

Format (all items must start flush with "- " at the same indent level):
- **[Story Headline]** ([Source Name](article URL))
  [3-4 sentence summary with full context, key details, numbers, and named actors]
  *Why it matters:* [2-3 sentence analytical reasoning on why this is significant]


# Category Breakdown

For each relevant category below, list 5 to 10 articles from the last 24 hours. If a category has no qualifying articles, omit its H3 header entirely. Each item must:
- Start with the headline in bold followed by a hyperlink to the article source.
- Include 2-3 sentences of elaboration below the headline providing context and key facts.
- No single-sentence bullets — every item requires substantive detail.
- No emojis.

Format (H3 headers must be capitalized exactly as written, e.g. "### Sports"):
### [Category Name]

- **[Headline]** ([Source Name](article URL))
  [2-3 sentence elaboration]

Available categories to use as H3 headers:
### Business, Markets & Economy
### Technology & Innovation
### Geopolitics & World News
### Domestic Politics & Governance
### Science, Health & Environment
### Sports
### Culture, Entertainment & Arts
### Lifestyle & Society


# Quick Hits

A short bulleted list of immediate facts from the last 24 hours (scores, specific numbers, product release dates, market moves). Each bullet is one concise factual sentence with a markdown hyperlink to its source.

Format:
- **[Headline/Fact]** ([Source Name](article URL))


=== TONE & CONSTRAINTS ===
- CRITICAL: Never concatenate a header directly with text (e.g. do not output "The HeadlineTwin earthquakes..."). Every header must stand alone on its own line, followed by a blank line, before the bullet points start.
- Absolutely no emojis anywhere in the output.
- Be objective, analytical, and precise. No filler phrases.
- Never hallucinate — every fact must come directly from the provided articles.
- Every article cited must include a working markdown hyperlink to its source URL.
- All three "Today's Top Stories" bullets must be formatted identically — each starting with "- " at column 0.
- NEVER truncate a description with "..." or "Continue reading". Every sentence must be complete.
- All descriptions must be full, grammatically complete sentences. Do not leave any thought unfinished.
- Every Quick Hits bullet must include a markdown hyperlink to its source article.
"""

def seed_briefs():
    for cat in ['global', 'indian', 'technology', 'sports', 'finance']:
        filepath = os.path.join(BRIEFINGS_DIR, f"latest_{cat}.json")
        if not os.path.exists(filepath):
            now_str = datetime.now(timezone.utc).isoformat()
            ist_tz = timezone(timedelta(hours=5, minutes=30))
            now_ist = datetime.now(timezone.utc).astimezone(ist_tz)
            formatted_date = now_ist.strftime('%A, %B %d, %Y, %I:%M:%S %p IST')

            init_text = f"""Live Briefing for: {formatted_date}

# The Headline

- **System Initialized:** The Daily Intelligence Summarizer has successfully booted.
- **Category Channels:** Selected category: {cat.upper()}. Click 'GENERATE BRIEF' to parse live feeds.

# Today's Top Stories

- **Daily Summarizer Active**
  The summarizer is operational and tracking 11 verified news feeds.
  *Why it matters:* Provides highly scannable, zero-fluff news briefs on demand.

# Category Breakdown

### SYSTEM STATUS
- Sector {cat.upper()} is active.
- Tracking feeds: BBC, The Indian Express, The Guardian, TechCrunch, Deccan Herald, Bloomberg, Financial Times, The Verge, Press Trust of India, AP News.

# Quick Hits
- System version 2.0 active.
- Grounded time synchronizer enabled.
- Gemini AI summarization ready."""

            brief_data = {
                "id": "initial",
                "timestamp": now_str,
                "briefing": init_text,
                "articlesCount": 0,
                "articles": []
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(brief_data, f, indent=2, ensure_ascii=False)

def fetch_world_cup_schedule():
    espn_url = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260719&limit=100"
    try:
        req = urllib.request.Request(espn_url, headers={'User-Agent': 'Mozilla/5.0'})
        kwargs = {'timeout': 15}
        if ssl_context:
            kwargs['context'] = ssl_context
        with urllib.request.urlopen(req, **kwargs) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching World Cup schedule: {e}")
        return {"matches": [], "count": 0}

    matches = []
    for event in data.get('events', []):
        comps = event.get('competitions', [{}])
        if not comps:
            continue
        c = comps[0]
        competitors = c.get('competitors', [])
        if len(competitors) < 2:
            continue
        team1 = competitors[0]['team']['shortDisplayName']
        team2 = competitors[1]['team']['shortDisplayName']
        score1 = competitors[0].get('score', '')
        score2 = competitors[1].get('score', '')
        status_obj = c.get('status', {})
        status_type = status_obj.get('type', {})
        status = status_type.get('description', 'Scheduled')
        display_clock = status_obj.get('displayClock', '')
        status_detail = status_type.get('detail', '')
        period = status_obj.get('period', 0)
        date_iso = event.get('date', '')
        venue = c.get('venue', {}).get('fullName', '') if c.get('venue') else ''
        group = c.get('group', {}).get('shortName', '') if c.get('group') else ''

        matches.append({
            "team1": team1,
            "team2": team2,
            "score1": score1,
            "score2": score2,
            "status": status,
            "displayClock": display_clock,
            "statusDetail": status_detail,
            "period": period,
            "date": date_iso,
            "venue": venue,
            "group": group
        })

    matches.sort(key=lambda m: m.get('date', ''))
    return {"matches": matches, "count": len(matches)}





class NewsBriefingHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-api-key')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        response_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # Handle Vercel URL rewrites passing the path via query parameter
        if '__path__' in query:
            path = '/api/' + query['__path__'][0]

        if path == '/api/sources':
            self.send_json(SOURCES)
        elif path == '/api/categories':
            self.send_json(CATEGORIES)
        elif path == '/api/config':
            has_key = is_valid_api_key(os.environ.get('GEMINI_API_KEY'))
            self.send_json({"apiKeyConfigured": has_key})
        elif path == '/api/world-cup':
            self.send_json(fetch_world_cup_schedule())
        elif path == '/api/latest-brief':
            category = query.get('category', ['global'])[0]
            filepath = os.path.join(BRIEFINGS_DIR, f"latest_{category}.json")
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        self.send_json(data)
                except Exception as err:
                    self.send_json({"error": "Failed to read briefing"}, 500)
            else:
                self.send_json({"error": f"Latest briefing for category {category} not found"}, 404)
        # Deleted: /api/story-of-the-day endpoint
        else:
            if path == '/':
                self.path = '/index.html'
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # Handle Vercel URL rewrites passing the path via query parameter
        if '__path__' in query:
            path = '/api/' + query['__path__'][0]

        if path == '/api/generate-brief':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                body = json.loads(post_data) if post_data else {}
            except Exception:
                body = {}

            grounded_time = body.get('groundedTime', datetime.now(timezone.utc).isoformat())
            category = body.get('category', 'global')
            client_key = self.headers.get('x-api-key')
            server_key = os.environ.get('GEMINI_API_KEY')
            api_key = client_key if is_valid_api_key(client_key) else server_key

            try:
                articles = get_filtered_articles(grounded_time)
                filtered_articles = filter_by_category(articles, category)

                parsed_gdt = parse_iso(grounded_time)
                if parsed_gdt:
                    ist_tz = timezone(timedelta(hours=5, minutes=30))
                    parsed_gdt_ist = parsed_gdt.astimezone(ist_tz)
                    formatted_date = parsed_gdt_ist.strftime('%A, %B %d, %Y, %I:%M:%S %p IST')
                else:
                    formatted_date = grounded_time

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

                live_briefing_header = f"Live Briefing for: {formatted_date}"
                if re.search(r'^Live Briefing for:.*$', brief_text, re.MULTILINE):
                    brief_text = re.sub(r'^Live Briefing for:.*$', live_briefing_header, brief_text, flags=re.MULTILINE)
                else:
                    brief_text = f"{live_briefing_header}\n\n{brief_text}"

                brief_data = {
                    "id": "latest",
                    "timestamp": grounded_time,
                    "briefing": brief_text,
                    "articlesCount": len(filtered_articles),
                    "articles": [{
                        "title": a['title'],
                        "sourceName": a['sourceName'],
                        "link": a['link'],
                        "pubDate": a['pubDate']
                    } for a in filtered_articles]
                }

                filepath = os.path.join(BRIEFINGS_DIR, f"latest_{category}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(brief_data, f, indent=2, ensure_ascii=False)

                self.send_json(brief_data)

            except Exception as e:
                print(f"Error in generate-brief: {e}")
                self.send_json({"error": str(e)}, 500)
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

if __name__ == "__main__":
    seed_briefs()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), NewsBriefingHandler) as httpd:
        print(f"Serving news app at http://localhost:{PORT}")
        httpd.serve_forever()
