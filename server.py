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
import traceback

from news_clustering import cluster_articles, rank_clusters, jaccard_similarity, normalize_title, cluster_into_stories
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
    key = key.strip().strip('"').strip("'")
    if not key:
        return False
    # Allow AIzaSy (Gemini API keys), AQ. (Google Cloud OAuth), and similar formats
    if not re.match(r'^[A-Za-z0-9_.-]+$', key):
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
  { "id": "the-print", "name": "The Print", "url": "https://news.google.com/rss/search?q=site:theprint.in", "siteUrl": "https://theprint.in/" },
  { "id": "the-guardian", "name": "The Guardian", "url": "https://www.theguardian.com/international/rss", "siteUrl": "https://www.theguardian.com/international" },
  { "id": "techcrunch", "name": "TechCrunch", "url": "https://techcrunch.com/feed/", "siteUrl": "https://techcrunch.com/" },
  { "id": "scroll", "name": "Scroll.in", "url": "https://feeds.feedburner.com/Scrollin", "siteUrl": "https://scroll.in/latest/" },
  { "id": "deccan-herald", "name": "Deccan Herald", "url": "https://www.deccanherald.com/feed/", "siteUrl": "https://www.deccanherald.com/" },
  { "id": "vox", "name": "Vox", "url": "https://www.vox.com/rss/index.xml", "siteUrl": "https://www.vox.com/" },
  { "id": "cnn", "name": "CNN", "url": "https://news.google.com/rss/search?q=site:cnn.com&hl=en-US&gl=US&ceid=US:en", "siteUrl": "https://edition.cnn.com/" },
  { "id": "reuters", "name": "Reuters", "url": "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en", "siteUrl": "https://www.reuters.com/" },
  { "id": "bloomberg", "name": "Bloomberg", "url": "https://feeds.bloomberg.com/markets/news.rss", "siteUrl": "https://www.bloomberg.com/asia" },
  { "id": "ap-news", "name": "AP News", "url": "https://rsshub.app/apnews/rss", "siteUrl": "https://apnews.com/" },
  { "id": "al-jazeera", "name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "siteUrl": "https://www.aljazeera.com/" },
  { "id": "npr", "name": "NPR", "url": "https://feeds.npr.org/1001/rss.xml", "siteUrl": "https://www.npr.org/" },
  { "id": "ndtv", "name": "NDTV", "url": "https://feeds.feedburner.com/ndtvnews-latest", "siteUrl": "https://www.ndtv.com/" },
  { "id": "the-hindu", "name": "The Hindu", "url": "https://www.thehindu.com/news/feeds/default.rss", "siteUrl": "https://www.thehindu.com/" },
  { "id": "nytimes", "name": "NYT", "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "siteUrl": "https://www.nytimes.com/" },
  { "id": "washington-post", "name": "Washington Post", "url": "http://feeds.washingtonpost.com/rss/world", "siteUrl": "https://www.washingtonpost.com/" },
  { "id": "wired", "name": "Wired", "url": "https://www.wired.com/feed/rss", "siteUrl": "https://www.wired.com/" },
  { "id": "ars-technica", "name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "siteUrl": "https://arstechnica.com/" },
  { "id": "hacker-news", "name": "Hacker News", "url": "https://hnrss.org/frontpage", "siteUrl": "https://news.ycombinator.com/" },
  { "id": "sky-sports", "name": "Sky Sports", "url": "https://www.skysports.com/rss/12040", "siteUrl": "https://www.skysports.com/" }
]

CATEGORIES = [
  { "id": "global",     "name": "Global",     "label": "ALL NEWS",           "icon": "" },
  { "id": "technology", "name": "Technology",  "label": "TECH & INNOVATION",  "icon": "" },
  { "id": "geopolitics", "name": "Geopolitics", "label": "WORLD & POLITICS",  "icon": "" },
  { "id": "science",    "name": "Science",     "label": "SCIENCE & HEALTH",   "icon": "" },
  { "id": "culture",    "name": "Culture",     "label": "CULTURE & ARTS",     "icon": "" },
  { "id": "society",    "name": "Society",     "label": "SOCIETY & LIFESTYLE", "icon": "" },
  { "id": "sports",     "name": "Sports",      "label": "SPORTS",             "icon": "" },
  { "id": "finance",    "name": "Finance",     "label": "MARKETS & ECONOMY",  "icon": "" },
]

SUBCATEGORY_NAMES = [
    "Business, Markets & Economy",
    "Technology & Innovation",
    "Geopolitics & World News",
    "Domestic Politics & Governance",
    "Science, Health & Environment",
    "Sports",
    "Culture, Entertainment & Arts",
    "Lifestyle & Society"
]

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


def assign_subcategory(article):
    text = ((article.get('title', '') or '') + ' ' + (article.get('content', '') or '')).lower()
    for name in SUBCATEGORY_NAMES:
        kws = SUBCATEGORY_KEYWORDS.get(name, [])
        if contains_word_boundary(text, kws):
            return name
    return "Lifestyle & Society"

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

        # Try standard RSS <item> tags first
        rss_items = root.findall('.//item')
        if rss_items:
            for item in rss_items:
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                desc = item.find('description')
                content_enc = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')

                title_text = (title.text if (title is not None and title.text is not None) else "").strip()
                link_text = (link.text if (link is not None and link.text is not None) else "").strip()
                pub_date_text = (pub_date.text if (pub_date is not None and pub_date.text is not None) else "").strip()

                # Prefer content:encoded (full body) over <description> (summary)
                if content_enc is not None and content_enc.text is not None:
                    raw_content = content_enc.text
                elif desc is not None and desc.text is not None:
                    raw_content = desc.text
                else:
                    raw_content = ""
                
                # Strip style and script tag contents first
                raw_content = re.sub(r'<style\b[^>]*>([\s\S]*?)<\/style>', ' ', raw_content, flags=re.IGNORECASE)
                raw_content = re.sub(r'<script\b[^>]*>([\s\S]*?)<\/script>', ' ', raw_content, flags=re.IGNORECASE)
                
                desc_clean = re.sub('<[^<]+?>', '', raw_content)

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
        else:
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            atom_entries = root.findall('.//atom:entry', ns)
            for entry in atom_entries:
                title = entry.find('atom:title', ns)
                link = entry.find('atom:link', ns)
                pub_date_elem = entry.find('atom:published', ns)
                pub_date = pub_date_elem if pub_date_elem is not None else entry.find('atom:updated', ns)
                desc_elem = entry.find('atom:summary', ns)
                desc = desc_elem if desc_elem is not None else entry.find('atom:content', ns)

                title_text = (title.text if (title is not None and title.text is not None) else "").strip()
                link_text = (link.attrib.get('href') if (link is not None) else "").strip()
                pub_date_text = (pub_date.text if (pub_date is not None and pub_date.text is not None) else "").strip()
                desc_text = (desc.text if (desc is not None and desc.text is not None) else "").strip()

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
    if art.get('content'):
        return art
    url = art.get('link')
    if not url:
        return art
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.google.com/',
                'Connection': 'keep-alive'
            }
        )
        kwargs = {'timeout': 5}
        if ssl_context:
            kwargs['context'] = ssl_context
        with urllib.request.urlopen(req, **kwargs) as response:
            html_bytes = response.read(100000)
            html_str = html_bytes.decode('utf-8', errors='ignore')
            match = re.search(r'<meta\s+[^>]*name=["\']description["\']\s+content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
            if not match:
                match = re.search(r'<meta\s+[^>]*content=["\']([^"\']+)["\']\s+name=["\']description["\']', html_str, re.IGNORECASE)
            if not match:
                match = re.search(r'<meta\s+[^>]*property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
            if not match:
                match = re.search(r'<meta\s+[^>]*content=["\']([^"\']+)["\']\s+property=["\']og:description["\']', html_str, re.IGNORECASE)
            if match:
                desc = html.unescape(match.group(1).strip())
                if desc:
                    art['content'] = desc
    except Exception as e:
        print(f"Error scraping content for {url}: {e}")
    if not art.get('content'):
        art['content'] = art.get('title', '')
    return art

def get_filtered_articles(grounded_time_str, max_hours=24.0):
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

        if -1.0 <= diff_hours <= max_hours:
            seen_keys.add(key)
            filtered.append(art)

    # Scrape description for articles with empty content in parallel
    empty_content_articles = [art for art in filtered if not art.get('content')]
    if empty_content_articles:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(empty_content_articles), 10)) as executor:
            list(executor.map(scrape_article_description, empty_content_articles))

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
    
    # Strip style and script tags along with their inner content
    text = re.sub(r'<style\b[^>]*>([\s\S]*?)<\/style>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<script\b[^>]*>([\s\S]*?)<\/script>', ' ', text, flags=re.IGNORECASE)
    
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


