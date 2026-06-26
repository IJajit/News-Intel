# Wiki Sidebar Facts — Design Spec

## Overview
Add two informational cards to the News Intel sidebar: "Did You Know" (random fact from Wikipedia's DYK section) and "On This Day" (random historical event from Wikipedia's OTD section). Both are fetched client-side from the Wikipedia API and randomized on each GENERATE BRIEF click.

## Data Source
- **Endpoint:** `https://en.wikipedia.org/w/api.php?action=parse&page=Main_Page&prop=text&format=json&origin=*`
- **Parsing:** Client-side `DOMParser` extracts:
  - DYK items from `#mp-dyk ul li` (the bullet list under "Did you know...")
  - OTD items from `#mp-otd ul li` (the bullet list under "On this day")
- **Selection:** A random item is chosen from each list every time the briefing is generated.

## Data Flow
1. User clicks GENERATE BRIEF → `triggerBriefingGeneration()` is called.
2. Parallel to the existing backend briefing call, `fetchWikiIntel()` runs in the browser.
3. `fetchWikiIntel()` calls the Wikipedia Action API, parses the HTML response, picks random items.
4. The selected fact and event are rendered into the sidebar cards.

## UI / Components
Two new cards inside `.sidebar-additional-elements` container in `index.html`:
- **DYK Card** — badge `DID YOU KNOW`, fact text, "Read more" link to the article.
- **OTD Card** — badge `ON THIS DAY`, year + event description, "Read more" link.

Styling uses compact `.wiki-card` class (reuses `.feed-article-card` patterns scaled down for sidebar width).

## Link Extraction
- The "Read more" link for each card is extracted from the first `<a>` tag inside the selected `<li>` element.
- The `href` attribute is taken as-is (e.g., `/wiki/Some_Article`) and converted to a full URL: `https://en.wikipedia.org/wiki/Some_Article`.
- The link text uses the article title from the anchor.

## Error Handling
If the Wikipedia API call fails, the card is left empty/hidden silently. No toasts or errors are shown to the user.

## Files Changed
| File | Change |
|------|--------|
| `index.html` | Add DYK and OTD card HTML skeletons in sidebar |
| `styles.css` | Add `.wiki-card` and `.wiki-card-content` styles |
| `script.js` | Add `fetchWikiIntel()`, DOM references, and integrate into generation flow |

## Future Considerations
- Facts could be cached in `sessionStorage` to avoid redundant API calls within a session.
- The "Read more" links point directly to the Wikipedia article for the selected item.
