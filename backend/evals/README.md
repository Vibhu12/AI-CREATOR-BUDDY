# CreatorOS — Eval Suite

This folder is **separate from `../tests/`** on purpose.

- `../tests/` checks *correctness*: does the endpoint return the right
  status code, the right shape, enforce auth/quotas correctly? These are
  deterministic and always pass/fail the same way.
- `evals/` checks *quality* of the AI-generated output itself: is the
  Strategy Plan / AI Coach response actually **grounded** in the signed-in
  user's real data, and are its numeric targets **scale-appropriate** for
  that user's business — not just "is it valid JSON".

## Why this exists

During iteration 17-18, the Strategy Engine passed every functional test
(valid JSON, correct schema, 200 status) while silently generating every
user's 30/60/90 day plan around a hardcoded demo persona ("Maya", 184k
YouTube subs, $56k MTD) regardless of who was actually logged in or what
their real portfolio looked like. Schema tests could not catch this because
the output was syntactically perfect — it was just talking about the wrong
business. That bug is now fixed in `backend/strategy.py`
(`_build_strategy_context`), and these evals exist so a regression like it
can't silently ship again.

## What's covered (minimal, real, extendable)

| File | Checks |
|---|---|
| `eval_groundedness.py` | Generates a Strategy Plan for two synthetic users with **distinct** portfolios and asserts: (1) neither plan leaks the old hardcoded "Maya" persona details, (2) each plan's `summary`/`north_star` text is not byte-identical between the two users — i.e. the model is actually conditioning on per-user context, not returning a cached/generic answer. |
| `eval_scale_appropriateness.py` | Extracts the `$` figures the model proposes in `north_star.target` / `kpis[].target` and asserts they sit within a sane multiple of the user's *actual* current MTD revenue (catches the class of bug where a $500/mo creator gets handed a plan sized for a $500k/mo business, or vice versa). |
| `eval_llm_judge.py` | **LLM-as-judge.** An independent model (GPT-5.4 — deliberately *not* the same model that generates the plan, Claude Sonnet 4.5, to avoid self-grading bias) reads the full plan next to the user's real portfolio and scores groundedness/actionability/scale-fit + an overall pass/fail verdict. Catches semantic quality issues structural checks can't — see "A real finding" below. |
| `conftest.py` | Seeds two throwaway eval users directly in MongoDB (mirrors `../tests/conftest.py`'s audit-user pattern) with deliberately different revenue scales, and tears them down after the run. |

## A real finding from `eval_llm_judge.py` (not yet fully resolved)

Running the judge surfaced a genuine, recurring quality issue: the Strategy
Planner tends to invent precise-sounding but unsupported numbers — e.g. "a
6.5% conversion rate," "260 new subscribers," "launch a paid tier" — stated
as fact rather than as a labelled estimate, regardless of scale. Two rounds
of prompt tightening in `strategy.py` (explicitly asking for realistic,
scale-appropriate assumptions, then explicitly forbidding invented precise
statistics) measurably changed *which* user's plan failed but did not
eliminate the pattern — this looks like a persistent LLM tendency toward
confident-sounding specificity rather than something a bigger prompt fully
solves.

**Deliberately not force-passed.** Lowering the judge's threshold to make
the test green would defeat the point of having it. This is left as an
honest, open finding. Real next steps if picked up: (a) a second
self-critique LLM pass that specifically checks the first draft for invented
statistics before returning it to the user, or (b) changing the UI/schema to
require the model to label estimates as ranges ("~5-8%") rather than single
precise figures, which is both more honest and probably easier for the model
to satisfy than "don't guess."

## Running

Requires a live backend (`sudo supervisorctl status backend`) and a valid
`EMERGENT_LLM_KEY` in `backend/.env` (these evals make real LLM calls —
Claude Sonnet 4.5 to generate the plan, GPT-5.4 to judge it — they are not
free, and not deterministic, which is why they live outside the main
pytest gate and are run on-demand rather than in every CI run).

```bash
cd backend
export EXPO_PUBLIC_BACKEND_URL=$(grep EXPO_PUBLIC_BACKEND_URL ../frontend/.env | cut -d= -f2-)
pytest evals/ -v -s
```

## Known limitations / future work

This is intentionally a **minimal starter**, not a full eval harness:

- Only covers Strategy Planner; AI Coach chat groundedness (does the coach's
  streamed answer actually reference the user's real numbers) is not yet
  covered by an automated eval, only by manual QA.
- Scale-appropriateness bounds are heuristic (a fixed multiple range), not
  learned from real creator revenue distributions.
- The LLM-as-judge eval (`eval_llm_judge.py`) is a single judge call per
  run, not an average over many samples — a genuinely borderline plan can
  flip pass/fail between runs. Treat a single failure as a signal to look
  closer, not as proof of a regression; treat a *pattern* of failures
  across several runs as one.

Next person picking this up: start by adding an AI Coach groundedness eval
(same pattern as `eval_groundedness.py`, pointed at `POST /api/ai/chat`),
and consider tackling the invented-statistics finding above (self-critique
pass or range-based estimates) before adding more judge dimensions.
