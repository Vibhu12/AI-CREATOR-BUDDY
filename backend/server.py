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
import re
import uuid
from contextlib import asynccontextmanager
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
from analytics import make_analytics_router
from billing import make_billing_router
from competitors import make_competitors_router
from integrations import make_integrations_router, YOUTUBE_API_KEY
from quotas import enforce_chat_message
from strategy import make_strategy_router

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


@asynccontextmanager
async def lifespan(app_: FastAPI):
    # Startup
    await ensure_indexes(db)
    await backfill_legacy_demo_tags()
    # SEC-002: shout loudly if DEMO_MODE is on — must be false in production.
    # Secure by default: absent/unset DEMO_MODE now means OFF, not ON.
    if os.environ.get("DEMO_MODE", "false").strip().lower() == "true":
        log.warning(
            "⚠  DEMO_MODE is ON — mock tier upgrades are enabled. "
            "This MUST be set to false in production (backend/.env → DEMO_MODE=false)."
        )
    yield
    # Shutdown
    client.close()


app = FastAPI(title="CreatorOS API", lifespan=lifespan)
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("creatoros")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# AI Coach conversation "epochs" — a fresh empty chat greets you after a
# period of inactivity, but stays fully continuous (UI + the LLM's own
# memory) while you're actively chatting. Rationale: showing a stale
# leftover conversation as the "default" every time you open the tab reads
# as broken/unfinished; but wiping context mid-conversation would feel
# forgetful. 30 minutes of inactivity ends an epoch.
CHAT_IDLE_TIMEOUT = timedelta(minutes=30)


async def _latest_chat_epoch(user_id: str, base_session: str) -> Optional[dict]:
    """Most recent message under any epoch of this logical thread name."""
    prefix = f"{user_id}::{base_session}"
    docs = await db.chat_messages.find(
        {"user_id": user_id, "session_id": {"$regex": f"^{re.escape(prefix)}"}},
        {"_id": 0, "session_id": 1, "at": 1},
    ).sort("at", -1).limit(1).to_list(1)
    return docs[0] if docs else None


def _epoch_is_fresh(last_at_iso: str) -> bool:
    try:
        last_at = datetime.fromisoformat(last_at_iso)
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return False
    return (now_utc() - last_at) < CHAT_IDLE_TIMEOUT


async def _resolve_send_session(user_id: str, base_session: str) -> str:
    """Which session_id a NEW outgoing message should be written under —
    continues the latest epoch if still fresh, otherwise mints a new one so
    the LLM (which keys its own memory off session_id) also starts clean."""
    latest = await _latest_chat_epoch(user_id, base_session)
    if latest and _epoch_is_fresh(latest["at"]):
        return latest["session_id"]
    return f"{user_id}::{base_session}::{int(now_utc().timestamp())}"


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
    instagram_handle: Optional[str] = None


# ---------------------------------------------------------------------------
# Starter data templates (copied into each new user's namespace on first sign-in)
# ---------------------------------------------------------------------------
STARTER_ASSETS: List[dict] = [
    {"name": "Maya Builds — YouTube", "platform": "youtube", "category": "Long-form video",
     "revenue_mtd": 18420.50, "profit_mtd": 12140.00, "followers": 184500, "ai_score": 87,
     "trend": [62, 68, 71, 74, 78, 82, 87]},
    {"name": "Ship It — Course", "platform": "course", "category": "Cohort course",
     "revenue_mtd": 24300.00, "profit_mtd": 19100.00, "followers": 1420, "ai_score": 91,
     "trend": [70, 74, 79, 83, 86, 89, 91]},
    {"name": "The Build Letter — Newsletter", "platform": "newsletter", "category": "Weekly essay",
     "revenue_mtd": 3120.00, "profit_mtd": 2710.00, "followers": 22800, "ai_score": 68,
     "trend": [60, 62, 63, 64, 66, 67, 68]},
]

STARTER_GOALS: List[dict] = [
    {"title": "$80K MRR by Q4", "kind": "revenue", "target": 80000, "current": 56660, "deadline": "2026-12-31"},
    {"title": "250K YouTube subs", "kind": "subscribers", "target": 250000, "current": 184500, "deadline": "2026-09-30"},
    {"title": "Launch Ship It v2", "kind": "launch", "target": 1, "current": 0.62, "deadline": "2026-08-15"},
]

