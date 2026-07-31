# CreatorOS — High-Level Design (HLD)

Version 1.0 · June 2026 · Owner: Engineering

---

## 1. Product & System Overview

**CreatorOS** is a mobile-first business operating system for digital creators
and entrepreneurs. It replaces the collection of spreadsheets, Notion pages,
and Stripe dashboards a solo creator normally cobbles together with a single
opinionated app that:

- Ingests portfolio data (YouTube, Instagram, courses, newsletters, SaaS)
- Computes a unified financial P&L and 90-day forecast
- Scores every asset with an AI health score
- Benchmarks the user against the "Top 1%" peer set
- Generates 30/60/90-day strategy plans via Claude Sonnet 4.5
- Runs an always-on AI Coach for advisory-grade Q&A
- Handles subscription billing (Stripe + PayPal) with real payment rails

The primary user is *"Maya"* — a 27-year-old creator earning $18k–$60k/mo
across 4–6 revenue streams who wants to feel like a CEO, not a bookkeeper.

---

## 2. Architecture at a Glance

```
                         ┌──────────────────────────┐
                         │        CLIENTS           │
                         │  iOS (Expo build)        │
                         │  Android (Expo build)    │
                         │  Web preview (Metro)     │
                         └────────────┬─────────────┘
                                      │  HTTPS
                                      │  (Bearer session token)
                                      ▼
                    ┌────────────────────────────────────┐
                    │   KUBERNETES INGRESS (Emergent)    │
                    │   /            → :3000  (Expo)     │
                    │   /api/*       → :8001  (FastAPI)  │
                    └────────────────────┬───────────────┘
                                         │
       ┌────────────────────────┬────────┴─────────┬──────────────────────┐
       ▼                        ▼                  ▼                      ▼
┌─────────────┐        ┌────────────────┐  ┌──────────────┐   ┌───────────────────┐
│ Expo Metro  │        │  FastAPI       │  │  MongoDB     │   │  External APIs    │
│ (Node 18)   │        │  (Uvicorn)     │  │  (Motor      │   │  • Emergent LLM   │
│ port 3000   │◄─call──│  port 8001     │──┤  async)      │   │  • Emergent Auth  │
│ RN Web +    │        │  • lifespan()  │  │              │   │  • PayPal REST v2 │
│ Expo Router │        │  • CORS *      │  │  Collections:│   │  • Stripe REST    │
└─────────────┘        │  • JWT Bearer  │  │   users      │   │  • YouTube v3     │
                       │  • Streaming   │  │   sessions   │   │    (dormant)      │
                       └────────────────┘  │   assets     │   │  • IG Graph       │
                                           │   goals      │   │    (dormant)      │
                                           │   content    │   └───────────────────┘
                                           │   plans      │
                                           │   chats      │
                                           │   connections│
                                           │   checkouts  │
                                           └──────────────┘
```

Every URL that isn't `/api/*` is routed to Expo Metro on **port 3000**; every
URL with `/api/*` prefix is routed to Uvicorn on **port 8001**. Only these two
ports are exposed; all other services (Mongo, LLM provider) are reached from
inside the pod over private networking.

---

## 3. Tech Stack

| Layer          | Choice                                | Why                                          |
|----------------|---------------------------------------|----------------------------------------------|
| Mobile UI      | React Native + Expo SDK (Expo Router) | One codebase → iOS, Android, Web preview     |
| Navigation     | Expo Router (file-based)              | Type-safe deep links, native transitions     |
| State          | React Context (Auth, Onboarding)      | Minimal — no Redux needed at this scale      |
| Charts         | react-native-svg (hand-rolled)        | Full control, no chart-lib bloat             |
| HTTP           | Native `fetch` wrapped in `api.ts`    | Bearer auto-injection, JSON helpers          |
| Storage        | `expo-secure-store` + `AsyncStorage`  | Session token in SecureStore, prefs in AS    |
| Auth           | Emergent Google Auth (platform)       | Zero-config OAuth for MVP                    |
| Backend        | FastAPI 0.116 + `lifespan`            | Native async, streaming, type-safe schemas   |
| DB driver      | Motor (Mongo async)                   | Non-blocking under Uvicorn's loop            |
| Payments       | Stripe REST + PayPal Orders v2 REST   | No deprecated SDKs — pure `httpx`            |
| LLM            | Claude Sonnet 4.5 via `emergentintegrations` | Streaming SSE, multi-turn context     |
| Rate limit     | In-process sliding window (`quotas.py`) | Zero-dep for single-worker Uvicorn         |
| Env / secrets  | `python-dotenv` from `backend/.env`   | K8s-friendly; secrets never in git           |

