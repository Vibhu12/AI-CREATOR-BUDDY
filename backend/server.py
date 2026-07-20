"""CreatorOS backend — AI Business OS for creators (per-user scoped).

All data endpoints require Authorization: Bearer <session_token> and are scoped
to the current user. On first sign-in, a starter dataset (Maya persona) is
auto-seeded into the new user's namespace so the wow moment is preserved.

Endpoints under /api:
  GET  /dashboard            → hero score + key metrics + recommendations
  GET  /portfolio            → user's assets
  POST /portfolio            → add asset
  GET  /content              → user's content
  GET  /finance              → user's finance summary + series + tx
  GET  /goals                → user's goals
  POST /goals                → create goal
  GET  /recommendations      → user's AI recommendations
  POST /ai/chat              → streaming AI coach chat
  GET  /ai/chat/history      → past messages for this user's session
  POST /ai/chat/reset        → clear this user's messages
  GET  /onboarding/status    → { complete: bool, youtube_handle: str|null }
  POST /onboarding/complete  → mark complete + optional youtube_handle
"""
from __future__ import annotations

import json
import logging
import os
import random
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Literal

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

# Load env BEFORE local imports — auth/integrations/strategy read os.environ at import.
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

from auth import make_auth_router, ensure_indexes
from competitors import make_competitors_router
from integrations import make_integrations_router, YOUTUBE_API_KEY
from strategy import make_strategy_router

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

