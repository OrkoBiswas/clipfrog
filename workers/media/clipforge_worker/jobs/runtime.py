import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from clipforge_api.db import SessionLocal, engine
from clipforge_api.models import Clip, ProcessingJob, Project, now
from clipforge_api.services.usage import settle
from sqlalchemy import select, text

logger = logging.getLogger("clipforge.worker")


class JobCanceled(Exception):
    pass


class JobContext:
    def __init__(self, job_id: str):
        self.id = uuid.UUID(job_id)

    def progress(self, stage: str, percent: int) -> None:
        with SessionLocal() as db:
            job = db.get(ProcessingJob, self.id)
            if not job or job.status in {"CANCELED", "CANCEL_REQUESTED"}:
                raise JobCanceled()
            job.stage = stage
            job.heartbeat_at = now()
            job.progress = max(0, min(100, percent))
            db.commit()
            logger.info(
                "stage",
                extra={
                    "job_id": str(self.id),
                    "project_id": str(job.project_id),
                    "stage": stage,
                    "progress": percent,
                },
            )


@contextmanager
def run_job(job_id: str, project_status: str) -> Iterator[JobContext | None]:
    """Connection-scoped lock releases on worker loss; redelivery can resume safely."""
    context = JobContext(job_id)
    with engine.connect() as lock:
        lock_key = context.id.int % (2**63 - 1)
        if not lock.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}).scalar():
            yield None
            return
        try:
            with SessionLocal() as db:
                job = db.get(ProcessingJob, context.id)
                if job:
                    db.execute(
                        select(Project).where(Project.id == job.project_id).with_for_update()
                    )
                    job = db.scalar(
                        select(ProcessingJob)
                        .where(ProcessingJob.id == context.id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                if not job or job.status in {"SUCCEEDED", "CANCELED", "FAILED"}:
                    yield None
                    return
                if job.status == "CANCEL_REQUESTED":
                    settle(db, job, False)
                    job.status = "CANCELED"
                    job.finished_at = now()
                    project = db.get(Project, job.project_id)
                    if project:
                        project.status = "CANCELED"
                    db.commit()
                    yield None
                    return
                project = db.get(Project, job.project_id)
                assert project is not None
                job.status = "RUNNING"
                job.started_at = now()
                job.heartbeat_at = now()
                job.attempts += 1
                project.status = project_status
                db.commit()
            yield context
        except JobCanceled:
            with SessionLocal() as db:
                job = db.get(ProcessingJob, context.id)
                if job:
                    job.status = "CANCELED"
                    settle(db, job, False)
                    for value in job.parameters.get("clip_ids", []):
                        clip = db.get(Clip, uuid.UUID(value))
                        if clip and clip.status == "RENDERING":
                            clip.status = "CANCELED"
                    job.finished_at = now()
                    project = db.get(Project, job.project_id)
                    if project:
                        project.status = "CANCELED"
                    db.commit()
        except Exception as exc:
            logger.exception("Job failed", extra={"job_id": job_id})
            with SessionLocal() as db:
                job = db.get(ProcessingJob, context.id)
                if job:
                    job.status = "FAILED"
                    settle(db, job, False)
                    for value in job.parameters.get("clip_ids", []):
                        clip = db.get(Clip, uuid.UUID(value))
                        if clip and clip.status == "RENDERING":
                            clip.status = "FAILED"
                    job.error_code = getattr(exc, "code", "PROCESSING_FAILED")
                    job.error_message = (
                        str(exc)
                        if isinstance(exc, ValueError)
                        else "Processing failed. Retry, or check worker logs with the job ID."
                    )
                    job.finished_at = now()
                    project = db.get(Project, job.project_id)
                    if project:
                        project.status = "FAILED"
                    db.commit()
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})


def succeed(context: JobContext, status: str, stage: str = "Complete") -> None:
    context.progress("Finalizing", 99)
    with SessionLocal() as db:
        record = db.get(ProcessingJob, context.id)
        assert record
        # Match API lock ordering (project, then job) to avoid cancellation deadlocks.
        db.execute(select(Project).where(Project.id == record.project_id).with_for_update())
        job = db.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.id == context.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        assert job
        if job.status == "CANCEL_REQUESTED":
            raise JobCanceled()
        job.status = "SUCCEEDED"
        settle(db, job, True)
        job.progress = 100
        job.stage = stage
        job.finished_at = now()
        project = db.get(Project, job.project_id)
        assert project
        project.status = status
        db.commit()
