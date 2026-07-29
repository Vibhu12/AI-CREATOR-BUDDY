"""Quota enforcement + basic rate limiting for paid resources.

Enforces the tier-based limits declared in `billing.py::TIERS` on hot paths:
  - AI chat: chats_per_day for free tier
  - Strategy plans: plans_per_week for free tier

Also provides a simple in-process sliding-window rate limiter to protect
against burst abuse on paid endpoints (e.g. one user hammering /ai/chat).

These checks are additive — user can still be blocked for other reasons (e.g.
auth). Raises fastapi.HTTPException(429) with a clear message on any breach.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

# --- Configuration -------------------------------------------------------
MAX_CHAT_MESSAGE_CHARS = 4000

FREE_TIER_LIMITS = {
    "chats_per_day": 10,
    "plans_per_week": 1,
}

# Absolute per-user burst caps regardless of tier (defense-in-depth).
BURST_LIMITS = {
    "chat": (30, 60),         # 30 chat messages / 60 sec
    "strategy": (5, 3600),    # 5 plans / hour
    "paypal_order": (10, 3600),  # 10 order creations / hour
}


# --- In-process sliding window (per-process; good enough for single-worker
# uvicorn dev/prod). Swap for Redis if you scale horizontally.
_windows: dict[str, dict[str, deque]] = defaultdict(lambda: defaultdict(deque))


def check_burst(user_id: str, kind: str) -> None:
    cap = BURST_LIMITS.get(kind)
    if not cap:
        return
    limit, window_sec = cap
    now = time.time()
    q = _windows[kind][user_id]
    # Drop old entries
    while q and (now - q[0]) > window_sec:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(
            429,
            f"Rate limit: too many {kind} requests. Try again in {int(window_sec - (now - q[0]))}s.",
        )
    q.append(now)


# --- Tier-based quotas ----------------------------------------------------
def _tier(user: dict[str, Any]) -> str:
    return (user.get("tier") or "free").lower()


async def enforce_chat_message(db, user: dict[str, Any], message: str) -> None:
    """Called before persisting/streaming a chat message.

    - Rejects messages exceeding MAX_CHAT_MESSAGE_CHARS
    - Enforces free-tier daily chat message limit
    - Applies burst rate limit
    """
    if not message or not message.strip():
        raise HTTPException(400, "Message cannot be empty")
    if len(message) > MAX_CHAT_MESSAGE_CHARS:
        raise HTTPException(
            413,
            f"Message too long. Max {MAX_CHAT_MESSAGE_CHARS} characters.",
        )

    check_burst(user["user_id"], "chat")

    if _tier(user) == "free":
        # Count only user-role messages in the last 24h across all sessions
        since = datetime.now(timezone.utc) - timedelta(days=1)
        count = await db.chat_messages.count_documents({
            "user_id": user["user_id"],
            "role": "user",
            "at": {"$gte": since.isoformat()},
        })
        limit = FREE_TIER_LIMITS["chats_per_day"]
        if count >= limit:
            raise HTTPException(
                402,
                f"Free tier limit reached ({limit} AI Coach messages / day). Upgrade to Pro for unlimited.",
            )


async def enforce_strategy_plan(db, user: dict[str, Any]) -> None:
    """Called before generating a new strategy plan.
    - Enforces free-tier weekly plan limit
    - Applies burst rate limit
    """
    check_burst(user["user_id"], "strategy")

    if _tier(user) == "free":
        since = datetime.now(timezone.utc) - timedelta(days=7)
        count = await db.strategy_plans.count_documents({
            "user_id": user["user_id"],
            "created_at": {"$gte": since.isoformat()},
        })
        limit = FREE_TIER_LIMITS["plans_per_week"]
        if count >= limit:
            raise HTTPException(
                402,
                f"Free tier limit reached ({limit} Strategy Plan / week). Upgrade to Pro for unlimited.",
            )


def enforce_paypal_order(user: dict[str, Any]) -> None:
    """Burst limit only — pricing is server-authoritative in TIERS."""
    check_burst(user["user_id"], "paypal_order")
