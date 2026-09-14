"""v17 — AI Coach conversation "epoch" timeout (30 min idle).

Verifies:
  - A message older than the 30-min idle window is NOT shown as "default"
    history (the leftover-conversation bug reported by the user).
  - Sending a new message after a stale gap starts a genuinely NEW epoch
    (different underlying session_id) rather than reusing/extending the
    stale one.
  - Two messages sent back-to-back (well within the window) stay in the
    SAME epoch — full continuity while actively chatting.
  - /ai/chat/reset clears every epoch for the thread, not just the latest.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests
from pymongo import MongoClient

from conftest import AUDIT_TOKEN, AUDIT_UID

BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/")
H = {"Authorization": f"Bearer {AUDIT_TOKEN}", "Content-Type": "application/json", "Accept": "text/event-stream"}
HJ = {"Authorization": f"Bearer {AUDIT_TOKEN}", "Content-Type": "application/json"}

SESSION = "timeout-test-session"
BASE_SCOPED = f"{AUDIT_UID}::{SESSION}"

_mongo = MongoClient(os.environ["MONGO_URL"])
_db = _mongo[os.environ["DB_NAME"]]


def _get(path, **kw):
    return requests.get(f"{BASE}{path}", headers=HJ, timeout=15, **kw)


def _post_reset():
    return requests.post(f"{BASE}/api/ai/chat/reset", headers=HJ, params={"session_id": SESSION}, timeout=15)


def _send_and_wait(message: str):
    """Real streaming call — mirrors test_ai_coach_streaming.py's pattern."""
    with requests.post(
        f"{BASE}/api/ai/chat", headers=H,
        json={"session_id": SESSION, "message": message},
        stream=True, timeout=60,
    ) as r:
        assert r.status_code == 200, r.text[:300]
        for raw in r.iter_lines(decode_unicode=True):
            if raw and raw.startswith("data:") and '"done"' in raw:
                break


def setup_module(_module):
    _post_reset()  # start with a clean slate for this dedicated session name


def teardown_module(_module):
    _post_reset()


# ==========================================================================
# 1. A stale (>30 min old) message must NOT surface as default history
# ==========================================================================
def test_stale_message_hidden_from_history():
    stale_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    _db.chat_messages.insert_one({
        "id": "stale-1", "user_id": AUDIT_UID, "session_id": BASE_SCOPED,
        "role": "assistant", "text": "OLD LEFTOVER REPLY — should never show as default",
        "at": stale_at,
    })
    r = _get("/api/ai/chat/history", params={"session_id": SESSION})
    assert r.status_code == 200, r.text
    assert r.json()["messages"] == [], "stale message leaked into default history"


# ==========================================================================
# 2. Sending a fresh message after a stale gap starts a NEW epoch
# ==========================================================================
def test_new_message_after_stale_gap_starts_new_epoch():
    _send_and_wait("Reply with exactly the word: PONG")

    r = _get("/api/ai/chat/history", params={"session_id": SESSION})
    assert r.status_code == 200, r.text
    msgs = r.json()["messages"]
    assert len(msgs) >= 2, "expected at least the user + assistant turn"
    texts = [m["text"] for m in msgs]
    assert not any("OLD LEFTOVER REPLY" in t for t in texts), "stale epoch leaked into fresh conversation"

    # Confirm at the storage level: the new turn lives under a NEW session_id
    # distinct from the bare (stale) BASE_SCOPED id.
    newest = _db.chat_messages.find({"user_id": AUDIT_UID, "session_id": {"$regex": f"^{BASE_SCOPED}"}}) \
        .sort("at", -1).limit(5)
    session_ids = {d["session_id"] for d in newest}
    assert any(sid != BASE_SCOPED for sid in session_ids), "expected a rotated epoch session_id"


# ==========================================================================
# 3. Continuing to chat right away stays in the SAME epoch (continuity)
# ==========================================================================
def test_continued_chat_stays_in_same_epoch():
    before = _get("/api/ai/chat/history", params={"session_id": SESSION}).json()["messages"]
    before_ids = {m["id"] for m in before}

    _send_and_wait("Reply with exactly the word: PONG2")

    after = _get("/api/ai/chat/history", params={"session_id": SESSION}).json()["messages"]
    after_ids = {m["id"] for m in after}
    assert before_ids.issubset(after_ids), "earlier turn disappeared — epoch was wrongly rotated while still active"
    assert len(after) > len(before), "new turn wasn't appended"


# ==========================================================================
# 4. Reset clears every epoch (old stale row + the new rotated one)
# ==========================================================================
def test_reset_clears_all_epochs():
    r = _post_reset()
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    remaining = _db.chat_messages.count_documents(
        {"user_id": AUDIT_UID, "session_id": {"$regex": f"^{BASE_SCOPED}"}}
    )
    assert remaining == 0, "reset should clear the stale row AND every rotated epoch"

    g = _get("/api/ai/chat/history", params={"session_id": SESSION})
    assert g.json()["messages"] == []
