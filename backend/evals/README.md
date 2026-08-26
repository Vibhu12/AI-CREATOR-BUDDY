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
| `conftest.py` | Seeds two throwaway eval users directly in MongoDB (mirrors `../tests/conftest.py`'s audit-user pattern) with deliberately different revenue scales, and tears them down after the run. |

## Running

Requires a live backend (`sudo supervisorctl status backend`) and a valid
`EMERGENT_LLM_KEY` in `backend/.env` (these evals make real Claude calls —
they are not free, and not deterministic, which is why they live outside
the main pytest gate and are run on-demand rather than in every CI run).

```bash
cd backend
export EXPO_PUBLIC_BACKEND_URL=$(grep EXPO_PUBLIC_BACKEND_URL ../frontend/.env | cut -d= -f2-)
pytest evals/ -v -s
```

## Known limitations / future work

This is intentionally a **minimal starter**, not a full eval harness:

- No LLM-as-judge scoring yet — checks are structural/regex-based, not
  semantic quality scoring.
- No historical tracking of eval scores over time / no regression
  dashboard.
- Only covers Strategy Planner; AI Coach chat groundedness (does the coach's
  streamed answer actually reference the user's real numbers) is not yet
  covered by an automated eval, only by manual QA.
- Scale-appropriateness bounds are heuristic (a fixed multiple range), not
  learned from real creator revenue distributions.

Next person picking this up: start by adding an AI Coach groundedness eval
(same pattern as `eval_groundedness.py`, pointed at `POST /api/ai/chat`),
and consider adding an LLM-as-judge pass for qualitative scoring.
