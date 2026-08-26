# CreatorOS — Build Log

Real iteration-by-iteration history from the `testing_agent` reports
generated during the build of CreatorOS (raw JSON reports live in
`/app/test_reports/iteration_*.json` — this file is the human-readable
index).

| Iter | Backend result | Frontend result | Highlight |
|---|---|---|---|
| 1 | 100% (10/10) | 100% (5/5 tabs) | First testing pass on the MVP — dashboard, portfolio, all core tabs render and populate from the API. |
| 2 | 100% (15/15) | 70% | Auth session/me/logout, competitors, Stripe status, YouTube 503 fallback, Strategy via Claude. Found: `/competitors` red-screen + broken quick-action nav. |
| 3 | 100% (25/25) | 100% | Full regression — all green after fixing iter-2 nav bugs. |
| 4 | 100% (26/26) | 100% | v3: per-user data isolation + onboarding wizard. 14 protected endpoints correctly 401 without auth. |
| 5 | 100% (16/16) | 100% | v4: editable Strategy tasks, Pricing tiers + mock Stripe upgrade, Instagram capture in onboarding. |
| 6 | 100% (13/13) | 100% | v5: notification bell + mark-read/mark-all, Add Asset modal creating real assets via POST. |
| 7 | 100% (9/9) | 60% (partial) | v6: reseed + expanded starter data. Found: Add Asset modal missing 2 chips, Dashboard showing wrong recs. |
| 8 | 100% (12/12) | 100% | v7 retest — both iter-7 bugs fixed and verified on mobile viewport. |
| 9 | 100% (11/11) | not tested (backend-only scope) | v8: auto-seed on first `/api/dashboard` / `/api/portfolio` hit for zero-row users. |
| 10 | 100% (28/28) | 100% (22/22 UI checks) | Full customer-perspective E2E audit across 8 screens — no critical bugs found. |
| 11 | 100% (25/25) | 100% (17/17) | New Connections Hub (`/api/integrations/*`) + Stripe/PayPal checkout modal. |
| 12 | 80% (12/15) | N/A (scope) | Real PayPal Orders v2 client — 3 failures traced to one root cause (missing `order_id` in mock-fallback persistence), fixed same iteration. |
| 13 | 100% (65/65) | N/A (backend-only) | **Security pass** — SEC-001 (mock-payment tier flip gating) and SEC-002 (free-tier quotas + burst rate limits) verified. |
| 14 | 100% (87/87) | 100% smoke | Goals CRUD, Asset detail, Finance revenue-mix + 90-day forecast, AddAssetModal validation UX. |
| 15 | 100% (87/87) | N/A | Engineering documentation set (HLD/LLD/User-Journey/Metrics) generated and verified readable in all 4 formats. |
| 16 | 100% (100/100) | N/A | Full security-audit re-verification — SEC-001/002 fixes confirmed still holding after further changes. |
| 17 | 100% (7/7 AI Coach suite) | 100% | Fixed AI Coach `401` streaming auth bug (missing Bearer header on raw SSE `fetch`). |
| 18 | 100% (107/107) | 100% | Fixed 2 production APK bugs: `frontend://auth` deep-link "Unmatched Route" screen, and a `.gitignore` misconfiguration that could strip `.env` (incl. the LLM key) from production deploys. |

## Notable regressions caught & fixed

- **Iter 7 → 8**: Add Asset modal missing category chips + Dashboard showing stale recommendations — both found and fixed within the same iteration pair.
- **Iter 12**: PayPal mock-fallback order persistence bug (missing `order_id` field) — root-caused to a single line, fixed, re-verified 100% same session.
- **Post-iter-18** (this session, not yet a numbered iteration): Strategy Planner was found to hardcode the demo "Maya" persona into its system prompt for every user regardless of who was signed in or what their real portfolio looked like — passed every schema/functional test because the JSON was always valid, just about the wrong business. Fixed in `backend/strategy.py` (`_build_strategy_context`), and covered going forward by `backend/evals/eval_groundedness.py`.

## Running the full backend suite yourself

```bash
cd backend
export EXPO_PUBLIC_BACKEND_URL=<your backend URL>
pytest tests/ -v        # 107 tests, deterministic, no LLM cost
pytest evals/ -v -s     # AI-output quality checks, real LLM calls, run on-demand
```
