"""Razorpay Payment Links client — lean, no SDK, direct httpx against the REST API.

Reads credentials from env at import:
  RAZORPAY_KEY_ID      - required for real flow (dormant when empty)
  RAZORPAY_KEY_SECRET  - required for real flow

Payment Links are one-time payments (not recurring subscriptions) — used here
as a single "subscribe this month" charge, mirroring how the mock/PayPal
checkout flips a tier on one successful payment.

Public helpers:
  is_configured()                        → bool
  usd_to_paise(amount_usd)                → int (INR paise, test-mode approx conversion)
  create_payment_link(...)                → { id, short_url }
  verify_payment_link_signature(...)      → bool (constant-time HMAC check)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any, Optional

import httpx

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()

_BASE = "https://api.razorpay.com/v1"

# Test-mode Payment Links only support charging in the account's home
# currency (INR for Indian test accounts). This fixed rate is ONLY used to
# show an approximate ₹ amount at Razorpay's own checkout step — the $
# price shown everywhere else in CreatorOS is unaffected.
USD_TO_INR_RATE = 83.0


def is_configured() -> bool:
    return bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)


def usd_to_paise(amount_usd: float) -> int:
    """Convert a USD tier price to INR paise (integer minor units)."""
    return round(amount_usd * USD_TO_INR_RATE * 100)


async def create_payment_link(
    *,
    amount_usd: float,
    description: str,
    reference_id: str,
    callback_url: str,
    notes: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Create a Razorpay Payment Link and return {id, short_url, amount_paise}."""
    if not is_configured():
        raise RuntimeError("Razorpay not configured")

    amount_paise = usd_to_paise(amount_usd)
    body = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": description[:255],
        "reference_id": reference_id,
        "notify": {"email": False, "sms": False},
        "reminder_enable": False,
        "expire_by": int(time.time()) + 3600,  # 1 hour to complete
        "notes": notes or {},
        "callback_url": callback_url,
        "callback_method": "get",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_BASE}/payment_links",
            json=body,
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "id": data["id"],
            "short_url": data["short_url"],
            "amount_paise": amount_paise,
            "raw": data,
        }


def verify_payment_link_signature(
    *,
    payment_link_id: str,
    reference_id: str,
    status: str,
    payment_id: str,
    signature: str,
) -> bool:
    """Constant-time HMAC-SHA256 check per Razorpay's exact field order for
    Payment Link callbacks. Never trust the callback without this passing."""
    if not is_configured():
        return False
    message = "|".join([payment_link_id, reference_id, status, payment_id])
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
