"""v12 — PayPal Orders v2 integration tests.

The PayPal env keys (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET) are intentionally
empty in this environment, so we're exercising the mock-fallback path in
`/app/backend/billing.py`.

Reuses the persistent audit user (`user_audit` / token `audit-token`)
established in prior iterations.
"""
import os
import uuid
import requests

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
TOKEN = "audit-token"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
NOAUTH = {"Content-Type": "application/json"}

RETURN_URL = "exp://demo/paypal/return"
CANCEL_URL = "exp://demo/paypal/cancel"


def _get(path, headers=H, **kw):
    return requests.get(f"{BASE}{path}", headers=headers, timeout=30, **kw)


def _post(path, json=None, headers=H, **kw):
    return requests.post(f"{BASE}{path}", headers=headers, json=json, timeout=60, **kw)


# ==========================================================================
# 1. PayPal /status endpoint
# ==========================================================================
def test_paypal_status_reports_unconfigured():
    r = _get("/api/billing/paypal/status")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["configured"] is False
    assert j["mode"] is None


# ==========================================================================
# 2. Auth gate on create-order + capture (paypal/status has no auth in impl)
# ==========================================================================
def test_paypal_create_order_requires_auth():
    r = requests.post(
        f"{BASE}/api/billing/paypal/create-order",
        json={"tier": "pro", "return_url": RETURN_URL, "cancel_url": CANCEL_URL},
        headers=NOAUTH, timeout=15,
    )
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


def test_paypal_capture_requires_auth():
    r = requests.post(
        f"{BASE}/api/billing/paypal/capture",
        json={"order_id": "cs_paypal_dummy"},
        headers=NOAUTH, timeout=15,
    )
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


# ==========================================================================
# 3. Create-order — mock-fallback path (keys empty)
# ==========================================================================
_state = {}


def test_paypal_create_order_pro_mock_fallback():
    # Reset tier to free first
    _post("/api/billing/upgrade", json={"tier": "free"})

    r = _post(
        "/api/billing/paypal/create-order",
        json={"tier": "pro", "return_url": RETURN_URL, "cancel_url": CANCEL_URL},
    )
    assert r.status_code == 200, r.text
    j = r.json()

    # Contract per review request
    assert j.get("mocked") is True
    assert j.get("provider") == "paypal"
    assert j.get("tier") == "pro"
    assert j.get("amount") == 29
    assert j.get("approval_url") is None
    assert j.get("status") == "pending"
    order_id = j.get("order_id")
    assert isinstance(order_id, str) and order_id.startswith("cs_paypal_"), order_id

    _state["pro_order_id"] = order_id


def test_paypal_create_order_studio_amount():
    _post("/api/billing/upgrade", json={"tier": "free"})
    r = _post(
        "/api/billing/paypal/create-order",
        json={"tier": "studio", "return_url": RETURN_URL, "cancel_url": CANCEL_URL},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["tier"] == "studio"
    assert j["amount"] == 99
    assert j["mocked"] is True
    assert j["order_id"].startswith("cs_paypal_")
    _state["studio_order_id"] = j["order_id"]


def test_paypal_create_order_free_rejected():
    r = _post(
        "/api/billing/paypal/create-order",
        json={"tier": "free", "return_url": RETURN_URL, "cancel_url": CANCEL_URL},
    )
    assert r.status_code == 400, r.text


def test_paypal_create_order_unknown_tier_rejected():
    r = _post(
        "/api/billing/paypal/create-order",
        json={"tier": "diamond", "return_url": RETURN_URL, "cancel_url": CANCEL_URL},
    )
    assert r.status_code == 400, r.text


# ==========================================================================
# 4. Capture — happy path flips tier & persists
# ==========================================================================
def test_paypal_capture_flips_tier_to_pro():
    order_id = _state.get("pro_order_id")
    assert order_id, "create-order test must have run first"

    r = _post("/api/billing/paypal/capture", json={"order_id": order_id})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    assert j.get("tier") == "pro"
    assert j.get("provider") == "paypal"
    assert j.get("mocked") is True

    # Verify tier reflected on /billing/plan (i.e. persisted to db.users)
    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "pro" or plan.get("id") == "pro"


def test_paypal_capture_idempotent_second_call():
    order_id = _state.get("pro_order_id")
    assert order_id
    r = _post("/api/billing/paypal/capture", json={"order_id": order_id})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("already_complete") is True
    assert j.get("tier") == "pro"


def test_paypal_capture_studio_order_flips_tier():
    order_id = _state.get("studio_order_id")
    assert order_id
    r = _post("/api/billing/paypal/capture", json={"order_id": order_id})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["tier"] == "studio"
    assert j["mocked"] is True

    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "studio" or plan.get("id") == "studio"


# ==========================================================================
# 5. Capture unknown order → 404
# ==========================================================================
def test_paypal_capture_unknown_order_returns_404():
    r = _post(
        "/api/billing/paypal/capture",
        json={"order_id": f"cs_paypal_does_not_exist_{uuid.uuid4().hex[:8]}"},
    )
    assert r.status_code == 404, r.text


# ==========================================================================
# 6. Regression — Connections Hub + legacy checkout untouched (iter_11)
# ==========================================================================
def test_regression_connections_lists_four_providers():
    r = _get("/api/integrations/connections")
    assert r.status_code == 200, r.text
    conns = r.json().get("connections")
    assert isinstance(conns, list) and len(conns) == 4
    ids = {c["id"] for c in conns}
    assert ids == {"youtube", "instagram", "stripe", "paypal"}


def test_regression_legacy_checkout_still_works():
    # Reset first
    _post("/api/billing/upgrade", json={"tier": "free"})
    r = _post("/api/billing/checkout", json={"tier": "pro", "provider": "stripe"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["session_id"].startswith("cs_stripe_")
    assert j["tier"] == "pro"
    assert j["amount"] == 29
    assert j["status"] == "pending"

    # Confirm to flip tier
    r2 = _post("/api/billing/checkout/confirm", json={"session_id": j["session_id"]})
    assert r2.status_code == 200, r2.text
    assert r2.json()["tier"] == "pro"


def test_regression_legacy_upgrade_still_works():
    r = _post("/api/billing/upgrade", json={"tier": "studio"})
    assert r.status_code == 200
    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "studio" or plan.get("id") == "studio"


# ==========================================================================
# Teardown — restore tier to free so downstream tests are clean
# ==========================================================================
def test_zz_teardown_restore_free_tier():
    r = _post("/api/billing/upgrade", json={"tier": "free"})
    assert r.status_code == 200
    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "free" or plan.get("id") == "free"
