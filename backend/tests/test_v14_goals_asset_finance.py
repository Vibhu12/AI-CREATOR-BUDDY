"""v14 — Goals PATCH/DELETE, Asset detail, Finance enhancements.

Covers:
  A) PATCH /api/goals/{id} — happy path + validation guardrails + cross-user
  B) DELETE /api/goals/{id} — deletes; 2nd delete → 404
  C) GET /api/assets/{id} — full detail; cross-user 404; response shape
  D) GET /api/finance — new fields (by_asset, by_platform, expense_categories,
     projection, summary.forecast_90d)
  E) Auth — new endpoints require Bearer
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")

AUDIT_TOKEN = "audit-token"
AUDIT_UID = "user_audit"
H_AUDIT = {"Authorization": f"Bearer {AUDIT_TOKEN}", "Content-Type": "application/json"}

# Second user for cross-user isolation tests
OTHER_TOKEN = "v14-other-token"
OTHER_UID = "user_v14_other"
H_OTHER = {"Authorization": f"Bearer {OTHER_TOKEN}", "Content-Type": "application/json"}

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module", autouse=True)
def other_user(mongo):
    now = datetime.now(timezone.utc)
    mongo.users.update_one(
        {"user_id": OTHER_UID},
        {"$set": {
            "user_id": OTHER_UID, "email": "v14-other@test.local",
            "name": "V14 Other", "picture": None, "onboarding_complete": True,
            "youtube_handle": None, "tier": "free",
            "created_at": now, "updated_at": now,
        }},
        upsert=True,
    )
    mongo.user_sessions.update_one(
        {"session_token": OTHER_TOKEN},
        {"$set": {
            "session_token": OTHER_TOKEN, "user_id": OTHER_UID,
            "expires_at": now + timedelta(days=1), "created_at": now,
        }},
        upsert=True,
    )
    # Seed 1 goal + 1 asset for OTHER user for cross-user tests
    mongo.goals.delete_many({"user_id": OTHER_UID})
    mongo.assets.delete_many({"user_id": OTHER_UID})
    mongo.goals.insert_one({
        "id": "v14-other-goal", "user_id": OTHER_UID,
        "title": "Other user goal", "kind": "revenue", "target": 5000, "current": 100,
        "deadline": None, "created_at": now,
    })
    mongo.assets.insert_one({
        "id": "v14-other-asset", "user_id": OTHER_UID,
        "name": "Other's asset", "platform": "youtube", "category": "test",
        "revenue_mtd": 100, "profit_mtd": 50, "followers": 100, "ai_score": 70,
        "trend": [60, 65, 70], "created_at": now,
    })
    yield
    mongo.goals.delete_many({"user_id": OTHER_UID})
    mongo.assets.delete_many({"user_id": OTHER_UID})
    mongo.user_sessions.delete_one({"session_token": OTHER_TOKEN})
    mongo.users.delete_one({"user_id": OTHER_UID})


def _get(path, headers=H_AUDIT, **kw):
    return requests.get(f"{BASE}{path}", headers=headers, timeout=30, **kw)


def _post(path, json=None, headers=H_AUDIT, **kw):
    return requests.post(f"{BASE}{path}", headers=headers, json=json, timeout=30, **kw)


def _patch(path, json=None, headers=H_AUDIT, **kw):
    return requests.patch(f"{BASE}{path}", headers=headers, json=json, timeout=30, **kw)


def _delete(path, headers=H_AUDIT, **kw):
    return requests.delete(f"{BASE}{path}", headers=headers, timeout=30, **kw)


def _make_goal(title="TEST_V14 goal", current=100, target=1000):
    r = _post("/api/goals", {"title": title, "kind": "revenue",
                             "target": target, "current": current})
    assert r.status_code == 200, r.text
    return r.json()


# ==========================================================================
# A) PATCH /api/goals/{id}
# ==========================================================================
class TestGoalPatch:
    def test_a1_patch_current_updates(self, mongo):
        g = _make_goal(title="TEST_V14 patch happy")
        gid = g["id"]
        r = _patch(f"/api/goals/{gid}", {"current": 5000})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["current"] == 5000
        assert body["id"] == gid
        # GET verify persisted
        got = _get("/api/goals")
        found = next((x for x in got.json()["items"] if x["id"] == gid), None)
        assert found and found["current"] == 5000
        mongo.goals.delete_one({"id": gid})

    def test_a2_patch_empty_title_400(self, mongo):
        g = _make_goal(title="TEST_V14 empty title")
        r = _patch(f"/api/goals/{g['id']}", {"title": "   "})
        assert r.status_code == 400, r.text
        mongo.goals.delete_one({"id": g["id"]})

    def test_a3_patch_negative_current_400(self, mongo):
        g = _make_goal(title="TEST_V14 neg current")
        r = _patch(f"/api/goals/{g['id']}", {"current": -1})
        assert r.status_code == 400, r.text
        mongo.goals.delete_one({"id": g["id"]})

    def test_a4_patch_target_zero_400(self, mongo):
        g = _make_goal(title="TEST_V14 target zero")
        r = _patch(f"/api/goals/{g['id']}", {"target": 0})
        assert r.status_code == 400, r.text
        mongo.goals.delete_one({"id": g["id"]})

    def test_a5_patch_title_over_120_returns_413(self, mongo):
        g = _make_goal(title="TEST_V14 long title")
        long_title = "x" * 121
        r = _patch(f"/api/goals/{g['id']}", {"title": long_title})
        assert r.status_code == 413, r.text
        mongo.goals.delete_one({"id": g["id"]})

    def test_a6_patch_unknown_id_404(self):
        r = _patch(f"/api/goals/{uuid.uuid4()}", {"current": 100})
        assert r.status_code == 404, r.text

    def test_a7_cross_user_patch_returns_404(self):
        # audit user tries to patch OTHER user's goal
        r = _patch("/api/goals/v14-other-goal", {"current": 999})
        assert r.status_code == 404, r.text


# ==========================================================================
# B) DELETE /api/goals/{id}
# ==========================================================================
class TestGoalDelete:
    def test_b1_delete_then_delete_returns_404(self):
        g = _make_goal(title="TEST_V14 delete me")
        gid = g["id"]
        r1 = _delete(f"/api/goals/{gid}")
        assert r1.status_code == 200, r1.text
        r2 = _delete(f"/api/goals/{gid}")
        assert r2.status_code == 404, r2.text

    def test_b2_cross_user_delete_returns_404(self, mongo):
        r = _delete("/api/goals/v14-other-goal")
        assert r.status_code == 404, r.text
        # Verify it still exists in DB
        assert mongo.goals.find_one({"id": "v14-other-goal"}) is not None


# ==========================================================================
# C) GET /api/assets/{id}
# ==========================================================================
class TestAssetDetail:
    def test_c1_own_asset_returns_full_shape(self):
        # Get first asset from portfolio
        p = _get("/api/portfolio").json()
        assert p["assets"], "audit user has no assets — seed missing"
        asset_id = p["assets"][0]["id"]
        r = _get(f"/api/assets/{asset_id}")
        assert r.status_code == 200, r.text
        body = r.json()
        # Shape
        for key in ("asset", "content", "recommendations", "benchmarks", "kpis"):
            assert key in body, f"missing key {key}: {body.keys()}"
        assert body["asset"]["id"] == asset_id
        assert isinstance(body["content"], list)
        assert isinstance(body["recommendations"], list)
        # Benchmarks shape
        assert "top_1pct_followers" in body["benchmarks"]
        assert "top_1pct_revenue" in body["benchmarks"]
        # KPIs: list of 4 dicts
        assert isinstance(body["kpis"], list) and len(body["kpis"]) == 4
        for kpi in body["kpis"]:
            assert "label" in kpi and "value" in kpi

    def test_c2_cross_user_asset_returns_404(self):
        # audit user tries to fetch OTHER's asset
        r = _get("/api/assets/v14-other-asset")
        assert r.status_code == 404, r.text

    def test_c3_unknown_asset_returns_404(self):
        r = _get(f"/api/assets/{uuid.uuid4()}")
        assert r.status_code == 404, r.text


# ==========================================================================
# D) GET /api/finance — new fields
# ==========================================================================
class TestFinance:
    def test_d1_new_fields_present(self):
        r = _get("/api/finance")
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("by_asset", "by_platform", "expense_categories", "projection"):
            assert key in body, f"missing {key}: {list(body.keys())}"
        assert "forecast_90d" in body["summary"]

    def test_d2_by_asset_sorted_desc(self):
        r = _get("/api/finance")
        by_asset = r.json()["by_asset"]
        assert isinstance(by_asset, list) and len(by_asset) > 0
        revs = [a["revenue_mtd"] for a in by_asset]
        assert revs == sorted(revs, reverse=True), f"not sorted desc: {revs}"

    def test_d3_expense_categories_five_items_sum_100(self):
        r = _get("/api/finance")
        cats = r.json()["expense_categories"]
        assert isinstance(cats, list) and len(cats) == 5
        total_share = sum(c["share"] for c in cats)
        assert 99 <= total_share <= 101, f"share sum {total_share}"

    def test_d4_projection_shape_90_items(self):
        r = _get("/api/finance")
        proj = r.json()["projection"]
        assert isinstance(proj, list) and len(proj) == 90
        for item in proj[:3]:
            assert "date" in item and "revenue" in item and "expense" in item

    def test_d5_by_platform_present(self):
        r = _get("/api/finance")
        by_plat = r.json()["by_platform"]
        assert isinstance(by_plat, list) and len(by_plat) > 0
        assert "platform" in by_plat[0] and "revenue_mtd" in by_plat[0]


# ==========================================================================
# E) Auth guard on new endpoints
# ==========================================================================
class TestAuthGuard:
    def test_e1_patch_goal_no_auth_401(self):
        r = requests.patch(f"{BASE}/api/goals/anything", json={"current": 1}, timeout=10)
        assert r.status_code == 401, r.text

    def test_e2_delete_goal_no_auth_401(self):
        r = requests.delete(f"{BASE}/api/goals/anything", timeout=10)
        assert r.status_code == 401, r.text

    def test_e3_asset_detail_no_auth_401(self):
        r = requests.get(f"{BASE}/api/assets/anything", timeout=10)
        assert r.status_code == 401, r.text

    def test_e4_finance_no_auth_401(self):
        r = requests.get(f"{BASE}/api/finance", timeout=10)
        assert r.status_code == 401, r.text


# ==========================================================================
# F) Deprecation warning check
# ==========================================================================
class TestNoOnEventDeprecation:
    def test_f1_no_on_event_deprecation(self):
        try:
            with open("/var/log/supervisor/backend.err.log", "r") as f:
                content = f.read()
        except FileNotFoundError:
            pytest.skip("backend.err.log not found")
        # Only fail on on_event-related deprecation
        lines = [ln for ln in content.split("\n")
                 if "on_event is deprecated" in ln.lower()
                 or ("deprecationwarning" in ln.lower() and "on_event" in ln.lower())]
        assert not lines, f"Found on_event deprecation: {lines[:3]}"
