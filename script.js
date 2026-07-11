/* ============================================================
   EXECUTIVE BRIEFING SUMMARIZER — CLIENT LOGIC
   Industrial Edition v2.0
   ============================================================ */

// ─── DOM ELEMENTS ────────────────────────────────────────────
const apiKeyInput         = document.getElementById('apiKeyInput');
const toggleKeyVisibility = document.getElementById('toggleKeyVisibility');
const generateBtn         = document.getElementById('generateBtn');
const tabHomepageBtn      = document.getElementById('tabHomepageBtn');
const tabReaderBtn        = document.getElementById('tabReaderBtn');
const tabMarkdownBtn      = document.getElementById('tabMarkdownBtn');
const tabArticlesBtn      = document.getElementById('tabArticlesBtn');
const tabWorldCupBtn      = document.getElementById('tabWorldCupBtn');
const stateEmpty          = document.getElementById('stateEmpty');
const stateLoading        = document.getElementById('stateLoading');
const loadingStatusText   = document.getElementById('loadingStatusText');
const viewHomepage        = document.getElementById('viewHomepage');
const homepageContent     = document.getElementById('homepageContent');
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
const sidebarAdditional   = document.getElementById('sidebarAdditional');
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
let activeTab       = localStorage.getItem('wcActiveTab') || 'homepage';
let currentBriefing = null;
let activeCategory  = localStorage.getItem('readerCategory') || 'global';