def truncate_to_words(text, max_words=250):
    """Truncate text to at most max_words words, cutting at the last complete sentence."""
    if not text:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    # Truncate to max_words then find last sentence boundary
    truncated = ' '.join(words[:max_words])
    # Find last sentence-ending punctuation
    last_end = -1
    for m in re.finditer(r'[.!?]["\u201d\u2019\']?(\s|$)', truncated):
        last_end = m.end()
    if last_end > 0:
        return truncated[:last_end].strip()
    return truncated.strip()


CATEGORY_FILTER_KEYWORDS = {
    "technology": ['tech', 'technology', 'ai', 'artificial intelligence', 'openai', 'microsoft', 'google', 'quantum', 'chip', 'chips', 'semiconductor', 'nvidia', 'robot', 'robotics', 'cyber', 'cybersecurity', 'software', 'hardware', 'app', 'apps', 'startup', 'startups', 'apple', 'meta', 'amazon'],
    "geopolitics": ['treaty', 'summit', 'diplomacy', 'military', 'defense', 'defence', 'election', 'border', 'nato', 'conflict', 'war', 'sanctions', 'foreign', 'president', 'prime minister', 'minister', 'parliament', 'government', 'vote', 'policy', 'law', 'legislation', 'diplomatic', 'ambassador', 'putin', 'biden', 'trump', 'zelensky', 'ukraine', 'russia', 'china', 'iran', 'israel', 'nuclear', 'missile', 'troop', 'army', 'navy'],
    "science": ['climate', 'fda', 'healthcare', 'nasa', 'science', 'scientists', 'research', 'study', 'earthquake', 'tsunami', 'virus', 'vaccine', 'drug', 'treatment', 'patient', 'disease', 'discover', 'planet', 'space', 'climate change', 'global warming', 'emission', 'renewable', 'solar', 'wind'],
    "culture": ['film', 'movie', 'box office', 'award', 'album', 'music', 'gaming', 'game', 'artist', 'art', 'exhibition', 'museum', 'book', 'author', 'celebrity', 'hollywood', 'bollywood', 'entertainment', 'tv', 'television', 'streaming', 'netflix', 'actor', 'actress', 'director'],
    "society": ['travel', 'real estate', 'housing', 'labor', 'union', 'crash', 'accident', 'aviation', 'airport', 'education', 'school', 'university', 'protest', 'strike', 'immigration', 'refugee', 'migrant', 'crime', 'police', 'court', 'rights', 'equality', 'welfare', 'poverty', 'homeless', 'suicide', 'mental health', 'weather', 'rain', 'flood', 'storm', 'cyclone', 'monsoon'],
    "sports": ['match', 'world cup', 'score', 'game', 'games', 'cricket', 'football', 'soccer', 'player', 'players', 'transfer', 'injury', 'league', 'tennis', 'olympics', 'olympic', 'athlete', 'athletes', 'championship', 'tournament', 'final', 'semi-final', 'win', 'won', 'defeat', 'lost', 'cup', 'goal', 'fifa', 'nba', 'nfl'],
    "finance": ['stock', 'stocks', 'market', 'markets', 'economy', 'economic', 'rate', 'rates', 'inflation', 'gdp', 'merger', 'mergers', 'earnings', 'fed', 'layoff', 'layoffs', 'funding', 'ipo', 'crypto', 'shares', 'gold', 'oil', 'price', 'prices', 'billion', 'million', 'deal', 'finance', 'fiscal', 'revenue', 'profit', 'losses', 'securities', 'dividend', 'bank', 'banking', 'loan', 'debt', 'budget']
}


