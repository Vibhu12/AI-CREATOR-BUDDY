"""Strategy Planner — AI-generated 30/60/90 day plans backed by MongoDB.

Endpoints:
  GET  /strategy/plans          → list latest plans
  POST /strategy/plans          → generate new plan via Claude Sonnet 4.5
  GET  /strategy/plans/{id}     → fetch by id
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage, StreamDone, TextDelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from quotas import enforce_strategy_plan

log = logging.getLogger("creatoros.strategy")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class StrategyRequest(BaseModel):
    horizon_days: int = 90  # 30, 60, or 90
    focus: Optional[str] = None  # optional user-provided goal


class TaskToggle(BaseModel):
    phase_index: int
    kind: str  # "milestones" | "weekly_tasks" | "leading_indicators"
    task_index: int
    checked: bool


STRATEGY_SCHEMA = (
    "You are CreatorOS Strategy Engine. You generate operator-grade roadmaps for a creator's business. "
    "Always respond with a single VALID JSON object — no prose, no markdown fences. "
    "Schema strictly:\n"
    "{\n"
    '  "title": str,\n'
    '  "summary": str (one sentence, <= 25 words),\n'
    '  "horizon_days": int,\n'
    '  "north_star": {"metric": str, "target": str — a RANGE for any projected/estimated figure '
    '(e.g. "$650-750/mo"), never a single invented precise number},\n'
    '  "kpis": [{"label": str, "target": str — ranges for projected/estimated figures '
    '(e.g. "5-8%", "150-250 subs"), not single invented figures}] (3-5 items),\n'
    '  "phases": [\n'
    '    {"window": "Days 1-30", "theme": str, "milestones": [str, str, str], '
    '"weekly_tasks": [str, str, str, str], "risk": str}\n'
    "  ] (one phase per 30-day block, sized to horizon_days),\n"
    '  "leading_indicators": [str, str, str]\n'
    "}\n"
    "Hard rule on numbers: any figure in this plan is either (a) a fact directly derivable from the "
    "user's real portfolio data given below, or (b) a projection, which MUST be expressed as a range "
    "(\"5-8%\", \"$1.2k-1.8k\") — never as a single precise-looking number like \"6.5%\" or \"$1,450\". "
    "A single exact figure implies false certainty you don't have; a range is the honest way to say "
    "'this is my estimate, not a measurement.'"
)

STRATEGY_CONTEXT_TEMPLATE = (
    "Context — the user is {name}, with these current business assets:\n{portfolio}\n"
    "Total revenue MTD: ${revenue:,.0f}. Profit MTD: ${profit:,.0f} (~{margin:.0f}% margin).\n"
    "Be specific. Quantify targets using THIS user's real numbers above — never invent a different "
    "business. Targets must scale proportionately to their current revenue (e.g. do not suggest a "
    "$56k/mo creator's roadmap for someone at $500/mo, or vice versa). Tie each phase to a measurable outcome. "
    "Ground every quantitative assumption (conversion rates, content output cadence, audience growth) in what "
    "this specific business could realistically sustain in 30 days given its current scale and team size of one "
    "— do not imply a content cadence or conversion rate far outside what a solo/small operator their size can "
    "actually execute, even if the resulting numbers look impressive. "
    "Do not invent precise-sounding statistics you have no basis for (e.g. a specific conversion percentage or "
    "subscriber delta stated as fact) — express any such estimate as a range per the hard rule above, not a "
    "single invented figure. Only reference metric TYPES that appear in the portfolio data above (revenue, "
    "profit, followers) or are a direct, named property of one of the user's listed assets — do not introduce "
    "new metric types the user's portfolio doesn't track (e.g. RPM, CPM, AOV, email list size) as if they were "
    "known figures; if a tactic genuinely needs one of those, name it as something the user should go measure, "
    "not as a number you're asserting."
)


def _demo_filter(user: dict) -> dict:
    """Mirrors server.py's `demo_filter()` — kept local to avoid a
    cross-module import between independent router modules."""
    if user.get("demo_mode", True):
        return {}
    return {"is_demo": {"$ne": True}}


async def _build_strategy_context(db, user: dict) -> str:
    """Builds a per-user context block for the Strategy Engine — mirrors the
    AI Coach's `_build_system_prompt` in server.py so plans are grounded in
    THIS user's real portfolio, not a fixed demo persona."""
    assets = await db.assets.find({"user_id": user["user_id"], **_demo_filter(user)}, {"_id": 0}).to_list(100)
    if not assets:
        portfolio = "  (no assets yet — recommend how to launch the first one)"
    else:
        portfolio = "\n".join(
            f"  - {a.get('name', 'Untitled')} ({a.get('platform', 'unknown')}) — "
            f"{a.get('followers', 0):,} followers, ${a.get('revenue_mtd', 0):,.0f} MTD"
            for a in assets
        )
    rev = sum(a.get("revenue_mtd", 0) for a in assets)
    prof = sum(a.get("profit_mtd", 0) for a in assets)
    margin = (prof / rev * 100) if rev else 0
    return STRATEGY_SCHEMA + STRATEGY_CONTEXT_TEMPLATE.format(
        name=user.get("name", "the creator"),
        portfolio=portfolio,
        revenue=rev,
        profit=prof,
        margin=margin,
    )


