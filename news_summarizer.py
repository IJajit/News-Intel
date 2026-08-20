import re
import json
import urllib.request
import urllib.error
import html
import os

CONTINUE_READING_RE = re.compile(r'\bContinue\s+reading\b.*$', re.IGNORECASE)
TRAILING_ELLIPSIS_RE = re.compile(r'(\.{2,}|\u2026)\s*$')
HTML_TAGS_RE = re.compile(r'<[^>]+>')
WHITESPACE_RE = re.compile(r'\s+')

# Simple in-memory cache to prevent duplicate Gemini calls
SUMMARY_CACHE = {}

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


def _structured_fallback(text, title=""):
    """
    Structured fallback when Gemini API key is missing or encounters issues.
    Constructs a clean 3-part brief from RSS content.
    """
    clean = _clean_rss_artifacts(text)
    sentences = _split_sentences(clean)
    
    if not sentences:
        bg = clean[:300] if clean else "No prior context available."
        kd = [title] if title else ["No detailed key developments recorded."]
        io = "Story details will update as live agency feeds update."
    else:
        bg = sentences[0]
        kd = sentences[1:4] if len(sentences) > 1 else [sentences[0]]
        io = sentences[-1] if len(sentences) > 4 else "This development remains under active coverage."

    return {
        "context_background": bg,
        "key_developments": kd,
        "impact_outlook": io
    }


def _call_gemini_api(text, title="", gemini_key=""):
    api_key = gemini_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(dotenv_path):
            with open(dotenv_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GEMINI_API_KEY='):
                        api_key = line.split('=', 1)[1].strip('\'"')
                        break
    if not api_key:
        return None

    clean = _clean_rss_artifacts(text) or title
    if not clean:
        return None

    # Construct Gemini prompt requesting a comprehensive paragraph summary covering context, developments, and impact
    prompt = f"""Synthesize the news story below into a clear, cohesive executive paragraph summary.
Ensure the paragraph seamlessly covers the origin/context, key factual developments, and future outlook/impact.
Use standard sentence case, active voice, and professional journalism style. No bullet points or markdown headings.

Title: {title}
Article: {clean}

Respond ONLY with valid JSON in this format:
{{
  "summary": "Full cohesive executive summary paragraph covering context, developments, and impact."
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2
        }
    }

    headers = {'Content-Type': 'application/json'}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            candidates = resp_data.get('candidates', [])
            if candidates:
                part_text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                part_text = re.sub(r'^```json\s*', '', part_text.strip(), flags=re.IGNORECASE)
                part_text = re.sub(r'^```\s*', '', part_text.strip(), flags=re.IGNORECASE)
                part_text = re.sub(r'```$', '', part_text.strip())
                parsed = json.loads(part_text)
                return parsed
    except Exception as e:
        print(f"[Gemini API Error]: {e}")

    return None


def generate_deep_dive_brief(content, title="", gemini_key=""):
    """
    Main entry point for generating Deep-Dive Analytical Briefs.
    Returns a dictionary with context_background, key_developments, and impact_outlook.
    """
    cache_key = f"{title}_{hash(content[:200])}"
    if cache_key in SUMMARY_CACHE:
        return SUMMARY_CACHE[cache_key]

    gemini_result = _call_gemini_api(content, title=title, gemini_key=gemini_key)
    if gemini_result:
        SUMMARY_CACHE[cache_key] = gemini_result
        return gemini_result

    fallback = _structured_fallback(content, title=title)
    SUMMARY_CACHE[cache_key] = fallback
    return fallback


def summarize_content(content, title="", ssl_ctx=None, hf_token=""):
    """
    Legacy wrapper retained for backward compatibility.
    """
    brief = generate_deep_dive_brief(content, title=title, gemini_key=hf_token)
    return brief.get("context_background", "") + " " + " ".join(brief.get("key_developments", []))


def extract_why_it_matters(content, title=""):
    """
    Legacy wrapper retained for backward compatibility.
    """
    brief = generate_deep_dive_brief(content, title=title)
    return brief.get("impact_outlook", None)
