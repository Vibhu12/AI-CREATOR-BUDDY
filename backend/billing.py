"""Billing / subscription tiers.

Three tiers:
  - free   : $0/mo, 10 AI Coach messages / day, 1 Strategy Plan / week
  - pro    : $29/mo, unlimited chat, unlimited plans, competitor benchmark
  - studio : $99/mo, everything + white-label report export (future)

Endpoints:
  GET  /billing/plan            → { tier, features, limits }
  GET  /billing/plans           → list all tiers
  POST /billing/checkout        → create a mock checkout session (Stripe or PayPal)
  POST /billing/checkout/confirm→ confirm the session and switch tier
  POST /billing/upgrade         → legacy direct upgrade (kept for compat)
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

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


class CheckoutRequest(BaseModel):
    tier: str
    provider: Literal["stripe", "paypal"] = "stripe"


class CheckoutConfirm(BaseModel):
    session_id: str


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

    @router.post("/checkout")
    async def create_checkout(req: CheckoutRequest, user: dict = Depends(current_user)):
        """Simulates a real Stripe/PayPal Checkout Session. Returns a session_id
        that the client polls / confirms. In production this would return a
        hosted checkout URL and the tier would flip only on webhook."""
        if req.tier not in TIERS:
            raise HTTPException(400, f"Unknown tier: {req.tier}")
        if TIERS[req.tier]["price_monthly"] == 0:
            raise HTTPException(400, "Cannot checkout the Free tier")

        session_id = f"cs_{req.provider}_{uuid.uuid4().hex[:24]}"
        session = {
            "session_id": session_id,
            "user_id": user["user_id"],
            "tier": req.tier,
            "provider": req.provider,
            "amount": TIERS[req.tier]["price_monthly"],
            "currency": "usd",
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            # In prod this would be a Stripe/PayPal-hosted URL:
            "checkout_url": f"https://checkout.creatoros.mock/{req.provider}/{session_id}",
        }
        await db.checkout_sessions.insert_one(session)
        session.pop("_id", None)
        return session

    @router.post("/checkout/confirm")
    async def confirm_checkout(req: CheckoutConfirm, user: dict = Depends(current_user)):
        """Confirms a checkout session — flips tier + marks session complete."""
        session = await db.checkout_sessions.find_one(
            {"session_id": req.session_id, "user_id": user["user_id"]},
            {"_id": 0},
        )
        if not session:
            raise HTTPException(404, "Checkout session not found")
        if session["status"] == "complete":
            return {"ok": True, "tier": session["tier"], "already_complete": True}

        # Simulate settlement time
        await asyncio.sleep(0.8)

        await db.checkout_sessions.update_one(
            {"session_id": req.session_id},
            {"$set": {"status": "complete", "completed_at": datetime.now(timezone.utc).isoformat()}},
        )
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"tier": session["tier"], "tier_updated_at": datetime.now(timezone.utc)}},
        )
        return {"ok": True, "tier": session["tier"], "provider": session["provider"], "mocked": True}

    @router.post("/upgrade")
    async def upgrade(req: UpgradeRequest, user: dict = Depends(current_user)):
        """Legacy direct-upgrade — kept for tests. Real flow uses /checkout."""
        if req.tier not in TIERS:
            raise HTTPException(400, f"Unknown tier: {req.tier}")
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"tier": req.tier, "tier_updated_at": datetime.now(timezone.utc)}},
        )
        return {"ok": True, "tier": req.tier, "mocked": True}

    return router
