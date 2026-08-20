# Design Spec: Google Gemini Deep-Dive Briefs & Vercel Serverless Fix

## Overview
This specification details the overhaul of the News Intel application to:
1. Replace the HuggingFace fallback summarizer with direct **Google Gemini API** integration for structured **Deep-Dive Analytical Briefs**.
2. Convert backend server endpoints into Vercel-compliant serverless function routes under `/api` for proper deployment.
3. Clean up UI navigation by removing legacy/placeholder components (e.g. World Cup 26 page & tabs).

---

## 1. Gemini AI Deep-Dive Brief Engine (`news_summarizer.py` & `server.py`)

### Requirements
- Integrate Google Gemini API using structured prompt execution and JSON parsing.
- Provide a 3-part structured breakdown for every story:
  - **Context & Background**: Historic context and events leading up to the news.
  - **Key Developments**: Core bullet points detailing the latest facts.
  - **Impact & Outlook**: Strategic significance and future expectations ("Why It Matters").
- Implement an in-memory/file cache for generated summaries to optimize performance and prevent rate limiting.
- Graceful Fallback: Clean RSS text into structured readable blocks if the API key is missing or quota limit is reached.

---

## 2. Vercel Serverless Architecture (`/api/index.py` & `vercel.json`)

### Requirements
- Create standard Python Serverless API handlers compatible with Vercel serverless runtime (`/api/index.py` or `/api/news.py`).
- Route static frontend files (`index.html`, `styles.css`, `script.js`) cleanly while proxying API endpoints (`/api/feed`, `/api/summarize`, `/api/sources`).
- Fix cross-origin/SSL issues for RSS feed parsing across serverless functions.

---

## 3. UI Cleanup & World Cup Removal (`index.html`, `script.js`)

### Requirements
- Remove `viewWorldCup` view container, tabs (`tabWorldCupBtn`), filter buttons, and associated JavaScript handlers.
- Retain streamlined vertical category navigation (Global, Technology, Geopolitics, Science, Culture, Society, Sports, Finance).
- Polish story cards to render the 3-part Deep-Dive AI Brief (Context & Background, Key Developments, Impact & Outlook) cleanly.

---

## Verification Plan

### Automated / Local Testing
- Execute local server test script to verify Gemini API connection and fallback formatting.
- Test serverless route responses (`/api/feed`, `/api/summarize`).

### Manual Verification
- Test feed refresh and AI brief generation in browser.
- Verify removal of World Cup section from sidebars and UI.
- Verify Vercel deployment configuration syntax (`vercel.json`).
