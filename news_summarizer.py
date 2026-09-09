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
    
    # Replace inline bullet characters (•, \u2022, ·, \u00b7) with spaces
    text = re.sub(r'[\u2022\u00b7\u25aa\u25ab\u2023\u2043\u2219•]', ' ', text)
    
    text = WHITESPACE_RE.sub(' ', text).strip()
    text = CONTINUE_READING_RE.sub('', text).strip()
    text = TRAILING_ELLIPSIS_RE.sub('', text).strip()
    
    # Remove concatenated agency brand names like "Reuters", "Al Jazeera" stuck in text
    text = re.sub(r'\b(Reuters|Al\s+Jazeera|NDTV|The\s+Indian\s+Express|BBC\s+News)\b', '', text, flags=re.IGNORECASE)
    
    # Fix missing spaces after full stops (e.g. "Wednesday.The" -> "Wednesday. The")
    text = re.sub(r'(?<=[a-zA-Z0-9])\.\s*(?=[A-Z])', '. ', text)
    text = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '. ', text)
    
    text = WHITESPACE_RE.sub(' ', text).strip()
    return text


def _split_sentences(text):
    # Split sentences cleanly on period, exclamation, or question mark followed by uppercase letter or end of string
    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text)
    return [s.strip() for s in raw if len(s.strip()) > 15]


def _derive_specific_wim(title, text):
    combined = (title + " " + text).lower()
    if any(k in combined for k in ['iran', 'hormuz', 'oil', 'strait', 'gulf', 'tanker', 'crude', 'petrol', 'diesel', 'opec']):
        return "Directly heightens disruption risks for global maritime energy corridors and crude shipments through the Persian Gulf."
    if any(k in combined for k in ['ukraine', 'russia', 'putin', 'zelensky', 'drone', 'leipzig', 'nato', 'missile', 'kyiv', 'moscow', 'consulate', 'hybrid']):
        return "Deepens security friction across Europe, escalating defensive readiness and diplomatic countermeasures against hybrid threats."
    if any(k in combined for k in ['israel', 'gaza', 'hamas', 'hezbollah', 'lebanon', 'beirut', 'ceasefire', 'netanyahu', 'hostage']):
        return "Directly impacts regional security balances and humanitarian conditions, testing international ceasefire mediation."
    if any(k in combined for k in ['china', 'taiwan', 'beijing', 'south china sea', 'xi jinping', 'philippines']):
        return "Carries profound strategic implications for Indo-Pacific maritime navigation, technology supply chains, and regional alliances."
    if any(k in combined for k in ['trump', 'biden', 'white house', 'congress', 'senate', 'election', 'voting', 'ballot', 'usps', 'democrat', 'republican']):
        return "Shifts federal policy priorities and legislative momentum ahead of upcoming electoral and administrative deadlines."
    if any(k in combined for k in ['stab', 'police', 'shooting', 'nypd', 'killed', 'times square', 'arrest', 'suspect', 'investigation']):
        return "Triggers heightened municipal security deployments and intensifies scrutiny over public safety and emergency protocols."
    if any(k in combined for k in ['heat', 'temperature', 'hottest', 'climate', 'met office', 'weather', 'flood', 'wildfire', 'storm', 'hurricane', 'monsoon']):
        return "Underscores accelerating climate extremes, increasing long-term operational strain on public infrastructure and utility grids."
    if any(k in combined for k in ['cancer', 'vaccine', 'drug', 'fda', 'trial', 'health', 'disease', 'hospital', 'medical', 'patient']):
        return "Marks an important milestone in treatment development, shaping clinical guidelines and patient standard-of-care."
    if any(k in combined for k in ['ai', 'artificial intelligence', 'apple', 'google', 'microsoft', 'nvidia', 'meta', 'openai', 'chip', 'semiconductor', 'software']):
        return "Accelerates competitive technological innovation, driving enterprise integration and regulatory review across the sector."
    if any(k in combined for k in ['cyber', 'hack', 'breach', 'security', 'ransomware', 'malware']):
        return "Highlights persistent enterprise infrastructure vulnerabilities, prompting defensive upgrades and compliance scrutiny."
    if any(k in combined for k in ['fed', 'interest rate', 'inflation', 'treasury', 'central bank', 'yield', 'rate cut', 'rate hike']):
        return "Directly influences borrowing costs, consumer spending appetite, and capital deployment across global financial markets."
    if any(k in combined for k in ['tariff', 'trade', 'export', 'import', 'wto', 'customs', 'duty']):
        return "Pressures corporate margins and forces cross-border supply chain realignments for international manufacturers."
    if any(k in combined for k in ['earnings', 'revenue', 'profit', 'shares', 'stock', 'nasdaq', 's&p', 'dow', 'market cap']):
        return "Influences institutional investor sentiment and valuation benchmarks across key equity and corporate market segments."
    if any(k in combined for k in ['layoff', 'job', 'unemployment', 'workforce', 'hiring', 'strike', 'union']):
        return "Reflects broader macroeconomic labor market adjustments as employers rebalance operating costs."
    if any(k in combined for k in ['fifa', 'world cup', 'match', 'goal', 'score', 'tournament', 'championship', 'league', 'ipl', 'cricket', 'bcci', 'icc']):
        return "Shapes tournament standings and competitive momentum ahead of upcoming qualifying fixtures."
    core_title = re.sub(r'(\s*[-|–—]\s*[^-|–—]+)$', '', title).strip()
    return f"Carries notable operational, policy, and market consequences surrounding '{core_title}'."

