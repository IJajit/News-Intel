# Wiki Sidebar Facts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Did You Know" and "On This Day" cards to the sidebar, fetched from Wikipedia and randomized on each GENERATE BRIEF click.

**Architecture:** Client-side only. On GENERATE BRIEF, JavaScript fetches the Wikipedia Main Page HTML via the MediaWiki Action API, parses it with DOMParser, randomly selects one DYK fact and one OTD event, and renders them into sidebar cards.

**Tech Stack:** Vanilla JS, Wikipedia Action API, DOMParser

---

### Task 1: HTML — Add sidebar card skeletons

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add DYK and OTD card HTML inside `.sidebar-additional-elements`**

Replace the empty `.sidebar-additional-elements` div with:

```html
      <!-- Additional Sidebar Elements Area -->
      <div class="sidebar-additional-elements">
        <div id="wikiDykCard" class="wiki-card" style="display: none;">
          <span class="wiki-card-badge">DID YOU KNOW</span>
          <p id="wikiDykText" class="wiki-card-content"></p>
          <a id="wikiDykLink" href="#" target="_blank" rel="noopener noreferrer" class="wiki-card-link">Read more &nearr;</a>
        </div>
        <div id="wikiOtdCard" class="wiki-card" style="display: none;">
          <span class="wiki-card-badge otd-badge">ON THIS DAY</span>
          <p id="wikiOtdText" class="wiki-card-content"></p>
          <a id="wikiOtdLink" href="#" target="_blank" rel="noopener noreferrer" class="wiki-card-link">Read more &nearr;</a>
        </div>
      </div>
```

- [ ] **Step 2: Commit**

```bash
git add index.html
git commit -m "feat: add wiki fact card skeletons to sidebar"
```

---

### Task 2: CSS — Style the wiki cards

**Files:**
- Modify: `styles.css`

- [ ] **Step 1: Add wiki-card styles**

Add after the `.sources-sidebar-item` block (around line 380):

```css
/* ─── WIKI SIDEBAR FACTS ────────────────────────────────── */
.wiki-card {
  background: var(--color-white);
  border: 1.5px solid var(--color-light-gray);
  border-radius: 3px;
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transition: var(--transition-fast);
  position: relative;
  overflow: hidden;
}

.wiki-card:hover {
  border-color: var(--color-black);
}

.wiki-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  width: 0;
  background-color: var(--color-orange);
  transition: width 0.15s ease;
}

.wiki-card:hover::before {
  width: 3px;
}

.wiki-card-badge {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-dark-gray);
}

.wiki-card-badge.otd-badge {
  color: var(--color-orange);
}

.wiki-card-content {
  font-family: var(--font-body);
  font-size: 0.78rem;
  line-height: 1.55;
  color: var(--color-black);
  margin: 0;
}

.wiki-card-link {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--color-dark-gray);
  text-decoration: none;
  transition: var(--transition-fast);
  align-self: flex-start;
}

.wiki-card-link:hover {
  color: var(--color-orange);
}
```

- [ ] **Step 2: Commit**

```bash
git add styles.css
git commit -m "feat: add wiki fact card styles"
```

---

### Task 3: JavaScript — Fetch, parse, and render Wikipedia facts

**Files:**
- Modify: `script.js`

- [ ] **Step 1: Add DOM references for wiki cards**

Add after line 24 (`const sourcesList = document.getElementById('sourcesList');`):

```js
const wikiDykCard   = document.getElementById('wikiDykCard');
const wikiDykText   = document.getElementById('wikiDykText');
const wikiDykLink   = document.getElementById('wikiDykLink');
const wikiOtdCard   = document.getElementById('wikiOtdCard');
const wikiOtdText   = document.getElementById('wikiOtdText');
const wikiOtdLink   = document.getElementById('wikiOtdLink');
```

- [ ] **Step 2: Add `fetchWikiIntel()` function**

Add after the `fetchSources()` function (around line 160):

```js
// ─── FETCH WIKIPEDIA FACTS ──────────────────────────────────
async function fetchWikiIntel() {
  try {
    const res = await fetch(
      'https://en.wikipedia.org/w/api.php?action=parse&page=Main_Page&prop=text&format=json&origin=*'
    );
    if (!res.ok) throw new Error('Wiki fetch failed');
    const data = await res.json();
    const html = data.parse.text['*'];

    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    // Extract DYK items
    const dykList = doc.querySelector('#mp-dyk ul');
    const dykItems = dykList ? [...dykList.querySelectorAll('li')].filter(li => li.querySelector('a')) : [];
    if (dykItems.length > 0) {
      const pick = dykItems[Math.floor(Math.random() * dykItems.length)];
      wikiDykText.textContent = pick.textContent.trim();
      const link = pick.querySelector('a');
      wikiDykLink.href = 'https://en.wikipedia.org' + link.getAttribute('href');
      wikiDykCard.style.display = 'flex';
    }

    // Extract OTD items
    const otdList = doc.querySelector('#mp-otd ul');
    const otdItems = otdList ? [...otdList.querySelectorAll('li')].filter(li => li.querySelector('a')) : [];
    if (otdItems.length > 0) {
      const pick = otdItems[Math.floor(Math.random() * otdItems.length)];
      wikiOtdText.textContent = pick.textContent.trim();
      const link = pick.querySelector('a');
      wikiOtdLink.href = 'https://en.wikipedia.org' + link.getAttribute('href');
      wikiOtdCard.style.display = 'flex';
    }
  } catch (err) {
    console.error('Wiki sidebar facts failed:', err);
    // Silently fail — cards stay hidden
  }
}
```

- [ ] **Step 3: Integrate into the generation flow**

Inside `triggerBriefingGeneration()`, after the existing `setLoadingState(true, ...)` call and before the `try` block, add:

```js
  fetchWikiIntel();
```

Also add a call in the `DOMContentLoaded` handler so facts load on initial page load too. After `loadLatestBrief(activeCategory);` add:

```js
  fetchWikiIntel();
```

- [ ] **Step 4: Hide wiki cards when generating new brief**

Inside `setLoadingState(true, ...)`, add these lines to hide the cards during generation:

```js
    wikiDykCard.style.display = 'none';
    wikiOtdCard.style.display = 'none';
```

- [ ] **Step 5: Commit**

```bash
git add script.js
git commit -m "feat: add Wikipedia fact fetching for sidebar"
```

---

### Task 4: Final integration check

- [ ] **Step 1: Verify everything works together**

Run the dev server and check:
1. On page load, both wiki cards should appear with content in the sidebar.
2. Click GENERATE BRIEF — new random facts should appear.
3. If wiki fetch fails, cards stay hidden, no errors shown to user.

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "chore: finalize wiki sidebar facts integration"
git push
```
