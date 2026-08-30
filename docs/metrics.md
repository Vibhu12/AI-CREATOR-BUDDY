# CreatorOS — Metrics Framework

How we know if CreatorOS is actually working, not just being used.

## North Star: Weekly Active Decisions

**Not Weekly Active Users.** A user who opens the dashboard, glances at a
number, and closes the app got nothing from the product — they were
active, but nothing changed as a result.

**Definition:** a user who, in a given week, does at least one of:
- completes a Strategy Plan task
- updates or completes a goal
- actions a recommendation (accepts, dismisses-with-reason, or acts on it)

**Why this is the right north star, not DAU/WAU:**
- It's proximate to *value delivered*, not to *engagement*. Someone
  chatting with the AI Coach for twenty minutes without ever acting on
  anything moved zero business metrics — WAU would count that as a great
  week; Weekly Active Decisions would not.
- It can't be gamed by making the app more addictive. Notification
  nudges, infinite scroll, streak guilt — none of that moves this number
  unless it also produces an actual decision. That's deliberate: optimizing
  for this metric optimizes for the user's business outcomes, not for
  session count.
- It survives the obvious interview follow-up ("why not DAU?"): DAU
  measures whether people show up. Weekly Active Decisions measures
  whether showing up did anything for them. For an operator tool, the
  second one is the actual product.

## Input Metrics

These are the metrics that move the north star — the levers, not the
scoreboard.

| Metric | Definition | Why it matters |
|---|---|---|
| Time to first insight | Signup → first recommendation viewed | The activation moment. If this is slow, everything downstream is slower. |
| Portfolio completeness | % of users with 2+ assets connected | A single-asset user gets a fraction of the product's value — there's no "portfolio" to manage, no cross-asset insight to generate. |
| Coach message depth | Median messages per session | One message is a lookup ("what's my MRR"). Five is a conversation the user is actually working through a problem in. |
| Plan task completion rate | % of weekly tasks marked done inside their phase window | The single best proxy for whether the AI's advice is *actionable*, not just plausible-sounding. |
| Recommendation action rate | % of shown recommendations actioned | A direct quality signal on the recommendation engine itself — low action rate means the recs are wrong or badly timed, not that users are lazy. |

## Guardrails

Metrics that don't move — if they slip, something is broken even if the
north star looks fine.

| Metric | Threshold |
|---|---|
| Coach p95 time to first token | Under 2s |
| Strategy generation schema validity | Above 98% |
| Eval groundedness pass rate (`backend/evals/`) | Above 95% |
| Free-tier quota hit rate | Between 15% and 40% of weekly actives |

**The quota hit rate is the sharpest line in this doc, and it's a
two-sided target, not a number to maximize.**

- **Too low (<15%):** almost nobody is hitting the free-tier ceiling,
  which means the paywall has no teeth — there's no conversion pressure,
  and the free tier is effectively the whole product for most people.
- **Too high (>40%):** most people are hitting the wall, which means
  we're throttling before users have felt enough value to want to pay —
  we're bleeding people out at activation, not converting engaged users.
- **The healthy band (15–40%)** means the limit binds specifically for
  users who are already engaged enough to want more, and stays invisible
  to everyone still deciding if the product is for them. That's the only
  version of a quota that's doing its job.

Treating a quota as a *band to hold*, not a *number to push in one
direction*, is the difference between reasoning about a paywall as a
product mechanism versus a knob to crank.

## Counter-Metrics

Metrics we watch specifically because the input metrics above can be
individually "improved" in ways that make the product worse.

1. **Plans generated per user rising while task completion rate falls.**
   This means people are *regenerating* plans instead of *executing* them
   — a sign the plans themselves aren't good enough to act on, and
   "engagement" with the Strategy Planner is masking a quality problem,
   not reflecting a happy user.

2. **Coach messages up while recommendation action rate stays flat.**
   This means people are *chatting* instead of *deciding* — high AI Coach
   engagement can look like a healthy metric while actually being a sign
   that conversation is substituting for action, not leading to it.

Both of these exist so that no single input metric can be improved in
isolation without the dashboard also showing whether it came at the cost
of the thing that actually matters (Weekly Active Decisions).

## Instrumentation status

The events needed to compute the metrics above are already wired via the
analytics allowlist in `backend/analytics.py`: `quota_hit`,
`upgrade_cta_shown`, `upgrade_cta_tapped`, `checkout_started`,
`checkout_completed`, `strategy_task_completed`, `goal_updated`,
`goal_completed`, `recommendation_shown`, `recommendation_actioned`,
`ai_chat_message_sent`. Weekly Active Decisions and the input metrics
above are computable today from `db.analytics_events` — none of this
requires new instrumentation, only a dashboard/query layer on top of data
already being collected.

**Note on the eval groundedness guardrail:** an LLM-as-judge eval
(`backend/evals/eval_llm_judge.py`) now exists and runs on demand. It
surfaced a real, recurring issue — the Strategy Planner inventing
precise-sounding but unsupported statistics — that three rounds of prompt
tightening improved substantially but did not fully close: measured
across 6 repeated runs, simple single-asset portfolios now pass ~100% of
the time, while complex multi-asset high-revenue portfolios still pass
only ~33% of the time (recurring cause: derived unit-economics math with
no real basis). The 95% threshold above is a target to build toward, not
a number currently being hit uniformly across portfolio complexity; see
`backend/evals/README.md` for the full breakdown.