Package-manager: **yarn** (frontend), **pip** with `requirements.txt` (backend).

---

## 4. Component Overview

### 4.1 Frontend components (React Native)

| Route / File                       | Type            | Purpose                                                            |
|-----------------------------------|-----------------|--------------------------------------------------------------------|
| `app/_layout.tsx`                 | Root layout     | Font loading, `SafeAreaProvider`, `GestureHandlerRootView`, LogBox |
| `app/login.tsx`                   | Screen          | Landing / Google OAuth trigger                                     |
| `app/onboarding.tsx`              | Screen (3-step) | Handle capture (YouTube, IG), goal, tier                           |
| `app/(tabs)/_layout.tsx`          | Tab nav         | 5 tabs: Dashboard, Portfolio, Coach, Finance, Profile              |
| `app/(tabs)/index.tsx`            | Dashboard       | Revenue, profit, health score, radar, top recs                     |
| `app/(tabs)/portfolio.tsx`        | Portfolio list  | Asset cards with sparklines · taps → `/asset/[id]`                 |
| `app/(tabs)/coach.tsx`            | AI Coach        | Streaming SSE chat with Claude Sonnet 4.5                          |
| `app/(tabs)/finance.tsx`          | Finance         | Chart, KPIs, revenue-mix, expense breakdown, 90d forecast          |
| `app/(tabs)/profile.tsx`          | Profile         | User info, tier, connections summary, goals summary                |
| `app/integrations.tsx`            | Screen          | Connections Hub — 4 provider cards + connect flow                  |
| `app/asset/[id].tsx`              | Dynamic screen  | Per-asset detail (KPIs, benchmarks, recs, content)                 |
| `app/goals.tsx`                   | Screen          | Goal CRUD with progress bars                                       |
| `app/strategy.tsx`                | Screen          | 30/60/90-day plans with task checkboxes                            |
| `app/competitors.tsx`             | Screen          | Radar chart vs Top 1%                                              |
| `app/pricing.tsx`                 | Screen          | Tier cards + Stripe/PayPal checkout modal                          |
| `src/components/AddAssetModal.tsx`| Component       | Portfolio "add" modal with per-field validation                    |
| `src/components/NotificationsModal.tsx` | Component | In-app notifications list                                          |
| `src/auth/AuthContext.tsx`        | Provider        | Session token, current user, sign-in/out                           |
| `src/services/api.ts`             | Service         | 40+ typed API methods, Bearer injection                            |
| `src/theme/tokens.ts`             | Design tokens   | Colors, spacing, radius, platformMeta, fmtCurrency                 |

### 4.2 Backend components (FastAPI)

| Module            | Responsibility                                            |
|-------------------|-----------------------------------------------------------|
| `server.py`       | App bootstrap, CORS, lifespan, health & dev endpoints, dashboards, portfolio, finance, goals, assets, recommendations, notifications, AI chat streaming, auto-seed |
| `auth.py`         | Google session handling, `current_user` dep, indexes      |
| `billing.py`      | Tier catalog (Free/Pro/Studio), checkout sessions, PayPal Orders v2 endpoints, DEMO_MODE gate |
| `paypal_client.py`| PayPal REST v2 client: `create_order`, `capture_order`, OAuth token cache |
| `integrations.py` | Connections Hub — YouTube, IG, Stripe, PayPal per-user connection state + deterministic mock data |
| `competitors.py`  | Top-1% peer benchmark radar data                          |
| `strategy.py`     | 30/60/90-day AI plan generator + task PATCH               |
| `quotas.py`       | Free-tier daily/weekly quotas + in-process rate limiting  |

