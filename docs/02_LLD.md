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
