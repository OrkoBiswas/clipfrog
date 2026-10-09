import uuid
from unittest.mock import Mock

import pytest
from clipforge_api.db import get_db
from clipforge_api.main import app
from clipforge_api.models import Clip, ClipCandidate, MediaAsset, Project
from clipforge_worker.vision.face_detector import FaceFrame, collage_sample_times


@pytest.fixture
def project_account(client, monkeypatch):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "project-layout@example.com",
            "name": "Project layout",
            "password": "long-enough-password",
        },
    ).raise_for_status()
    monkeypatch.setattr("clipforge_api.routes.jobs.celery.send_task", Mock())
    storage = Mock()
    storage.generate_presigned_url.return_value = "https://example.com/source.mp4"
    monkeypatch.setattr("clipforge_api.routes.clips.s3", Mock(return_value=storage))
    monkeypatch.setattr(
        "clipforge_api.services.collage.CollageFaceDetector.analyze",
        lambda self, source, start, end, progress: [
            FaceFrame(timestamp=t, faces=[], detector="yunet-collage-v2")
            for t in collage_sample_times(start, end)
        ],
    )


def create_source_project(client, config):
    response = client.post(
        "/api/v1/projects", json={"name": "Project settings", "processing_config": config}
    )
    assert response.status_code == 201, response.text
    project = response.json()
    for db in app.dependency_overrides[get_db]():
        model = db.get(Project, uuid.UUID(project["id"]))
        source = MediaAsset(
            id=uuid.uuid4(),
            user_id=model.user_id,
            project_id=model.id,
            type="SOURCE",
            storage_key="source.mp4",
            original_filename="source.mp4",
            mime_type="video/mp4",
            size_bytes=1000,
            width=1920,
            height=1080,
            duration_ms=30000,
        )
        db.add(source)
        model.source_asset_id, model.status = source.id, "READY_FOR_CLIPS"
        candidate = ClipCandidate(
            id=uuid.uuid4(),
            project_id=model.id,
            start_ms=1000,
            end_ms=16000,
            title="Two people",
            transcript_text="A complete interview highlight.",
            score_total=85,
            score_breakdown={"hook": 85},
            reason="Complete thought",
            selected=True,
            rank=1,
        )
        db.add(candidate)
        db.commit()
        candidate_id = str(candidate.id)
    return project, candidate_id


def test_project_persists_layout_and_inherits_legacy_render_defaults(client, project_account):
    project, _ = create_source_project(
        client,
        {
            "quality": "High",
            "crop_mode": "SCENE_AWARE_LOCK",
            "render_config": {"layout": "stacked"},
        },
    )
    config = project["processing_config"]["render_config"]
    assert config["quality"] == "High" and config["crop_mode"] == "SCENE_AWARE_LOCK"
    assert [panel["subject"] for panel in config["panels"]] == ["person-1", "person-2"]
    base = f"/api/v1/projects/{project['id']}"
    assert client.get(base).json()["processing_config"]["render_config"] == config
    response = client.put(
        base,
        json={
            "name": "Project settings",
            "processing_config": {
                "quality": "High",
                "render_config": {
                    "layout": "grid",
                    "quality": "Draft",
                    "panels": [
                        {"subject": "person-1"},
                        {"subject": "person-2"},
                        {"subject": "person-3", "anchor_x": 0.8, "anchor_y": 0.4, "zoom": 2},
                    ],
                },
            },
        },
    )
    assert response.status_code == 200, response.text
    config = client.get(base).json()["processing_config"]["render_config"]
    assert config["quality"] == "Draft" and config["layout"] == "grid"
    assert len(config["panels"]) == 3 and config["panels"][2]["zoom"] == 2
    response = client.put(
        base,
        json={
            "name": "Invalid layout",
            "processing_config": {"render_config": {"layout": "grid", "panels": [{}, {}]}},
        },
    )
    assert response.status_code == 422
    assert client.get(base).json()["processing_config"]["render_config"] == config


