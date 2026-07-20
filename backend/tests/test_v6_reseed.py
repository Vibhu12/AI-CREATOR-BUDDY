"""v6 backend tests — POST /api/dev/reseed + expanded starter (8 assets, 7 recs).

Covers:
- POST /api/dev/reseed requires auth (401 without Bearer)
- Reseed is user-scoped (A cannot touch B's data)
- After reseed for user, counts scoped to that user_id are:
  assets=8 (includes affiliate + digital), goals=4, content=4,
  recommendations=7 (includes 3 new titles), notifications=6,
  chat_messages=4, strategy_plans=1
- GET /api/portfolio returns 8 assets, total_revenue_mtd ~ $66,460
- GET /api/recommendations returns 7 items with 3 new titles
- GET /api/dashboard revenue metric ~ $66,460, recommendations shows 4
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

NEW_ASSET_AFFILIATE = "Amazon + ConvertKit Affiliate"
NEW_ASSET_DIGITAL = "Notion Templates — Gumroad"
NEW_REC_TITLES = {
    "Bundle Notion templates into a $99 pack",
    "Diversify affiliate portfolio",
    "Repurpose podcast into YouTube shorts",
}
EXPECTED_TOTAL_REV = 66_460.50  # sum of the 8 STARTER_ASSETS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def mongo():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


async def _mk_user(db, suffix: str, seed: bool = True) -> tuple[str, str]:
    user_id = f"user_v6_{suffix}_{uuid.uuid4().hex[:8]}"
    token = f"v6-token-{suffix}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id, "email": f"{user_id}@test.com",
            "name": f"V6 {suffix}", "picture": None,
            "onboarding_complete": True, "tier": "free",
            "created_at": now, "updated_at": now,
        }},
        upsert=True,
    )
    await db.user_sessions.update_one(
        {"session_token": token},
        {"$set": {
            "session_token": token, "user_id": user_id,
            "expires_at": now + timedelta(days=1), "created_at": now,
        }},
        upsert=True,
    )
    if seed:
        await seed_user_starter(user_id)
    return user_id, token


async def _cleanup(db, user_id: str):
    for coll in ("users", "user_sessions", "assets", "goals", "content",
                 "recommendations", "notifications", "chat_messages",
                 "strategy_plans"):
        await db[coll].delete_many({"user_id": user_id})


@pytest.fixture(scope="module")
def users(mongo, event_loop):
    a_id, a_tok = event_loop.run_until_complete(_mk_user(mongo, "a", seed=False))
    b_id, b_tok = event_loop.run_until_complete(_mk_user(mongo, "b", seed=True))
    yield {"a": (a_id, a_tok), "b": (b_id, b_tok)}
    event_loop.run_until_complete(_cleanup(mongo, a_id))
    event_loop.run_until_complete(_cleanup(mongo, b_id))


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_reseed_requires_auth():
    r = requests.post(f"{BASE_URL}/api/dev/reseed", timeout=15)
    assert r.status_code == 401, r.text


def test_reseed_returns_ok_and_user_id(users):
    _, tok = users["a"]
    r = requests.post(f"{BASE_URL}/api/dev/reseed", headers=H(tok), timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("user_id") == users["a"][0]


def test_reseed_counts_all_collections(users, mongo, event_loop):
    a_id, tok = users["a"]
    # Already reseeded in prior test — call again to ensure idempotence w/ wipe
    r = requests.post(f"{BASE_URL}/api/dev/reseed", headers=H(tok), timeout=20)
    assert r.status_code == 200

    async def _c():
        return {
            "assets": await mongo.assets.count_documents({"user_id": a_id}),
            "goals": await mongo.goals.count_documents({"user_id": a_id}),
            "content": await mongo.content.count_documents({"user_id": a_id}),
            "recommendations": await mongo.recommendations.count_documents({"user_id": a_id}),
            "notifications": await mongo.notifications.count_documents({"user_id": a_id}),
            "chat_messages": await mongo.chat_messages.count_documents({"user_id": a_id}),
            "strategy_plans": await mongo.strategy_plans.count_documents({"user_id": a_id}),
        }
    c = event_loop.run_until_complete(_c())
    assert c == {"assets": 8, "goals": 4, "content": 4,
                 "recommendations": 7, "notifications": 6,
                 "chat_messages": 4, "strategy_plans": 1}, c


def test_reseed_includes_new_affiliate_and_digital_assets(users):
    _, tok = users["a"]
    r = requests.get(f"{BASE_URL}/api/portfolio", headers=H(tok), timeout=15)
    assert r.status_code == 200
    assets = r.json()["assets"]
    by_name = {a["name"]: a for a in assets}
    assert NEW_ASSET_AFFILIATE in by_name, list(by_name.keys())
    assert NEW_ASSET_DIGITAL in by_name, list(by_name.keys())
    aff = by_name[NEW_ASSET_AFFILIATE]
    assert aff["platform"] == "affiliate"
    assert aff["revenue_mtd"] == 4180.0
    dig = by_name[NEW_ASSET_DIGITAL]
    assert dig["platform"] == "digital"
    assert dig["revenue_mtd"] == 5620.0


def test_portfolio_total_matches_expected(users):
    _, tok = users["a"]
    r = requests.get(f"{BASE_URL}/api/portfolio", headers=H(tok), timeout=15)
    body = r.json()
    assert body["asset_count"] == 8
    # Allow floating point tolerance
    assert abs(body["total_revenue_mtd"] - EXPECTED_TOTAL_REV) < 1.0, body["total_revenue_mtd"]


def test_recommendations_has_7_with_new_titles(users):
    _, tok = users["a"]
    r = requests.get(f"{BASE_URL}/api/recommendations", headers=H(tok), timeout=15)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 7, len(items)
    titles = {i["title"] for i in items}
    missing = NEW_REC_TITLES - titles
    assert not missing, f"missing new rec titles: {missing}"


def test_dashboard_metrics_and_recs(users):
    _, tok = users["a"]
    r = requests.get(f"{BASE_URL}/api/dashboard", headers=H(tok), timeout=15)
    assert r.status_code == 200
    body = r.json()
    metrics = {m["key"]: m for m in body["metrics"]}
    assert metrics["revenue"]["label"] == "Revenue MTD"
    assert abs(metrics["revenue"]["value"] - EXPECTED_TOTAL_REV) < 1.0
    # dashboard returns top-4 of 7 recommendations
    assert len(body["recommendations"]) == 4


def test_reseed_is_user_scoped(users, mongo, event_loop):
    """User A reseed must NOT touch user B's data."""
    a_id, a_tok = users["a"]
    b_id, _ = users["b"]

    # Add 3 custom assets to B on top of the seeded 8
    async def _add_b_custom():
        now = datetime.now(timezone.utc)
        await mongo.assets.insert_many([
            {"id": str(uuid.uuid4()), "user_id": b_id,
             "name": f"TEST_B_custom_{i}", "platform": "youtube",
             "category": "TEST", "revenue_mtd": 100.0, "profit_mtd": 50.0,
             "followers": 10, "ai_score": 60, "trend": [1, 2, 3],
             "created_at": now}
            for i in range(3)
        ])
    event_loop.run_until_complete(_add_b_custom())

    async def _b_count():
        return await mongo.assets.count_documents({"user_id": b_id})
    b_before = event_loop.run_until_complete(_b_count())
    assert b_before == 11  # 8 seeded + 3 custom

    # A reseeds — B must be untouched
    r = requests.post(f"{BASE_URL}/api/dev/reseed", headers=H(a_tok), timeout=20)
    assert r.status_code == 200

    b_after = event_loop.run_until_complete(_b_count())
    assert b_after == 11, f"B's asset count changed: {b_before} → {b_after}"

    # Verify B's custom assets still exist
    async def _custom():
        return await mongo.assets.count_documents({"user_id": b_id, "name": {"$regex": "^TEST_B_custom_"}})
    assert event_loop.run_until_complete(_custom()) == 3


