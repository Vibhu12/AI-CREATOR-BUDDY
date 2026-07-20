"""v7 targeted tests — verify BUG FIX #2 (dashboard rec ordering by priority + impact).

Expected top-4 for a reseeded user (STARTER_RECS priorities/impacts):
  1. 'Double down on YouTube long-form'        high, impact 9
  2. 'Raise Ship It cohort price by 18%'       high, impact 8
  3. 'Bundle Notion templates into a $99 pack' high, impact 7  <-- NEW rec must surface
  4. 'Diversify affiliate portfolio'           medium, impact 8 (highest medium)
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from server import seed_user_starter  # noqa: E402

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

EXPECTED_TOP4_TITLES = [
    "Double down on YouTube long-form",
    "Raise Ship It cohort price by 18%",
    "Bundle Notion templates into a $99 pack",
    "Diversify affiliate portfolio",
]


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def mongo():
    client = AsyncIOMotorClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def seeded_user(mongo, event_loop):
    uid = f"user_v7_{uuid.uuid4().hex[:8]}"
    tok = f"v7-token-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    async def _setup():
        await mongo.users.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid, "email": f"{uid}@test.com",
                      "name": "V7 User", "picture": None,
                      "onboarding_complete": True, "tier": "free",
                      "created_at": now, "updated_at": now}},
            upsert=True,
        )
        await mongo.user_sessions.update_one(
            {"session_token": tok},
            {"$set": {"session_token": tok, "user_id": uid,
                      "expires_at": now + timedelta(days=1), "created_at": now}},
            upsert=True,
        )
        await seed_user_starter(uid)

    async def _teardown():
        for coll in ("users", "user_sessions", "assets", "goals", "content",
                     "recommendations", "notifications", "chat_messages",
                     "strategy_plans"):
            await mongo[coll].delete_many({"user_id": uid})

    event_loop.run_until_complete(_setup())
    yield uid, tok
    event_loop.run_until_complete(_teardown())


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def test_dashboard_top4_titles_in_correct_order(seeded_user):
    _, tok = seeded_user
    r = requests.get(f"{BASE_URL}/api/dashboard", headers=H(tok), timeout=15)
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    assert len(recs) == 4, recs
    got = [r["title"] for r in recs]
    assert got == EXPECTED_TOP4_TITLES, f"top-4 order wrong: {got}"


def test_dashboard_top3_are_all_high_priority(seeded_user):
    _, tok = seeded_user
    r = requests.get(f"{BASE_URL}/api/dashboard", headers=H(tok), timeout=15)
    recs = r.json()["recommendations"]
    # There are 3 high-priority recs — those must occupy slots 0..2
    assert [x["priority"] for x in recs[:3]] == ["high", "high", "high"]
    # Impact must be descending within same priority tier
    assert recs[0]["impact"] >= recs[1]["impact"] >= recs[2]["impact"]


def test_bundle_notion_appears_in_top4(seeded_user):
    """Regression check for BUG FIX #2 — this rec was missing before the fix."""
    _, tok = seeded_user
    r = requests.get(f"{BASE_URL}/api/dashboard", headers=H(tok), timeout=15)
    titles = [r["title"] for r in r.json()["recommendations"]]
    assert "Bundle Notion templates into a $99 pack" in titles, titles
