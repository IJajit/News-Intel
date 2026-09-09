# Hourly News Updates, "Latest" 1-Hour Feed & Web Push Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide automated hourly news intelligence across all categories via a dedicated "Latest" 1-hour view in the web app and native Web Push Notifications dispatched hourly to users' devices.

**Architecture:** 
- In `server.py`, add 1-hour filtering pipeline (`max_hours=1.0`) across all RSS sources to compile `latest_1hour.json` with multi-sentence editorial briefs.
- Implement standard RFC 8291/8292 Web Push with VAPID key pairs via `pywebpush`, exposing `/api/vapid-public-key`, `/api/subscribe`, `/api/unsubscribe`, and `/api/cron-hourly`.
- Add PWA `manifest.json` and Service Worker `sw.js` with 'push' and 'notificationclick' listeners routing directly to `/?tab=latest`.
- In `index.html` and `script.js`, position the **"Latest"** button directly **above the "Home" tab** in the left sidebar, add `#notifToggleBtn` with Material Symbols web icon (`notifications` / `notifications_active`), and set up GitHub Actions hourly cron workflow (`.github/workflows/hourly-push.yml`).

**Tech Stack:** Python 3 (stdlib, `pywebpush`, `py-vapid`, `urllib`), Vanilla JavaScript (ES6+, Service Worker API, Push API), HTML5, Tailwind CSS / Custom CSS, GitHub Actions.

## Global Constraints
- **Web Icon Only:** Must use Google Material Symbols web icon (`notifications`, `notifications_active`, `schedule`) for all navigation and notifications; NO emojis or pictorial symbols.
- **Button Placement:** The "Latest" button must be positioned strictly **above the "Home" tab** in the left sidebar navigation.
- **Strict 1-Hour Window:** "Latest" tab stories must strictly represent articles published in the last 60 minutes (`max_hours=1.0`) across all categories, paired with 150–200 word editorial briefs.
- **Zero Third-Party Paid Services:** Pure native Web Push protocol (RFC 8291 / 8292); no Firebase, Pusher, or OneSignal subscriptions.
- **Resilience:** Gracefully handle subscription expiration (HTTP 410 Gone / 404 Not Found), offline state, and empty 1-hour news windows.

---

### Task 1: 1-Hour Feed Pipeline & Seed Generation (`server.py`)

**Files:**
- Modify: `c:/AntiGravity/News App/server.py`
- Modify: `c:/AntiGravity/News App/requirements.txt`
- Create: `c:/AntiGravity/News App/briefings_seed/latest_1hour.json`
- Create: `c:/AntiGravity/News App/tests/test_hourly_pipeline.py`

**Interfaces:**
- Produces: `generate_hourly_brief(grounded_time=None) -> dict` in `server.py`
- Produces: `GET /api/latest-brief?category=1hour` returning `{ "id": "latest", "category": "1hour", "articlesCount": N, "stories": [...] }`
- Produces: `briefings_seed/latest_1hour.json` for immediate deployment and cold-start seeding

- [ ] **Step 1: Write unit test for 1-hour feed generation and time-filtering**

Create `tests/test_hourly_pipeline.py`:
```python
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server import filter_articles_by_hours

class TestHourlyPipeline(unittest.TestCase):
    def test_filter_articles_within_one_hour(self):
        now = datetime.now(timezone.utc)
        articles = [
            {"title": "Breaking 20m ago", "published_at": (now - timedelta(minutes=20)).isoformat()},
            {"title": "Breaking 55m ago", "published_at": (now - timedelta(minutes=55)).isoformat()},
            {"title": "Old 75m ago", "published_at": (now - timedelta(minutes=75)).isoformat()},
            {"title": "Yesterday news", "published_at": (now - timedelta(hours=24)).isoformat()},
        ]
        filtered = filter_articles_by_hours(articles, max_hours=1.0, current_time=now)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["title"], "Breaking 20m ago")
        self.assertEqual(filtered[1]["title"], "Breaking 55m ago")

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_hourly_pipeline.py`
Expected: FAIL with `ImportError: cannot import name 'filter_articles_by_hours'`

- [ ] **Step 3: Implement `filter_articles_by_hours` and 1-hour briefing logic in `server.py`**

In `server.py`:
1. Implement `filter_articles_by_hours(articles, max_hours=1.0, current_time=None)`
2. In `seed_briefs()`: add `"1hour"` to the category list copied from `SEED_DIR` to `BRIEFINGS_DIR`.
3. In `do_GET()`: handle `category == '1hour'` and ensure no 20-story cap for `1hour`.
4. Create initial seed file `briefings_seed/latest_1hour.json`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_hourly_pipeline.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server.py briefings_seed/latest_1hour.json tests/test_hourly_pipeline.py
git commit -m "feat: add 1-hour feed filtering and latest_1hour endpoint"
```

---

### Task 2: "Latest" Navigation Tab & Feed UI View (`index.html`, `script.js`)

**Files:**
- Modify: `c:/AntiGravity/News App/index.html`
- Modify: `c:/AntiGravity/News App/script.js`
- Create: `c:/AntiGravity/News App/tests/test_latest_ui.py`

**Interfaces:**
- Consumes: `GET /api/latest-brief?category=1hour`
- Produces: `#tabLatestBtn` in `#readerSubtabs` placed directly above `#tabHomepageBtn`
- Produces: `#viewLatest` panel with `#latestContent`
- Produces: `renderLatestView(brief)` and tab routing supporting `/?tab=latest`