app = FastAPI(title="CreatorOS API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("creatoros")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class AssetIn(BaseModel):
    name: str
    platform: str
    category: str
    revenue_mtd: float = 0.0
    profit_mtd: float = 0.0
    followers: int = 0
    ai_score: int = 70
    trend: List[float] = Field(default_factory=list)


class Asset(AssetIn):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    created_at: datetime = Field(default_factory=now_utc)


class GoalIn(BaseModel):
    title: str
    kind: Literal["revenue", "followers", "subscribers", "launch", "content"]
    target: float
    current: float = 0.0
    deadline: Optional[str] = None
    icon: Optional[str] = None


class Goal(GoalIn):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    created_at: datetime = Field(default_factory=now_utc)


class ChatRequest(BaseModel):
    session_id: str
    message: str


class OnboardingComplete(BaseModel):
    youtube_handle: Optional[str] = None


# ---------------------------------------------------------------------------
# Starter data templates (copied into each new user's namespace on first sign-in)
# ---------------------------------------------------------------------------
STARTER_ASSETS: List[dict] = [
    {"name": "Maya Builds — YouTube", "platform": "youtube", "category": "Long-form video",
     "revenue_mtd": 18420.50, "profit_mtd": 12140.00, "followers": 184500, "ai_score": 87,
     "trend": [62, 68, 71, 74, 78, 82, 87]},
    {"name": "@mayabuilds — Instagram", "platform": "instagram", "category": "Short-form + carousels",
     "revenue_mtd": 6740.00, "profit_mtd": 5210.00, "followers": 92300, "ai_score": 74,
     "trend": [55, 58, 62, 66, 68, 71, 74]},
    {"name": "Ship It — Course", "platform": "course", "category": "Cohort course",
     "revenue_mtd": 24300.00, "profit_mtd": 19100.00, "followers": 1420, "ai_score": 91,
     "trend": [70, 74, 79, 83, 86, 89, 91]},
    {"name": "The Build Letter — Newsletter", "platform": "newsletter", "category": "Weekly essay",
     "revenue_mtd": 3120.00, "profit_mtd": 2710.00, "followers": 22800, "ai_score": 68,
     "trend": [60, 62, 63, 64, 66, 67, 68]},
    {"name": "TikTok — @maya.builds", "platform": "tiktok", "category": "Short-form",
     "revenue_mtd": 1240.00, "profit_mtd": 920.00, "followers": 41700, "ai_score": 58,
     "trend": [48, 51, 55, 56, 57, 58, 58]},
    {"name": "Founder Mode — Podcast", "platform": "podcast", "category": "Interview show",
     "revenue_mtd": 2840.00, "profit_mtd": 2110.00, "followers": 11200, "ai_score": 72,
     "trend": [62, 64, 66, 68, 70, 71, 72]},
]

STARTER_GOALS: List[dict] = [
    {"title": "$80K MRR by Q4", "kind": "revenue", "target": 80000, "current": 56660, "deadline": "2026-12-31"},
    {"title": "250K YouTube subs", "kind": "subscribers", "target": 250000, "current": 184500, "deadline": "2026-09-30"},
    {"title": "Launch Ship It v2", "kind": "launch", "target": 1, "current": 0.62, "deadline": "2026-08-15"},
    {"title": "Ship 12 videos this quarter", "kind": "content", "target": 12, "current": 7, "deadline": "2026-08-31"},
]

STARTER_CONTENT: List[dict] = [
    {"platform": "youtube", "title": "I tried to build a $10k MRR SaaS in 30 days",
     "views": 412_000, "likes": 28_900, "comments": 1840, "ctr": 11.2, "watch_pct": 47.8,
     "virality": 92, "ai_score": 88, "_offset_days": 4},
    {"platform": "youtube", "title": "Why creators are leaving Substack",
     "views": 184_300, "likes": 12_100, "comments": 920, "ctr": 8.4, "watch_pct": 41.2,
     "virality": 71, "ai_score": 76, "_offset_days": 11},
    {"platform": "instagram", "title": "The 5-second hook that 10x'd my reach",
     "views": 96_500, "likes": 7_200, "comments": 410, "ctr": 6.1, "watch_pct": 58.3,
     "virality": 64, "ai_score": 81, "_offset_days": 2},
    {"platform": "tiktok", "title": "POV: you finally ship the thing",
     "views": 51_400, "likes": 4_180, "comments": 290, "ctr": 4.2, "watch_pct": 62.1,
     "virality": 48, "ai_score": 62, "_offset_days": 1},
]

STARTER_RECS: List[dict] = [
    {"title": "Double down on YouTube long-form",
     "summary": "Your last 4 videos averaged 11% CTR — 2.4× channel average. Ship 2 more in this format this week.",
     "priority": "high", "impact": 9, "effort": 5, "confidence": 92,
     "category": "Content", "expected_roi": "+$8.4k MTD"},
    {"title": "Raise Ship It cohort price by 18%",
     "summary": "Conversion held at $499 for 3 cohorts. Demand signal + waitlist size suggests $589 is the sweet spot.",
     "priority": "high", "impact": 8, "effort": 2, "confidence": 84,
     "category": "Pricing", "expected_roi": "+$11.2k / cohort"},
    {"title": "Cut Instagram Reels production by 40%",
     "summary": "Reels drove 3% of revenue but consumed 22% of editing hours. Reallocate to YouTube Shorts repurposing.",
     "priority": "medium", "impact": 6, "effort": 3, "confidence": 78,
     "category": "Operations", "expected_roi": "+9 hrs/week"},
    {"title": "Launch newsletter sponsor tier",
     "summary": "22.8k engaged readers, 48% open rate. Conservative CPM benchmarks suggest $1.8k/issue floor.",
     "priority": "medium", "impact": 7, "effort": 4, "confidence": 81,
     "category": "Monetization", "expected_roi": "+$7.2k MTD"},
]


async def seed_user_starter(user_id: str) -> None:
    """Copy the starter template into a new user's namespace."""
    if await db.assets.count_documents({"user_id": user_id}) > 0:
        return
    await db.assets.insert_many([
        {**a, "id": str(uuid.uuid4()), "user_id": user_id, "created_at": now_utc()}
        for a in STARTER_ASSETS
    ])
    await db.goals.insert_many([
        {**g, "id": str(uuid.uuid4()), "user_id": user_id, "created_at": now_utc()}
        for g in STARTER_GOALS
    ])
    await db.content.insert_many([
        {
            **{k: v for k, v in c.items() if k != "_offset_days"},
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "published_at": (now_utc() - timedelta(days=c["_offset_days"])).isoformat(),
        }
        for c in STARTER_CONTENT
    ])
    await db.recommendations.insert_many([
        {**r, "id": str(uuid.uuid4()), "user_id": user_id}
        for r in STARTER_RECS
    ])
    log.info("seeded starter data for %s", user_id)


# ---------------------------------------------------------------------------
# Auth wiring — sub-router + current_user dependency
# ---------------------------------------------------------------------------
auth_router, current_user = make_auth_router(db, on_new_user=seed_user_starter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PROJECTION = {"_id": 0}


def _finance_series(days: int = 30, base_rev: float = 1400.0, base_exp: float = 620.0, seed: int = 7) -> List[dict]:
    rng = random.Random(seed)
    series = []
    today = now_utc().date()
    for i in range(days, 0, -1):
        d = today - timedelta(days=i - 1)
        wobble_r = rng.uniform(-220, 380) + (i * 14)
        wobble_e = rng.uniform(-90, 140) + (i * 4.2)
        series.append({
            "date": d.isoformat(),
            "revenue": round(base_rev + wobble_r, 2),
            "expense": round(base_exp + wobble_e, 2),
        })
    return series


def _hash_seed(user_id: str) -> int:
    return sum(ord(c) for c in user_id) or 7


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"name": "CreatorOS API", "ok": True}


@api.get("/dashboard")
async def dashboard(user: dict = Depends(current_user)):
    assets = await db.assets.find({"user_id": user["user_id"]}, PROJECTION).to_list(100)
    recs = await db.recommendations.find({"user_id": user["user_id"]}, PROJECTION).to_list(100)
    revenue_mtd = sum(a.get("revenue_mtd", 0) for a in assets)
    profit_mtd = sum(a.get("profit_mtd", 0) for a in assets)
    followers_total = sum(a.get("followers", 0) for a in assets)
    margin = (profit_mtd / revenue_mtd * 100) if revenue_mtd else 0
    first_name = (user.get("name") or "there").split(" ")[0]
    return {
        "greeting": f"Welcome back, {first_name}",
        "subtitle": "Your business is operating at 87% efficiency",
        "hero": {
            "score": 87,
            "label": "Business Health",
            "delta": "+6 vs last month",
            "breakdown": [
                {"label": "Growth", "value": 91},
                {"label": "Financial", "value": 84},
                {"label": "Content", "value": 88},
                {"label": "Brand", "value": 79},
            ],
        },
        "metrics": [
            {"key": "revenue", "label": "Revenue MTD", "value": revenue_mtd, "delta": 12.4, "format": "currency"},
            {"key": "profit", "label": "Profit MTD", "value": profit_mtd, "delta": 9.1, "format": "currency"},
            {"key": "margin", "label": "Margin", "value": round(margin, 1), "delta": 1.8, "format": "percent"},
            {"key": "followers", "label": "Total Audience", "value": followers_total, "delta": 4.6, "format": "compact"},
        ],
        "recommendations": recs[:4],
        "alerts": [
            {"kind": "viral", "text": "Your YouTube video crossed 400k views — schedule a follow-up"},
            {"kind": "opportunity", "text": "Ship It waitlist hit 612 — open enrollment within 7 days"},
        ],
    }


@api.get("/portfolio")
async def get_portfolio(user: dict = Depends(current_user)):
    assets = await db.assets.find({"user_id": user["user_id"]}, PROJECTION).sort("revenue_mtd", -1).to_list(200)
    total_revenue = sum(a.get("revenue_mtd", 0) for a in assets)
    total_profit = sum(a.get("profit_mtd", 0) for a in assets)
    return {
        "total_revenue_mtd": total_revenue,
        "total_profit_mtd": total_profit,
        "asset_count": len(assets),
        "assets": assets,
    }


@api.post("/portfolio", response_model=Asset)
async def create_asset(payload: AssetIn, user: dict = Depends(current_user)):
    asset = Asset(**payload.model_dump(), user_id=user["user_id"])
    await db.assets.insert_one(asset.model_dump())
    return asset


@api.get("/content")
async def get_content(user: dict = Depends(current_user)):
    items = await db.content.find({"user_id": user["user_id"]}, PROJECTION).sort("published_at", -1).to_list(50)
    return {"items": items}


@api.get("/finance")
async def get_finance(user: dict = Depends(current_user)):
    # Derive baseline from user's assets so revenue scales meaningfully
    assets = await db.assets.find({"user_id": user["user_id"]}, PROJECTION).to_list(100)
    total_rev_mtd = sum(a.get("revenue_mtd", 0) for a in assets)
    total_prof_mtd = sum(a.get("profit_mtd", 0) for a in assets)
    daily_rev = (total_rev_mtd / 30) if total_rev_mtd else 1400.0
    daily_exp = ((total_rev_mtd - total_prof_mtd) / 30) if total_rev_mtd else 620.0
    series = _finance_series(base_rev=daily_rev, base_exp=daily_exp, seed=_hash_seed(user["user_id"]))
    revenue = sum(d["revenue"] for d in series)
    expense = sum(d["expense"] for d in series)
    profit = revenue - expense
    return {
        "summary": {
            "revenue_30d": round(revenue, 2),
            "expense_30d": round(expense, 2),
            "profit_30d": round(profit, 2),
            "margin": round(profit / revenue * 100, 1) if revenue else 0,
            "forecast_60d": round(profit * 2.18, 2),
            "runway_months": 14.2,
        },
        "series": series,
        "transactions": [
            {"id": "t1", "label": "Ship It cohort #4 — Stripe payout", "amount": 8420.50, "kind": "in", "at": (now_utc() - timedelta(hours=6)).isoformat()},
            {"id": "t2", "label": "YouTube AdSense", "amount": 3120.00, "kind": "in", "at": (now_utc() - timedelta(days=1)).isoformat()},
            {"id": "t3", "label": "Editor — September retainer", "amount": -1800.00, "kind": "out", "at": (now_utc() - timedelta(days=1)).isoformat()},
            {"id": "t4", "label": "Sponsor — Linear", "amount": 6500.00, "kind": "in", "at": (now_utc() - timedelta(days=2)).isoformat()},
            {"id": "t5", "label": "Tools — Adobe, Figma, Notion", "amount": -184.00, "kind": "out", "at": (now_utc() - timedelta(days=3)).isoformat()},
        ],
    }


@api.get("/goals")
async def get_goals(user: dict = Depends(current_user)):
    items = await db.goals.find({"user_id": user["user_id"]}, PROJECTION).to_list(200)
    return {"items": items}


@api.post("/goals", response_model=Goal)
async def create_goal(payload: GoalIn, user: dict = Depends(current_user)):
    goal = Goal(**payload.model_dump(), user_id=user["user_id"])
    await db.goals.insert_one(goal.model_dump())
    return goal


@api.get("/recommendations")
async def get_recs(user: dict = Depends(current_user)):
    items = await db.recommendations.find({"user_id": user["user_id"]}, PROJECTION).to_list(200)
    return {"items": items}


# --- Onboarding ------------------------------------------------------------
@api.get("/onboarding/status")
async def onboarding_status(user: dict = Depends(current_user)):
    return {
        "complete": bool(user.get("onboarding_complete")),
        "youtube_handle": user.get("youtube_handle"),
        "youtube_api_configured": bool(YOUTUBE_API_KEY),
    }


@api.post("/onboarding/complete")
async def onboarding_complete(payload: OnboardingComplete, user: dict = Depends(current_user)):
    update = {"onboarding_complete": True, "updated_at": now_utc()}
    if payload.youtube_handle:
        update["youtube_handle"] = payload.youtube_handle.lstrip("@")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": update})
    return {"ok": True, "onboarding_complete": True, "youtube_handle": update.get("youtube_handle")}


# --- AI Coach (streaming) --------------------------------------------------
SYSTEM_PROMPT_TEMPLATE = (
    "You are CreatorOS Coach — an elite AI business consultant for digital creators, solopreneurs, and "
    "personal brands. You think like a CEO + CFO + growth strategist + content director rolled into one.\n\n"
    "You serve {name}, a creator with these current business assets:\n{portfolio}\n"
    "Total revenue MTD: ${revenue:,.0f}. Profit MTD: ${profit:,.0f} (~{margin:.0f}% margin).\n\n"
    "Style: confident, specific, numerical. Always quantify impact. Always tie suggestions to a concrete "
    "next action. Use short paragraphs and tight bullet lists. Never hedge with 'it depends' — pick a path. "
    "Never use emojis unless the user does. Be encouraging but never sycophantic."
)


async def _build_system_prompt(user: dict) -> str:
    assets = await db.assets.find({"user_id": user["user_id"]}, PROJECTION).to_list(100)
    if not assets:
        portfolio = "  (no assets yet)"
    else:
        portfolio = "\n".join(
            f"  - {a['name']} ({a['platform']}) — {a.get('followers', 0):,} followers, ${a.get('revenue_mtd', 0):,.0f} MTD"
            for a in assets
        )
    rev = sum(a.get("revenue_mtd", 0) for a in assets)
    prof = sum(a.get("profit_mtd", 0) for a in assets)
    margin = (prof / rev * 100) if rev else 0
    return SYSTEM_PROMPT_TEMPLATE.format(
        name=user.get("name", "the creator"),
        portfolio=portfolio,
        revenue=rev,
        profit=prof,
        margin=margin,
    )


@api.post("/ai/chat")
async def ai_chat(req: ChatRequest, user: dict = Depends(current_user)):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI not configured")

    scoped_session = f"{user['user_id']}::{req.session_id}"

    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "session_id": scoped_session,
        "role": "user",
        "text": req.message,
        "at": now_utc().isoformat(),
    })

    system_prompt = await _build_system_prompt(user)

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=scoped_session,
        system_message=system_prompt,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    async def gen():
        full = []
        try:
            async for ev in chat.stream_message(UserMessage(text=req.message)):
                if isinstance(ev, TextDelta):
                    full.append(ev.content)
                    yield f"data: {json.dumps({'delta': ev.content})}\n\n"
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:
            log.exception("ai stream failed")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        assistant_text = "".join(full)
        if assistant_text:
            await db.chat_messages.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user["user_id"],
                "session_id": scoped_session,
                "role": "assistant",
                "text": assistant_text,
                "at": now_utc().isoformat(),
            })
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@api.get("/ai/chat/history")
async def chat_history(session_id: str, user: dict = Depends(current_user)):
    scoped_session = f"{user['user_id']}::{session_id}"
    msgs = await db.chat_messages.find(
        {"session_id": scoped_session, "user_id": user["user_id"]},
        PROJECTION,
    ).sort("at", 1).to_list(500)
    return {"messages": msgs}


@api.post("/ai/chat/reset")
async def chat_reset(session_id: str, user: dict = Depends(current_user)):
    scoped_session = f"{user['user_id']}::{session_id}"
    await db.chat_messages.delete_many({"session_id": scoped_session, "user_id": user["user_id"]})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Sub-routers
# ---------------------------------------------------------------------------
api.include_router(auth_router)
api.include_router(make_integrations_router())
api.include_router(make_competitors_router())
api.include_router(make_strategy_router(db, EMERGENT_LLM_KEY, current_user))
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes(db)


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