### 4.3 Data model (MongoDB collections)

| Collection         | Key fields                                                          | Indexes                     |
|--------------------|---------------------------------------------------------------------|-----------------------------|
| `users`            | user_id (UUID), email, name, tier, onboarding_complete, integrations| email UQ, user_id UQ        |
| `user_sessions`    | session_token, user_id, expires_at                                  | token UQ, user_id, TTL      |
| `assets`           | id, user_id, name, platform, category, revenue_mtd, profit_mtd, followers, ai_score, trend[] | user_id |
| `goals`            | id, user_id, title, kind, target, current, deadline                 | user_id                     |
| `content`          | id, user_id, platform, title, views, likes, ctr, virality           | user_id                     |
| `recommendations`  | id, user_id, title, summary, priority, expected_roi                 | user_id                     |
| `strategy_plans`   | id, user_id, title, duration_days, north_star, phases[], task_progress{}, progress_pct | user_id |
| `chat_messages`    | id, user_id, session_id, role, content, at                          | user_id, (user_id+session_id+at) |
| `connections`      | user_id, provider, account, summary, stats, connected_at            | user_id, (user_id+provider) UQ |
| `checkout_sessions`| session_id / order_id, user_id, tier, provider, amount, status      | user_id, (user_id+order_id) |
| `notifications`    | id, user_id, title, body, kind, read, created_at                    | user_id                     |

---

## 5. Cross-cutting Concerns

### 5.1 Authentication
- Emergent Google Auth issues a **session token** returned via deep link
  callback (`creatoros://auth/callback?session_id=...`) — parsed by
  `AuthContext.parseSessionId`.
- Token stored in **SecureStore** (native) / **AsyncStorage** (web).
- Every backend call attaches `Authorization: Bearer <token>` via
  `authFetch` in `api.ts`.
- `current_user` dependency in FastAPI resolves the token in `user_sessions`
  and hydrates the user document. **TTL index** auto-expires stale sessions.
- No refresh tokens; sessions valid for ~30 days then silent re-login.

### 5.2 Authorization / Multi-tenant isolation
- Every non-public endpoint requires `Depends(current_user)`.
- Every query filters by `user_id = user["user_id"]`. Cross-user reads/writes
  are structurally impossible — pytest suite `test_v13/14` explicitly enforces
  this with a cross-user 404 test on every collection.

### 5.3 Streaming (AI Coach)
- FastAPI returns `StreamingResponse(media_type="text/event-stream")`.
- `emergentintegrations.LlmChat.send_message_stream` yields `TextDelta` chunks
  → serialised as SSE `data: {"delta": "..."}\n\n`.
- Frontend uses `fetch` + `ReadableStream` reader in `coach.tsx` — no
  third-party SSE library needed.

### 5.4 Payments — dual-provider strategy

```
User picks tier in Pricing screen
       │
       ▼
   Choose method
   ┌─────────┴─────────┐
   ▼                   ▼
Stripe                PayPal
(mock/live)         (mock/live)
   │                   │
   ▼                   ▼
POST /checkout      POST /paypal/create-order
   │                   │
   │                   ▼
   │            approval_url? ── yes ──► WebBrowser.openAuthSessionAsync
   │                   │                            │
   ▼                   ▼                            ▼
POST /checkout/    POST /paypal/capture   ◄────  callback URL parsed
   confirm             │
   │                   ▼
   ▼             flip user.tier
flip user.tier
```

- **DEMO_MODE=true**: mock capture flips tier without a real charge — great
  for demos/tests. Backend logs `WARNING` on every mock flip.
