# CreatorOS — API Keys Setup Guide

This guide walks you through obtaining the API credentials needed to activate the
real (non-mock) integrations for **YouTube**, **Instagram**, and **PayPal** in
CreatorOS.

All three integrations already have real API paths wired into the backend —
they gracefully fall back to mock data when credentials are missing. Once you
paste the keys into `/app/backend/.env` and restart the backend, they go live
automatically. No code change needed.

---

## 1. YouTube Data API v3 🎥

**Cost:** Free — 10,000 units/day quota (channel + video fetch ≈ 5 units/call).
**Difficulty:** ⭐ Easy (5 minutes)
**What it unlocks:** Real channel subscriber count, view count, video list with
per-video stats (views, likes, comments) on the Portfolio + Asset detail
screens.

### Steps

1. Go to https://console.cloud.google.com/
2. Create a new project (or select an existing one). Any name works, e.g. `CreatorOS`.
3. In the left menu → **APIs & Services → Library**.
4. Search **"YouTube Data API v3"** → click it → **Enable**.
5. Left menu → **APIs & Services → Credentials**.
6. Click **+ Create Credentials → API key**.
7. Copy the key (starts with `AIza...`).
8. *(Optional but recommended)* Click **Restrict key** → under
   "API restrictions" select **Restrict key → YouTube Data API v3**.

### Paste into CreatorOS

Edit `/app/backend/.env` and set:
```
YOUTUBE_API_KEY=AIzaSyABC...yourkey...
```

Then restart the backend:
```
sudo supervisorctl restart backend
```

### Verify it works

In the Connections Hub, connect a YouTube handle (e.g. `@MrBeast`) — you should
see **real** subscriber counts and recent videos with actual view counts
instead of the deterministic mock numbers.

---

## 2. Instagram Graph API 📸

**Cost:** Free.
**Difficulty:** ⭐⭐⭐ Moderate (15–30 minutes; involves Meta app review flow)
**Important:** The Instagram Graph API **can only fetch data for the
Instagram Business/Creator account that owns the access token.** It cannot
look up arbitrary Instagram handles. This is a Meta policy limitation, not a
CreatorOS one.

**What it unlocks:** Real follower count, media list with likes/comments, and
profile info **for your own connected Instagram Business account**.

### Prerequisites

- An Instagram account that is set to **Business** or **Creator** (Personal
  accounts are not supported).
- A Facebook Page linked to that Instagram account.

### Steps

1. Go to https://developers.facebook.com/ → **My Apps → Create App**.
2. App type: choose **Business**.
3. In your app dashboard → **Add products → Instagram → Set up**.
4. Under **Instagram → API setup with Instagram login**, follow the
   **"Business login for Instagram"** flow. Meta will guide you through
   connecting your IG Business account and generating a **short-lived access
   token** with the `instagram_business_basic` scope.
5. Exchange the short-lived token for a **long-lived token** (60-day expiry) by
   calling this URL from your terminal (replace placeholders):
   ```
   curl -X GET "https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=YOUR_APP_SECRET&access_token=SHORT_LIVED_TOKEN"
   ```
6. Note the numeric **Instagram User ID** shown in the Meta dashboard for
   your business account.

### Paste into CreatorOS

Edit `/app/backend/.env` and set:
```
INSTAGRAM_API_VERSION=v25.0
INSTAGRAM_USER_ID=17841400000000000
INSTAGRAM_LONG_LIVED_TOKEN=IGQVJ...yourlonglivedtoken...
```

Then restart the backend:
```
sudo supervisorctl restart backend
```

### Token refresh reminder

Long-lived tokens last **60 days** and can be refreshed before expiry with:
```
curl -X GET "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=CURRENT_LONG_LIVED_TOKEN"
```
Set a calendar reminder for day 50 to refresh, or automate this.

---

## 3. PayPal Orders v2 (Sandbox first, then Live) 💳

**Cost:** Free for sandbox; standard transaction fees when live.
**Difficulty:** ⭐⭐ Easy-Moderate (10 minutes for sandbox)
**What it unlocks:** Real PayPal Checkout on the Pricing / upgrade page. Users
can complete a real $19 Pro-tier order (in test money for sandbox, real money
for live).

### Sandbox setup (recommended first)

1. Go to https://developer.paypal.com/dashboard/ → sign in with your PayPal
   account.
2. Left menu → **Apps & Credentials → Sandbox** tab.
3. Click **Create App**.
4. App type: **Merchant**. Name it e.g. `CreatorOS Sandbox`.
5. After creation you'll see:
   - **Client ID** (starts with `A...`, ~80 chars)
   - **Secret** (click "Show" to reveal, starts with `E...`)

### Paste into CreatorOS

Edit `/app/backend/.env` and set:
```
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=AeA1QIZ...yourclientid...
PAYPAL_CLIENT_SECRET=EGnHDx...yoursecret...
```

Then restart the backend:
```
sudo supervisorctl restart backend
```

### Test with sandbox buyer accounts

PayPal auto-creates sandbox buyer/personal accounts under
**Dashboard → Sandbox → Accounts**. Use the "Personal" account email +
password to complete a test checkout — no real money changes hands.

### Going live

1. In PayPal Dashboard, switch to the **Live** tab (top-right).
2. Repeat the "Create App" step there → get **live** Client ID + Secret.
3. Update `/app/backend/.env`:
   ```
   PAYPAL_MODE=live
   PAYPAL_CLIENT_ID=<live client id>
   PAYPAL_CLIENT_SECRET=<live secret>
   ```
4. Also set `DEMO_MODE=false` to disable the mock upgrade shortcut and force
   all upgrades to go through PayPal (or Stripe).
5. Restart backend.

⚠️ **Never commit these secrets to a public repo.** Note: `/app/.gitignore`
no longer excludes `.env` files (this exclusion was removed so production
deploys correctly receive required env vars like `EMERGENT_LLM_KEY`). If you
push this repo to GitHub, treat your repo as containing live secrets and use
a **private** repository.

---

## Quick Reference — Where to paste

| Integration | Env vars to set | File |
|---|---|---|
| YouTube | `YOUTUBE_API_KEY` | `/app/backend/.env` |
| Instagram | `INSTAGRAM_USER_ID`, `INSTAGRAM_LONG_LIVED_TOKEN`, `INSTAGRAM_API_VERSION` (default `v25.0`) | `/app/backend/.env` |
| PayPal | `PAYPAL_MODE` (`sandbox` or `live`), `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | `/app/backend/.env` |

After any change:
```
sudo supervisorctl restart backend
```

That's it — the integrations auto-detect the presence of keys and switch
from mock to live at boot.

---

## Verifying live vs. mock

Each API response includes a `"mocked": true|false` field. If you see
`"mocked": false`, you're hitting the real provider. If you see
`"mocked": true`, either the key is missing or the provider returned an
error and the fallback kicked in — check `/var/log/supervisor/backend.err.*`
for details in the latter case.
