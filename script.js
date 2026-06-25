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
const stateEmpty          = document.getElementById('stateEmpty');
const stateLoading        = document.getElementById('stateLoading');
const loadingStatusText   = document.getElementById('loadingStatusText');
const viewReader          = document.getElementById('viewReader');
const viewMarkdown        = document.getElementById('viewMarkdown');
const viewArticles        = document.getElementById('viewArticles');
const markdownTextarea    = document.getElementById('markdownTextarea');
const articlesCountVal    = document.getElementById('articlesCountVal');
const articlesList        = document.getElementById('articlesList');
const copyMarkdownBtn     = document.getElementById('copyMarkdownBtn');
const groundedTimeVal     = document.getElementById('groundedTimeVal');
const sourcesList         = document.getElementById('sourcesList');

// ─── APP STATE ────────────────────────────────────────────────
let apiKey          = '';
let showApiKey      = false;
let activeTab       = 'reader';
let currentBriefing = null;
let activeCategory  = 'global';
let localClockTimer = null;

// ─── INITIALIZATION ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Load saved API key from localStorage
  const savedKey = localStorage.getItem('GEMINI_API_KEY');
  if (savedKey) {
    apiKey = savedKey;
    apiKeyInput.value = savedKey;
  }

  // Check if API key is already configured on the server-side
  checkServerConfig();

  // Start real-time clock
  startGroundedClock();

  // Load sources into sidebar
  fetchSources();

  // Load default briefing
  loadLatestBrief(activeCategory);

  // ─── EVENT LISTENERS ──────────────────────────────────────
  apiKeyInput.addEventListener('input', (e) => {
    apiKey = e.target.value.trim();
    localStorage.setItem('GEMINI_API_KEY', apiKey);
  });

  toggleKeyVisibility.addEventListener('click', () => {
    showApiKey = !showApiKey;
    apiKeyInput.type = showApiKey ? 'text' : 'password';
    toggleKeyVisibility.textContent = showApiKey ? 'Hide' : 'Show';
  });

  generateBtn.addEventListener('click', triggerBriefingGeneration);
  copyMarkdownBtn.addEventListener('click', copyMarkdownToClipboard);

  // Tab switching
  [tabReaderBtn, tabMarkdownBtn, tabArticlesBtn].forEach(btn => {
    btn.addEventListener('click', (e) => {
      switchTab(e.currentTarget.getAttribute('data-tab'));
    });
  });
});

// Check if server already has the Gemini API Key in its environment
async function checkServerConfig() {
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
function startGroundedClock() {
  const updateClock = () => {
    const now = new Date();
    groundedTimeVal.textContent = now.toLocaleString('en-IN', {
      day:          '2-digit',
      month:        'short',
      year:         'numeric',
      hour:         '2-digit',
      minute:       '2-digit',
      second:       '2-digit',
      hour12:       true,
      timeZoneName: 'short'
    });
  };
  updateClock();
  localClockTimer = setInterval(updateClock, 1000);
}

function stopGroundedClock(frozenTime) {
  if (localClockTimer) clearInterval(localClockTimer);
  localClockTimer = null;
  if (frozenTime) {
    groundedTimeVal.textContent = new Date(frozenTime).toLocaleString('en-IN', {
      day:          '2-digit',
      month:        'short',
      year:         'numeric',
      hour:         '2-digit',
      minute:       '2-digit',
      second:       '2-digit',
      hour12:       true,
      timeZoneName: 'short'
    });
  }
}

// ─── FETCH SOURCES ───────────────────────────────────────────
async function fetchSources() {
  if (!sourcesList) return;
  try {
    const res = await fetch('/api/sources');
    if (!res.ok) return;
    const sources = await res.json();
    sourcesList.innerHTML = sources.map(src => `
      <div class="sources-sidebar-item">
        <span class="sources-sidebar-dot">●</span>
        <a href="${src.siteUrl}" target="_blank" rel="noopener noreferrer">${src.name}</a>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load sources:', err);
  }
}

// ─── LOAD LATEST BRIEF ────────────────────────────────────────
async function loadLatestBrief(category) {
  setLoadingState(true, 'Loading latest briefing...');
  try {
    const res = await fetch(`/api/latest-brief?category=${category}&t=${Date.now()}`);
    if (!res.ok) throw new Error('Briefing not found');

    const brief = await res.json();
    currentBriefing = brief;

    stopGroundedClock(brief.timestamp);
    renderBriefing(brief);
    switchTab('reader');
  } catch (err) {
    console.error('Error loading latest brief:', err);
    currentBriefing = null;
    setLoadingState(false);
  } finally {
    setLoadingState(false);
  }
}

// ─── GENERATE NEW BRIEF ───────────────────────────────────────
async function triggerBriefingGeneration() {
  const generationTime = new Date().toISOString();

  stopGroundedClock(generationTime);
  setLoadingState(true, 'Establishing ground-truth timestamp...');

  await sleep(400);
  updateLoadingStatus('Fetching 9 live RSS feeds...');

  try {
    updateLoadingStatus('Compiling briefing with Gemini AI...');

    // Sanitize API key: strip any non-ASCII characters that would break fetch headers
    const sanitizedKey = apiKey.replace(/[^\x00-\xff]/g, '').trim();

    const fetchHeaders = { 'Content-Type': 'application/json' };
    if (sanitizedKey) {
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
    switchTab('reader');
    showToast('Briefing generated successfully.', 'success');
  } catch (err) {
    console.error('Generation failed:', err);
    showToast('Failed to generate briefing: ' + err.message, 'error');
    startGroundedClock();
  } finally {
    setLoadingState(false);
  }
}

// ─── TAB SWITCHING ────────────────────────────────────────────
function switchTab(tabName) {
  activeTab = tabName;

  [tabReaderBtn, tabMarkdownBtn, tabArticlesBtn].forEach(btn => {
    const isActive = btn.getAttribute('data-tab') === tabName;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive);
  });

  viewReader.style.display   = (tabName === 'reader'   && currentBriefing) ? 'block' : 'none';
  viewMarkdown.style.display = (tabName === 'markdown' && currentBriefing) ? 'flex'  : 'none';
  viewArticles.style.display = (tabName === 'articles' && currentBriefing) ? 'block' : 'none';
}

// ─── LOADING STATE CONTROLLER ─────────────────────────────────
function setLoadingState(isLoading, statusText = '') {
  if (isLoading) {
    stateEmpty.style.display   = 'none';
    viewReader.style.display   = 'none';
    viewMarkdown.style.display = 'none';
    viewArticles.style.display = 'none';
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
  // Intel Reader
  viewReader.innerHTML = parseMarkdownToHtml(brief.briefing);

  // Raw Markdown
  markdownTextarea.value = brief.briefing;

  // Articles Count
  articlesCountVal.textContent = brief.articlesCount || 0;

  // Articles list
  if (!brief.articles || brief.articles.length === 0) {
    articlesList.innerHTML = `
      <div class="empty-state" style="min-height: 180px;">
        <div class="empty-state-icon">No articles passed the 12-hour recency filter for this category.</div>
      </div>
    `;
    return;
  }

  articlesList.innerHTML = brief.articles.map(art => {
    const pubDate = parseDate(art.pubDate);
    const timeStr = pubDate ? pubDate.toLocaleString('en-IN', {
      hour:   '2-digit',
      minute: '2-digit',
      day:    'numeric',
      month:  'short'
    }) : art.pubDate;

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
        <div class="feed-article-meta">Published: ${timeStr}</div>
      </article>
    `;
  }).join('');
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
