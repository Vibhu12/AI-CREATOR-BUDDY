# CreatorOS — End-to-End User Journey & Edge-Case Matrix

Version 1.0 · June 2026 · Companion to `01_HLD.md` and `02_LLD.md`

This document walks through **every screen and every interaction** for the
primary persona *"Maya"* and documents the edge cases handled at each step.
The reader should be able to trace what happens client-side, server-side,
and in the database for any user action.

---

## Persona: Maya Nakamura

- **27, based in Berlin**. Full-time creator since 2024.
- Runs:
  - `@mayabuilds` YouTube (148k subs, $4.1k/mo AdSense)
  - `@maya.builds` Instagram (72k followers)
  - **Ship It cohort** — quarterly cohort-based course ($997)
  - **Ship List** newsletter (18k subs, $6.4k/mo sponsors)
  - **NotionKit** template shop
- Frustrations: Six tabs open at all times. Never sure "is this month
  actually profitable?" Wants to feel like a CEO, not a bookkeeper.

---

## Journey Map

```
┌──────────┐   ┌──────────────┐   ┌───────────┐   ┌──────────────┐
│  Login   │──▶│  Onboarding  │──▶│ Dashboard │──▶│   Anywhere    │
│ (Google) │   │  3 steps     │   │ (auto-    │   │  Portfolio,   │
│          │   │              │   │  seeded)  │   │  Coach,       │
└──────────┘   └──────────────┘   └───────────┘   │  Finance,     │
                                                    │  Strategy,    │
                                                    │  Integrations,│
                                                    │  Goals, etc.  │
                                                    └──────────────┘
```

---

## 1. First-Launch → Login

### Happy path
1. User opens the app → sees the landing screen (`login.tsx`) with the
   CreatorOS mark + tagline: *"The business OS for creators."*
2. Taps **Continue with Google** (testID `login-google-btn`).
3. `AuthContext.signIn()` calls `WebBrowser.openAuthSessionAsync(
   loginUrl, deepLinkReturnUrl)` — hosted Google Auth screen appears.
4. User picks a Google account → consent → Emergent redirects back with
   `creatoros://auth/callback?session_id=<opaque_token>`.
5. `parseSessionId(url)` extracts the token → stored in `SecureStore`.
6. `GET /api/auth/me` hydrates `user` state.
7. Because `user.onboarding_complete = false`, router pushes `/onboarding`.

### Edge cases
| Case                                     | Behavior                                                     |
|------------------------------------------|--------------------------------------------------------------|
| User dismisses the browser sheet         | `WebBrowser.type === 'dismiss'` → back on login, no state change |
| Browser closes without callback          | Silent no-op — user still on login screen                    |
| Malformed callback URL                   | `parseSessionId` returns null → error toast "Login failed"   |
| Stale token in SecureStore               | `/auth/me` returns 401 → context clears token, back to login |
| Multiple accounts on device              | Standard Google account picker — no special handling         |
| Airplane mode                            | `fetch` throws → surfaces "Check your connection"            |
| Session already exists                   | Skip login flow, go directly to dashboard                    |

---

## 2. Onboarding (3 steps)

### Flow
```
Step 1 — Handles          Step 2 — Primary Goal        Step 3 — Tier
YouTube handle input   →  What is your #1 goal?   →   Free / Pro / Studio
Instagram handle input     (revenue, subs, launch)    (defaults to Free)
```

On completion:
- `PATCH /api/users/me` sets `onboarding_complete=true`, `youtube_handle`,
  `instagram_handle`, `primary_goal`.
- Redirect to `/(tabs)/index` (Dashboard).

### Edge cases
| Case                                | Behavior                                                            |
|-------------------------------------|---------------------------------------------------------------------|
| Blank YouTube handle                | Optional — user can proceed without it                              |
| Handle contains "@"                 | Stripped server-side before storage                                 |
| User backgrounds mid-onboarding     | Local state preserved (React state) — must complete in one session  |
| User dies on step 3                 | On next login, `onboarding_complete=false` → resumes at step 3      |
| Free-tier picked                    | No payment prompt shown; user lands on Dashboard normally           |
| Pro-tier picked at onboarding       | Deep-links to `/pricing` after step 3                               |

---

## 3. Dashboard (first entry)

### Auto-seed trigger
On the very first `GET /api/dashboard` for a user:
1. `_ensure_seeded(uid)` runs. Idempotent — sets `db.users.seeded_at`.
2. Inserts ~8 assets, 4 goals, ~12 content items, 5 recommendations, 3
   notifications — all scoped to `user_id`. Numbers are deterministic per
   user based on `_hash_seed(uid)`.
3. Returns the composed dashboard.

Result: Maya sees a **living, believable OS** on first launch — no empty
states. Every subsequent request skips the seed check via early-return.

