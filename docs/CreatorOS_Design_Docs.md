# CreatorOS — Complete Engineering Design Documentation
> **Version 1.0 · June 2026 · Confidential**
> HLD · LLD · User Journeys · Evaluation Metrics · A/B Framework

---

## Table of Contents
1. **Part I — High-Level Design**
2. **Part II — Low-Level Design**
3. **Part III — End-to-End User Journey**
4. **Part IV — Evaluation Metrics & A/B Testing**

---



# Part I — High-Level Design

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


---



# Part II — Low-Level Design

# CreatorOS — Low-Level Design (LLD)

Version 1.0 · June 2026 · Companion to `01_HLD.md`

This document describes **every backend module, every endpoint, every DB
collection field, every third-party call, and every frontend screen** with
parameter-level detail. Read this before touching any part of the codebase.

---

## Table of Contents
1. Directory layout
2. Backend modules
3. REST API reference (grouped)
4. MongoDB schema reference
5. Frontend module reference
6. Third-party integrations
7. Security controls
8. Testing surfaces

---

## 1. Directory Layout

```
/app
├── backend/
│   ├── server.py          # FastAPI app + core endpoints (~825 lines)
│   ├── auth.py            # Google session dep + indexes
│   ├── billing.py         # Tiers, checkout, PayPal endpoints, DEMO_MODE
│   ├── paypal_client.py   # PayPal REST v2 (httpx)
│   ├── integrations.py    # Connections Hub — YT/IG/Stripe/PayPal
│   ├── competitors.py     # Top-1% radar peer set
│   ├── strategy.py        # AI-generated 30/60/90-day plans
│   ├── quotas.py          # Quota + rate-limit enforcement
│   ├── requirements.txt
│   ├── .env               # DO NOT COMMIT
│   └── tests/             # v10, v12, v13, v14 pytest suites
│
├── frontend/
│   ├── app/               # Expo Router (file = route)
│   │   ├── _layout.tsx    # Root providers
│   │   ├── login.tsx
│   │   ├── onboarding.tsx
│   │   ├── integrations.tsx
│   │   ├── goals.tsx
│   │   ├── strategy.tsx
│   │   ├── competitors.tsx
│   │   ├── pricing.tsx
│   │   ├── asset/[id].tsx
│   │   └── (tabs)/        # Tab bar group
│   │       ├── _layout.tsx
│   │       ├── index.tsx  # Dashboard
│   │       ├── portfolio.tsx
│   │       ├── coach.tsx
│   │       ├── finance.tsx
│   │       └── profile.tsx
│   ├── src/
│   │   ├── auth/AuthContext.tsx
│   │   ├── services/api.ts
│   │   ├── theme/tokens.ts
│   │   └── components/
│   │       ├── AddAssetModal.tsx
│   │       └── NotificationsModal.tsx
│   ├── app.json
│   ├── package.json
│   └── .env
│
└── docs/                  # ← You are here
```

---

## 2. Backend Modules

### 2.1 `server.py`

**Bootstrap**
```python
@asynccontextmanager
async def lifespan(app_: FastAPI):
    await ensure_indexes(db)   # from auth.py
    yield
    client.close()             # Motor client teardown

app = FastAPI(title="CreatorOS API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, ...)
```

**Sub-routers included**
```python
api.include_router(auth_router)
api.include_router(make_integrations_router(db, current_user))
api.include_router(make_competitors_router())
api.include_router(make_strategy_router(db, current_user, EMERGENT_LLM_KEY))
api.include_router(make_billing_router(db, current_user))
app.include_router(api, prefix="/api")
```

**Key helpers**
- `_hash_seed(user_id: str) → int` — deterministic seed for per-user mocks
- `_ensure_seeded(uid: str)` — idempotent Maya-style dataset seeding
- `_finance_series(base_rev, base_exp, seed) → list[dict]` — 30-day P&L
  synthesis with daily variance
- `PROJECTION = {"_id": 0}` — always strip Mongo `_id` from responses

**Domain models (Pydantic)**
```python
class ChatRequest(BaseModel):
    session_id: str
    message: str

class Asset(BaseModel):
    id: str; user_id: str
    name: str; platform: str; category: str
    revenue_mtd: float; profit_mtd: float
    followers: int; ai_score: int
    trend: list[float]

class Goal(BaseModel):
    id: str; user_id: str
    title: str; kind: Literal["revenue","followers","subscribers","launch","content"]
    target: float; current: float
    deadline: Optional[str]

class GoalUpdate(BaseModel):
    current: Optional[float] = None
    target: Optional[float] = None
    title: Optional[str] = None
    deadline: Optional[str] = None
```

### 2.2 `auth.py`
```python
async def current_user(authorization: str = Header(...)) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    session = await db.user_sessions.find_one({"session_token": token})
    if not session or session["expires_at"] < now_utc():
        raise HTTPException(401, "Invalid session")
    user = await db.users.find_one({"user_id": session["user_id"]})
    return user

async def ensure_indexes(db):
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)  # TTL
    for c in ("assets","goals","content","recommendations","notifications",
              "strategy_plans","chat_messages","connections","checkout_sessions"):
        await db[c].create_index("user_id")
    await db.chat_messages.create_index([("user_id",1),("session_id",1),("at",1)])
    await db.connections.create_index([("user_id",1),("provider",1)], unique=True)
```

### 2.3 `billing.py`

