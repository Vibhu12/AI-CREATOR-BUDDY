"""Auth helpers — Emergent Google Auth integration.

Endpoints (mounted under /api):
  POST /auth/session          → exchange session_id for stored session_token + user
  GET  /auth/me               → current user from Authorization: Bearer
  POST /auth/logout           → revoke session

Also exposes `make_get_current_user(db)` — a FastAPI dependency factory that
resolves the Bearer token to the current user document. Use it as
`user: dict = Depends(current_user)` on any protected route.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
SESSION_TTL = timedelta(days=7)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class SessionExchange(BaseModel):
    session_id: str


def make_auth_router(db, on_new_user=None):
    router = APIRouter(prefix="/auth", tags=["auth"])

    async def _resolve_token(authorization: Optional[str]) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
        if not session:
            raise HTTPException(401, "Invalid session")
        if _aware(session["expires_at"]) < now_utc():
            raise HTTPException(401, "Session expired")
        user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(401, "User not found")
        return user

    @router.post("/session")
    async def exchange_session(payload: SessionExchange):
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                EMERGENT_SESSION_URL,
                headers={"X-Session-ID": payload.session_id},
            )
        if r.status_code != 200:
            raise HTTPException(401, f"Auth provider rejected session ({r.status_code})")
        data = r.json()
        email = data.get("email")
        name = data.get("name")
        picture = data.get("picture")
        session_token = data.get("session_token")
        if not (email and session_token):
            raise HTTPException(502, "Malformed auth response")

        existing = await db.users.find_one({"email": email}, {"_id": 0})
        is_new = existing is None
        if existing:
            user_id = existing["user_id"]
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {"name": name, "picture": picture, "updated_at": now_utc()}},
            )
        else:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({
                "user_id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "onboarding_complete": False,
                "youtube_handle": None,
                "instagram_handle": None,
                "tier": "free",
                "created_at": now_utc(),
                "updated_at": now_utc(),
            })

        await db.user_sessions.update_one(
            {"session_token": session_token},
            {"$set": {
                "session_token": session_token,
                "user_id": user_id,
                "expires_at": now_utc() + SESSION_TTL,
                "created_at": now_utc(),
            }},
            upsert=True,
        )

        # First-time hook — seed starter data
        if is_new and on_new_user is not None:
            try:
                await on_new_user(user_id)
            except Exception:
                pass

        # Fetch the fresh user doc (includes onboarding flags)
        user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        return {"token": session_token, "user": user_doc}

    @router.get("/me")
    async def me(authorization: Optional[str] = Header(None)):
        user = await _resolve_token(authorization)
        return {"user": user}

    @router.post("/logout")
    async def logout(authorization: Optional[str] = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            return {"ok": True}
        token = authorization.split(" ", 1)[1].strip()
        await db.user_sessions.delete_one({"session_token": token})
        return {"ok": True}

    async def _current_user(authorization: Optional[str] = Header(None)) -> dict:
        return await _resolve_token(authorization)

    return router, _current_user


async def ensure_indexes(db):
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("user_id")
    # TTL index removes expired sessions automatically
    try:
        await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
    except Exception:
        pass
