"""Upload and analyze real speech without paid providers. Run after creating .local/speech.mp4."""

import json
import time
import uuid
from pathlib import Path

import httpx

path = Path(".local/speech.mp4")
with httpx.Client(
    base_url="http://localhost:8000/api/v1", headers={"Origin": "http://localhost:3000"}, timeout=60
) as client:
    email = f"analysis-{uuid.uuid4().hex}@example.com"
    password = "integration-test-password"
    client.post(
        "/auth/register", json={"email": email, "name": "Analysis test", "password": password}
    ).raise_for_status()
    response = client.post(
        "/projects", json={"name": "Real speech analysis", "content_type": "Podcast"}
    )
    response.raise_for_status()
    project_id = response.json()["id"]
    base = f"/projects/{project_id}"
    response = client.post(
        f"{base}/upload/initiate",
        json={"filename": path.name, "size_bytes": path.stat().st_size, "mime_type": "video/mp4"},
    )
    response.raise_for_status()
    upload = response.json()
    with path.open("rb") as stream:
        for number in range(1, upload["part_count"] + 1):
            response = client.post(f"{base}/upload/{upload['id']}/parts/{number}")
            response.raise_for_status()
            httpx.put(
                response.json()["url"], content=stream.read(upload["part_size"]), timeout=60
            ).raise_for_status()
    client.post(f"{base}/upload/{upload['id']}/complete").raise_for_status()

    def wait_job() -> None:
        last = None
        for _ in range(600):
            job = client.get(f"{base}/jobs").json()[0]
            state = (job["stage"], job["status"])
            if state != last:
                print(state, flush=True)
                last = state
            if job["status"] == "SUCCEEDED":
                return
            assert job["status"] not in {"FAILED", "CANCELED"}, job
            time.sleep(2)
        raise TimeoutError("Analysis exceeded 20 minutes")

    wait_job()
    client.post(f"{base}/analyze").raise_for_status()
    wait_job()
    transcript = client.get(f"{base}/transcript").json()
    assert len(transcript["text"]) > 100 and transcript["segments"][0]["words"]
    assert transcript["scenes"]
    Path(".local/analysis-test.json").write_text(
        json.dumps({"project_id": project_id, "email": email, "password": password})
    )
    print("Real analysis passed", project_id, len(transcript["segments"]), "segments", flush=True)
