"""Real brand CRUD, ownership, project snapshots and rendered-logo acceptance check."""

import io
import subprocess
import time
import uuid
from pathlib import Path

import httpx
from PIL import Image

API = "http://localhost:8000/api/v1"
HEADERS = {"Origin": "http://localhost:3000"}


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else None


def register(client):
    request(
        client,
        "POST",
        "/auth/register",
        json={
            "email": f"brands-{uuid.uuid4().hex}@example.com",
            "name": "Brand acceptance",
            "password": "integration-test-password",
        },
    )


def wait_job(client, base, identifier):
    for _ in range(120):
        jobs = request(client, "GET", f"{base}/jobs")
        job = next(item for item in jobs if item["id"] == identifier)
        if job["status"] == "SUCCEEDED":
            return
        assert job["status"] not in {"FAILED", "CANCELED"}, job
        time.sleep(1)
    raise TimeoutError("Brand acceptance job timed out")


def main():
    fixture = Path(".local/fixture.mp4")
    logo = Image.new("RGBA", (120, 80), (240, 20, 30, 255))
    buffer = io.BytesIO()
    logo.save(buffer, format="PNG")
    Path(".local/brand-logo.png").write_bytes(buffer.getvalue())
    with (
        httpx.Client(base_url=API, headers=HEADERS, timeout=60) as client,
        httpx.Client(base_url=API, headers=HEADERS, timeout=60) as stranger,
    ):
        register(client)
        register(stranger)
        body = {
            "name": "Acceptance brand",
            "captions": {
                "enabled": False,
                "primary_color": "#12ABEF",
                "highlight_color": "#ABCDEF",
                "font": "Noto Sans",
            },
            "overlay": {"logo_position": "bottom-right", "title_style": "Boxed"},
            "ratios": ["1:1"],
        }
        kit = request(client, "POST", "/brand-kits", json=body)
        kit_path = f"/brand-kits/{kit['id']}"
        assert client.put(f"{kit_path}/logo", content=b"not an image").status_code == 422
        request(
            client,
            "PUT",
            f"{kit_path}/logo",
            content=buffer.getvalue(),
            headers={"Content-Type": "image/png"},
        )
        preview = request(client, "GET", f"{kit_path}/logo")
        assert httpx.get(preview["url"]).status_code == 200
        for method, suffix in [("GET", "/logo"), ("DELETE", "/logo"), ("DELETE", "")]:
            assert stranger.request(method, kit_path + suffix).status_code == 404
        assert stranger.put(kit_path, json=body).status_code == 404
        usage = request(client, "GET", "/usage")
        assert usage["usage"]["storage_bytes"] > 0
        project = request(
            client,
            "POST",
            "/projects",
            json={
                "name": "Branded render acceptance",
                "processing_config": {"brand_kit_id": kit["id"]},
            },
        )
        base = f"/projects/{project['id']}"
        assert project["brand_config"]["captions"]["primary_color"] == "#12ABEF"
        assert project["processing_config"]["ratios"] == ["1:1"]
        original_logo_id = project["brand_config"]["overlay"]["logo_asset_id"]
        foreign = request(stranger, "POST", "/projects", json={"name": "Other owner"})
        assert (
            stranger.put(f"/projects/{foreign['id']}/brand", json={"kit_id": kit["id"]}).status_code
            == 404
        )
        upload = request(
            client,
            "POST",
            f"{base}/upload/initiate",
            json={
                "filename": fixture.name,
                "size_bytes": fixture.stat().st_size,
                "mime_type": "video/mp4",
            },
        )
        with fixture.open("rb") as stream:
            for number in range(1, upload["part_count"] + 1):
                signed = request(client, "POST", f"{base}/upload/{upload['id']}/parts/{number}")
                httpx.put(
                    signed["url"], content=stream.read(upload["part_size"]), timeout=60
                ).raise_for_status()
        probe = request(client, "POST", f"{base}/upload/{upload['id']}/complete")
        wait_job(client, base, probe["job_id"])
        clip = request(
            client,
            "POST",
            f"{base}/clips",
            json={
                "title": "Branded clip",
                "start_ms": 0,
                "end_ms": 2000,
                "aspect_ratio": "1:1",
                "render_config": {"quality": "Draft"},
            },
        )
        assert clip["overlay_config"]["logo_asset_id"] == original_logo_id
        clip_path = f"{base}/clips/{clip['id']}"
        # Kit changes and deletion must not invalidate project-owned logo copies.
        request(client, "PUT", kit_path, json={**body, "name": "Changed brand"})
        request(client, "DELETE", kit_path)
        job = request(client, "POST", f"{clip_path}/render")
        wait_job(client, base, job["job_id"])
        media = request(client, "GET", f"{clip_path}/media")
        response = httpx.get(media["url"], timeout=60)
        response.raise_for_status()
        output = Path(".local/brand-render.mp4")
        output.write_bytes(response.content)
        frame = Path(".local/brand-render.png")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(output), "-frames:v", "1", str(frame)],
            check=True,
        )
        with Image.open(frame) as image:
            # Logo center at the configured bottom-right corner in a 540-square output.
            pixel = image.getpixel((475, 490))
            assert pixel[0] > 180 and pixel[1] < 70 and pixel[2] < 80, pixel
        updated = request(client, "GET", f"{base}/clips")[0]
        edit = {
            name: updated[name]
            for name in [
                "title",
                "start_ms",
                "end_ms",
                "aspect_ratio",
                "caption_config",
                "overlay_config",
                "render_config",
            ]
        }
        edit["overlay_config"]["logo_asset_id"] = str(uuid.uuid4())
        assert client.put(clip_path, json=edit).status_code == 404
        edit["overlay_config"]["logo_asset_id"] = original_logo_id
        edit["overlay_config"]["logo_enabled"] = False
        request(client, "PUT", clip_path, json=edit)
        job = request(client, "POST", f"{clip_path}/render")
        wait_job(client, base, job["job_id"])
        replacement = request(client, "POST", "/brand-kits", json=body)
        request(
            client,
            "PUT",
            f"{base}/brand",
            json={"kit_id": replacement["id"], "include_existing": True},
        )
        revised = request(client, "GET", f"{base}/clips")[0]
        assert revised["status"] == "DRAFT" and revised["revision"] == 3
        assert revised["overlay_config"]["logo_asset_id"] is None
        request(client, "DELETE", f"/brand-kits/{replacement['id']}")
        request(client, "DELETE", base)
        request(stranger, "DELETE", f"/projects/{foreign['id']}")
        print(
            "Real brand CRUD, private logo, ownership, project snapshot, render, toggle and reapply checks passed.",
            flush=True,
        )


if __name__ == "__main__":
    main()