STARTER_CONTENT: List[dict] = [
    {"platform": "youtube", "title": "I tried to build a $10k MRR SaaS in 30 days",
     "views": 412_000, "likes": 28_900, "comments": 1840, "ctr": 11.2, "watch_pct": 47.8,
     "virality": 92, "ai_score": 88, "_offset_days": 4},
    {"platform": "youtube", "title": "Why creators are leaving Substack",
     "views": 184_300, "likes": 12_100, "comments": 920, "ctr": 8.4, "watch_pct": 41.2,
     "virality": 71, "ai_score": 76, "_offset_days": 11},
    {"platform": "newsletter", "title": "The Build Letter #47 — Ship It v2 teaser",
     "views": 22_800, "likes": 1_640, "comments": 82, "ctr": 48.1, "watch_pct": 62.0,
     "virality": 54, "ai_score": 79, "_offset_days": 2},
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
    {"title": "Launch newsletter sponsor tier",
     "summary": "22.8k engaged readers, 48% open rate. Conservative CPM benchmarks suggest $1.8k/issue floor.",
     "priority": "medium", "impact": 7, "effort": 4, "confidence": 81,
     "category": "Monetization", "expected_roi": "+$7.2k MTD"},
]


STARTER_NOTIFICATIONS: List[dict] = [
    {"kind": "viral", "title": "YouTube video crossed 400k views",
     "body": "'I tried to build a $10k MRR SaaS in 30 days' hit 412k views — schedule a follow-up while momentum's high.",
     "_offset_hours": 3, "priority": "high"},
    {"kind": "opportunity", "title": "Ship It waitlist hit 612",
     "body": "You have 612 warm leads. At $499 × 12% conversion, that's $36.6k. Open enrollment in the next 7 days.",
     "_offset_hours": 5, "priority": "high"},
    {"kind": "insight", "title": "AI Coach flagged pricing gap",
     "body": "Claude analyzed 3 cohorts — recommends raising Ship It to $589. Est. impact: +$11.2k per cohort.",
     "_offset_hours": 26, "priority": "high"},
]


STARTER_CHAT: List[dict] = [
    {"role": "user", "text": "What's the fastest lever I can pull this week?",
     "_offset_minutes": 90},
    {"role": "assistant",
     "text": ("Raise Ship It's price to $589 before Friday's launch. Three signals:\n\n"
              "• Waitlist is at 612 — 3.4× last cohort's converting demand\n"
              "• Last 3 cohorts sold out at $499 with zero pricing objections\n"
              "• Your closest comp (Cohort Capital) charges $749 for comparable scope\n\n"
              "Estimated impact: +$11.2k on cohort #5 alone. Do it today, announce Wednesday."),
     "_offset_minutes": 88},
    {"role": "user", "text": "What should I ship on YouTube this month?",
     "_offset_minutes": 60},
    {"role": "assistant",
     "text": ("Your top performer this quarter is the '$10k MRR in 30 days' format — 412k views, 11.2% CTR, 2.4× your channel average. Ship two more in that lane:\n\n"
              "1. 'I tried to fix an ugly SaaS in 7 days' — teardown format, high hook density\n"
              "2. 'Solo dev vs $50k competitor' — David-vs-Goliath, high emotion\n\n"
              "Publish Tue + Thu. Keep hooks under 5s. I'll review your thumbnails when they're ready."),
     "_offset_minutes": 58},
]


