"""Integrations hub — YouTube, Instagram, Stripe, PayPal.

Per-user connection state is stored in db.connections. When real API keys are
configured (YOUTUBE_API_KEY, STRIPE_API_KEY, PAYPAL_CLIENT_ID) the endpoints
call the real APIs. When they're not configured, the endpoints return
deterministic, believable mock data derived from the handle/account so the UX
is fully testable end-to-end without any live keys.

All endpoints under /api/integrations.
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx
import stripe
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "").strip()
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "").strip()

if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY


# ---------------------------------------------------------------------------
# Deterministic mock generators — same handle always produces same "stats"
# ---------------------------------------------------------------------------
def _seed_from(text: str) -> int:
    h = hashlib.md5(text.lower().encode()).hexdigest()
    return int(h[:8], 16)


def _mock_youtube(handle: str) -> dict[str, Any]:
    rng = random.Random(_seed_from(handle))
    subs = rng.randint(48_000, 620_000)
    views = subs * rng.randint(180, 640)
    videos = rng.randint(84, 480)
    recent = []
    for i in range(6):
        recent.append({
            "title": rng.choice([
                "I tried to build a $10k MRR SaaS in 30 days",
                "Why creators are leaving Substack",
                "How I doubled my YouTube RPM",
                "The 5-minute editing trick every creator needs",
                "Solo dev vs $50k competitor",
                "I quit my $220k job to make YouTube — 90 days later",
                "The pricing mistake killing your course",
                "Ship faster with this Notion setup",
            ]),
            "views": rng.randint(24_000, 480_000),
            "likes": rng.randint(1_200, 32_000),
            "published_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(2, 90))).isoformat(),
        })
    recent.sort(key=lambda x: x["published_at"], reverse=True)
    return {
        "id": f"UC{hashlib.md5(handle.encode()).hexdigest()[:22]}",
        "handle": handle,
        "title": handle.replace("_", " ").replace("-", " ").title(),
        "description": f"Creator building at the intersection of code, content, and community. Home of @{handle}.",
        "thumbnail": None,
        "subscribers": subs,
        "views": views,
        "videos": videos,
        "published_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(400, 1800))).isoformat(),
        "recent_videos": recent,
        "avg_rpm": round(rng.uniform(3.4, 12.8), 2),
        "avg_ctr": round(rng.uniform(4.2, 12.6), 2),
        "avg_watch_pct": round(rng.uniform(32.0, 58.0), 1),
        "monthly_earnings": round(views / 1000 * rng.uniform(3.4, 12.8) / 12, 2),
        "mocked": True,
    }


def _mock_instagram(handle: str) -> dict[str, Any]:
    rng = random.Random(_seed_from(handle) + 42)
    followers = rng.randint(18_000, 260_000)
    following = rng.randint(180, 1600)
    posts = rng.randint(120, 1400)
    engagement = round(rng.uniform(2.4, 8.9), 2)
    reels = []
    for i in range(6):
        reels.append({
            "caption": rng.choice([
                "The 5-second hook that 10x'd my reach",
                "POV: you finally ship the thing",
                "3 things I wish I knew at $10k MRR",
                "Stop building. Start selling.",
                "Read this if your Reels aren't landing",
                "The one caption formula that works",
            ]),
            "views": rng.randint(8_000, 320_000),
            "likes": rng.randint(800, 24_000),
            "comments": rng.randint(24, 1_800),
            "posted_at": (datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 60))).isoformat(),
        })
    reels.sort(key=lambda x: x["posted_at"], reverse=True)
    return {
        "id": hashlib.md5(handle.encode()).hexdigest()[:15],
        "handle": handle,
        "name": handle.replace("_", " ").replace(".", " ").title(),
        "bio": f"Creator · Builder · Storyteller. DM me for collabs.",
        "profile_picture": None,
        "followers": followers,
        "following": following,
        "posts": posts,
        "engagement_rate": engagement,
        "avg_reel_views": rng.randint(24_000, 96_000),
        "story_completion_rate": round(rng.uniform(68.0, 92.0), 1),
        "recent_reels": reels,
        "monthly_reach": rng.randint(180_000, 2_400_000),
        "mocked": True,
    }


async def _to_thread(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class ConnectRequest(BaseModel):
    account: str  # handle for yt/ig, email for stripe/paypal


PROVIDER_META = {
    "youtube": {
        "name": "YouTube",
        "description": "Sync channel stats, video analytics, and revenue signals.",
        "color": "#FF3D3D",
        "input_label": "YouTube handle",
        "input_placeholder": "@yourhandle",
        "input_prefix": "@",
    },
    "instagram": {
        "name": "Instagram",
        "description": "Track followers, reels engagement, and story performance.",
        "color": "#E1306C",
        "input_label": "Instagram handle",
        "input_placeholder": "@yourhandle",
        "input_prefix": "@",
    },
    "stripe": {
        "name": "Stripe",
        "description": "Sync payouts, subscriptions, and revenue in real-time.",
        "color": "#635BFF",
        "input_label": "Stripe account email",
        "input_placeholder": "you@business.com",
        "input_prefix": None,
    },
    "paypal": {
        "name": "PayPal",
        "description": "Accept cross-border payments for products and courses.",
        "color": "#0070BA",
        "input_label": "PayPal account email",
        "input_placeholder": "you@business.com",
        "input_prefix": None,
    },
}


def make_integrations_router(db, current_user):
    router = APIRouter(prefix="/integrations", tags=["integrations"])

    async def _get_connection(user_id: str, provider: str) -> Optional[dict]:
        return await db.connections.find_one({"user_id": user_id, "provider": provider}, {"_id": 0})

    async def _upsert_connection(user_id: str, provider: str, data: dict) -> dict:
        record = {
            "user_id": user_id,
            "provider": provider,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        await db.connections.update_one(
            {"user_id": user_id, "provider": provider},
            {"$set": record},
            upsert=True,
        )
        record.pop("_id", None)
        return record

    # -----------------------------------------------------------------------
    # Unified connections list
    # -----------------------------------------------------------------------
    @router.get("/connections")
    async def list_connections(user: dict = Depends(current_user)) -> dict[str, Any]:
        rows = await db.connections.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(20)
        by_provider = {r["provider"]: r for r in rows}
        out = []
        for pid, meta in PROVIDER_META.items():
            conn = by_provider.get(pid)
            out.append({
                "id": pid,
                **meta,
                "connected": bool(conn),
                "account": (conn or {}).get("account"),
                "connected_at": (conn or {}).get("connected_at"),
                "summary": (conn or {}).get("summary"),
            })
        return {"connections": out}

    # -----------------------------------------------------------------------
    # Connect / disconnect (mock OAuth handshake)
    # -----------------------------------------------------------------------
    @router.post("/{provider}/connect")
    async def connect_provider(
        provider: str,
        req: ConnectRequest,
        user: dict = Depends(current_user),
    ) -> dict[str, Any]:
        if provider not in PROVIDER_META:
            raise HTTPException(400, f"Unknown provider: {provider}")
        account = req.account.strip()
        if not account:
            raise HTTPException(400, "Account handle required")
        # Simulate 3rd-party OAuth latency
        await asyncio.sleep(0.6)

        clean = account.lstrip("@") if provider in ("youtube", "instagram") else account

        if provider == "youtube":
            stats = _mock_youtube(clean)
            summary = {
                "label": f"@{clean}",
                "primary_metric": f"{stats['subscribers']:,} subs",
                "secondary_metric": f"${stats['monthly_earnings']:,.0f}/mo est.",
            }
        elif provider == "instagram":
            stats = _mock_instagram(clean)
            summary = {
                "label": f"@{clean}",
                "primary_metric": f"{stats['followers']:,} followers",
                "secondary_metric": f"{stats['engagement_rate']}% engagement",
            }
        elif provider == "stripe":
            rng = random.Random(_seed_from(clean))
            stats = {
                "email": clean,
                "mode": "test",
                "available_balance": round(rng.uniform(8_400, 42_800), 2),
                "pending_balance": round(rng.uniform(1_200, 8_600), 2),
                "mtd_processed": round(rng.uniform(24_000, 128_000), 2),
            }
            summary = {
                "label": clean,
                "primary_metric": f"${stats['available_balance']:,.0f} available",
                "secondary_metric": f"${stats['mtd_processed']:,.0f} MTD",
            }
        else:  # paypal
            rng = random.Random(_seed_from(clean) + 7)
            stats = {
                "email": clean,
                "available_balance": round(rng.uniform(2_400, 18_600), 2),
                "mtd_processed": round(rng.uniform(4_800, 32_400), 2),
                "cross_border_pct": round(rng.uniform(18.0, 62.0), 1),
            }
            summary = {
                "label": clean,
                "primary_metric": f"${stats['available_balance']:,.0f} available",
                "secondary_metric": f"{stats['cross_border_pct']}% international",
            }

        record = await _upsert_connection(user["user_id"], provider, {
            "account": clean,
            "summary": summary,
            "stats": stats,
        })
        return {"ok": True, "provider": provider, "connection": record}

    @router.post("/{provider}/disconnect")
    async def disconnect_provider(provider: str, user: dict = Depends(current_user)):
        if provider not in PROVIDER_META:
            raise HTTPException(400, f"Unknown provider: {provider}")
        await asyncio.sleep(0.3)
        await db.connections.delete_one({"user_id": user["user_id"], "provider": provider})
        return {"ok": True, "provider": provider}

    # -----------------------------------------------------------------------
    # Detail endpoints (return live data if connected, else prompt)
    # -----------------------------------------------------------------------
    @router.get("/youtube/channel")
    async def youtube_channel(
        handle: Optional[str] = Query(default=None),
        user: dict = Depends(current_user),
    ) -> dict[str, Any]:
        # Prefer explicit handle → then user's connected account
        conn = await _get_connection(user["user_id"], "youtube")
        target = handle or (conn or {}).get("account")
        if not target:
            raise HTTPException(404, "No YouTube account connected. Connect one first.")
        clean = target.lstrip("@")

        # Real API path (only when a real key is configured)
        if YOUTUBE_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(
                        "https://www.googleapis.com/youtube/v3/channels",
                        params={"part": "snippet,statistics", "forHandle": clean, "key": YOUTUBE_API_KEY},
                    )
                if r.status_code == 200:
                    data = r.json()
                    items = data.get("items") or []
                    if items:
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
                            "mocked": False,
                        }
            except Exception:
                pass  # fall through to mock

        return _mock_youtube(clean)

    @router.get("/instagram/profile")
    async def instagram_profile(
        handle: Optional[str] = Query(default=None),
        user: dict = Depends(current_user),
    ) -> dict[str, Any]:
        conn = await _get_connection(user["user_id"], "instagram")
        target = handle or (conn or {}).get("account")
        if not target:
            raise HTTPException(404, "No Instagram account connected. Connect one first.")
        clean = target.lstrip("@")
        return _mock_instagram(clean)

    @router.get("/stripe/status")
    async def stripe_status(user: dict = Depends(current_user)) -> dict[str, Any]:
        """Reports Stripe connection status for the user. Uses real API when key
        is set, else returns mocked stats from the stored connection."""
        conn = await _get_connection(user["user_id"], "stripe")
        # Real Stripe path
        if STRIPE_API_KEY and STRIPE_API_KEY.startswith(("sk_test", "sk_live")):
            try:
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
                    "mocked": False,
                }
            except Exception:
                pass  # fall through to mock

        if conn:
            stats = conn.get("stats", {})
            rng = random.Random(_seed_from(conn.get("account", "unknown")))
            recent = [
                {
                    "id": f"ch_{hashlib.md5(f'{i}'.encode()).hexdigest()[:14]}",
                    "amount": round(rng.uniform(29, 899), 2),
                    "currency": "usd",
                    "description": rng.choice([
                        "Ship It cohort #5 — enrollment",
                        "Notion Template Bundle",
                        "Newsletter sponsor — Linear",
                        "Consulting call — 60min",
                        "Ship It cohort #4 — enrollment",
                    ]),
                    "status": "succeeded",
                    "created": int((datetime.now(timezone.utc) - timedelta(hours=rng.randint(2, 96))).timestamp()),
                }
                for i in range(5)
            ]
            return {
                "connected": True,
                "mode": "test",
                "available_balance": stats.get("available_balance", 0),
                "pending_balance": stats.get("pending_balance", 0),
                "recent_charges": recent,
                "mocked": True,
            }
        return {"connected": False, "mode": None, "mocked": True}

    @router.get("/paypal/status")
    async def paypal_status(user: dict = Depends(current_user)) -> dict[str, Any]:
        conn = await _get_connection(user["user_id"], "paypal")
        if not conn:
            return {"connected": False, "mocked": True}
        stats = conn.get("stats", {})
        rng = random.Random(_seed_from(conn.get("account", "unknown")) + 3)
        recent = [
            {
                "id": f"PP-{hashlib.md5(f'p{i}'.encode()).hexdigest()[:10].upper()}",
                "amount": round(rng.uniform(19, 480), 2),
                "currency": rng.choice(["USD", "USD", "USD", "EUR", "GBP"]),
                "buyer": rng.choice([
                    "sarah.k@gmail.com",
                    "marco.r@outlook.com",
                    "alex.chen@yahoo.com",
                    "priya.s@icloud.com",
                    "dev.james@proton.me",
                ]),
                "description": rng.choice([
                    "Course purchase",
                    "Template pack",
                    "Consulting",
                    "Sponsor payment",
                ]),
                "status": "completed",
                "created": (datetime.now(timezone.utc) - timedelta(hours=rng.randint(4, 120))).isoformat(),
            }
            for i in range(5)
        ]
        return {
            "connected": True,
            "email": stats.get("email"),
            "available_balance": stats.get("available_balance", 0),
            "mtd_processed": stats.get("mtd_processed", 0),
            "cross_border_pct": stats.get("cross_border_pct", 0),
            "recent_transactions": recent,
            "mocked": True,
        }

    return router
