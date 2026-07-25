"""v10 — Connections Hub (YouTube/Instagram/Stripe/PayPal) + Stripe/PayPal
Checkout Flow tests.

Reuses the persistent audit user (`user_audit` / token `audit-token`)
established in the v9 iteration_10 seed. Tests are ordered so that
disconnect happens at the end and tier is restored to free.
"""
import os
import uuid
import requests

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
TOKEN = "audit-token"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def _get(path, headers=H, **kw):
    return requests.get(f"{BASE}{path}", headers=headers, timeout=30, **kw)


def _post(path, json=None, headers=H, **kw):
    return requests.post(f"{BASE}{path}", headers=headers, json=json, timeout=60, **kw)


# ==========================================================================
# Auth gate — every integrations & billing endpoint requires bearer
# ==========================================================================
def test_connections_requires_auth():
    r = requests.get(f"{BASE}/api/integrations/connections", timeout=15)
    assert r.status_code == 401


def test_connect_requires_auth():
    r = requests.post(
        f"{BASE}/api/integrations/youtube/connect",
        json={"account": "@x"}, timeout=15,
    )
    assert r.status_code == 401


def test_checkout_requires_auth():
    r = requests.post(
        f"{BASE}/api/billing/checkout",
        json={"tier": "pro", "provider": "stripe"}, timeout=15,
    )
    assert r.status_code == 401


# ==========================================================================
# Baseline — 4 providers listed, initially disconnected (after cleanup)
# ==========================================================================
def test_baseline_disconnect_all_then_list():
    for p in ("youtube", "instagram", "stripe", "paypal"):
        _post(f"/api/integrations/{p}/disconnect", json={})
    r = _get("/api/integrations/connections")
    assert r.status_code == 200, r.text
    conns = r.json().get("connections")
    assert isinstance(conns, list) and len(conns) == 4
    ids = {c["id"] for c in conns}
    assert ids == {"youtube", "instagram", "stripe", "paypal"}
    for c in conns:
        assert c["connected"] is False
        assert c.get("summary") is None
        assert "name" in c and "description" in c and "color" in c