### Dashboard sections (top → bottom)
1. **Hero** — Revenue MTD, delta vs last 30d, Health score (0–100)
2. **KPI strip** — 4 tiles: MTD Revenue, MTD Profit, Margin, Runway (mo)
3. **Radar** — user's percentile vs Top 1% on 6 axes (revenue, followers,
   consistency, engagement, monetization, growth). Tap → `/competitors`.
4. **Top 3 recommendations** — priority-sorted from `recommendations`
   collection. Each has expected ROI, effort, and a CTA.
5. **Notifications bell** (top-right) → in-app sheet.
6. **Pull-to-refresh** — re-fetches dashboard.

### Edge cases
| Case                                       | Behavior                                                   |
|--------------------------------------------|------------------------------------------------------------|
| Seed race (two dashboard hits in parallel) | `_ensure_seeded` uses `$setOnInsert` — only one wins       |
| User has 0 assets somehow                  | Hero shows $0 with helper: "Add your first asset →"        |
| Radar has one axis at 0                    | Draws truncated polygon without crashing                   |
| Session expired mid-fetch                  | 401 → AuthContext clears token → route back to login       |
| Backend timeout                            | Retry banner at the top; last cached data still visible    |

---

## 4. Portfolio → Per-Asset Detail

### Portfolio (`/(tabs)/portfolio.tsx`)
- Renders `assets[]` as sparkline-decorated rows.
- Top summary strip: total revenue MTD, portfolio AI score (avg), asset count.
- Floating "+" button → `AddAssetModal`.
- Tap a row → `router.push('/asset/<id>')`.

### AddAssetModal edge cases (validation UX overhauled in iter_14)
| Field         | Validation                                          | Error text                        |
|---------------|-----------------------------------------------------|-----------------------------------|
| name          | required, 2–80 chars                                | "Name is required" / "At least 2 characters" |
| revenue_mtd   | optional; if given, ≥0 and ≤10,000,000              | "Enter a positive number"         |
| followers     | optional; if given, ≥0 and ≤1,000,000,000           | "Value too large"                 |
| Submit btn    | disabled while any error present or `busy=true`     |                                   |
| Server error  | Banner: "Failed to create — try again"              |                                   |

Numeric fields strip non-numeric characters on input so "-" / "e" can never
enter state.

### Asset detail (`/asset/[id]`)
Fetches `GET /api/assets/{id}`:
```json
{
  "asset": { ... },
  "content": [{...} × 20],
  "recommendations": [{...} × ≤4],
  "benchmarks": {
    "top_1pct_followers": 473600,   // 3.2× user's followers
    "top_1pct_revenue":   114080,   // 4.6× user's MTD
    "median_engagement":  4.8,
    "your_engagement":    6.4
  },
  "kpis": [
    {"label":"AI Score","value":88,"unit":"/100"},
    {"label":"Revenue MTD","value":24800,"unit":"$"},
    {"label":"Profit margin","value":75,"unit":"%"},
    {"label":"Audience","value":4200,"unit":"reach"}
  ]
}
```

UI sections:
1. Hero — platform emoji + AI score ring + trend area chart + category
2. KPI grid — 4 cells
3. Top-1% benchmark card — dual bars + "gap to close" split block
4. Scoped recommendations (filtered by platform in title/summary)
5. Recent content list — top 6 with virality score

### Edge cases
| Case                                             | Behavior                                     |
|--------------------------------------------------|----------------------------------------------|
| Asset id doesn't belong to user                  | 404 → error screen "Could not load this asset." + back button |
| Deleted mid-view                                 | Same 404 path                                |
| No recent content for platform                   | Section hidden, EmptyState shown at bottom   |
| No recommendations                               | Section hidden                               |
| Followers = 0                                    | Gap block shows "0" instead of NaN            |

---

## 5. AI Coach (streaming)

### Flow (`/(tabs)/coach.tsx`)
1. User types → tap Send.
2. Client calls `POST /api/ai/chat` and consumes the SSE stream via
   `response.body.getReader()`.
3. Each `data: {"delta":"..."}` chunk appends to `currentDelta` state and
   re-renders the streaming bubble.
4. On stream close, the bubble commits to `messages[]` as an assistant
   message.

### Quota & validation
| Check                                          | HTTP  | Client UX                                     |
|------------------------------------------------|-------|-----------------------------------------------|
| Empty message                                  | 400   | Send button disabled while `input.trim()==='' ` |
| Message > 4000 chars                           | 413   | Client cuts input at 4000 with warning       |
| Free tier: 11th user-role msg in 24h           | 402   | Banner: "Free tier: 10 msgs/day. Upgrade →"   |
| Burst: 31st msg in 60s                         | 429   | Toast: "Slow down — try again in Xs"          |
| No `EMERGENT_LLM_KEY`                          | 500   | Toast: "AI temporarily unavailable"           |

