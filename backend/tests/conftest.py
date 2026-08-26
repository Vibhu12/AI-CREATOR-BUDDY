"""Shared test fixtures.

SECURITY NOTE: The previous version of this file used a static session token
("audit-token") which lived in the app's runtime DB for 30 days. That was
flagged as SEC-001 in the security audit. This version:
  - Generates a random, high-entropy token per pytest session
  - Uses a per-run user_id so parallel test suites don't collide
  - CLEANS UP the session + fixture data at teardown so no token persists
    after the tests finish

Import in test files:
    from conftest import AUDIT_TOKEN, AUDIT_UID
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

# Load backend/.env so MONGO_URL / DB_NAME are picked up automatically.
load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))
# EXPO_PUBLIC_BACKEND_URL lives in the frontend .env — load it too so tests
# don't require a manual `export` before running.
load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "frontend", ".env"))

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

if not MONGO_URL or not DB_NAME:
    raise RuntimeError(
        "MONGO_URL and DB_NAME must be set in the environment before running tests."
    )

# Generated once per pytest session — never persisted between runs.
AUDIT_TOKEN = f"test_{secrets.token_urlsafe(32)}"
AUDIT_UID = f"user_audit_{secrets.token_hex(8)}"

# Collections whose fixture rows should be cleaned up at teardown
_SCOPED_COLLECTIONS = (
    "assets", "goals", "content", "recommendations", "notifications",
    "strategy_plans", "chat_messages", "connections", "checkout_sessions",
    "analytics_events",
)


@pytest.fixture(scope="session", autouse=True)
def _ensure_audit_user():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc)

    # Belt-and-suspenders: nuke any legacy static token that might still be
    # lingering from prior runs (SEC-001 remediation).
    db.user_sessions.delete_many({"session_token": {"$in": ["audit-token", "test-token"]}})

    db.users.update_one(
        {"user_id": AUDIT_UID},
        {"$set": {
            "user_id": AUDIT_UID,
            "email": f"audit-{AUDIT_UID}@creatoros.test",
            "name": "Audit Bot",
            "picture": None,
            "onboarding_complete": True,
            "youtube_handle": "mayabuilds",
            "instagram_handle": "maya.builds",
            "tier": "free",
            "integrations": {},
            "updated_at": now,
         },
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    db.user_sessions.insert_one({
        "session_token": AUDIT_TOKEN,
        "user_id": AUDIT_UID,
        "expires_at": now + timedelta(hours=2),  # short TTL — session-only
        "created_at": now,
    })

    yield {"token": AUDIT_TOKEN, "uid": AUDIT_UID}

    # Teardown — remove EVERYTHING this fixture created so no artefacts
    # remain in the runtime database.
    db.user_sessions.delete_many({"session_token": AUDIT_TOKEN})
    db.users.delete_many({"user_id": AUDIT_UID})
    for coll in _SCOPED_COLLECTIONS:
        db[coll].delete_many({"user_id": AUDIT_UID})
    client.close()
