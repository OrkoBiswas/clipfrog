import time
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from clipforge_api.config import settings
from clipforge_api.models import BillingEvent, Subscription, User
from clipforge_api.security import CurrentUser, Db
from clipforge_api.services import billing
from clipforge_api.services.usage import snapshot

router = APIRouter(tags=["Usage and billing"])


@router.get("/usage")
def usage(db: Db, user: CurrentUser) -> dict[str, object]:
    result = snapshot(db, user.id)
    result["billing_enabled"] = bool(
        settings().stripe_secret_key and settings().stripe_webhook_secret
    )
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    result["customer_portal_available"] = bool(subscription)
    result["subscription_status"] = subscription.status if subscription else "free"
    result["administrator"] = user.is_admin
    return result


class CheckoutInput(BaseModel):
    plan: Literal["creator", "pro"]


@router.post("/billing/checkout")
def checkout(body: CheckoutInput, db: Db, user: CurrentUser) -> dict[str, str]:
    if user.is_admin:
        raise HTTPException(409, "Administrator accounts have unlimited usage and do not need a plan.")
    cfg = settings()
    price = cfg.stripe_price_creator if body.plan == "creator" else cfg.stripe_price_pro
    if not cfg.stripe_secret_key or not cfg.stripe_webhook_secret or not price:
        raise HTTPException(503, "This plan is not configured for checkout.")
    db.execute(select(User).where(User.id == user.id).with_for_update())
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if subscription and subscription.status in {"active", "trialing"}:
        raise HTTPException(409, "Use the billing portal to change your active subscription.")
    try:
        if not subscription:
            customer = billing.provider.request(
                "POST",
                "customers",
                {"email": user.email, "metadata[user_id]": str(user.id)},
                f"customer:{user.id}",
            )
            subscription = Subscription(user_id=user.id, customer_id=customer["id"])
            db.add(subscription)
            db.commit()
        session = billing.provider.request(
            "POST",
            "checkout/sessions",
            {
                "customer": subscription.customer_id,
                "mode": "subscription",
                "line_items[0][price]": price,
                "line_items[0][quantity]": "1",
                "client_reference_id": str(user.id),
                "subscription_data[metadata][user_id]": str(user.id),
                "success_url": cfg.app_url + "/billing?checkout=complete",
                "cancel_url": cfg.app_url + "/billing",
            },
            f"checkout:{user.id}:{body.plan}:{int(time.time()) // 300}",
        )
        return {"url": str(session["url"])}
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(502, "The billing provider is unavailable. Please retry.") from None


@router.post("/billing/portal")
def portal(db: Db, user: CurrentUser) -> dict[str, str]:
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if not subscription:
        raise HTTPException(409, "No billing account exists yet.")
    try:
        session = billing.provider.request(
            "POST",
            "billing_portal/sessions",
            {
                "customer": subscription.customer_id,
                "return_url": settings().app_url + "/billing",
            },
        )
        return {"url": str(session["url"])}
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(502, "The billing portal is unavailable.") from None


@router.post("/billing/webhook")
async def webhook(request: Request, db: Db) -> dict[str, bool]:
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 1024 * 1024:
            raise HTTPException(413, "Webhook payload too large.")
    try:
        event = billing.verify_event(
            bytes(payload),
            request.headers.get("stripe-signature", ""),
            settings().stripe_webhook_secret,
        )
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid webhook.") from None
    if db.get(BillingEvent, event["id"]):
        return {"received": True}
    if event["type"] in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "checkout.session.completed",
    }:
        obj = event.get("data", {}).get("object", {})
        customer = obj.get("customer")
        subscription = db.scalar(
            select(Subscription).where(Subscription.customer_id == customer).with_for_update()
        )
        if not subscription:
            raise HTTPException(409, "Customer is not synchronized yet; retry this event.")
        identifier = (
            obj.get("subscription")
            if event["type"] == "checkout.session.completed"
            else obj.get("id")
        )
        if (
            not isinstance(identifier, str)
            or not identifier.startswith("sub_")
            or "/" in identifier
        ):
            raise HTTPException(400, "Invalid subscription reference.")
        try:
            # Fetch authoritative current state, so out-of-order webhooks cannot restore old plans.
            current = billing.provider.request("GET", f"subscriptions/{identifier}")
        except (httpx.HTTPError, ValueError):
            raise HTTPException(
                502, "Could not synchronize subscription; retry this event."
            ) from None
        if current.get("customer") != customer:
            raise HTTPException(400, "Subscription customer mismatch.")
        prices = {settings().stripe_price_creator: "creator", settings().stripe_price_pro: "pro"}
        items = current.get("items", {}).get("data", [])
        price = items[0].get("price", {}).get("id", "") if items else ""
        subscription.plan = prices.get(price, "free") if price else "free"
        subscription.status = str(current.get("status", "inactive"))
        subscription.subscription_id = identifier
    db.add(BillingEvent(id=event["id"]))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"received": True}
