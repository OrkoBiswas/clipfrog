import uuid
from typing import get_args

import pytest
from clipforge_api.clip_schemas import CaptionAnimation, CaptionConfig
from clipforge_api.db import get_db
from clipforge_api.main import app
from clipforge_api.models import Clip, Project
from pydantic import ValidationError


def test_removed_templates_api_is_unavailable(client):
    assert client.get("/api/v1/caption-templates").status_code == 404


def test_retired_external_animations_keep_custom_appearance():
    for animation in [
        "mogrt-pack1-01",
        "mogrt-pack1-02",
        "mogrt-pack1-03",
        "mogrt-pack1-04",
        "blue-slice",
        "smoke-block",
        "vertical-snap",
        "blue-echo",
    ]:
        config = CaptionConfig(
            animation=animation,
            style="Karaoke",
            font="Urbanist",
            size=42,
            primary_color="#000000",
            enabled=False,
        )
        assert config.animation == "word-pop"
        assert config.style == "Karaoke"
        assert config.font == "Urbanist"
        assert config.size == 42
        assert config.primary_color == "#000000"
        assert config.enabled is False


@pytest.mark.parametrize("animation", get_args(CaptionAnimation))
def test_caption_settings_round_trip(animation):
    config = CaptionConfig(
        animation=animation,
        style="My signature",
        italic=True,
        size=72,
        font="Montserrat",
        spacing=2.5,
        outline=0,
        background=True,
        background_opacity=0.9,
        y=0.6,
        word_display="build",
        active_scale=1.12,
        inactive_opacity=0.4,
    )
    assert CaptionConfig.model_validate(config.model_dump()) == config
    assert config.animation == animation
    assert config.font == "Montserrat"


@pytest.mark.parametrize(
    "bad",
    [
        {"size": 999},
        {"primary_color": "not-a-color"},
        {"animation": "unknown"},
        {"y": float("nan")},
        {"word_display": "unknown"},
        {"active_scale": 5},
        {"inactive_opacity": -1},
    ],
)
def test_invalid_customizations_are_rejected(bad):
    with pytest.raises(ValidationError):
        CaptionConfig.model_validate(bad)


def test_apply_template_preserves_cues_and_checks_ownership(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Caption test",
            "email": "captions@example.com",
            "password": "test-long-password-123",
        },
    )
    project_id = client.post("/api/v1/projects", json={"name": "Isolated caption test"}).json()[
        "id"
    ]
    cues = [{"start_ms": 0, "end_ms": 2000, "text": "Original words"}]
    with next(app.dependency_overrides[get_db]()) as db:
        project = db.get(Project, uuid.UUID(project_id))
        project.status = "UPLOADED"
        clip = Clip(
            project_id=project.id,
            title="Existing clip",
            start_ms=0,
            end_ms=2000,
            aspect_ratio="9:16",
            caption_config={"cues": cues},
        )
        db.add(clip)
        db.commit()
        clip_id = str(clip.id)
    payload = {
        "action": "update",
        "clip_ids": [clip_id],
        "caption_config": {
            "animation": "word-pill",
            "word_display": "build",
            "active_scale": 1.12,
            "font": "Montserrat",
            "size": 72,
            "style": "Studio Rise",
            "cues": [],
        },
    }
    path = f"/api/v1/projects/{project_id}/clip-actions"
    assert client.post(path, json=payload).status_code == 200
    saved = client.get(f"/api/v1/projects/{project_id}/clips").json()[0]
    assert saved["caption_config"]["animation"] == "word-pill"
    assert saved["caption_config"]["word_display"] == "build"
    assert saved["caption_config"]["active_scale"] == 1.12
    assert saved["caption_config"]["size"] == 72
    assert saved["caption_config"]["cues"] == cues
    assert saved["revision"] == 2
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Other",
            "email": "other-captions@example.com",
            "password": "test-long-password-123",
        },
    )
    assert client.post(path, json=payload).status_code == 404
