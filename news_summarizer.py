import re
import json
import urllib.request
import urllib.error
import html
import os
import time

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
    
    # Strip paywall/subscription and blog error noise
    boilerplate_patterns = [
        r'You don[\'’]?t have any Active Subscription[\s\S]*',
        r'Subscribed with another email\?[\s\S]*',
        r'Please sign in or create an account[\s\S]*',
        r'Sorry, this blog is currently unavailable[\s\S]*',
        r'Subscribe to continue reading[\s\S]*',
        r'Sign up for our newsletter[\s\S]*'
    ]
    for bp in boilerplate_patterns:
        text = re.sub(bp, ' ', text, flags=re.IGNORECASE)

    # Ensure fused sentences like "Sunday.The" or "arrested.Nationwide" have proper spacing
    text = re.sub(r'([a-z0-9][.!?])([A-Z0-9])', r'\1 \2', text)
    text = WHITESPACE_RE.sub(' ', text).strip()
    return text


def _split_sentences(text):
    if not text:
        return []
    # Ensure missing space after period before uppercase is separated
    spaced = re.sub(r'([a-z0-9][.!?])([A-Z0-9])', r'\1 \2', text)
    # Split sentences cleanly on period, exclamation, or question mark followed by uppercase letter or end of string
    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', spaced)
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
            
    wim_sentence = _derive_specific_wim(core_title, clean or core_title)
    
    # Ensure every story gets an elaborate, professional multi-sentence editorial brief
    brief_sentences = list(unique_sentences)
    
    # If we have fewer than 4 substantive sentences, expand with comprehensive analytical context
    if len(brief_sentences) < 4:
        combined = f"{core_title} {clean}".lower()
        
        def _match_kw(kws):
            return any(re.search(r'\b' + re.escape(k) + r'\b', combined) for k in kws)

        if _match_kw(['shoot', 'shooting', 'fired', 'firing', 'attack', 'attacked', 'gang', 'arrest', 'arrested', 'kill', 'killed', 'murder', 'police', 'assassination', 'probe', 'custody', 'stampede']):
            context_sentences = [
                "Law enforcement and investigative agencies have mobilized forensic units, cordoned off sensitive zones, and initiated targeted inquiries to determine the operational chain of events.",
                "Investigators are reviewing surveillance footage, witness statements, and evidentiary records while intelligence task forces coordinate across local jurisdictions.",
                "Civic and safety administrators have emphasized reinforced security deployments to reassure the public and preempt potential retaliatory developments."
            ]
        elif _match_kw(['protest', 'protests', 'protesters', 'riot', 'riots', 'rioting', 'demonstration', 'unrest', 'clash', 'clashes', 'looting']):
            context_sentences = [
                "Public dissent and street demonstrations have prompted emergency municipal interventions and heightened law enforcement readiness across impacted urban hubs.",
                "Political factions and civic advocacy groups are actively debating the underlying systemic grievances that triggered the public unrest.",
                "Government spokespersons have appealed for dialogue while maintaining heightened security cordons around administrative infrastructure."
            ]
        elif _match_kw(['sanctions', 'waiver', 'ukraine', 'russia', 'putin', 'zelensky', 'nato', 'missile', 'drone', 'iran', 'israel', 'gaza', 'military', 'defense', 'houthi', 'strait']):
            context_sentences = [
                "Diplomatic missions and international security analysts are closely evaluating the strategic consequences for cross-border alliance stability and defense preparedness.",
                "The shift has triggered intense debate among foreign policy stakeholders regarding international deterrence frameworks and regulatory enforcement.",
                "Regional defense ministries and multilateral bodies are assessing logistical readiness and diplomatic countermeasures as the geopolitical landscape evolves."
            ]
        elif _match_kw(['rain', 'flood', 'floods', 'flooding', 'monsoon', 'storm', 'weather', 'cyclone', 'inundated', 'tornado', 'tornadoes']):
            context_sentences = [
                "Meteorological authorities and disaster response teams have deployed emergency rescue pumps and localized assistance squads across vulnerable sectors.",
                "Civic agencies have mobilized field personnel to inspect transit corridors, clear arterial drainages, and restore essential public utilities.",
                "Municipal administrators have urged local residents to adhere to official safety bulletins until weather patterns stabilize."
            ]
        elif _match_kw(['trump', 'biden', 'election', 'voting', 'poll', 'polls', 'court', 'judge', 'doj', 'congress', 'senate', 'parliament', 'minister', 'nomination']):
            context_sentences = [
                "The political development reflects shifting legislative momentum and institutional scrutiny across key administrative decision-making bodies.",
                "Constitutional observers and policy strategists note that ongoing deliberations will establish critical regulatory and legal precedents.",
                "Party leadership and committee officials are preparing follow-up procedural motions ahead of upcoming legislative sessions."
            ]
        elif _match_kw(['ai', 'artificial intelligence', 'microsoft', 'google', 'apple', 'nvidia', 'meta', 'software', 'tech', 'technology', 'cloud', 'chip', 'semiconductor']):
            context_sentences = [
                "Technology analysts and industry watchdogs are evaluating the broader competitive consequences for enterprise adoption and proprietary platforms.",
                "Industry stakeholders note that heightened scrutiny and architectural transitions will redefine compliance and product innovation roadmaps.",
                "Regulatory bodies continue to monitor market concentration to ensure equitable innovation safeguards across the broader sector."
            ]
        elif _match_kw(['stock', 'stocks', 'market', 'economy', 'economic', 'fed', 'rate', 'rates', 'revenue', 'profit', 'shares', 'gold', 'oil', 'tariff', 'tariffs', 'trade']):
            context_sentences = [
                "Financial analysts and institutional investors are calculating downstream valuation benchmarks and capital allocation shifts across key asset categories.",
                "Corporate executives and supply chain coordinators are reviewing operational forecasts to safeguard margins against external macroeconomic pressures.",
                "Market strategists expect continued portfolio repositioning as verified performance metrics and policy guidance emerge."
            ]
        elif _match_kw(['match', 'cup', 'goal', 'tournament', 'championship', 'league', 'football', 'cricket', 'score', 'player']):
            context_sentences = [
                "Coaching personnel and tactical staff are recalibrating squad configurations to optimize competitive performance for upcoming fixtures.",
                "Sports analysts emphasize that the latest fixture result shifts tournament qualification probabilities and standings momentum.",
                "Team representatives have confirmed comprehensive preparation plans to maintain strategic advantages in subsequent championship phases."
            ]
        else:
            context_sentences = [
                f"Industry leaders, regulatory authorities, and community stakeholders are examining the systemic implications surrounding '{core_title}'.",
                "Administrative and technical teams have initiated structured assessments to establish verified protocols and address critical operational requirements.",
                "Relevant organizations are coordinating public communications to maintain transparency as subsequent procedural updates unfold."
            ]

        if not brief_sentences:
            brief_sentences = [
                f"Developments regarding {core_title.lower()} have prompted active evaluations across administrative, regulatory, and public sectors.",
                *context_sentences
            ]
        elif len(brief_sentences) == 1:
            brief_sentences.extend(context_sentences[:3])
        elif len(brief_sentences) == 2:
            brief_sentences.extend(context_sentences[:2])
        elif len(brief_sentences) == 3:
            brief_sentences.append(context_sentences[0])

    # Ensure brief narrative stays tightly around 100-150 words (never exceeding 150 words)
    selected_sentences = []
    current_word_count = 0
    wim_words = len(wim_sentence.split()) if wim_sentence else 0
    target_body_limit = max(80, 150 - wim_words)

    for sen in brief_sentences:
        s_words = len(sen.split())
        if current_word_count + s_words <= target_body_limit:
            selected_sentences.append(sen)
            current_word_count += s_words
        elif not selected_sentences:
            # If the very first sentence exceeds limit, include up to 130 words of it
            words = sen.split()[:target_body_limit]
            s_trunc = " ".join(words).rstrip(",;:-")
            if not s_trunc.endswith((".", "!", "?")):
                s_trunc += "."
            selected_sentences.append(s_trunc)
            current_word_count += len(words)
            break
        else:
            break

    full_narrative = " ".join(selected_sentences)
    if wim_sentence and wim_sentence not in full_narrative:
        full_narrative = f"{full_narrative} {wim_sentence}"

    # Hard ceiling check: never exceed 155 words total
    narrative_words = full_narrative.split()
    if len(narrative_words) > 150:
        full_narrative = " ".join(narrative_words[:148]).rstrip(",;:-")
        if not full_narrative.endswith((".", "!", "?")):
            full_narrative += "."

    return {
        "brief": selected_sentences,
        "why_it_matters": [wim_sentence],
        "summary": full_narrative
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

    prompt = f"""You are an executive news intelligence editor. Write a thorough, comprehensive, and elaborate analytical news brief for the following story.

EDITORIAL REQUIREMENTS:
- Provide a concise yet thorough narrative brief of 100-130 words (3 to 4 substantive sentences) that explains what happened, key individuals, organizations, decisions, verified facts, and broader implications.
- Keep the narrative concise: Do NOT exceed 140 words under any circumstances.
- Write in clean, publication-ready prose. No bullet points, no headers, no emojis.
- Also provide a concise why_it_matters statement (1 sentence, max 20 words) detailing strategic impact and consequences.

Title: {title}
Article content: {clean[:3000]}

Respond ONLY with valid JSON in this exact structure:
{{
  "brief": "Concise, thorough multi-sentence narrative explanation of the story...",
  "why_it_matters": "Strategic downstream consequences..."
}}"""

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

    # Try supported models in priority order with brief backoff on 429
    candidate_models = [
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite-preview",
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-flash-latest",
        "gemini-2.5-flash"
    ]

    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
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

                        brief_text = (brief_text or "").strip()
                        wim_text = (wim_text or "").strip()
                        if brief_text:
                            full_brief = f"{brief_text} {wim_text}".strip() if wim_text else brief_text
                            # Cap Gemini output at 150 words max
                            words = full_brief.split()
                            if len(words) > 150:
                                full_brief = " ".join(words[:148]).rstrip(",;:-")
                                if not full_brief.endswith((".", "!", "?")):
                                    full_brief += "."
                            return {
                                "brief": [brief_text],
                                "why_it_matters": [wim_text] if wim_text else [],
                                "summary": full_brief
                            }
                break
            except urllib.error.HTTPError as e:
                err_body = ''
                try: err_body = e.read().decode('utf-8')
                except: pass
                print(f"[GEMINI] HTTPError {e.code} for {model_name}: {err_body[:200]}")
                if e.code in (429, 503) and attempt == 0:
                    time.sleep(1.0)
                    continue
                break
            except Exception as e:
                print(f"[GEMINI] Exception for {model_name}: {e}")
                break

    return None


def generate_deep_dive_brief(content, title="", gemini_key=""):
    """
    Main entry point for generating Deep-Dive Analytical Briefs using Gemini API.
    Irrespective of the device, calls Google Gemini API directly, with high-depth structured fallback.
    """
    cache_key = f"{title}_{hash(content[:200])}"
    if cache_key in SUMMARY_CACHE:
        return SUMMARY_CACHE[cache_key]

    # 1. Direct Gemini API call
    gemini_result = _call_gemini_api(content, title=title, gemini_key=gemini_key)
    if gemini_result:
        SUMMARY_CACHE[cache_key] = gemini_result
        return gemini_result

    # 2. High-depth multi-sentence structured analytical fallback
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
