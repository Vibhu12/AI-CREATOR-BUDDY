"""Shared test fixtures — seeds the persistent audit user before every test.

Previously the `user_audit` session was seeded by `test_v9_full_audit.py`
which was cleaned up in iter_14. This conftest re-creates that fixture at
module import so tests v10 → v14 keep working.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

AUDIT_TOKEN = "audit-token"
AUDIT_UID = "user_audit"


@pytest.fixture(scope="session", autouse=True)
def _ensure_audit_user():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc)
    db.users.update_one(
        {"user_id": AUDIT_UID},
        {"$set": {
            "user_id": AUDIT_UID,
            "email": "audit@creatoros.test",
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
    db.user_sessions.update_one(
        {"session_token": AUDIT_TOKEN},
        {"$set": {
            "session_token": AUDIT_TOKEN,
            "user_id": AUDIT_UID,
            "expires_at": now + timedelta(days=30),
            "created_at": now,
        }},
        upsert=True,
    )
    yield
    client.close()
