"""v8 backend tests — Auto-seed on /api/dashboard and /api/portfolio.

Verifies the targeted fix: `await seed_user_starter(user['user_id'])` inserted
at the top of GET /api/dashboard and GET /api/portfolio. Because
seed_user_starter is idempotent (returns immediately if the user already has
assets), the guarantees are:

1. First hit to /api/dashboard by a fresh authed user → auto-seed fires
   → revenue_mtd ~ $66,460.50, recs non-empty, all 7 collections populated.
2. First hit to /api/portfolio by a different fresh user → same guarantee,
   asset_count=8, total_revenue_mtd=$66,460.50, WITHOUT calling dashboard first.
3. Subsequent hits are idempotent — counts stay the same.
4. User additions via POST /api/portfolio compose on top of the Maya seed
   (not replaced) — 8 Maya + 1 custom = 9 assets.
5. Per-user isolation — auto-seed for user A must not affect user B, and
   user B triggering their own auto-seed later gets an independent copy.
6. Auth still required — no Bearer → 401.
7. Other endpoints (/goals, /content, /recommendations, /notifications)
   remain empty for a truly fresh user (they don't trigger auto-seed).
8. Regression — /api/dev/reseed still works; dashboard rec ordering unchanged.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

EXPECTED_TOTAL_REV = 66_460.50
EXPECTED_COUNTS = {
    "assets": 8, "goals": 4, "content": 4,
    "recommendations": 7, "notifications": 6,
    "chat_messages": 4, "strategy_plans": 1,
}
SCOPED_COLLS = (
    "assets", "goals", "content", "recommendations",
    "notifications", "chat_messages", "strategy_plans",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def mongo():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


async def _mk_fresh_user(db, suffix: str) -> tuple[str, str]:
    """Create an authed user with ZERO scoped data and return (user_id, token).

    Aggressively wipes any leftover rows to guarantee freshness."""
    user_id = f"user_v8_{suffix}_{uuid.uuid4().hex[:8]}"
    token = f"v8-token-{suffix}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    for coll in SCOPED_COLLS:
        await db[coll].delete_many({"user_id": user_id})
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id, "email": f"{user_id}@test.com",
            "name": f"V8 {suffix}", "picture": None,
            "onboarding_complete": True, "tier": "free",
            "created_at": now, "updated_at": now,
        }},
        upsert=True,
    )
    await db.user_sessions.update_one(
        {"session_token": token},
        {"$set": {
            "session_token": token, "user_id": user_id,
            "expires_at": now + timedelta(days=1), "created_at": now,
        }},
        upsert=True,
    )
    return user_id, token


async def _cleanup(db, user_id: str):
    for coll in ("users", "user_sessions", *SCOPED_COLLS):
        await db[coll].delete_many({"user_id": user_id})


async def _counts(db, user_id: str) -> dict:
    out = {}
    for coll in SCOPED_COLLS:
        out[coll] = await db[coll].count_documents({"user_id": user_id})
    return out


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# TEST 1 — AUTO-SEED ON DASHBOARD
# ---------------------------------------------------------------------------
def test_dashboard_autoseed_fires_for_fresh_user(mongo, event_loop):
    user_id, tok = event_loop.run_until_complete(_mk_fresh_user(mongo, "dash"))
    try:
        # Confirm truly zero before the call
        pre = event_loop.run_until_complete(_counts(mongo, user_id))
        assert pre == {k: 0 for k in EXPECTED_COUNTS}, pre

        r = requests.get(f"{BASE_URL}/api/dashboard", headers=H(tok), timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()

        # revenue metric
        metrics = {m["key"]: m for m in body["metrics"]}
        assert "revenue" in metrics
        assert abs(metrics["revenue"]["value"] - EXPECTED_TOTAL_REV) < 1.0, \
            metrics["revenue"]["value"]

        # recommendations populated
        assert isinstance(body["recommendations"], list)
        assert len(body["recommendations"]) == 4, len(body["recommendations"])

        # metrics all four keys present
        for k in ("revenue", "profit", "margin", "followers"):
            assert k in metrics

        # DB counts after auto-seed
        post = event_loop.run_until_complete(_counts(mongo, user_id))
        assert post == EXPECTED_COUNTS, post
    finally:
        event_loop.run_until_complete(_cleanup(mongo, user_id))


# ---------------------------------------------------------------------------
# TEST 2 — AUTO-SEED ON PORTFOLIO (no prior dashboard call)
# ---------------------------------------------------------------------------
def test_portfolio_autoseed_fires_for_fresh_user(mongo, event_loop):
    user_id, tok = event_loop.run_until_complete(_mk_fresh_user(mongo, "port"))
    try:
        pre = event_loop.run_until_complete(_counts(mongo, user_id))
        assert pre["assets"] == 0

        r = requests.get(f"{BASE_URL}/api/portfolio", headers=H(tok), timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["asset_count"] == 8, body["asset_count"]
        assert abs(body["total_revenue_mtd"] - EXPECTED_TOTAL_REV) < 1.0, \
            body["total_revenue_mtd"]
        assert len(body["assets"]) == 8

        post = event_loop.run_until_complete(_counts(mongo, user_id))
        assert post == EXPECTED_COUNTS, post
    finally:
        event_loop.run_until_complete(_cleanup(mongo, user_id))


# ---------------------------------------------------------------------------
# TEST 3 — IDEMPOTENCY (repeat calls do NOT re-seed)
# ---------------------------------------------------------------------------
def test_autoseed_is_idempotent_on_dashboard(mongo, event_loop):
    user_id, tok = event_loop.run_until_complete(_mk_fresh_user(mongo, "idem"))
    try:
        r1 = requests.get(f"{BASE_URL}/api/dashboard", headers=H(tok), timeout=20)
        assert r1.status_code == 200
        c1 = event_loop.run_until_complete(_counts(mongo, user_id))
        assert c1 == EXPECTED_COUNTS

        # Call again 3x
        for _ in range(3):
            r = requests.get(f"{BASE_URL}/api/dashboard", headers=H(tok), timeout=20)
            assert r.status_code == 200

        c2 = event_loop.run_until_complete(_counts(mongo, user_id))
        assert c2 == c1, f"counts grew after repeat calls: {c1} → {c2}"

        # Responses should be structurally identical (same revenue, same rec titles/order)
        b1 = r1.json()
        b2 = r.json()
        rev1 = next(m["value"] for m in b1["metrics"] if m["key"] == "revenue")
        rev2 = next(m["value"] for m in b2["metrics"] if m["key"] == "revenue")
        assert rev1 == rev2
        titles1 = [x["title"] for x in b1["recommendations"]]
        titles2 = [x["title"] for x in b2["recommendations"]]
        assert titles1 == titles2, (titles1, titles2)
    finally:
        event_loop.run_until_complete(_cleanup(mongo, user_id))


# ---------------------------------------------------------------------------
# TEST 4 — USER ADDITIONS COMPOSE (not replace)
# ---------------------------------------------------------------------------
def test_user_additions_compose_on_top_of_maya_seed(mongo, event_loop):
    user_id, tok = event_loop.run_until_complete(_mk_fresh_user(mongo, "add"))
    try:
        # Trigger auto-seed via portfolio
        r0 = requests.get(f"{BASE_URL}/api/portfolio", headers=H(tok), timeout=20)
        assert r0.status_code == 200
        assert r0.json()["asset_count"] == 8

        custom_rev = 1234.56
        custom_payload = {
            "name": "TEST_custom_asset_v8",
            "platform": "youtube",
            "category": "TEST",
            "revenue_mtd": custom_rev,
            "profit_mtd": 500.0,
            "followers": 100,
            "ai_score": 77,
            "trend": [1.0, 2.0, 3.0],
        }
        r1 = requests.post(f"{BASE_URL}/api/portfolio", headers=H(tok),
                           json=custom_payload, timeout=20)
        assert r1.status_code == 200, r1.text
        created = r1.json()
        assert created["name"] == "TEST_custom_asset_v8"
        assert created["user_id"] == user_id

        # Now GET must return 9 assets
        r2 = requests.get(f"{BASE_URL}/api/portfolio", headers=H(tok), timeout=20)
        body = r2.json()
        assert body["asset_count"] == 9, body["asset_count"]
        expected_total = EXPECTED_TOTAL_REV + custom_rev
        assert abs(body["total_revenue_mtd"] - expected_total) < 1.0, \
            (body["total_revenue_mtd"], expected_total)

        # The 8 Maya seed rows are still present (verify by known names)
        names = {a["name"] for a in body["assets"]}
        for maya_name in ("Amazon + ConvertKit Affiliate",
                          "Notion Templates — Gumroad"):
            assert maya_name in names, f"Maya asset {maya_name} missing after add"
        assert "TEST_custom_asset_v8" in names
    finally:
        event_loop.run_until_complete(_cleanup(mongo, user_id))


# ---------------------------------------------------------------------------
# TEST 5 — PER-USER ISOLATION
# ---------------------------------------------------------------------------
def test_per_user_isolation_holds(mongo, event_loop):
    a_id, a_tok = event_loop.run_until_complete(_mk_fresh_user(mongo, "iso_a"))
    b_id, b_tok = event_loop.run_until_complete(_mk_fresh_user(mongo, "iso_b"))
    try:
        # A hits dashboard → auto-seeds A only
        r = requests.get(f"{BASE_URL}/api/dashboard", headers=H(a_tok), timeout=20)
        assert r.status_code == 200
        a_counts = event_loop.run_until_complete(_counts(mongo, a_id))
        assert a_counts == EXPECTED_COUNTS

        # B has ZERO rows (never touched the app)
        b_counts = event_loop.run_until_complete(_counts(mongo, b_id))
        assert b_counts == {k: 0 for k in EXPECTED_COUNTS}, b_counts

        # B now hits portfolio → independent auto-seed
        r = requests.get(f"{BASE_URL}/api/portfolio", headers=H(b_tok), timeout=20)
        assert r.status_code == 200
        assert r.json()["asset_count"] == 8
        b_counts2 = event_loop.run_until_complete(_counts(mongo, b_id))
        assert b_counts2 == EXPECTED_COUNTS

        # A's counts unchanged
        a_counts2 = event_loop.run_until_complete(_counts(mongo, a_id))
        assert a_counts2 == a_counts

        # Row IDs are distinct between A and B (independent copies)
        async def _ids():
            aa = await mongo.assets.find({"user_id": a_id}).to_list(50)
            bb = await mongo.assets.find({"user_id": b_id}).to_list(50)
            return {x["id"] for x in aa}, {x["id"] for x in bb}
        aa_ids, bb_ids = event_loop.run_until_complete(_ids())
        assert aa_ids.isdisjoint(bb_ids), "asset IDs must be independent uuids"
        assert len(aa_ids) == 8 and len(bb_ids) == 8
    finally:
        event_loop.run_until_complete(_cleanup(mongo, a_id))
        event_loop.run_until_complete(_cleanup(mongo, b_id))


# ---------------------------------------------------------------------------
# TEST 6 — AUTH STILL REQUIRED (auto-seed runs AFTER dependency)
# ---------------------------------------------------------------------------
def test_dashboard_requires_auth_no_bearer():
    r = requests.get(f"{BASE_URL}/api/dashboard", timeout=15)
    assert r.status_code == 401, r.text


def test_portfolio_requires_auth_no_bearer():
    r = requests.get(f"{BASE_URL}/api/portfolio", timeout=15)
    assert r.status_code == 401, r.text


def test_dashboard_rejects_bad_bearer():
    r = requests.get(f"{BASE_URL}/api/dashboard",
                     headers={"Authorization": "Bearer nope-does-not-exist"},
                     timeout=15)
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# TEST 7 — OTHER ENDPOINTS DO NOT AUTOSEED
# ---------------------------------------------------------------------------
def test_other_endpoints_remain_empty_for_fresh_user(mongo, event_loop):
    """Only /dashboard and /portfolio trigger the auto-seed. /goals, /content,
    /recommendations, /notifications for a brand-new user must return empty
    lists and leave DB untouched."""
    user_id, tok = event_loop.run_until_complete(_mk_fresh_user(mongo, "other"))
    try:
        # Sanity: DB is empty
        pre = event_loop.run_until_complete(_counts(mongo, user_id))
        assert pre == {k: 0 for k in EXPECTED_COUNTS}

        endpoints = ["goals", "content", "recommendations", "notifications"]
        for ep in endpoints:
            r = requests.get(f"{BASE_URL}/api/{ep}", headers=H(tok), timeout=15)
            assert r.status_code == 200, (ep, r.status_code, r.text)
            body = r.json()
            # Different endpoints wrap items differently — probe common shapes
            if isinstance(body, dict):
                if "items" in body:
                    items = body["items"]
                elif ep in body:
                    items = body[ep]
                else:
                    # e.g. notifications might return {"notifications":[..],"unread_count":n}
                    items = next((v for v in body.values() if isinstance(v, list)), [])
            else:
                items = body
            assert items == [] or items == {}, f"{ep} should be empty for fresh user, got {items!r}"

        # DB counts still zero — no side-effects
        post = event_loop.run_until_complete(_counts(mongo, user_id))
        assert post == {k: 0 for k in EXPECTED_COUNTS}, post
    finally:
        event_loop.run_until_complete(_cleanup(mongo, user_id))


# ---------------------------------------------------------------------------
# TEST 8 — REGRESSION: /api/dev/reseed still works
# ---------------------------------------------------------------------------
def test_reseed_still_works_regression(mongo, event_loop):
    user_id, tok = event_loop.run_until_complete(_mk_fresh_user(mongo, "reseed"))
    try:
        # First reseed on fresh user
        r = requests.post(f"{BASE_URL}/api/dev/reseed", headers=H(tok), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data.get("user_id") == user_id
        c = event_loop.run_until_complete(_counts(mongo, user_id))
        assert c == EXPECTED_COUNTS, c

        # Reseed after adding custom → still 8 assets (wipes + reseeds)
        async def _add():
            await mongo.assets.insert_one({
                "id": str(uuid.uuid4()), "user_id": user_id,
                "name": "TEST_will_wipe", "platform": "youtube",
                "category": "TEST", "revenue_mtd": 1.0, "profit_mtd": 0,
                "followers": 0, "ai_score": 50, "trend": [1],
                "created_at": datetime.now(timezone.utc),
            })
        event_loop.run_until_complete(_add())

        r = requests.post(f"{BASE_URL}/api/dev/reseed", headers=H(tok), timeout=20)
        assert r.status_code == 200
        c2 = event_loop.run_until_complete(_counts(mongo, user_id))
        assert c2["assets"] == 8
    finally:
        event_loop.run_until_complete(_cleanup(mongo, user_id))


# ---------------------------------------------------------------------------
# TEST 9 — REGRESSION: dashboard rec ordering still correct after autoseed
# ---------------------------------------------------------------------------
def test_dashboard_rec_ordering_regression(mongo, event_loop):
    user_id, tok = event_loop.run_until_complete(_mk_fresh_user(mongo, "order"))
    try:
        r = requests.get(f"{BASE_URL}/api/dashboard", headers=H(tok), timeout=20)
        assert r.status_code == 200
        recs = r.json()["recommendations"]
        assert len(recs) == 4
        # Top-4 order established in v7:
        expected_titles = [
            "Double down on YouTube long-form",
            "Raise Ship It cohort price by 18%",
            "Bundle Notion templates into a $99 pack",
            "Diversify affiliate portfolio",
        ]
        actual = [r["title"] for r in recs]
        assert actual == expected_titles, actual
    finally:
        event_loop.run_until_complete(_cleanup(mongo, user_id))
