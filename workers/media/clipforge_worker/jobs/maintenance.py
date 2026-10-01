from datetime import timedelta

from clipforge_api.config import settings
from clipforge_api.db import SessionLocal, engine
from clipforge_api.models import (
    AuthSession,
    AuthToken,
    MediaAsset,
    ProcessingJob,
    Project,
    UploadSession,
    now,
)
from clipforge_api.services.multipart import discard
from clipforge_api.services.usage import settle
from clipforge_api.storage import s3
from sqlalchemy import delete, or_, select, text

from clipforge_worker.celery_app import celery


@celery.task(name="clipforge.maintenance")
def maintain() -> None:
    """Recover committed-but-undelivered tasks; never steal a live advisory lock."""
    cutoff = now() - timedelta(minutes=5)
    with SessionLocal() as db:
        jobs = list(
            db.scalars(
                select(ProcessingJob)
                .where(
                    ProcessingJob.status.in_(["QUEUED", "RETRYING", "RUNNING", "CANCEL_REQUESTED"]),
                    ProcessingJob.created_at < cutoff,
                    or_(ProcessingJob.heartbeat_at.is_(None), ProcessingJob.heartbeat_at < cutoff),
                )
                .limit(100)
            )
        )
        for item in jobs:
            requeue = False
            with engine.connect() as lock:
                key = item.id.int % (2**63 - 1)
                if not lock.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
                ).scalar():
                    continue
                try:
                    # Refresh under the same lock order as job transitions/API operations.
                    db.execute(
                        select(Project).where(Project.id == item.project_id).with_for_update()
                    )
                    db.refresh(item, with_for_update=True)
                    if item.status not in {"QUEUED", "RETRYING", "RUNNING", "CANCEL_REQUESTED"}:
                        db.rollback()
                        continue
                    if item.status == "CANCEL_REQUESTED":
                        item.status, item.finished_at = "CANCELED", now()
                        settle(db, item, False)
                        project = db.get(Project, item.project_id)
                        if project:
                            project.status = "CANCELED"
                    else:
                        item.status, item.heartbeat_at = "RETRYING", now()
                    db.commit()
                    requeue = item.status == "RETRYING"
                finally:
                    lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            if requeue:
                celery.send_task(
                    f"clipforge.{item.job_type}",
                    args=[str(item.id)],
                    task_id=str(item.id),
                    queue=item.queue,
                )
        for project in db.scalars(select(Project).where(Project.status == "DELETING").limit(100)):
            celery.send_task("clipforge.cleanup", args=[str(project.id)], queue="maintenance")
        for upload in db.scalars(
            select(UploadSession)
            .where(UploadSession.status == "UPLOADING", UploadSession.expires_at < now())
            .limit(100)
        ):
            project = db.scalar(
                select(Project).where(Project.id == upload.project_id).with_for_update()
            )
            db.refresh(upload, with_for_update=True)
            if upload.status != "UPLOADING":
                continue
            asset = db.get(MediaAsset, upload.asset_id)
            if asset:
                discard(s3(), settings().s3_bucket, asset.storage_key, upload.upload_id)
                asset.size_bytes = 0
            upload.status = "EXPIRED"
            if project and project.status == "UPLOADING":
                project.status = "DRAFT"
            db.commit()
        db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
        db.execute(delete(AuthToken).where(AuthToken.expires_at < now()))
        db.commit()
        # Disabled by default. Only idle, inactive projects qualify; normal cleanup
        # retains ownership records until object deletion succeeds and is retryable.
        days = settings().media_retention_days
        if days:
            expired = list(db.scalars(select(Project.id).where(
                Project.updated_at < now() - timedelta(days=days),
                Project.status.not_in(["DELETING", "UPLOADING"]),
            ).limit(100)))
            for identifier in expired:
                project = db.scalar(select(Project).where(Project.id == identifier).with_for_update())
                if not project or project.updated_at >= now() - timedelta(days=days):
                    continue
                active = db.scalar(select(ProcessingJob.id).where(
                    ProcessingJob.project_id == identifier,
                    ProcessingJob.status.in_(["QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"]),
                ).limit(1))
                if active or project.status in {"DELETING", "UPLOADING"}:
                    continue
                project.status = "DELETING"
                db.commit()
                celery.send_task("clipforge.cleanup", args=[str(identifier)], queue="maintenance")
