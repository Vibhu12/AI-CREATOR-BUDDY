"""Shared fixtures for the eval suite.

Mirrors ../tests/conftest.py's pattern (random per-run tokens, session-scoped
teardown, no persisted secrets) but seeds TWO users with deliberately
different revenue scales so groundedness/scale evals have something
meaningful to diff against.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))
# EXPO_PUBLIC_BACKEND_URL lives in the frontend .env — load it too so evals
# don't require a manual `export` before running.
load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "frontend", ".env"))

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

if not MONGO_URL or not DB_NAME:
    raise RuntimeError("MONGO_URL and DB_NAME must be set before running evals.")

_SCOPED_COLLECTIONS = ("assets", "strategy_plans", "goals", "content", "recommendations")


def _make_user(db, now, *, uid_prefix: str, name: str, assets: list[dict]) -> dict:
    uid = f"{uid_prefix}_{secrets.token_hex(6)}"
    token = f"eval_{secrets.token_urlsafe(32)}"

    db.users.update_one(
        {"user_id": uid},
        {"$set": {
            "user_id": uid,
            "email": f"{uid}@creatoros.eval",
            "name": name,
            "picture": None,
            "onboarding_complete": True,
            "youtube_handle": None,
            "instagram_handle": None,
            "tier": "pro",  # avoid free-tier weekly-plan quota interfering with evals
            "integrations": {},
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": uid,
        "expires_at": now + timedelta(hours=1),
        "created_at": now,
    })
    for a in assets:
        db.assets.insert_one({
            "id": secrets.token_hex(8),
            "user_id": uid,
            "created_at": now.isoformat(),
            **a,
        })
    return {"uid": uid, "token": token}


@pytest.fixture(scope="session", autouse=True)
def eval_users():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc)

    # A tiny solo creator just getting started — one small newsletter.
    lo = _make_user(
        db, now,
        uid_prefix="eval_lo",
        name="Priya Solo",
        assets=[{
            "name": "Weekend Notes", "platform": "newsletter", "category": "Weekly essay",
            "revenue_mtd": 480.0, "profit_mtd": 410.0, "followers": 640, "ai_score": 40,
        }],
    )

    # A large multi-asset creator business — should get a very different plan.
    hi = _make_user(
        db, now,
        uid_prefix="eval_hi",
        name="Jordan Scale",
        assets=[
            {"name": "Jordan Scale — YouTube", "platform": "youtube", "category": "Long-form video",
             "revenue_mtd": 142000.0, "profit_mtd": 98000.0, "followers": 2_400_000, "ai_score": 95},
            {"name": "Scale Systems — Course", "platform": "course", "category": "Cohort course",
             "revenue_mtd": 68000.0, "profit_mtd": 54000.0, "followers": 8_200, "ai_score": 93},
        ],
    )

    yield {"lo": lo, "hi": hi}

    for u in (lo, hi):
        db.user_sessions.delete_many({"session_token": u["token"]})
        db.users.delete_many({"user_id": u["uid"]})
        for coll in _SCOPED_COLLECTIONS:
            db[coll].delete_many({"user_id": u["uid"]})
    client.close()
