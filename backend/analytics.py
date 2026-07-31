"""Analytics event ingestion.

Endpoints:
  POST /api/analytics/events    Batch-ingest events. Auth required.
  GET  /api/analytics/summary   Small rollup for the calling user (last 30d).

Envelope (one event):
{
  "event":     "checkout_completed",         (required, must be in ALLOWED)
  "at":        "2026-06-15T18:03:22Z",       (optional; server clocks if absent)
  "session":   { "device": "ios", ... },     (optional)
  "props":     { "tier": "pro", ... }        (optional dict; capped size)
}

Rules:
- Event name allowlist prevents cardinality explosion.
- Props dict is trimmed to <=32 keys, <=2KB total when serialised.
- Rate-limited per user (200 events/min) via quotas.check_burst.
- PII scrub: any prop named `email`, `token`, `password`, `phone` is dropped.
- Every event is stamped with `user_id`, `tier`, `at` (server-side truth).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from quotas import check_burst, BURST_LIMITS

log = logging.getLogger("analytics")

# --- Configuration --------------------------------------------------------
ALLOWED_EVENTS = {
    # Auth
    "signup_started", "signup_completed", "signout",
    # Onboarding
    "onboarding_step_started", "onboarding_step_completed",
    # Core screens
    "dashboard_loaded", "portfolio_loaded", "finance_loaded",
    "asset_added", "asset_detail_viewed", "asset_deleted",
    # AI
    "ai_chat_message_sent", "ai_chat_stream_started",
    "ai_chat_stream_completed", "ai_chat_stream_error",
    # Strategy
    "strategy_plan_requested", "strategy_plan_generated",
    "strategy_task_completed",
    # Goals
    "goal_created", "goal_updated", "goal_completed", "goal_deleted",
    # Integrations
    "connect_provider_attempted", "connect_provider_succeeded",
    "connect_provider_failed", "disconnect_provider",
    # Payments
    "checkout_started", "checkout_method_selected",
    "checkout_completed", "checkout_failed", "checkout_cancelled",
    # Monetization
    "quota_hit", "upgrade_cta_shown", "upgrade_cta_tapped",
    # Recommendations
    "recommendation_shown", "recommendation_actioned",
    # Experiments (reserved for future)
    "exposure_recorded",
    # Generic screen view (catchall)
    "screen_view",
}
MAX_PROPS_KEYS   = 32
MAX_PROPS_BYTES  = 2048
MAX_BATCH_SIZE   = 100
BURST_LIMITS["analytics"] = (200, 60)  # register a per-user rate limit
_PII_KEYS = {"email", "token", "password", "phone", "session_token", "authorization"}


# --- Models ---------------------------------------------------------------
class AnalyticsEvent(BaseModel):
    event: str = Field(..., max_length=64)
    at: str | None = None
    session: dict[str, Any] | None = None
    props: dict[str, Any] | None = None


class AnalyticsBatch(BaseModel):
    events: list[AnalyticsEvent]


# --- Helpers --------------------------------------------------------------
def _scrub_props(props: dict[str, Any] | None) -> dict[str, Any]:
    if not props:
        return {}
    out: dict[str, Any] = {}
    for k, v in list(props.items())[:MAX_PROPS_KEYS]:
        if not isinstance(k, str) or k.lower() in _PII_KEYS:
            continue
        # Coerce non-JSON-serializable values to str
        try:
            json.dumps(v)
            out[k] = v
        except Exception:
            out[k] = str(v)[:256]
    # Trim to size budget
    if len(json.dumps(out).encode()) > MAX_PROPS_BYTES:
        return {k: out[k] for k in list(out)[: MAX_PROPS_KEYS // 2]}
    return out


def _scrub_session(session: dict[str, Any] | None) -> dict[str, Any]:
    if not session:
        return {}
    keep = {"device", "os", "os_version", "app_version", "build", "locale", "timezone"}
    return {k: v for k, v in session.items() if k in keep and isinstance(v, (str, int, float, bool))}


# --- Router ---------------------------------------------------------------
def make_analytics_router(db, current_user):
    router = APIRouter(prefix="/analytics", tags=["analytics"])

    @router.post("/events")
    async def ingest(batch: AnalyticsBatch, user: dict = Depends(current_user)):
        if not batch.events:
            return {"accepted": 0}
        if len(batch.events) > MAX_BATCH_SIZE:
            raise HTTPException(413, f"Batch too large (max {MAX_BATCH_SIZE})")

        # Rate limit — one budget check per batch (cheap protection against floods)
        check_burst(user["user_id"], "analytics")

        server_now = datetime.now(timezone.utc)
        docs: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for e in batch.events:
            if e.event not in ALLOWED_EVENTS:
                skipped.append({"event": e.event, "reason": "unknown_event"})
                continue

            try:
                at = datetime.fromisoformat(e.at.replace("Z", "+00:00")) if e.at else server_now
            except Exception:
                at = server_now
            # Ignore future timestamps or events older than 7 days (clock skew guard)
            if at > server_now + timedelta(minutes=5):
                at = server_now
            if at < server_now - timedelta(days=7):
                skipped.append({"event": e.event, "reason": "too_old"})
                continue

            docs.append({
                "user_id": user["user_id"],
                "tier": user.get("tier") or "free",
                "event": e.event,
                "at": at,
                "session": _scrub_session(e.session),
                "props": _scrub_props(e.props),
                "ingested_at": server_now,
            })

        if docs:
            await db.analytics_events.insert_many(docs, ordered=False)

        return {"accepted": len(docs), "skipped": skipped, "server_time": server_now.isoformat()}

    @router.get("/summary")
    async def summary(user: dict = Depends(current_user), days: int = 30):
        """Small rollup for the calling user. Used by internal debug UI."""
        days = max(1, min(90, days))
        since = datetime.now(timezone.utc) - timedelta(days=days)

        pipeline = [
            {"$match": {"user_id": user["user_id"], "at": {"$gte": since}}},
            {"$group": {"_id": "$event", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        by_event = [{"event": r["_id"], "count": r["count"]} async for r in db.analytics_events.aggregate(pipeline)]
        total = sum(row["count"] for row in by_event)

        # Simple daily bucket for the last N days
        daily_pipe = [
            {"$match": {"user_id": user["user_id"], "at": {"$gte": since}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$at"}},
                "count": {"$sum": 1},
            }},
            {"$sort": {"_id": 1}},
        ]
        daily = [{"date": r["_id"], "count": r["count"]} async for r in db.analytics_events.aggregate(daily_pipe)]

        return {
            "window_days": days,
            "total_events": total,
            "by_event": by_event[:32],
            "daily": daily,
        }

    return router
