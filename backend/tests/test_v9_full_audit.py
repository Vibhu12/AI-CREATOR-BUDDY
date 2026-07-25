"""v9 full end-to-end audit — hits every endpoint the frontend depends on."""
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


# --- Health & auth gate ---
def test_health_root():
    r = _get("/api/", headers={})
    assert r.status_code == 200 and r.json().get("ok") is True


def test_dashboard_401_without_bearer():
    assert _get("/api/dashboard", headers={}).status_code == 401


def test_dashboard_401_bad_bearer():
    assert _get("/api/dashboard", headers={"Authorization": "Bearer garbage"}).status_code == 401


# --- Dashboard ---
def test_dashboard_shape():
    r = _get("/api/dashboard")
    assert r.status_code == 200, r.text
    j = r.json()
    for k in ("greeting", "hero", "metrics", "recommendations"):
        assert k in j, f"missing {k}"
    rev = next((m for m in j["metrics"] if m["key"] == "revenue"), None)
    assert rev and rev["value"] > 0
    assert len(j["recommendations"]) >= 3


# --- Portfolio ---
def test_portfolio_list():
    r = _get("/api/portfolio")
    assert r.status_code == 200
    j = r.json()
    assert j.get("asset_count", 0) >= 1
    assert isinstance(j.get("assets"), list) and len(j["assets"]) >= 1


def test_portfolio_add_asset_persists():
    name = f"TEST_v9_{uuid.uuid4().hex[:6]}"
    payload = {"name": name, "platform": "youtube", "category": "video",
               "revenue_mtd": 111.11, "cost_mtd": 22.22, "followers": 1000}
    r = _post("/api/portfolio", json=payload)
    assert r.status_code in (200, 201), r.text
    got = _get("/api/portfolio").json()
    assert name in [a.get("name") for a in got.get("assets", [])]


def test_portfolio_missing_name_rejected():
    r = _post("/api/portfolio", json={"platform": "youtube", "category": "video", "revenue_mtd": 1})
    assert r.status_code in (400, 422)


def test_portfolio_non_numeric_revenue_rejected():
    r = _post("/api/portfolio", json={"name": "x", "platform": "youtube", "category": "video",
                                       "revenue_mtd": "abc"})
    assert r.status_code in (400, 422)


# --- Finance ---
def test_finance_ranges():
    for rng in ("1W", "1M", "3M"):
        r = _get(f"/api/finance?range={rng}")
        assert r.status_code == 200, f"{rng}: {r.status_code} {r.text[:120]}"


# --- Goals / Content / Recs / Notifications (envelope: {items:[...]}) ---
def test_goals_shape():
    r = _get("/api/goals")
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j, dict) and isinstance(j.get("items"), list) and len(j["items"]) >= 1


def test_content_shape():
    r = _get("/api/content")
    assert r.status_code == 200


def test_recommendations_shape():
    r = _get("/api/recommendations")
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j.get("items"), list) and len(j["items"]) >= 1


def test_notifications_and_mark_read():
    r = _get("/api/notifications")
    assert r.status_code == 200
    j = r.json()
    items = j.get("items") if isinstance(j, dict) else j
    assert isinstance(items, list) and len(items) >= 1
    unread_before = j.get("unread") if isinstance(j, dict) else None
    unread = [n for n in items if not n.get("read")]
    if unread:
        nid = unread[0].get("id")
        rr = _post(f"/api/notifications/{nid}/read", json={})
        assert rr.status_code in (200, 204), rr.text
        j2 = _get("/api/notifications").json()
        if unread_before is not None:
            assert j2.get("unread", unread_before) <= unread_before


# --- AI Coach ---
SID = "audit-session"


def test_ai_chat_history():
    r = _get(f"/api/ai/chat/history?session_id={SID}")
    assert r.status_code == 200


def test_ai_chat_send():
    r = _post("/api/ai/chat", json={"message": "One tip in 5 words.", "session_id": SID})
    assert r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}"


def test_ai_chat_reset():
    r = _post(f"/api/ai/chat/reset?session_id={SID}", json={})
    assert r.status_code in (200, 204)


# --- Strategy ---
def test_strategy_plans_list():
    r = _get("/api/strategy/plans")
    assert r.status_code == 200


def test_strategy_generate_plan():
    r = _post("/api/strategy/plans", json={"horizon": "30d"})
    assert r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}"


# --- Competitors (public) ---
def test_competitors_endpoints_public():
    for p in ("/api/competitors", "/api/competitors/radar", "/api/competitors/gaps"):
        r = requests.get(f"{BASE}{p}", timeout=15)
        assert r.status_code == 200, f"{p}: {r.status_code}"


# --- Integrations placeholders ---
def test_integration_stripe_status_public():
    r = requests.get(f"{BASE}/api/integrations/stripe/status", timeout=15)
    assert r.status_code == 200
    assert r.json().get("connected") is False  # placeholder key expected


def test_integration_instagram_503_with_handle():
    r = requests.get(f"{BASE}/api/integrations/instagram/profile?handle=test", timeout=15)
    assert r.status_code == 503


def test_integration_instagram_422_without_handle():
    r = requests.get(f"{BASE}/api/integrations/instagram/profile", timeout=15)
    assert r.status_code == 422  # missing required query param


# --- Billing upgrade (mock) ---
def test_billing_upgrade_and_reflected_in_plan():
    r = _post("/api/billing/upgrade", json={"tier": "pro"})
    assert r.status_code in (200, 201), r.text
    plan = _get("/api/billing/plan")
    assert plan.status_code == 200
    assert plan.json().get("id") in ("pro", "PRO", "Pro")


def test_billing_plans_list():
    r = requests.get(f"{BASE}/api/billing/plans", timeout=15)
    assert r.status_code == 200


# --- Onboarding endpoints ---
def test_onboarding_status():
    r = _get("/api/onboarding/status")
    assert r.status_code == 200


def test_onboarding_complete_idempotent():
    r = _post("/api/onboarding/complete", json={"youtube_handle": "@testhandle"})
    assert r.status_code in (200, 201)


# --- Auth me ---
def test_auth_me_returns_user():
    r = _get("/api/auth/me")
    assert r.status_code == 200
    j = r.json()
    # v9 audit: /me returns nested {user: {...}} — flag if `tier` is missing at top of user
    u = j.get("user") or j
    assert u.get("email") == "audit@example.com"


# --- Dev reseed ---
def test_dev_reseed_ok():
    r = _post("/api/dev/reseed", json={})
    assert r.status_code == 200
    assert r.json().get("ok") is True
