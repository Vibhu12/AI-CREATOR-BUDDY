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
