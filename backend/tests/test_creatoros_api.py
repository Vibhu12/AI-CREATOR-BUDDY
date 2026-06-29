"""CreatorOS backend test suite — covers dashboard, portfolio, finance, goals,
content, recommendations, AI chat (SSE), and chat history."""
import json
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "https://business-ai-hub-47.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# --- Health -----------------------------------------------------------------
def test_root(s):
    r = s.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("ok") is True


# --- Dashboard --------------------------------------------------------------
def test_dashboard(s):
    r = s.get(f"{API}/dashboard")
    assert r.status_code == 200
    d = r.json()
    assert d["greeting"] == "Welcome back, Maya"
    assert d["hero"]["score"] == 87
    assert isinstance(d["metrics"], list) and len(d["metrics"]) == 4
    assert isinstance(d["recommendations"], list) and len(d["recommendations"]) >= 1
    assert isinstance(d["alerts"], list) and len(d["alerts"]) >= 1
    # no _id leaks
    for rec in d["recommendations"]:
        assert "_id" not in rec


# --- Portfolio --------------------------------------------------------------
def test_portfolio_list(s):
    r = s.get(f"{API}/portfolio")
    assert r.status_code == 200
    d = r.json()
    assert d["asset_count"] >= 6
    assert d["total_revenue_mtd"] > 0
    assert isinstance(d["assets"], list)
    a = d["assets"][0]
    for k in ("name", "platform", "revenue_mtd", "ai_score", "trend"):
        assert k in a
    assert "_id" not in a


def test_portfolio_create_and_persist(s):
    payload = {
        "name": f"TEST_Asset_{uuid.uuid4().hex[:6]}",
        "platform": "newsletter",
        "category": "Test",
        "revenue_mtd": 100.0,
        "profit_mtd": 75.0,
        "followers": 500,
        "ai_score": 80,
        "trend": [10, 20, 30],
    }
    r = s.post(f"{API}/portfolio", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "_id" not in body
    assert body["name"] == payload["name"]
    assert "id" in body

    # GET to verify persistence
    r2 = s.get(f"{API}/portfolio")
    names = [a["name"] for a in r2.json()["assets"]]
    assert payload["name"] in names


# --- Finance ----------------------------------------------------------------
def test_finance(s):
    r = s.get(f"{API}/finance")
    assert r.status_code == 200
    d = r.json()
    assert "summary" in d
    for k in ("revenue_30d", "expense_30d", "profit_30d", "margin", "forecast_60d", "runway_months"):
        assert k in d["summary"]
    assert len(d["series"]) == 30
    assert all("date" in p and "revenue" in p and "expense" in p for p in d["series"])
    assert len(d["transactions"]) >= 5


# --- Goals ------------------------------------------------------------------
def test_goals(s):
    r = s.get(f"{API}/goals")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 4
    for g in items:
        assert "_id" not in g
        for k in ("title", "kind", "target", "current"):
            assert k in g


# --- Content ----------------------------------------------------------------
def test_content(s):
    r = s.get(f"{API}/content")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    for c in items:
        assert "_id" not in c


# --- Recommendations --------------------------------------------------------
def test_recommendations(s):
    r = s.get(f"{API}/recommendations")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 4
    for rec in items:
        assert "_id" not in rec
        for k in ("title", "summary", "priority"):
            assert k in rec


# --- AI Chat SSE (budget may be exhausted; validate stream protocol) --------
def test_ai_chat_stream_protocol(s):
    session_id = f"test-{uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{API}/ai/chat",
        json={"session_id": session_id, "message": "Hi coach, one-line tip."},
        stream=True,
        timeout=60,
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")

    events = []
    done_seen = False
    for raw in r.iter_lines(decode_unicode=True):
        if not raw:
            continue
        assert raw.startswith("data: "), f"bad SSE line: {raw!r}"
        payload = json.loads(raw[len("data: "):])
        events.append(payload)
        if payload.get("done") is True:
            done_seen = True
            break
    assert done_seen, f"no done event; got: {events}"
    # error event acceptable (budget exhausted) — that's per the request spec
    assert len(events) >= 1


def test_ai_chat_history(s):
    session_id = f"test-hist-{uuid.uuid4().hex[:8]}"
    # send one message
    requests.post(
        f"{API}/ai/chat",
        json={"session_id": session_id, "message": "ping"},
        stream=True, timeout=60,
    ).close()
    r = s.get(f"{API}/ai/chat/history", params={"session_id": session_id})
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert len(msgs) >= 1
    # user message persisted
    assert any(m["role"] == "user" and m["text"] == "ping" for m in msgs)
    for m in msgs:
        assert "_id" not in m
