# Design Spec: Hourly News Updates, "Latest" 1-Hour Feed & Web Push Notifications

- **Date**: 2026-09-09
- **Status**: Approved by User
- **Author**: Antigravity AI Pair Programmer

---

## 1. Overview & Objectives

Provide users with an immediate, real-time pulse of global news by:
1. Adding a dedicated **"Latest"** view in the web interface displaying all breaking articles from the **past 1 hour** across all monitored categories.
2. Generating detailed, analytical AI briefs (150–200 words) for each story in the 1-hour window.
3. Sending native **Web Push Notifications** to subscribers' phones and browsers every hour on the hour with the top headline and category summary.
4. Providing a toggle in the top header with a web icon to enable or disable hourly push alerts.

---

## 2. User Experience & Interface

### 2.1 "Latest" Sidebar Button
* **Placement**: Located in the left sidebar, placed directly **above the "Home" tab**.
* **Appearance**: Matches the existing industrial typography and button geometry:
  - Icon: Material Symbol `bolt` or `schedule` (no emojis).
  - Label: `LATEST`.
  - Active state: Highlighted with orange accent `var(--color-orange)` and background fill matching the theme.
* **Interaction**: Clicking switches the view to `#viewLatest`, marks the button active, and removes active highlights from Home and category buttons.

### 2.2 "Latest" Feed View (`#viewLatest`)
* **Content Scope**: Filtered to articles published within the last 60 minutes (`max_hours=1.0`) across all categories.
* **Card Structure**: Exactly matches the Homepage and Category cards:
  - Primary headline link with hover color transition.
  - Source badge (e.g., `Reuters`, `AP News`, `BBC`) + relative timestamp (e.g., `24m ago`).
  - Multi-sentence cohesive AI analytical brief (150–200 words in editorial prose).
  - Multi-source expandable cluster ("Also reported by ▶") if covered by multiple outlets.
* **Empty State**: If no new stories were published in the last 60 minutes, displays:
  *"No new breaking stories published in the past 60 minutes. Monitoring feeds continuously."*

### 2.3 Header Notification Control
* **Icon Button**: Placed in the top right header between the Theme toggle and the Refresh button:
  - HTML ID: `#notifToggleBtn`.
  - Icon ID: `#notifIcon` using Material Symbol `notifications` (when disabled) and `notifications_active` (when enabled in orange `var(--color-orange)`).
  - Title: *"Toggle Hourly Alerts"*.
* **Permission Flow**:
  - Tapping queries `Notification.requestPermission()`.
  - If granted, registers the Service Worker push subscription and syncs keys with `/api/subscribe`.
  - Shows an instant toast message: *"Hourly alerts enabled. You will receive updates every hour."*

---

## 3. Web Push Notification Architecture

### 3.1 Standards & Protocols
* **Web Push API + VAPID**: Uses standard RFC 8291 / 8292 open Web Push protocol via `pywebpush` on the backend.
* **Zero Third-Party Fees**: Free, native browser push supported across:
  - Android (Chrome, Edge, Firefox, Samsung Internet).
  - iOS (Safari 16.4+ via PWA / "Add to Home Screen").
  - Desktop (macOS, Windows, Linux Chrome/Safari/Edge/Firefox).

### 3.2 Service Worker (`sw.js`) & Manifest (`manifest.json`)
* **`manifest.json`**: Configures PWA name (*News Intel*), display mode (*standalone*), and icons for mobile installability.
* **`sw.js`**:
  - Listens for `'push'` event:
    ```javascript
    self.addEventListener('push', event => {
      const data = event.data ? event.data.json() : {};
      const title = data.title || 'News Intel · Past Hour Update';
      const options = {
        body: data.body || 'New breaking stories available.',
        icon: '/icons/icon-192.png',
        badge: '/icons/badge-72.png',
        data: { url: '/?tab=latest' }
      };
      event.waitUntil(self.registration.showNotification(title, options));
    });
    ```
  - Listens for `'notificationclick'` event: Wakes device, focuses or opens window to `/?tab=latest`.

### 3.3 Notification Payload Format
* **Title**: `News Intel · Past Hour Update`
* **Body**: Top story headline + category summary (e.g. `US military intercepts drone barrage in Red Sea (+ 11 more in Tech, Markets & World)`).

---

## 4. Backend & Scheduled Pipeline

### 4.1 Endpoints in `server.py`

1. **`POST /api/subscribe`**:
   - Body: `{ "subscription": { "endpoint": "...", "keys": { "p256dh": "...", "auth": "..." } } }`
   - Appends subscription to `data/subscriptions.json` (deduplicating by endpoint).
   - Returns `{ "success": true }`.

2. **`POST /api/unsubscribe`**:
   - Removes matching endpoint from `data/subscriptions.json`.
   - Returns `{ "success": true }`.

3. **`GET /api/latest-brief?category=1hour`**:
   - Reads `latest_1hour.json` (or falls back to `briefings_seed/latest_1hour.json`).
   - Returns `{ "id": "latest", "category": "1hour", "articlesCount": N, "stories": [...] }`.

4. **`POST /api/cron-hourly`**:
   - Secured with `Authorization: Bearer <CRON_SECRET>` or shared secret header.
   - **Pipeline**:
     1. Fetches all RSS feeds filtered to `max_hours=1.0`.
     2. Clusters articles into stories and generates detailed briefs via `gemini-3.5-flash-lite` (with multi-sentence structured fallback).
     3. Saves `latest_1hour.json` and updates `briefings_seed/latest_1hour.json`.
     4. Dispatches push notifications to all endpoints in `data/subscriptions.json`.

### 4.2 Hourly Automation Trigger

* **GitHub Actions Workflow (`.github/workflows/hourly-push.yml`)**:
  ```yaml
  name: Hourly News Intel Trigger
  on:
    schedule:
      - cron: '0 * * * *'
    workflow_dispatch:
  jobs:
    hourly-trigger:
      runs-on: ubuntu-latest
      steps:
        - name: Trigger Hourly Briefing & Web Push
          run: |
            curl -X POST "https://news-intel-lovat.vercel.app/api/cron-hourly" \
              -H "Authorization: Bearer ${{ secrets.CRON_SECRET }}" \
              --fail --max-time 120
  ```
* **Local Fallback**: In `server.py`, a background thread timer triggers the 1-hour pipeline if running as a standalone local server.

---

## 5. Verification & Testing Strategy

1. **Unit & API Testing**:
   - Test `POST /api/subscribe` and `POST /api/unsubscribe`.
   - Test `/api/latest-brief?category=1hour` returns valid JSON with ~200-word briefs.
   - Test manual invocation of `/api/cron-hourly`.
2. **UI & Navigation Verification**:
   - Verify "Latest" button renders above Home tab and navigates to `#viewLatest`.
   - Verify stories strictly match the past 1-hour window.
   - Verify notification bell toggles state between inactive and active with toast feedback.
3. **Notification Verification**:
   - Send test web push notification to a subscribed browser instance and verify lock-screen alert and direct click-through to `#viewLatest`.
