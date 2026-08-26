"""Eval: Strategy Planner groundedness.

Fails if the Strategy Engine returns a plan that either:
  (a) leaks the old hardcoded demo persona ("Maya", her subscriber count,
      her course name) instead of the actual signed-in user's data, or
  (b) returns effectively the same plan for two users with very different
      businesses — a sign the model isn't actually conditioning on the
      per-user context block built in `strategy.py::_build_strategy_context`.

Requires a live backend + real EMERGENT_LLM_KEY (see evals/README.md).
"""
from __future__ import annotations

import os

import httpx
import pytest

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")

# Strings that must NEVER appear in a generated plan — they're fingerprints
# of the old hardcoded "Maya" demo persona that used to leak into every
# user's Strategy Plan regardless of who was actually logged in.
_PERSONA_LEAK_MARKERS = ("Maya", "184k", "184,000", "Ship It", "22.8k")


def _generate_plan(token: str, horizon_days: int = 30) -> dict:
    r = httpx.post(
        f"{BASE}/api/strategy/plans",
        headers={"Authorization": f"Bearer {token}"},
        json={"horizon_days": horizon_days},
        timeout=60,
    )
    assert r.status_code == 200, f"plan generation failed: {r.status_code} {r.text[:300]}"
    return r.json()


def _plan_text(plan: dict) -> str:
    """Flatten the plan into one big string for substring/marker checks."""
    parts = [plan.get("title", ""), plan.get("summary", "")]
    ns = plan.get("north_star") or {}
    parts += [ns.get("metric", ""), ns.get("target", "")]
    for kpi in plan.get("kpis") or []:
        parts += [kpi.get("label", ""), kpi.get("target", "")]
    for ph in plan.get("phases") or []:
        parts += [ph.get("theme", ""), ph.get("risk", "")]
        parts += ph.get("milestones") or []
        parts += ph.get("weekly_tasks") or []
    parts += plan.get("leading_indicators") or []
    return " \n ".join(str(p) for p in parts)


@pytest.mark.eval
def test_no_hardcoded_persona_leak(eval_users):
    """Neither user's plan should mention the old fixed demo persona."""
    for key in ("lo", "hi"):
        plan = _generate_plan(eval_users[key]["token"])
        text = _plan_text(plan)
        for marker in _PERSONA_LEAK_MARKERS:
            assert marker not in text, (
                f"Plan for eval user '{key}' leaked hardcoded persona marker "
                f"'{marker}' — Strategy Engine is not grounding on the real user. "
                f"Plan text: {text[:500]}"
            )


@pytest.mark.eval
def test_plans_differ_across_distinct_users(eval_users):
    """A $480/mo solo newsletter and a $210k/mo multi-asset creator should
    not receive byte-identical (or near-identical) plans."""
    plan_lo = _generate_plan(eval_users["lo"]["token"])
    plan_hi = _generate_plan(eval_users["hi"]["token"])

    assert plan_lo.get("summary") != plan_hi.get("summary"), (
        "Both users received the identical plan summary — model is not "
        "conditioning on per-user portfolio context."
    )
    ns_lo = (plan_lo.get("north_star") or {}).get("target", "")
    ns_hi = (plan_hi.get("north_star") or {}).get("target", "")
    assert ns_lo != ns_hi, "Both users received the identical north_star target."
