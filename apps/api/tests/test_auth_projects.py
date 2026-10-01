def register(client, email="creator@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": "Creator", "password": "a-strong-password-123"},
    )


def test_auth_lifecycle(client):
    assert client.get("/api/v1/me").status_code == 401
    response = register(client)
    assert response.status_code == 201
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "password_hash" not in response.json()
    assert client.get("/api/v1/me").json()["email"] == "creator@example.com"
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "creator@example.com", "password": "wrong-password-123"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "creator@example.com", "password": "a-strong-password-123"},
        ).status_code
        == 200
    )


def test_crud_and_ownership(client):
    register(client)
    response = client.post("/api/v1/projects", json={"name": "Podcast episode"})
    assert response.status_code == 201
    project_id = response.json()["id"]
    assert client.get("/api/v1/projects").json()[0]["name"] == "Podcast episode"
    assert (
        client.put(f"/api/v1/projects/{project_id}", json={"name": "Renamed"}).json()["name"]
        == "Renamed"
    )
    client.post("/api/v1/auth/logout")
    register(client, "other@example.com")
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 404
    assert client.get("/api/v1/projects").json() == []
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/login",
        json={"email": "creator@example.com", "password": "a-strong-password-123"},
    )
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204
    assert client.get("/api/v1/projects").json() == []


def test_csrf_and_validation(client):
    assert (
        client.post(
            "/api/v1/auth/register", headers={"Origin": "https://evil.example"}, json={}
        ).status_code
        == 403
    )
    register(client)
    assert client.post("/api/v1/projects", json={"name": " "}).status_code == 422
    assert (
        client.post(
            "/api/v1/projects",
            json={"name": "Test", "processing_config": {"duration_min": 60, "duration_max": 20}},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/projects", json={"name": "Test", "processing_config": {"clip_count": 101}}
        ).status_code
        == 422
    )
    assert client.get("/openapi.json").status_code == 200


def test_duplicate_registration_and_expired_token(client):
    register(client)
    assert register(client).status_code == 409
    assert (
        client.post(
            "/api/v1/auth/reset-password", json={"token": "x" * 64, "password": "new-long-password"}
        ).status_code
        == 400
    )


def test_admin_access_and_registration_cannot_escalate(client):
    from clipforge_api.db import get_db
    from clipforge_api.main import app
    from clipforge_api.models import User
    from sqlalchemy import select

    register(client)
    project_id = client.post("/api/v1/projects", json={"name": "Owner project"}).json()["id"]
    client.post("/api/v1/auth/logout")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@example.com",
            "name": "Admin",
            "password": "a-strong-password-123",
            "is_admin": True,
        },
    )
    assert response.json()["is_admin"] is False
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
    for db in app.dependency_overrides[get_db]():
        user = db.scalar(select(User).where(User.email == "admin@example.com"))
        user.is_admin = True
        db.commit()
    assert client.get("/api/v1/me").json()["is_admin"] is True
    assert client.get("/api/v1/projects").json()[0]["id"] == project_id
    assert client.get("/api/v1/dashboard").json()["projects"] == 1
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/jobs").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}/source").status_code == 200
    assert (
        client.put(f"/api/v1/projects/{project_id}", json={"name": "Admin updated"}).status_code
        == 200
    )
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204


def test_admin_bulk_delete_is_guarded_and_uses_project_cleanup(client, monkeypatch):
    import uuid

    from clipforge_api.db import get_db
    from clipforge_api.main import app
    from clipforge_api.models import MediaAsset, ProcessingJob, Project, User
    from sqlalchemy import select

    register(client)
    first_id = client.post("/api/v1/projects", json={"name": "No media"}).json()["id"]
    second_id = client.post("/api/v1/projects", json={"name": "Has media"}).json()["id"]
    for db in app.dependency_overrides[get_db]():
        owner = db.scalar(select(User).where(User.email == "creator@example.com"))
        project = db.get(Project, uuid.UUID(second_id))
        db.add(
            MediaAsset(
                id=uuid.uuid4(),
                project_id=project.id,
                user_id=owner.id,
                type="SOURCE",
                storage_key="bulk-delete-source.mp4",
                original_filename="source.mp4",
                mime_type="video/mp4",
                size_bytes=1000,
            )
        )
        job = ProcessingJob(
            user_id=owner.id,
            project_id=project.id,
            job_type="analyze",
            status="QUEUED",
        )
        db.add(job)
        db.commit()
        job_id = job.id

    path = "/api/v1/admin/projects/bulk-delete"
    project_ids = [first_id, second_id]
    assert client.post(path, json={"project_ids": project_ids}).status_code == 403
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "name": "Admin", "password": "a-strong-password-123"},
    )
    for db in app.dependency_overrides[get_db]():
        admin = db.scalar(select(User).where(User.email == "admin@example.com"))
        admin.is_admin = True
        db.commit()

    queued = []
    monkeypatch.setattr(
        "clipforge_api.routes.projects.celery.send_task",
        lambda name, *args, **kwargs: queued.append((name, args, kwargs)),
    )
    projects = client.get("/api/v1/projects").json()
    assert {item["owner_email"] for item in projects} == {"creator@example.com"}
    response = client.post(path, json={"project_ids": project_ids})
    assert response.status_code == 409
    assert client.get(f"/api/v1/projects/{first_id}").status_code == 200
    for db in app.dependency_overrides[get_db]():
        db.get(ProcessingJob, job_id).status = "FAILED"
        db.commit()

    response = client.post(path, json={"project_ids": project_ids})
    assert response.status_code == 200
    assert set(response.json()["deleted"]) == {first_id}
    assert set(response.json()["queued_for_cleanup"]) == {second_id}
    assert queued == [
        ("clipforge.cleanup", (), {"args": [second_id], "queue": "maintenance"})
    ]
    for db in app.dependency_overrides[get_db]():
        assert db.get(Project, uuid.UUID(first_id)) is None
        assert db.get(Project, uuid.UUID(second_id)).status == "DELETING"