STARTER_PLAN: dict = {
    "title": "30-Day Revenue Acceleration Playbook",
    "summary": "Turn Ship It waitlist momentum into a $78k month by shipping YouTube volume and repricing the course.",
    "horizon_days": 30,
    "north_star": {"metric": "Monthly Revenue", "target": "$78,400 (+38% vs $56.7k baseline)"},
    "kpis": [
        {"label": "Ship It cohort #5 enrollments", "target": "95 students at $589 (+$11.2k)"},
        {"label": "YouTube RPM", "target": "$8.50 (+15% via mid-roll optimization)"},
        {"label": "Newsletter → course conversion", "target": "4.2% (960 opens → 40 enrollments)"},
        {"label": "TikTok → YouTube funnel", "target": "6.8% weighted cross-platform CTR"},
    ],
    "phases": [
        {
            "window": "Days 1-10",
            "theme": "Reprice + reload the funnel",
            "milestones": [
                "Update Ship It landing page to $589 with grandfather clause",
                "Ship YouTube video #1 (teardown format, 400k+ target)",
                "Send waitlist a 'price change coming' warning email",
            ],
            "weekly_tasks": [
                "Rewrite Ship It sales page top-half with new positioning",
                "Record + edit YouTube video #1 (Tues drop)",
                "Draft cohort #5 launch sequence (5 emails)",
                "Update Stripe + Gumroad prices in sync",
            ],
            "risk": "Pricing pushback from waitlist — mitigate with grandfathered rate for early sign-ups.",
        },
        {
            "window": "Days 11-20",
            "theme": "Launch cohort #5 with paid amplification",
            "milestones": [
                "Open Ship It #5 enrollment publicly",
                "Ship YouTube video #2 (David-vs-Goliath format)",
                "First $2k in paid ads → warm YouTube audiences",
            ],
            "weekly_tasks": [
                "Launch email #1 to waitlist (Monday 9am ET)",
                "Publish YouTube video #2 (Thursday)",
                "Set up Meta Ads retargeting from YouTube channel",
                "Post 3 Twitter threads reinforcing course value",
            ],
            "risk": "Ad account newness may throttle spend — start at $150/day, scale to $500 over 7 days.",
        },
        {
            "window": "Days 21-30",
            "theme": "Close strong + rebuild pipeline",
            "milestones": [
                "Hit 95 enrollments (95 × $589 = $55.9k)",
                "Newsletter sponsor tier goes live",
                "Cohort #5 kick-off + first live session",
            ],
            "weekly_tasks": [
                "Close cart with 48-hour last-call sequence",
                "Publish sponsor kit + reach out to 5 target brands",
                "Batch-record next 4 YouTube episodes",
                "Analyze cohort data → seed content ideas for month 2",
            ],
            "risk": "Content burnout — schedule a 3-day break in week 4 after cart closes.",
        },
    ],
    "leading_indicators": [
        "Waitlist → cart page CTR above 22%",
        "YouTube subscriber velocity above +2.4k/week",
        "Newsletter open rate stays above 46%",
    ],
}


async def seed_user_starter(user_id: str) -> None:
    """Copy the starter template into a new user's namespace. Idempotent —
    silently no-ops if the user already has assets. Every record is tagged
    `is_demo: True` so it can be hidden by the demo-mode toggle without
    being confused with data the user actually owns."""
    if await db.assets.count_documents({"user_id": user_id, "is_demo": True}) > 0:
        return
    await db.assets.insert_many([
        {**a, "id": str(uuid.uuid4()), "user_id": user_id, "created_at": now_utc(), "is_demo": True}
        for a in STARTER_ASSETS
    ])
    await db.goals.insert_many([
        {**g, "id": str(uuid.uuid4()), "user_id": user_id, "created_at": now_utc(), "is_demo": True}
        for g in STARTER_GOALS
    ])
    await db.content.insert_many([
        {
            **{k: v for k, v in c.items() if k != "_offset_days"},
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "published_at": (now_utc() - timedelta(days=c["_offset_days"])).isoformat(),
            "is_demo": True,
        }
        for c in STARTER_CONTENT
    ])
    await db.recommendations.insert_many([
        {**r, "id": str(uuid.uuid4()), "user_id": user_id, "is_demo": True}
        for r in STARTER_RECS
    ])
    await db.notifications.insert_many([
        {
            **{k: v for k, v in n.items() if k != "_offset_hours"},
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "read": False,
            "at": (now_utc() - timedelta(hours=n["_offset_hours"])).isoformat(),
            "is_demo": True,
        }
        for n in STARTER_NOTIFICATIONS
    ])
    scoped_session = f"{user_id}::maya-default-session"
    await db.chat_messages.insert_many([
        {
            **{k: v for k, v in m.items() if k != "_offset_minutes"},
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "session_id": scoped_session,
            "at": (now_utc() - timedelta(minutes=m["_offset_minutes"])).isoformat(),
            "is_demo": True,
        }
        for m in STARTER_CHAT
    ])
    await db.strategy_plans.insert_one({
        **STARTER_PLAN,
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "focus": None,
        "created_at": now_utc().isoformat(),
        "task_progress": {"0.weekly_tasks.0": True, "0.weekly_tasks.1": True},
        "progress_pct": 16.7,
        "is_demo": True,
    })
    log.info("seeded starter data for %s", user_id)


LEGACY_ASSET_NAMES = [a["name"] for a in STARTER_ASSETS]
LEGACY_GOAL_TITLES = [g["title"] for g in STARTER_GOALS]
LEGACY_CONTENT_TITLES = [c["title"] for c in STARTER_CONTENT]
LEGACY_REC_TITLES = [r["title"] for r in STARTER_RECS]
LEGACY_NOTIF_TITLES = [n["title"] for n in STARTER_NOTIFICATIONS]
LEGACY_CHAT_TEXTS = [m["text"] for m in STARTER_CHAT]
LEGACY_PLAN_TITLE = STARTER_PLAN["title"]


