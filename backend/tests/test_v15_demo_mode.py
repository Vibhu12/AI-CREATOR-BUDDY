"""Tests for the demo_mode toggle feature (v15).

Covers:
  - TestDefaultDemoTrue: demo_mode=true (default) preserves exact legacy
    Maya hero/dashboard/portfolio/finance/goals behavior.
  - TestGoalRegressionInDemoTrue: CRITICAL regression — creating a real goal
    while demo_mode=true must remain immediately visible/editable/deletable
    (the asymmetric filter design).
  - TestDemoFalse: toggling to demo_mode=false hides seeded Maya data and
    shows only real user-added records, with honest 0/empty states.
  - TestToggleEndpoint: PATCH /profile/demo-mode persists + round-trips.
  - TestReseedPreservesRealData: POST /dev/reseed only wipes is_demo:True
    records, never touches real user data.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

from conftest import MONGO_URL, DB_NAME

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")


@pytest.fixture(scope="module")
def demo_user():
    """A fresh user seeded with the Maya starter dataset via /api/dashboard
    (which calls seed_user_starter), isolated from the shared audit user."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc)
    uid = f"user_demotest_{secrets.token_hex(6)}"
    token = f"test_{secrets.token_urlsafe(24)}"
    db.users.insert_one({
        "user_id": uid,
        "email": f"{uid}@creatoros.test",
        "name": "Demo Tester",
        "picture": None,
        "onboarding_complete": True,
        "tier": "free",
        "demo_mode": True,
        "created_at": now,
        "updated_at": now,
    })
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": uid,
        "expires_at": now + timedelta(hours=2),
        "created_at": now,
    })
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    yield {"uid": uid, "token": token, "session": session}

    # Teardown
    db.user_sessions.delete_many({"session_token": token})
    db.users.delete_many({"user_id": uid})
    for coll in ("assets", "goals", "content", "recommendations", "notifications",
                 "strategy_plans", "chat_messages"):
        db[coll].delete_many({"user_id": uid})
    client.close()


