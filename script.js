/* ============================================================
   EXECUTIVE BRIEFING SUMMARIZER — CLIENT LOGIC
   Industrial Edition v2.0
   ============================================================ */

// ─── DOM ELEMENTS ────────────────────────────────────────────
const apiKeyInput         = document.getElementById('apiKeyInput');
const toggleKeyVisibility = document.getElementById('toggleKeyVisibility');
const generateBtn         = document.getElementById('generateBtn');
const tabReaderBtn        = document.getElementById('tabReaderBtn');
const tabMarkdownBtn      = document.getElementById('tabMarkdownBtn');
const tabArticlesBtn      = document.getElementById('tabArticlesBtn');
const tabWorldCupBtn      = document.getElementById('tabWorldCupBtn');
const stateEmpty          = document.getElementById('stateEmpty');
const stateLoading        = document.getElementById('stateLoading');
const loadingStatusText   = document.getElementById('loadingStatusText');
const viewReader          = document.getElementById('viewReader');
const viewMarkdown        = document.getElementById('viewMarkdown');
const viewArticles        = document.getElementById('viewArticles');
const viewWorldCup        = document.getElementById('viewWorldCup');
const markdownTextarea    = document.getElementById('markdownTextarea');
const articlesCountVal    = document.getElementById('articlesCountVal');
const articlesList        = document.getElementById('articlesList');
const worldCupSchedule    = document.getElementById('worldCupSchedule');
const worldCupLoader      = document.getElementById('worldCupLoader');
const copyMarkdownBtn     = document.getElementById('copyMarkdownBtn');
const feedSourcesList     = document.getElementById('feedSourcesList');
const feedSearchInput     = document.getElementById('feedSearchInput');
const feedSearchCount     = document.getElementById('feedSearchCount');
const sidebarAdditional   = document.getElementById('sidebarAdditional');
const categoryList        = document.getElementById('categoryList');
const totalArticleCount   = document.getElementById('totalArticleCount');
const readerContent       = document.getElementById('readerContent');
const readerSubtabs       = document.getElementById('readerSubtabs');
const imageModal          = document.getElementById('imageModal');
const modalCloseBtn       = document.getElementById('modalCloseBtn');
const modalImage          = document.getElementById('modalImage');
const wikiDykCard         = document.getElementById('wikiDykCard');
const wikiDykText         = document.getElementById('wikiDykText');
const wikiDykLink         = document.getElementById('wikiDykLink');
const wikiOtdCard         = document.getElementById('wikiOtdCard');
const wikiOtdText         = document.getElementById('wikiOtdText');
const wikiOtdLink         = document.getElementById('wikiOtdLink');

// ─── APP STATE ────────────────────────────────────────────────
let apiKey          = '';
let showApiKey      = false;
let activeTab       = localStorage.getItem('wcActiveTab') || 'reader';
let currentBriefing = null;
let activeCategory  = localStorage.getItem('readerCategory') || 'global';
let categories     = [];
let searchQuery    = '';

