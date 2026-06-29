# CreatorOS — Product Requirements (v2: + Auth, Strategy, Competitors, Real APIs)

## Vision
An AI-native business operating system for digital creators, solopreneurs, and personal brands.

## v2 additions (this release)
- **Emergent Google Auth** — sign-in gate at `/login`, 7-day session tokens, AuthContext + route gate. All `/api/*` calls send `Authorization: Bearer <token>`.
- **Top 1% Benchmark** (`/competitors`) — radar chart (Consistency / Content / Monetization / Brand / Engagement) showing You vs Top 1% vs Industry Avg, plus ranked Gap analysis bars (Revenue, Audience, Reach, Cadence, etc).
- **AI Strategy Planner** (`/strategy`) — Claude Sonnet 4.5 generates structured 30/60/90-day roadmaps with North Star metric, KPIs, phased milestones, weekly tasks, risks, and leading indicators. Plans persist to MongoDB and are browsable as history.
- **YouTube Data API** integration — `GET /api/integrations/youtube/channel?handle=X` returns live channel stats (subscribers, views, videos). Gracefully returns 503 with friendly message when `YOUTUBE_API_KEY` not configured.
- **Stripe** integration — `GET /api/integrations/stripe/status` checks live balance + 5 recent charges via `stripe-python`. Returns `{connected: bool, mode: "test"|"live", ...}`. Reports auth errors gracefully when key is invalid.
- **Profile** shows current Google user (name, picture, email), connected integrations status (Stripe / YouTube), goals, top content, and sign-out.

## v1 (still present)
- Smart AI Dashboard, Portfolio, Finance, AI Coach (Claude streaming chat) — all now behind auth.

## Tech additions
- Backend: `httpx` (Emergent session exchange + YouTube), `stripe` (sk_test_emergent dev key).
- Frontend: `expo-web-browser` + `expo-linking` + `expo-secure-store` for OAuth.
- Modular FastAPI sub-routers: `auth.py`, `competitors.py`, `strategy.py`, `integrations.py`.

## Architecture notes
- `load_dotenv()` runs BEFORE local imports so sub-routers can read env at module import.
- TTL index on `user_sessions.expires_at` so expired sessions auto-purge.
- Auth uses Bearer header (not cookies) — required for React Native.
- Stripe SDK is sync; wrapped via `run_in_executor` so it never blocks the event loop.

## What's still NOT in scope
- Real per-user data isolation (everyone signed in sees the Maya persona — intentional for demo; next phase will scope assets/goals by `user_id`)
- Instagram Graph OAuth (heavy lift, deferred)
- Custom YouTube key onboarding UI (env var only)
- Light theme toggle, push notifications

## Smart business enhancement
**The "Top 1% Benchmark" radar is the share-bait moment.** Creators love showing how they stack against the best — this single screen turns CreatorOS from "personal dashboard" into "creator status symbol", driving organic growth via screenshots shared on X/IG. We use synthetic archetypal personas (no real handles) so there's no IP exposure.
