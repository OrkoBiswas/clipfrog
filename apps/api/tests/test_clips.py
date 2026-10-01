import uuid

from clipforge_api.db import get_db
from clipforge_api.main import app
from clipforge_api.models import MediaAsset, Project


def test_manual_clip_validation_and_owner_isolation(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "clips@example.com", "name": "Clips", "password": "long-enough-password"},
    )
    project_id = client.post("/api/v1/projects", json={"name": "Manual clips"}).json()["id"]
    for db in app.dependency_overrides[get_db]():
        project = db.get(Project, uuid.UUID(project_id))
        asset = MediaAsset(
            id=uuid.uuid4(),
            project_id=project.id,
            user_id=project.user_id,
            type="SOURCE",
            storage_key="test.mp4",
            original_filename="test.mp4",
            mime_type="video/mp4",
            size_bytes=1000,
            duration_ms=10000,
        )
        db.add(asset)
        project.source_asset_id = asset.id
        project.status = "UPLOADED"
        db.commit()
    base = f"/api/v1/projects/{project_id}/clips"
    payload = {"title": "A manual clip", "start_ms": 1000, "end_ms": 5000}
    assert client.post(base, json={**payload, "end_ms": 11000}).status_code == 422
    assert client.post(base, json={**payload, "start_ms": 6000}).status_code == 422
    result = client.post(base, json=payload)
    assert result.status_code == 201
    clip_id = result.json()["id"]
    assert client.get(f"{base}/{clip_id}/media").status_code == 409
    assert (
        client.put(f"{base}/{clip_id}", json={**payload, "title": "Edited"}).json()["revision"] == 2
    )
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "stranger@example.com",
            "name": "Stranger",
            "password": "long-enough-password",
        },
    )
    assert client.get(base).status_code == 404
    assert client.get(f"{base}/{clip_id}/media").status_code == 404
    assert client.put(f"{base}/{clip_id}", json=payload).status_code == 404