class TestDefaultDemoTrue:
    """demo_mode=true (default) must look EXACTLY like legacy Maya behavior."""

    def test_a1_dashboard_hero_matches_legacy_maya(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/dashboard")
        assert r.status_code == 200
        d = r.json()
        assert d["demo_mode"] is True
        assert d["hero"]["score"] == 87
        breakdown = {b["label"]: b["value"] for b in d["hero"]["breakdown"]}
        assert breakdown == {"Growth": 91, "Financial": 84, "Content": 88, "Brand": 79}
        assert len(d["alerts"]) == 2
        metrics = {m["key"]: m["delta"] for m in d["metrics"]}
        assert metrics == {"revenue": 12.4, "profit": 9.1, "margin": 1.8, "followers": 4.6}

    def test_a2_portfolio_has_3_seeded_assets(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/portfolio")
        assert r.status_code == 200
        d = r.json()
        assert d["asset_count"] == 3
        names = {a["name"] for a in d["assets"]}
        assert "Ship It — Course" in names

    def test_a3_finance_has_hardcoded_transactions(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/finance")
        assert r.status_code == 200
        d = r.json()
        assert len(d["transactions"]) == 5
        assert d["summary"]["runway_months"] == 14.2

    def test_a4_goals_has_3_seeded(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/goals")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 3


class TestGoalRegressionInDemoTrue:
    """CRITICAL: creating a real goal while demo_mode=true must remain
    immediately visible + editable + deletable."""

    def test_b1_create_goal_visible_immediately(self, demo_user):
        payload = {"title": "TEST_real goal", "kind": "revenue", "target": 5000, "current": 0}
        r = demo_user["session"].post(f"{BASE_URL}/api/goals", json=payload)
        assert r.status_code == 200
        goal = r.json()
        goal_id = goal["id"]

        # GET goals -> new goal must appear (demo_mode true = no filter, sees everything)
        r2 = demo_user["session"].get(f"{BASE_URL}/api/goals")
        ids = [g["id"] for g in r2.json()["items"]]
        assert goal_id in ids

        # PATCH immediately after creation
        r3 = demo_user["session"].patch(f"{BASE_URL}/api/goals/{goal_id}", json={"current": 1200})
        assert r3.status_code == 200, r3.text
        assert r3.json()["current"] == 1200

        # DELETE immediately after
        r4 = demo_user["session"].delete(f"{BASE_URL}/api/goals/{goal_id}")
        assert r4.status_code == 200
        assert r4.json()["ok"] is True

        # Verify gone
        r5 = demo_user["session"].get(f"{BASE_URL}/api/goals")
        ids_after = [g["id"] for g in r5.json()["items"]]
        assert goal_id not in ids_after


class TestDemoFalse:
    """Toggling demo_mode=false must hide seeded Maya data and show clean
    0/empty states for a user with no real data."""

    def test_c0_toggle_off(self, demo_user):
        r = demo_user["session"].patch(f"{BASE_URL}/api/profile/demo-mode", json={"demo_mode": False})
        assert r.status_code == 200
        assert r.json() == {"ok": True, "demo_mode": False}

    def test_c1_dashboard_zero_state(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/dashboard")
        assert r.status_code == 200
        d = r.json()
        assert d["demo_mode"] is False
        assert d["hero"]["score"] == 0
        assert d["alerts"] == []
        assert "connect an integration" in d["subtitle"]
        metrics = {m["key"]: m["value"] for m in d["metrics"]}
        assert metrics["revenue"] == 0
        assert metrics["followers"] == 0

    def test_c2_portfolio_empty(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/portfolio")
        d = r.json()
        assert d["asset_count"] == 0
        assert d["assets"] == []

    def test_c3_finance_zero_state(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/finance")
        d = r.json()
        assert d["summary"]["revenue_30d"] == 0
        assert d["summary"]["runway_months"] == 0
        assert d["transactions"] == []
        assert d["expense_categories"] == []

    def test_c4_goals_empty(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/goals")
        assert r.json()["items"] == []

    def test_c5_content_empty(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/content")
        assert r.json()["items"] == []

    def test_c6_recommendations_empty(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/recommendations")
        assert r.json()["items"] == []

    def test_c7_notifications_empty(self, demo_user):
        r = demo_user["session"].get(f"{BASE_URL}/api/notifications")
        d = r.json()
        assert d["items"] == []
        assert d["unread"] == 0

    def test_c8_seeded_asset_detail_404s(self, demo_user):
        # Grab a seeded asset id directly from mongo, confirm it 404s now
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        seeded = db.assets.find_one({"user_id": demo_user["uid"], "is_demo": True})
        client.close()
        assert seeded is not None
        r = demo_user["session"].get(f"{BASE_URL}/api/assets/{seeded['id']}")
        assert r.status_code == 404

    def test_c9_toggle_back_on_restores_maya(self, demo_user):
        r = demo_user["session"].patch(f"{BASE_URL}/api/profile/demo-mode", json={"demo_mode": True})
        assert r.status_code == 200
        r2 = demo_user["session"].get(f"{BASE_URL}/api/dashboard")
        d = r2.json()
        assert d["demo_mode"] is True
        assert d["hero"]["score"] == 87
        r3 = demo_user["session"].get(f"{BASE_URL}/api/portfolio")
        assert r3.json()["asset_count"] == 3


class TestReseedPreservesRealData:
    """POST /dev/reseed must wipe only is_demo:True records, never real
    user data (the pre-existing bug fixed in this session)."""

    def test_d1_reseed_preserves_real_goal(self, demo_user):
        # DEMO_MODE env must be true for this endpoint to be enabled
        demo_env = os.environ.get("DEMO_MODE", "false").strip().lower()
        if demo_env != "true":
            pytest.skip("DEMO_MODE is not 'true' in backend env; /dev/reseed disabled (403 expected)")

        # Add a real (non-demo) goal
        payload = {"title": "TEST_survives_reseed", "kind": "content", "target": 10, "current": 1}
        r = demo_user["session"].post(f"{BASE_URL}/api/goals", json=payload)
        assert r.status_code == 200
        real_goal_id = r.json()["id"]

        # Reseed
        r2 = demo_user["session"].post(f"{BASE_URL}/api/dev/reseed")
        assert r2.status_code == 200

        # Real goal must still exist
        r3 = demo_user["session"].get(f"{BASE_URL}/api/goals")
        ids = [g["id"] for g in r3.json()["items"]]
        assert real_goal_id in ids, "Reseed wiped real user data — regression!"

        # Seeded goals must still be present too (idempotent reseed)
        r4 = demo_user["session"].get(f"{BASE_URL}/api/portfolio")
        assert r4.json()["asset_count"] == 3
