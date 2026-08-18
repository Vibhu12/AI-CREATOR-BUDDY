# CreatorOS — Product Requirements (v3: Multi-tenant + Onboarding Wizard)

## Vision
An AI-native business operating system for digital creators, solopreneurs, and personal brands.

## v3 additions (this release)
- **Per-user data isolation** — every asset, goal, content item, recommendation, chat message, and strategy plan is now tagged with `user_id` and scoped in every query. Legacy un-scoped data has been purged.
- **Auto-seeded starter dataset** — first time a user signs in via `/api/auth/session`, an `on_new_user` callback fires `seed_user_starter(user_id)` which copies the Maya persona (6 assets, 4 goals, 4 content items, 4 recommendations) into their namespace. Preserves the wow-moment while keeping data isolated.
- **Onboarding wizard** (`/onboarding`) — 3-step flow: Welcome → Connect YouTube (live handle lookup via YouTube Data API if key configured, else soft-save) → Stripe (placeholder / coming-soon card) → Done. Backed by `GET /api/onboarding/status` + `POST /api/onboarding/complete`.
- **Route gate** — unauth → `/login`; authed & not-onboarded → `/onboarding`; authed & onboarded → `/(tabs)`. Fully bidirectional so completed users can't get back into the wizard.
- **AI Coach system prompt** now dynamically builds from the user's actual portfolio ("You serve `{name}`, with these current assets: ...") — the Coach knows what YOU have, not what Maya has.
- **Dashboard greeting** uses the signed-in user's first name.

## Auth model
All data endpoints (`/api/dashboard`, `/api/portfolio`, `/api/finance`, `/api/goals`, `/api/content`, `/api/recommendations`, `/api/ai/chat*`, `/api/strategy/plans*`, `/api/onboarding/*`) require `Authorization: Bearer <token>` — 401 otherwise. Public endpoints: `/api/`, `/api/competitors/*`, `/api/integrations/*`, `/api/auth/session`.

## Chat scope
`session_id` is internally namespaced as `{user_id}::{session_id}` so two users using the same client-side session_id string never see each other's history.

## What's NOT in scope
- Real Stripe OAuth connect flow (still placeholder in step 3)
- Instagram Graph OAuth
- Editing/persistence of Strategy plan tasks (read-only for now)
- Light theme toggle, push notifications

## Smart business enhancement
The **starter dataset** is a deliberate acquisition play — new sign-ups get a fully-populated dashboard on day zero. That gives them dopamine before they've done any work, dramatically increasing D1/D7 retention vs the typical "empty state, please connect X integrations" onboarding used by every other SaaS in this category.

## Next steps reference
See `/app/docs/NEXT_STEPS.md` for the up-to-date backlog: live-data activation
requirements (YouTube/Instagram/PayPal/Stripe), payment gateway status, the
progress-tracking feature backlog (trend charts, goal ETA/pace, streaks,
weekly recap, milestone celebration), and other pending UI/onboarding/export
tasks. Check that file at the start of any new session before planning work.