- [ ] **Step 1: Write test for "Latest" DOM element hierarchy in `index.html`**

Create `tests/test_latest_ui.py`:
```python
import os
import unittest
import re

class TestLatestUI(unittest.TestCase):
    def test_latest_button_is_before_home_button(self):
        html_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        latest_match = re.search(r'id=["\']tabLatestBtn["\']', content)
        home_match = re.search(r'id=["\']tabHomepageBtn["\']', content)

        self.assertIsNotNone(latest_match, "tabLatestBtn not found in index.html")
        self.assertIsNotNone(home_match, "tabHomepageBtn not found in index.html")
        self.assertLess(latest_match.start(), home_match.start(), "tabLatestBtn MUST be placed before tabHomepageBtn")

    def test_view_latest_container_exists(self):
        html_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('id="viewLatest"', content)
        self.assertIn('id="latestContent"', content)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_latest_ui.py`
Expected: FAIL with `tabLatestBtn not found in index.html`

- [ ] **Step 3: Update `index.html` and `script.js`**

1. In `index.html`: add `#tabLatestBtn` above `#tabHomepageBtn` and add `#viewLatest`.
2. In `script.js`: bind elements, update `switchTab('latest')`, implement `loadLatest1Hour()` and `renderLatestView(brief)`, and handle URL parameter `?tab=latest`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_latest_ui.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add index.html script.js tests/test_latest_ui.py
git commit -m "feat: add Latest tab button above Home with dedicated 1-hour view"
```

---

### Task 3: VAPID Key Management & Push Subscription Endpoints (`server.py`)

**Files:**
- Modify: `c:/AntiGravity/News App/server.py`
- Modify: `c:/AntiGravity/News App/requirements.txt`
- Create: `c:/AntiGravity/News App/tests/test_push_api.py`

**Interfaces:**
- Produces: `get_or_create_vapid_keys() -> (public_key_b64, private_key_pem)`
- Produces: `GET /api/vapid-public-key` -> `{ "publicKey": "..." }`
- Produces: `POST /api/subscribe` -> `{ "success": true }`
- Produces: `POST /api/unsubscribe` -> `{ "success": true }`

- [ ] **Step 1: Write test for VAPID key generation and subscription persistence**

Create `tests/test_push_api.py`:
```python
import os
import sys
import unittest
import json
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server import get_or_create_vapid_keys, save_subscription, remove_subscription, load_subscriptions

class TestPushAPI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.subs_file = os.path.join(self.tmp_dir.name, 'subscriptions.json')

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_vapid_key_format(self):
        pub_key, priv_pem = get_or_create_vapid_keys()
        self.assertIsInstance(pub_key, str)
        self.assertGreater(len(pub_key), 60)
        self.assertIn("BEGIN PRIVATE KEY", priv_pem)

    def test_subscription_lifecycle(self):
        sub_sample = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/sample-token-123",
            "keys": {
                "p256dh": "mock-p256dh",
                "auth": "mock-auth"
            }
        }
        save_subscription(sub_sample, filepath=self.subs_file)
        subs = load_subscriptions(filepath=self.subs_file)
        self.assertEqual(len(subs), 1)

        save_subscription(sub_sample, filepath=self.subs_file)
        subs = load_subscriptions(filepath=self.subs_file)
        self.assertEqual(len(subs), 1)

        remove_subscription(sub_sample["endpoint"], filepath=self.subs_file)
        subs = load_subscriptions(filepath=self.subs_file)
        self.assertEqual(len(subs), 0)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_push_api.py`
Expected: FAIL with `ImportError: cannot import name 'get_or_create_vapid_keys'`

- [ ] **Step 3: Implement VAPID key and subscription endpoints in `server.py`**

In `server.py`:
1. Add `pywebpush` and `py-vapid` imports.
2. Implement `get_or_create_vapid_keys()`, `load_subscriptions()`, `save_subscription()`, `remove_subscription()`.
3. Add `GET /api/vapid-public-key`, `POST /api/subscribe`, `POST /api/unsubscribe`.
4. Add `pywebpush==2.5.0` and `py-vapid==1.9.4` to `requirements.txt`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_push_api.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server.py requirements.txt tests/test_push_api.py
git commit -m "feat: add VAPID key management and push subscription endpoints"
```

---

### Task 4: Web App Manifest, Service Worker (`sw.js`) & Header Notification Toggle