def test_reseed_wipes_prior_custom_assets_for_self(users, mongo, event_loop):
    """Reseeding for self should wipe user's prior data (including custom)."""
    a_id, a_tok = users["a"]

    async def _add_a_custom():
        now = datetime.now(timezone.utc)
        await mongo.assets.insert_one({
            "id": str(uuid.uuid4()), "user_id": a_id,
            "name": "TEST_A_will_be_wiped", "platform": "youtube",
            "category": "TEST", "revenue_mtd": 999.0, "profit_mtd": 0,
            "followers": 0, "ai_score": 50, "trend": [1],
            "created_at": now,
        })
    event_loop.run_until_complete(_add_a_custom())

    async def _c():
        return await mongo.assets.count_documents({"user_id": a_id})
    assert event_loop.run_until_complete(_c()) == 9  # 8 seed + 1 custom

    r = requests.post(f"{BASE_URL}/api/dev/reseed", headers=H(a_tok), timeout=20)
    assert r.status_code == 200

    # After reseed: back to 8, custom wiped
    assert event_loop.run_until_complete(_c()) == 8

    async def _custom():
        return await mongo.assets.count_documents({"user_id": a_id, "name": "TEST_A_will_be_wiped"})
    assert event_loop.run_until_complete(_custom()) == 0