**TIERS constant** (server-authoritative pricing):
```python
TIERS = {
  "free":   {price_monthly: 0,  limits: {chats_per_day: 10, plans_per_week: 1}, ...},
  "pro":    {price_monthly: 29, limits: {chats_per_day: None, plans_per_week: None}, popular: true},
  "studio": {price_monthly: 99, limits: {...}},
}
DEMO_MODE = os.environ["DEMO_MODE"].lower() == "true"  # default true
```

**Key helpers**
- `_reject_mock_upgrade()` → `HTTPException(402, "Payment required...")`
- `_is_safe_callback_url(url)` → bool. Accepts `https://` + `<scheme>://`
  deep-links. Rejects `http://`, `javascript:`, `data:`, `file:`, `vbscript:`
  and URLs > 2000 chars.

**Endpoints** (see §3.4)

### 2.4 `paypal_client.py`

Constants: `PAYPAL_MODE` (sandbox|live), `_BASE` (auto-selected).

Functions:
```python
def is_configured() -> bool:
    return bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)

async def _get_access_token(client) -> str:
    # OAuth2 client_credentials; cached in _token_cache with expires_at

async def create_order(*, amount, currency='USD', reference_id,
                       description, return_url, cancel_url) -> dict:
    # POST /v2/checkout/orders with intent=CAPTURE, purchase_units,
    # application_context (brand_name, PAY_NOW user_action, NO_SHIPPING).
    # Returns {id, status, approval_url, raw}

async def capture_order(order_id: str) -> dict:
    # POST /v2/checkout/orders/{id}/capture
    # Idempotent via PayPal-Request-Id: cap_{order_id}

async def get_order(order_id: str) -> dict:
    # GET /v2/checkout/orders/{id}
```

Token cache lives in module scope: `_token_cache = {"token": None, "expires_at": 0}`.

### 2.5 `integrations.py`

`PROVIDER_META` dict — 4 entries (youtube, instagram, stripe, paypal) with
`name`, `description`, `color`, `input_label`, `input_placeholder`, `input_prefix`.

Deterministic mock generators:
```python
def _seed_from(text) -> int:  # md5[:8] → int
def _mock_youtube(handle) -> dict:  # subs, views, videos, recent_videos[6], avg_rpm, avg_ctr, monthly_earnings
def _mock_instagram(handle) -> dict: # followers, engagement, recent_reels[6], monthly_reach
```

Real API fallback: if `YOUTUBE_API_KEY` is set and the HTTP call to
`googleapis.com/youtube/v3/channels?forHandle=...` returns 200, use real data;
else fall back to mock.

### 2.6 `strategy.py`

`generate()` endpoint takes `StrategyRequest(horizon_days: Literal[30,60,90], focus: Optional[str], asset_context: Optional[list])`.

Flow:
1. Call `enforce_strategy_plan(db, user)` → quota check.
2. Validate `focus <= 500` chars.
3. Compose system prompt with tier-aware persona instructions.
4. Stream Claude Sonnet 4.5 via `LlmChat.send_message_stream`.
5. Parse the final JSON into a `StrategyPlan` doc, persist with `progress_pct=0`.

`PATCH /strategy/{plan_id}/task` updates `task_progress` map and recomputes
`progress_pct = done_tasks / total_tasks * 100`.

### 2.7 `quotas.py`

Constants:
```python
MAX_CHAT_MESSAGE_CHARS = 4000
FREE_TIER_LIMITS = {"chats_per_day": 10, "plans_per_week": 1}
BURST_LIMITS = {
  "chat":          (30, 60),     # 30 / min
  "strategy":      (5, 3600),    # 5 / hour
  "paypal_order":  (10, 3600),   # 10 / hour
}
```

Public functions:
- `check_burst(user_id, kind)` — raises 429 if window exceeded.
- `enforce_chat_message(db, user, message)` — 400 empty, 413 too long,
  burst check, then 402 if free-tier daily cap hit.
- `enforce_strategy_plan(db, user)` — burst check + 402 if weekly cap hit.
- `enforce_paypal_order(user)` — burst only (pricing is server-authoritative).

Storage: `_windows: dict[kind → dict[user_id → deque[timestamps]]]`.

---

## 3. REST API Reference

Base URL: `<host>/api`. All non-public endpoints require
`Authorization: Bearer <session_token>`. All responses are JSON except AI
streaming which is `text/event-stream`.

### 3.1 Health & Auth
| Method | Path             | Params                             | Success | Errors      |
|--------|------------------|------------------------------------|---------|-------------|
| GET    | `/`              | —                                  | `{name, ok}` | —           |
| POST   | `/auth/google/callback` | `{code, redirect_uri}` (deep-link) | `{session_token, user}` | 400, 401 |
| GET    | `/auth/me`       | Header only                        | user doc | 401         |
| POST   | `/auth/logout`   | Header only                        | `{ok: true}` | 401         |

