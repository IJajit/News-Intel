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
        return None

    clean = _clean_rss_artifacts(text)
    if len(clean.split()) < 15:
        return None

    # Construct Gemini prompt requesting explicit structured JSON
    prompt = f"""You are an executive intelligence analyst. Synthesize the news story below into a Deep-Dive Analytical Brief.

Title: {title}
Article Text: {clean}

Respond ONLY with valid JSON (no markdown wrapping, no text outside JSON) matching this exact format:
{{
  "context_background": "2-3 sentences explaining the historical context, origin, or events leading up to this news.",
  "key_developments": [
    "Bullet point 1 detailing core recent facts/actions",
    "Bullet point 2 detailing additional key factual progress",
    "Bullet point 3 detailing critical statements or metrics"
  ],
  "impact_outlook": "2-3 sentences covering strategic global/industry impact and what to watch next ('Why It Matters')."
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
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
                # Clean up any potential markdown code fence wrapping
                part_text = re.sub(r'^```json\s*', '', part_text.strip(), flags=re.IGNORECASE)
                part_text = re.sub(r'```$', '', part_text.strip())
                parsed = json.loads(part_text)
                if "context_background" in parsed and "key_developments" in parsed and "impact_outlook" in parsed:
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
