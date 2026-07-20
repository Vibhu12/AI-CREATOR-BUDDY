"""v4 CreatorOS backend tests — billing tiers, editable strategy tasks, Instagram stub, IG onboarding.

Covers:
  - GET /api/billing/plans (3 tiers with popular flag on pro)
  - GET /api/billing/plan (401 without auth, includes free tier metadata for free user)
  - POST /api/billing/upgrade (mock-upgrades tier in Mongo; invalid tier => 400)
  - PATCH /api/strategy/plans/{id}/task (progress_pct calc, remove on uncheck)
  - Cross-user 404 on toggle_task
  - Invalid 'kind' => 400
  - Insert plan has task_progress:{}
  - GET /api/integrations/instagram/profile => 503 with FB app credentials message
  - POST /api/onboarding/complete strips @ from both youtube_handle & instagram_handle
  - Regression: GET /api/auth/me includes both handles
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") if os.environ.get("EXPO_PUBLIC_BACKEND_URL") else None
if not BASE_URL:
    # fall back to reading the frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

API = f"{BASE_URL}/api"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]


def _mk_user(prefix: str):
    """Insert an ephemeral user + session, return (user_id, token, headers)."""
    now = datetime.now(timezone.utc)
    user_id = f"user_v4_{prefix}_{uuid.uuid4().hex[:8]}"
    token = f"v4-token-{prefix}-{uuid.uuid4().hex[:8]}"
    _db.users.insert_one({
        "user_id": user_id,
        "email": f"TEST_{user_id}@example.com",
        "name": f"Test {prefix}",
        "picture": None,
        "onboarding_complete": True,
        "youtube_handle": None,
        "instagram_handle": None,
        "tier": "free",
        "created_at": now,
        "updated_at": now,
    })
    _db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "expires_at": now + timedelta(days=1),
        "created_at": now,
    })
    return user_id, token, {"Authorization": f"Bearer {token}"}


def _cleanup(user_id: str):
    for coll in ("users", "user_sessions", "strategy_plans", "assets", "goals", "content", "recommendations", "chat_messages"):
        _db[coll].delete_many({"user_id": user_id})
    _db.user_sessions.delete_many({"user_id": user_id})


@pytest.fixture
def user_a():
    uid, tok, hdr = _mk_user("a")
    yield uid, tok, hdr
    _cleanup(uid)


@pytest.fixture
def user_b():
    uid, tok, hdr = _mk_user("b")
    yield uid, tok, hdr
    _cleanup(uid)


# ---------- Billing ----------
class TestBilling:
    def test_plans_list(self):
        r = requests.get(f"{API}/billing/plans")
        assert r.status_code == 200
        data = r.json()
        tiers = {t["id"]: t for t in data["tiers"]}
        assert set(tiers.keys()) == {"free", "pro", "studio"}
        for t in tiers.values():
            assert "name" in t and "price_monthly" in t and "features" in t and "limits" in t and "cta" in t
        assert tiers["pro"].get("popular") is True
        assert tiers["free"]["price_monthly"] == 0
        assert tiers["pro"]["price_monthly"] == 29
        assert tiers["studio"]["price_monthly"] == 99

    def test_plan_401_without_auth(self):
        r = requests.get(f"{API}/billing/plan")
        assert r.status_code == 401

    def test_plan_free_default(self, user_a):
        _uid, _tok, hdr = user_a
        r = requests.get(f"{API}/billing/plan", headers=hdr)
        assert r.status_code == 200
        j = r.json()
        assert j["tier"] == "free"
        assert j["name"] == "Free"
        assert "features" in j and "limits" in j
        assert j["limits"]["chat_daily"] == 10

    def test_upgrade_to_pro_and_persists(self, user_a):
        uid, _tok, hdr = user_a
        r = requests.post(f"{API}/billing/upgrade", headers=hdr, json={"tier": "pro"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True and j["tier"] == "pro" and j["mocked"] is True

        # Verify db
        doc = _db.users.find_one({"user_id": uid})
        assert doc["tier"] == "pro"

        # Verify GET /plan reflects
        r2 = requests.get(f"{API}/billing/plan", headers=hdr)
        assert r2.status_code == 200
        assert r2.json()["tier"] == "pro"

    def test_upgrade_invalid_tier(self, user_a):
        _uid, _tok, hdr = user_a
        r = requests.post(f"{API}/billing/upgrade", headers=hdr, json={"tier": "enterprise"})
        assert r.status_code == 400


# ---------- Strategy task toggle ----------
def _seed_plan(user_id: str) -> str:
    plan_id = str(uuid.uuid4())
    _db.strategy_plans.insert_one({
        "id": plan_id,
        "user_id": user_id,
        "horizon_days": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "Test Plan",
        "summary": "seeded",
        "phases": [
            {"window": "Days 1-30", "theme": "Growth",
             "milestones": ["m1", "m2"],
             "weekly_tasks": ["w1", "w2", "w3", "w4"],
             "risk": "none"}
        ],
        "leading_indicators": ["li1", "li2"],
        "task_progress": {},
    })
    return plan_id


class TestStrategyTasks:
    def test_toggle_task_updates_progress(self, user_a):
        uid, _tok, hdr = user_a
        plan_id = _seed_plan(uid)
        # Total tasks = 2 milestones + 4 weekly + 2 li = 8 → 1 done = 12.5%
        r = requests.patch(
            f"{API}/strategy/plans/{plan_id}/task", headers=hdr,
            json={"phase_index": 0, "kind": "milestones", "task_index": 0, "checked": True},
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j["task_progress"].get("0.milestones.0") is True
        assert j["progress_pct"] == 12.5

        # Toggle back off → key removed, pct=0
        r2 = requests.patch(
            f"{API}/strategy/plans/{plan_id}/task", headers=hdr,
            json={"phase_index": 0, "kind": "milestones", "task_index": 0, "checked": False},
        )
        assert r2.status_code == 200
        j2 = r2.json()
        assert "0.milestones.0" not in j2["task_progress"]
        assert j2["progress_pct"] == 0

        # Persistence: reload via GET
        r3 = requests.get(f"{API}/strategy/plans/{plan_id}", headers=hdr)
        assert r3.status_code == 200
        assert r3.json().get("task_progress", {}) == {}

    def test_toggle_scopes_by_user(self, user_a, user_b):
        uid_a, _ta, ha = user_a
        _uid_b, _tb, hb = user_b
        plan_id = _seed_plan(uid_a)
        # user B tries to toggle A's plan → 404
        r = requests.patch(
            f"{API}/strategy/plans/{plan_id}/task", headers=hb,
            json={"phase_index": 0, "kind": "milestones", "task_index": 0, "checked": True},
        )
        assert r.status_code == 404

    def test_toggle_invalid_kind(self, user_a):
        uid, _tok, hdr = user_a
        plan_id = _seed_plan(uid)
        r = requests.patch(
            f"{API}/strategy/plans/{plan_id}/task", headers=hdr,
            json={"phase_index": 0, "kind": "junk", "task_index": 0, "checked": True},
        )
        assert r.status_code == 400

    def test_seeded_plan_has_task_progress_field(self, user_a):
        uid, _tok, hdr = user_a
        plan_id = _seed_plan(uid)
        r = requests.get(f"{API}/strategy/plans/{plan_id}", headers=hdr)
        assert r.status_code == 200
        assert "task_progress" in r.json()
        assert r.json()["task_progress"] == {}


# ---------- Instagram stub ----------
class TestInstagramStub:
    def test_ig_profile_503(self):
        r = requests.get(f"{API}/integrations/instagram/profile", params={"handle": "someone"})
        assert r.status_code == 503
        j = r.json()
        # FastAPI returns {"detail": "..."}
        msg = j.get("detail", "") if isinstance(j, dict) else str(j)
        assert "Instagram Graph API" in msg and "Facebook app credentials" in msg


# ---------- Onboarding with instagram_handle ----------
class TestOnboardingIG:
    def test_complete_saves_both_handles(self, user_a):
        uid, _tok, hdr = user_a
        r = requests.post(
            f"{API}/onboarding/complete", headers=hdr,
            json={"youtube_handle": "@mytube", "instagram_handle": "@mygram"},
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["youtube_handle"] == "mytube"
        assert j["instagram_handle"] == "mygram"
        # Verify via /auth/me
        r2 = requests.get(f"{API}/auth/me", headers=hdr)
        assert r2.status_code == 200
        u = r2.json()["user"]
        assert u["youtube_handle"] == "mytube"
        assert u["instagram_handle"] == "mygram"
        assert u["onboarding_complete"] is True


# ---------- v3 regression sanity ----------
class TestV3Regression:
    def test_dashboard_still_auth_gated(self):
        assert requests.get(f"{API}/dashboard").status_code == 401

    def test_portfolio_still_auth_gated(self):
        assert requests.get(f"{API}/portfolio").status_code == 401

    def test_root_still_public(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_stripe_status_public(self):
        r = requests.get(f"{API}/integrations/stripe/status")
        assert r.status_code == 200
        # placeholder key → connected:false expected
        assert "connected" in r.json()

    def test_competitors_public(self):
        r = requests.get(f"{API}/competitors")
        assert r.status_code == 200
        assert "you" in r.json()