**Files:**
- Create: `c:/AntiGravity/News App/manifest.json`
- Create: `c:/AntiGravity/News App/sw.js`
- Modify: `c:/AntiGravity/News App/index.html`
- Modify: `c:/AntiGravity/News App/script.js`
- Create: `c:/AntiGravity/News App/tests/test_pwa_assets.py`

**Interfaces:**
- Produces: `manifest.json` (PWA spec)
- Produces: `sw.js` with 'push' and 'notificationclick' listeners
- Produces: `#notifToggleBtn` with Material Symbol `notifications` in header
- Produces: Client subscription sync with `/api/subscribe` and toast feedback

- [ ] **Step 1: Write test for manifest JSON validity and Service Worker registration**

Create `tests/test_pwa_assets.py`:
```python
import os
import unittest
import json

class TestPwaAssets(unittest.TestCase):
    def test_manifest_is_valid_json(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'manifest.json')
        self.assertTrue(os.path.exists(path), "manifest.json does not exist")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data.get("name"), "News Intel")
        self.assertEqual(data.get("display"), "standalone")

    def test_service_worker_has_push_and_click_listeners(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'sw.js')
        self.assertTrue(os.path.exists(path), "sw.js does not exist")
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("addEventListener('push'", content)
        self.assertIn("addEventListener('notificationclick'", content)
        self.assertIn("tab=latest", content)

    def test_header_has_notification_web_icon(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('id="notifToggleBtn"', content)
        self.assertIn('id="notifIcon"', content)
        self.assertIn('notifications', content)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_pwa_assets.py`
Expected: FAIL with `manifest.json does not exist`

- [ ] **Step 3: Create `manifest.json`, `sw.js`, and add header toggle button**

1. Create `manifest.json` with PWA icons, name, display standalone, and start URL `/?tab=latest`.
2. Create `sw.js` with `push` and `notificationclick` listeners.
3. Link `manifest.json` and add `#notifToggleBtn` with Material Symbol `notifications` in `index.html`.
4. In `script.js`: register `/sw.js`, check subscription status, and implement click toggle with toast notification.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_pwa_assets.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manifest.json sw.js index.html script.js tests/test_pwa_assets.py
git commit -m "feat: add PWA manifest, service worker and header notification toggle"
```

---

### Task 5: Hourly Cron Pipeline, Dispatcher & GitHub Actions (`server.py`, `.github/workflows/hourly-push.yml`)

**Files:**
- Modify: `c:/AntiGravity/News App/server.py`
- Create: `c:/AntiGravity/News App/.github/workflows/hourly-push.yml`
- Create: `c:/AntiGravity/News App/tests/test_cron_hourly.py`

**Interfaces:**
- Produces: `format_hourly_push_payload(stories) -> dict` in `server.py`
- Produces: `POST /api/cron-hourly` endpoint in `server.py`
- Produces: `.github/workflows/hourly-push.yml` scheduled at `cron: '0 * * * *'`

- [ ] **Step 1: Write test for hourly cron briefing and notification payload format**

Create `tests/test_cron_hourly.py`:
```python
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server import format_hourly_push_payload

class TestCronHourly(unittest.TestCase):
    def test_format_push_payload_with_stories(self):
        stories = [
            {"primary_headline": "Global Leaders Agree on Climate Framework", "category": "geopolitics"},
            {"primary_headline": "New Battery Tech Doubles Electric Vehicle Range", "category": "technology"},
            {"primary_headline": "Central Banks Announce Joint Currency Stability Plan", "category": "finance"}
        ]
        payload = format_hourly_push_payload(stories)
        self.assertIn("News Intel · Past Hour Update", payload["title"])
        self.assertIn("Global Leaders Agree on Climate Framework", payload["body"])
        self.assertIn("+ 2 more in", payload["body"])
        self.assertEqual(payload["url"], "/?tab=latest")

    def test_format_push_payload_empty_stories(self):
        payload = format_hourly_push_payload([])
        self.assertIn("News Intel · Hourly Update", payload["title"])
        self.assertIn("No breaking stories", payload["body"])

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_cron_hourly.py`
Expected: FAIL with `ImportError: cannot import name 'format_hourly_push_payload'`

- [ ] **Step 3: Implement `format_hourly_push_payload`, push dispatcher, and cron endpoint in `server.py`**

In `server.py`:
1. Implement `format_hourly_push_payload(stories)`.
2. Implement `send_web_push_notification(subscription, payload_data)` using `pywebpush`.
3. Implement `run_hourly_pipeline()` executing 1-hour feed compilation and dispatching push alerts.
4. Implement `POST /api/cron-hourly` in `do_POST()`.
5. Create `.github/workflows/hourly-push.yml`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_cron_hourly.py`
Expected: PASS

- [ ] **Step 5: Run all test suites together**

Run: `python -m unittest discover tests/ -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add server.py .github/workflows/hourly-push.yml tests/test_cron_hourly.py
git commit -m "feat: implement hourly cron pipeline, push notification dispatcher and GitHub Actions workflow"
```
