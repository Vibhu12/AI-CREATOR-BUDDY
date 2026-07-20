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


def make_strategy_router(db, api_key: str, current_user):
    router = APIRouter(prefix="/strategy", tags=["strategy"])

    @router.get("/plans")
    async def list_plans(user: dict = Depends(current_user)):
        plans = await db.strategy_plans.find(
            {"user_id": user["user_id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        return {"items": plans}

    @router.get("/plans/{plan_id}")
    async def get_plan(plan_id: str, user: dict = Depends(current_user)):
        plan = await db.strategy_plans.find_one(
            {"id": plan_id, "user_id": user["user_id"]}, {"_id": 0}
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
            {"id": plan_id, "user_id": user["user_id"]}, {"_id": 0}
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
