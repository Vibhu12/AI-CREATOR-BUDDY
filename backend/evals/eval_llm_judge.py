"""Eval: LLM-as-judge quality scoring for the Strategy Planner.

`eval_groundedness.py` and `eval_scale_appropriateness.py` catch the two
concrete bugs we've actually hit (persona leakage, wildly-off-scale
targets) with cheap, deterministic structural checks. This file adds a
third, complementary layer: an independent LLM reads the *full* generated
plan next to the user's real portfolio and scores it on dimensions a
regex can't — is this advice actually specific and actionable, or generic
filler that happens to be grounded in the right numbers?

Judge model is intentionally NOT the same model that generates the plan
(Strategy Planner generates with Claude Sonnet 4.5; this judges with
GPT-5.4) — using a different model/provider as judge avoids the
well-known "grading its own homework" bias of self-evaluation.

Requires a live backend + real EMERGENT_LLM_KEY (see evals/README.md).
Non-deterministic by nature (LLM judging LLM output) — thresholds below
are intentionally lenient (>=3/5) to avoid flaky failures on borderline
scores; the point is to catch clearly bad output, not to nitpick a 4 vs a
5.
"""
from __future__ import annotations

import asyncio
import json
import os
import re

import httpx
import pytest
from emergentintegrations.llm.chat import LlmChat, UserMessage

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

JUDGE_SYSTEM = (
    "You are a skeptical, independent QA reviewer for an AI product. You did "
    "not generate the content you are reviewing — you are grading someone "
    "else's work, and your job is to catch problems, not to be agreeable. "
    "You will be shown a creator's real business portfolio and a 30-day "
    "strategy plan an AI generated for them. Score the plan honestly.\n\n"
    "Respond with ONLY a valid JSON object, no markdown fences, no prose "
    "outside the JSON:\n"
    "{\n"
    '  "groundedness": <1-5 int>,   // does it reference THIS user\'s real numbers/assets, not generic advice?\n'
    '  "actionability": <1-5 int>,  // are tasks specific and doable this week, not vague ("grow your audience")?\n'
    '  "scale_fit": <1-5 int>,      // are targets proportionate to their actual current revenue?\n'
    '  "verdict": "pass" | "fail",\n'
    '  "rationale": "<one sentence, the single biggest reason for your score>"\n'
    "}"
)


def _generate_plan(token: str) -> dict:
    r = httpx.post(
        f"{BASE}/api/strategy/plans",
        headers={"Authorization": f"Bearer {token}"},
        json={"horizon_days": 30},
        timeout=60,
    )
    assert r.status_code == 200, f"plan generation failed: {r.status_code} {r.text[:300]}"
    return r.json()


async def _judge_async(portfolio_desc: str, plan: dict) -> dict:
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id="eval-judge",
        system_message=JUDGE_SYSTEM,
    ).with_model("openai", "gpt-5.4")

    prompt = (
        f"User's real portfolio:\n{portfolio_desc}\n\n"
        f"Generated 30-day plan:\n{json.dumps(plan, indent=2)}\n\n"
        "Score it."
    )
    reply = await chat.send_message(UserMessage(text=prompt))
    text = reply if isinstance(reply, str) else getattr(reply, "text", str(reply))
    match = re.search(r"\{.*\}", text, re.DOTALL)
    assert match, f"Judge did not return parseable JSON: {text[:300]}"
    return json.loads(match.group(0))


def _judge(portfolio_desc: str, plan: dict) -> dict:
    """Sync wrapper — the rest of this eval suite (and ../tests/) is
    synchronous, so we avoid pulling in pytest-asyncio for one async call."""
    return asyncio.run(_judge_async(portfolio_desc, plan))


@pytest.mark.eval
@pytest.mark.parametrize("key,portfolio_desc", [
    ("lo", "Priya Solo — 1 asset: 'Weekend Notes' newsletter, 640 subscribers, $480 MTD revenue."),
    ("hi", "Jordan Scale — 2 assets: YouTube channel (2.4M subs, $142k MTD) + 'Scale Systems' cohort course ($68k MTD)."),
])
def test_llm_judge_scores_plan_acceptable(eval_users, key, portfolio_desc):
    if not EMERGENT_LLM_KEY:
        pytest.skip("EMERGENT_LLM_KEY not set — cannot run LLM-as-judge eval")

    plan = _generate_plan(eval_users[key]["token"])
    verdict = _judge(portfolio_desc, plan)

    for dim in ("groundedness", "actionability", "scale_fit"):
        score = verdict.get(dim)
        assert isinstance(score, int) and 1 <= score <= 5, f"Judge returned invalid '{dim}': {verdict}"
        assert score >= 3, (
            f"Judge scored '{dim}'={score}/5 for eval user '{key}' (below the >=3 floor). "
            f"Rationale: {verdict.get('rationale')!r}. Full plan: {json.dumps(plan)[:500]}"
        )
    assert verdict.get("verdict") == "pass", (
        f"Judge marked plan as FAIL for eval user '{key}'. Rationale: {verdict.get('rationale')!r}"
    )
