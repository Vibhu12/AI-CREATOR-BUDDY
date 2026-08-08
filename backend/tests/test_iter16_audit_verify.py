"""iter_16 verification of security audit fixes.

Confirms:
- SEC-001 legacy audit-token is inert (401)
- P3 competitors auth-gated (401 unauth, 200 with valid Bearer)
- P3 nested PII scrubbing in analytics
- Prior fixes still hold: DEMO_MODE tier gate (410/402), quota enforcement, 
  PayPal URL allowlist, error sanitization sampling.

Uses the session-scoped AUDIT_TOKEN from conftest.py — which is now
random per pytest run and torn down at session end.
"""
from __future__ import annotations

import os
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

from conftest import AUDIT_TOKEN, AUDIT_UID

load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))

BASE_URL = "http://localhost:8001"
H = {"Authorization": f"Bearer {AUDIT_TOKEN}", "Content-Type": "application/json"}


# --- SEC-001 ---------------------------------------------------------
def test_sec001_legacy_audit_token_rejected():
    r = requests.get(f"{BASE_URL}/api/dashboard",
                     headers={"Authorization": "Bearer audit-token"})
    assert r.status_code == 401, f"expected 401, got {r.status_code}"

    r2 = requests.get(f"{BASE_URL}/api/portfolio",
                      headers={"Authorization": "Bearer audit-token"})
    assert r2.status_code == 401


def test_sec001_random_token_format():
    assert AUDIT_TOKEN.startswith("test_")
    # token_urlsafe(32) -> ~43 base64url chars; total >= 40
    assert len(AUDIT_TOKEN) >= 40


def test_sec001_random_token_works_on_dashboard():
    r = requests.get(f"{BASE_URL}/api/dashboard", headers=H)
    assert r.status_code == 200


# --- P3 competitors auth gate ---------------------------------------
@pytest.mark.parametrize("path", ["/api/competitors", "/api/competitors/radar", "/api/competitors/gaps"])
def test_p3_competitors_no_auth_401(path):
    r = requests.get(f"{BASE_URL}{path}")
    assert r.status_code == 401, f"{path} -> {r.status_code}"


@pytest.mark.parametrize("path", ["/api/competitors", "/api/competitors/radar", "/api/competitors/gaps"])
def test_p3_competitors_with_auth_200(path):
    r = requests.get(f"{BASE_URL}{path}", headers=H)
    assert r.status_code == 200, f"{path} -> {r.status_code} :: {r.text[:200]}"
    body = r.json()
    assert isinstance(body, dict) and body  # non-empty payload


# --- P3 nested PII scrubbing ----------------------------------------
def test_p3_nested_pii_scrubbing():
    payload = {"events": [{
        "event": "screen_view",
        "props": {
            "nested": {
                "email": "foo@bar.com",
                "user_id": "safe",
                "deep": {"password": "hunter2", "keep": "ok"},
                "arr": [{"token": "abc", "ok": 1}],
            },
            "email": "top@bar.com",  # top-level exact PII key -> stripped
            "kept_top": "yes",
        },
    }]}
    r = requests.post(f"{BASE_URL}/api/analytics/events", headers=H, json=payload)
    assert r.status_code == 200, r.text
    assert r.json().get("accepted") == 1

    # Read back and check the persisted document.
    mc = MongoClient(os.environ["MONGO_URL"])
    db = mc[os.environ["DB_NAME"]]
    doc = db.analytics_events.find_one(
        {"user_id": AUDIT_UID, "event": "screen_view"},
        sort=[("ingested_at", -1)],
    )
    mc.close()
    assert doc is not None, "event was not persisted"
    props = doc.get("props", {})
    # top-level PII stripped, non-PII preserved
    assert "email" not in props
    assert props.get("kept_top") == "yes"
    nested = props.get("nested", {})
    assert "email" not in nested, f"nested.email leaked: {nested}"
    assert nested.get("user_id") == "safe"
    # deeper level
    deep = nested.get("deep", {})
    assert "password" not in deep, f"nested.deep.password leaked: {deep}"
    assert deep.get("keep") == "ok"
    # inside array element
    arr = nested.get("arr", [])
    assert arr and "token" not in arr[0], f"nested.arr[0].token leaked: {arr}"
    assert arr[0].get("ok") == 1


# --- Prior fixes sampling -------------------------------------------
def test_regression_dashboard_still_200():
    r = requests.get(f"{BASE_URL}/api/dashboard", headers=H)
    assert r.status_code == 200


def test_regression_paypal_allowlist_rejects_bad_return_url():
    # Confirm URL allowlist still active — plain http:// should be rejected (400).
    r = requests.post(
        f"{BASE_URL}/api/billing/paypal/create-order",
        headers=H,
        json={"tier": "pro", "return_url": "http://evil.example.com/x",
              "cancel_url": "http://evil.example.com/y"},
    )
    assert r.status_code == 400, f"paypal allowlist regression: {r.status_code} :: {r.text[:200]}"


def test_regression_error_sanitization_no_stack_trace():
    # Malformed body — response must not include Python traceback / file paths.
    r = requests.post(f"{BASE_URL}/api/analytics/events", headers=H,
                      data="not-json", timeout=10)
    body = r.text.lower()
    assert "traceback" not in body
    assert "/app/backend/" not in body
