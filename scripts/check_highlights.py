"""Use the real analysis fixture account to verify persisted Celery highlight results."""

import json
import time
from pathlib import Path

import httpx

fixture = json.loads(Path(".local/analysis-test.json").read_text())
with httpx.Client(
    base_url="http://localhost:8000/api/v1", headers={"Origin": "http://localhost:3000"}, timeout=60
) as client:
    client.post(
        "/auth/login", json={"email": fixture["email"], "password": fixture["password"]}
    ).raise_for_status()
    base = f"/projects/{fixture['project_id']}"
    response = client.post(f"{base}/highlights")
    response.raise_for_status()
    job_id = response.json()["job_id"]
    for _ in range(120):
        job = next(j for j in client.get(f"{base}/jobs").json() if j["id"] == job_id)
        if job["status"] == "SUCCEEDED":
            break
        assert job["status"] not in {"FAILED", "CANCELED"}, job
        time.sleep(1)
    else:
        raise TimeoutError("Highlight generation exceeded 2 minutes")
    response = client.get(f"{base}/highlights")
    response.raise_for_status()
    result = response.json()
    assert result["candidates_evaluated"] > 0 and result["items"], result
    for candidate in result["items"]:
        assert 20000 <= candidate["end_ms"] - candidate["start_ms"] <= 35000
        assert abs(sum(candidate["breakdown"].values()) - candidate["score"]) < 0.03
        assert candidate["reason"] and candidate["text"]
    print(
        f"Real highlights passed: {len(result['items'])} selected from {result['candidates_evaluated']} windows."
    )
