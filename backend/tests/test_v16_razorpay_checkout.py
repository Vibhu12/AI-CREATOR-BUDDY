"""v16 — Razorpay Payment Links integration tests (real test-mode keys are
configured in this environment: RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET).

Unlike the PayPal v12 tests (which exercise the mock-fallback path because
PayPal keys are empty here), these tests exercise the REAL Razorpay REST API
in test mode — create_payment_link actually calls api.razorpay.com. No real
money moves in test mode.

Signature verification is exercised directly against razorpay_client using
the real shared secret, since we can't complete an actual card payment on
Razorpay's hosted page from an automated test.
"""
import hashlib
import hmac
import os
import sys
import uuid

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))
import razorpay_client  # noqa: E402

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
from conftest import AUDIT_TOKEN as TOKEN

H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
NOAUTH = {"Content-Type": "application/json"}


def _get(path, headers=H, **kw):
    return requests.get(f"{BASE}{path}", headers=headers, timeout=30, **kw)


def _post(path, json=None, headers=H, **kw):
    return requests.post(f"{BASE}{path}", headers=headers, json=json, timeout=60, **kw)


def _sign(payment_link_id, reference_id, status, payment_id):
    message = "|".join([payment_link_id, reference_id, status, payment_id])
    return hmac.new(
        razorpay_client.RAZORPAY_KEY_SECRET.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


# ==========================================================================
# 1. Config reflects the real test-mode keys loaded in this environment
# ==========================================================================
def test_razorpay_status_reports_configured():
    r = _get("/api/billing/razorpay/status")
    assert r.status_code == 200, r.text
    assert r.json()["configured"] is True


# ==========================================================================
# 2. Auth gates
# ==========================================================================
def test_razorpay_create_link_requires_auth():
    r = requests.post(
        f"{BASE}/api/billing/razorpay/create-link",
        json={"tier": "pro", "return_url": "https://example.com/pricing", "callback_base_url": BASE},
        headers=NOAUTH, timeout=15,
    )
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


def test_razorpay_session_status_requires_auth():
    r = requests.get(f"{BASE}/api/billing/razorpay/status/does-not-exist", headers=NOAUTH, timeout=15)
    assert r.status_code == 401


# NOTE: /api/billing/razorpay/callback is intentionally PUBLIC (Razorpay's
# server redirects the paying user's bare browser here — no bearer token
# available). Verified via signature checks below, not an auth gate.


# ==========================================================================
# 3. create-link validation
# ==========================================================================
def test_razorpay_create_link_free_tier_rejected():
    r = _post("/api/billing/razorpay/create-link", json={
        "tier": "free", "return_url": "https://example.com/pricing", "callback_base_url": BASE,
    })
    assert r.status_code == 400, r.text


def test_razorpay_create_link_unknown_tier_rejected():
    r = _post("/api/billing/razorpay/create-link", json={
        "tier": "diamond", "return_url": "https://example.com/pricing", "callback_base_url": BASE,
    })
    assert r.status_code == 400, r.text


def test_razorpay_create_link_rejects_non_https_callback_base():
    r = _post("/api/billing/razorpay/create-link", json={
        "tier": "pro", "return_url": "https://example.com/pricing", "callback_base_url": "http://example.com",
    })
    assert r.status_code == 400, r.text


def test_razorpay_create_link_rejects_unsafe_return_url():
    r = _post("/api/billing/razorpay/create-link", json={
        "tier": "pro", "return_url": "javascript:alert(1)", "callback_base_url": BASE,
    })
    assert r.status_code == 400, r.text


# ==========================================================================
# 4. Happy path — real Razorpay API call, then simulated signed callback
# ==========================================================================
_state = {}


def test_razorpay_create_link_pro_real_api_call():
    _post("/api/billing/upgrade", json={"tier": "free"})  # reset

    r = _post("/api/billing/razorpay/create-link", json={
        "tier": "pro", "return_url": "https://example.com/pricing", "callback_base_url": BASE,
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["reference_id"].startswith("rzp_")
    assert j["short_url"].startswith("https://")
    # $29 * 83.0 rate * 100 paise
    assert j["amount_paise"] == round(29 * razorpay_client.USD_TO_INR_RATE * 100)
    _state["reference_id"] = j["reference_id"]


def test_razorpay_session_status_pending_before_payment():
    ref = _state["reference_id"]
    r = _get(f"/api/billing/razorpay/status/{ref}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    assert r.json()["tier"] == "pro"


def test_razorpay_callback_rejects_bad_signature():
    ref = _state["reference_id"]
    r = _get(
        "/api/billing/razorpay/callback",
        headers=NOAUTH,
        params={
            "razorpay_payment_id": "pay_fake123",
            "razorpay_payment_link_id": "plink_fake",
            "razorpay_payment_link_reference_id": ref,
            "razorpay_payment_link_status": "paid",
            "razorpay_signature": "not_a_real_signature",
        },
        allow_redirects=False,
    )
    assert r.status_code in (307, 302, 200), r.text
    # Tier must NOT have flipped from a forged callback
    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "free" or plan.get("id") == "free"


def test_razorpay_callback_flips_tier_with_valid_signature():
    ref = _state["reference_id"]
    # We need the real razorpay_payment_link_id that was stored server-side —
    # fetch it straight from Mongo since the create-link response doesn't
    # leak it to the client (client only needs short_url/reference_id).
    from pymongo import MongoClient
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    session = db.checkout_sessions.find_one({"reference_id": ref})
    assert session, "checkout session must exist"
    link_id = session["razorpay_payment_link_id"]
    client.close()

    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    sig = _sign(link_id, ref, "paid", payment_id)

    r = requests.get(
        f"{BASE}/api/billing/razorpay/callback",
        headers=NOAUTH,
        params={
            "razorpay_payment_id": payment_id,
            "razorpay_payment_link_id": link_id,
            "razorpay_payment_link_reference_id": ref,
            "razorpay_payment_link_status": "paid",
            "razorpay_signature": sig,
        },
        allow_redirects=False,
        timeout=15,
    )
    assert r.status_code in (307, 302), r.text
    assert "razorpay_status=success" in r.headers.get("location", "")

    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "pro" or plan.get("id") == "pro"

    status = _get(f"/api/billing/razorpay/status/{ref}").json()
    assert status["status"] == "complete"


def test_razorpay_callback_replay_does_not_duplicate_or_error():
    ref = _state["reference_id"]
    from pymongo import MongoClient
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    session = db.checkout_sessions.find_one({"reference_id": ref})
    link_id = session["razorpay_payment_link_id"]
    payment_id = session["razorpay_payment_id"]
    client.close()

    sig = _sign(link_id, ref, "paid", payment_id)
    r = requests.get(
        f"{BASE}/api/billing/razorpay/callback",
        headers=NOAUTH,
        params={
            "razorpay_payment_id": payment_id,
            "razorpay_payment_link_id": link_id,
            "razorpay_payment_link_reference_id": ref,
            "razorpay_payment_link_status": "paid",
            "razorpay_signature": sig,
        },
        allow_redirects=False,
        timeout=15,
    )
    assert r.status_code in (307, 302)
    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "pro" or plan.get("id") == "pro"


# ==========================================================================
# 5. Regression — PayPal + mock checkout untouched by this change
# ==========================================================================
def test_regression_paypal_status_still_unconfigured():
    r = _get("/api/billing/paypal/status")
    assert r.status_code == 200
    assert r.json()["configured"] is False


def test_regression_connections_still_four_providers():
    r = _get("/api/integrations/connections")
    assert r.status_code == 200
    assert len(r.json()["connections"]) == 4


# ==========================================================================
# Teardown
# ==========================================================================
def test_zz_teardown_restore_free_tier():
    r = _post("/api/billing/upgrade", json={"tier": "free"})
    assert r.status_code == 200
    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "free" or plan.get("id") == "free"
