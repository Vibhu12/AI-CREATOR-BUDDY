"""PayPal Checkout (Orders v2) client — lean, modern, no deprecated SDK.

Uses httpx directly against the REST API. Reads credentials from env at import:
  PAYPAL_MODE          - "sandbox" (default) or "live"
  PAYPAL_CLIENT_ID     - required for real flow (dormant when empty)
  PAYPAL_CLIENT_SECRET - required for real flow

Public helpers:
  is_configured()          → bool; True when both client id + secret set
  create_order(...)        → { id, status, approval_url } | raises HTTPError
  capture_order(order_id)  → capture payload dict
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx

PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox").strip().lower()
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "").strip()
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "").strip()

_BASE = "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"

# Simple in-process token cache — access tokens live ~9 hours
_token_cache: dict[str, Any] = {"token": None, "expires_at": 0}


def is_configured() -> bool:
    return bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)


async def _get_access_token(client: httpx.AsyncClient) -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["token"]

    r = await client.post(
        f"{_BASE}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        timeout=15,
    )
    r.raise_for_status()
    payload = r.json()
    _token_cache["token"] = payload["access_token"]
    _token_cache["expires_at"] = now + int(payload.get("expires_in", 32000))
    return _token_cache["token"]


async def create_order(
    *,
    amount: float,
    currency: str = "USD",
    reference_id: str,
    description: str,
    return_url: str,
    cancel_url: str,
) -> dict[str, Any]:
    """Create a one-time PayPal order and return {id, status, approval_url}."""
    if not is_configured():
        raise RuntimeError("PayPal not configured")

    async with httpx.AsyncClient() as client:
        token = await _get_access_token(client)
        body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": reference_id,
                    "description": description[:127],
                    "amount": {
                        "currency_code": currency,
                        "value": f"{amount:.2f}",
                    },
                }
            ],
            "application_context": {
                "brand_name": "CreatorOS",
                "landing_page": "NO_PREFERENCE",
                "shipping_preference": "NO_SHIPPING",
                "user_action": "PAY_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }
        r = await client.post(
            f"{_BASE}/v2/checkout/orders",
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                # PayPal supports idempotency via PayPal-Request-Id
                "PayPal-Request-Id": reference_id,
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        approval_url: Optional[str] = None
        for link in data.get("links", []):
            if link.get("rel") in ("approve", "payer-action"):
                approval_url = link.get("href")
                break
        return {
            "id": data["id"],
            "status": data.get("status"),
            "approval_url": approval_url,
            "raw": data,
        }


async def capture_order(order_id: str) -> dict[str, Any]:
    """Capture an approved order. Returns the raw capture payload."""
    if not is_configured():
        raise RuntimeError("PayPal not configured")

    async with httpx.AsyncClient() as client:
        token = await _get_access_token(client)
        r = await client.post(
            f"{_BASE}/v2/checkout/orders/{order_id}/capture",
            json={},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                # Idempotent capture
                "PayPal-Request-Id": f"cap_{order_id}",
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json()


async def get_order(order_id: str) -> dict[str, Any]:
    if not is_configured():
        raise RuntimeError("PayPal not configured")
    async with httpx.AsyncClient() as client:
        token = await _get_access_token(client)
        r = await client.get(
            f"{_BASE}/v2/checkout/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
