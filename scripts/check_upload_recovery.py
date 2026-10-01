"""Exercise interrupted upload completion against real PostgreSQL, MinIO and Celery."""

import time
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
from botocore.exceptions import ClientError
from clipforge_api.config import settings
from clipforge_api.db import SessionLocal
from clipforge_api.models import MediaAsset, UploadSession, now
from clipforge_api.services.multipart import finalize
from clipforge_api.storage import s3
from clipforge_worker.celery_app import celery


def main() -> None:
    path = Path(".local/fixture.mp4")
    storage = s3()
    bucket = settings().s3_bucket
    with httpx.Client(
        base_url="http://localhost:8000/api/v1",
        headers={"Origin": "http://localhost:3000"},
        timeout=60,
    ) as client:
        client.post(
            "/auth/register",
            json={
                "email": f"recovery-{uuid.uuid4().hex}@example.com",
                "name": "Upload recovery",
                "password": "integration-test-password",
            },
        ).raise_for_status()
        for action in ["complete", "cancel", "expire"]:
            response = client.post("/projects", json={"name": f"Upload recovery: {action}"})
            response.raise_for_status()
            base = f"/projects/{response.json()['id']}"
            response = client.post(
                f"{base}/upload/initiate",
                json={
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                    "mime_type": "video/mp4",
                },
            )
            response.raise_for_status()
            upload = response.json()
            endpoint = f"{base}/upload/{upload['id']}"
            with path.open("rb") as stream:
                for number in range(1, upload["part_count"] + 1):
                    signed = client.post(f"{endpoint}/parts/{number}")
                    signed.raise_for_status()
                    httpx.put(
                        signed.json()["url"], content=stream.read(upload["part_size"]), timeout=60
                    ).raise_for_status()
            # Commit S3 completion only, simulating loss before the API's DB commit.
            with SessionLocal() as db:
                session = db.get(UploadSession, uuid.UUID(upload["id"]))
                assert session
                asset = db.get(MediaAsset, session.asset_id)
                assert asset
                key = asset.storage_key
                finalize(
                    storage, bucket, key, session.upload_id, asset.size_bytes, session.part_size
                )
            resumed = client.get(endpoint)
            resumed.raise_for_status()
            assert sum(part["size"] for part in resumed.json()["parts"]) == path.stat().st_size
            if action == "complete":
                response = client.post(f"{endpoint}/complete")
                response.raise_for_status()
                identifier = response.json()["job_id"]
                duplicate = client.post(f"{endpoint}/complete")
                duplicate.raise_for_status()
                assert duplicate.json()["job_id"] == identifier
                for _ in range(60):
                    jobs = client.get(f"{base}/jobs").json()
                    assert len(jobs) == 1
                    job = jobs[0]
                    if job["status"] == "SUCCEEDED":
                        break
                    assert job["status"] not in {"FAILED", "CANCELED"}, job
                    time.sleep(1)
                else:
                    raise TimeoutError("Recovered upload validation did not finish")
            else:
                if action == "cancel":
                    client.delete(endpoint).raise_for_status()
                else:
                    with SessionLocal() as db:
                        session = db.get(UploadSession, uuid.UUID(upload["id"]))
                        assert session
                        session.expires_at = now() - timedelta(minutes=1)
                        db.commit()
                    celery.send_task("clipforge.maintenance", queue="maintenance").get(timeout=60)
                    assert client.get(endpoint).json()["status"] == "EXPIRED"
                try:
                    storage.head_object(Bucket=bucket, Key=key)
                except ClientError as exc:
                    assert exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}
                else:
                    raise AssertionError("Canceled upload left an unaccounted storage object")
                assert client.get(base).json()["status"] == "DRAFT"
            client.delete(base).raise_for_status()
            print(f"Interrupted upload {action} passed.", flush=True)


if __name__ == "__main__":
    main()
