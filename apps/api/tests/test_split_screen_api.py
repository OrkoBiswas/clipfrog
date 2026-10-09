import uuid
from unittest.mock import Mock

import pytest
from clipforge_api.clip_schemas import RenderConfig
from clipforge_api.db import get_db
from clipforge_api.main import app
from clipforge_api.models import Analysis, MediaAsset, Project, Scene, Transcript
from clipforge_worker.vision.face_detector import FaceFrame
from pydantic import ValidationError
from sqlalchemy import select


@pytest.mark.parametrize(
    "config",
    [
        {"layout": "stacked", "panels": [{"subject": "left"}]},
        {"layout": "side-by-side", "panels": [{}, {}, {}]},
        {"layout": "grid", "panels": [{}, {}]},
        {"layout": "grid", "panels": [{}, {}, {}, {}, {}]},
        {"layout": "stacked", "panels": [{"anchor_x": 0.5}, {}]},
        {"layout": "stacked", "panels": [{"anchor_x": -0.1, "anchor_y": 0.5}, {}]},
        {"layout": "stacked", "panels": [{"zoom": 3.5}, {}]},
        {"layout": "stacked", "panels": [{"subject": "person-5"}, {}]},
    ],
)
def test_invalid_panel_configuration_is_rejected(config):
    with pytest.raises(ValidationError):
        RenderConfig.model_validate(config)


def test_legacy_single_and_split_defaults():
    assert RenderConfig.model_validate({"zoom": 1.5}).layout == "single"
    assert RenderConfig().panels == []
    assert [panel.subject for panel in RenderConfig(layout="stacked").panels] == [
        "person-1",
        "person-2",
    ]
    assert len(RenderConfig(layout="grid").panels) == 4
    assert len(RenderConfig.model_validate({"layout": "grid", "panels": [{}, {}, {}]}).panels) == 3
    assert RenderConfig.model_validate({"layout": "auto", "panels": [{"zoom": 2}]}).panels == []


@pytest.fixture
def source_project(client, monkeypatch):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "split-screen@example.com",
            "name": "Split screen",
            "password": "long-enough-password",
        },
    ).raise_for_status()
    project_id = client.post("/api/v1/projects", json={"name": "Same-video speakers"}).json()["id"]
    with next(app.dependency_overrides[get_db]()) as db:
        project = db.get(Project, uuid.UUID(project_id))
        source = MediaAsset(
            id=uuid.uuid4(),
            user_id=project.user_id,
            project_id=project.id,
            type="SOURCE",
            storage_key="same-video.mp4",
            original_filename="same-video.mp4",
            mime_type="video/mp4",
            size_bytes=1000,
            width=1920,
            height=1080,
            duration_ms=10000,
        )
        db.add(source)
        project.source_asset_id = source.id
        project.status = "READY_FOR_CLIPS"
        db.add(
            Analysis(
                project_id=project.id,
                face_frames=[
                    {
                        "detector": "yunet-collage-v2",
                        "timestamp": index / 3,
                        "faces": [
                            {
                                "confidence": 0.95,
                                "x": x - 0.05,
                                "y": 0.2,
                                "w": 0.1,
                                "h": 0.25,
                                "center_x": x,
                                "center_y": 0.325,
                            }
                            for x in [0.25, 0.75]
                        ],
                    }
                    for index in range(30)
                ],
            )
        )
        db.commit()
    storage = Mock()
    storage.generate_presigned_url.return_value = "https://example.com/same-video.mp4"
    monkeypatch.setattr("clipforge_api.routes.clips.s3", Mock(return_value=storage))
    return project_id


