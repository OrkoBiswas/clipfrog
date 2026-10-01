import uuid
from unittest.mock import MagicMock

from clipforge_api.db import get_db
from clipforge_api.main import app
from clipforge_api.models import ProcessingJob, Project


def test_failed_job_redelivery_requires_explicit_retry(client, monkeypatch):
    from clipforge_worker.jobs import runtime

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "redelivery@example.com",
            "name": "Redelivery",
            "password": "long-enough-password",
        },
    ).raise_for_status()
    project_id = client.post("/api/v1/projects", json={"name": "Failed delivery"}).json()["id"]
    identifier = uuid.uuid4()
    for db in app.dependency_overrides[get_db]():
        project = db.get(Project, uuid.UUID(project_id))
        project.status = "FAILED"
        db.add(
            ProcessingJob(
                id=identifier,
                project_id=project.id,
                user_id=project.user_id,
                job_type="analyze",
                status="FAILED",
                attempts=1,
            )
        )
        db.commit()
        monkeypatch.setattr(runtime, "SessionLocal", lambda session=db: session)
        lock_engine = MagicMock()
        lock_engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = True
        monkeypatch.setattr(runtime, "engine", lock_engine)
        with runtime.run_job(str(identifier), "ANALYZING") as context:
            assert context is None
        job = db.get(ProcessingJob, identifier)
        assert job.status == "FAILED" and job.attempts == 1
        assert db.get(Project, uuid.UUID(project_id)).status == "FAILED"


def test_pending_cancel_blocks_delete_and_retry(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "jobs@example.com",
            "name": "Jobs",
            "password": "long-enough-password",
        },
    )
    project_id = client.post("/api/v1/projects", json={"name": "Job states"}).json()["id"]
    running, failed = uuid.uuid4(), uuid.uuid4()
    for db in app.dependency_overrides[get_db]():
        project = db.get(Project, uuid.UUID(project_id))
        for identifier, status in [(running, "RUNNING"), (failed, "FAILED")]:
            db.add(
                ProcessingJob(
                    id=identifier,
                    project_id=project.id,
                    user_id=project.user_id,
                    job_type="analyze",
                    status=status,
                )
            )
        db.commit()
    base = f"/api/v1/projects/{project_id}"
    assert client.post(f"{base}/jobs/{failed}/retry").status_code == 409
    assert client.post(f"{base}/jobs/{running}/cancel").json()["status"] == "CANCEL_REQUESTED"
    job = next(j for j in client.get(f"{base}/jobs").json() if j["id"] == str(running))
    assert job["finished_at"] is None
    assert client.delete(base).status_code == 409
    assert client.post(f"{base}/jobs/{failed}/retry").status_code == 409


def test_queue_failure_is_visible_on_project(client, monkeypatch):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "queue@example.com",
            "name": "Queue",
            "password": "long-enough-password",
        },
    )
    project_id = client.post("/api/v1/projects", json={"name": "Queue failure"}).json()["id"]
    identifier = uuid.uuid4()
    for db in app.dependency_overrides[get_db]():
        project = db.get(Project, uuid.UUID(project_id))
        db.add(
            ProcessingJob(
                id=identifier,
                project_id=project.id,
                user_id=project.user_id,
                job_type="analyze",
                status="FAILED",
            )
        )
        db.commit()

    def unavailable(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr("clipforge_api.routes.jobs.celery.send_task", unavailable)
    base = f"/api/v1/projects/{project_id}"
    assert client.post(f"{base}/jobs/{identifier}/retry").status_code == 503
    assert client.get(base).json()["status"] == "FAILED"
    assert client.get(f"{base}/jobs").json()[0]["error_code"] == "QUEUE_UNAVAILABLE"
