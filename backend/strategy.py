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

from emergentintegrations.llm.chat import LlmChat, UserMessage
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

# --- Tool-calling: the model must go through these for any real number ---
# rather than inventing derived unit-economics (e.g. "implying a course
# price point by dividing revenue by an assumed enrollment count") in
# free-form prose, which was the recurring failure mode measured by
# evals/eval_llm_judge.py on complex multi-asset portfolios. See
# evals/README.md "A real finding" for the before/after this was measured.
MAX_TOOL_ROUNDS = 4

TOOL_USAGE_RULES = (
    "\n\nYou have two tools — use them, don't do math or fact-recall yourself:\n"
    "1. get_portfolio_facts() — the ONLY source of truth for this user's real numbers. "
    "Call it before writing any north_star or KPI target.\n"
    "2. compute_metric(...) — the ONLY way to do arithmetic anywhere in this plan "
    "(division, multiplication, percentages, addition, subtraction). Never compute a "
    "derived number yourself in prose — e.g. an implied price point, a growth rate, a "
    "conversion-driven projection. Always call compute_metric instead, and honestly "
    "label each input's source: 'known_fact' only if it came directly from "
    "get_portfolio_facts, or 'assumption' if you're estimating it (an enrollment count, "
    "a conversion rate, anything not in the portfolio data). If compute_metric reports a "
    "result as assumption_based, you MUST present that figure in the plan as a labelled "
    "range with a verify-note (e.g. \"~$40-60 implied price point — estimate, verify "
    "against your real funnel\"), never as a bare precise fact."
)

STRATEGY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_facts",
            "description": (
                "Returns this user's EXACT real business numbers — per-asset revenue, "
                "profit and followers, plus totals and margin. The only ground-truth "
                "source for any figure stated as fact in the plan. Call this before "
                "writing north_star or KPI targets."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_metric",
            "description": (
                "The only way to do arithmetic for this plan. Never compute a derived "
                "figure yourself in prose — call this instead, and label each input's "
                "source honestly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide", "percentage"],
                        "description": "'percentage' returns a/b*100",
                    },
                    "a": {"type": "number"},
                    "a_source": {
                        "type": "string",
                        "enum": ["known_fact", "assumption"],
                        "description": "'known_fact' only if this value came directly from get_portfolio_facts",
                    },
                    "b": {"type": "number"},
                    "b_source": {"type": "string", "enum": ["known_fact", "assumption"]},
                    "label": {
                        "type": "string",
                        "description": "what this computes, e.g. 'implied course price point'",
                    },
                },
                "required": ["operation", "a", "a_source", "b", "b_source", "label"],
            },
        },
    },
]


def _exec_compute_metric(args: dict) -> dict:
    op = args.get("operation")
    try:
        a = float(args.get("a", 0))
        b = float(args.get("b", 0))
    except (TypeError, ValueError):
        return {"error": "'a' and 'b' must be numbers"}
    if op == "add":
        result = a + b
    elif op == "subtract":
        result = a - b
    elif op == "multiply":
        result = a * b
    elif op == "divide":
        result = (a / b) if b else 0.0
    elif op == "percentage":
        result = (a / b * 100) if b else 0.0
    else:
        return {"error": f"unknown operation '{op}'"}

    assumption_based = args.get("a_source") == "assumption" or args.get("b_source") == "assumption"
    return {
        "label": args.get("label", ""),
        "result": round(result, 2),
        "assumption_based": assumption_based,
        "instruction": (
            "At least one input was an assumption — present this in the plan as a "
            "labelled range with a verify-note, never as a bare precise fact."
            if assumption_based else
            "Both inputs were known facts — you may state this result as fact."
        ),
    }


def _exec_tool(name: str, arguments: dict, facts: dict) -> dict:
    if name == "get_portfolio_facts":
        return facts
    if name == "compute_metric":
        return _exec_compute_metric(arguments or {})
    return {"error": f"unknown tool '{name}'"}