def filter_by_category(articles, category):
    if category == 'global':
        return articles

    filtered = []
    kws = CATEGORY_FILTER_KEYWORDS.get(category, [])

    for art in articles:
        text = ((art.get('title', '') or '') + ' ' + (art.get('content', '') or '')).lower()
        if contains_word_boundary(text, kws):
            filtered.append(art)

    return filtered


def get_pub_time(art):
    dt = parse_date(art.get('pubDate', ''))
    return dt.timestamp() if dt else 0


SOURCE_AUTHORITY = {
    'bbc': 3, 'reuters': 3, 'ap-news': 3, 'nytimes': 3, 'washington-post': 3,
    'bloomberg': 3, 'the-guardian': 3, 'cnn': 2, 'npr': 2, 'al-jazeera': 2,
    'wired': 2, 'ars-technica': 2, 'techcrunch': 2, 'vox': 2,
    'indian-express': 2, 'the-hindu': 2, 'ndtv': 2, 'deccan-herald': 2,
    'the-print': 2, 'scroll': 1, 'sky-sports': 1, 'hacker-news': 1
}

URGENCY_KW_SCORE = [
    ('breaking', 2.0), ('crisis', 1.8), ('emergency', 1.8), ('confirmed', 1.5),
    ('developing', 1.5), ('death', 1.5), ('deaths', 1.5), ('attack', 1.5),
    ('war', 1.8), ('crash', 1.5), ('disaster', 1.8), ('killed', 1.8),
    ('injured', 1.5), ('collapse', 1.5), ('warning', 1.2), ('urgent', 2.0),
    ('explosion', 1.8), ('strike', 1.3), ('military', 1.0), ('nuclear', 1.5),
    ('evacuate', 1.5), ('evacuation', 1.5), ('catastrophe', 2.0), ('fatal', 1.8),
    ('deadly', 1.8), ('critical', 1.3), ('halt', 1.0), ('suspend', 1.0),
    ('recall', 1.0), ('warning', 1.2), ('sanction', 1.2), ('verdict', 1.0),
    ('indict', 1.5), ('arrest', 1.0), ('ban', 1.0), ('approves', 0.8),
    ('launch', 0.6), ('unveils', 0.6), ('releases', 0.5), ('surge', 0.8),
    ('plunge', 0.8), ('record', 0.7), ('breakthrough', 1.2), ('discover', 0.8)
]


def compute_significance(article, grounded_dt):
    score = 0.0

    source_id = article.get('sourceId', '')
    authority = SOURCE_AUTHORITY.get(source_id, 1)
    score += authority * 0.8

    pub_dt = parse_date(article.get('pubDate', ''))
    if pub_dt and grounded_dt:
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        diff_hours = (grounded_dt - pub_dt).total_seconds() / 3600.0
        if diff_hours <= 1:
            score += 2.5
        elif diff_hours <= 3:
            score += 2.0
        elif diff_hours <= 6:
            score += 1.5
        elif diff_hours <= 12:
            score += 1.0
        elif diff_hours <= 18:
            score += 0.5
        else:
            score += 0.2

    title_lower = (article.get('title', '') or '').lower()
    content_lower = (article.get('content', '') or '').lower()
    text = title_lower + ' ' + content_lower
    kw_score = 0.0
    for kw, val in URGENCY_KW_SCORE:
        if kw in text:
            kw_score += val
    score += min(kw_score, 2.5)

    score = max(0.0, min(score, 10.0))
    return round(score, 1)


def compute_article_significance(articles, grounded_dt):
    if not articles:
        return articles

    clusters = cluster_articles(articles)
    cluster_coverage = {}
    for cluster in clusters:
        rep_title = cluster.get('representative_title', '')
        source_count = cluster.get('source_count', 1)
        for art in cluster.get('articles', []):
            key = art.get('link') or art.get('title', '')
            cluster_coverage[key] = source_count

    for art in articles:
        base_score = compute_significance(art, grounded_dt)
        key = art.get('link') or art.get('title', '')
        coverage_bonus = cluster_coverage.get(key, 1)
        if coverage_bonus >= 3:
            base_score += 1.5
        elif coverage_bonus >= 2:
            base_score += 0.8
        base_score = max(0.0, min(base_score, 10.0))
        art['significance'] = round(base_score, 1)

    return articles


