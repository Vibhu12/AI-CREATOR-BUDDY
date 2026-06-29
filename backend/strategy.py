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
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("creatoros.strategy")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class StrategyRequest(BaseModel):
    horizon_days: int = 90  # 30, 60, or 90
    focus: Optional[str] = None  # optional user-provided goal


STRATEGY_SYSTEM = (
    "You are CreatorOS Strategy Engine. You generate operator-grade roadmaps for a creator's business. "
    "Always respond with a single VALID JSON object — no prose, no markdown fences. "
    "Schema strictly:\n"
    "{\n"
    '  "title": str,\n'
    '  "summary": str (one sentence, <= 25 words),\n'
    '  "horizon_days": int,\n'
    '  "north_star": {"metric": str, "target": str},\n'
    '  "kpis": [{"label": str, "target": str}] (3-5 items),\n'
    '  "phases": [\n'
    '    {"window": "Days 1-30", "theme": str, "milestones": [str, str, str], '
    '"weekly_tasks": [str, str, str, str], "risk": str}\n'
    "  ] (one phase per 30-day block, sized to horizon_days),\n"
    '  "leading_indicators": [str, str, str]\n'
    "}\n"
    "Context — the user is Maya, running a YouTube channel (184k subs), Ship It course "
    "($24k/cohort, ~75% margin), newsletter (22.8k), IG (92k), podcast, TikTok. Total revenue ~$56k MTD. "
    "Be specific. Quantify targets. Tie each phase to a measurable outcome."
)


def make_strategy_router(db, api_key: str):
    router = APIRouter(prefix="/strategy", tags=["strategy"])

    @router.get("/plans")
    async def list_plans():
        plans = await db.strategy_plans.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"items": plans}

    @router.get("/plans/{plan_id}")
    async def get_plan(plan_id: str):
        plan = await db.strategy_plans.find_one({"id": plan_id}, {"_id": 0})
        if not plan:
            raise HTTPException(404, "plan not found")
        return plan

    @router.post("/plans")
    async def generate(req: StrategyRequest):
        if req.horizon_days not in (30, 60, 90):
            raise HTTPException(400, "horizon_days must be 30, 60, or 90")
        if not api_key:
            raise HTTPException(500, "AI not configured")

        user_prompt = (
            f"Generate a {req.horizon_days}-day strategic roadmap. "
            + (f"User priority: {req.focus}. " if req.focus else "")
            + "Return JSON only matching the schema."
        )

        chat = LlmChat(
            api_key=api_key,
            session_id=f"strategy-{uuid.uuid4().hex[:8]}",
            system_message=STRATEGY_SYSTEM,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        chunks: list[str] = []
        async for ev in chat.stream_message(UserMessage(text=user_prompt)):
            if isinstance(ev, TextDelta):
                chunks.append(ev.content)
            elif isinstance(ev, StreamDone):
                break
        raw = "".join(chunks).strip()
        # Strip code fences if model wrapped JSON in them
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
            "horizon_days": req.horizon_days,
            "focus": req.focus,
            "created_at": now_utc().isoformat(),
            **data,
        }
        await db.strategy_plans.insert_one({**plan})
        # Re-fetch with projection so _id is gone
        return await db.strategy_plans.find_one({"id": plan["id"]}, {"_id": 0})

    return router
