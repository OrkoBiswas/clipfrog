"""Render a real analyzed source, download and ffprobe it, then edit and re-render."""

import json
import time
from pathlib import Path

import httpx
from clipforge_worker.media.probe import probe

fixture = json.loads(Path(".local/analysis-test.json").read_text())
with httpx.Client(
    base_url="http://localhost:8000/api/v1", headers={"Origin": "http://localhost:3000"}, timeout=60
) as client:
    client.post(
        "/auth/login", json={"email": fixture["email"], "password": fixture["password"]}
    ).raise_for_status()
    base = f"/projects/{fixture['project_id']}"
    highlights = client.get(f"{base}/highlights").json()["items"]
    assert highlights
    response = client.post(
        f"{base}/clips/generate", json={"candidate_ids": [highlights[0]["id"]], "ratios": ["9:16"]}
    )
    response.raise_for_status()
    clip_id = response.json()["clip_ids"][0]

    def wait_job(identifier):
        last = None
        for _ in range(900):
            job = next(j for j in client.get(f"{base}/jobs").json() if j["id"] == identifier)
            if job["stage"] != last:
                print(job["stage"], flush=True)
                last = job["stage"]
            if job["status"] == "SUCCEEDED":
                return
            assert job["status"] not in {"FAILED", "CANCELED"}, job
            time.sleep(1)
        raise TimeoutError("Render exceeded 15 minutes")

    wait_job(response.json()["job_id"])

    def download(name):
        result = client.get(f"{base}/clips/{clip_id}/media", params={"download": True})
        result.raise_for_status()
        media = httpx.get(result.json()["url"], timeout=60)
        media.raise_for_status()
        output = Path(f".local/{name}.mp4")
        output.write_bytes(media.content)
        metadata = probe(output)
        assert metadata.width == 1080 and metadata.height == 1920 and metadata.has_audio
        return metadata

    original = download("render-test")
    clips = client.get(f"{base}/clips").json()
    clip = next(c for c in clips if c["id"] == clip_id)
    assert len(clip["crop_plan"]["keyframes"]) == 1
    changes = {
        k: clip[k]
        for k in [
            "title",
            "start_ms",
            "end_ms",
            "aspect_ratio",
            "caption_config",
            "overlay_config",
            "render_config",
        ]
    }
    changes["end_ms"] -= 2000
    changes["overlay_config"] = {"title": "A practical lesson", "watermark": "Integration test"}
    changes["caption_config"]["style"] = "Karaoke"
    client.put(f"{base}/clips/{clip_id}", json=changes).raise_for_status()
    response = client.post(f"{base}/clips/{clip_id}/render")
    response.raise_for_status()
    wait_job(response.json()["job_id"])
    edited = download("render-edited-test")
    assert abs(original.duration_ms - edited.duration_ms - 2000) < 150
    fixture["clip_id"] = clip_id
    Path(".local/analysis-test.json").write_text(json.dumps(fixture))
    print("Real portrait MP4 preview/download and edited re-render passed.", flush=True)