@pytest.mark.parametrize("legacy", [False, True])
def test_generated_clips_inherit_project_layout_and_render_settings(
    client, project_account, legacy
):
    processing = {"quality": "High", "crop_mode": "SCENE_AWARE_LOCK"}
    if not legacy:
        processing["render_config"] = {
            "layout": "side-by-side",
            "normalize_audio": False,
            "panels": [{"subject": "person-1", "zoom": 1.5}, {"subject": "person-2"}],
        }
    project, candidate_id = create_source_project(client, processing)
    base = f"/api/v1/projects/{project['id']}"
    response = client.post(
        f"{base}/clips/generate", json={"candidate_ids": [candidate_id], "ratios": ["9:16", "1:1"]}
    )
    assert response.status_code == 202, response.text
    clips = client.get(f"{base}/clips").json()
    assert len(clips) == 2
    for clip in clips:
        config = clip["render_config"]
        assert config["quality"] == "High" and config["crop_mode"] == "SCENE_AWARE_LOCK"
        assert config["layout"] == ("single" if legacy else "auto")
        if not legacy:
            assert config["normalize_audio"] is False and config["panels"] == []


def test_manual_clips_inherit_project_layout_with_explicit_overrides(client, project_account):
    project, _ = create_source_project(
        client,
        {
            "quality": "High",
            "crop_mode": "SCENE_AWARE_LOCK",
            "render_config": {"layout": "grid", "normalize_audio": False},
        },
    )
    base = f"/api/v1/projects/{project['id']}"
    body = {"title": "Manual clip", "start_ms": 0, "end_ms": 9000}
    inherited = client.post(f"{base}/clips", json=body)
    assert inherited.status_code == 201, inherited.text
    config = inherited.json()["render_config"]
    assert config["layout"] == "auto" and config["panels"] == []
    assert config["quality"] == "High" and config["normalize_audio"] is False
    # A preview body represents an existing clip exactly, including older clips
    # without layout fields; changed project defaults must not alter it.
    assert client.post(f"{base}/editor-preview", json=body).json()["plan"]["layout"] == "single"
    preview_body = {**body, "render_config": config}
    assert (
        client.post(f"{base}/editor-preview", json=preview_body).json()["plan"]["layout"]
        == "single"
    )
    body["render_config"] = {"quality": "Draft", "layout": "single", "zoom": 1.7}
    overridden = client.post(f"{base}/clips", json=body)
    assert overridden.status_code == 201, overridden.text
    config = overridden.json()["render_config"]
    assert config["layout"] == "single" and config["zoom"] == 1.7 and config["quality"] == "Draft"
    assert config["normalize_audio"] is False and config["crop_mode"] == "SCENE_AWARE_LOCK"
    preview = client.post(f"{base}/editor-preview", json=body).json()["plan"]
    assert preview["layout"] == "single" and preview["panels"] == []
    body["render_config"] = {"layout": "stacked"}
    split = client.post(f"{base}/clips", json=body)
    assert split.status_code == 201, split.text
    assert split.json()["render_config"]["layout"] == "stacked"
    assert len(split.json()["render_config"]["panels"]) == 2
    render_preview = client.post(
        f"{base}/render-preview",
        json={
            "title": "Old clip preview",
            "start_ms": 0,
            "end_ms": 9000,
        },
    )
    assert render_preview.status_code == 202, render_preview.text
    for db in app.dependency_overrides[get_db]():
        preview_clip = db.get(Clip, uuid.UUID(render_preview.json()["clip_ids"][0]))
        assert preview_clip.is_preview and preview_clip.render_config["layout"] == "single"


def test_manual_legacy_project_keeps_original_quality_and_crop_mode(client, project_account):
    project, _ = create_source_project(client, {"quality": "High", "crop_mode": "SCENE_AWARE_LOCK"})
    clip = client.post(
        f"/api/v1/projects/{project['id']}/clips",
        json={
            "title": "Legacy project",
            "start_ms": 0,
            "end_ms": 9000,
        },
    ).json()
    assert clip["render_config"]["quality"] == "High"
    assert clip["render_config"]["crop_mode"] == "SCENE_AWARE_LOCK"
    assert clip["render_config"]["layout"] == "single"
