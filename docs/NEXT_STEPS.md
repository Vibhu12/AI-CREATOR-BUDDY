# CreatorOS — Next Steps Reference

This file is the single source of truth for **pending work** on CreatorOS.
Whenever starting a new session, check this file first for context before
planning new work.

Last updated: session covering APK login/AI-coach production bugfix +
progress-tracking feature discussion.

---

## 1. Activating Live Data (Real Integrations)

All backend code paths for these integrations already exist and gracefully
fall back to mock data when keys are missing (`"mocked": true|false` field
on every response tells you which mode is active). See
`/app/docs/API_KEYS_SETUP_GUIDE.md` for full step-by-step instructions for
YouTube, Instagram, and PayPal.

| Integration | What's needed | Where to get it | Effort | Status |
|---|---|---|---|---|
| **YouTube** | `YOUTUBE_API_KEY` (Google Cloud API key with YouTube Data API v3 enabled) | Google Cloud Console → free | Low — 5 min | Pre-wired, dormant (key empty) |
| **Instagram** | `INSTAGRAM_USER_ID` + `INSTAGRAM_LONG_LIVED_TOKEN` | Facebook Developer App + an Instagram Business/Creator account linked to a Facebook Page → generate long-lived token via Graph API | High — requires Meta App review for some permissions | Pre-wired, dormant (keys empty). **Limitation**: Graph API can only fetch the token-owner's own account — cannot look up arbitrary/competitor handles live. |
| **PayPal** | `PAYPAL_CLIENT_ID` + `PAYPAL_CLIENT_SECRET` | PayPal Developer Dashboard (sandbox is free/instant) | Low | Pre-wired end-to-end (create-order → hosted approval → capture), dormant (keys empty) |
| **Stripe** | Real `STRIPE_API_KEY` | Currently set to a placeholder (`sk_test_emergent`) — not a real working key. Real checkout/payment flow is **not implemented** yet (only balance/charges read-side supports a real key; the actual pay flow is 100% simulated via a mock `checkout.creatoros.mock` URL). | Needs real key + actual Stripe Checkout Session implementation | Read-side pre-wired; checkout flow needs real build-out |
| **Going fully live** | Set `DEMO_MODE=false` in `backend/.env` | — | Required so mock "confirm/capture" payment paths get disabled once real providers are wired | Currently `true` (demo) |

### Env vars quick reference (`/app/backend/.env`)
```
YOUTUBE_API_KEY=
INSTAGRAM_USER_ID=
INSTAGRAM_LONG_LIVED_TOKEN=
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
STRIPE_API_KEY=sk_test_emergent   # placeholder — replace with real key
DEMO_MODE=true                    # flip to false when going live
```

---

## 2. Payment Gateway Status

- **Frontend** (`/app/frontend/app/pricing.tsx`): Fully built — checkout modal,
  payment method picker (Stripe/PayPal), real PayPal browser-based approval
  flow (opens PayPal hosted page, captures return, confirms order). No
  frontend work needed here.
- **PayPal backend**: Real Orders v2 flow fully implemented
  (`create-order` → hosted approval → `capture`) — just needs real
  Client ID/Secret to switch from mock to live.
- **Stripe backend**: Only the *read side* (balance/charges) supports a real
  key. The actual **checkout/payment flow is currently 100% simulated** —
  needs real Stripe Checkout Session integration work before it can take
  real payments.

---

## 3. Progress-Tracking Feature Backlog (creator-usability improvements)

Discussed with user, not yet built — pick up next when user confirms:

1. **Trend charts** — visual graphs on Dashboard for revenue/followers/health
   score over time (7/30/90-day view), not just a single snapshot number.
2. **Goal ETA + pace indicator** — "on track" / "behind schedule" badge +
   predicted completion date on goal cards, based on recent progress velocity.
3. **Consistency streak tracker** — content posting streak counter surfaced
   on Dashboard (e.g. "6-week posting streak 🔥").
4. **Weekly "Recap" card** — auto-generated week-over-week summary card on
   Dashboard (biggest win, biggest change, goal progress made).
5. **Milestone celebration** — confetti/animation + shareable card when a
   goal hits 100% or a big revenue/follower milestone is crossed.

User was asked to pick one/more/all — awaiting confirmation before starting.

---

## 4. Other known backlog items (pre-existing, from earlier sessions)

- UI polish: pull-to-refresh + skeleton loaders across all tabs.
- Onboarding tour / product walkthrough for first-time users.
- PDF export for dashboard reports.
- Push notifications for goal milestones & AI insights (build only on
  explicit user request — do not suggest proactively).

---

## 5. Deployment notes (fixed this session, keep in mind)

- Root `/app/.gitignore` previously excluded `.env`/`.env.*`/`*.env`, which
  could strip required env vars (incl. `EMERGENT_LLM_KEY`) from production
  deploys. **Fixed** — those exclusion lines were removed. `.env` files ARE
  now tracked/deployed; do not re-add a blanket `.env` exclusion.
- Added `/app/frontend/app/auth.tsx` as the real screen for the
  `frontend://auth` Google-login deep link (previously caused an
  "Unmatched Route" error in production APK builds). Keep this file in sync
  if the auth redirect scheme ever changes.
- Any code fix requires the user to re-click **Publish** and regenerate the
  APK/IPA build for it to take effect on a real device — code changes alone
  don't update an already-installed build.
