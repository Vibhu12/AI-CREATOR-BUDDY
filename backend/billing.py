"""Billing / subscription tiers.

Three tiers:
  - free   : $0/mo, 10 AI Coach messages / day, 1 Strategy Plan / week
  - pro    : $29/mo, unlimited chat, unlimited plans, competitor benchmark
  - studio : $99/mo, everything + white-label report export (future)

Endpoints:
  GET  /billing/plan                     → { tier, features, limits }
  GET  /billing/plans                    → list all tiers
  POST /billing/checkout                 → create a mock checkout session (Stripe or PayPal)
  POST /billing/checkout/confirm         → confirm the session and switch tier
  POST /billing/paypal/create-order      → real PayPal Orders v2 order (needs env keys)
  POST /billing/paypal/capture           → capture real order + flip tier
  GET  /billing/paypal/status            → { configured, mode }
  POST /billing/upgrade                  → legacy direct upgrade (kept for compat)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import paypal_client
from quotas import enforce_paypal_order

log = logging.getLogger("billing")

# DEMO_MODE: when "true", mock payment paths (Stripe checkout/confirm, PayPal
# capture on mocked orders, legacy /upgrade) can flip the user's tier without
# a real charge. When "false" (production), these paths are rejected — only
# a verified real-provider webhook / capture can grant paid tiers.
DEMO_MODE = os.environ.get("DEMO_MODE", "false").strip().lower() == "true"


def _reject_mock_upgrade():
    raise HTTPException(
        402,
        "Payment required. Mock-tier upgrades are disabled in production. "
        "Configure Stripe / PayPal credentials and use a real checkout.",
    )


def _is_safe_callback_url(url: str) -> bool:
    """Allowlist for PayPal return_url / cancel_url — prevent open-redirect.

    Accepts:
      - https:// URLs
      - app deep-link schemes (exp://, creatoros://, myapp://) — anything with
        a scheme that ISN'T http:// and doesn't look like a bare URL
    Rejects:
      - Plain http://
      - Missing scheme
      - javascript:, data:, file:
    """
    if not url or len(url) > 2000:
        return False
    lower = url.strip().lower()
    if lower.startswith(("javascript:", "data:", "file:", "vbscript:", "http://")):
        return False
    if lower.startswith("https://"):
        return True
    # Deep-link scheme: <scheme>://... — must have :// and scheme chars only
    if "://" not in lower:
        return False
    scheme = lower.split("://", 1)[0]
    return scheme.replace("-", "").replace("+", "").isalnum() and len(scheme) <= 40


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


class PayPalCreateRequest(BaseModel):
    tier: str
    return_url: str  # Deep-link back to app on success (e.g. creatoros://paypal/return)
    cancel_url: str  # Deep-link back to app on cancel


class PayPalCaptureRequest(BaseModel):
    order_id: str


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
        # SEC-001: mocked checkout confirm can only flip tier in DEMO_MODE.
        if not DEMO_MODE:
            _reject_mock_upgrade()

        session = await db.checkout_sessions.find_one(
            {"session_id": req.session_id, "user_id": user["user_id"]},
            {"_id": 0},
        )
        if not session:
            raise HTTPException(404, "Checkout session not found")
        if session["status"] == "complete":
            return {"ok": True, "tier": session["tier"], "already_complete": True}

        log.warning("DEMO_MODE tier flip via mock checkout for user=%s tier=%s",
                    user["user_id"], session["tier"])

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

    # -----------------------------------------------------------------------
    # PayPal Orders v2 — real integration (dormant when keys not set)
    # -----------------------------------------------------------------------
    @router.get("/paypal/status")
    async def paypal_status(user: dict = Depends(current_user)):
        return {
            "configured": paypal_client.is_configured(),
            "mode": paypal_client.PAYPAL_MODE if paypal_client.is_configured() else None,
        }

    @router.post("/paypal/create-order")
    async def paypal_create_order(req: PayPalCreateRequest, user: dict = Depends(current_user)):
        """Creates a PayPal Orders v2 order for the given tier and returns the
        approval_url the app should open. Falls back to the mock checkout
        session if PayPal keys aren't configured."""
        if req.tier not in TIERS or TIERS[req.tier]["price_monthly"] == 0:
            raise HTTPException(400, f"Cannot checkout tier '{req.tier}'")

        # SEC: burst rate limit + return_url scheme allowlist (open redirect)
        enforce_paypal_order(user)
        if not _is_safe_callback_url(req.return_url) or not _is_safe_callback_url(req.cancel_url):
            raise HTTPException(400, "return_url / cancel_url must use https:// or an app deep-link scheme")

        amount = TIERS[req.tier]["price_monthly"]
        description = f"CreatorOS {TIERS[req.tier]['name']} — monthly subscription"
        reference_id = f"co_{user['user_id'][:8]}_{uuid.uuid4().hex[:12]}"

        # Fallback path: keys not set — return a mock session so UX still works
        if not paypal_client.is_configured():
            session_id = f"cs_paypal_{uuid.uuid4().hex[:24]}"
            session = {
                "session_id": session_id,
                "order_id": session_id,   # so /capture can look it up by order_id
                "user_id": user["user_id"],
                "tier": req.tier,
                "provider": "paypal",
                "amount": amount,
                "currency": "usd",
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "checkout_url": f"https://checkout.creatoros.mock/paypal/{session_id}",
                "approval_url": None,
                "mocked": True,
            }
            await db.checkout_sessions.insert_one(session)
            session.pop("_id", None)
            return session

        # Real PayPal flow
        try:
            order = await paypal_client.create_order(
                amount=float(amount),
                currency="USD",
                reference_id=reference_id,
                description=description,
                return_url=req.return_url,
                cancel_url=req.cancel_url,
            )
        except httpx.HTTPStatusError as e:
            log.exception("PayPal create_order failed: %s", e.response.text if e.response else e)
            raise HTTPException(502, "PayPal order creation failed")
        except Exception:
            log.exception("PayPal error")
            raise HTTPException(502, "PayPal order creation failed")

        # Persist the pending order so /capture can look it up
        session_record = {
            "session_id": order["id"],
            "order_id": order["id"],
            "user_id": user["user_id"],
            "tier": req.tier,
            "provider": "paypal",
            "amount": amount,
            "currency": "usd",
            "status": order.get("status", "CREATED").lower(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approval_url": order.get("approval_url"),
            "mocked": False,
        }
        await db.checkout_sessions.insert_one(session_record)
        session_record.pop("_id", None)
        return session_record

    @router.post("/paypal/capture")
    async def paypal_capture(req: PayPalCaptureRequest, user: dict = Depends(current_user)):
        """Captures an approved PayPal order and flips the user's tier."""
        session = await db.checkout_sessions.find_one(
            {"order_id": req.order_id, "user_id": user["user_id"]},
            {"_id": 0},
        )
        if not session:
            raise HTTPException(404, "PayPal order not found for this user")
        if session["status"] == "complete":
            return {"ok": True, "tier": session["tier"], "already_complete": True}

        # Mock fallback: if this was a mocked order, complete without hitting PayPal
        if session.get("mocked") or not paypal_client.is_configured():
            # SEC-001: mock capture can only flip tier in DEMO_MODE.
            if not DEMO_MODE:
                _reject_mock_upgrade()
            log.warning("DEMO_MODE tier flip via mock PayPal capture user=%s tier=%s",
                        user["user_id"], session["tier"])
            await asyncio.sleep(0.4)
            await db.checkout_sessions.update_one(
                {"order_id": req.order_id},
                {"$set": {"status": "complete", "completed_at": datetime.now(timezone.utc).isoformat()}},
            )
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"tier": session["tier"], "tier_updated_at": datetime.now(timezone.utc)}},
            )
            return {"ok": True, "tier": session["tier"], "provider": "paypal", "mocked": True}

        # Real capture
        try:
            capture = await paypal_client.capture_order(req.order_id)
        except httpx.HTTPStatusError as e:
            log.exception("PayPal capture failed: %s", e.response.text if e.response else e)
            raise HTTPException(502, "PayPal capture failed — order not approved or already captured")
        except Exception:
            log.exception("PayPal capture error")
            raise HTTPException(502, "PayPal error")

        status = capture.get("status", "").upper()
        if status != "COMPLETED":
            raise HTTPException(400, f"PayPal capture status: {status}")

        # Extract capture id for auditing
        capture_id: Optional[str] = None
        try:
            capture_id = capture["purchase_units"][0]["payments"]["captures"][0]["id"]
        except (KeyError, IndexError):
            pass

        await db.checkout_sessions.update_one(
            {"order_id": req.order_id},
            {"$set": {
                "status": "complete",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "capture_id": capture_id,
                "capture_payload": capture,
            }},
        )
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"tier": session["tier"], "tier_updated_at": datetime.now(timezone.utc)}},
        )
        return {
            "ok": True,
            "tier": session["tier"],
            "provider": "paypal",
            "mode": paypal_client.PAYPAL_MODE,
            "capture_id": capture_id,
            "mocked": False,
        }

    @router.post("/upgrade")
    async def upgrade(req: UpgradeRequest, user: dict = Depends(current_user)):
        """Legacy direct-upgrade — DEMO_MODE only.

        SEC-001: In production this endpoint would let any user self-grant a
        paid tier. It's kept behind DEMO_MODE for tests / seeded demos only.
        """
        if not DEMO_MODE:
            raise HTTPException(410, "This endpoint is deprecated. Use /billing/checkout.")
        if req.tier not in TIERS:
            raise HTTPException(400, f"Unknown tier: {req.tier}")
        log.warning("DEMO_MODE tier flip via legacy /upgrade user=%s tier=%s",
                    user["user_id"], req.tier)
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"tier": req.tier, "tier_updated_at": datetime.now(timezone.utc)}},
        )
        return {"ok": True, "tier": req.tier, "mocked": True}

    return router
