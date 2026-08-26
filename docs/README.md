# CreatorOS — Documentation Index

Comprehensive engineering documentation for **CreatorOS**, the mobile-first
business operating system for creators and digital entrepreneurs.

Generated June 2026 · Reflects code state as of iteration 14.

---

## 📚 Contents

| # | Document                        | Audience                                | Read-time |
|---|---------------------------------|-----------------------------------------|-----------|
| 1 | [`01_HLD.md`](./01_HLD.md)     | Eng leads, new hires, execs             | 8 min     |
| 2 | [`02_LLD.md`](./02_LLD.md)     | Engineers implementing / reviewing code | 20 min    |
| 3 | [`03_USER_JOURNEY.md`](./03_USER_JOURNEY.md) | PMs, designers, QA, support | 15 min    |
| 4 | [`04_METRICS_AND_AB.md`](./04_METRICS_AND_AB.md) | Growth, analytics, engineering leads | 12 min    |

---

## 🧭 What each document covers

### 1. High-Level Design (HLD)
- System context & architecture diagram
- Tech stack rationale
- Component overview (frontend + backend + DB collections)
- Cross-cutting concerns: auth, streaming, quotas, payments
- Non-functional requirements & SLOs
- Deployment topology & environments
- Known trade-offs

### 2. Low-Level Design (LLD)
- Directory layout
- Every backend module with signatures, params, algorithms
- Full REST API reference — every endpoint, params, error codes
- MongoDB schema per collection with example documents
- Frontend module reference — Auth, API service, state models
- Design tokens (colors, spacing, formatters)
- Third-party integration wire-flows (PayPal Orders v2, YouTube v3, Claude Sonnet 4.5)
- Security controls table
- Testing surfaces & counts

### 3. End-to-End User Journey
- Primary persona (Maya)
- Every screen walkthrough (Login → Onboarding → Dashboard → Portfolio →
  Coach → Strategy → Integrations → Pricing → Goals → Assets → Profile)
- Edge-case matrix per flow
- Global edge cases (auth, network, LLM, payments, deep links, time zones)
- Instrumentation hooks

### 4. Evaluation Metrics & A/B Testing
- North-Star Metric definition (Weekly Actioned Insights)
- Full KPI tree with Q3 2026 targets
- Complete event taxonomy (30+ events with props)
- A/B testing framework: assignment, sample size, guardrails
- 6 reference experiments ready to run
- AI-specific offline & online eval strategy
- Financial / business metrics
- Data governance & privacy
- Runbooks

---

## 🔗 Related resources

- `/app/memory/PRD.md` — Original Product Requirements Document
- `/app/docs/NEXT_STEPS.md` — Live backlog: integration activation, payment gateway status, feature roadmap
- `/app/docs/build-log/README.md` — Human-readable iteration-by-iteration build history (18 iterations)
- `/app/memory/test_credentials.md` — Test-user credentials
- `/app/test_reports/iteration_*.json` — Historical test agent reports (raw)
- `/app/backend/tests/` — Backend pytest suites (107 tests, 100% pass)
- `/app/backend/evals/` — AI-output quality evals (groundedness + scale-appropriateness), run on-demand

## 🔧 Local links

- Backend health: `http://localhost:8001/api/`
- Metro dev server: `http://localhost:3000`
- Expo QR code: shown in `sudo supervisorctl tail -f expo`

## 📝 Change log

| Iter | Date       | Highlight                                                 |
|------|------------|-----------------------------------------------------------|
| 10   | 2026-06-14 | MVP E2E audit — no critical bugs found                    |
| 11   | 2026-06-14 | Connections Hub — YouTube/Instagram/Stripe/PayPal mocks   |
| 12   | 2026-06-15 | Real PayPal Orders v2 client (dormant until keys added)   |
| 13   | 2026-06-15 | SEC-001 & SEC-002 fixes: DEMO_MODE gate, quotas, rate limit |
| 14   | 2026-06-15 | Goal Tracking screen, Asset detail, Finance breakdown; on_event→lifespan; test cleanup |
| 15   | 2026-06-15 | HLD/LLD/User-Journey/Metrics documentation set (this file)|

---

## Getting started (as a new engineer)

1. Skim `01_HLD.md` end-to-end.
2. Read `02_LLD.md` §3 (REST API reference) — bookmark it.
3. Trace one full flow through `03_USER_JOURNEY.md` (recommend: Checkout).
4. Run `cd /app/backend && pytest tests/ -v` — should be 87/87 green.
5. Load the app on Expo Go; use the audit-token in `test_credentials.md` to
   log in without OAuth.
6. Ship something small (a copy tweak or new event) and open a PR.
