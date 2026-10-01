from clipforge_api.services.caption_templates import TEMPLATES


def register(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": "Templates", "password": "long-enough-password"},
    ).raise_for_status()


def test_custom_library_ownership_defaults_and_deletion(client):
    register(client, "templates@example.com")
    assert len(client.get("/api/v1/caption-templates").json()["items"]) == 25
    result = client.post(
        "/api/v1/caption-templates", json={"name": "Personal", "config": TEMPLATES[0]["config"]}
    )
    assert result.status_code == 201
    identifier = result.json()["id"]
    for action in ["favorite", "recent", "default"]:
        assert (
            client.post(
                f"/api/v1/caption-templates/{identifier}/preference", json={"action": action}
            ).status_code
            == 200
        )
    library = client.get("/api/v1/caption-templates").json()
    assert library["default"] == identifier and identifier in library["favorites"]
    assert (
        client.put(
            f"/api/v1/caption-templates/{identifier}",
            json={"name": "Renamed", "config": {"size": 80}},
        ).status_code
        == 200
    )
    client.post("/api/v1/auth/logout")
    register(client, "outsider-template@example.com")
    assert client.delete(f"/api/v1/caption-templates/{identifier}").status_code == 404
    assert len(client.get("/api/v1/caption-templates").json()["items"]) == 25


def test_templates_are_distinct_and_valid():
    assert len(TEMPLATES) == 25
    assert (
        len(
            {
                tuple(sorted((k, str(v)) for k, v in t["config"].items() if k != "template_id"))
                for t in TEMPLATES
            }
        )
        == 25
    )