async def backfill_legacy_demo_tags() -> None:
    """Accounts created before the demo_mode toggle existed had their
    auto-seeded Maya starter data written WITHOUT the `is_demo` flag, so
    demo_filter() can't tell it apart from real data — toggling demo_mode
    off silently does nothing for those users (Maya's data stays visible,
    possibly mixed in with anything they've genuinely added since).
    This retags those specific records by their exact persona-specific
    name/title/text — values a real user's own data cannot coincidentally
    match — as is_demo: True. Safe to run on every startup: idempotent,
    only touches documents that don't already have is_demo set."""
    ops = [
        (db.assets, "name", LEGACY_ASSET_NAMES),
        (db.goals, "title", LEGACY_GOAL_TITLES),
        (db.content, "title", LEGACY_CONTENT_TITLES),
        (db.recommendations, "title", LEGACY_REC_TITLES),
        (db.notifications, "title", LEGACY_NOTIF_TITLES),
        (db.chat_messages, "text", LEGACY_CHAT_TEXTS),
        (db.strategy_plans, "title", [LEGACY_PLAN_TITLE]),
    ]
    total = 0
    for coll, field, values in ops:
        r = await coll.update_many(
            {field: {"$in": values}, "is_demo": {"$ne": True}},
            {"$set": {"is_demo": True}},
        )
        total += r.modified_count
    if total:
        log.info("backfilled is_demo tag on %d legacy seed records", total)


def demo_filter(user: dict) -> dict:
    """Mongo filter fragment selecting which of the user's own records to
    read, based on their `demo_mode` toggle:
      - demo_mode True  (default) → no filter at all — this is the existing
        behavior preserved exactly (seeded Maya data + anything real the
        user has added, merged, same as before this toggle existed).
      - demo_mode False            → hide seeded data, show ONLY the user's
        real records (anything they actually added/connected themselves).
    Deliberately asymmetric rather than a strict either/or: a real action
    (adding a goal, generating a plan) must never become invisible just
    because demo_mode happens to be on.
    """
    if user.get("demo_mode", True):
        return {}
    return {"is_demo": {"$ne": True}}


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


def _compute_real_hero(assets: List[dict]) -> dict:
    """Computed (not hardcoded) health score for a real, non-demo portfolio.
    Deliberately simple/heuristic — see docs/decisions.md for why this
    exists instead of a fixed number."""
    if not assets:
        return {
            "score": 0,
            "label": "Business Health",
            "delta": "Add your first asset to see this",
            "breakdown": [
                {"label": "Growth", "value": 0},
                {"label": "Financial", "value": 0},
                {"label": "Content", "value": 0},
                {"label": "Brand", "value": 0},
            ],
        }
    revenue_mtd = sum(a.get("revenue_mtd", 0) for a in assets)
    profit_mtd = sum(a.get("profit_mtd", 0) for a in assets)
    followers_total = sum(a.get("followers", 0) for a in assets)
    margin = (profit_mtd / revenue_mtd * 100) if revenue_mtd else 0
    financial = round(min(100, max(0, margin)))
    trends = [a.get("trend") for a in assets if a.get("trend") and len(a["trend"]) >= 2]
    growth = round(min(100, sum(max(t[-1] - t[0], 0) for t in trends) / len(trends) * 6)) if trends else round(
        sum(a.get("ai_score", 50) for a in assets) / len(assets)
    )
    content = round(sum(a.get("ai_score", 50) for a in assets) / len(assets))
    brand = round(min(100, followers_total / 3000))
    score = round((financial + growth + content + brand) / 4)
    return {
        "score": score,
        "label": "Business Health",
        "delta": "Based on your current portfolio",
        "breakdown": [
            {"label": "Growth", "value": growth},
            {"label": "Financial", "value": financial},
            {"label": "Content", "value": content},
            {"label": "Brand", "value": brand},
        ],
    }


