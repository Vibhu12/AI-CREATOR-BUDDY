"""Eval: Strategy Planner scale-appropriateness.

Fails if the model proposes dollar targets wildly out of proportion to the
signed-in user's actual current revenue — a heuristic guard against the
class of bug where a big-creator-sized plan gets handed to a tiny creator
(or vice versa), which is exactly what happened when the persona was
hardcoded (every user got Maya's ~$56k/mo numbers regardless of their own).

This is intentionally a coarse order-of-magnitude check, not a precise
financial model — see evals/README.md "Known limitations".
"""
from __future__ import annotations

import os
import re

import httpx
import pytest

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")

_DOLLAR_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)([kKmM])?(?![a-zA-Z])")


def _parse_dollar_amounts(text: str) -> list[float]:
    out = []
    for num, suffix in _DOLLAR_RE.findall(text):
        val = float(num.replace(",", ""))
        if suffix.lower() == "k":
            val *= 1_000
        elif suffix.lower() == "m":
            val *= 1_000_000
        out.append(val)
    return out


def _generate_plan(token: str) -> dict:
    r = httpx.post(
        f"{BASE}/api/strategy/plans",
        headers={"Authorization": f"Bearer {token}"},
        json={"horizon_days": 30},
        timeout=60,
    )
    assert r.status_code == 200, f"plan generation failed: {r.status_code} {r.text[:300]}"
    return r.json()


@pytest.mark.eval
@pytest.mark.parametrize("key,current_revenue,max_multiple", [
    ("lo", 480.0, 100),      # tiny creator — target shouldn't imply a 100x+ overnight jump
    ("hi", 210_000.0, 20),   # large creator — target shouldn't imply a >20x overnight jump
])
def test_north_star_target_within_sane_multiple(eval_users, key, current_revenue, max_multiple):
    plan = _generate_plan(eval_users[key]["token"])
    ns = plan.get("north_star") or {}
    target_text = f"{ns.get('metric', '')} {ns.get('target', '')}"

    amounts = _parse_dollar_amounts(target_text)
    if not amounts:
        pytest.skip(f"north_star for '{key}' isn't a dollar-denominated metric — nothing to check")

    biggest = max(amounts)
    ratio = biggest / current_revenue
    assert ratio <= max_multiple, (
        f"north_star target for eval user '{key}' (${biggest:,.0f}) is {ratio:.1f}x their "
        f"current ${current_revenue:,.0f} MTD revenue — exceeds the {max_multiple}x sanity bound. "
        f"Full target text: {target_text!r}"
    )