def _dedup_articles_by_similarity(articles, threshold=0.4):
    if not articles:
        return []
    deduped = []
    seen_tokens = []
    for art in articles:
        tokens, _, _ = normalize_title(art.get('title', ''))
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

    ranked_deduped.sort(key=get_pub_time, reverse=True)

    headline_articles = ranked_deduped[:3]
    headline_ids = set(id(a) for a in headline_articles)

    top_candidates = []
    if ranked:
        for cluster in ranked:
            for art in cluster["articles"]:
                if id(art) not in headline_ids:
                    top_candidates.append(art)
                    if len(top_candidates) >= 3:
                        break
            if len(top_candidates) >= 3:
                break

    if not top_candidates:
        top_candidates = [a for a in ranked_deduped if id(a) not in headline_ids][:3]

    top_story_articles = top_candidates[:3]
    top_ids = set(id(a) for a in top_story_articles)

    remaining = [a for a in ranked_deduped if id(a) not in headline_ids and id(a) not in top_ids]

    if category == 'homepage':
        def make_homepage_headline_bullet(art):
            raw_content = art.get('content', '') or ''
            cleaned = clean_content(raw_content)
            brief = summarize_content(cleaned, art.get('title', ''), ssl_context, HF_API_TOKEN)
            return f"- {brief}"

        headline_bullets = []
        for a in headline_articles[:5]:
            headline_bullets.append(make_homepage_headline_bullet(a))
        headline_text = "\n".join(headline_bullets) if headline_bullets else "- No critical headlines at this moment."

        top_stories_list = []
        for a in top_story_articles[:3]:
            raw_content = a.get('content', '') or ''
            cleaned = clean_content(raw_content)
            brief = summarize_content(cleaned, a.get('title', ''), ssl_context, HF_API_TOKEN)
            why = extract_why_it_matters(raw_content, a.get('title', '')) or "Critical security and operational updates are ongoing."
            top_stories_list.append(f"{a.get('title', '')}\n{brief} Why it matters: {why}")
        top_stories_text = "\n\n".join(top_stories_list) if top_stories_list else "No top stories identified for this session."

        cat_grouped = {name: [] for name in SUBCATEGORY_NAMES}
        for a in remaining:
            text = (a.get('title', '') + " " + (a.get('content', '') or '')).lower()
            matched = False
            for cat_name in SUBCATEGORY_NAMES:
                kws = SUBCATEGORY_KEYWORDS.get(cat_name, [])
                if contains_word_boundary(text, kws):
                    cat_grouped[cat_name].append(a)
                    matched = True
                    break
            if not matched:
                cat_grouped["Lifestyle & Society"].append(a)

        for cat_name in SUBCATEGORY_NAMES:
            cat_grouped[cat_name] = _dedup_articles_by_similarity(cat_grouped[cat_name])

        breakdown_list = []
        for cat_name in SUBCATEGORY_NAMES:
            arts = cat_grouped[cat_name]
            if arts:
                breakdown_list.append(cat_name)
                for a in arts[:4]:
                    raw_content = a.get('content', '') or ''
                    cleaned = clean_content(raw_content)
                    brief = summarize_content(cleaned, a.get('title', ''), ssl_context, HF_API_TOKEN)
                    breakdown_list.append(brief)
                breakdown_list.append("")
        breakdown_text = "\n".join(breakdown_list).strip()

        quick_hits_list = []
        quick_source = remaining[-4:] if len(remaining) > 4 else remaining
        for a in quick_source:
            raw_content = a.get('content', '') or ''
            cleaned = clean_content(raw_content)
            brief = summarize_content(cleaned, a.get('title', ''), ssl_context, HF_API_TOKEN)
            quick_hits_list.append(f"Fact update: {brief}")
        quick_hits_text = "\n".join(quick_hits_list) if quick_hits_list else "No additional stories in this cycle."

        return f"""Live Briefing for: {formatted_date}

The Headline
{headline_text}

Today's Top Stories
{top_stories_text}

{breakdown_text}

Quick Hits
{quick_hits_text}"""

    def make_article_bullet(art, detail_level="brief"):
        raw_content = art.get('content', '') or ''
        cleaned = clean_content(raw_content)
        brief = summarize_content(cleaned, art.get('title', ''), ssl_context, HF_API_TOKEN)
        link = art.get('link', '')
        source = art.get('sourceName', '')
        if detail_level == "brief":
            return f"- **{art.get('title', '')}** ([{source}]({link}))\n  {brief}"
        else:
            why = extract_why_it_matters(raw_content, art.get('title', ''))
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

    cat_grouped = {name: [] for name in SUBCATEGORY_NAMES}
    for a in remaining:
        text = (a.get('title', '') + " " + (a.get('content', '') or '')).lower()
        matched = False
        for cat_name in SUBCATEGORY_NAMES:
            kws = SUBCATEGORY_KEYWORDS.get(cat_name, [])
            if contains_word_boundary(text, kws):
                cat_grouped[cat_name].append(a)
                matched = True
                break
        if not matched:
            cat_grouped["Lifestyle & Society"].append(a)

    for cat_name in SUBCATEGORY_NAMES:
        cat_grouped[cat_name] = _dedup_articles_by_similarity(cat_grouped[cat_name])

    breakdown_bullets = []
    for cat_name in SUBCATEGORY_NAMES:
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