@api.get("/dashboard")
async def dashboard(user: dict = Depends(current_user)):
    # Guarantee starter data is available for any authenticated user — this covers
    # accounts that were created before the on-new-user hook existed or were
    # seeded incompletely.
    await seed_user_starter(user["user_id"])
    dfilter = demo_filter(user)
    assets = await db.assets.find({"user_id": user["user_id"], **dfilter}, PROJECTION).to_list(100)
    recs = await db.recommendations.find({"user_id": user["user_id"], **dfilter}, PROJECTION).to_list(100)
    notifs = await db.notifications.find(
        {"user_id": user["user_id"], **dfilter, "read": False}, PROJECTION
    ).sort("at", -1).to_list(2)
    # Rank recommendations by priority tier then impact descending so newer high-impact
    # items surface even when added after the initial seed.
    _priority_rank = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: (_priority_rank.get(r.get("priority"), 3), -int(r.get("impact") or 0)))
    revenue_mtd = sum(a.get("revenue_mtd", 0) for a in assets)
    profit_mtd = sum(a.get("profit_mtd", 0) for a in assets)
    followers_total = sum(a.get("followers", 0) for a in assets)
    margin = (profit_mtd / revenue_mtd * 100) if revenue_mtd else 0
    first_name = (user.get("name") or "there").split(" ")[0]
    is_demo = user.get("demo_mode", True)

    if is_demo:
        # Fixed demo-persona presentation — matches the seeded Maya dataset 1:1.
        subtitle = "Your business is operating at 87% efficiency"
        hero = {
            "score": 87,
            "label": "Business Health",
            "delta": "+6 vs last month",
            "breakdown": [
                {"label": "Growth", "value": 91},
                {"label": "Financial", "value": 84},
                {"label": "Content", "value": 88},
                {"label": "Brand", "value": 79},
            ],
        }
        alerts = [
            {"kind": "viral", "text": "Your YouTube video crossed 400k views — schedule a follow-up"},
            {"kind": "opportunity", "text": "Ship It waitlist hit 612 — open enrollment within 7 days"},
        ]
        metric_deltas = {"revenue": 12.4, "profit": 9.1, "margin": 1.8, "followers": 4.6}
    else:
        hero = _compute_real_hero(assets)
        subtitle = (
            f"Your business is operating at {hero['score']}% efficiency"
            if assets else "No real data yet — connect an integration or add your first asset"
        )
        # Alerts derived from the user's own unread notifications — no fabricated text.
        alerts = [
            {"kind": n.get("kind", "opportunity"), "text": n.get("title") or n.get("body") or ""}
            for n in notifs
        ]
        metric_deltas = {"revenue": 0, "profit": 0, "margin": 0, "followers": 0}

    return {
        "greeting": f"Welcome back, {first_name}",
        "subtitle": subtitle,
        "hero": hero,
        "metrics": [
            {"key": "revenue", "label": "Revenue MTD", "value": revenue_mtd, "delta": metric_deltas["revenue"], "format": "currency"},
            {"key": "profit", "label": "Profit MTD", "value": profit_mtd, "delta": metric_deltas["profit"], "format": "currency"},
            {"key": "margin", "label": "Margin", "value": round(margin, 1), "delta": metric_deltas["margin"], "format": "percent"},
            {"key": "followers", "label": "Total Audience", "value": followers_total, "delta": metric_deltas["followers"], "format": "compact"},
        ],
        "recommendations": recs[:4],
        "alerts": alerts,
        "demo_mode": is_demo,
    }


@api.get("/portfolio")
async def get_portfolio(user: dict = Depends(current_user)):
    await seed_user_starter(user["user_id"])
    dfilter = demo_filter(user)
    assets = await db.assets.find(
        {"user_id": user["user_id"], **dfilter}, PROJECTION
    ).sort("revenue_mtd", -1).to_list(200)
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
    items = await db.content.find(
        {"user_id": user["user_id"], **demo_filter(user)}, PROJECTION
    ).sort("published_at", -1).to_list(50)
    return {"items": items}