### 3.2 Dashboard, Portfolio, Finance, Assets
| Method | Path                | Params / Body                                        | Success shape                                                                 |
|--------|---------------------|------------------------------------------------------|-------------------------------------------------------------------------------|
| GET    | `/dashboard`        | —                                                    | `{hero{...}, kpis[4], top_recs[3], radar{...}, health_score:int}`             |
| GET    | `/portfolio`        | —                                                    | `{assets: Asset[]}`                                                           |
| POST   | `/assets`           | `{name, platform, category, revenue_mtd, profit_mtd, followers, ai_score, trend[]}` | Asset                                    |
| GET    | `/assets/{id}`      | path id                                              | `{asset, content[], recommendations[], benchmarks{...}, kpis[4]}` — 404 cross-user |
| GET    | `/finance`          | —                                                    | `{summary{revenue_30d, expense_30d, profit_30d, margin, forecast_60d, forecast_90d, runway_months}, series[30], projection[90], by_asset[], by_platform[], expense_categories[5], transactions[]}` |
| GET    | `/goals`            | —                                                    | `{items: Goal[]}`                                                             |
| POST   | `/goals`            | `{title, kind, target, current, deadline?}`          | Goal                                                                          |
| PATCH  | `/goals/{id}`       | `{title?, target?, current?, deadline?}` — at least one | Updated Goal · 400 invalid · 413 title>120 · 404 cross-user                |
| DELETE | `/goals/{id}`       | —                                                    | `{ok: true}` · 404 cross-user                                                 |
| GET    | `/content`          | —                                                    | `{items: ContentItem[]}`                                                      |
| GET    | `/recommendations`  | —                                                    | `{items: Recommendation[]}` — sorted by priority desc                         |
| GET    | `/notifications`    | —                                                    | `{items: Notification[]}`                                                     |
| PATCH  | `/notifications/{id}` | `{read: true}`                                     | Notification                                                                  |

### 3.3 AI Coach & Strategy
| Method | Path              | Params / Body                                          | Success                                            |
|--------|-------------------|--------------------------------------------------------|----------------------------------------------------|
| POST   | `/ai/chat`        | `{session_id: str, message: str}`                      | SSE stream `data: {"delta":"..."}\n\n` · 400 empty · 413 >4000 chars · 402 free-tier cap · 429 burst |
| GET    | `/ai/chat/history` | `?session_id=<str>`                                   | `{items: [{role, content, at}]}`                   |
| POST   | `/strategy/plans` | `{horizon_days: 30|60|90, focus?: str, asset_context?}`| StrategyPlan · 400 invalid horizon · 413 focus>500 · 402 free-tier cap · 429 burst · 500 no AI key |
| GET    | `/strategy/current` | —                                                    | `{plans: StrategyPlan[]}`                          |
| PATCH  | `/strategy/{plan_id}/task` | `{task_id, done: bool}`                       | Plan with updated `progress_pct` · 404              |

### 3.4 Billing
| Method | Path                              | Body                                             | Success                                          |
|--------|-----------------------------------|--------------------------------------------------|--------------------------------------------------|
| GET    | `/billing/plans`                  | —                                                | `{tiers: [FreeTier, ProTier, StudioTier]}`       |
| GET    | `/billing/plan`                   | —                                                | `{tier, ...tier_metadata}`                       |
| POST   | `/billing/checkout`               | `{tier: 'pro'|'studio', provider: 'stripe'|'paypal'}` | Session doc with `session_id`, `checkout_url`, `status:'pending'` — 400 free tier |
| POST   | `/billing/checkout/confirm`       | `{session_id}`                                   | `{ok, tier}` — **402 in DEMO_MODE=false**         |
| POST   | `/billing/paypal/create-order`    | `{tier, return_url, cancel_url}`                 | Session with `order_id`, `approval_url` (or null in mock) — 400 invalid URL / tier |
| POST   | `/billing/paypal/capture`         | `{order_id}`                                     | `{ok, tier, provider:'paypal', mode?}` — **402 mock in DEMO_MODE=false** · 404 unknown |
| GET    | `/billing/paypal/status`          | —                                                | `{configured, mode}`                             |
| POST   | `/billing/upgrade`                | `{tier}`                                         | DEMO_MODE only — else **410 Gone**               |

### 3.5 Integrations Hub
| Method | Path                                    | Body            | Success                                                           |
|--------|-----------------------------------------|-----------------|-------------------------------------------------------------------|
| GET    | `/integrations/connections`             | —               | `{connections: [Provider × 4]}`                                   |
| POST   | `/integrations/{provider}/connect`      | `{account}`     | `{ok, provider, connection}` — 400 empty                          |
| POST   | `/integrations/{provider}/disconnect`   | —               | `{ok, provider}`                                                  |
| GET    | `/integrations/youtube/channel?handle=` | query optional  | Channel dict (real via `YOUTUBE_API_KEY` else deterministic mock) |
| GET    | `/integrations/instagram/profile?handle=` | query optional | Profile dict                                                      |
| GET    | `/integrations/stripe/status`           | —               | `{connected, mode, available_balance, pending_balance, recent_charges}` |
| GET    | `/integrations/paypal/status`           | —               | `{connected, email, available_balance, mtd_processed, cross_border_pct, recent_transactions}` |

### 3.6 Dev-only (DEMO_MODE guarded)
| Method | Path             | Body | Success                                     |
|--------|------------------|------|---------------------------------------------|
| POST   | `/dev/reseed`    | —    | `{ok:true, seeded:{...}}` — **403** in prod |

---

## 4. MongoDB Schema Reference

### `users`
```json
{
  "user_id": "uuid",
  "email": "maya@example.com",
  "name": "Maya Nakamura",
  "picture": "https://...",
  "onboarding_complete": true,
  "youtube_handle": "mayabuilds",
  "instagram_handle": "maya.builds",
  "tier": "free",
  "tier_updated_at": "2026-06-15T...",
  "integrations": {},
  "created_at": ISODate
}
```