def build_story_prompt(story):
    category = story.get('category', 'General')
    primary_headline = story.get('primary_headline', '')
    sources = story.get('sources', [])

    sources_text = ""
    for src in sources:
        ts = src.get('published_at', '')
        content = src.get('content', '') or ''
        sources_text += f"Source: {src['source_name']} | Published: {ts}\n{content}\n---\n"

    prompt = f"""You are a news editor writing a single synthesized brief for a story, based on multiple source articles covering the same event.

TASK:
Write one cohesive brief of 150-200 words that synthesizes the information across ALL provided sources below. Do not summarize each source separately — merge the facts into one unified narrative, as if you are the most well-informed reporter on this story.

RULES:
- If sources agree on a fact, state it plainly once.
- If sources add different details (numbers, quotes, context, reactions), weave them in — don't repeat the same fact from each source.
- If sources conflict on a fact (e.g. different casualty counts, different figures), note the discrepancy briefly rather than picking one arbitrarily.
- Do not attribute every sentence to a specific outlet (no "According to Reuters..."). Write it as a clean editorial brief, not a source-by-source roundup.
- Lead with the most important, most recent development. Background/context comes after, only if space allows.
- No filler openers ("In a significant development..."). Start directly with the news.
- Target length: 150-200 words. Do not pad to hit the minimum — if the sources genuinely don't support 150 words of substance, write less rather than fabricate detail.
- Do not editorialize or add opinion not supported by the sources.

STORY CATEGORY: {category}
PRIMARY HEADLINE: {primary_headline}

SOURCES:
{sources_text}

Output only the brief text. No headers, no preamble, no source list."""
    return prompt


def call_gemini_structured(api_key, prompt, attempt_label="attempt"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "object",
                "properties": {
                    "brief": {"type": "string"},
                    "word_count": {"type": "integer"}
                },
                "required": ["brief", "word_count"]
            }
        }
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            res_data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"[Gemini {attempt_label}] HTTP {e.code}: {body[:200]}")
        if e.code in (401, 403):
            print(f"[Gemini {attempt_label}] *** API KEY REJECTED ({e.code}) — check GEMINI_API_KEY env var is a valid Gemini API key ***")
        elif e.code == 429:
            retry_after = 2 ** (attempt_label.count('retry'))
            print(f"[Gemini {attempt_label}] *** RATE LIMITED (429) — will retry in ~{retry_after}s ***")
        raise
    except Exception as e:
        print(f"[Gemini {attempt_label}] Network/HTTP error: {e}")
        raise

    if 'candidates' not in res_data or not res_data['candidates']:
        reason = res_data.get('promptFeedback', {}).get('blockReason', 'unknown')
        print(f"[Gemini {attempt_label}] No candidates returned. blockReason={reason}, full={json.dumps(res_data)[:500]}")
        raise ValueError(f"Gemini returned no candidates (blockReason={reason})")

    try:
        raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError) as e:
        print(f"[Gemini {attempt_label}] Unexpected response structure: {json.dumps(res_data)[:500]}")
        raise

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"[Gemini {attempt_label}] JSON parse failed: {e}. Raw text: {raw_text[:500]}")
        raise

    brief = parsed.get('brief', '')
    wc = parsed.get('word_count', 0)
    print(f"[Gemini {attempt_label}] Success — brief={len(brief)} chars, reported_word_count={wc}")
    return brief, wc


def validate_brief(brief_text):
    if not brief_text or not brief_text.strip():
        return False, "empty brief"
    wc = len(brief_text.strip().split())
    if wc < 130 or wc > 220:
        return False, f"word count {wc} out of range (130-220)"
    return True, wc


