"""Integrations: YouTube Data API + Stripe.

Both gracefully degrade when keys aren't configured.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
import stripe
from fastapi import APIRouter, HTTPException, Query

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "").strip()

if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY


def make_integrations_router():
    router = APIRouter(prefix="/integrations", tags=["integrations"])

    @router.get("/youtube/channel")
    async def youtube_channel(handle: str = Query(..., min_length=1)) -> dict[str, Any]:
        """Public lookup of YouTube channel stats by handle (no OAuth needed)."""
        if not YOUTUBE_API_KEY:
            raise HTTPException(503, "YouTube not connected. Set YOUTUBE_API_KEY in backend/.env.")
        clean = handle.lstrip("@")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "snippet,statistics", "forHandle": clean, "key": YOUTUBE_API_KEY},
            )
        if r.status_code != 200:
            raise HTTPException(502, f"YouTube API error {r.status_code}: {r.text[:200]}")
        data = r.json()
        items = data.get("items") or []
        if not items:
            raise HTTPException(404, f"No YouTube channel found for @{clean}")
        ch = items[0]
        s = ch.get("statistics", {})
        sn = ch.get("snippet", {})
        return {
            "id": ch.get("id"),
            "handle": clean,
            "title": sn.get("title"),
            "description": sn.get("description"),
            "thumbnail": (sn.get("thumbnails", {}).get("high") or {}).get("url"),
            "subscribers": int(s.get("subscriberCount", 0)),
            "views": int(s.get("viewCount", 0)),
            "videos": int(s.get("videoCount", 0)),
            "published_at": sn.get("publishedAt"),
        }

    @router.get("/stripe/status")
    async def stripe_status() -> dict[str, Any]:
        """Confirm Stripe is wired. Returns mode + recent payment summary if possible."""
        if not STRIPE_API_KEY:
            return {"connected": False, "mode": None}
        try:
            # Cheap call to verify key
            balance = await _to_thread(stripe.Balance.retrieve)
            available = sum(b["amount"] for b in balance.get("available", [])) / 100.0
            pending = sum(b["amount"] for b in balance.get("pending", [])) / 100.0
            charges = await _to_thread(stripe.Charge.list, limit=5)
            recent = [
                {
                    "id": c["id"],
                    "amount": c["amount"] / 100.0,
                    "currency": c["currency"],
                    "description": c.get("description") or "Payment",
                    "status": c["status"],
                    "created": c["created"],
                }
                for c in charges.get("data", [])
            ]
            return {
                "connected": True,
                "mode": "test" if STRIPE_API_KEY.startswith("sk_test") else "live",
                "available_balance": available,
                "pending_balance": pending,
                "recent_charges": recent,
            }
        except stripe.error.StripeError as e:
            return {"connected": False, "mode": None, "error": str(e)}
        except Exception as e:
            return {"connected": False, "mode": None, "error": str(e)}

    return router


# Helper — stripe SDK is sync; run in thread to avoid blocking the loop
import asyncio
import functools

async def _to_thread(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
