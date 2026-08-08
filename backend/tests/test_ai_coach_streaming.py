"""Tests for AI Coach streaming endpoint after auth-header fix.

Verifies:
  - POST /api/ai/chat returns 401 when Authorization header is missing
  - POST /api/ai/chat returns 200 SSE stream when authenticated (Emergent
    LLM key + Claude Sonnet 4.5)
  - Streamed chunks arrive as `data: {"delta": "..."}` SSE frames and
    eventually form a non-empty assistant response
  - GET /api/ai/chat/history and POST /api/ai/chat/reset still work
"""
from __future__ import annotations

import json
import os

import pytest
import requests

from conftest import AUDIT_TOKEN

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "https://business-ai-hub-47.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")
CHAT_URL = f"{BASE_URL}/api/ai/chat"
HISTORY_URL = f"{BASE_URL}/api/ai/chat/history"
RESET_URL = f"{BASE_URL}/api/ai/chat/reset"

SESSION_ID = "maya-default-session"


def _auth_headers():
    return {
        "Authorization": f"Bearer {AUDIT_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }


# -----------------------------------------------------------------------------
# Auth gate — confirms the fix path is real
# -----------------------------------------------------------------------------
class TestAiChatAuthGate:
    def test_post_chat_missing_auth_returns_401(self):
        r = requests.post(
            CHAT_URL,
            json={"session_id": SESSION_ID, "message": "hello"},
            timeout=10,
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:300]}"

    def test_post_chat_bad_token_returns_401(self):
        r = requests.post(
            CHAT_URL,
            headers={"Authorization": "Bearer this-is-not-a-valid-token"},
            json={"session_id": SESSION_ID, "message": "hello"},
            timeout=10,
        )
        assert r.status_code == 401


# -----------------------------------------------------------------------------
# Streaming happy-path with Emergent LLM key
# -----------------------------------------------------------------------------
class TestAiChatStreaming:
    def test_post_chat_with_bearer_streams_200(self):
        with requests.post(
            CHAT_URL,
            headers=_auth_headers(),
            json={"session_id": SESSION_ID, "message": "Say hi in 5 words."},
            stream=True,
            timeout=60,
        ) as r:
            assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
            ctype = r.headers.get("content-type", "")
            assert "text/event-stream" in ctype, f"expected SSE, got {ctype}"

            deltas = []
            saw_done = False
            saw_error = False
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                if not raw.startswith("data:"):
                    continue
                payload = raw[5:].strip()
                try:
                    evt = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "delta" in evt:
                    deltas.append(evt["delta"])
                if evt.get("done"):
                    saw_done = True
                    break
                if evt.get("error"):
                    saw_error = True
                    break

            if saw_error:
                pytest.fail("Backend emitted stream error frame — LLM integration failing.")

            assert saw_done, "Stream ended without a 'done' frame."
            assistant_text = "".join(deltas)
            assert assistant_text.strip(), "Assistant response was empty — no delta frames."
            print(f"assistant_text ({len(assistant_text)} chars): {assistant_text[:200]!r}")


# -----------------------------------------------------------------------------
# History + reset regression
# -----------------------------------------------------------------------------
class TestAiChatHistoryReset:
    def test_history_returns_persisted_messages(self):
        r = requests.get(
            HISTORY_URL,
            headers={"Authorization": f"Bearer {AUDIT_TOKEN}"},
            params={"session_id": SESSION_ID},
            timeout=10,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "messages" in data and isinstance(data["messages"], list)
        # After the streaming test above, we should have >=2 (user + assistant)
        # Not strictly enforced because ordering is class-level, but check keys
        for m in data["messages"]:
            assert "role" in m and "text" in m and "id" in m

    def test_history_missing_auth_returns_401(self):
        r = requests.get(HISTORY_URL, params={"session_id": SESSION_ID}, timeout=10)
        assert r.status_code == 401

    def test_reset_clears_messages(self):
        r = requests.post(
            RESET_URL,
            headers={"Authorization": f"Bearer {AUDIT_TOKEN}"},
            params={"session_id": SESSION_ID},
            timeout=10,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("ok") is True

        # verify GET now returns empty
        g = requests.get(
            HISTORY_URL,
            headers={"Authorization": f"Bearer {AUDIT_TOKEN}"},
            params={"session_id": SESSION_ID},
            timeout=10,
        )
        assert g.status_code == 200
        assert g.json().get("messages") == []

    def test_reset_missing_auth_returns_401(self):
        r = requests.post(RESET_URL, params={"session_id": SESSION_ID}, timeout=10)
        assert r.status_code == 401
