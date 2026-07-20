"""Billing / subscription tiers.

Three tiers:
  - free   : $0/mo, 10 AI Coach messages / day, 1 Strategy Plan / week
  - pro    : $29/mo, unlimited chat, unlimited plans, competitor benchmark
  - studio : $99/mo, everything + white-label report export (future)

Endpoints:
  GET  /billing/plan       → { tier, features, limits }
  GET  /billing/plans      → list all tiers
  POST /billing/upgrade    → mock-upgrade (real Stripe Checkout requires a
                             valid Stripe key; current sk_test_emergent
                             placeholder does not authenticate)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


TIERS = {
    "free": {
        "id": "free",
        "name": "Free",
        "price_monthly": 0,
        "tagline": "Get a feel for CreatorOS",
        "features": [
            "Full Dashboard access",
            "Portfolio + Finance tracking",
            "10 AI Coach messages / day",
            "1 Strategy Plan / week",
        ],
        "limits": {"chat_daily": 10, "plans_weekly": 1},
        "cta": "Current plan",
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price_monthly": 29,
        "tagline": "For creators running a serious business",
        "features": [
            "Everything in Free",
            "Unlimited AI Coach",
            "Unlimited Strategy Plans",
            "Top 1% Competitor Benchmark",
            "Priority streaming responses",
        ],
        "limits": {"chat_daily": None, "plans_weekly": None},
        "cta": "Upgrade to Pro",
        "popular": True,
    },
    "studio": {
        "id": "studio",
        "name": "Studio",
        "price_monthly": 99,
        "tagline": "For agencies & multi-brand operators",
        "features": [
            "Everything in Pro",
            "Multi-brand workspaces (coming)",
            "White-label PDF reports (coming)",
            "1:1 human review of Q&A plans (coming)",
        ],
        "limits": {"chat_daily": None, "plans_weekly": None},
        "cta": "Upgrade to Studio",
    },
}


class UpgradeRequest(BaseModel):
    tier: str


def make_billing_router(db, current_user):
    router = APIRouter(prefix="/billing", tags=["billing"])

    @router.get("/plans")
    async def list_plans() -> dict[str, Any]:
        return {"tiers": list(TIERS.values())}

    @router.get("/plan")
    async def current_plan(user: dict = Depends(current_user)) -> dict[str, Any]:
        tier_id = user.get("tier") or "free"
        info = TIERS.get(tier_id, TIERS["free"])
        return {"tier": tier_id, **info}

    @router.post("/upgrade")
    async def upgrade(req: UpgradeRequest, user: dict = Depends(current_user)):
        if req.tier not in TIERS:
            raise HTTPException(400, f"Unknown tier: {req.tier}")
        # NOTE: Real Stripe Checkout would happen here — create a Checkout Session,
        # redirect the user, and update tier only on the webhook. For now we
        # mock-upgrade in-place so the UX is testable end-to-end.
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"tier": req.tier, "tier_updated_at": datetime.now(timezone.utc)}},
        )
        return {"ok": True, "tier": req.tier, "mocked": True}

    return router