def _structured_fallback(text, title=""):
    """
    Extracts core article sentences into clean, thorough bulleted brief and why_it_matters lists.
    """
    clean = _clean_rss_artifacts(text)
    if not clean or len(clean.strip()) < 15:
        clean = title
    
    clean = re.sub(re.escape(title), '', clean, flags=re.IGNORECASE).strip()
    sentences = _split_sentences(clean)
    
    core_title = re.sub(r'(\s*[-|–—]\s*[^-|–—]+)$', '', title).strip()
    
    # Filter duplicate sentences
    unique_sentences = []
    seen_lower = set()
    for s in sentences:
        s_norm = s.lower().strip()
        if s_norm not in seen_lower and len(s_norm) > 15:
            seen_lower.add(s_norm)
            if not s.endswith(('.', '!', '?')):
                s += '.'
            unique_sentences.append(s)
            
    if not unique_sentences:
        clean_title = core_title if core_title.endswith(('.', '!', '?')) else core_title + '.'
        return {
            "brief": [clean_title],
            "why_it_matters": [_derive_specific_wim(core_title, clean_title)],
            "summary": clean_title
        }
    
    # Produce an elaborate, multi-sentence brief (at least 3-5 sentences)
    wim_sentence = _derive_specific_wim(core_title, " ".join(unique_sentences))

    if len(unique_sentences) >= 4:
        brief_sentences = unique_sentences[:4]
    elif len(unique_sentences) >= 2:
        brief_sentences = unique_sentences
    else:
        brief_sentences = [unique_sentences[0]]

    full_narrative = " ".join(brief_sentences)
    if wim_sentence and wim_sentence not in full_narrative:
        full_narrative = f"{full_narrative} {wim_sentence}"

    return {
        "brief": brief_sentences,
        "why_it_matters": [wim_sentence],
        "summary": full_narrative
    }


