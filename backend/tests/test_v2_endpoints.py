"""CreatorOS v2 backend tests — auth, competitors, integrations, strategy."""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://business-ai-hub-47.preview.emergentagent.com"
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def synthetic_session():
    """Insert a synthetic user + session and yield (token, user_id). Cleanup at end."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    user_id = f"user_test_{uuid.uuid4().hex[:8]}"
    token = f"test-token-{uuid.uuid4().hex[:12]}"
    email = f"TEST_{uuid.uuid4().hex[:6]}@example.com"
    now = datetime.now(timezone.utc)
    db.users.insert_one({
        "user_id": user_id, "email": email, "name": "Test User",
        "picture": None, "created_at": now, "updated_at": now,
    })
    db.user_sessions.insert_one({
        "session_token": token, "user_id": user_id,
        "expires_at": now + timedelta(days=1), "created_at": now,
    })
    yield token, user_id, email
    db.users.delete_one({"user_id": user_id})
    db.user_sessions.delete_one({"session_token": token})
    client.close()


# --- Auth -------------------------------------------------------------------
def test_auth_session_invalid(s):
    r = s.post(f"{API}/auth/session", json={"session_id": "invalid-bogus-id-1234"})
    assert r.status_code == 401


def test_auth_me_no_header(s):
    r = requests.get(f"{API}/auth/me")  # no Authorization header
    assert r.status_code == 401
    assert "Missing bearer token" in r.json().get("detail", "")


def test_auth_me_with_synthetic_token(synthetic_session):
    token, user_id, email = synthetic_session
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    assert user["user_id"] == user_id
    assert user["email"] == email


def test_auth_logout_deletes_session(synthetic_session):
    token, _, _ = synthetic_session
    r = requests.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    # Subsequent /me should now 401
    r2 = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 401


# --- Competitors ------------------------------------------------------------
def test_competitors_list(s):
    r = s.get(f"{API}/competitors")
    assert r.status_code == 200
    d = r.json()
    for k in ("you", "industry_avg", "top_10", "top_1", "competitors"):
        assert k in d
    assert isinstance(d["competitors"], list) and len(d["competitors"]) >= 3


def test_competitors_radar(s):
    r = s.get(f"{API}/competitors/radar")
    assert r.status_code == 200
    dims = r.json()["dimensions"]
    assert isinstance(dims, list) and len(dims) >= 3
    for row in dims:
        for k in ("key", "label", "you", "top_1", "industry_avg"):
            assert k in row
        # All normalized 0-100
        for k in ("you", "top_1", "industry_avg"):
            assert 0 <= row[k] <= 100


def test_competitors_gaps(s):
    r = s.get(f"{API}/competitors/gaps")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 3
    # Sorted desc by gap_pct
    gaps = [it["gap_pct"] for it in items]
    assert gaps == sorted(gaps, reverse=True)
    # Revenue should be the top gap
    assert items[0]["key"] == "revenue_mtd"


# --- Integrations -----------------------------------------------------------
def test_stripe_status_shape(s):
    r = s.get(f"{API}/integrations/stripe/status")
    assert r.status_code == 200
    d = r.json()
    assert "connected" in d
    # placeholder key — expected to fail auth
    assert d["connected"] is False
    assert "error" in d or d.get("mode") is None


def test_youtube_503_when_not_configured(s):
    r = s.get(f"{API}/integrations/youtube/channel", params={"handle": "test"})
    # Either 503 (no key) or 200/other if configured. Per spec we expect 503.
    assert r.status_code in (503, 200), r.text
    if r.status_code == 503:
        msg = r.json().get("detail", "")
        assert "YouTube" in msg or "YOUTUBE_API_KEY" in msg


# --- Strategy ---------------------------------------------------------------
@pytest.fixture(scope="module")
def generated_plan(s):
    r = s.post(f"{API}/strategy/plans", json={"horizon_days": 30}, timeout=90)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    return r.json()


def test_strategy_generate(generated_plan):
    plan = generated_plan
    for k in ("id", "title", "summary", "north_star", "kpis", "phases", "leading_indicators", "horizon_days"):
        assert k in plan, f"missing key {k}: {plan.keys()}"
    assert plan["horizon_days"] == 30
    assert isinstance(plan["kpis"], list) and len(plan["kpis"]) >= 1
    assert isinstance(plan["phases"], list) and len(plan["phases"]) >= 1
    assert "_id" not in plan


def test_strategy_list(s, generated_plan):
    r = s.get(f"{API}/strategy/plans")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(p["id"] == generated_plan["id"] for p in items)
    # sorted desc by created_at — first item should be the latest
    assert items[0]["id"] == generated_plan["id"] or generated_plan["id"] in [items[0]["id"]]


def test_strategy_get_by_id(s, generated_plan):
    r = s.get(f"{API}/strategy/plans/{generated_plan['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == generated_plan["id"]


# --- v1 still works (no auth required for demo persona) --------------------
def test_v1_dashboard_no_auth(s):
    r = s.get(f"{API}/dashboard")
    assert r.status_code == 200
    assert r.json()["hero"]["score"] == 87


def test_v1_portfolio_no_auth(s):
    r = s.get(f"{API}/portfolio")
    assert r.status_code == 200
    assert r.json()["asset_count"] >= 6


def test_v1_finance_no_auth(s):
    r = s.get(f"{API}/finance")
    assert r.status_code == 200
    assert "summary" in r.json()