### `assets`
```json
{
  "id": "asset_uuid",
  "user_id": "uuid",
  "name": "Ship It cohort",
  "platform": "course",
  "category": "Cohort-based course",
  "revenue_mtd": 24800,
  "profit_mtd": 18600,
  "followers": 4200,
  "ai_score": 88,
  "trend": [64, 66, 70, 74, 78, 82, 88]
}
```

### `goals`
```json
{
  "id": "goal_uuid",
  "user_id": "uuid",
  "title": "250k YouTube subs",
  "kind": "subscribers",
  "target": 250000,
  "current": 148000,
  "deadline": "2026-12-31"
}
```

### `chat_messages`
```json
{
  "id": "msg_uuid",
  "user_id": "uuid",
  "session_id": "coach-main",
  "role": "user" | "assistant",
  "content": "How do I price my next cohort?",
  "at": "2026-06-15T...Z"
}
```

### `strategy_plans`
```json
{
  "id": "plan_uuid",
  "user_id": "uuid",
  "title": "60-day scale plan",
  "duration_days": 60,
  "north_star": "$40k MRR by Aug",
  "phases": [
    {"id": "p1", "name": "Foundation (days 1-14)", "tasks": [
      {"id": "t1", "text": "Ship pricing page A/B test"}, ...
    ]}, ...
  ],
  "task_progress": { "t1": true, "t2": false, ... },
  "progress_pct": 42,
  "created_at": "..."
}
```

### `connections`
```json
{
  "user_id": "uuid",
  "provider": "youtube",
  "account": "mayabuilds",
  "connected_at": "...",
  "summary": {"label": "@mayabuilds", "primary_metric": "148,209 subs", "secondary_metric": "$4,120/mo est."},
  "stats": { /* full mock or live payload */ }
}
```

### `checkout_sessions`
```json
{
  "session_id": "cs_stripe_...",
  "order_id": "cs_stripe_...",          // == session_id in mock; PayPal order id in real
  "user_id": "uuid",
  "tier": "pro",
  "provider": "stripe" | "paypal",
  "amount": 29,
  "currency": "usd",
  "status": "pending" | "complete",
  "approval_url": null | "https://...",
  "mocked": true | false,
  "created_at": "...",
  "completed_at": "...",
  "capture_id": "...",                   // PayPal capture id when real
  "capture_payload": { ... }             // full PayPal response for audit
}
```

---

## 5. Frontend Module Reference

### 5.1 `AuthContext.tsx`
```typescript
type AuthState = {
  user: User | null;
  token: string | null;
  loading: boolean;
  signIn: () => Promise<void>;        // Opens WebBrowser with OAuth URL
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  parseSessionId: (url: string) => string | null;  // extracts from callback
};

// Token flow:
//   signIn → openAuthSessionAsync → callback URL → parseSessionId
//     → SecureStore.setItemAsync('session_token', token)
//     → fetch /api/auth/me → setUser
```

### 5.2 `api.ts` — 40+ methods
Every method wraps `authFetch()`:
```typescript
async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getToken();
  return fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: token ? `Bearer ${token}` : '',
    },
  });
}
```

Grouped exports: `dashboard`, `portfolio`, `createAsset`, `assetDetail`,
`goals` / `createGoal` / `updateGoal` / `deleteGoal`, `finance`, `content`,
`recommendations`, `notifications`, `notificationsMarkRead`, `aiChatStream`
(returns ReadableStream), `chatHistory`, `strategyPlans`, `strategyCurrent`,
`toggleStrategyTask`, `competitors`, `billingPlans` / `billingPlan` /
`billingCheckout` / `billingConfirm`, `paypalConfig` / `paypalCreateOrder` /
`paypalCapture`, `connections` / `connectProvider` / `disconnectProvider`,
`youtubeChannel`, `instagramProfile`, `stripeStatus`, `paypalStatus`.

### 5.3 Screen state models (representative)

**`goals.tsx`**
```typescript
[goals, setGoals]         : Goal[]
[loading, setLoading]     : boolean
[refreshing, setRefreshing]: boolean
[showAdd, setShowAdd]     : boolean
[editing, setEditing]     : Goal | null
// Modal-local:
[title, setTitle]         : string
[kind, setKind]           : GoalKind
[target, setTarget]       : string    // string during input; parsed on save
[current, setCurrent]     : string
[deadline, setDeadline]   : string
[err, setErr]             : string | null
```

**`pricing.tsx`**
```typescript
[tiers, setTiers]         : Tier[]
[current, setCurrent]     : string   // user's current tier
[paypalLive, setPaypalLive]: boolean
[checkoutTier, setCheckoutTier]: Tier | null
[phase, setPhase]         : 'idle' | 'creating' | 'method' | 'processing' | 'success' | 'error'
[session, setSession]     : any
[provider, setProvider]   : 'stripe' | 'paypal'
[errorMsg, setErrorMsg]   : string | null
```

**`coach.tsx`** (streaming)
```typescript
[messages, setMessages]   : {role, content}[]
[input, setInput]         : string
[streaming, setStreaming] : boolean
[currentDelta, setDelta]  : string    // accumulates SSE chunks
// On submit: fetch → response.body.getReader() → decode → append to delta.
// On done: push assistant message, clear delta.
```

