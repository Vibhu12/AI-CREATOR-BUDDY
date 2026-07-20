"""v5 backend tests — Notifications + expanded starter seed.

Covers:
- GET /api/notifications (list + unread count)
- POST /api/notifications/{id}/read (single mark)
- POST /api/notifications/read-all (bulk mark)
- Auth gate (401 without Bearer) + user-scoping (A can't touch B's data)
- seed_user_starter counts: assets=6, goals=4, content=4, recommendations=4,
  notifications=6, chat_messages=4 (scoped session), strategy_plans=1
  (title contains '30-Day Revenue Acceleration', task_progress has 2 entries,
   progress_pct=16.7).
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

# Load backend env + import server module for seed_user_starter
sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from server import seed_user_starter  # noqa: E402

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") if os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL"
) else None
if not BASE_URL:
    # Fallback to frontend .env
    load_dotenv("/app/frontend/.env")
    BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ---------------------------------------------------------------------------
# Fixtures — create two synthetic users w/ tokens, seeded starter data
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


async def _mk_user(db, suffix: str) -> tuple[str, str]:
    """Create user + session; seed starter. Returns (user_id, token)."""
    user_id = f"user_v5_{suffix}_{uuid.uuid4().hex[:8]}"
    token = f"v5-token-{suffix}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "email": f"{user_id}@test.com",
            "name": f"V5 {suffix}",
            "picture": None,
            "onboarding_complete": True,
            "youtube_handle": None,
            "instagram_handle": None,
            "tier": "free",
            "created_at": now,
            "updated_at": now,
        }},
        upsert=True,
    )
    await db.user_sessions.update_one(
        {"session_token": token},
        {"$set": {
            "session_token": token,
            "user_id": user_id,
            "expires_at": now + timedelta(days=1),
            "created_at": now,
        }},
        upsert=True,
    )
    await seed_user_starter(user_id)
    return user_id, token


async def _cleanup_user(db, user_id: str):
    for coll in ("users", "user_sessions", "assets", "goals", "content",
                 "recommendations", "notifications", "chat_messages",
                 "strategy_plans"):
        await db[coll].delete_many({"user_id": user_id})


@pytest.fixture(scope="module")
def users(mongo, event_loop):
    """Create user A + B; teardown at end."""
    a_id, a_tok = event_loop.run_until_complete(_mk_user(mongo, "a"))
    b_id, b_tok = event_loop.run_until_complete(_mk_user(mongo, "b"))
    yield {"a": (a_id, a_tok), "b": (b_id, b_tok)}
    event_loop.run_until_complete(_cleanup_user(mongo, a_id))
    event_loop.run_until_complete(_cleanup_user(mongo, b_id))


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_notifications_requires_auth():
    r = requests.get(f"{BASE_URL}/api/notifications", timeout=15)
    assert r.status_code == 401, r.text


def test_mark_read_requires_auth():
    r = requests.post(f"{BASE_URL}/api/notifications/abc/read", timeout=15)
    assert r.status_code == 401


def test_mark_all_requires_auth():
    r = requests.post(f"{BASE_URL}/api/notifications/read-all", timeout=15)
    assert r.status_code == 401


def test_seed_produces_6_notifications_all_unread(users):
    _, tok = users["a"]
    r = requests.get(f"{BASE_URL}/api/notifications", headers=_headers(tok), timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 6, f"expected 6 items, got {len(data['items'])}"
    assert data["unread"] == 6, f"expected unread=6, got {data['unread']}"
    # Validate shape
    n = data["items"][0]
    for k in ("id", "kind", "title", "body", "read", "at"):
        assert k in n, f"missing key {k} in notification"
    assert n["read"] is False


def test_mark_single_read_decrements_unread(users):
    _, tok = users["a"]
    r = requests.get(f"{BASE_URL}/api/notifications", headers=_headers(tok), timeout=15)
    items = r.json()["items"]
    unread_before = r.json()["unread"]
    # find an unread
    target = next(i for i in items if not i["read"])

    m = requests.post(
        f"{BASE_URL}/api/notifications/{target['id']}/read",
        headers=_headers(tok), timeout=15,
    )
    assert m.status_code == 200, m.text
    assert m.json().get("ok") is True

    r2 = requests.get(f"{BASE_URL}/api/notifications", headers=_headers(tok), timeout=15)
    assert r2.json()["unread"] == unread_before - 1
    updated = next(i for i in r2.json()["items"] if i["id"] == target["id"])
    assert updated["read"] is True


def test_mark_unknown_id_returns_404(users):
    _, tok = users["a"]
    r = requests.post(
        f"{BASE_URL}/api/notifications/does-not-exist-xyz/read",
        headers=_headers(tok), timeout=15,
    )
    assert r.status_code == 404


def test_mark_all_read_zeros_unread(users):
    _, tok = users["a"]
    r = requests.post(
        f"{BASE_URL}/api/notifications/read-all",
        headers=_headers(tok), timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["updated"] >= 0

    r2 = requests.get(f"{BASE_URL}/api/notifications", headers=_headers(tok), timeout=15)
    assert r2.json()["unread"] == 0
    assert all(i["read"] for i in r2.json()["items"])


def test_user_scoping_a_cannot_read_bs_notification(users):
    _, tok_a = users["a"]
    _, tok_b = users["b"]
    # get a B notification
    rb = requests.get(f"{BASE_URL}/api/notifications", headers=_headers(tok_b), timeout=15)
    b_items = rb.json()["items"]
    assert b_items, "user B should have seeded notifications"
    b_target = b_items[0]["id"]
    b_unread_before = rb.json()["unread"]

    # A tries to mark B's notification → 404
    r = requests.post(
        f"{BASE_URL}/api/notifications/{b_target}/read",
        headers=_headers(tok_a), timeout=15,
    )
    assert r.status_code == 404, r.text

    # B's unread count untouched
    rb2 = requests.get(f"{BASE_URL}/api/notifications", headers=_headers(tok_b), timeout=15)
    assert rb2.json()["unread"] == b_unread_before


def test_seed_counts_all_collections(users, mongo, event_loop):
    """Verify starter seed populated all collections with expected counts."""
    b_id, _ = users["b"]

    async def _counts():
        return {
            "assets": await mongo.assets.count_documents({"user_id": b_id}),
            "goals": await mongo.goals.count_documents({"user_id": b_id}),
            "content": await mongo.content.count_documents({"user_id": b_id}),
            "recommendations": await mongo.recommendations.count_documents({"user_id": b_id}),
            "notifications": await mongo.notifications.count_documents({"user_id": b_id}),
            "chat_messages": await mongo.chat_messages.count_documents({"user_id": b_id}),
            "strategy_plans": await mongo.strategy_plans.count_documents({"user_id": b_id}),
        }

    c = event_loop.run_until_complete(_counts())
    assert c["assets"] == 6, c
    assert c["goals"] == 4, c
    assert c["content"] == 4, c
    assert c["recommendations"] == 4, c
    assert c["notifications"] == 6, c
    assert c["chat_messages"] == 4, c
    assert c["strategy_plans"] == 1, c


def test_seed_chat_messages_use_scoped_session(users, mongo, event_loop):
    b_id, _ = users["b"]

    async def _msgs():
        return await mongo.chat_messages.find({"user_id": b_id}).to_list(50)

    msgs = event_loop.run_until_complete(_msgs())
    assert len(msgs) == 4
    expected_session = f"{b_id}::maya-default-session"
    for m in msgs:
        assert m["session_id"] == expected_session
        assert m["role"] in ("user", "assistant")
        assert m["text"]


def test_seed_strategy_plan_shape(users, mongo, event_loop):
    b_id, _ = users["b"]

    async def _plan():
        return await mongo.strategy_plans.find_one({"user_id": b_id})

    plan = event_loop.run_until_complete(_plan())
    assert plan is not None
    assert "30-Day Revenue Acceleration" in plan["title"], plan["title"]
    assert plan["task_progress"] == {"0.weekly_tasks.0": True, "0.weekly_tasks.1": True}
    assert plan["progress_pct"] == 16.7


def test_ai_chat_history_returns_seeded_messages(users):
    """Frontend regression: /ai/chat/history for a fresh seeded user should
    return the 4 seeded messages when queried with session_id='maya-default-session'.
    """
    _, tok = users["b"]
    r = requests.get(
        f"{BASE_URL}/api/ai/chat/history",
        headers=_headers(tok),
        params={"session_id": "maya-default-session"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    msgs = r.json()["messages"]
    assert len(msgs) == 4, f"expected 4 seeded chat messages, got {len(msgs)}"
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_portfolio_add_asset_refreshes_count(users):
    """Frontend regression: POST /api/portfolio creates asset and increments count."""
    _, tok = users["a"]
    r0 = requests.get(f"{BASE_URL}/api/portfolio", headers=_headers(tok), timeout=15)
    before = r0.json()["asset_count"]

    payload = {
        "name": "TEST_v5_new_asset",
        "platform": "youtube",
        "category": "TEST",
        "revenue_mtd": 100.0,
        "profit_mtd": 75.0,
        "followers": 1000,
        "ai_score": 70,
        "trend": [70, 71, 72],
    }
    r1 = requests.post(f"{BASE_URL}/api/portfolio", headers=_headers(tok),
                       json=payload, timeout=15)
    assert r1.status_code == 200, r1.text
    created = r1.json()
    assert created["name"] == "TEST_v5_new_asset"
    assert created["platform"] == "youtube"

    r2 = requests.get(f"{BASE_URL}/api/portfolio", headers=_headers(tok), timeout=15)
    assert r2.json()["asset_count"] == before + 1