def _fallback_extractive(text, max_sentences=2):
    """Short extractive fallback: clean text, take first max_sentences complete sentences."""
    if not text:
        return "No details available for this story."
    text = clean_content(text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if not sentences:
        return text[:500] if len(text) > 500 else text
    taken = []
    for s in sentences[:max_sentences]:
        taken.append(s)
    result = " ".join(taken)
    return result


def _validate_or_trim(brief_text, max_words=220):
    """Validate word count. If over max, trim to max_words. Returns (text, word_count)."""
    if not brief_text or not brief_text.strip():
        return "Brief unavailable for this story.", 5
    wc = len(brief_text.strip().split())
    if wc <= max_words:
        return brief_text.strip(), wc
    trimmed = " ".join(brief_text.strip().split()[:max_words])
    return trimmed, max_words


def _validate_brief_minmax(brief_text, min_words=130, max_words=220):
    """Validate brief is within min_words..max_words. If over max, trim.
    Returns (text, word_count, is_valid) where is_valid=False means below minimum."""
    if not brief_text or not brief_text.strip():
        return "Brief unavailable for this story.", 5, False
    wc = len(brief_text.strip().split())
    if wc < min_words:
        return brief_text.strip(), wc, False
    if wc <= max_words:
        return brief_text.strip(), wc, True
    trimmed = " ".join(brief_text.strip().split()[:max_words])
    return trimmed, max_words, True


def generate_story_brief(story, api_key, ssl_ctx, hf_token=""):
    prompt = build_story_prompt(story)
    story_label = story.get('story_id', 'unknown')
    headline = story.get('primary_headline', '?')[:80]

    print(f"[BRIEF] === Story {story_label}: \"{headline}\" ===")
    print(f"[BRIEF] {story_label}: api_key={'SET (' + api_key[:8] + '...)' if api_key else 'NOT SET'}")

    def _call_with_retry(api_key, prompt, label):
        """Call Gemini with one 429 retry after 1s backoff."""
        import time
        last_exc = None
        for retry in range(2):
            try:
                return call_gemini_structured(api_key, prompt, attempt_label=f"{label} retry={retry}")
            except urllib.error.HTTPError as e:
                if e.code == 429 and retry == 0:
                    print(f"[BRIEF] {story_label}: 429 on {label}, one retry in 1s...")
                    time.sleep(1)
                    last_exc = e
                    continue
                raise
        if last_exc:
            raise last_exc

    if api_key:
        # Attempt 1: Gemini with structured output
        print(f"[BRIEF] {story_label}: === GEMINI ATTEMPT 1 START ===")
        try:
            brief_text, wc = _call_with_retry(api_key, prompt, f"story={story_label} attempt=1")
            print(f"[BRIEF] {story_label}: Gemini attempt 1 returned raw brief={repr(brief_text[:120])}, wc={wc}")
            valid, msg = validate_brief(brief_text)
            print(f"[BRIEF] {story_label}: Gemini attempt 1 validation: valid={valid}, msg={msg}")
            if valid:
                print(f"[BRIEF] {story_label}: === GEMINI ATTEMPT 1 SUCCESS ({wc} words) ===")
                return brief_text.strip(), wc
            print(f"[BRIEF] {story_label}: === GEMINI ATTEMPT 1 VALIDATION FAILED ({msg}). RETRYING... ===")
            # Retry with appended note
            retry_prompt = prompt + f"\n\nYour previous attempt was {wc} words. Strictly target 150-200 words this time."
            print(f"[BRIEF] {story_label}: === GEMINI ATTEMPT 2 START ===")
            brief_text, wc = _call_with_retry(api_key, retry_prompt, f"story={story_label} attempt=2")
            print(f"[BRIEF] {story_label}: Gemini attempt 2 returned raw brief={repr(brief_text[:120])}, wc={wc}")
            valid, msg = validate_brief(brief_text)
            print(f"[BRIEF] {story_label}: Gemini attempt 2 validation: valid={valid}, msg={msg}")
            if valid:
                print(f"[BRIEF] {story_label}: === GEMINI ATTEMPT 2 SUCCESS ({wc} words) ===")
                return brief_text.strip(), wc
            # Per spec Step 4: accept 2nd attempt even if invalid (don't block the update)
            print(f"[BRIEF] {story_label}: === GEMINI ATTEMPT 2 VALIDATION FAILED ({msg}) — ACCEPTING OUTPUT PER SPEC ===")
            print(f"[BRIEF] {story_label}: === GEMINI ATTEMPT 2 ACCEPTED ({wc} words, below 130 minimum) ===")
            return brief_text.strip(), wc
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else ''
            print(f"[BRIEF] {story_label}: === GEMINI HTTP ERROR {e.code} ===")
            if body:
                print(f"[BRIEF] {story_label}: HTTPError body: {body[:500]}")
        except Exception as e:
            print(f"[BRIEF] {story_label}: === GEMINI EXCEPTION: {type(e).__name__}: {e} ===")
            import traceback
            traceback.print_exc()
    else:
        print(f"[BRIEF] {story_label}: === NO API KEY — SKIPPING GEMINI entirely ===")

    # Fallback: BART summarizer on primary source content only (not multi-article dump)
    primary_content = story.get('primary_source', {}).get('content', '') or ''
    primary_content_len = len(primary_content)
    print(f"[BRIEF] {story_label}: === FALLBACK PATH: primary_content_len={primary_content_len} chars ===")
    if primary_content and len(primary_content.strip()) > 30:
        try:
            print(f"[BRIEF] {story_label}: === BART FALLBACK START ===")
            brief = summarize_content(primary_content, story.get('primary_headline', ''), ssl_ctx, hf_token)
            print(f"[BRIEF] {story_label}: BART returned raw brief len={len(brief)} chars, preview={repr(brief[:120])}")
            if brief and len(brief.strip()) > 50:
                brief, wc = _validate_or_trim(brief, max_words=220)
                print(f"[BRIEF] {story_label}: === BART FALLBACK ACCEPTED ({wc} words) ===")
                return brief, wc
            else:
                print(f"[BRIEF] {story_label}: BART returned too-short text ({len(brief.strip())} chars) — falling through to extractive")
        except Exception as e:
            print(f"[BRIEF] {story_label}: === BART FALLBACK EXCEPTION: {type(e).__name__}: {e} ===")
            import traceback
            traceback.print_exc()
    else:
        print(f"[BRIEF] {story_label}: primary_content too short ({primary_content_len} chars) — skipping BART")

    # Last resort: short extractive from primary source only
    if primary_content and len(primary_content.strip()) > 30:
        print(f"[BRIEF] {story_label}: === EXTRACTIVE FALLBACK START ===")
        # Try progressively more sentences to get as much content as possible
        for max_sent in [2, 5, 10]:
            brief = _fallback_extractive(primary_content, max_sentences=max_sent)
            wc = len(brief.split())
            print(f"[BRIEF] {story_label}: extractive ({max_sent} sentences): {wc} words")
            if wc >= 30:
                break
        brief, wc = _validate_or_trim(brief, max_words=220)
        print(f"[BRIEF] {story_label}: === EXTRACTIVE FALLBACK RESULT ({wc} words): {repr(brief[:120])} ===")
        return brief, wc

    print(f"[BRIEF] {story_label}: === ALL PATHS EXHAUSTED — returning unavailable ===")
    return "Brief unavailable for this story.", 5


def get_system_prompt(formatted_date, category):
    return f"""You are my executive daily news summarizer. Your job is to extract the absolute latest, breaking updates from today from the provided source articles and present them in a highly scannable, zero-fluff briefing.

Grounded Timestamp (Source of Truth): {formatted_date}
Category Focus: {category.upper()}

=== STEP 1 — RECENCY FILTER (mechanical, not interpretive) ===
For every candidate story, identify its explicit published timestamp from the source. Compare it against the grounded time above.
- Discard any story whose timestamp is more than 24 hours before the grounded time.
- If a source does not show a clear timestamp, do not include it.
- Do not include recap articles, "week in review" pieces, analysis of older events, or evergreen content.
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
- A detailed and elaborate editor's brief of approximately 150-200 words (750-1000 characters), consisting of 4-6 substantive sentences summarizing the core facts of the source article.
- No emojis anywhere in the output.

Format (use exactly double newlines around header, and start list items with "- "):
- **[Story Headline]** ([Source Name](article URL))
  [Elaborate editor's brief: 4-6 sentences, approx 150-200 words. Detail what happened, who is involved, key figures, and immediate consequences.]


# Today's Top Stories

Identify the 3 single most important stories from the last 24 hours. For each:
- Lead with the headline in bold, followed by a hyperlink to the source.
- Write a detailed and elaborate editor's brief of approximately 150-200 words (750-1000 characters), consisting of 4-6 substantive sentences covering the core facts, context, and key details.
- Explicitly state "Why it matters:" followed by a substantive explanation of why the story is important, its significance, and the underlying stakes (3-4 sentences, approx 200-300 words). Do NOT just repeat facts; explain the impact and why this news is critical.

Format (all items must start flush with "- " at the same indent level):
- **[Story Headline]** ([Source Name](article URL))
  [Elaborate editor's brief: 2-3 sentences, approx 300 characters. Full context, key details, numbers, and named actors.]
  *Why it matters:* [Substantive explanation of why this story matters, its importance, stakes, and broader implications. 2-3 sentences.]


# Category Breakdown

For each relevant category below, list 5 to 10 articles from the last 24 hours. If a category has no qualifying articles, omit its H3 header entirely. Each item must:
- Start with the headline in bold followed by a hyperlink to the article source.
- Include a detailed and elaborate editor's brief of approximately 150-200 words (750-1000 characters, 4-6 sentences) below the headline providing context, key facts, and figures.
- No single-sentence bullets — every item requires substantive detail.
- No emojis.

Format (H3 headers must be capitalized exactly as written, e.g. "### Sports"):
### [Category Name]

- **[Headline]** ([Source Name](article URL))
  [Elaborate editor's brief: 4-6 sentences, approx 150-200 words.]

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

def get_homepage_system_prompt(formatted_date):
    return f"""You are my executive daily news summarizer. Your job is to extract the absolute latest, breaking updates from today from the provided source websites and present them in a highly scannable, zero-fluff briefing.

STEP 1 — ESTABLISH GROUND TRUTH TIME (mandatory, do this first):
State this grounded timestamp explicitly at the very top of your output as "Live Briefing for: {formatted_date}" — this is your source of truth for all filtering below.

STEP 2 — RECENCY FILTER (mechanical, not interpretive):
For every candidate story, identify its explicit published timestamp from the source. Compare it against the grounded time.
- Discard any story whose timestamp is more than 12 hours before the grounded time.
- If a source doesn't show a clear timestamp, do not include it — don't assume recency.
- Do not include recap articles, "week in review" pieces, analysis of older events, or evergreen content, even if republished or resurfaced today.
- This 12-hour rule applies uniformly across every section below — there is no separate 24-hour allowance anywhere in this brief.

CATEGORIES TO TRACK:
Scan the sources specifically for live news related to these core areas:
- Business, Markets & Economy (stock indices, commodities, crypto, forex, yields, M&A, earnings, leadership, layoffs, inflation, central bank rates, employment, GDP, funding, IPOs)
- Technology & Innovation (product launches, hardware specs, software updates, AI, robotics, quantum computing, cloud, data breaches, antitrust, privacy regulation)
- Geopolitics & World News (treaties, summits, diplomacy, military updates, defense spending, global elections)
- Domestic Politics & Governance (new laws, tax changes, public policy, polling, debates, voting results, major court rulings, high-profile trials)
- Science, Health & Environment (weather events, green energy, climate policy, treatments, FDA approvals, healthcare policy, space exploration)
- Sports (scores, league rankings, transfers, player movements, injuries)
- Culture, Entertainment & Arts (film releases, box office, award shows, album drops, tours, gaming studio releases, esports)
- Lifestyle & Society (city planning, transit, real estate, remote work trends, labor, unions, travel disruptions, hospitality trends)

FORMATTING RULES:
Structure the daily briefing exactly like this:

Live Briefing for: {formatted_date}

The Headline

For each of the 5 to 8 biggest breaking stories from the last 12 hours, write a detailed bullet with a 150-200 word (4-6 sentence) editor's brief explaining what happened, who is involved, key figures, and immediate consequences. Use concise bullet points. Each bullet starts with "- ".

Today's Top Stories

Identify the 3 most important stories from the last 12 hours overall. For each, give a 150-200 word (4-6 sentence) detailed brief and explicitly state "Why it matters:" with a 2-3 sentence explanation.

Category Breakdown

Group remaining breaking news under the categories above. Concise bullet points per update. Each bullet should implicitly reflect a story within the 12-hour window — if you're unsure of timing, leave it out.

Quick Hits

A short bulleted list of immediate facts from the last 12 hours: overnight match scores, specific product release dates, major daily market movements.

TONE & CONSTRAINTS:
- Apply the 12-hour rule from Step 2 with no exceptions — there is no 24-hour fallback anywhere in this brief.
- Be objective, concise, and analytical.
- No filler introductions ("Here is your daily news") or conclusions.
- Never hallucinate; stick strictly to facts found in live sources with verifiable timestamps.
- If a category has no breaking news within the window, omit it entirely — don't write "No updates."
- Every article must cite its source name.
- Do NOT output markdown hyperlinks. Use plain text only with source names in parentheses, e.g. "Story headline (BBC News)".
"""

def seed_briefs():
    for cat in ['homepage', 'global', 'technology', 'geopolitics', 'science', 'culture', 'society', 'sports', 'finance']:
        filepath = os.path.join(BRIEFINGS_DIR, f"latest_{cat}.json")
        if not os.path.exists(filepath):
            now_str = datetime.now(timezone.utc).isoformat()
            ist_tz = timezone(timedelta(hours=5, minutes=30))
            now_ist = datetime.now(timezone.utc).astimezone(ist_tz)
            formatted_date = now_ist.strftime('%A, %B %d, %Y, %I:%M:%S %p IST')

            brief_data = {
                "id": "initial",
                "timestamp": now_str,
                "articlesCount": 0,
                "stories": []
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
            api_key = client_key if is_valid_api_key(client_key) else (server_key if is_valid_api_key(server_key) else None)

            try:
                # Step 1: Fetch + recency filter (12h for homepage, 24h for category feeds)
                articles = get_filtered_articles(grounded_time, max_hours=(12.0 if category == 'homepage' else 24.0))

                if not articles:
                    self.send_json({
                        "id": "latest",
                        "timestamp": grounded_time,
                        "articlesCount": 0,
                        "stories": []
                    })
                    return

                # Step 2: Cluster into story objects (single pass, all categories)
                stories = cluster_into_stories(articles)

                # Step 3: Generate brief for each story in parallel
                brief_cache = {}
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    fut_map = {}
                    for story in stories:
                        fut = pool.submit(generate_story_brief, story, api_key, ssl_context, HF_API_TOKEN)
                        fut_map[fut] = story
                    for future in concurrent.futures.as_completed(fut_map):
                        story = fut_map[future]
                        try:
                            brief_text, word_count = future.result()
                            brief_cache[story["story_id"]] = {
                                "brief": truncate_to_words(clean_content(brief_text), 200),
                                "brief_word_count": word_count
                            }
                        except Exception as e:
                            print(f"Brief generation failed for story {story['story_id']}: {e}")
                            brief_cache[story["story_id"]] = {
                                "brief": "Brief could not be generated for this story.",
                                "brief_word_count": 0
                            }

                # Step 3b: Final validation — log every brief's word count
                for sid, cached in brief_cache.items():
                    bw = cached.get("brief_word_count", 0)
                    btxt = cached.get("brief", "")
                    btxt_wc = len(btxt.split()) if btxt else 0
                    if bw < 130:
                        print(f"[FINAL] story={sid}: brief_word_count={bw}, actual_wc={btxt_wc} — BELOW 130-WORD MINIMUM, preview={repr(btxt[:80])}")
                    elif bw > 220:
                        print(f"[FINAL] story={sid}: brief_word_count={bw} — OVER 220-WORD MAXIMUM")

                # Step 4: Assemble story objects with briefs attached
                story_objects = []
                for story in stories:
                    cached = brief_cache.get(story["story_id"], {})
                    story_obj = {
                        "story_id": story["story_id"],
                        "category": story["category"],
                        "primary_headline": story["primary_headline"],
                        "primary_source": story["primary_source"],
                        "sources": [
                            {
                                "source_name": s["source_name"],
                                "headline": s["headline"],
                                "published_at": s["published_at"],
                                "url": s["url"]
                            }
                            for s in story["sources"]
                        ],
                        "source_count": story["source_count"],
                        "total_count": story["total_count"],
                        "combined_score": story["combined_score"],
                        "brief": cached.get("brief", ""),
                        "brief_word_count": cached.get("brief_word_count", 0)
                    }
                    story_objects.append(story_obj)

                brief_data = {
                    "id": "latest",
                    "timestamp": grounded_time,
                    "articlesCount": len(articles),
                    "stories": story_objects
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
    # Diagnose API key at startup
    server_key = os.environ.get('GEMINI_API_KEY')
    if server_key and is_valid_api_key(server_key):
        print(f"[STARTUP] GEMINI_API_KEY found and passes format check ({server_key[:8]}...{server_key[-4:]})")
        print(f"[STARTUP] WARNING: Key will be tested on first API call — if it fails with 401/403, replace it with a valid Gemini API key (starts with AIzaSy)")
    elif server_key:
        print(f"[STARTUP] GEMINI_API_KEY present but FAILS format check (key={server_key[:16]}...)")
        print(f"[STARTUP] Valid Gemini API keys start with AIzaSy or are URL-safe tokens >= 10 chars")
    else:
        print(f"[STARTUP] GEMINI_API_KEY not set — all briefs will use BART/extractive fallback")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), NewsBriefingHandler) as httpd:
        print(f"Serving news app at http://localhost:{PORT}")
        httpd.serve_forever()
