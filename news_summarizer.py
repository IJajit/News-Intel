import re
import json
import urllib.request
import urllib.error
import html

HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

CONTINUE_READING_RE = re.compile(r'\bContinue\s+reading\b.*$', re.IGNORECASE)
TRAILING_ELLIPSIS_RE = re.compile(r'(\.{2,}|\u2026)\s*$')
HTML_TAGS_RE = re.compile(r'<[^>]+>')
WHITESPACE_RE = re.compile(r'\s+')

ANALYTICAL_KEYWORDS = [
    'because', 'significant', 'critical', 'threatens', 'threatened',
    'could', 'will', 'means', 'marks', 'signals', 'underscores',
    'highlights', 'raises', 'sparks', 'triggers', 'prompts',
    'impact', 'implication', 'consequence', 'concern', 'warning',
    'deadly', 'devastating', 'unprecedented', 'historic', 'major'
]


def _clean_rss_artifacts(text):
    if not text:
        return ''
    text = html.unescape(text)
    
    # Strip style and script tags along with their inner content
    text = re.sub(r'<style\b[^>]*>([\s\S]*?)<\/style>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<script\b[^>]*>([\s\S]*?)<\/script>', ' ', text, flags=re.IGNORECASE)
    
    text = HTML_TAGS_RE.sub(' ', text)
    text = WHITESPACE_RE.sub(' ', text).strip()
    text = CONTINUE_READING_RE.sub('', text).strip()
    text = TRAILING_ELLIPSIS_RE.sub('', text).strip()
    text = WHITESPACE_RE.sub(' ', text).strip()
    return text


def _split_sentences(text):
    raw = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in raw if len(s.strip()) > 10]


def _extractive_fallback(text):
    if not text:
        return "No details available for this story."

    text = _clean_rss_artifacts(text)
    sentences = _split_sentences(text)
    if not sentences:
        return text[:800] if len(text) > 800 else text

    # Build a detailed multi-sentence brief — keep adding sentences until we have
    # at least 1200 characters or we've used up to 14 sentences.
    result = sentences[0]
    for s in sentences[1:14]:
        result = result + " " + s
        if len(result) >= 1200:
            break

    return result


def extract_why_it_matters(content, title):
    if not content:
        return None

    text = _clean_rss_artifacts(content)
    sentences = _split_sentences(text)
    if not sentences:
        return None

    lower_sentences = [s.lower() for s in sentences]
    scored = []
    for i, (orig, low) in enumerate(zip(sentences, lower_sentences)):
        score = 0
        for kw in ANALYTICAL_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', low):
                score += 1
        if len(orig.split()) > 8:
            scored.append((score, i, orig))

    if scored:
        scored.sort(key=lambda x: (-x[0], -x[1]))
        best = scored[0][2]
        if len(best.split()) > 6:
            return best

    last = sentences[-1]
    if len(last.split()) > 6:
        return last

    return None


def _call_hf_inference(text, ssl_ctx, hf_token=""):
    if not hf_token:
        return None
    if not text or len(text.strip()) < 30:
        return None

    payload = {
        "inputs": text,
        "parameters": {
            "max_length": 800,
            "min_length": 300,
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


def summarize_content(content, title, ssl_ctx, hf_token=""):
    if not content:
        return "No details available for this story."

    clean = _clean_rss_artifacts(content)
    word_count = len(clean.split())

    if word_count < 30:
        return clean

    hf_result = _call_hf_inference(clean, ssl_ctx, hf_token)
    if hf_result and len(hf_result) >= 100:
        hf_result = WHITESPACE_RE.sub(' ', hf_result).strip()
        sentence_count = len(re.findall(r'[.!?]+', hf_result))
        if 1 <= sentence_count <= 10:
            return hf_result

    fallback = _extractive_fallback(clean)
    return fallback