### Edge cases
| Case                                          | Behavior                                                |
|-----------------------------------------------|---------------------------------------------------------|
| User pulls up new conversation                | `session_id = "coach-<uuid>"` — new context (persisted) |
| App backgrounded mid-stream                   | Stream aborts. On resume, `chat_history` re-hydrates    |
| Network drops mid-stream                      | Partial delta shown with "Response cut off — retry"     |
| Backend `except Exception`                    | `data: {"error":"AI stream failed. Please retry."}` — no internal text leaked |
| User has 200 msgs in history                  | Only last 50 hydrated in view; API returns full history on demand |

---

## 6. Strategy Planner

### Flow (`/strategy.tsx`)
1. Picks horizon: **30 / 60 / 90** days.
2. Optional focus text (e.g. "Launch NotionKit v2 by August").
3. `POST /api/strategy/plans` — streams Claude Sonnet 4.5 output, parses JSON
   at end, persists.
4. Renders phases (usually 3–5) with checkbox tasks. Toggling a checkbox
   calls `PATCH /strategy/{plan_id}/task` which recomputes `progress_pct`.

### Edge cases
| Case                              | Behavior                                                        |
|-----------------------------------|-----------------------------------------------------------------|
| horizon not in {30,60,90}         | 400                                                             |
| Focus text >500 chars             | 413                                                             |
| Free tier: 2nd plan in a week     | 402 → "Free tier: 1 plan/week. Upgrade →"                      |
| Burst: 6th plan in an hour        | 429                                                             |
| Claude returns malformed JSON     | Fallback: raw markdown shown; task toggling disabled            |
| User completes all tasks          | `progress_pct=100`, confetti animation, badge on Dashboard      |

---

## 7. Connections Hub

### Flow (`/integrations`)
Shows 4 provider cards. Each has a Connect button until connected, then
shows summary metrics + "View data" + Disconnect.

### Connect flow (OAuth simulation)
```
Tap "Connect X" → modal opens
  ├─ Input handle (yt/ig) or email (stripe/paypal)
  ├─ Show permission list (read-only)
  ├─ Submit → phase='redirect' (500ms fake) → phase='authorizing' (backend call)
  ├─ Backend upserts db.connections + returns summary
  ├─ phase='success' with checkmark animation
  └─ Modal auto-closes after 900ms; list refetches
```

### Edge cases
| Case                                            | Behavior                                                       |
|-------------------------------------------------|----------------------------------------------------------------|
| Empty handle                                    | Inline error "Please enter your YouTube handle"                |
| Stripe/PayPal: not a valid email               | Inline error "Please enter a valid email"                      |
| Backend 502 during connect                      | Modal returns to input phase with error toast                  |
| Handle already connected (reconnect)            | `upsert` updates in-place; summary refreshed                   |
| Long-press disconnect while offline             | Alert stays open; retry once online                            |
| Real API key present but call fails             | Falls back to deterministic mock, `mocked: true` in payload    |

### Detail sheet
Full stats + recent items (videos/reels/charges/transactions). Refetches
the appropriate endpoint on open. Uses `mode: 'test' | 'live'` badge for
Stripe/PayPal.

---

## 8. Pricing → Checkout

### Flow (`/pricing.tsx`)
1. Tier cards render from `GET /api/billing/plans`. Current tier is disabled.
2. Tap **Upgrade to Pro** → `CheckoutModal` opens in `phase='method'`.
3. Pick Stripe (default) or PayPal. If PayPal keys are set the option shows
   a **LIVE** badge in green.
4. Tap **Pay $X securely**:
   - **Stripe path (mock)**: `POST /billing/checkout` → wait 1.4s →
     `POST /billing/checkout/confirm` → tier flips.
   - **PayPal path (mock)**: `POST /paypal/create-order` (approval_url:null)
     → simulated processing → `POST /paypal/capture` → tier flips.
   - **PayPal path (live)**: `POST /paypal/create-order` returns real
     `approval_url` → `WebBrowser.openAuthSessionAsync(approval_url, return_url)`
     → user approves at PayPal → app receives `return_url?token=<order_id>`
     → `POST /paypal/capture` → real PayPal capture → tier flips.
5. Success phase: green check + "You're on Pro!" auto-close.

### Edge cases matrix

