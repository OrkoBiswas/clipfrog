import uuid
from contextlib import contextmanager
from unittest.mock import Mock

from clipforge_api.db import get_db
from clipforge_api.main import app
from clipforge_api.models import (
    ClipCandidate,
    HighlightFeedback,
    MediaAsset,
    ProcessingJob,
    Project,
    Transcript,
)
from clipforge_api.services.highlight_learning import learning_report, rejected_moment
from clipforge_worker.highlights.heuristic_ranker import DEFAULT_WEIGHTS, ENGINE_VERSION
from clipforge_worker.jobs import find_highlights as pipeline
from sqlalchemy import select


def test_local_highlight_job_applies_validated_preferences_and_stays_offline(client, monkeypatch):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "pipeline-learning@example.com",
            "name": "Learner",
            "password": "long-enough-password",
        },
    ).raise_for_status()
    project_id = client.post("/api/v1/projects", json={"name": "Learned pipeline"}).json()["id"]
    for db in app.dependency_overrides[get_db]():
        project = db.get(Project, uuid.UUID(project_id))
        asset = MediaAsset(
            id=uuid.uuid4(),
            project_id=project.id,
            user_id=project.user_id,
            type="SOURCE",
            storage_key="source.mp4",
            original_filename="source.mp4",
            mime_type="video/mp4",
            size_bytes=100,
            duration_ms=45000,
        )
        db.add(asset)
        project.source_asset_id = asset.id
        # A legacy opt-in cannot cause a network request in the new local engine.
        project.processing_config = {
            "duration_min": 5,
            "duration_max": 12,
            "clip_count": 1,
            "minimum_score": 0,
            "semantic_ranking": True,
        }
        db.add(
            Transcript(
                project_id=project.id,
                language="en",
                full_text="A clear idea.",
                segments=[
                    {
                        "start": 1,
                        "end": 11,
                        "text": "Why do interviews fail? Ask about real behavior instead because opinions cannot validate your idea.",
                    },
                    {
                        "start": 20,
                        "end": 30,
                        "text": "First test the microphone. A loose cable can ruin a recording, so record an example before starting.",
                    },
                ],
            )
        )
        for label in ["good", "poor"]:
            for i in range(4):
                features = dict.fromkeys(DEFAULT_WEIGHTS, 0.5)
                features["insight"] = 0.9 - i * 0.01 if label == "good" else 0.1 + i * 0.01
                features["visual"] = 0.1 + i * 0.01 if label == "good" else 0.9 - i * 0.01
                db.add(
                    HighlightFeedback(
                        user_id=project.user_id,
                        project_id=project.id,
                        fingerprint=f"{label}-{i}",
                        start_ms=35000 + i,
                        end_ms=40000 + i,
                        rating=label,
                        features=features,
                        engine_version=ENGINE_VERSION,
                    )
                )
        job = ProcessingJob(
            id=uuid.uuid4(), project_id=project.id, user_id=project.user_id, job_type="highlights"
        )
        db.add(job)
        db.commit()
        job_id = str(job.id)
        learned = learning_report(db, project.user_id)
    assert learned["status"] == "personalized"

    @contextmanager
    def session():
        yield from app.dependency_overrides[get_db]()

    context = Mock(id=uuid.UUID(job_id))

    @contextmanager
    def running(*args):
        yield context

    monkeypatch.setattr(pipeline, "SessionLocal", session)
    monkeypatch.setattr(pipeline, "run_job", running)
    monkeypatch.setattr(pipeline, "succeed", Mock())
    monkeypatch.setattr(pipeline, "s3", lambda: Mock())
    monkeypatch.setattr(pipeline, "extract_audio", Mock())
    monkeypatch.setattr(pipeline, "audio_energy", lambda path: [])
    cloud = Mock(side_effect=AssertionError("Highlight ranking must remain local"))
    monkeypatch.setattr("httpx.post", cloud)
    pipeline.find_highlights.run(job_id)
    cloud.assert_not_called()
    for db in app.dependency_overrides[get_db]():
        job = db.get(ProcessingJob, uuid.UUID(job_id))
        assert job.parameters["highlight_engine"]["personalized"] is True
        assert job.parameters["highlight_engine"]["mode"] == "local"
        candidates = list(
            db.scalars(
                select(ClipCandidate).where(ClipCandidate.project_id == uuid.UUID(project_id))
            )
        )
        assert candidates and any(candidate.selected for candidate in candidates)
        for candidate in candidates:
            assert candidate.scoring_metadata["engine_version"] == ENGINE_VERSION
            features = candidate.scoring_metadata["features"]
            assert candidate.score_total == sum(
                round(features[key] * learned["weights"][key], 2) for key in features
            )


def test_rejection_covers_trimmed_variants_without_removing_a_different_moment():
    assert rejected_moment(1000, 11000, [(2000, 12000)])
    assert rejected_moment(1000, 11000, [(2000, 5000)])
    assert not rejected_moment(20000, 30000, [(2000, 12000)])