### 5.4 Design tokens (`theme/tokens.ts`)
```typescript
colors = {
  brand: '#FFD060',           // Accent gold
  brandSecondary: '#7FB3FF',  // Cool blue
  brandTertiary: 'rgba(255,208,96,0.14)',
  onBrandPrimary: '#0D0B08',
  surface: '#0A0A0A',
  surfaceSecondary: '#121212',
  surfaceTertiary: '#1B1B1B',
  onSurface: '#FAFAFA',
  onSurfaceSecondary: '#B8B8B8',
  onSurfaceTertiary: '#7A7A7A',
  success: '#45C97A',
  warning: '#E3A72F',
  error: '#E5484D',
  border: '#1F1F1F',
  borderStrong: '#2A2A2A',
  divider: '#181818',
}
spacing = { xs:4, sm:8, md:12, lg:16, xl:24, xxl:32, xxxl:48 }
radius  = { sm:6, md:12, lg:20, pill:999 }
fmtCurrency(n)  → "$24,800"
fmtCompact(n)   → "24.8k"
fmtPercent(n)   → "18.4%"
```

---

## 6. Third-Party Integrations

### 6.1 Emergent LLM (Claude Sonnet 4.5)
```python
from emergentintegrations.llm.chat import LlmChat, UserMessage
chat = LlmChat(api_key=EMERGENT_LLM_KEY, provider="anthropic",
               model="claude-sonnet-4-5",
               system_prompt=coach_system_prompt(user_context))
async for delta in chat.send_message_stream(session_id=scoped_id,
                                            message=UserMessage(content=req.message)):
    yield f"data: {json.dumps({'delta': delta.text})}\n\n"
```
Session id is scoped: `f"{user_id}::{session_id}"` so multi-tenant contexts
never bleed.

### 6.2 PayPal Orders v2
Endpoints hit:
- `POST https://api-m.{sandbox|}paypal.com/v1/oauth2/token` — client_credentials
- `POST /v2/checkout/orders` — with `intent: CAPTURE`, `purchase_units[]`,
  `application_context.return_url/cancel_url`, `PayPal-Request-Id` header for
  idempotency
- `POST /v2/checkout/orders/{id}/capture` — idempotent via header
- Approval URL is extracted from `links[]` where `rel in ('approve','payer-action')`

Deep-link callback flow on mobile:
```
Frontend                              Backend                    PayPal
    │                                    │                          │
    ├── paypalCreateOrder({tier, return_url, cancel_url}) ──►│
    │                                    ├── create_order() ──►│
    │◄──── { order_id, approval_url } ───┤                      │
    │                                                                │
    ├── WebBrowser.openAuthSessionAsync(approval_url, return_url)  ─►│
    │                                                                │  (user approves)
    │◄──────────────── deep link: return_url?token=<order_id> ──────┤
    │                                                                │
    ├── paypalCapture({order_id}) ───────►│                          │
    │                                     ├── capture_order() ────►│
    │◄──── { ok, tier, capture_id } ──────┤                          │
    ▼
[tier flips, success animation]
```

### 6.3 Stripe (test key only, mocked upgrade path in demo)
Real path is prepared: `stripe.Balance.retrieve()` + `stripe.Charge.list()`
in `integrations.py::stripe_status`. Full checkout webhook not yet wired —
next milestone.

### 6.4 YouTube Data API v3 (dormant)
Real call when `YOUTUBE_API_KEY` is set:
```
GET https://www.googleapis.com/youtube/v3/channels
    ?part=snippet,statistics
    &forHandle={handle}
    &key={YOUTUBE_API_KEY}
```

### 6.5 Instagram Graph API (dormant / stub)
Endpoint reserved but not implemented — requires Meta App + long-lived token
handshake. All calls currently return deterministic mock via `_mock_instagram`.

### 6.6 Emergent Google Auth
Platform-managed. Frontend just calls `openAuthSessionAsync(login_url,
callback_deeplink)`. Backend receives the code (or session token embedded in
the callback) and creates a `user_sessions` doc with TTL.

---

## 7. Security Controls

| Control                         | Implementation                                              |
|---------------------------------|-------------------------------------------------------------|
| Multi-tenant isolation          | `Depends(current_user)` + `user_id` filter on every query   |
| Session token storage           | `expo-secure-store` on device                              |
| Session expiry                  | Mongo TTL index on `user_sessions.expires_at`               |
| Payment authorization           | `DEMO_MODE=false` blocks mock upgrades (SEC-001 fix)         |
| Quota / rate limit              | `quotas.py` in-process sliding window (SEC-002 fix)         |
| Message length cap              | 4000 chars (413 on breach)                                  |
| Open-redirect defense           | PayPal `return_url` allowlist (`_is_safe_callback_url`)     |
| Server-authoritative pricing    | Tier `price_monthly` comes only from `TIERS` dict           |
| PayPal capture authorization    | Session lookup filters by `user_id` → cross-user 404        |
| Idempotency                     | `PayPal-Request-Id` on both create + capture                |
| Secret handling                 | `.env` git-ignored; never logged; never returned in errors  |
| Error sanitization              | AI stream & PayPal errors return generic strings to client  |
| CORS                            | `allow_origins=["*"]` — safe with Bearer (no cookie auth)   |

---

## 8. Testing Surfaces

