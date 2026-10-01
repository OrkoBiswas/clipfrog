"""Real PostgreSQL + SMTP integration check for one-use auth tokens."""

import re
import time
import uuid

import httpx

email = f"auth-check-{uuid.uuid4().hex}@example.com"
with httpx.Client(
    base_url="http://localhost:8000/api/v1", headers={"Origin": "http://localhost:3000"}
) as client:
    client.post(
        "/auth/register",
        json={"email": email, "name": "Auth check", "password": "original-strong-password"},
    ).raise_for_status()
    client.post("/auth/forgot-password", json={"email": email}).raise_for_status()
    token = None
    for _ in range(20):
        messages = httpx.get("http://localhost:8025/api/v1/messages").json()["messages"]
        for message in messages:
            if message["Subject"] == "Reset your password" and any(
                item["Address"] == email for item in message["To"]
            ):
                content = httpx.get(f"http://localhost:8025/api/v1/message/{message['ID']}").json()
                match = re.search(r"token=([A-Za-z0-9_-]+)", content["Text"])
                assert match
                token = match.group(1)
        if token:
            break
        time.sleep(0.25)
    assert token, "Reset email was not delivered"
    payload = {"token": token, "password": "replacement-strong-password"}
    assert client.post("/auth/reset-password", json=payload).status_code == 200
    assert client.get("/me").status_code == 401, "Reset must revoke existing sessions"
    assert client.post("/auth/reset-password", json=payload).status_code == 400, (
        "Token must be single-use"
    )
    assert (
        client.post(
            "/auth/login", json={"email": email, "password": payload["password"]}
        ).status_code
        == 200
    )
    print("SMTP delivery, password reset, session revocation and token replay protection passed")