def make_strategy_router(db, api_key: str, current_user):
    router = APIRouter(prefix="/strategy", tags=["strategy"])

    @router.get("/plans")
    async def list_plans(user: dict = Depends(current_user)):
        plans = await db.strategy_plans.find(
            {"user_id": user["user_id"], **_demo_filter(user)}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        return {"items": plans}

    @router.get("/plans/{plan_id}")
    async def get_plan(plan_id: str, user: dict = Depends(current_user)):
        plan = await db.strategy_plans.find_one(
            {"id": plan_id, "user_id": user["user_id"], **_demo_filter(user)}, {"_id": 0}
        )
        if not plan:
            raise HTTPException(404, "plan not found")
        return plan

    @router.post("/plans")
    async def generate(req: StrategyRequest, user: dict = Depends(current_user)):
        if req.horizon_days not in (30, 60, 90):
            raise HTTPException(400, "horizon_days must be 30, 60, or 90")
        if not api_key:
            raise HTTPException(500, "AI not configured")

        # SEC: enforce free-tier weekly plan limit + burst rate limit
        await enforce_strategy_plan(db, user)

        if req.focus and len(req.focus) > 500:
            raise HTTPException(413, "focus too long (max 500 chars)")

        user_prompt = (
            f"Generate a {req.horizon_days}-day strategic roadmap. "
            + (f"User priority: {req.focus}. " if req.focus else "")
            + "Return JSON only matching the schema."
        )

        system_prompt = await _build_strategy_context(db, user)
        chat = LlmChat(
            api_key=api_key,
            session_id=f"strategy-{uuid.uuid4().hex[:8]}",
            system_message=system_prompt,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        chunks: list[str] = []
        async for ev in chat.stream_message(UserMessage(text=user_prompt)):
            if isinstance(ev, TextDelta):
                chunks.append(ev.content)
            elif isinstance(ev, StreamDone):
                break
        raw = "".join(chunks).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        try:
            data = json.loads(raw)
        except Exception as e:
            log.warning("strategy json parse failed: %s | raw=%s", e, raw[:300])
            raise HTTPException(502, "AI returned unparseable plan; retry")

        plan = {
            "id": str(uuid.uuid4()),
            "user_id": user["user_id"],
            "horizon_days": req.horizon_days,
            "focus": req.focus,
            "created_at": now_utc().isoformat(),
            "task_progress": {},
            **data,
        }
        await db.strategy_plans.insert_one({**plan})
        return await db.strategy_plans.find_one(
            {"id": plan["id"], "user_id": user["user_id"]}, {"_id": 0}
        )

    @router.patch("/plans/{plan_id}/task")
    async def toggle_task(plan_id: str, payload: TaskToggle, user: dict = Depends(current_user)):
        if payload.kind not in ("milestones", "weekly_tasks", "leading_indicators"):
            raise HTTPException(400, "invalid kind")
        plan = await db.strategy_plans.find_one(
            {"id": plan_id, "user_id": user["user_id"], **_demo_filter(user)}, {"_id": 0}
        )
        if not plan:
            raise HTTPException(404, "plan not found")
        key = f"{payload.phase_index}.{payload.kind}.{payload.task_index}"
        progress = plan.get("task_progress") or {}
        if payload.checked:
            progress[key] = True
        else:
            progress.pop(key, None)
        # Compute overall completion pct
        total, done = _count_tasks(plan, progress)
        pct = round((done / total) * 100, 1) if total else 0
        await db.strategy_plans.update_one(
            {"id": plan_id, "user_id": user["user_id"]},
            {"$set": {"task_progress": progress, "progress_pct": pct}},
        )
        return {"ok": True, "task_progress": progress, "progress_pct": pct}

    return router


def _count_tasks(plan: dict, progress: dict) -> tuple[int, int]:
    total = 0
    done = 0
    phases = plan.get("phases") or []
    for pi, ph in enumerate(phases):
        for kind in ("milestones", "weekly_tasks"):
            items = ph.get(kind) or []
            for ti in range(len(items)):
                total += 1
                if progress.get(f"{pi}.{kind}.{ti}"):
                    done += 1
    # leading indicators live at plan root, use phase_index=-1
    li = plan.get("leading_indicators") or []
    for ti in range(len(li)):
        total += 1
        if progress.get(f"-1.leading_indicators.{ti}"):
            done += 1
    return total, done
