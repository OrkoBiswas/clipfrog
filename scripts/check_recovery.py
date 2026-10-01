"""Simulate a committed job whose queue publication was lost, then recover it."""

import json
import time
import uuid
from datetime import timedelta
from pathlib import Path

from clipforge_api.db import SessionLocal, engine
from clipforge_api.models import ProcessingJob, Project, now
from clipforge_worker.celery_app import celery
from sqlalchemy import text

fixture = json.loads(Path(".local/analysis-test.json").read_text())
locked_id = uuid.uuid4()
lock_key = locked_id.int % (2**63 - 1)
with engine.connect() as lock:
    lock.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
    try:
        with SessionLocal() as db:
            project = db.get(Project, uuid.UUID(fixture["project_id"]))
            assert project
            db.add(
                ProcessingJob(
                    id=locked_id,
                    project_id=project.id,
                    user_id=project.user_id,
                    job_type="highlights",
                    status="RUNNING",
                    created_at=now() - timedelta(minutes=6),
                    heartbeat_at=now() - timedelta(minutes=6),
                )
            )
            db.commit()
        celery.send_task("clipforge.maintenance", queue="maintenance").get(timeout=60)
        with SessionLocal() as db:
            job = db.get(ProcessingJob, locked_id)
            assert job and job.status == "RUNNING" and job.attempts == 0
            job.status = "CANCEL_REQUESTED"
            db.commit()
    finally:
        lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
celery.send_task("clipforge.maintenance", queue="maintenance").get(timeout=60)
with SessionLocal() as db:
    job = db.get(ProcessingJob, locked_id)
    assert job and job.status == "CANCELED" and job.finished_at is not None
print(
    "Live worker lock respected; interrupted cancellation settled after lock release.", flush=True
)

identifier = uuid.uuid4()
with SessionLocal() as db:
    project = db.get(Project, uuid.UUID(fixture["project_id"]))
    assert project
    db.add(
        ProcessingJob(
            id=identifier,
            project_id=project.id,
            user_id=project.user_id,
            job_type="highlights",
            created_at=now() - timedelta(minutes=6),
        )
    )
    project.status = "FINDING_HIGHLIGHTS"
    db.commit()
celery.send_task("clipforge.maintenance", queue="maintenance")
for _ in range(120):
    with SessionLocal() as db:
        job = db.get(ProcessingJob, identifier)
        assert job and job.status not in {"FAILED", "CANCELED"}, (
            job.error_message if job else "missing"
        )
        if job.status == "SUCCEEDED":
            assert job.attempts == 1
            print("Committed-but-undelivered job recovered through Celery and completed once.")
            break
    time.sleep(1)
else:
    raise TimeoutError("Job recovery did not complete")