@api.get("/finance")
async def get_finance(user: dict = Depends(current_user)):
    is_demo = user.get("demo_mode", True)
    # Derive baseline from user's assets so revenue scales meaningfully
    assets = await db.assets.find(
        {"user_id": user["user_id"], **demo_filter(user)}, PROJECTION
    ).to_list(100)

    if not assets:
        # No real data yet (demo_mode off, nothing added/connected) — honest
        # zero-state rather than a fabricated fallback series.
        today = now_utc().date()
        zero_series = [
            {"date": (today - timedelta(days=i - 1)).isoformat(), "revenue": 0, "expense": 0}
            for i in range(30, 0, -1)
        ]
        zero_proj = [
            {"date": (today + timedelta(days=i)).isoformat(), "revenue": 0, "expense": 0}
            for i in range(1, 91)
        ]
        return {
            "summary": {
                "revenue_30d": 0, "expense_30d": 0, "profit_30d": 0, "margin": 0,
                "forecast_60d": 0, "forecast_90d": 0, "runway_months": 0,
            },
            "series": zero_series,
            "projection": zero_proj,
            "by_asset": [],
            "by_platform": [],
            "expense_categories": [],
            "transactions": [],
        }

    total_rev_mtd = sum(a.get("revenue_mtd", 0) for a in assets)
    total_prof_mtd = sum(a.get("profit_mtd", 0) for a in assets)
    # Demo persona gets a stylized non-zero baseline even in edge cases;
    # real users with genuinely $0 tracked revenue see 0, not a fake number.
    fallback_rev, fallback_exp = (1400.0, 620.0) if is_demo else (0.0, 0.0)
    daily_rev = (total_rev_mtd / 30) if total_rev_mtd else fallback_rev
    daily_exp = ((total_rev_mtd - total_prof_mtd) / 30) if total_rev_mtd else fallback_exp
    series = _finance_series(base_rev=daily_rev, base_exp=daily_exp, seed=_hash_seed(user["user_id"]))
    revenue = sum(d["revenue"] for d in series)
    expense = sum(d["expense"] for d in series)
    profit = revenue - expense

    # Revenue breakdown by asset (sorted desc)
    by_asset = sorted(
        [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "platform": a.get("platform"),
                "revenue_mtd": round(a.get("revenue_mtd", 0), 2),
                "profit_mtd": round(a.get("profit_mtd", 0), 2),
                "share": round((a.get("revenue_mtd", 0) / total_rev_mtd * 100), 1) if total_rev_mtd else 0,
            }
            for a in assets
        ],
        key=lambda x: -x["revenue_mtd"],
    )

    # Aggregate by platform for the donut / bar
    plat_totals: dict = {}
    for a in assets:
        p = a.get("platform") or "other"
        plat_totals[p] = plat_totals.get(p, 0) + a.get("revenue_mtd", 0)
    by_platform = sorted(
        [
            {"platform": p, "revenue_mtd": round(v, 2),
             "share": round((v / total_rev_mtd * 100), 1) if total_rev_mtd else 0}
            for p, v in plat_totals.items()
        ],
        key=lambda x: -x["revenue_mtd"],
    )

    # Simple expense category split (synthetic but stable per user)
    _rng = random.Random(_hash_seed(user["user_id"]) + 3)
    exp_categories = [
        {"label": "Team + contractors", "share": 42, "amount": round(expense * 0.42, 2)},
        {"label": "Software + tools", "share": 14, "amount": round(expense * 0.14, 2)},
        {"label": "Advertising", "share": 22, "amount": round(expense * 0.22, 2)},
        {"label": "Ops + platform fees", "share": 12, "amount": round(expense * 0.12, 2)},
        {"label": "Other", "share": 10, "amount": round(expense * 0.10, 2)},
    ]

    # 90-day forward projection (simple linear + slight growth)
    proj = []
    last_rev = series[-1]["revenue"] if series else daily_rev
    last_exp = series[-1]["expense"] if series else daily_exp
    for i in range(1, 91):
        d = (now_utc().date() + timedelta(days=i)).isoformat()
        rev = last_rev * (1 + 0.0028 * i) + _rng.uniform(-140, 140)
        exp = last_exp * (1 + 0.0015 * i) + _rng.uniform(-60, 60)
        proj.append({"date": d, "revenue": round(rev, 2), "expense": round(exp, 2)})

    return {
        "summary": {
            "revenue_30d": round(revenue, 2),
            "expense_30d": round(expense, 2),
            "profit_30d": round(profit, 2),
            "margin": round(profit / revenue * 100, 1) if revenue else 0,
            "forecast_60d": round(profit * 2.18, 2),
            "forecast_90d": round(profit * 3.31, 2),
            "runway_months": 14.2 if is_demo else 0,
        },
        "series": series,
        "projection": proj,
        "by_asset": by_asset,
        "by_platform": by_platform,
        "expense_categories": exp_categories,
        "transactions": [
            {"id": "t1", "label": "Ship It cohort #4 — Stripe payout", "amount": 8420.50, "kind": "in", "at": (now_utc() - timedelta(hours=6)).isoformat()},
            {"id": "t2", "label": "YouTube AdSense", "amount": 3120.00, "kind": "in", "at": (now_utc() - timedelta(days=1)).isoformat()},
            {"id": "t3", "label": "Editor — September retainer", "amount": -1800.00, "kind": "out", "at": (now_utc() - timedelta(days=1)).isoformat()},
            {"id": "t4", "label": "Sponsor — Linear", "amount": 6500.00, "kind": "in", "at": (now_utc() - timedelta(days=2)).isoformat()},
            {"id": "t5", "label": "Tools — Adobe, Figma, Notion", "amount": -184.00, "kind": "out", "at": (now_utc() - timedelta(days=3)).isoformat()},
        ] if is_demo else [],
    }


@api.get("/goals")
async def get_goals(user: dict = Depends(current_user)):
    items = await db.goals.find(
        {"user_id": user["user_id"], **demo_filter(user)}, PROJECTION
    ).to_list(200)
    return {"items": items}