| Suite                                | Coverage                                       | Count |
|--------------------------------------|------------------------------------------------|-------|
| `test_v10_connections_checkout.py`   | Connections Hub CRUD + Stripe mock checkout    | 25    |
| `test_v12_paypal_orders.py`          | PayPal Orders v2 mock flow + auth              | 15    |
| `test_v13_security_fixes.py`         | SEC-001 (DEMO_MODE), SEC-002 (quotas), URL allowlist | 25 |
| `test_v14_goals_asset_finance.py`    | Goals PATCH/DELETE, /assets/{id}, /finance mix | 22    |
| **Total**                            |                                                | **87 pass** |

Frontend smoke: Playwright / `mcp_screenshot_tool` — see `test_reports/iteration_14.json`.

Contract tests (recommended additions):
- Snapshot tests on dashboard/finance response shapes
- Chaos: kill Mongo mid-request → 503 with retry hint
- Load: `wrk`/`k6` on `/dashboard` + `/ai/chat` (streaming latency)


---



# Part III — End-to-End User Journey

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


---



# Part IV — Evaluation Metrics & A/B Testing

# CreatorOS — Evaluation Metrics & A/B Testing Framework

Version 1.0 · June 2026 · Companion to `01_HLD.md`, `02_LLD.md`, `03_USER_JOURNEY.md`

Purpose: define **what "success" means** for CreatorOS, how it is measured
end-to-end, and how experiments are designed, powered, and analyzed.

---

## 1. Measurement Philosophy

We treat CreatorOS as a **compound product**:

1. Data platform (portfolio + finance) — value = *insight density per session*
2. AI advisor (Coach + Strategy) — value = *actions the user commits to*
3. Business OS (goals, integrations, payments) — value = *time saved & tier upgrades*

Every metric ladders up to a single north star. Every experiment either
improves the north star directly or improves an input metric proven to
correlate with it.

---

## 2. Metric Tree

```
                         ┌─────────────────────────────────┐
                         │       NORTH STAR METRIC          │
                         │  Weekly Actioned Insights (WAI)  │
                         │  = per-user count of {AI recs    │
                         │  accepted, strategy tasks done,  │
                         │  goals updated} in last 7 days   │
                         └───────────────┬─────────────────┘
                                         │
       ┌─────────────────────────────────┼─────────────────────────────────┐
       ▼                                 ▼                                 ▼
┌──────────────┐                ┌──────────────┐                  ┌──────────────┐
│  Engagement  │                │   Insight    │                  │ Monetization │
│  L2, L3, L4  │                │  Generation  │                  │              │
└──────┬───────┘                └──────┬───────┘                  └──────┬───────┘
       │                                │                                 │
       ▼                                ▼                                 ▼
 D1, W1, W4                    Insights delivered              Free → Pro conv %
 retention                     per active user                 Pro net retention
 Sessions/week                 AI plan completion rate         ARPU
 Session length                Recs-to-action rate             Payment success %
 Deep-linked opens             Chat msgs / week                Free-tier cap hits
```

### 2.1 North Star — WAI (Weekly Actioned Insights)

Formal definition:
```
WAI(user, week) = |{ acts in that week where act ∈ {
  ai_recommendation_dismissed_with_action == True,
  strategy_task_completed,
  goal_progress_updated (current field changed),
  asset_added,
  new_connection_established,
} }|
```

Rationale: measures whether the app is turning insight into action. Pure
usage metrics (session count) reward re-opens; WAI rewards value delivery.
The **North Star Target for Q3 2026: median WAI per active user ≥ 5.**

### 2.2 Layered KPI reference

| Tier         | KPI                                        | Definition                                        | Q3 target        |
|--------------|--------------------------------------------|---------------------------------------------------|------------------|
| Acquisition  | Signup conversion                          | login-arrived / login-shown                       | ≥ 32%            |
|              | Onboarding completion                      | Step-3-complete / signup                          | ≥ 70%            |
| Activation   | Time-to-First-Insight (TTFI)               | signup → first AI rec viewed                      | < 3 min          |
|              | Time-to-First-Strategy                     | signup → first plan generated                     | < 12 min          |
| Retention    | D1 / W1 / W4                               | active on day/week 1/4 after signup               | 62 / 45 / 28 %   |
| Engagement   | Median sessions / week                     | Any authenticated app open                        | ≥ 4              |
|              | Coach msgs / week (free)                   | User-role msgs, capped by quota                   | 6–10             |
| Insight      | AI plan completion rate                    | plans with `progress_pct = 100`                   | ≥ 40%            |
|              | Rec-to-action rate                         | recs marked "done"/"applied"                      | ≥ 25%            |
| Monetization | Free → Pro conversion                      | Trialists who upgrade within 14 days              | ≥ 4%             |
|              | Payment success rate                       | checkout_completed / checkout_started             | ≥ 92%            |
|              | Free-tier cap hit rate                     | Users hitting `/ai/chat` 402 in a week            | Watch — high = raise limits or promote upgrade |
| Reliability  | API p95 latency                            | Nginx → Uvicorn RTT                                | < 400 ms         |
|              | AI TTFT (time to first token)              | Client-observed                                    | < 1200 ms        |
|              | Crash-free sessions                        | Sentry crash rate                                  | ≥ 99.6%          |
| Trust        | Cross-user isolation regressions           | pytest failures                                    | 0                |