def _call_omniroute_api(text, title=""):
    """Call OmniRoute local AI router (using gemini-3.1-flash-lite)."""
    clean = _clean_rss_artifacts(text) or title
    if not clean:
        return None

    prompt = f"""You are an executive news intelligence editor. Write a thorough, comprehensive, and elaborate analytical news brief for the following story.

EDITORIAL REQUIREMENTS:
- Provide an elaborate narrative brief of 120-180 words (4 to 6 substantive sentences) that thoroughly explains what happened, key individuals, organizations, decisions, verified facts, and broader implications.
- Do NOT overly compress or truncate into a single short sentence. Explain the entire story properly.
- Write in clean, publication-ready prose. No bullet points, no headers, no emojis.
- Also provide a concise why_it_matters statement (1-2 sentences) detailing strategic impact and consequences.

Title: {title}
Article content: {clean[:3000]}

Respond ONLY with valid JSON in this format:
{{
  "brief": "Comprehensive, elaborate multi-sentence narrative explanation of the story...",
  "why_it_matters": "Strategic downstream consequences..."
}}"""

    url = "http://localhost:20128/v1/chat/completions"
    payload = {
        "model": "antigravity/gemini-3.1-flash-lite",
        "messages": [
            {"role": "system", "content": "You are an executive news editor. Output only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.25,
        "response_format": {"type": "json_object"}
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer sk-antigravity-bridge'
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            choices = resp_data.get('choices', [])
            if choices:
                raw_content = choices[0].get('message', {}).get('content', '')
                raw_content = re.sub(r'^```json\s*', '', raw_content.strip(), flags=re.IGNORECASE)
                raw_content = re.sub(r'^```\s*', '', raw_content.strip(), flags=re.IGNORECASE)
                raw_content = re.sub(r'```$', '', raw_content.strip())
                parsed = json.loads(raw_content)

                brief_text = parsed.get("brief", "").strip()
                wim_text = parsed.get("why_it_matters", "").strip()
                if brief_text:
                    full_brief = f"{brief_text} {wim_text}".strip() if wim_text else brief_text
                    return {
                        "brief": [brief_text],
                        "why_it_matters": [wim_text] if wim_text else [],
                        "summary": full_brief
                    }
    except Exception as e:
        # Silently proceed to next provider
        pass

    return None


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

    prompt = f"""You are an executive news intelligence editor. Write a thorough, comprehensive, and elaborate analytical news brief for the following story.

EDITORIAL REQUIREMENTS:
- Provide an elaborate narrative brief of 120-180 words (4 to 6 substantive sentences) that thoroughly explains what happened, key individuals, organizations, decisions, verified facts, and broader implications.
- Do NOT overly compress or truncate into a single short sentence. Explain the entire story properly.
- Write in clean, publication-ready prose. No bullet points, no headers, no emojis.
- Also provide a concise why_it_matters statement (1-2 sentences) detailing strategic impact and consequences.

Title: {title}
Article: {clean[:3000]}

Respond ONLY with valid JSON in this format:
{{
  "brief": "Comprehensive, elaborate multi-sentence narrative explanation of the story...",
  "why_it_matters": "Strategic downstream consequences..."
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

                brief_text = parsed.get("brief", "")
                if isinstance(brief_text, list):
                    brief_text = " ".join(brief_text)
                wim_text = parsed.get("why_it_matters", "")
                if isinstance(wim_text, list):
                    wim_text = " ".join(wim_text)

                brief_text = brief_text.strip()
                wim_text = wim_text.strip()
                if brief_text:
                    full_brief = f"{brief_text} {wim_text}".strip() if wim_text else brief_text
                    return {
                        "brief": [brief_text],
                        "why_it_matters": [wim_text] if wim_text else [],
                        "summary": full_brief
                    }
    except Exception as e:
        pass

    return None


def generate_deep_dive_brief(content, title="", gemini_key=""):
    """
    Main entry point for generating Deep-Dive Analytical Briefs.
    Tries OmniRoute local inference first, then Gemini cloud API, then high-depth structured fallback.
    """
    cache_key = f"{title}_{hash(content[:200])}"
    if cache_key in SUMMARY_CACHE:
        return SUMMARY_CACHE[cache_key]

    # 1. OmniRoute AI router (free, unlimited local bridge)
    omni_result = _call_omniroute_api(content, title=title)
    if omni_result:
        SUMMARY_CACHE[cache_key] = omni_result
        return omni_result

    # 2. Gemini Cloud API
    gemini_result = _call_gemini_api(content, title=title, gemini_key=gemini_key)
    if gemini_result:
        SUMMARY_CACHE[cache_key] = gemini_result
        return gemini_result

    # 3. High-depth multi-sentence structured analytical fallback
    fallback = _structured_fallback(content, title=title)
    SUMMARY_CACHE[cache_key] = fallback
    return fallback


def summarize_content(content, title="", ssl_ctx=None, hf_token=""):
    """
    Legacy wrapper retained for backward compatibility.
    """
    brief = generate_deep_dive_brief(content, title=title, gemini_key=hf_token)
    return brief.get("summary", "")


def extract_why_it_matters(content, title=""):
    """
    Legacy wrapper retained for backward compatibility.
    """
    brief = generate_deep_dive_brief(content, title=title)
    wim = brief.get("why_it_matters", [])
    return " ".join(wim) if isinstance(wim, list) else str(wim)