// ─── INITIALIZATION ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Load saved API key from localStorage
  const savedKey = localStorage.getItem('GEMINI_API_KEY');
  if (savedKey) {
    const isInvalid = savedKey.includes(' ') || savedKey.includes('•') || savedKey.startsWith('Live Briefing');
    if (isInvalid) {
      localStorage.removeItem('GEMINI_API_KEY');
    } else {
      apiKey = savedKey;
      if (apiKeyInput) apiKeyInput.value = savedKey;
    }
  }

  // Check if API key is already configured on the server-side
  checkServerConfig();

  // Load sources into sidebar
  fetchSources();

  // Fetch categories and render sidebar + sub-tabs
  fetchCategories();

  // Load default briefing then auto-generate fresh one
  loadLatestBrief(activeCategory).then(() => {
    setTimeout(() => triggerBriefingGeneration(), 800);
  });

  // Load Wikipedia sidebar facts
  fetchWikiIntel();

  // ─── EVENT LISTENERS ──────────────────────────────────────
  if (apiKeyInput) {
    apiKeyInput.addEventListener('input', (e) => {
      apiKey = e.target.value.trim();
      const isInvalid = apiKey.includes(' ') || apiKey.includes('•') || apiKey.startsWith('Live Briefing');
      if (apiKey && !isInvalid) {
        localStorage.setItem('GEMINI_API_KEY', apiKey);
      } else {
        localStorage.removeItem('GEMINI_API_KEY');
      }
    });
  }

  if (toggleKeyVisibility) {
    toggleKeyVisibility.addEventListener('click', () => {
      showApiKey = !showApiKey;
      apiKeyInput.type = showApiKey ? 'text' : 'password';
      toggleKeyVisibility.textContent = showApiKey ? 'Hide' : 'Show';
    });
  }

  generateBtn.addEventListener('click', triggerBriefingGeneration);
  copyMarkdownBtn.addEventListener('click', copyMarkdownToClipboard);

  // Tab switching
  [tabReaderBtn, tabMarkdownBtn, tabArticlesBtn, tabWorldCupBtn].forEach(btn => {
    btn.addEventListener('click', (e) => {
      switchTab(e.currentTarget.getAttribute('data-tab'));
    });
  });

  // Image modal - close on X or backdrop click
  modalCloseBtn.addEventListener('click', closeImageModal);
  imageModal.addEventListener('click', (e) => {
    if (e.target === imageModal) closeImageModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && imageModal.classList.contains('open')) closeImageModal();
  });

  // Click delegation for briefing images
  viewReader.addEventListener('click', (e) => {
    const img = e.target.closest('.briefing-image');
    if (img) openImageModal(img.src, img.alt);
  });

  // World Cup filter tabs
  document.getElementById('wcFilterAll').addEventListener('click', () => setWorldCupFilter('all'));
  document.getElementById('wcFilterArgentina').addEventListener('click', () => setWorldCupFilter('argentina'));

  // Intel Reader sub-tabs
  if (readerSubtabs) {
    readerSubtabs.addEventListener('click', (e) => {
      const btn = e.target.closest('.reader-subtab');
      if (!btn) return;
      const cat = btn.dataset.category;
      readerSubtabs.querySelectorAll('.reader-subtab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeCategory = cat;
      localStorage.setItem('readerCategory', cat);
      triggerBriefingGeneration();
    });
  }

  // Search input
  if (feedSearchInput) {
    feedSearchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.trim().toLowerCase();
      renderArticlesList();
    });
  }
});

// Check if server already has the Gemini API Key in its environment
async function checkServerConfig() {
  if (!apiKeyInput) return;
  try {
    const res = await fetch('/api/config');
    if (res.ok) {
      const data = await res.json();
      if (data.apiKeyConfigured) {
        apiKeyInput.disabled = true;
        apiKeyInput.placeholder = "Configured on Server";
        apiKeyInput.value = "••••••••••••••••";
        apiKeyInput.style.opacity = "0.7";
        toggleKeyVisibility.style.display = "none";
      }
    }
  } catch (err) {
    console.error('Failed to check server config:', err);
  }
}