---

## 3. Event Taxonomy

All events are POSTed to `/api/analytics` (to be built) with a common envelope:

```json
{
  "event": "checkout_completed",
  "at": "2026-06-15T18:03:22Z",
  "user_id": "uuid",
  "tier": "pro",
  "session": {"device": "ios", "app_version": "1.4.0", "build": 200},
  "props": { "provider": "paypal", "amount": 29, "real": true, "duration_ms": 3410 }
}
```

### 3.1 Event catalogue

| Event                                     | Required props                                         |
|-------------------------------------------|--------------------------------------------------------|
| `signup_started`                          | source                                                 |
| `signup_completed`                        | provider (google), ms                                  |
| `onboarding_step_started`                 | step (1,2,3)                                           |
| `onboarding_step_completed`               | step, dwell_ms                                         |
| `dashboard_loaded`                        | seeded (bool), ms, kpi_count                           |
| `asset_added`                             | platform, source ("modal"|"seed")                       |
| `asset_detail_viewed`                     | asset_id, platform                                     |
| `ai_chat_message_sent`                    | tier, len, session_id                                  |
| `ai_chat_stream_started`                  | ttft_ms                                                |
| `ai_chat_stream_completed`                | total_ms, tokens_out                                   |
| `ai_chat_stream_error`                    | reason                                                 |
| `strategy_plan_requested`                 | horizon, tier                                          |
| `strategy_plan_generated`                 | horizon, ms                                            |
| `strategy_task_completed`                 | plan_id, task_id, plan_progress_pct                    |
| `goal_created`                            | kind                                                   |
| `goal_updated`                            | kind, delta_pct                                        |
| `goal_completed`                          | kind, days_to_close                                    |
| `connect_provider_attempted`              | provider                                               |
| `connect_provider_succeeded`              | provider, mocked                                       |
| `connect_provider_failed`                 | provider, reason                                       |
| `checkout_started`                        | tier, provider                                         |
| `checkout_method_selected`                | tier, provider                                         |
| `checkout_completed`                      | tier, provider, real, ms                               |
| `checkout_failed`                         | tier, provider, code, reason                           |
| `quota_hit`                               | kind (chat|strategy|paypal_order), tier                |
| `upgrade_cta_shown`                       | placement (chat_402|strategy_402|profile_banner)       |
| `upgrade_cta_tapped`                      | placement                                              |
| `recommendation_shown` / `recommendation_actioned` | rec_id, priority                             |

### 3.2 Instrumentation levels

- **Client** — Every screen entry, every button tap with meaningful side
  effect, every stream begin/end. Batched every 15s with retry on backoff.
- **Server** — Every 4xx/5xx on payment or quota endpoints logged with
  reason. Every DEMO_MODE tier flip logged as WARNING for audit.
- **Aggregation** — Daily rollup job writes `daily_metrics` per user for
  fast dashboard reads.

---

## 4. A/B Testing Framework

### 4.1 Assignment
```
bucket(user_id, experiment_key) =
   int(md5(f"{user_id}:{experiment_key}").hexdigest()[:8], 16) % 100
```
- Stable per user per experiment.
- Ramp control: expose only bucket < RAMP_PCT.
- Variant assignment written to `db.experiments` for the user on first
  exposure and never mutated (avoids the "peeked at data, moved a user"
  bias).

### 4.2 Framework contract
```python
# backend/experiments.py (to be built)
def get_variant(user_id: str, key: str, variants: list[str],
                ramp_pct: int = 100) -> str | None:
    """
    Returns None if user is outside the ramp — caller renders control.
    Otherwise deterministically hashes into one variant.
    Persists the assignment on first call.
    """
```

Frontend calls `useExperiment(key, variants)` — returns variant string.
Every render/exposure emits `exposure_recorded{experiment, variant}` event.

### 4.3 Sample size & power

Standard settings:
- α = 0.05 (two-sided)
- 1−β = 0.8
- Baseline conversion rates observed from `daily_metrics` for the past 4
  weeks. Effect-size floor: **relative +10%** for growth metrics,
  **absolute +2pp** for retention.