@api.post("/goals", response_model=Goal)
async def create_goal(payload: GoalIn, user: dict = Depends(current_user)):
    goal = Goal(**payload.model_dump(), user_id=user["user_id"])
    await db.goals.insert_one(goal.model_dump())
    return goal


class GoalUpdate(BaseModel):
    current: Optional[float] = None
    target: Optional[float] = None
    title: Optional[str] = None
    deadline: Optional[str] = None


@api.patch("/goals/{goal_id}")
async def update_goal(goal_id: str, payload: GoalUpdate, user: dict = Depends(current_user)):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "No fields to update")
    # Guardrails
    if "title" in update:
        if not update["title"].strip():
            raise HTTPException(400, "Title cannot be empty")
        if len(update["title"]) > 120:
            raise HTTPException(413, "Title too long")
    if "current" in update and update["current"] < 0:
        raise HTTPException(400, "current cannot be negative")
    if "target" in update and update["target"] <= 0:
        raise HTTPException(400, "target must be positive")

    r = await db.goals.update_one(
        {"id": goal_id, "user_id": user["user_id"], **demo_filter(user)},
        {"$set": update},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "Goal not found")
    goal = await db.goals.find_one({"id": goal_id, "user_id": user["user_id"]}, PROJECTION)
    return goal


@api.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, user: dict = Depends(current_user)):
    r = await db.goals.delete_one({"id": goal_id, "user_id": user["user_id"], **demo_filter(user)})
    if r.deleted_count == 0:
        raise HTTPException(404, "Goal not found")
    return {"ok": True}


# --- Per-asset detail --------------------------------------------------
@api.get("/assets/{asset_id}")
async def get_asset_detail(asset_id: str, user: dict = Depends(current_user)):
    """Rich single-asset detail: base asset + platform-scoped content + AI recs."""
    asset = await db.assets.find_one(
        {"id": asset_id, "user_id": user["user_id"], **demo_filter(user)}, PROJECTION,
    )
    if not asset:
        raise HTTPException(404, "Asset not found")

    # Recent content for this platform
    content = await db.content.find(
        {"user_id": user["user_id"], "platform": asset.get("platform"), **demo_filter(user)}, PROJECTION,
    ).sort("published_at", -1).to_list(20)

    # AI recommendations scoped by platform mention (heuristic — matches category)
    all_recs = await db.recommendations.find(
        {"user_id": user["user_id"], **demo_filter(user)}, PROJECTION
    ).to_list(50)
    platform = (asset.get("platform") or "").lower()
    scoped_recs = [
        r for r in all_recs
        if platform in (r.get("title", "").lower() + " " + r.get("summary", "").lower())
    ][:4]

    # Peer benchmarks for this asset (synthetic — same rank across all assets)
    followers = asset.get("followers") or 0
    revenue = asset.get("revenue_mtd") or 0
    return {
        "asset": asset,
        "content": content,
        "recommendations": scoped_recs,
        "benchmarks": {
            "top_1pct_followers": int(followers * 3.2) if followers else 0,
            "top_1pct_revenue": round(revenue * 4.6, 2) if revenue else 0,
            "median_engagement": 4.8,
            "your_engagement": round(min(9.6, 4.2 + (asset.get("ai_score", 70) - 60) / 6.0), 2),
        },
        "kpis": [
            {"label": "AI Score", "value": asset.get("ai_score", 70), "unit": "/100"},
            {"label": "Revenue MTD", "value": round(revenue, 0), "unit": "$"},
            {"label": "Profit margin",
             "value": round((asset.get("profit_mtd", 0) / revenue * 100) if revenue else 0, 0),
             "unit": "%"},
            {"label": "Audience", "value": followers, "unit": "reach"},
        ],
    }


@api.get("/recommendations")
async def get_recs(user: dict = Depends(current_user)):
    items = await db.recommendations.find(
        {"user_id": user["user_id"], **demo_filter(user)}, PROJECTION
    ).to_list(200)
    return {"items": items}


# --- Notifications --------------------------------------------------------
@api.get("/notifications")
async def get_notifications(user: dict = Depends(current_user)):
    items = await db.notifications.find(
        {"user_id": user["user_id"], **demo_filter(user)}, PROJECTION,
    ).sort("at", -1).to_list(100)
    unread = sum(1 for i in items if not i.get("read"))
    return {"items": items, "unread": unread}