// ─── GROUNDED CLOCK ───────────────────────────────────────────
// ─── FETCH SOURCES ───────────────────────────────────────────
async function fetchSources() {
  if (!feedSourcesList) return;
  try {
    const res = await fetch('/api/sources');
    if (!res.ok) return;
    const sources = await res.json();
    feedSourcesList.innerHTML = sources.map(src => `
      <div class="sources-sidebar-item">
        <span class="sources-sidebar-dot">●</span>
        <a href="${src.siteUrl}" target="_blank" rel="noopener noreferrer">${src.name}</a>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load sources:', err);
  }
}

// ─── FETCH CATEGORIES & RENDER SIDEBAR ──────────────────────
async function fetchCategories() {
  try {
    const res = await fetch('/api/categories');
    if (!res.ok) return;
    categories = await res.json();
    renderSidebarCategories();
  } catch (err) {
    console.error('Failed to load categories:', err);
  }
}

function renderSidebarCategories(counts) {
  if (!categoryList) return;
  const countsMap = counts || {};
  let total = 0;
  categoryList.innerHTML = categories.map(cat => {
    const count = countsMap[cat.id] || 0;
    total += count;
    const isActive = cat.id === activeCategory;
    return `
      <div class="category-item ${isActive ? 'active' : ''}" data-category="${cat.id}">
        <span class="category-icon">${cat.icon}</span>
        <div class="category-text">
          <span class="category-name">${cat.name}</span>
          <span class="category-meta">${cat.label} &middot; ${count} ARTICLES</span>
        </div>
      </div>
    `;
  }).join('');
  if (totalArticleCount) {
    totalArticleCount.textContent = `${total} ARTICLES`;
  }

  categoryList.querySelectorAll('.category-item').forEach(item => {
    item.addEventListener('click', () => {
      const cat = item.dataset.category;
      categoryList.querySelectorAll('.category-item').forEach(c => c.classList.remove('active'));
      item.classList.add('active');
      activeCategory = cat;
      // Update sub-tab active state
      if (readerSubtabs) {
        readerSubtabs.querySelectorAll('.reader-subtab').forEach(b => {
          b.classList.toggle('active', b.dataset.category === cat);
        });
      }
      localStorage.setItem('readerCategory', cat);
      triggerBriefingGeneration();
    });
  });
}

// ─── FETCH WIKIPEDIA FACTS ──────────────────────────────────
async function fetchWikiIntel() {
  const fallbackDyk = 'Wikipedia is a free, collaborative encyclopedia written by volunteers worldwide.';
  const fallbackOtd = 'On this day in history — explore Wikipedia to discover what happened today.';
  const wikiUrl = 'https://en.wikipedia.org/wiki/Main_Page';

  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const res = await fetch(
        'https://en.wikipedia.org/w/api.php?action=parse&page=Main_Page&prop=text&format=json&origin=*'
      );
      if (!res.ok) throw new Error('Wiki fetch failed');
      const data = await res.json();
      const html = data.parse.text['*'];

      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');

      const dykList = doc.querySelector('#mp-dyk ul');
      const dykItems = dykList ? [...dykList.querySelectorAll('li')].filter(li => li.querySelector('a')) : [];
      if (dykItems.length > 0) {
        const pick = dykItems[Math.floor(Math.random() * dykItems.length)];
        wikiDykText.textContent = pick.textContent.trim();
        const link = pick.querySelector('a');
        wikiDykLink.href = 'https://en.wikipedia.org' + link.getAttribute('href');
      } else {
        wikiDykText.textContent = fallbackDyk;
        wikiDykLink.href = wikiUrl;
      }
      wikiDykCard.style.display = 'flex';

      const otdList = doc.querySelector('#mp-otd ul');
      const otdItems = otdList ? [...otdList.querySelectorAll('li')].filter(li => li.querySelector('a')) : [];
      if (otdItems.length > 0) {
        const pick = otdItems[Math.floor(Math.random() * otdItems.length)];
        wikiOtdText.textContent = pick.textContent.trim();
        const link = pick.querySelector('a');
        wikiOtdLink.href = 'https://en.wikipedia.org' + link.getAttribute('href');
      } else {
        wikiOtdText.textContent = fallbackOtd;
        wikiOtdLink.href = wikiUrl;
      }
      wikiOtdCard.style.display = 'flex';
      return;
    } catch (err) {
      console.error('Wiki sidebar facts attempt ' + (attempt + 1) + ' failed:', err);
    }
  }

  // Fallback: show cards with generic content
  wikiDykText.textContent = fallbackDyk;
  wikiDykLink.href = wikiUrl;
  wikiDykCard.style.display = 'flex';
  wikiOtdText.textContent = fallbackOtd;
  wikiOtdLink.href = wikiUrl;
  wikiOtdCard.style.display = 'flex';
}

// ─── LOAD LATEST BRIEF ────────────────────────────────────────
async function loadLatestBrief(category) {
  setLoadingState(true, 'Loading latest briefing...');
  try {
    const res = await fetch(`/api/latest-brief?category=${category}&t=${Date.now()}`);
    if (!res.ok) throw new Error('Briefing not found');

    const brief = await res.json();
    currentBriefing = brief;

    renderBriefing(brief);
    switchTab(activeTab);
  } catch (err) {
    console.error('Error loading latest brief:', err);
    currentBriefing = null;
  } finally {
    setLoadingState(false);
  }
}

// ─── GENERATE NEW BRIEF ───────────────────────────────────────
async function triggerBriefingGeneration() {
  const generationTime = new Date().toISOString();

  setLoadingState(true, 'Establishing ground-truth timestamp...');

  // Fetch fresh Wikipedia sidebar facts
  fetchWikiIntel();

  await sleep(400);
  updateLoadingStatus('Fetching 9 live RSS feeds...');

  try {
    updateLoadingStatus('Compiling briefing with Gemini AI...');

    // Sanitize API key: strip any non-ASCII characters that would break fetch headers
    const sanitizedKey = apiKey.replace(/[^\x00-\xff]/g, '').trim();

    const fetchHeaders = { 'Content-Type': 'application/json' };
    const isValidKey = sanitizedKey && !sanitizedKey.includes(' ') && !sanitizedKey.includes('•') && !sanitizedKey.startsWith('Live Briefing');
    if (isValidKey) {
      fetchHeaders['x-api-key'] = sanitizedKey;
    }

    const res = await fetch('/api/generate-brief', {
      method: 'POST',
      headers: fetchHeaders,
      body: JSON.stringify({
        groundedTime: generationTime,
        category:     activeCategory
      })
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.error || 'Briefing compilation failed');
    }

    const brief = await res.json();
    currentBriefing = brief;

    renderBriefing(brief);
    switchTab(activeTab);
    showToast('Briefing generated successfully.', 'success');
  } catch (err) {
    console.error('Generation failed:', err);
    showToast('Failed to generate briefing: ' + err.message, 'error');
  } finally {
    setLoadingState(false);
  }
}

// ─── TAB SWITCHING ────────────────────────────────────────────
function switchTab(tabName) {
  activeTab = tabName;
  localStorage.setItem('wcActiveTab', tabName);

  [tabReaderBtn, tabMarkdownBtn, tabArticlesBtn, tabWorldCupBtn].forEach(btn => {
    const isActive = btn.getAttribute('data-tab') === tabName;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive);
  });

  viewReader.style.display   = (tabName === 'reader'   && currentBriefing) ? 'block' : 'none';
  viewMarkdown.style.display = (tabName === 'markdown' && currentBriefing) ? 'flex'  : 'none';
  viewArticles.style.display = (tabName === 'articles' && currentBriefing) ? 'block' : 'none';
  viewWorldCup.style.display = (tabName === 'worldcup') ? 'flex' : 'none';

  if (tabName === 'worldcup') {
    stateEmpty.style.display = 'none';
    fetchWorldCupSchedule();
  } else if (!currentBriefing) {
    stateEmpty.style.display = 'flex';
  }
}

// ─── LOADING STATE CONTROLLER ─────────────────────────────────
function setLoadingState(isLoading, statusText = '') {
  if (isLoading) {
    stateEmpty.style.display   = 'none';
    viewReader.style.display   = 'none';
    viewMarkdown.style.display = 'none';
    viewArticles.style.display = 'none';
    viewWorldCup.style.display = 'none';
    stateLoading.style.display = 'flex';
    if (statusText) loadingStatusText.textContent = statusText;
    generateBtn.disabled = true;
  } else {
    stateLoading.style.display = 'none';
    generateBtn.disabled = false;

    if (currentBriefing) {
      switchTab(activeTab);
    } else {
      stateEmpty.style.display = 'flex';
    }
  }
}

function updateLoadingStatus(text) {
  loadingStatusText.textContent = text;
}

// ─── RENDER BRIEFING ──────────────────────────────────────────
function renderBriefing(brief) {
  // Intel Reader — render into content sub-area
  if (readerContent) {
    readerContent.innerHTML = parseMarkdownToHtml(brief.briefing);
  }

  // Raw Markdown
  markdownTextarea.value = brief.briefing;

  // Articles Count
  articlesCountVal.textContent = brief.articlesCount || 0;

  // Update sidebar category counts
  updateSidebarCounts(brief);

  // Store articles for search filtering, then render
  window._allArticles = brief.articles || [];
  renderArticlesList();
}

function getSigClass(score) {
  if (score >= 6) return 'high';
  if (score >= 3) return 'med';
  return 'low';
}

function renderArticlesList() {
  let articles = window._allArticles || [];

  if (searchQuery) {
    articles = articles.filter(a =>
      (a.title || '').toLowerCase().includes(searchQuery)
    );
  }

  if (feedSearchCount) {
    feedSearchCount.textContent = `${articles.length} of ${(window._allArticles || []).length}`;
  }

  if (articles.length === 0) {
    articlesList.innerHTML = `
      <div class="empty-state" style="min-height: 120px; padding: 2rem 0;">
        <div class="empty-state-icon" style="font-size: 1.5rem;">No articles match your filter.</div>
      </div>
    `;
    return;
  }

  articlesList.innerHTML = articles.map(art => {
    const pubDate = parseDate(art.pubDate);
    const timeStr = pubDate ? pubDate.toLocaleString('en-IN', {
      hour:   '2-digit',
      minute: '2-digit',
      day:    'numeric',
      month:  'short'
    }) : art.pubDate;

    const sig = art.significance || 0;
    const sigClass = getSigClass(sig);
    const excerpt = art.excerpt || '';

    return `
      <article class="feed-article-card">
        <div class="feed-article-header">
          <a
            href="${escapeHtml(art.link)}"
            target="_blank"
            rel="noopener noreferrer"
            class="feed-article-title"
          >${escapeHtml(art.title)}</a>
          <span class="badge badge-source">${escapeHtml(art.sourceName)}</span>
        </div>
        ${excerpt ? `<div class="feed-article-excerpt">${escapeHtml(excerpt)}</div>` : ''}
        <div class="feed-article-meta">
          <span>Published: ${timeStr}</span>
          <span class="sig-badge ${sigClass}">${sig.toFixed(1)}</span>
        </div>
      </article>
    `;
  }).join('');
}

function updateSidebarCounts(brief) {
  if (!categories.length) return;
  const articles = brief.articles || [];
  const countsMap = {};
  for (const cat of categories) {
    countsMap[cat.id] = 0;
  }
  for (const art of articles) {
    const cat = assignArticleCategory(art);
    if (countsMap[cat] !== undefined) countsMap[cat]++;
  }
  renderSidebarCategories(countsMap);
}

function assignArticleCategory(art) {
  const text = ((art.title || '') + ' ' + (art.excerpt || '')).toLowerCase();
  const src = (art.sourceName || '').toLowerCase();

  const indianSources = ['the indian express', 'the print', 'scroll.in', 'deccan herald', 'ndtv', 'the hindu'];
  const indianKws = ['india', 'indian', 'delhi', 'mumbai', 'modi', 'bjp', 'congress', 'isro', 'rupee', 'lok sabha'];
  const techKws = ['tech', 'technology', 'ai', 'artificial intelligence', 'openai', 'microsoft', 'google', 'nvidia', 'chip', 'cyber', 'software', 'apple'];
  const sportsKws = ['match', 'world cup', 'score', 'cricket', 'football', 'soccer', 'player', 'tennis', 'goal', 'fifa'];
  const financeKws = ['stock', 'market', 'economy', 'inflation', 'gdp', 'crypto', 'shares', 'gold', 'oil', 'billion', 'deal'];

  if (indianSources.includes(src) || indianKws.some(k => text.includes(k))) return 'indian';
  if (techKws.some(k => text.includes(k))) return 'technology';
  if (sportsKws.some(k => text.includes(k))) return 'sports';
  if (financeKws.some(k => text.includes(k))) return 'finance';
  return 'global';
}

// ─── COPY MARKDOWN ────────────────────────────────────────────
function copyMarkdownToClipboard() {
  if (!currentBriefing?.briefing) return;
  navigator.clipboard.writeText(currentBriefing.briefing)
    .then(() => showToast('Markdown briefing copied to clipboard.', 'success'))
    .catch(err => showToast('Failed to copy: ' + err.message, 'error'));
}

// ─── MARKDOWN PARSER ──────────────────────────────────────────
// Handles:
//   - Live Briefing for: ...            => timestamp bar
//   - # Header                          => h1
//   - ### Header                        => h3
//   - - bullet line                     => <li> in <ul>
//   -   indented continuation lines     => appended to current <li>
//   - **bold**, *italic*, [text](url)   => inline formatting
//   - blank lines                       => close any open <ul>
//
function parseMarkdownToHtml(markdown) {
  if (!markdown) return '';
  const lines = markdown.split('\n');
  let html = '';
  let inList = false;
  let pendingLi = null;   // accumulates multi-line list item content

  function flushLi() {
    if (pendingLi !== null) {
      html += `<li>${pendingLi}</li>`;
      pendingLi = null;
    }
  }

  function flushList() {
    flushLi();
    if (inList) {
      html += '</ul>';
      inList = false;
    }
  }

  function parseInline(text) {
    // Bold: **text**
    let out = text.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    // Italic: *text*
    out = out.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em>$1</em>');
    // Markdown links: [text](url)
    out = out.replace(
      /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer" class="briefing-link">$1</a>'
    );
    // Markdown images: ![alt](url)
    out = out.replace(
      /!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g,
      '<img src="$2" alt="$1" class="briefing-image" loading="lazy">'
    );
    return out;
  }

  for (let i = 0; i < lines.length; i++) {
    const raw     = lines[i];
    const trimmed = raw.trim();

    // ── Timestamp line ────────────────────────────────────────
    if (trimmed.startsWith('Live Briefing for:')) {
      flushList();
      html += `<div class="briefing-timestamp">${escapeHtml(trimmed)}</div>`;

    // ── H1 ────────────────────────────────────────────────────
    } else if (trimmed.startsWith('# ')) {
      flushList();
      html += `<h1>${parseInline(escapeHtml(trimmed.substring(2)))}</h1>`;

    // ── H2 ────────────────────────────────────────────────────
    } else if (trimmed.startsWith('## ')) {
      flushList();
      html += `<h2>${parseInline(escapeHtml(trimmed.substring(3)))}</h2>`;

    // ── H3 ────────────────────────────────────────────────────
    } else if (trimmed.startsWith('### ')) {
      flushList();
      html += `<h3>${parseInline(escapeHtml(trimmed.substring(4)))}</h3>`;

    // ── List item start: "- " ─────────────────────────────────
    } else if (trimmed.startsWith('- ')) {
      if (!inList) { html += '<ul>'; inList = true; }
      flushLi();
      pendingLi = parseInline(escapeHtml(trimmed.substring(2)));

    // ── Continuation / indented line (appended to current li) ──
    } else if (raw.match(/^\s{2,}/) && trimmed !== '' && inList && pendingLi !== null) {
      // Append with a line break so alignment stays consistent
      pendingLi += '<br>' + parseInline(escapeHtml(trimmed));

    // ── Blank line ────────────────────────────────────────────
    } else if (trimmed === '') {
      flushList();

    // ── Plain paragraph ───────────────────────────────────────
    } else {
      flushList();
      html += `<p>${parseInline(escapeHtml(trimmed))}</p>`;
    }
  }

  flushList();
  return html;
}

// ─── UTILITIES ────────────────────────────────────────────────
function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function parseDate(str) {
  if (!str) return null;
  try { return new Date(str); } catch { return null; }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ─── WORLD CUP TAB ──────────────────────────────────────────────
let cachedWorldCupData = null;
let worldCupActiveFilter = localStorage.getItem('wcFilter') || 'all';

function setWorldCupFilter(filter) {
  worldCupActiveFilter = filter;
  localStorage.setItem('wcFilter', filter);
  document.querySelectorAll('.wc-filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === filter);
  });
  if (cachedWorldCupData) {
    renderWorldCupSchedule(filter);
  } else {
    fetchWorldCupSchedule();
  }
}

async function fetchWorldCupSchedule() {
  worldCupLoader.style.display = 'block';
  worldCupLoader.textContent = 'Loading match schedule...';
  worldCupSchedule.innerHTML = '';

  try {
    const res = await fetch('/api/world-cup');
    if (!res.ok) throw new Error('Failed to fetch');
    const data = await res.json();
    cachedWorldCupData = data;
    setWorldCupFilter(worldCupActiveFilter);
  } catch (err) {
    console.error('World Cup schedule fetch failed:', err);
    worldCupLoader.style.display = 'block';
    worldCupLoader.textContent = 'Failed to load match schedule. Please try again.';
  }
}

function renderWorldCupSchedule(filter) {
  const data = cachedWorldCupData;
  if (!data || !data.matches || data.matches.length === 0) {
    worldCupLoader.style.display = 'block';
    worldCupLoader.textContent = 'No match data available at this time.';
    return;
  }

  worldCupLoader.style.display = 'none';

  if (filter === 'argentina') {
    renderArgentinaTimeline(data);
    return;
  }

  renderAllMatches(data);
}

function renderAllMatches(data) {
  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10);

  // Group matches by date
  const groups = {};
  for (const m of data.matches) {
    const d = new Date(m.date);
    const dateStr = d.toISOString().slice(0, 10);
    if (!groups[dateStr]) groups[dateStr] = { date: d, matches: [] };
    groups[dateStr].matches.push(m);
  }

  const sortedDates = Object.keys(groups).sort();
  const pastDates = sortedDates.filter(d => d < todayStr);
  const futureDates = sortedDates.filter(d => d >= todayStr);

  let html = '';

  // Previous matches toggle
  if (pastDates.length > 0) {
    const pastCount = pastDates.reduce((sum, d) => sum + groups[d].matches.length, 0);
    html += `
      <button class="wc-prev-toggle" onclick="togglePrevMatches(this)">
        <span class="arrow">&#9654;</span> PREVIOUS MATCHES (${pastCount})
      </button>
      <div class="wc-prev-list">
        ${pastDates.map(dateStr => {
          const g = groups[dateStr];
          const d = g.date;
          const dayLabel = d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
          return g.matches.map(m => {
            const isFinished = m.status === 'Full Time' || m.status === 'Finished';
            const isLive = !isFinished && m.status !== 'Scheduled' && m.score1 !== '' && m.score2 !== '';
            const score = (isLive || isFinished) ? `${m.score1}-${m.score2}` : '–';
            const statusLabel = isLive && m.displayClock ? m.displayClock : (isFinished ? 'Full Time' : '');
            return `
              <div class="wc-prev-row">
                <span class="wc-prev-date">${dayLabel}</span>
                <span class="wc-prev-teams">${escapeHtml(m.team1)} vs ${escapeHtml(m.team2)}</span>
                <span class="wc-prev-score">${score}</span>
                <span class="wc-prev-status ${isLive ? 'live' : ''}">${statusLabel ? escapeHtml(statusLabel) : ''}</span>
              </div>
            `;
          }).join('');
        }).join('')}
      </div>
    `;
  }

  // Future dates horizontal scroll
  html += `<div class="world-cup-schedule-inner">`;
  html += futureDates.map(dateStr => {
    const g = groups[dateStr];
    const d = g.date;
    const dayName = d.toLocaleDateString('en-IN', { weekday: 'short' });
    const monthDay = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

    let badge = '';
    if (dateStr === todayStr) {
      badge = '<span class="wc-date-badge today">TODAY</span>';
    } else {
      const tomorrowUTC = new Date(now);
      tomorrowUTC.setUTCDate(tomorrowUTC.getUTCDate() + 1);
      const tomorrowStr = tomorrowUTC.toISOString().slice(0, 10);
      if (dateStr === tomorrowStr) badge = '<span class="wc-date-badge">TOMORROW</span>';
    }

    return `
      <div class="wc-date-group">
        <div class="wc-date-header">${dayName}, ${monthDay} ${badge}</div>
        ${g.matches.map(m => {
          const matchTime = new Date(m.date).toLocaleTimeString('en-IN', {
            hour: '2-digit', minute: '2-digit', hour12: true
          });

          let scoreClass = 'wc-score scheduled';
          let scoreDisplay = matchTime;
          const isFinished = m.status === 'Full Time' || m.status === 'Finished';
          const isLive = !isFinished && m.status !== 'Scheduled' && m.score1 !== '' && m.score2 !== '';
          if (isLive) {
            scoreClass = 'wc-score live';
            scoreDisplay = `${m.score1} - ${m.score2}`;
          } else if (isFinished) {
            scoreClass = 'wc-score';
            scoreDisplay = `${m.score1} - ${m.score2}`;
          }

          const clockDisplay = isLive && m.displayClock ? escapeHtml(m.displayClock) : '';
          const statusDisplay = clockDisplay ? clockDisplay : (isFinished ? 'Full Time' : '');

          return `
            <div class="wc-match-card">
              <div class="wc-team home">${escapeHtml(m.team1)}</div>
              <div class="${scoreClass}">${scoreDisplay}</div>
              <div class="wc-team away">${escapeHtml(m.team2)}</div>
              <div class="wc-match-meta">
                ${m.group ? `<span>${escapeHtml(m.group)}</span>` : ''}
                ${m.venue ? `<span>${escapeHtml(m.venue)}</span>` : ''}
                ${statusDisplay ? `<span>${statusDisplay}</span>` : ''}
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }).join('');
  html += `</div>`;

  worldCupSchedule.innerHTML = html;
}

function renderArgentinaTimeline(data) {
  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10);

  const filtered = data.matches.filter(m =>
    m.team1.toLowerCase().includes('argentina') ||
    m.team2.toLowerCase().includes('argentina')
  );

  if (filtered.length === 0) {
    worldCupSchedule.innerHTML = '<div class="world-cup-loader" style="display:block">No Argentina matches found in the schedule.</div>';
    return;
  }

  filtered.sort((a, b) => a.date.localeCompare(b.date));

  worldCupSchedule.innerHTML = `
    <div class="wc-argentina-list">
      <div class="wc-arg-header" aria-hidden="true"></div>
      ${filtered.map(m => {
        const d = new Date(m.date);
        const dayLabel = d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
        const matchTime = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });

        let scoreClass = 'wc-arg-score scheduled';
        let scoreDisplay = matchTime;
        const isFinished = m.status === 'Full Time' || m.status === 'Finished';
        const isLive = !isFinished && m.status !== 'Scheduled' && m.score1 !== '' && m.score2 !== '';
        if (isLive) {
          scoreClass = 'wc-arg-score live';
          scoreDisplay = `${m.score1} - ${m.score2}`;
        } else if (isFinished) {
          scoreClass = 'wc-arg-score';
          scoreDisplay = `${m.score1} - ${m.score2}`;
        }

        const clockDisplay = isLive && m.displayClock ? escapeHtml(m.displayClock) : '';
        const statusDisplay = clockDisplay ? clockDisplay : (isFinished ? 'Full Time' : '');
        const metaDisplay = statusDisplay ? `${statusDisplay}${m.venue ? ` &middot; ${escapeHtml(m.venue)}` : ''}` : (m.venue ? escapeHtml(m.venue) : '');

        const isArgTeam1 = m.team1.toLowerCase().includes('argentina');
        const teamsDisplay = isArgTeam1
          ? `<span class="highlight">${escapeHtml(m.team1)}</span> vs ${escapeHtml(m.team2)}`
          : `${escapeHtml(m.team1)} vs <span class="highlight">${escapeHtml(m.team2)}</span>`;

        return `
          <div class="wc-arg-row">
            <div class="wc-arg-date">${dayLabel}</div>
            <div class="wc-arg-teams">${teamsDisplay}</div>
            <div class="${scoreClass}">${scoreDisplay}</div>
            <div class="wc-arg-meta">${metaDisplay}</div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function togglePrevMatches(btn) {
  btn.classList.toggle('open');
  const list = btn.nextElementSibling;
  if (list) list.classList.toggle('open');
}

// ─── IMAGE MODAL ──────────────────────────────────────────────
function openImageModal(src, alt) {
  modalImage.src = src;
  modalImage.alt = alt || '';
  imageModal.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeImageModal() {
  imageModal.classList.remove('open');
  document.body.style.overflow = '';
  modalImage.src = '';
}

// ─── TOAST NOTIFICATIONS ──────────────────────────────────────
function showToast(message, type = 'info') {
  const existing = document.getElementById('toastNotification');
  if (existing) existing.remove();

  const colors = {
    success: { border: '#22c55e' },
    error:   { border: '#ef4444' },
    info:    { border: '#F25623' },
  };
  const c = colors[type] || colors.info;

  const toast = document.createElement('div');
  toast.id = 'toastNotification';
  toast.style.cssText = `
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    background: #171717;
    border: 1.5px solid ${c.border};
    color: #FFFFFF;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.75rem 1.25rem;
    border-radius: 3px;
    box-shadow: 4px 4px 0px 0px ${c.border};
    z-index: 9999;
    max-width: 380px;
    animation: toast-in 0.2s ease;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'toast-out 0.2s ease forwards';
    setTimeout(() => toast.remove(), 250);
  }, 3000);
}

// Toast keyframes
const toastStyle = document.createElement('style');
toastStyle.textContent = `
  @keyframes toast-in  { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes toast-out { from { opacity: 1; } to { opacity: 0; transform: translateY(10px); } }
  .briefing-link {
    color: var(--color-orange, #F25623);
    text-decoration: underline;
    text-decoration-color: rgba(242,86,35,0.4);
    text-underline-offset: 2px;
    font-weight: 600;
    transition: color 0.15s ease;
  }
  .briefing-link:hover { color: #c43e14; }
`;
document.head.appendChild(toastStyle);