Rule of thumb:
```
n_per_arm ≈ 16 * p*(1-p) / MDE²
```
For a 4% Free→Pro baseline and a +1pp MDE: n ≈ 61,400 per arm (which
means we're often bandwidth-limited and must pick fewer, larger bets).

### 4.4 Guardrails
Every experiment must declare:
- Primary metric (usually WAI or a direct input)
- Guardrails that MUST NOT regress by more than X% at 95% CI:
  - crash-free sessions (never < 99.4%)
  - checkout success rate
  - AI TTFT
  - Free-tier cap hit rate (must not spike)
  - Session duration (protect from dark-pattern outcomes)

Auto-stop if any guardrail regresses beyond threshold for 3 consecutive days.

---

## 5. Reference Experiments (Q3 2026)

### E1 — Onboarding: 3-step vs 1-step
- **Hypothesis**: A single "handles + goal" screen increases completion
  by ≥ 8pp without hurting downstream activation.
- Primary: onboarding_completion
- Secondary: TTFI, W1 retention
- Guardrails: crash-free, drop-off at step 1
- Sample: 12k signups → ~4 weeks

### E2 — AI Coach quota surface
- **Hypothesis**: Showing "3 of 10 free msgs used" preemptively reduces
  friction at 402 and lifts Free→Pro by ≥ 1pp.
- Variants: Control (no meter) / Meter-only / Meter + upsell chip
- Primary: Free→Pro conv within 14d of first quota_hit
- Secondary: chat msgs/week, upgrade_cta_tapped rate

### E3 — Dashboard hero framing
- **Hypothesis**: Leading with **profit** instead of **revenue** in the
  hero card correlates with faster action on recommendations.
- Variants: revenue-first / profit-first / margin-first
- Primary: WAI within 7 days of first exposure
- Secondary: rec_actioned rate

### E4 — Strategy plan default horizon
- **Hypothesis**: Defaulting to 30 days (vs 60) increases plan completion
  rate ≥ 5pp because scope feels tractable.
- Variants: 30 (control) / 60 / 90
- Primary: strategy_plan_completion (progress_pct = 100 within 45d)
- Guardrails: strategy_plan_requested rate

### E5 — Checkout provider order
- **Hypothesis**: Placing PayPal above Stripe for non-US users increases
  checkout success ≥ 4pp.
- Variants: Stripe-first (control) / PayPal-first
- Primary: checkout_completed / checkout_started
- Cohort: users whose Google account country ∈ EU|LatAm

### E6 — AI Coach system prompt (LLM eval)
- Two prompt variants (concise vs empathic). Each user routed to one.
- Primary: `msg_helpful_thumb_up_rate` (add thumbs-up/down UI to bubbles)
- Secondary: assistant_ttft_ms, chat_len_msgs
- Uses **CTR × conversion** as the joint OEC (Overall Evaluation Criterion)

---

## 6. AI-specific Evaluation

### 6.1 Offline eval
Maintain a golden set of 200 real user prompts (anonymized) covering:
- Pricing questions
- Growth strategy
- Content ideation
- Portfolio triage
- Ambiguous / off-topic prompts

Each new prompt template or model change runs through:
- **BLEU / ROUGE** — surface similarity vs curated gold answers
- **LLM-as-judge** — Claude Opus 4.7 scores helpfulness 1–5 with rubric
- **Regression watchlist** — 20 questions that MUST retain answer quality

### 6.2 Online eval
- Thumb-up/down on every assistant message (feature to add)
- Followed-by-action within 24h: if the user acts on advice the same
  conversation touched, consider the message "actionable" (heuristic
  correlator).
- Length distribution guard — protect against runaway 4k-char answers.

### 6.3 Cost & latency SLOs
- Median cost / assistant message: ≤ $0.008
- P95 cost / assistant message: ≤ $0.03
- Median TTFT: ≤ 1200ms
- P95 total time: ≤ 8s

Alert when any SLO breaches for 15 min sustained.

---

## 7. Financial / Business Metrics

Live on a dedicated internal dashboard, not exposed in-app.

| Metric                 | Definition                                                        |
|------------------------|-------------------------------------------------------------------|
| MRR                    | Σ(active subscribers × tier price)                                |
| ARPU                   | MRR / active users                                                |
| Gross margin           | (Revenue − LLM cost − payment fees − hosting) / Revenue           |
| Payback period         | CAC / (ARPU × gross_margin)                                       |
| Churn (monthly)        | Downgrade or cancellation / total paying users                    |
| NRR                    | Retained + expansion - churn                                      |
| Free-tier LLM cost     | LLM $$ spent per non-paying MAU (protect via quotas)              |

---

## 8. Data Governance & Privacy

- No PII in analytics props. `user_id` is the opaque UUID; email/name
  never sent to the analytics ingestion path.
- Only aggregated, anonymized metrics leave the pod (dashboards read
  from `daily_metrics`).
- Users can request deletion → cascades across `users`, `assets`,
  `chat_messages`, `connections`, `strategy_plans`, `checkout_sessions`
  (soft-delete flag first, hard-delete after 30 days).
- LLM prompts are stored (`chat_messages`) — user can `/auth/purge-history`
  at any time.
- Do not log full LLM outputs to third-party observability tools; log
  metadata only.

---

## 9. Experiment Cadence

| Cadence   | Activity                                                          |
|-----------|-------------------------------------------------------------------|
| Weekly    | Read guardrails; review any auto-stopped experiments               |
| Bi-weekly | Design review: 1 new experiment ships, 1 rolled out or killed     |
| Monthly   | North-star readout to leadership; recalibrate targets              |
| Quarterly | Persona refresh; goldset refresh for LLM eval                     |

---

## 10. Runbooks

- **Experiment auto-stopped**: check guardrail dashboards → post-mortem
  in `/docs/experiments/YYYYMMDD_key.md` → revert variant.
- **Quota_hit spike**: verify LLM cost is stable; if free-tier cap hits
  ≥ 25% of DAU, propose a limits update or upsell push.
- **Payment success drop**: check `checkout_failed.reason` distribution;
  isolate provider; page on-call if drop > 5pp in 15 min.
- **AI TTFT spike**: check emergent LLM upstream latency; auto-fallback
  path to a shorter system prompt if TTFT > 3s p50 for 10 min.

---

## 11. Backlog

- Instrumentation wiring (event ingestion + dashboards) — in progress.
- Server-side experiments framework (`experiments.py`).
- LLM eval harness with automated goldset scoring.
- Cohort explorer for MRR & retention.
- Ship the "insight actioned" thumb-up/down UI on Coach + Recommendations.


---