@api.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(current_user)):
    r = await db.notifications.update_one(
        {"id": notification_id, "user_id": user["user_id"]},
        {"$set": {"read": True}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "notification not found")
    return {"ok": True}


@api.post("/notifications/read-all")
async def mark_all_read(user: dict = Depends(current_user)):
    r = await db.notifications.update_many(
        {"user_id": user["user_id"]},
        {"$set": {"read": True}},
    )
    return {"ok": True, "updated": r.modified_count}


# --- Onboarding ------------------------------------------------------------
@api.get("/onboarding/status")
async def onboarding_status(user: dict = Depends(current_user)):
    return {
        "complete": bool(user.get("onboarding_complete")),
        "youtube_handle": user.get("youtube_handle"),
        "youtube_api_configured": bool(YOUTUBE_API_KEY),
    }


class DemoModeUpdate(BaseModel):
    demo_mode: bool


@api.patch("/profile/demo-mode")
async def set_demo_mode(payload: DemoModeUpdate, user: dict = Depends(current_user)):
    """Toggle between the seeded Maya demo persona and the signed-in user's
    own real data. See `demo_filter()` for how every read endpoint respects
    this — this endpoint only flips the flag itself."""
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"demo_mode": payload.demo_mode, "updated_at": now_utc()}},
    )
    return {"ok": True, "demo_mode": payload.demo_mode}


@api.post("/dev/reseed")
async def reseed_starter(user: dict = Depends(current_user)):
    """Reload the Maya starter dataset for the current user. Wipes only the
    seeded demo data (is_demo: True) and reseeds it fresh — never touches
    the user's own real data. DEMO_MODE only."""
    if os.environ.get("DEMO_MODE", "false").strip().lower() != "true":
        raise HTTPException(403, "Endpoint disabled in production")
    uid = user["user_id"]
    for coll in ("assets", "goals", "content", "recommendations",
                 "strategy_plans", "chat_messages", "notifications"):
        await db[coll].delete_many({"user_id": uid, "is_demo": True})
    await seed_user_starter(uid)
    return {"ok": True, "user_id": uid}


@api.post("/onboarding/complete")
async def onboarding_complete(payload: OnboardingComplete, user: dict = Depends(current_user)):
    update = {"onboarding_complete": True, "updated_at": now_utc()}
    if payload.youtube_handle:
        update["youtube_handle"] = payload.youtube_handle.lstrip("@")
    if payload.instagram_handle:
        update["instagram_handle"] = payload.instagram_handle.lstrip("@")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": update})
    return {
        "ok": True,
        "onboarding_complete": True,
        "youtube_handle": update.get("youtube_handle"),
        "instagram_handle": update.get("instagram_handle"),
    }


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
    assets = await db.assets.find(
        {"user_id": user["user_id"], **demo_filter(user)}, PROJECTION
    ).to_list(100)
    if not assets:
        portfolio = (
            "  (no assets yet — encourage them to add their first asset or connect an "
            "integration; don't invent numbers for a business that doesn't exist yet)"
        )
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

    # SEC: enforce message length + free-tier daily quota + burst rate limit
    await enforce_chat_message(db, user, req.message)

    scoped_session = await _resolve_send_session(user["user_id"], req.session_id)

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
            yield f"data: {json.dumps({'error': 'AI stream failed. Please retry.'})}\n\n"
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
    # An idle gap of 30+ minutes ends the conversation epoch — you get a
    # clean, empty Coach instead of a stale leftover transcript every time
    # you open the tab. Still actively chatting within that window? Full
    # history + context, like any normal chat.
    latest = await _latest_chat_epoch(user["user_id"], session_id)
    if not latest or not _epoch_is_fresh(latest["at"]):
        return {"messages": []}
    scoped_session = latest["session_id"]
    msgs = await db.chat_messages.find(
        {"session_id": scoped_session, "user_id": user["user_id"], **demo_filter(user)},
        PROJECTION,
    ).sort("at", 1).to_list(500)
    return {"messages": msgs}


@api.post("/ai/chat/reset")
async def chat_reset(session_id: str, user: dict = Depends(current_user)):
    prefix = f"{user['user_id']}::{session_id}"
    await db.chat_messages.delete_many(
        {"user_id": user["user_id"], "session_id": {"$regex": f"^{re.escape(prefix)}"}}
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Sub-routers
# ---------------------------------------------------------------------------
api.include_router(auth_router)
api.include_router(make_analytics_router(db, current_user))
api.include_router(make_integrations_router(db, current_user))
api.include_router(make_competitors_router(current_user))
api.include_router(make_strategy_router(db, EMERGENT_LLM_KEY, current_user))
api.include_router(make_billing_router(db, current_user))
app.include_router(api)

ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:8081,http://localhost:19006"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,          # auth is Bearer header, not cookies
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