def test_split_preview_persistence_and_switching_to_single(client, source_project):
    base = f"/api/v1/projects/{source_project}"
    body = {
        "title": "Two people",
        "start_ms": 0,
        "end_ms": 9000,
        "aspect_ratio": "9:16",
        "render_config": {
            "layout": "stacked",
            "panels": [{"subject": "person-1"}, {"subject": "person-2", "zoom": 1.2}],
        },
    }
    response = client.post(f"{base}/editor-preview", json=body)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["source_url"] == "https://example.com/same-video.mp4"
    assert preview["plan"]["layout"] == "stacked"
    panels = preview["plan"]["panels"]
    assert len(panels) == 2 and panels[0]["keyframes"][0]["x"] < panels[1]["keyframes"][0]["x"]
    assert panels[0]["crop_width"] > panels[1]["crop_width"]
    assert preview["debug_allowed"] is False
    assert preview["plan"]["subjects"] == [] and "samples" not in preview["plan"]["quality"]
    assert all(panel["subjects"] == [] and "samples" not in panel["quality"] for panel in panels)
    response = client.post(f"{base}/clips", json=body)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["render_config"]["layout"] == "stacked"
    assert saved["render_config"]["panels"][1]["zoom"] == 1.2
    body["render_config"]["layout"] = "single"
    response = client.put(f"{base}/clips/{saved['id']}", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["render_config"]["panels"] == saved["render_config"]["panels"]
    preview = client.post(f"{base}/editor-preview", json=body).json()
    assert preview["plan"]["layout"] == "single" and preview["plan"]["panels"] == []


def test_preview_rejects_invalid_panel_count(client, source_project):
    response = client.post(
        f"/api/v1/projects/{source_project}/editor-preview",
        json={
            "title": "Invalid split",
            "start_ms": 0,
            "end_ms": 9000,
            "render_config": {"layout": "stacked", "panels": [{"subject": "person-1"}]},
        },
    )
    assert response.status_code == 422


def test_automatic_collage_preview_switches_to_single_without_manual_controls(
    client, source_project
):
    for db in app.dependency_overrides[get_db]():
        analysis = db.scalar(
            select(Analysis).where(Analysis.project_id == uuid.UUID(source_project))
        )
        analysis.face_frames = [
            {**frame, "faces": frame["faces"] if frame["timestamp"] < 4 else frame["faces"][:1]}
            for frame in analysis.face_frames
        ]
        db.add(Scene(project_id=uuid.UUID(source_project), start_ms=0, end_ms=4000))
        db.add(Scene(project_id=uuid.UUID(source_project), start_ms=4000, end_ms=10000))
        db.commit()
    response = client.post(
        f"/api/v1/projects/{source_project}/editor-preview",
        json={
            "title": "Auto collage",
            "start_ms": 0,
            "end_ms": 9000,
            "render_config": {"layout": "auto"},
        },
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert [scene["layout"] for scene in preview["plan"]["scenes"]] == ["stacked", "single"]
    assert preview["debug_allowed"] is False
    for scene in preview["plan"]["scenes"]:
        assert scene["subjects"] == [] and "samples" not in scene["quality"]
        assert all(
            panel["subjects"] == [] and "samples" not in panel["quality"]
            for panel in scene["panels"]
        )


def test_batch_template_updates_layout_and_captions_preserving_clip_settings(
    client, source_project
):
    base = f"/api/v1/projects/{source_project}"
    cues = [{"start_ms": 100, "end_ms": 4000, "text": "Keep my edited transcript"}]
    body = {
        "title": "Customized clip",
        "start_ms": 0,
        "end_ms": 9000,
        "caption_config": {"cues": cues},
        "render_config": {
            "quality": "High",
            "normalize_audio": False,
            "crop_mode": "SCENE_AWARE_LOCK",
            "anchor_x": 0.4,
            "anchor_y": 0.6,
            "zoom": 1.3,
            "lock_camera": False,
            "eye_line": 0.4,
            "minimum_crop_hold_seconds": 5,
        },
    }
    saved = client.post(f"{base}/clips", json=body).json()
    panels = [
        {"subject": "person-1"},
        {"subject": "person-2", "anchor_x": 0.7, "anchor_y": 0.5, "zoom": 1.8},
    ]
    response = client.post(
        f"{base}/clip-actions",
        json={
            "action": "update",
            "clip_ids": [saved["id"]],
            "caption_config": {"font": "Montserrat", "weight": 500, "width": 0.75},
            "render_config": {"layout": "stacked", "panels": panels},
        },
    )
    assert response.status_code == 200, response.text
    updated = next(clip for clip in client.get(f"{base}/clips").json() if clip["id"] == saved["id"])
    assert updated["render_config"]["layout"] == "stacked"
    assert updated["render_config"]["panels"][1]["zoom"] == 1.8
    for key, value in body["render_config"].items():
        assert updated["render_config"][key] == value
    assert updated["caption_config"]["font"] == "Montserrat"
    assert updated["caption_config"]["weight"] == 500
    assert updated["caption_config"]["cues"] == cues
    assert updated["revision"] == saved["revision"] + 1 and updated["status"] == "DRAFT"
    response = client.post(
        f"{base}/clip-actions",
        json={
            "action": "update",
            "clip_ids": [saved["id"]],
            "caption_config": {"size": 62},
        },
    )
    assert response.status_code == 200, response.text
    caption_only = next(
        clip for clip in client.get(f"{base}/clips").json() if clip["id"] == saved["id"]
    )
    assert caption_only["render_config"] == updated["render_config"]
    assert caption_only["caption_config"]["cues"] == cues
    assert caption_only["caption_config"]["size"] == 62


def test_batch_layout_only_update_and_invalid_panels(client, source_project):
    base = f"/api/v1/projects/{source_project}"
    saved = client.post(
        f"{base}/clips",
        json={
            "title": "Apply layout",
            "start_ms": 0,
            "end_ms": 9000,
        },
    ).json()
    response = client.post(
        f"{base}/clip-actions",
        json={
            "action": "update",
            "clip_ids": [saved["id"]],
            "render_config": {"layout": "grid"},
        },
    )
    assert response.status_code == 200, response.text
    grid = next(clip for clip in client.get(f"{base}/clips").json() if clip["id"] == saved["id"])
    assert grid["render_config"]["layout"] == "grid" and len(grid["render_config"]["panels"]) == 4
    for config in [
        {"layout": "stacked", "panels": [{"subject": "person-1"}]},
        {"panels": [{"subject": "person-1"}]},
    ]:
        response = client.post(
            f"{base}/clip-actions",
            json={
                "action": "update",
                "clip_ids": [saved["id"]],
                "render_config": config,
            },
        )
        assert response.status_code == 422, response.text
    unchanged = next(
        clip for clip in client.get(f"{base}/clips").json() if clip["id"] == saved["id"]
    )
    assert (
        unchanged["render_config"] == grid["render_config"]
        and unchanged["revision"] == grid["revision"]
    )


@pytest.mark.parametrize("edited", [False, True])
def test_editor_and_subtitles_share_speech_only_caption_timing(client, source_project, edited):
    base = f"/api/v1/projects/{source_project}"
    with next(app.dependency_overrides[get_db]()) as db:
        db.add(
            Transcript(
                project_id=uuid.UUID(source_project),
                language="en",
                full_text="Before after",
                segments=[
                    {
                        "start": 1,
                        "end": 7,
                        "text": "Before after",
                        "words": [
                            {"start": 1.2, "end": 2, "text": "Before"},
                            {"start": 5, "end": 6, "text": "after"},
                        ],
                    }
                ],
            )
        )
        db.commit()
    body = {"title": "Speech timing", "start_ms": 1000, "end_ms": 7000}
    if edited:
        body["caption_config"] = {
            "cues": [{"start_ms": 0, "end_ms": 6000, "text": "Fixed wording"}]
        }
    response = client.post(f"{base}/editor-preview", json=body)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert [(s["start"], s["end"]) for s in preview["caption_segments"]] == [(1.2, 2), (5, 6)]
    assert len(preview["segments"]) == 1, "Transcript remains intact for navigation"
    saved = client.post(f"{base}/clips", json=body)
    assert saved.status_code == 201, saved.text
    clip_id = saved.json()["id"]
    exported = client.get(f"{base}/clips/{clip_id}/subtitles")
    assert exported.status_code == 200, exported.text
    assert "00:00:00,200 --> 00:00:01,000" in exported.text
    assert "00:00:04,000 --> 00:00:05,000" in exported.text
    assert ("Fixed" if edited else "Before") in exported.text
    cues = client.get(f"{base}/clips/{clip_id}/captions").json()
    if edited:
        assert cues == body["caption_config"]["cues"], "Retain editable custom cue windows"
    else:
        assert [(cue["start_ms"], cue["end_ms"]) for cue in cues] == [(200, 1000), (4000, 5000)]


def test_automatic_preview_refines_legacy_faces_once_and_caches_the_original_footage(
    client, source_project, monkeypatch
):
    with next(app.dependency_overrides[get_db]()) as db:
        analysis = db.scalar(
            select(Analysis).where(Analysis.project_id == uuid.UUID(source_project))
        )
        original = analysis.face_frames
        refined = [FaceFrame.model_validate(frame) for frame in original]
        analysis.face_frames = [
            {"timestamp": frame["timestamp"], "faces": frame["faces"][:1]} for frame in original
        ]
        db.commit()
    detect = Mock(return_value=refined[:27])
    monkeypatch.setattr("clipforge_api.services.collage.CollageFaceDetector.analyze", detect)
    body = {
        "title": "Detect in source",
        "start_ms": 0,
        "end_ms": 9000,
        "render_config": {"layout": "auto"},
    }
    base = f"/api/v1/projects/{source_project}"
    for _ in range(2):
        response = client.post(f"{base}/editor-preview", json=body)
        assert response.status_code == 200, response.text
        assert response.json()["plan"]["layout"] == "stacked"
    assert detect.call_count == 1
    assert detect.call_args.args[:3] == ("https://example.com/same-video.mp4", 0, 9)
    with next(app.dependency_overrides[get_db]()) as db:
        analysis = db.scalar(
            select(Analysis).where(Analysis.project_id == uuid.UUID(source_project))
        )
        assert (
            sum(frame.get("detector") == "yunet-collage-v2" for frame in analysis.face_frames) == 27
        )
        assert len(analysis.face_frames) == 30, "Keep detections outside the refined clip range"
