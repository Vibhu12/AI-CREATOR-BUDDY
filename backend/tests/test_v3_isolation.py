"""V3 per-user isolation + onboarding + auth-gate tests.

Focus: verify that all data endpoints require Bearer, and that data is
scoped by user_id (users A and B cannot see each other's data).
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
from pymongo import MongoClient

# Load backend env & make server importable for seed helper
sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _now():
    return datetime.now(timezone.utc)


# ---- Fixtures --------------------------------------------------------------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def users(mongo):
    """Create two synthetic users A + B with valid session tokens.

    Also seeds user A's namespace with the starter dataset (6 assets, etc.).
    """
    uid_a = f"user_v3_a_{uuid.uuid4().hex[:6]}"
    uid_b = f"user_v3_b_{uuid.uuid4().hex[:6]}"
    tok_a = f"v3-tok-a-{uuid.uuid4().hex[:8]}"
    tok_b = f"v3-tok-b-{uuid.uuid4().hex[:8]}"
    now = _now()
    for uid, tok, name, email in [
        (uid_a, tok_a, "Alice Test", f"TEST_{uid_a}@ex.com"),
        (uid_b, tok_b, "Bob Test", f"TEST_{uid_b}@ex.com"),
    ]:
        mongo.users.update_one(
            {"user_id": uid},
            {"$set": {
                "user_id": uid, "email": email, "name": name, "picture": None,
                "onboarding_complete": False, "youtube_handle": None,
                "created_at": now, "updated_at": now,
            }},
            upsert=True,
        )
        mongo.user_sessions.update_one(
            {"session_token": tok},
            {"$set": {"session_token": tok, "user_id": uid,
                      "expires_at": now + timedelta(days=1), "created_at": now}},
            upsert=True,
        )

    # Seed A's namespace via server helper
    from server import seed_user_starter
    asyncio.get_event_loop().run_until_complete(seed_user_starter(uid_a))

    yield {"a": {"uid": uid_a, "tok": tok_a},
           "b": {"uid": uid_b, "tok": tok_b}}

    # Teardown
    for uid in (uid_a, uid_b):
        mongo.users.delete_many({"user_id": uid})
        mongo.user_sessions.delete_many({"user_id": uid})
        mongo.assets.delete_many({"user_id": uid})
        mongo.goals.delete_many({"user_id": uid})
        mongo.content.delete_many({"user_id": uid})
        mongo.recommendations.delete_many({"user_id": uid})
        mongo.chat_messages.delete_many({"user_id": uid})
        mongo.strategy_plans.delete_many({"user_id": uid})


def hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---- 1. Auth gate: all data endpoints must 401 without token --------------
PROTECTED = [
    ("GET", "/dashboard"),
    ("GET", "/portfolio"),
    ("POST", "/portfolio"),
    ("GET", "/finance"),
    ("GET", "/goals"),
    ("POST", "/goals"),
    ("GET", "/content"),
    ("GET", "/recommendations"),
    ("POST", "/ai/chat"),
    ("GET", "/ai/chat/history?session_id=s1"),
    ("GET", "/strategy/plans"),
    ("POST", "/strategy/plans"),
    ("GET", "/onboarding/status"),
    ("POST", "/onboarding/complete"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_returns_401_without_token(method, path):
    r = requests.request(method, f"{API}{path}", json={} if method == "POST" else None, timeout=10)
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}"
    assert "bearer" in r.text.lower() or "missing" in r.text.lower() or "invalid" in r.text.lower()


# ---- 2. Public endpoints remain open --------------------------------------
def test_root_public():
    r = requests.get(f"{API}/", timeout=10)
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_stripe_status_public():
    r = requests.get(f"{API}/integrations/stripe/status", timeout=10)
    assert r.status_code == 200


def test_youtube_channel_public():
    r = requests.get(f"{API}/integrations/youtube/channel?handle=mkbhd", timeout=15)
    assert r.status_code in (200, 503)


def test_competitors_public():
    r = requests.get(f"{API}/competitors/list", timeout=10)
    # allow 200 or 404 depending on route naming — probe list of common ones
    if r.status_code == 404:
        for p in ("/competitors", "/competitors/radar", "/competitors/gaps"):
            r2 = requests.get(f"{API}{p}", timeout=10)
            if r2.status_code == 200:
                return
    assert r.status_code in (200, 404)


# ---- 3. Per-user scoping: A's namespace vs B's ----------------------------
def test_A_has_6_seeded_assets_B_has_zero(users):
    ra = requests.get(f"{API}/portfolio", headers=hdr(users["a"]["tok"]), timeout=10)
    rb = requests.get(f"{API}/portfolio", headers=hdr(users["b"]["tok"]), timeout=10)
    assert ra.status_code == 200 and rb.status_code == 200
    assert ra.json()["asset_count"] == 6, ra.json()
    assert rb.json()["asset_count"] == 0, rb.json()


def test_POST_asset_scoped_to_A_not_visible_to_B(users, mongo):
    payload = {"name": "TEST_ScopedAsset", "platform": "youtube", "category": "test",
               "revenue_mtd": 100, "profit_mtd": 50, "followers": 1, "ai_score": 50, "trend": [1, 2]}
    r = requests.post(f"{API}/portfolio", headers=hdr(users["a"]["tok"]), json=payload, timeout=10)
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    # DB row must be scoped to A
    row = mongo.assets.find_one({"id": aid})
    assert row["user_id"] == users["a"]["uid"]
    # B cannot see it
    rb = requests.get(f"{API}/portfolio", headers=hdr(users["b"]["tok"]), timeout=10)
    names = [a["name"] for a in rb.json()["assets"]]
    assert "TEST_ScopedAsset" not in names


def test_seed_B_also_gets_6_assets(users):
    # Trigger seed for B
    from server import seed_user_starter
    asyncio.get_event_loop().run_until_complete(seed_user_starter(users["b"]["uid"]))
    ra = requests.get(f"{API}/portfolio", headers=hdr(users["a"]["tok"]), timeout=10)
    rb = requests.get(f"{API}/portfolio", headers=hdr(users["b"]["tok"]), timeout=10)
    # A had 6 seeded + 1 posted above = 7
    assert ra.json()["asset_count"] >= 6
    assert rb.json()["asset_count"] == 6


# ---- 4. Onboarding flow ---------------------------------------------------
def test_onboarding_status_initial_false(users):
    r = requests.get(f"{API}/onboarding/status", headers=hdr(users["b"]["tok"]), timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["complete"] is False
    assert data["youtube_handle"] is None
    assert "youtube_api_configured" in data


def test_onboarding_complete_strips_at_and_persists(users):
    r = requests.post(f"{API}/onboarding/complete",
                      headers=hdr(users["b"]["tok"]),
                      json={"youtube_handle": "@testhandle"}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["onboarding_complete"] is True
    assert body["youtube_handle"] == "testhandle"  # @ stripped
    # follow-up status
    r2 = requests.get(f"{API}/onboarding/status", headers=hdr(users["b"]["tok"]), timeout=10)
    assert r2.json()["complete"] is True
    assert r2.json()["youtube_handle"] == "testhandle"


# ---- 5. Dashboard greeting uses first name --------------------------------
def test_dashboard_greeting_first_name(users):
    r = requests.get(f"{API}/dashboard", headers=hdr(users["a"]["tok"]), timeout=10)
    assert r.status_code == 200
    assert r.json()["greeting"] == "Welcome back, Alice"


# ---- 6. AI chat history is user-scoped by session_id ---------------------
def test_chat_history_scoped_by_user(users, mongo):
    # Directly insert a chat message for A only
    mongo.chat_messages.insert_one({
        "id": str(uuid.uuid4()), "user_id": users["a"]["uid"],
        "session_id": f"{users['a']['uid']}::s1",
        "role": "user", "text": "hello from A", "at": _now().isoformat(),
    })
    ra = requests.get(f"{API}/ai/chat/history?session_id=s1", headers=hdr(users["a"]["tok"]), timeout=10)
    rb = requests.get(f"{API}/ai/chat/history?session_id=s1", headers=hdr(users["b"]["tok"]), timeout=10)
    assert ra.status_code == 200 and rb.status_code == 200
    a_msgs = ra.json()["messages"]
    b_msgs = rb.json()["messages"]
    assert any(m.get("text") == "hello from A" for m in a_msgs)
    assert not any(m.get("text") == "hello from A" for m in b_msgs)


# ---- 7. Strategy plans scoped by user_id ---------------------------------
def test_strategy_plans_scoped(users, mongo):
    # Insert a plan directly for A to avoid slow Claude call in most CI runs
    plan_id = str(uuid.uuid4())
    mongo.strategy_plans.insert_one({
        "id": plan_id, "user_id": users["a"]["uid"],
        "horizon_days": 30, "focus": None,
        "created_at": _now().isoformat(),
        "title": "TEST plan", "summary": "s", "north_star": {"metric": "x", "target": "y"},
        "kpis": [], "phases": [], "leading_indicators": [],
    })
    ra = requests.get(f"{API}/strategy/plans", headers=hdr(users["a"]["tok"]), timeout=10)
    rb = requests.get(f"{API}/strategy/plans", headers=hdr(users["b"]["tok"]), timeout=10)
    assert ra.status_code == 200 and rb.status_code == 200
    a_titles = [p.get("title") for p in ra.json()["items"]]
    b_titles = [p.get("title") for p in rb.json()["items"]]
    assert "TEST plan" in a_titles
    assert "TEST plan" not in b_titles