def _demo_filter(user: dict) -> dict:
    """Mirrors server.py's `demo_filter()` — kept local to avoid a
    cross-module import between independent router modules."""
    if user.get("demo_mode", True):
        return {}
    return {"is_demo": {"$ne": True}}


async def _load_assets(db, user: dict) -> list[dict]:
    return await db.assets.find({"user_id": user["user_id"], **_demo_filter(user)}, {"_id": 0}).to_list(100)


def _facts_from_assets(assets: list[dict]) -> dict:
    rev = sum(a.get("revenue_mtd", 0) for a in assets)
    prof = sum(a.get("profit_mtd", 0) for a in assets)
    margin = (prof / rev * 100) if rev else 0
    return {
        "assets": [
            {
                "name": a.get("name", "Untitled"),
                "platform": a.get("platform", "unknown"),
                "followers": a.get("followers", 0),
                "revenue_mtd": round(a.get("revenue_mtd", 0), 2),
                "profit_mtd": round(a.get("profit_mtd", 0), 2),
            }
            for a in assets
        ],
        "total_revenue_mtd": round(rev, 2),
        "total_profit_mtd": round(prof, 2),
        "margin_pct": round(margin, 1),
        "note": (
            "These are the ONLY real numbers that exist for this user. Anything else "
            "(price points, conversion rates, enrollment counts, RPM/CPM/AOV, etc.) is "
            "not tracked — treat it as an assumption if you reference it, never as fact."
        ),
    }


async def _build_strategy_context(db, user: dict) -> tuple[str, dict]:
    """Builds a per-user context block for the Strategy Engine — mirrors the
    AI Coach's `_build_system_prompt` in server.py so plans are grounded in
    THIS user's real portfolio, not a fixed demo persona. Also returns the
    structured `facts` dict the get_portfolio_facts tool serves verbatim."""
    assets = await _load_assets(db, user)
    facts = _facts_from_assets(assets)
    if not assets:
        portfolio = "  (no assets yet — recommend how to launch the first one)"
    else:
        portfolio = "\n".join(
            f"  - {a.get('name', 'Untitled')} ({a.get('platform', 'unknown')}) — "
            f"{a.get('followers', 0):,} followers, ${a.get('revenue_mtd', 0):,.0f} MTD"
            for a in assets
        )
    system_prompt = STRATEGY_SCHEMA + TOOL_USAGE_RULES + STRATEGY_CONTEXT_TEMPLATE.format(
        name=user.get("name", "the creator"),
        portfolio=portfolio,
        revenue=facts["total_revenue_mtd"],
        profit=facts["total_profit_mtd"],
        margin=facts["margin_pct"],
    )
    return system_prompt, facts


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

        system_prompt, facts = await _build_strategy_context(db, user)
        chat = (
            LlmChat(
                api_key=api_key,
                session_id=f"strategy-{uuid.uuid4().hex[:8]}",
                system_message=system_prompt,
            )
            .with_model("anthropic", "claude-sonnet-4-5-20250929")
            .with_tools(STRATEGY_TOOLS)
        )

        tool_call_count = 0
        try:
            resp = await chat.send_message_with_tools(UserMessage(text=user_prompt))
            rounds = 0
            while resp.tool_calls and rounds < MAX_TOOL_ROUNDS:
                for tc in resp.tool_calls:
                    result = _exec_tool(tc.name, tc.arguments, facts)
                    tool_call_count += 1
                    chat.add_tool_result(tc.id, json.dumps(result))
                resp = await chat.send_message_with_tools()
                rounds += 1
        except HTTPException:
            raise
        except Exception as e:
            log.exception("strategy tool-calling loop failed: %s", e)
            raise HTTPException(502, "AI generation failed; retry")

        raw = (resp.content or "").strip()
        log.info(
            "strategy plan generated user=%s horizon=%s tool_calls=%d",
            user["user_id"], req.horizon_days, tool_call_count,
        )
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
            "tool_calls_used": tool_call_count,
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
