# News Intel — Brief Generation Improvement Spec

## Goal
Fix the AI-generated category/story briefs (currently via Gemini API) so that each brief:
- Is 150–200 words
- Synthesizes multiple source articles into one coherent narrative (not a source-by-source recap)
- Is consistent in length/format every time the user clicks "Update Feed"
- Only reflects stories within the active recency window (12h for homepage headline/top stories, 24h for category feed, per existing filter)

Root cause of current issues: source articles are not grouped/structured before being sent to Gemini, so the model can't reliably cross-reference them. This spec fixes both the input structure and the prompt/API config.

---

## Step 1 — Aggregation: group articles into stories before calling the model

Before any brief is generated, articles fetched from the 9 sources must be clustered into "stories" (multiple outlets covering the same event) rather than treated as independent items.

**Minimum viable approach** (no ML clustering needed to start):
1. For each fetched article, extract: `headline`, `source_name`, `published_at`, `url`, `content` (or best available extract/snippet), `category`.
2. Group articles into a story cluster if they share strong headline/entity overlap (e.g. cosine similarity on headline embeddings, or simpler: shared proper nouns/keywords above a threshold). If you don't already have an embedding step, a simple keyword-overlap heuristic is fine as v1 — this can be upgraded later.
3. Within each cluster, pick a `primary_headline` (from the source with the most complete content, or the earliest reputable one) and attach all cluster members as `sources[]`.

**Story object shape** (this is what gets passed to the brief-generation call):

```json
{
  "story_id": "string",
  "category": "Technology | Geopolitics | Science | Culture | Society | Sports | Finance",
  "primary_headline": "string",
  "sources": [
    {
      "source_name": "string",
      "headline": "string",
      "published_at": "ISO 8601 timestamp",
      "content": "string (full text or best extract available)"
    }
  ]
}
```

If a story only has one source, `sources` is just an array of length 1 — same code path, no special-casing needed.

---

## Step 2 — Brief generation prompt

Use this as the prompt template for the Gemini call. Interpolate `{category}`, `{primary_headline}`, and the source list.

```
You are a news editor writing a single synthesized brief for a story, based on multiple source articles covering the same event.

TASK:
Write one cohesive brief of 150–200 words that synthesizes the information across ALL provided sources below. Do not summarize each source separately — merge the facts into one unified narrative, as if you are the most well-informed reporter on this story.

RULES:
- If sources agree on a fact, state it plainly once.
- If sources add different details (numbers, quotes, context, reactions), weave them in — don't repeat the same fact from each source.
- If sources conflict on a fact (e.g. different casualty counts, different figures), note the discrepancy briefly rather than picking one arbitrarily.
- Do not attribute every sentence to a specific outlet (no "According to Reuters..."). Write it as a clean editorial brief, not a source-by-source roundup.
- Lead with the most important, most recent development. Background/context comes after, only if space allows.
- No filler openers ("In a significant development..."). Start directly with the news.
- Target length: 150–200 words. Do not pad to hit the minimum — if the sources genuinely don't support 150 words of substance, write less rather than fabricate detail.
- Do not editorialize or add opinion not supported by the sources.

STORY CATEGORY: {category}
PRIMARY HEADLINE: {primary_headline}

SOURCES:
{for each source in sources: "Source: {source_name} | Published: {published_at}\n{content}\n---"}

Output only the brief text. No headers, no preamble, no source list.
```

---

## Step 3 — Gemini API config (structured output + low temperature)

Use structured output so length is enforced programmatically, not just requested in prose. Set temperature low since this is a factual-synthesis task, not creative writing.

```javascript
const response = await fetch(
  `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${GEMINI_API_KEY}`,
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: buildBriefPrompt(story) }] }],
      generationConfig: {
        temperature: 0.3,
        responseMimeType: "application/json",
        responseSchema: {
          type: "object",
          properties: {
            brief: { type: "string" },
            word_count: { type: "integer" }
          },
          required: ["brief", "word_count"]
        }
      }
    })
  }
);

const data = await response.json();
const parsed = JSON.parse(data.candidates[0].content.parts[0].text);
```

> Note: confirm the exact model name/endpoint currently used in the codebase (e.g. `gemini-2.0-flash`, `gemini-1.5-pro`, etc.) — swap in whatever is already configured. The important parts to add are `responseSchema` and `temperature`, not the model itself.

---

## Step 4 — Validation / retry logic

After parsing the response:

```javascript
function validateBrief(parsed) {
  const wc = parsed.brief.trim().split(/\s+/).length;
  if (wc < 130 || wc > 220) {
    return { valid: false, reason: `word count ${wc} out of range` };
  }
  return { valid: true };
}
```

If invalid, retry once with an appended note in the prompt: `"Your previous attempt was {wc} words. Strictly target 150-200 words this time."` If it fails twice, accept the output but log it for review rather than blocking the update — don't let one bad brief break the whole feed refresh.

---

## Step 5 — Pipeline order (on "Update Feed" click)

1. Fetch raw articles from all 9 sources.
2. Apply recency filter (12h for headline/top stories, 24h for category feed — existing logic).
3. Cluster articles into story objects (Step 1).
4. For each story, call Gemini with the brief prompt (Step 2–3), validate (Step 4).
5. Assemble homepage sections (Headline / Top Stories / Category Breakdown) from the generated story briefs, per the existing structure prompt already in use for the homepage summary layer.
6. Render.

---

## Step 6 — One shared pipeline, not one per page

This entire pipeline (Steps 1–4) should run **once per "Update Feed" click**, generating a full set of story objects — each already tagged with its `category` — covering all 7 categories (Technology, Geopolitics, Science, Culture, Society, Sports, Finance) in a single pass. Do not build a separate clustering/generation flow per category page.

The homepage and each category page are then just different **filters/views** over that same generated set:

- **Homepage — The Headline / Top Stories**: pulled from the full story set, filtered to the 12h window, ranked by importance/urgency across all categories.
- **Homepage — Category Breakdown**: same story set, grouped by `category`, remaining stories after Top Stories are pulled out.
- **Individual category page (e.g. /technology)**: same story set, filtered where `category === "Technology"`, using the 24h window, showing top 5 stories with their headline + AI brief + "other sources reporting this" list (the `sources[]` array already gives you that for free — just render `source_name` + `url` for each entry beyond the primary one).

Concretely, this means:
1. One aggregation pass fetches and clusters articles across all sources/categories.
2. One loop generates a brief per story cluster (Step 2–3), regardless of category.
3. Category is just a field you filter/sort on when rendering — homepage, category pages, and the "top 5 per category" logic all read from this same array of story objects.

This keeps brief quality and format consistent everywhere (fixes "why does Sports look different from Finance") and means Step 4's validation/retry logic only needs to exist in one place.

---

## Open question for your coding agent to flag back to you
How many source articles typically cluster per story (2–3 vs 6+)? If clusters can get large, add a cap (e.g. top 5 sources by recency/reputability) before Step 2, so the prompt input doesn't get diluted or blow the context window.
