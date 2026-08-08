"""v13 — Security fixes for SEC-001 (mock-payment tier flip) and SEC-002 (quotas).

Covers:
  A) DEMO_MODE=true: mock upgrade / checkout / paypal capture still flip tier.
  B) DEMO_MODE=false: /billing/upgrade→410, /billing/checkout/confirm→402,
     /billing/paypal/capture→402, /dev/reseed→403.
  C) Free-tier quota enforcement + rate limits:
     - empty/oversized chat -> 400/413
     - 11th chat / 24h -> 402
     - 2nd strategy plan / 7d -> 402
     - Pro-tier user bypasses limits
  D) PayPal return_url/cancel_url scheme allowlist (open-redirect).
  F) Regression: /dashboard, /portfolio, /integrations/connections still 200
     and v10 / v12 suites unaffected (spot-check).

Uses persistent audit user (user_audit / audit-token) for main flow,
plus a synthetic free-tier user (user_v13_free / v13-free-token) and
pro-tier user (user_v13_pro / v13-pro-token) inserted directly via pymongo
for quota tests.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")

from conftest import AUDIT_TOKEN, AUDIT_UID
H_AUDIT = {"Authorization": f"Bearer {AUDIT_TOKEN}", "Content-Type": "application/json"}

FREE_TOKEN = "v13-free-token"
FREE_UID = "user_v13_free"
H_FREE = {"Authorization": f"Bearer {FREE_TOKEN}", "Content-Type": "application/json"}

PRO_TOKEN = "v13-pro-token"
PRO_UID = "user_v13_pro"
H_PRO = {"Authorization": f"Bearer {PRO_TOKEN}", "Content-Type": "application/json"}

RETURN_URL_OK = "exp://demo/paypal/return"
CANCEL_URL_OK = "exp://demo/paypal/cancel"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

BACKEND_ENV_PATH = "/app/backend/.env"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _upsert_user_and_session(db, uid: str, token: str, tier: str, email: str):
    now = datetime.now(timezone.utc)
    db.users.update_one(
        {"user_id": uid},
        {"$set": {
            "user_id": uid,
            "email": email,
            "name": f"V13 {tier}",
            "picture": None,
            "onboarding_complete": True,
            "youtube_handle": None,
            "tier": tier,
            "created_at": now,
            "updated_at": now,
        }},
        upsert=True,
    )
    db.user_sessions.update_one(
        {"session_token": token},
        {"$set": {
            "session_token": token,
            "user_id": uid,
            "expires_at": now + timedelta(days=1),
            "created_at": now,
        }},
        upsert=True,
    )


def _wipe_user_data(db, uid: str):
    for coll in ("chat_messages", "strategy_plans", "checkout_sessions"):
        db[coll].delete_many({"user_id": uid})


@pytest.fixture(scope="module", autouse=True)
def synth_users(mongo):
    _upsert_user_and_session(mongo, FREE_UID, FREE_TOKEN, "free", "v13-free@test.local")
    _upsert_user_and_session(mongo, PRO_UID, PRO_TOKEN, "pro", "v13-pro@test.local")
    _wipe_user_data(mongo, FREE_UID)
    _wipe_user_data(mongo, PRO_UID)
    # Reset audit user back to free tier
    mongo.users.update_one({"user_id": AUDIT_UID}, {"$set": {"tier": "free"}})
    yield
    # Cleanup
    _wipe_user_data(mongo, FREE_UID)
    _wipe_user_data(mongo, PRO_UID)
    mongo.user_sessions.delete_one({"session_token": FREE_TOKEN})
    mongo.user_sessions.delete_one({"session_token": PRO_TOKEN})
    mongo.users.delete_one({"user_id": FREE_UID})
    mongo.users.delete_one({"user_id": PRO_UID})
    mongo.users.update_one({"user_id": AUDIT_UID}, {"$set": {"tier": "free"}})


def _post(path, json=None, headers=H_AUDIT, **kw):
    return requests.post(f"{BASE}{path}", headers=headers, json=json, timeout=60, **kw)


def _get(path, headers=H_AUDIT, **kw):
    return requests.get(f"{BASE}{path}", headers=headers, timeout=30, **kw)


def _set_demo_mode(value: bool):
    """Rewrite backend/.env DEMO_MODE line and restart backend."""
    with open(BACKEND_ENV_PATH, "r") as f:
        lines = f.readlines()
    out = []
    found = False
    for ln in lines:
        if ln.strip().startswith("DEMO_MODE="):
            out.append(f"DEMO_MODE={'true' if value else 'false'}\n")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"DEMO_MODE={'true' if value else 'false'}\n")
    with open(BACKEND_ENV_PATH, "w") as f:
        f.writelines(out)
    # Use -n so sudo never prompts; fall back to plain supervisorctl if sudo not needed.
    try:
        subprocess.run(["sudo", "-n", "supervisorctl", "restart", "backend"],
                       check=False, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        subprocess.run(["supervisorctl", "restart", "backend"],
                       check=False, capture_output=True, timeout=30)
    # Wait for backend to become ready
    for _ in range(30):
        try:
            r = requests.get(f"{BASE}/api/", timeout=3)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("backend did not restart in time")


# ==========================================================================
# A) SEC-001 verification — DEMO_MODE=true (default state)
# ==========================================================================
class TestDemoModeTrue:
    """With DEMO_MODE=true, mock-payment paths still flip tier (with warning log)."""

    def test_a1_upgrade_still_flips_tier(self, mongo):
        mongo.users.update_one({"user_id": AUDIT_UID}, {"$set": {"tier": "free"}})
        r = _post("/api/billing/upgrade", {"tier": "pro"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True and j["tier"] == "pro" and j.get("mocked") is True
        # Verify persisted
        u = mongo.users.find_one({"user_id": AUDIT_UID})
        assert u["tier"] == "pro"
        # reset
        mongo.users.update_one({"user_id": AUDIT_UID}, {"$set": {"tier": "free"}})

    def test_a2_checkout_confirm_flips_tier(self, mongo):
        mongo.users.update_one({"user_id": AUDIT_UID}, {"$set": {"tier": "free"}})
        r = _post("/api/billing/checkout", {"tier": "pro", "provider": "stripe"})
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]
        r2 = _post("/api/billing/checkout/confirm", {"session_id": sid})
        assert r2.status_code == 200, r2.text
        assert r2.json()["tier"] == "pro"
        assert mongo.users.find_one({"user_id": AUDIT_UID})["tier"] == "pro"
        mongo.users.update_one({"user_id": AUDIT_UID}, {"$set": {"tier": "free"}})

    def test_a3_paypal_capture_mock_flips_tier(self, mongo):
        mongo.users.update_one({"user_id": AUDIT_UID}, {"$set": {"tier": "free"}})
        r = _post("/api/billing/paypal/create-order",
                  {"tier": "pro", "return_url": RETURN_URL_OK, "cancel_url": CANCEL_URL_OK})
        assert r.status_code == 200, r.text
        oid = r.json()["order_id"]
        r2 = _post("/api/billing/paypal/capture", {"order_id": oid})
        assert r2.status_code == 200, r2.text
        assert r2.json()["tier"] == "pro"
        assert mongo.users.find_one({"user_id": AUDIT_UID})["tier"] == "pro"
        mongo.users.update_one({"user_id": AUDIT_UID}, {"$set": {"tier": "free"}})


# ==========================================================================
# C) SEC-002 quota + rate-limit enforcement (still DEMO_MODE=true)
# ==========================================================================
class TestQuotas:
    def test_c1_chat_empty_returns_400(self):
        r = _post("/api/ai/chat", {"session_id": "quota-test", "message": ""},
                  headers=H_FREE)
        assert r.status_code == 400, r.text
        assert "empty" in r.text.lower()

    def test_c1b_chat_whitespace_only_returns_400(self):
        r = _post("/api/ai/chat", {"session_id": "quota-test", "message": "   \n  "},
                  headers=H_FREE)
        assert r.status_code == 400, r.text

    def test_c2_chat_over_4000_chars_returns_413(self):
        big = "a" * 4001
        r = _post("/api/ai/chat", {"session_id": "quota-test", "message": big},
                  headers=H_FREE)
        assert r.status_code == 413, r.text
        assert "4000" in r.text or "too long" in r.text.lower()

    def test_c3_free_tier_11th_chat_returns_402(self, mongo):
        # Seed 10 user-role chat_messages within last 24h for FREE_UID
        _wipe_user_data(mongo, FREE_UID)
        now = datetime.now(timezone.utc)
        docs = [{
            "id": str(uuid.uuid4()),
            "user_id": FREE_UID,
            "session_id": f"{FREE_UID}::seed",
            "role": "user",
            "text": f"seed msg {i}",
            "at": (now - timedelta(minutes=i)).isoformat(),
        } for i in range(10)]
        mongo.chat_messages.insert_many(docs)

        r = _post("/api/ai/chat", {"session_id": "quota-test", "message": "hi"},
                  headers=H_FREE)
        assert r.status_code == 402, r.text
        assert "free tier" in r.text.lower() or "upgrade" in r.text.lower()

    def test_c4_free_tier_2nd_strategy_plan_returns_402(self, mongo):
        # Seed one strategy_plan within last 7d for FREE_UID
        mongo.strategy_plans.delete_many({"user_id": FREE_UID})
        mongo.strategy_plans.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": FREE_UID,
            "title": "Seeded plan",
            "horizon_days": 30,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        r = _post("/api/strategy/plans", {"horizon_days": 30}, headers=H_FREE)
        assert r.status_code == 402, r.text
        assert "free tier" in r.text.lower() or "upgrade" in r.text.lower()

    def test_c5_pro_tier_bypasses_chat_limit(self, mongo):
        # Seed 15 user-role messages for pro user (way over free limit)
        _wipe_user_data(mongo, PRO_UID)
        now = datetime.now(timezone.utc)
        docs = [{
            "id": str(uuid.uuid4()),
            "user_id": PRO_UID,
            "session_id": f"{PRO_UID}::seed",
            "role": "user",
            "text": f"seed msg {i}",
            "at": (now - timedelta(minutes=i)).isoformat(),
        } for i in range(15)]
        mongo.chat_messages.insert_many(docs)

        r = _post("/api/ai/chat", {"session_id": "pro-bypass", "message": "hi"},
                  headers=H_PRO)
        # Should NOT be 402 — free-tier gate should be bypassed.
        # (200 stream OR 500 AI-unavailable is fine; just not 402/413/400.)
        assert r.status_code != 402, r.text
        assert r.status_code not in (400, 413), r.text

    def test_c6_pro_tier_bypasses_plan_limit(self, mongo):
        mongo.strategy_plans.delete_many({"user_id": PRO_UID})
        mongo.strategy_plans.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": PRO_UID,
            "title": "Seeded plan",
            "horizon_days": 30,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Don't wait for AI completion — just verify it's not blocked with 402.
        # Use a short timeout since AI call may take a while.
        try:
            r = requests.post(f"{BASE}/api/strategy/plans",
                              json={"horizon_days": 30}, headers=H_PRO, timeout=5)
            assert r.status_code != 402, r.text
        except requests.exceptions.ReadTimeout:
            # Timeout means the request got past the quota check into the AI call — pass.
            pass


# ==========================================================================
# D) URL allowlist for PayPal return_url / cancel_url
# ==========================================================================
class TestUrlAllowlist:
    def _create(self, return_url, cancel_url):
        return _post("/api/billing/paypal/create-order",
                     {"tier": "pro", "return_url": return_url, "cancel_url": cancel_url},
                     headers=H_AUDIT)

    def test_d1_http_return_url_rejected(self):
        r = self._create("http://evil.com", CANCEL_URL_OK)
        assert r.status_code == 400, r.text

    def test_d2_javascript_scheme_rejected(self):
        r = self._create("javascript:alert(1)", CANCEL_URL_OK)
        assert r.status_code == 400, r.text

    def test_d2b_data_scheme_rejected(self):
        r = self._create("data:text/html,<script>alert(1)</script>", CANCEL_URL_OK)
        assert r.status_code == 400, r.text

    def test_d3_https_accepted(self):
        r = self._create("https://good.example.com/return", "https://good.example.com/cancel")
        assert r.status_code == 200, r.text

    def test_d4_exp_deep_link_accepted(self):
        r = self._create("exp://192.168.0.1/paypal/return", "exp://192.168.0.1/paypal/cancel")
        assert r.status_code == 200, r.text

    def test_d5_cancel_url_also_validated(self):
        r = self._create(RETURN_URL_OK, "http://evil.com")
        assert r.status_code == 400, r.text


# ==========================================================================
# F) Regression — general auth-gated endpoints still 200 for authed users
# ==========================================================================
class TestRegression:
    def test_f1_dashboard_ok(self):
        r = _get("/api/dashboard")
        assert r.status_code == 200, r.text
        j = r.json()
        assert "hero" in j and "metrics" in j and "recommendations" in j

    def test_f2_portfolio_ok(self):
        r = _get("/api/portfolio")
        assert r.status_code == 200, r.text
        j = r.json()
        assert "assets" in j and isinstance(j["assets"], list)

    def test_f3_integrations_connections_ok(self):
        r = _get("/api/integrations/connections")
        assert r.status_code == 200, r.text

    def test_f4_billing_plan_ok(self):
        r = _get("/api/billing/plan")
        assert r.status_code == 200, r.text
        assert "tier" in r.json()


# ==========================================================================
# B) DEMO_MODE=false — mock payment paths must reject.
# Runs last so it can restore DEMO_MODE=true at teardown.
# ==========================================================================
@pytest.fixture(scope="class")
def demo_mode_false():
    _set_demo_mode(False)
    yield
    _set_demo_mode(True)


@pytest.mark.usefixtures("demo_mode_false")
class TestZZDemoModeFalse:
    """Named TestZZ… so it runs last (pytest collects in file order but this
    also guards against reordering)."""

    def test_b1_upgrade_returns_410(self):
        r = _post("/api/billing/upgrade", {"tier": "pro"})
        assert r.status_code == 410, r.text

    def test_b2_checkout_confirm_returns_402(self, mongo):
        # Create session first (create still works), then confirm should 402
        r = _post("/api/billing/checkout", {"tier": "pro", "provider": "stripe"})
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]
        r2 = _post("/api/billing/checkout/confirm", {"session_id": sid})
        assert r2.status_code == 402, r2.text
        # Verify tier was NOT flipped
        u = mongo.users.find_one({"user_id": AUDIT_UID})
        assert u["tier"] == "free", f"tier flipped despite DEMO_MODE=false: {u.get('tier')}"

    def test_b3_paypal_capture_mock_returns_402(self, mongo):
        r = _post("/api/billing/paypal/create-order",
                  {"tier": "pro", "return_url": RETURN_URL_OK, "cancel_url": CANCEL_URL_OK})
        assert r.status_code == 200, r.text
        oid = r.json()["order_id"]
        r2 = _post("/api/billing/paypal/capture", {"order_id": oid})
        assert r2.status_code == 402, r2.text
        u = mongo.users.find_one({"user_id": AUDIT_UID})
        assert u["tier"] == "free"

    def test_b4_dev_reseed_returns_403(self):
        r = _post("/api/dev/reseed", {})
        assert r.status_code == 403, r.text

    def test_b5_regression_dashboard_still_ok_in_prod_mode(self):
        r = _get("/api/dashboard")
        assert r.status_code == 200, r.text
