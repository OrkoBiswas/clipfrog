import hashlib
import hmac
import json
import time
from typing import Any, Protocol

import httpx

from clipforge_api.config import settings


class BillingProvider(Protocol):
    def request(
        self, method: str, path: str, data: dict[str, str] | None = None, key: str | None = None
    ) -> dict[str, Any]: ...


class StripeProvider:
    def request(
        self, method: str, path: str, data: dict[str, str] | None = None, key: str | None = None
    ) -> dict[str, Any]:
        secret = settings().stripe_secret_key
        if not secret:
            raise ValueError("Billing is not configured on this server.")
        headers = {"Authorization": f"Bearer {secret}"}
        if key:
            headers["Idempotency-Key"] = key
        response = httpx.request(
            method, f"https://api.stripe.com/v1/{path}", data=data, headers=headers, timeout=20
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


def verify_event(payload: bytes, signature: str, secret: str) -> dict[str, Any]:
    """Authenticate the exact raw body with bounded timestamp replay tolerance."""
    if not secret or len(payload) > 1024 * 1024:
        raise ValueError("Webhook unavailable or payload too large.")
    parts: dict[str, list[str]] = {}
    for part in signature.split(","):
        key, _, value = part.partition("=")
        parts.setdefault(key, []).append(value)
    try:
        timestamp = int(parts["t"][0])
    except (KeyError, ValueError, IndexError) as exc:
        raise ValueError("Invalid webhook signature.") from exc
    if abs(time.time() - timestamp) > 300:
        raise ValueError("Expired webhook signature.")
    expected = hmac.new(
        secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, value) for value in parts.get("v1", [])):
        raise ValueError("Invalid webhook signature.")
    event = json.loads(payload)
    if (
        not isinstance(event, dict)
        or not isinstance(event.get("id"), str)
        or len(event["id"]) > 100
        or not isinstance(event.get("type"), str)
    ):
        raise ValueError("Invalid event envelope.")
    return event


provider: BillingProvider = StripeProvider()
