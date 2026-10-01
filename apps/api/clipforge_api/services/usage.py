import uuid
from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clipforge_api.models import (
    BrandKit,
    MediaAsset,
    ProcessingJob,
    Subscription,
    UsageLedger,
    User,
    now,
)


def stored_bytes(db: Session, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(select(func.sum(MediaAsset.size_bytes)).where(MediaAsset.user_id == user_id)) or 0
    ) + int(db.scalar(select(func.sum(BrandKit.logo_size)).where(BrandKit.user_id == user_id)) or 0)


@dataclass(frozen=True)
class Allowance:
    input_minutes: int | None
    render_minutes: int | None
    storage_bytes: int | None


PLANS = {
    "free": Allowance(60, 30, 5 * 1024**3),
    "creator": Allowance(600, 300, 50 * 1024**3),
    "pro": Allowance(2400, 1200, 200 * 1024**3),
    "admin": Allowance(None, None, None),
}


class QuotaExceeded(ValueError):
    code = "QUOTA_EXCEEDED"


def plan_for(db: Session, user_id: uuid.UUID) -> str:
    user = db.get(User, user_id)
    if user and user.is_admin:
        return "admin"
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    return (
        subscription.plan
        if subscription
        and subscription.status in {"active", "trialing"}
        and subscription.plan in PLANS
        else "free"
    )


def snapshot(db: Session, user_id: uuid.UUID) -> dict[str, object]:
    plan = plan_for(db, user_id)
    month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage = {
        metric: float(
            db.scalar(
                select(func.sum(UsageLedger.quantity)).where(
                    UsageLedger.user_id == user_id,
                    UsageLedger.metric == metric,
                    UsageLedger.created_at >= month,
                )
            )
            or 0
        )
        for metric in ["input_minutes", "render_minutes"]
    }
    usage["storage_bytes"] = float(stored_bytes(db, user_id))
    return {
        "plan": plan,
        "allowance": asdict(PLANS[plan]),
        "usage": usage,
        "period_start": month.isoformat(),
    }


def storage_check(db: Session, user_id: uuid.UUID, additional: int) -> None:
    limit = PLANS[plan_for(db, user_id)].storage_bytes
    if limit is None:
        return
    db.execute(select(User).where(User.id == user_id).with_for_update())
    occupied = stored_bytes(db, user_id)
    if occupied + additional > limit:
        raise QuotaExceeded(
            "Storage allowance exceeded. Remove unused projects or upgrade your plan."
        )


def reserve(db: Session, job: ProcessingJob, metric: str, quantity: float) -> None:
    if quantity <= 0:
        return
    db.execute(select(User).where(User.id == job.user_id).with_for_update())
    key = f"job:{job.id}:{metric}"
    if db.scalar(select(UsageLedger.id).where(UsageLedger.idempotency_key == key)):
        return
    month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = (
        db.scalar(
            select(func.sum(UsageLedger.quantity)).where(
                UsageLedger.user_id == job.user_id,
                UsageLedger.metric == metric,
                UsageLedger.created_at >= month,
            )
        )
        or 0
    )
    limit = getattr(PLANS[plan_for(db, job.user_id)], metric)
    if limit is not None and used + quantity > limit:
        raise QuotaExceeded(
            f"Monthly {metric.replace('_', ' ')} allowance exceeded. Reduce the batch or upgrade your plan."
        )
    db.add(
        UsageLedger(
            user_id=job.user_id,
            project_id=job.project_id,
            metric=metric,
            quantity=quantity,
            unit="minutes",
            idempotency_key=key,
            details={"status": "RESERVED", "job_id": str(job.id)},
        )
    )
    job.parameters = {**(job.parameters or {}), "usage_metric": metric, "usage_quantity": quantity}


def settle(db: Session, job: ProcessingJob, success: bool) -> None:
    metric = job.parameters.get("usage_metric")
    if not metric:
        return
    row = db.scalar(
        select(UsageLedger).where(UsageLedger.idempotency_key == f"job:{job.id}:{metric}")
    )
    if row:
        if success:
            row.details = {**row.details, "status": "COMPLETED"}
        else:
            db.delete(row)
