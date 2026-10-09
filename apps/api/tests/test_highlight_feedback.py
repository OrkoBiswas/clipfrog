import uuid

from clipforge_api.db import get_db
from clipforge_api.main import app
from clipforge_api.models import ClipCandidate, HighlightFeedback
from clipforge_worker.highlights.heuristic_ranker import DEFAULT_WEIGHTS, ENGINE_VERSION
from sqlalchemy import select


def setup(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "learning@example.com",
            "name": "Learning",
            "password": "long-enough-password",
        },
    ).raise_for_status()
    project_id = client.post("/api/v1/projects", json={"name": "Private ranking"}).json()["id"]
    for db in app.dependency_overrides[get_db]():
        db.add(
            ClipCandidate(
                id=uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                start_ms=1000,
                end_ms=15000,
                transcript_text="A real moment with a clear complete idea.",
                score_total=70,
                score_breakdown={"hook": 20},
                reason="Editorial quality",
                title="A real moment",
                selected=True,
                rank=1,
                scoring_metadata={
                    "engine_version": ENGINE_VERSION,
                    "features": dict.fromkeys(DEFAULT_WEIGHTS, 0.7),
                },
            )
        )
        db.commit()
    base = f"/api/v1/projects/{project_id}"
    item = client.get(f"{base}/highlights").json()["items"][0]
    return project_id, base, item


def test_feedback_is_idempotent_reversible_and_survives_regeneration(client):
    project_id, base, item = setup(client)
    url = f"{base}/highlights/{item['id']}/feedback"
    for _ in range(2):
        response = client.put(url, json={"rating": "good"})
        assert response.status_code == 200, response.text
        assert response.json()["learning"]["good_ratings"] == 1
    assert client.put(url, json={"rating": "poor"}).json()["learning"]["good_ratings"] == 0
    assert client.get(f"{base}/highlights").json()["items"][0]["feedback"] == "poor"
    for db in app.dependency_overrides[get_db]():
        previous = db.get(ClipCandidate, uuid.UUID(item["id"]))
        data = {
            key: getattr(previous, key)
            for key in (
                "project_id",
                "start_ms",
                "end_ms",
                "transcript_text",
                "score_total",
                "score_breakdown",
                "scoring_metadata",
                "reason",
                "title",
                "selected",
                "rank",
            )
        }
        db.delete(previous)
        db.flush()
        db.add(ClipCandidate(id=uuid.uuid4(), **data))
        db.commit()
        assert len(list(db.scalars(select(HighlightFeedback)))) == 1
    new_item = client.get(f"{base}/highlights").json()["items"][0]
    assert new_item["feedback"] == "poor"
    assert new_item["id"] != item["id"]
    response = client.put(f"{base}/highlights/{new_item['id']}/feedback", json={"rating": None})
    assert response.json()["learning"]["poor_ratings"] == 0


def test_feedback_and_learning_are_isolated_by_account(client):
    project_id, base, item = setup(client)
    client.put(
        f"{base}/highlights/{item['id']}/feedback", json={"rating": "good"}
    ).raise_for_status()
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-learning@example.com",
            "name": "Other",
            "password": "long-enough-password",
        },
    )
    assert client.get(f"{base}/highlights").status_code == 404
    assert (
        client.put(f"{base}/highlights/{item['id']}/feedback", json={"rating": "poor"}).status_code
        == 404
    )
    assert client.get(f"{base}/highlights/{item['id']}/preview").status_code == 404
    other_id = client.post("/api/v1/projects", json={"name": "Other"}).json()["id"]
    report = client.get(f"/api/v1/projects/{other_id}/highlights").json()["learning"]
    assert report["good_ratings"] == 0 and report["poor_ratings"] == 0


def test_old_candidates_need_rescoring_and_wrong_project_is_rejected(client):
    project_id, base, item = setup(client)
    for db in app.dependency_overrides[get_db]():
        db.get(ClipCandidate, uuid.UUID(item["id"])).scoring_metadata = {}
        db.commit()
    response = client.put(f"{base}/highlights/{item['id']}/feedback", json={"rating": "good"})
    assert response.status_code == 409
    other_id = client.post("/api/v1/projects", json={"name": "Other project"}).json()["id"]
    assert (
        client.put(
            f"/api/v1/projects/{other_id}/highlights/{item['id']}/feedback", json={"rating": "good"}
        ).status_code
        == 404
    )
    assert (
        client.put(f"{base}/highlights/{item['id']}/feedback", json={"rating": "viral"}).status_code
        == 422
    )


def test_feature_snapshot_is_immutable_when_changing_a_vote(client):
    project_id, base, item = setup(client)
    url = f"{base}/highlights/{item['id']}/feedback"
    client.put(url, json={"rating": "good"}).raise_for_status()
    for db in app.dependency_overrides[get_db]():
        db.get(ClipCandidate, uuid.UUID(item["id"])).scoring_metadata = {
            "engine_version": ENGINE_VERSION,
            "features": dict.fromkeys(DEFAULT_WEIGHTS, 0.2),
        }
        db.commit()
    client.put(url, json={"rating": "poor"}).raise_for_status()
    for db in app.dependency_overrides[get_db]():
        feedback = db.scalar(select(HighlightFeedback))
        assert feedback.features == dict.fromkeys(DEFAULT_WEIGHTS, 0.7)
