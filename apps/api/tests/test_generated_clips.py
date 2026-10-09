import uuid
from unittest.mock import Mock

import pytest
from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig, RenderConfig
from clipforge_api.db import get_db
from clipforge_api.main import app
from clipforge_api.models import (
    ClipCandidate,
    MediaAsset,
    ProcessingJob,
    Project,
    Transcript,
    UsageLedger,
)
from sqlalchemy import select


@pytest.fixture
def highlighted_project(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "highlights-render@example.com",
            "name": "Highlights renderer",
            "password": "long-enough-password",
        },
    ).raise_for_status()
    project_id = client.post("/api/v1/projects", json={"name": "Render highlights"}).json()["id"]
    for db in app.dependency_overrides[get_db]():
        project = db.get(Project, uuid.UUID(project_id))
        source = MediaAsset(
            id=uuid.uuid4(),
            user_id=project.user_id,
            project_id=project.id,
            type="SOURCE",
            storage_key="highlight-test.mp4",
            original_filename="highlight-test.mp4",
            mime_type="video/mp4",
            size_bytes=1000,
            width=1920,
            height=1080,
            duration_ms=60000,
        )
        db.add(source)
        project.source_asset_id = source.id
        project.status = "READY_FOR_CLIPS"
        for job_type in ["analyze", "highlights"]:
            db.add(
                ProcessingJob(
                    user_id=project.user_id,
                    project_id=project.id,
                    job_type=job_type,
                    status="SUCCEEDED",
                )
            )
        db.add(
            ClipCandidate(
                project_id=project.id,
                start_ms=1000,
                end_ms=16000,
                title="Selected highlight",
                transcript_text="The words in the selected highlight.",
                score_total=85,
                score_breakdown={"hook": 85},
                reason="A complete thought",
                selected=True,
                rank=1,
            )
        )
        db.commit()
    return project_id


@pytest.mark.parametrize("custom_captions", [False, True])
def test_render_selected_highlights_queues_outputs(
    client, monkeypatch, highlighted_project, custom_captions
):
    project_id = highlighted_project
    if custom_captions:
        for db in app.dependency_overrides[get_db]():
            project = db.get(Project, uuid.UUID(project_id))
            project.processing_config = {
                "captions": False,
                "caption_style": "Bold",
                "caption_config": {"font": "Urbanist", "size": 72, "animation": "word-pill"},
                "quality": "High",
                "crop_mode": "SCENE_AWARE_LOCK",
            }
            project.brand_config = {
                "captions": {"size": 60, "primary_color": "#123456"},
                "overlay": {"watermark": "My channel"},
            }
            db.commit()
    send_task = Mock()
    monkeypatch.setattr("clipforge_api.routes.jobs.celery.send_task", send_task)
    base = f"/api/v1/projects/{project_id}"
    highlight = client.get(f"{base}/highlights").json()["items"][0]
    response = client.post(
        f"{base}/clips/generate",
        json={
            "candidate_ids": [highlight["id"], highlight["id"]],
            "ratios": ["9:16", "1:1", "9:16"],
        },
    )
    assert response.status_code == 202, response.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    result = response.json()
    send_task.assert_called_once_with(
        "clipforge.render", args=[result["job_id"]], task_id=result["job_id"], queue="render"
    )
    clips = client.get(f"{base}/clips").json()
    assert {clip["id"] for clip in clips} == set(result["clip_ids"])
    assert len(clips) == 2
    assert {clip["aspect_ratio"] for clip in clips} == {"9:16", "1:1"}
    for clip in clips:
        assert (clip["start_ms"], clip["end_ms"], clip["title"]) == (
            1000,
            16000,
            "Selected highlight",
        )
        captions = CaptionConfig.model_validate(clip["caption_config"])
        render = RenderConfig.model_validate(clip["render_config"])
        overlay = OverlayConfig.model_validate(clip["overlay_config"])
        if custom_captions:
            assert captions.enabled is False
            assert (captions.font, captions.size, captions.animation) == (
                "Urbanist",
                72,
                "word-pill",
            )
            assert captions.primary_color == "#123456"
            assert (render.quality, render.crop_mode) == ("High", "SCENE_AWARE_LOCK")
            assert overlay.watermark == "My channel"
        else:
            assert captions == CaptionConfig()
            assert render == RenderConfig()
    assert client.get(base).json()["status"] == "RENDERING"
    for db in app.dependency_overrides[get_db]():
        job = db.get(ProcessingJob, uuid.UUID(result["job_id"]))
        assert job.status == "QUEUED"
        assert set(job.parameters["clip_ids"]) == set(result["clip_ids"])
        reservation = db.scalar(
            select(UsageLedger).where(UsageLedger.project_id == job.project_id)
        )
        assert reservation.metric == "render_minutes"
        assert reservation.quantity == pytest.approx(0.5)


def test_render_queue_failure_is_readable_and_releases_usage(
    client, monkeypatch, highlighted_project
):
    monkeypatch.setattr(
        "clipforge_api.routes.jobs.celery.send_task", Mock(side_effect=ConnectionError("offline"))
    )
    base = f"/api/v1/projects/{highlighted_project}"
    highlight = client.get(f"{base}/highlights").json()["items"][0]
    response = client.post(f"{base}/clips/generate", json={"candidate_ids": [highlight["id"]]})
    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "queue is unavailable" in response.json()["detail"]
    job = next(job for job in client.get(f"{base}/jobs").json() if job["job_type"] == "render")
    assert job["status"] == "FAILED"
    assert job["error_code"] == "QUEUE_UNAVAILABLE"
    for db in app.dependency_overrides[get_db]():
        assert (
            db.scalar(
                select(UsageLedger).where(
                    UsageLedger.project_id == uuid.UUID(highlighted_project)
                )
            )
            is None
        )


@pytest.mark.parametrize("has_answer", [True, False])
def test_old_highlight_question_must_finish_answer_before_rendering(client, monkeypatch, highlighted_project, has_answer):
    send_task = Mock()
    monkeypatch.setattr("clipforge_api.routes.jobs.celery.send_task", send_task)
    for db in app.dependency_overrides[get_db]():
        db.add(Transcript(
            project_id=uuid.UUID(highlighted_project), language="en", full_text="Question and answer",
            segments=[
                {"start": 1, "end": 16, "text": "Here is the situation. What should you do?"},
                {"start": 16.5, "end": 20, "text": "Start with one small test and use the result." if has_answer else "What would you test?"},
            ],
        ))
        db.commit()
    base = f"/api/v1/projects/{highlighted_project}"
    highlight = client.get(f"{base}/highlights").json()["items"][0]
    response = client.post(f"{base}/clips/generate", json={"candidate_ids": [highlight["id"]]})
    if has_answer:
        assert response.status_code == 202, response.text
        clip = client.get(f"{base}/clips").json()[0]
        assert clip["end_ms"] == 20350
        send_task.assert_called_once()
    else:
        assert response.status_code == 422, response.text
        assert "complete ending" in response.json()["detail"]
        assert client.get(f"{base}/clips").json() == []
        send_task.assert_not_called()