// ─── INITIALIZATION ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Load saved API key from localStorage
  const savedKey = localStorage.getItem('GEMINI_API_KEY');
  if (savedKey) {
    const isInvalid = savedKey.includes(' ') || savedKey.includes('\u2022') || savedKey.startsWith('Live Briefing');
    if (isInvalid) {
      localStorage.removeItem('GEMINI_API_KEY');
    } else {
      apiKey = savedKey;
      if (apiKeyInput) apiKeyInput.value = savedKey;
    }
  }

  checkServerConfig();
  fetchSources();

  loadLatestBrief(activeTab === 'homepage' ? 'homepage' : 'global').then(() => {
    setTimeout(() => triggerBriefingGeneration(), 800);
  });

  fetchWikiIntel();
  initWorldCupRightSidebar();

  // ─── GENERATE BUTTON ────────────────────────────────────────
  generateBtn.addEventListener('click', triggerBriefingGeneration);


  // ─── THEME TOGGLE ───────────────────────────────────────────
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      const isDark = document.documentElement.classList.contains('dark');
      if (isDark) {
        document.documentElement.classList.remove('dark');
        localStorage.setItem('theme', 'light');
        if (themeIcon) themeIcon.textContent = 'dark_mode';
        document.body.style.backgroundColor = '#f7f3ee';
        document.body.style.color = '#2d2a26';
      } else {
        document.documentElement.classList.add('dark');
        localStorage.setItem('theme', 'dark');
        if (themeIcon) themeIcon.textContent = 'light_mode';
        document.body.style.backgroundColor = '#1e1e1e';
        document.body.style.color = '#f4f4f5';
      }
    });
  }
  const currentTheme = localStorage.getItem('theme') || 'dark';
  if (themeIcon) themeIcon.textContent = currentTheme === 'dark' ? 'light_mode' : 'dark_mode';

  // ─── MOBILE SIDEBAR TOGGLE ──────────────────────────────────
  const mobileSidebarToggle = document.getElementById('mobileSidebarToggle');
  if (mobileSidebarToggle) {
    mobileSidebarToggle.addEventListener('click', () => {
      const sidebar = document.getElementById('leftSidebar');
      const overlay = document.getElementById('mobileSidebarOverlay');
      if (sidebar) sidebar.classList.toggle('mobile-open');
      if (overlay) overlay.classList.toggle('hidden');
      // Close right sidebar if open
      const rightSidebar = document.getElementById('rightSidebar');
      const rightOverlay = document.getElementById('mobileRightSidebarOverlay');
      if (rightSidebar) rightSidebar.classList.remove('mobile-open');
      if (rightOverlay) rightOverlay.classList.add('hidden');
    });
  }

  // ─── MOBILE RIGHT SIDEBAR TOGGLE ────────────────────────────
  const mobileRightSidebarToggle = document.getElementById('mobileRightSidebarToggle');
  if (mobileRightSidebarToggle) {
    mobileRightSidebarToggle.addEventListener('click', () => {
      const sidebar = document.getElementById('rightSidebar');
      const overlay = document.getElementById('mobileRightSidebarOverlay');
      if (sidebar) sidebar.classList.toggle('mobile-open');
      if (overlay) overlay.classList.toggle('hidden');
      // Close left sidebar if open
      const leftSidebar = document.getElementById('leftSidebar');
      const leftOverlay = document.getElementById('mobileSidebarOverlay');
      if (leftSidebar) leftSidebar.classList.remove('mobile-open');
      if (leftOverlay) leftOverlay.classList.add('hidden');
    });
  }

  // ─── LEFT SIDEBAR MAIN NAV BUTTONS ──────────────────────────
  document.querySelectorAll('.sidebar-nav-btn').forEach(btn => {
    const tab = btn.getAttribute('data-tab');
    if (tab) {
      btn.classList.toggle('active', tab === activeTab);
      btn.addEventListener('click', () => {
        // If clicking Home, clear category active highlights
        if (tab === 'homepage') {
          const readerSubtabs = document.getElementById('readerSubtabs');
          if (readerSubtabs) {
            readerSubtabs.querySelectorAll('.sidebar-cat-btn').forEach(b => b.classList.remove('active'));
          }
        }
        switchTab(tab);
        closeMobileSidebar();
      });
    }
  });

  // ─── LEFT SIDEBAR CATEGORY SUB-BUTTONS ──────────────────────
  const readerSubtabs = document.getElementById('readerSubtabs');
  if (readerSubtabs) {
    readerSubtabs.querySelectorAll('.sidebar-cat-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.category === activeCategory && activeTab === 'reader');
    });

    readerSubtabs.addEventListener('click', (e) => {
      const btn = e.target.closest('.sidebar-cat-btn');
      if (!btn) return;
      const cat = btn.dataset.category;
      
      // Highlight category, un-highlight Home
      readerSubtabs.querySelectorAll('.sidebar-cat-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.sidebar-nav-btn').forEach(b => b.classList.remove('active'));

      activeCategory = cat;
      localStorage.setItem('readerCategory', cat);
      
      // Force panel to show Reader View
      switchTab('reader');
      switchReaderCategory(cat);
      closeMobileSidebar();
    });
  }

  // Right sidebar: "View All" filtered feed button
  const tabArticlesBtn2 = document.getElementById('tabArticlesBtn');
  if (tabArticlesBtn2) {
    tabArticlesBtn2.addEventListener('click', () => {
      switchTab('articles');
      closeMobileRightSidebar();
    });
  }

  // Articles View category filter sub-nav click handler
  const articlesFilterNav = document.getElementById('articlesFilterNav');
  if (articlesFilterNav) {
    articlesFilterNav.addEventListener('click', (e) => {
      const btn = e.target.closest('.art-filter-tab-btn');
      if (!btn) return;
      const cat = btn.dataset.category;
      
      // Update local storage and global state
      activeCategory = cat;
      localStorage.setItem('readerCategory', cat);
      
      // Highlight correct sub-nav button
      articlesFilterNav.querySelectorAll('.art-filter-tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.category === cat);
        b.classList.toggle('font-semibold', b.dataset.category === cat);
      });
      
      // Sync left sidebar highlights
      const readerSubtabs = document.getElementById('readerSubtabs');
      if (readerSubtabs) {
        readerSubtabs.querySelectorAll('.sidebar-cat-btn').forEach(b => {
          b.classList.toggle('active', b.dataset.category === cat);
        });
        document.querySelectorAll('.sidebar-nav-btn').forEach(b => b.classList.remove('active'));
      }
      
      // Re-render views
      if (currentBriefing) {
        if (readerContent) {
          readerContent.innerHTML = renderReaderView(currentBriefing);
        }
        renderArticlesList();
      }
    });
  }

  // Right sidebar: "Full View" world cup button
  document.querySelectorAll('.sidebar-wc-expand-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab('worldcup');
      closeMobileRightSidebar();
    });
  });

  // World Cup tab filter buttons
  document.querySelectorAll('.wc-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      setWorldCupFilter(btn.dataset.filter);
    });
  });

  // ─── IMAGE MODAL ────────────────────────────────────────────
  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeImageModal);
  if (imageModal) imageModal.addEventListener('click', (e) => {
    if (e.target === imageModal) closeImageModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && imageModal && imageModal.classList.contains('open')) closeImageModal();
  });
  if (viewReader) viewReader.addEventListener('click', (e) => {
    const img = e.target.closest('.briefing-image');
    if (img) openImageModal(img.src, img.alt);
  });

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



