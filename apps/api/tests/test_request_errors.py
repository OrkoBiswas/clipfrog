import pytest
from clipforge_api.config import Settings
from clipforge_api.db import get_db
from clipforge_api.main import app


@pytest.mark.parametrize(
    "origin", ["http://localhost:3000", "http://127.0.0.1:3000", "http://[::1]:3000"]
)
def test_loopback_render_requests_reach_auth_instead_of_failing_cors(client, origin):
    path = "/api/v1/projects/00000000-0000-0000-0000-000000000000/render-preview"
    preflight = client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    response = client.post(
        path, json={"title": "Preview", "start_ms": 0, "end_ms": 2000}, headers={"Origin": origin}
    )
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == origin
    assert response.json()["detail"] == "Please sign in to continue."


def test_production_origin_does_not_trust_loopback_or_lookalikes():
    assert Settings(app_url="https://app.example.com").trusted_origins == [
        "https://app.example.com"
    ]
    assert "http://localhost.evil.test:3000" not in Settings().trusted_origins


def test_foreign_mutations_stay_blocked(client):
    response = client.post("/api/v1/auth/logout", headers={"Origin": "https://evil.test"})
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers


def test_unhandled_error_is_safe_json_with_request_id_and_cors(client):
    def broken_db():
        raise RuntimeError("private database details")

    original = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/api/v1/me")
    finally:
        app.dependency_overrides[get_db] = original
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "private database" not in response.text