- **DEMO_MODE=false**: `/checkout/confirm`, `/upgrade`, and mocked PayPal
  captures return **402 Payment Required**. Only a real Stripe webhook or a
  real PayPal capture (with configured keys) can flip a tier — makes
  self-service upgrade impossible.

### 5.5 Quotas & Rate limiting (`quotas.py`)
- Free tier: **10** AI chat msgs / day, **1** strategy plan / week.
- Message length hard cap: **4000 chars** → 413.
- Sliding-window burst caps (per user_id, per process):
  - chat: 30 requests / 60s
  - strategy: 5 / hour
  - PayPal order create: 10 / hour
- Pro / Studio bypass tier quotas but still hit burst caps.
- Storage: `collections.deque` in-process. Swap for Redis when running >1
  worker.

### 5.6 Deterministic mocks
- `integrations.py` uses `hashlib.md5(handle)` → `random.Random(seed)` so the
  same handle always produces the same "stats". This means demo screenshots
  are stable across sessions, and QA can rely on fixed numbers.

### 5.7 Auto-seed
- First hit to `/api/dashboard` or `/api/portfolio` triggers `_ensure_seeded`
  which populates a rich Maya-style starter dataset (assets, goals, content,
  recommendations, notifications) scoped to that user. Preserves the sense
  that "the app is already alive" from first launch.

### 5.8 Observability
- Uvicorn access logs + supervisor stderr → `/var/log/supervisor/*.log`.
- Structured warnings on all security-sensitive events
  (`DEMO_MODE tier flip via ...`).
- PII (emails, tokens) is never logged — sanitized in error responses.

---

## 6. Non-Functional Requirements & Guarantees

| Attribute            | Target                                                  |
|----------------------|---------------------------------------------------------|
| Cold start (mobile)  | < 2.5s on Expo Go, < 1.2s on native build               |
| Dashboard fetch      | p95 < 400ms (auto-seed adds ~600ms on first call)       |
| AI first-token latency | < 1.2s (streaming)                                    |
| Availability         | 99.5% (single-region K8s deployment)                    |
| Data durability      | MongoDB replicated at platform layer                    |
| Security             | 65/65 pytest for cross-user, quota, and auth pass       |
| Accessibility        | 44pt hit targets, dynamic-type friendly, VoiceOver labels |

---

## 7. Environments & Deployment

| Env         | DEMO_MODE | Real payment keys | Real integration keys | Notes                           |
|-------------|-----------|-------------------|-----------------------|---------------------------------|
| dev (pod)   | true      | absent            | absent                | Auto-seed + mock capture on     |
| staging     | true      | Stripe test key   | absent                | Real Stripe test charges        |
| production  | false     | Stripe live + PayPal live | YouTube + IG keys | Only real captures flip tiers   |

Build & release:
- **Web preview**: Metro dev server on `:3000` — instant hot reload.
- **iOS TestFlight**: Expo Application Services build → App Store Connect.
- **Android APK/AAB**: Same EAS pipeline → Google Play internal track.
- Backend: single Uvicorn worker managed by supervisord; scale by adding
  workers + replacing in-process rate-limit deque with Redis.

---

## 8. Known Trade-offs

1. **Mock data by default**: chosen intentionally so the app is demoable
   without third-party credentials. Real APIs auto-activate when keys are
   supplied — no code change needed.
2. **In-process rate limit**: fine for single-worker MVP. Redis-based
   limiter needed above ~50 rps or with horizontal scaling.
3. **No webhooks yet**: PayPal capture is inline (blocking). For production
   we should add async webhook receivers to survive network glitches during
   the return trip.
4. **Session tokens are opaque, non-refresh**: acceptable for MVP; JWT + RT
   pair would allow shorter TTLs.

---

## 9. Related Documents

- `02_LLD.md` — Low-level design (module-by-module, endpoint-by-endpoint)
- `03_USER_JOURNEY.md` — End-to-end flows with edge-case matrix
- `04_METRICS_AND_AB.md` — Evaluation metrics & A/B test framework
- `/app/memory/PRD.md` — Original product requirements