// ─── FETCH WIKIPEDIA FACTS ──────────────────────────────────
async function fetchWikiIntel() {
  if (!wikiDykText || !wikiOtdText) return;
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
    updateLoadingStatus('Compiling brief...');

    // Sanitize API key
    const sanitizedKey = apiKey.replace(/[^\x00-\xff]/g, '').trim();

    const fetchHeaders = { 'Content-Type': 'application/json' };
    const isValidKey = sanitizedKey && !sanitizedKey.includes(' ') && !sanitizedKey.includes('\u2022') && !sanitizedKey.startsWith('Live Briefing');
    if (isValidKey) {
      fetchHeaders['x-api-key'] = sanitizedKey;
    }

    const res = await fetch('/api/generate-brief', {
      method: 'POST',
      headers: fetchHeaders,
      body: JSON.stringify({
        groundedTime: generationTime,
        category: activeTab === 'homepage' ? 'homepage' : 'global'
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

// ─── RENDER BRIEFING ─────────────────────────────────────────────
function renderBriefing(brief) {
  if (homepageContent) {
    homepageContent.innerHTML = renderHomepageView(brief);
  }
  if (readerContent) {
    readerContent.innerHTML = renderReaderView(brief);
  }
  if (articlesCountVal) articlesCountVal.textContent = brief.articlesCount || 0;

  window._allStories = (brief.stories || []);
  renderArticlesList();
  renderRightSidebarArticles(brief.stories || []);
}

// ─── RIGHT SIDEBAR HELPERS ────────────────────────────────────────
function renderRightSidebarArticles(stories) {
  const container = document.getElementById('rightSidebarArticles');
  if (!container) return;
  if (stories.length === 0) {
    container.innerHTML = '<div class="text-xs font-mono" style="color: var(--color-dark-gray);">No articles yet.</div>';
    return;
  }
  // Show primary source for each story
  container.innerHTML = stories.map(story => {
    const primary = story.primary_source || {};
    return `
      <a href="${escapeHtml(primary.url)}" target="_blank" rel="noopener noreferrer" class="right-sidebar-article block">
        <div class="right-sidebar-article-title">${escapeHtml(story.primary_headline)}</div>
        <div class="right-sidebar-article-meta">${escapeHtml(primary.source_name)} ${story.source_count > 1 ? `+${story.source_count - 1} more` : ''}</div>
      </a>
    `;
  }).join('');
}

async function initWorldCupRightSidebar() {
  const container = document.getElementById('rightSidebarWC');
  if (!container) return;
  try {
    const res = await fetch('/api/world-cup');
    if (!res.ok) throw new Error('WC fetch failed');
    const data = await res.json();
    const matches = data.matches || [];
    
    if (matches.length === 0) {
      container.innerHTML = '<div class="text-xs font-mono" style="color: var(--color-dark-gray);">No matches scheduled.</div>';
      return;
    }
    
    // Find the next upcoming/scheduled match
    const now = new Date();
    let nextMatch = matches.find(m => {
      const matchDate = new Date(m.date);
      return matchDate >= now && (m.status === 'Scheduled' || m.status === 'Future');
    });
    
    // Fallback if all matches are past/finished
    if (!nextMatch) {
      nextMatch = matches[matches.length - 1];
    }
    
    const home = escapeHtml(nextMatch.team1);
    const away = escapeHtml(nextMatch.team2);
    
    const matchDateObj = new Date(nextMatch.date);
    const dateLabel = matchDateObj.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
    const timeLabel = matchDateObj.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    
    container.innerHTML = `
      <div class="wc-mini-match">
        <div class="wc-mini-teams" style="text-align:left;">${home}</div>
        <div class="wc-mini-score">vs</div>
        <div class="wc-mini-teams" style="text-align:right;">${away}</div>
        <div class="wc-mini-status" style="grid-column: 1 / -1;">${dateLabel} \u00b7 ${timeLabel} \u00b7 ${escapeHtml(nextMatch.venue || 'FIFA WC 2026')}</div>
      </div>
    `;
  } catch (e) {
    container.innerHTML = '<div class="text-xs font-mono" style="color: var(--color-dark-gray);">Match data unavailable.</div>';
  }
}

// ─── LOADING STATE CONTROLLER ─────────────────────────────────
function setLoadingState(isLoading, statusText = '') {
  if (isLoading) {
    stateEmpty.style.display   = 'none';
    viewHomepage.style.display = 'none';
    viewReader.style.display   = 'none';

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

// ─── TAB SWITCHING ─────────────────────────────────────────────
function switchTab(tabName) {
  activeTab = tabName;
  localStorage.setItem('wcActiveTab', tabName);

  // Update sidebar-nav-btn active states
  document.querySelectorAll('.sidebar-nav-btn').forEach(btn => {
    const isActive = btn.getAttribute('data-tab') === tabName;
    btn.classList.toggle('active', isActive);
  });

  // Show/hide content panes
  if (viewHomepage) viewHomepage.style.display = (tabName === 'homepage' && currentBriefing) ? 'block' : 'none';
  if (viewReader)   viewReader.style.display   = (tabName === 'reader'   && currentBriefing) ? 'block' : 'none';

  if (viewArticles) viewArticles.style.display = (tabName === 'articles' && currentBriefing) ? 'block' : 'none';
  if (viewWorldCup) viewWorldCup.style.display = (tabName === 'worldcup') ? 'flex' : 'none';



  if (tabName === 'worldcup') {
    if (stateEmpty) stateEmpty.style.display = 'none';
    fetchWorldCupSchedule();
  } else if (!currentBriefing) {
    if (stateEmpty) stateEmpty.style.display = 'flex';
  }
}


function updateLoadingStatus(text) {
  loadingStatusText.textContent = text;
}


const CATEGORY_LABELS = {
  'Finance': 'Business, Markets & Economy',
  'Technology': 'Technology & Innovation',
  'Geopolitics': 'Geopolitics & World News',
  'Science': 'Science, Health & Environment',
  'Sports': 'Sports',
  'Culture': 'Culture, Entertainment & Arts',
  'Society': 'Lifestyle & Society'
};

const CATEGORY_ORDER = ['Finance', 'Technology', 'Geopolitics', 'Science', 'Sports', 'Culture', 'Society'];

// ─── HOMEPAGE VIEW ────────────────────────────────────────────
function renderHomepageView(brief) {
  const stories = brief.stories || [];

  if (!stories || stories.length === 0) {
    return '<div class="empty-state" style="min-height: 120px; padding: 2rem 0;"><div class="empty-state-text">No articles available. Click Generate Latest Update.</div></div>';
  }

  const ranked = [...stories].sort((a, b) => b.source_count - a.source_count || b.combined_score - a.combined_score);

  let html = '';

  // ── THE HEADLINE — top 5 stories ──────────────────────────
  const headline = ranked.slice(0, 5);
  const headlineIds = new Set(headline.map(s => s.story_id));

  if (headline.length > 0) {
    html += `<h2 class="font-label-caps text-sm uppercase tracking-widest font-bold pb-2 mt-6 border-b border-[var(--color-border-heavy)] text-[var(--color-black)] dark:text-white" style="border-color: var(--color-border-heavy);">The Headline</h2>`;
    html += '<div class="space-y-10 mt-4">';
    for (const story of headline) {
      html += renderHomepageStory(story, false);
    }
    html += '</div>';
  }

  // ── TODAY'S TOP STORIES — next 3 ──────────────────────────
  const topCandidates = ranked.filter(s => !headlineIds.has(s.story_id));
  const topStories = topCandidates.slice(0, 3);
  const topStoryIds = new Set(topStories.map(s => s.story_id));

  if (topStories.length > 0) {
    html += `<h2 class="font-label-caps text-sm uppercase tracking-widest font-bold pb-2 mt-6 border-b border-[var(--color-border-heavy)] text-[var(--color-black)] dark:text-white" style="border-color: var(--color-border-heavy);">Today's Top Stories</h2>`;
    html += '<div class="space-y-10 mt-4">';
    topStories.forEach((story, idx) => {
      html += renderHomepageStory(story, true, idx + 1);
    });
    html += '</div>';
  }

  // ── CATEGORY BREAKDOWN — remaining grouped ────────────────
  const usedIds = new Set([...headlineIds, ...topStoryIds]);
  const remaining = ranked.filter(s => !usedIds.has(s.story_id));

  const grouped = {};
  for (const story of remaining) {
    const cat = story.category;
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(story);
  }

  for (const cat of CATEGORY_ORDER) {
    const storiesInCat = grouped[cat];
    if (!storiesInCat || storiesInCat.length === 0) continue;

    const label = CATEGORY_LABELS[cat] || cat;
    html += `<h2 class="font-label-caps text-sm uppercase tracking-widest font-bold pb-2 mt-6 border-b border-[var(--color-border-heavy)] text-[var(--color-black)] dark:text-white" style="border-color: var(--color-border-heavy);">${label}</h2>`;
    html += '<div class="space-y-10 mt-4">';
    for (const story of storiesInCat.slice(0, 5)) {
      html += renderHomepageStory(story, false);
    }
    html += '</div>';
  }

  return html;
}

function renderHomepageStory(story, numbered, num) {
  const primary = story.primary_source || {};
  const primaryUrl = primary.url || '';
  const primaryName = primary.source_name || '';
  const brief = story.brief || '';
  const extraCount = story.total_count - 1;

  const sourcesHtml = extraCount > 0 ? renderSourcesList(story.sources, primaryUrl) : '';

  const numberHtml = numbered
    ? `<span class="font-headline-md font-bold text-lg flex-shrink-0" style="color: var(--color-orange);">${num}.</span>`
    : '';

  const containerClass = numbered ? 'flex items-start gap-3' : '';

  return `
    <div class="${containerClass}">
      ${numberHtml}
      <div>
        <p class="font-body-md leading-relaxed text-sm font-bold" style="color: var(--color-black);">
          <a href="${escapeHtml(primaryUrl)}" target="_blank" rel="noopener noreferrer" class="headline-link hover:text-[var(--color-orange)] transition-colors">${escapeHtml(story.primary_headline)}</a>
          <span class="source-badge">${escapeHtml(primaryName)}</span>
          ${extraCount > 0 ? `<span class="font-label-data text-[10px] text-[var(--color-dark-gray)] font-mono ml-2">+${extraCount} other source${extraCount > 1 ? 's' : ''}</span>` : ''}
        </p>
        ${brief ? renderExcerpt(brief, 'font-body-md leading-relaxed text-sm mt-1', 'color: var(--color-dark-gray);') : ''}
        ${sourcesHtml}
      </div>
    </div>
  `;
}

function renderSourcesList(sources, excludeUrl) {
  const others = sources.filter(s => s.url !== excludeUrl);
  if (others.length === 0) return '';

  return `
    <button class="reader-cluster-toggle mt-2" onclick="toggleSublist(this)">Also reported by \u25B6</button>
    <div class="reader-cluster-sublist">` +
    others.map(s => {
      const pubDate = parseDate(s.published_at);
      const timeStr = pubDate ? pubDate.toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' }) : '';
      return `
        <div class="reader-cluster-subitem">
          <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" class="reader-cluster-sublink">${escapeHtml(s.headline)}</a>
          <span class="badge badge-source">${escapeHtml(s.source_name)}</span>
          <span class="reader-cluster-subtime">${timeStr}</span>
        </div>
      `;
    }).join('') + `</div>`;
}

// ─── RENDER EXCERPT (multi-paragraph) ────────────────────────
function renderExcerpt(text, cssClass, cssStyle) {
  if (!text) return '';
  const paras = text.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
  if (paras.length === 0) return '';
  return paras.map(p =>
    `<p class="${cssClass}" style="${cssStyle}">${escapeHtml(p)}</p>`
  ).join('\n');
}

function storyMatchesCategory(story, category) {
  if (category === 'global') return true;
  return story.category.toLowerCase() === category.toLowerCase();
}

// ─── READER VIEW ─────────────────────────────────────────────
function renderReaderView(brief) {
  const stories = brief.stories || [];

  if (!stories || stories.length === 0) {
    return '<div class="empty-state" style="min-height: 120px; padding: 2rem 0;"><div class="empty-state-text">No articles available for this category.</div></div>';
  }

  const filtered = stories.filter(s => storyMatchesCategory(s, activeCategory));

  if (filtered.length === 0) {
    return '<div class="empty-state" style="min-height: 120px; padding: 2rem 0;"><div class="empty-state-text">No articles available for this category.</div></div>';
  }

  let html = '';
  for (const story of filtered) {
    const primary = story.primary_source || {};
    const primaryUrl = primary.url || '';
    const primaryName = primary.source_name || '';
    const pubDate = parseDate(primary.published_at);
    const timeStr = pubDate ? pubDate.toLocaleString('en-IN', {
      hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short'
    }) : '';
    const extraCount = story.total_count - 1;
    const brief = story.brief || '';

    const sourcesHtml = extraCount > 0 ? renderSourcesList(story.sources, primaryUrl) : '';

    html += `
      <article class="group cursor-pointer space-y-3 py-4 border-b border-[var(--color-border-heavy)]" style="border-color: var(--color-border-heavy);">
        <h2 class="font-headline-md text-xl font-bold leading-snug text-primary-container transition-colors">
          <a href="${escapeHtml(primaryUrl)}" target="_blank" rel="noopener noreferrer" class="headline-link">${escapeHtml(story.primary_headline)}</a>
        </h2>
        <div class="flex items-center gap-2">
          <span class="source-badge">${escapeHtml(primaryName)}</span>
          ${extraCount > 0 ? `<span class="font-label-data text-[10px] text-[var(--color-dark-gray)] font-mono">+${extraCount} other source${extraCount > 1 ? 's' : ''}</span>` : ''}
          <span class="font-label-data text-[10px] text-[var(--color-dark-gray)] font-mono">${timeStr}</span>
        </div>
        ${brief ? renderExcerpt(brief, 'font-body-md leading-relaxed text-sm', 'color: var(--color-black);') : ''}
        ${sourcesHtml}
      </article>
    `;
  }

  return html;
}

function switchReaderCategory(category) {
  activeCategory = category;
  localStorage.setItem('readerCategory', category);
  // Sync mobile subtab if it exists
  const syncMobileSubtab = (cat) => {
    const subNav = document.getElementById('articlesFilterNav');
    if (subNav) {
      subNav.querySelectorAll('.art-filter-tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.category === cat);
        b.classList.toggle('font-semibold', b.dataset.category === cat);
      });
    }
  };
  syncMobileSubtab(category);
  if (currentBriefing) {
    if (readerContent) {
      readerContent.innerHTML = renderReaderView(currentBriefing);
    }
    renderArticlesList();
  }
}

function renderArticlesList() {
  const stories = window._allStories || [];
  if (stories.length === 0) {
    articlesList.innerHTML = `
      <div class="empty-state" style="min-height: 120px; padding: 2rem 0;">
        <div class="empty-state-text">No articles available.</div>
      </div>
    `;
    return;
  }

  const filtered = stories.filter(s => storyMatchesCategory(s, activeCategory));
  if (filtered.length === 0) {
    articlesList.innerHTML = `
      <div class="empty-state" style="min-height: 120px; padding: 2rem 0;">
        <div class="empty-state-text">No articles available for this category.</div>
      </div>
    `;
    return;
  }

  const grouped = {};
  for (const story of filtered) {
    const cat = story.category;
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(story);
  }

  const categoryLabels = {
    'Finance': 'Business, Markets & Economy',
    'Technology': 'Technology & Innovation',
    'Geopolitics': 'Geopolitics & World News',
    'Science': 'Science, Health & Environment',
    'Sports': 'Sports',
    'Culture': 'Culture, Entertainment & Arts',
    'Society': 'Lifestyle & Society'
  };
  const categoriesList = ['Finance', 'Technology', 'Geopolitics', 'Science', 'Sports', 'Culture', 'Society'];

  let html = '';
  for (const cat of categoriesList) {
    const storiesInCat = grouped[cat];
    if (!storiesInCat || storiesInCat.length === 0) continue;

    const primary = storiesInCat[0].primary_source || {};
    html += `
      <div class="category-group space-y-4 my-6">
        <h3 class="font-label-caps text-sm uppercase tracking-widest font-bold pb-2 border-b border-[var(--color-border-heavy)]" style="color: var(--color-orange); border-color: var(--color-border-heavy);">${categoryLabels[cat]}</h3>
        <div class="space-y-3">
          ${storiesInCat.map(story => {
            const p = story.primary_source || {};
            const pubDate = parseDate(p.published_at);
            const timeStr = pubDate ? pubDate.toLocaleString('en-IN', {
              hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short'
            }) : '';
            return `
              <div class="group flex items-center justify-between py-2.5 border-b border-[var(--color-border-heavy)] last:border-0 gap-4" style="border-color: var(--color-border-heavy);">
                <a href="${escapeHtml(p.url)}" target="_blank" rel="noopener noreferrer" class="headline-link text-sm font-normal text-[var(--color-black)] group-hover:text-[var(--color-orange)] transition-colors flex-grow">${escapeHtml(story.primary_headline)}</a>
                <div class="flex items-center gap-3 flex-shrink-0">
                  <span class="font-label-data text-[10px] text-[var(--color-dark-gray)] font-mono">${timeStr}</span>
                  <span class="source-badge">${escapeHtml(p.source_name)}</span>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;
  }

  articlesList.innerHTML = html;
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

  const plainHeaders = ["The Headline", "Today's Top Stories", "Category Breakdown", "Quick Hits"];
  const subcategoriesList = [
    "Business, Markets & Economy",
    "Technology & Innovation",
    "Geopolitics & World News",
    "Domestic Politics & Governance",
    "Science, Health & Environment",
    "Sports",
    "Culture, Entertainment & Arts",
    "Lifestyle & Society"
  ];

  for (let i = 0; i < lines.length; i++) {
    const raw     = lines[i];
    const trimmed = raw.trim();

    // ── Timestamp line ────────────────────────────────────────
    if (trimmed.startsWith('Live Briefing for:') || trimmed.startsWith('Briefing generated:')) {
      flushList();
      html += `<div class="briefing-timestamp">${escapeHtml(trimmed)}</div>`;

    // ── Plain Headers ─────────────────────────────────────────
    } else if (plainHeaders.includes(trimmed)) {
      flushList();
      html += `<h2>${escapeHtml(trimmed)}</h2>`;

    // ── Subcategories ─────────────────────────────────────────
    } else if (subcategoriesList.includes(trimmed)) {
      flushList();
      html += `<h3>${escapeHtml(trimmed)}</h3>`;

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

    // ── List item start: "- " or "* " ─────────────────────────
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
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
      // Check if it's a Top Story Title (the next non-empty line has "Why it matters:")
      let isTopStoryTitle = false;
      for (let j = i + 1; j < lines.length; j++) {
        const nextTrimmed = lines[j].trim();
        if (nextTrimmed === '') continue;
        if (nextTrimmed.includes('Why it matters:')) {
          isTopStoryTitle = true;
        }
        break;
      }

      flushList();
      if (isTopStoryTitle) {
        html += `<h4 class="font-bold text-lg mt-6" style="color: var(--color-orange);">${parseInline(escapeHtml(trimmed))}</h4>`;
      } else {
        html += `<p>${parseInline(escapeHtml(trimmed))}</p>`;
      }
    }
  }

  flushList();
  return html;
}

// ─── UTILITIES ────────────────────────────────────────────────
function toggleSublist(btn) {
  const list = btn.nextElementSibling;
  if (list) {
    list.classList.toggle('open');
    btn.classList.toggle('open');
    btn.textContent = btn.classList.contains('open') ? 'Other sources \u25BC' : 'Other sources \u25B6';
  }
}

function closeMobileSidebar() {
  const sidebar = document.getElementById('leftSidebar');
  const overlay = document.getElementById('mobileSidebarOverlay');
  if (sidebar) sidebar.classList.remove('mobile-open');
  if (overlay) overlay.classList.add('hidden');
}

function closeMobileRightSidebar() {
  const sidebar = document.getElementById('rightSidebar');
  const overlay = document.getElementById('mobileRightSidebarOverlay');
  if (sidebar) sidebar.classList.remove('mobile-open');
  if (overlay) overlay.classList.add('hidden');
}

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
    border: 3px solid ${c.border};
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.75rem 1.25rem;
    border-radius: 3px;
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