# ==========================================================================
# YouTube connect → list → detail → disconnect
# ==========================================================================
def test_youtube_connect_flow():
    r = _post("/api/integrations/youtube/connect", json={"account": "@testchannel"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    conn = j.get("connection")
    assert conn and "subs" in conn["summary"]["primary_metric"]

    lst = _get("/api/integrations/connections").json()["connections"]
    yt = next(c for c in lst if c["id"] == "youtube")
    assert yt["connected"] is True
    assert yt["summary"] is not None
    assert yt["account"] == "testchannel"

    ch = _get("/api/integrations/youtube/channel").json()
    for k in ("subscribers", "recent_videos", "avg_rpm", "monthly_earnings"):
        assert k in ch, f"missing {k}"
    assert isinstance(ch["recent_videos"], list) and len(ch["recent_videos"]) >= 1


def test_youtube_channel_404_when_disconnected():
    _post("/api/integrations/youtube/disconnect", json={})
    r = _get("/api/integrations/youtube/channel")
    assert r.status_code == 404
    # Reconnect for downstream regression
    _post("/api/integrations/youtube/connect", json={"account": "@testchannel"})


# ==========================================================================
# Instagram
# ==========================================================================
def test_instagram_connect_and_profile():
    r = _post("/api/integrations/instagram/connect", json={"account": "@maya"})
    assert r.status_code == 200
    assert "followers" in r.json()["connection"]["summary"]["primary_metric"]
    prof = _get("/api/integrations/instagram/profile").json()
    for k in ("followers", "engagement_rate", "recent_reels"):
        assert k in prof


def test_instagram_profile_404_when_disconnected():
    _post("/api/integrations/instagram/disconnect", json={})
    r = _get("/api/integrations/instagram/profile")
    assert r.status_code == 404


# ==========================================================================
# Stripe
# ==========================================================================
def test_stripe_status_when_disconnected():
    _post("/api/integrations/stripe/disconnect", json={})
    j = _get("/api/integrations/stripe/status").json()
    assert j["connected"] is False


def test_stripe_connect_and_status():
    r = _post("/api/integrations/stripe/connect", json={"account": "biz@example.com"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert "available" in j["connection"]["summary"]["primary_metric"]

    s = _get("/api/integrations/stripe/status").json()
    assert s["connected"] is True
    assert isinstance(s["available_balance"], (int, float))
    assert isinstance(s["recent_charges"], list) and len(s["recent_charges"]) >= 1


# ==========================================================================
# PayPal
# ==========================================================================
def test_paypal_connect_and_status():
    r = _post("/api/integrations/paypal/connect", json={"account": "biz@paypal.com"})
    assert r.status_code == 200
    p = _get("/api/integrations/paypal/status").json()
    assert p["connected"] is True
    assert isinstance(p["available_balance"], (int, float))
    assert isinstance(p["recent_transactions"], list) and len(p["recent_transactions"]) >= 1


def test_paypal_status_when_disconnected():
    _post("/api/integrations/paypal/disconnect", json={})
    j = _get("/api/integrations/paypal/status").json()
    assert j["connected"] is False


# ==========================================================================
# Unknown provider / empty account
# ==========================================================================
def test_connect_unknown_provider():
    r = _post("/api/integrations/bogus/connect", json={"account": "x"})
    assert r.status_code == 400


def test_connect_empty_account():
    r = _post("/api/integrations/youtube/connect", json={"account": "   "})
    assert r.status_code == 400


# ==========================================================================
# Billing checkout
# ==========================================================================
_state = {}


def test_checkout_pro_stripe_creates_session():
    # Reset to free first via legacy upgrade
    _post("/api/billing/upgrade", json={"tier": "free"})
    r = _post("/api/billing/checkout", json={"tier": "pro", "provider": "stripe"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["session_id"].startswith("cs_stripe_")
    assert j["status"] == "pending"
    assert j["amount"] == 29
    assert j["tier"] == "pro"
    assert j["currency"] == "usd"
    _state["sid"] = j["session_id"]


def test_checkout_free_rejected():
    r = _post("/api/billing/checkout", json={"tier": "free", "provider": "stripe"})
    assert r.status_code == 400


def test_checkout_unknown_tier_rejected():
    r = _post("/api/billing/checkout", json={"tier": "diamond", "provider": "stripe"})
    assert r.status_code == 400


def test_checkout_confirm_flips_tier():
    sid = _state.get("sid")
    assert sid, "prior checkout test must have run"
    r = _post("/api/billing/checkout/confirm", json={"session_id": sid})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["tier"] == "pro"

    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "pro" or plan.get("id") == "pro"


def test_checkout_confirm_bad_session():
    r = _post("/api/billing/checkout/confirm", json={"session_id": "cs_stripe_nope"})
    assert r.status_code == 404


def test_checkout_paypal_provider():
    _post("/api/billing/upgrade", json={"tier": "free"})
    r = _post("/api/billing/checkout", json={"tier": "pro", "provider": "paypal"})
    assert r.status_code == 200
    j = r.json()
    assert j["session_id"].startswith("cs_paypal_")
    assert j["provider"] == "paypal"
    # Confirm it
    r2 = _post("/api/billing/checkout/confirm", json={"session_id": j["session_id"]})
    assert r2.status_code == 200
    assert r2.json()["tier"] == "pro"


def test_legacy_upgrade_still_works():
    r = _post("/api/billing/upgrade", json={"tier": "studio"})
    assert r.status_code == 200
    plan = _get("/api/billing/plan").json()
    assert plan.get("tier") == "studio" or plan.get("id") == "studio"
    # Restore to free
    _post("/api/billing/upgrade", json={"tier": "free"})


# ==========================================================================
# Regression — v10 iteration's core endpoints still healthy
# ==========================================================================
def test_regression_dashboard():
    r = _get("/api/dashboard")
    assert r.status_code == 200
    assert "hero" in r.json()


def test_regression_portfolio():
    r = _get("/api/portfolio")
    assert r.status_code == 200


def test_regression_competitors_public():
    r = requests.get(f"{BASE}/api/competitors/radar", timeout=15)
    assert r.status_code == 200


def test_regression_strategy_list():
    r = _get("/api/strategy/plans")
    assert r.status_code == 200