| Case                                            | HTTP | Client UX                              |
|-------------------------------------------------|------|----------------------------------------|
| Trying to checkout Free tier                    | 400  | Tier button disabled — never reached   |
| Invalid `return_url` (open-redirect attempt)    | 400  | Toast: "Invalid checkout URL"          |
| PayPal user cancels in browser                  | —    | Modal switches to error state with Retry/Cancel |
| PayPal capture fails (already captured)         | 502  | "PayPal capture failed — order not approved or already captured" |
| DEMO_MODE=false + mock capture attempted        | 402  | "Payment required — configure real keys" |
| DEMO_MODE=false + /billing/upgrade              | 410  | Never called from client               |
| Double-tap Pay button                           | —    | Ignored — modal is `busy` while phase in {creating,processing} |
| Backend restart mid-processing                  | 5xx  | Client retries once; else error state  |
| Real Stripe webhook not implemented             | —    | Tier will not flip in prod until webhook is wired |

---

## 9. Goal Tracking

### Flow (`/goals.tsx`)
1. Summary card: Active / Completed / Avg progress %.
2. Goal cards with progress bars. Tap → edit. Long-press → delete confirm.
3. "+" button → add modal with type chips (revenue, subscribers, followers,
   launch, content).
4. Deadline is optional; if given, must be `YYYY-MM-DD`.

### Backend validation
| Field   | Rule                                | Error                                                |
|---------|-------------------------------------|------------------------------------------------------|
| title   | required, non-empty, ≤120 chars     | 400 "Title cannot be empty" / 413 "Title too long"   |
| target  | > 0                                 | 400 "target must be positive"                        |
| current | ≥ 0                                 | 400 "current cannot be negative"                     |
| ownership | must match user_id                | 404 "Goal not found"                                 |

### Edge cases
| Case                                     | Behavior                                                |
|------------------------------------------|---------------------------------------------------------|
| Delete goal not owned by user            | 404 (silent; UI still refetches list)                   |
| Deadline in past                         | UI shows red "Xd overdue"                              |
| current > target                         | Progress bar caps at 100%, goal marked "Complete"       |
| Delete during another user's request     | Cross-user isolation → 404, no data loss                |
| 200+ goals                               | List is a `ScrollView` (no virtualization) — acceptable for typical usage <50 |

---

## 10. Global Edge-Case Matrix

| Category                | Case                                            | Handling                                                 |
|-------------------------|-------------------------------------------------|----------------------------------------------------------|
| **Auth**                | Session expired                                 | 401 → AuthContext clears token → route to `/login`       |
|                         | Session token tampered                          | 401                                                      |
|                         | Token stored on stolen device                   | Mongo TTL expires it; user can also `POST /auth/logout` remotely (future)|
| **Data**                | Cross-user read/write                           | Filter by user_id → 404 (never 403; don't leak existence)|
|                         | Deleted asset referenced by strategy plan       | Plan renders; nav to asset detail 404s → "Not found"     |
| **Payments**            | Duplicate PayPal capture                        | Backend detects `status=='complete'` → returns `already_complete: true` |
|                         | Stripe/PayPal webhook missing (prod)            | Tier stays free; user contacts support                   |
|                         | Amount tampering (client sends different amount)| Backend ignores; pricing derived server-side from TIERS  |
| **Network**             | Offline                                         | fetch throws; UI shows "Check your connection"           |
|                         | Slow 3G                                         | Skeletons on Dashboard/Portfolio; ActivityIndicator elsewhere |
| **LLM**                 | Rate limit from provider                        | 429 → user-facing toast; retry after backoff             |
|                         | Long response                                    | Streamed progressively; no timeout on client            |
|                         | User navigates away mid-stream                  | Stream aborts on unmount; partial message discarded      |
| **Permissions (native)**| No permissions used yet — no camera/mic/location required for MVP | N/A                                     |
| **Backgrounding**       | iOS suspends network                            | On resume, `AppState` listener refetches dashboard       |
| **Push notifications**  | Not implemented                                 | Design uses in-app notifications only (`/notifications`) |
| **Deep links**          | Malformed callback                              | Silent ignore                                            |
| **Currency/locale**     | Non-USD users                                   | All numbers formatted as USD (MVP); i18n on backlog      |
| **Time zones**          | User in JST vs server UTC                       | All timestamps stored & compared in UTC; client formats to local |

---

## 11. Instrumentation Hooks Expected

Every screen transition and every server action should emit an analytics
event. See `04_METRICS_AND_AB.md` for the taxonomy.

Recommended event names (not yet fully wired):
- `onboarding_step_complete{step:int}`
- `dashboard_loaded{seeded:bool, ms:int}`
- `ai_chat_message_sent{tier:str, len:int}`
- `ai_chat_stream_error{code:str}`
- `strategy_plan_generated{horizon:int, ms:int, tier:str}`
- `connect_provider_attempted{provider:str}`
- `connect_provider_succeeded{provider:str}`
- `checkout_started{tier, provider}`
- `checkout_completed{tier, provider, real:bool}`
- `checkout_failed{tier, provider, reason:str}`
- `goal_created{kind}` / `goal_completed{kind, days_to_close}`
- `rate_limit_hit{kind:str, tier:str}`
