import hashlib
import hmac
import json
import time
import uuid

import pytest
from clipforge_api.config import settings
from clipforge_api.db import get_db
from clipforge_api.main import app
from clipforge_api.models import ProcessingJob, Project, Subscription, User
from clipforge_api.services.billing import verify_event
from clipforge_api.services.usage import QuotaExceeded, reserve, settle, snapshot, storage_check
from sqlalchemy import select


def signed(payload, timestamp=None):
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(b"whsec_test", f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_webhook_authentication_tampering_and_expiry():
    payload = b'{"id":"evt_1","type":"example"}'
    assert verify_event(payload, signed(payload), "whsec_test")["id"] == "evt_1"
    with pytest.raises(ValueError):
        verify_event(payload + b" ", signed(payload), "whsec_test")
    with pytest.raises(ValueError):
        verify_event(payload, signed(payload, int(time.time()) - 301), "whsec_test")


def test_reservations_prevent_overuse_and_release_on_failure(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "usage@example.com", "name": "Usage", "password": "long-enough-password"},
    )
    project_id = client.post("/api/v1/projects", json={"name": "Usage test"}).json()["id"]
    for db in app.dependency_overrides[get_db]():
        project = db.get(Project, uuid.UUID(project_id))
        job = ProcessingJob(
            id=uuid.uuid4(), project_id=project.id, user_id=project.user_id, job_type="analyze"
        )
        db.add(job)
        reserve(db, job, "input_minutes", 50)
        reserve(db, job, "input_minutes", 50)
        db.commit()
        assert snapshot(db, project.user_id)["usage"]["input_minutes"] == 50
        other = ProcessingJob(
            id=uuid.uuid4(), project_id=project.id, user_id=project.user_id, job_type="analyze"
        )
        with pytest.raises(QuotaExceeded):
            reserve(db, other, "input_minutes", 20)
        settle(db, job, False)
        db.commit()
        assert snapshot(db, project.user_id)["usage"]["input_minutes"] == 0


def test_admin_has_unlimited_usage_and_storage_without_disabling_tracking(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin-usage@example.com", "name": "Admin", "password": "long-enough-password"},
    )
    project_id = client.post("/api/v1/projects", json={"name": "Admin usage"}).json()["id"]
    for db in app.dependency_overrides[get_db]():
        user = db.scalar(select(User).where(User.email == "admin-usage@example.com"))
        project = db.get(Project, uuid.UUID(project_id))
        user.is_admin = True
        job = ProcessingJob(
            id=uuid.uuid4(), project_id=project.id, user_id=user.id, job_type="render"
        )
        db.add(job)
        reserve(db, job, "input_minutes", 100_000)
        reserve(db, job, "render_minutes", 100_000)
        storage_check(db, user.id, 10**15)
        db.commit()

        report = snapshot(db, user.id)
        assert report["plan"] == "admin"
        assert report["allowance"] == {
            "input_minutes": None,
            "render_minutes": None,
            "storage_bytes": None,
        }
        assert report["usage"]["input_minutes"] == 100_000
        assert report["usage"]["render_minutes"] == 100_000

    response = client.get("/api/v1/usage")
    assert response.json()["administrator"] is True
    assert response.json()["plan"] == "admin"
    assert client.post("/api/v1/billing/checkout", json={"plan": "pro"}).status_code == 409


def test_webhook_sync_duplicate_and_unconfigured_checkout(client, monkeypatch):
    user = client.post(
        "/api/v1/auth/register",
        json={
            "email": "billing@example.com",
            "name": "Billing",
            "password": "long-enough-password",
        },
    ).json()
    assert client.post("/api/v1/billing/checkout", json={"plan": "creator"}).status_code == 503
    monkeypatch.setattr(settings(), "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(settings(), "stripe_price_creator", "price_creator")
    for db in app.dependency_overrides[get_db]():
        db.add(Subscription(user_id=uuid.UUID(user["id"]), customer_id="cus_test"))
        db.commit()

    class FakePaymentProvider:
        def request(self, *args, **kwargs):
            return {
                "customer": "cus_test",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_creator"}}]},
            }

    monkeypatch.setattr("clipforge_api.services.billing.provider", FakePaymentProvider())
    payload = json.dumps(
        {
            "id": "evt_test",
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_test", "customer": "cus_test"}},
        }
    ).encode()
    headers = {"stripe-signature": signed(payload), "Origin": "https://api.stripe.com"}
    assert (
        client.post("/api/v1/billing/webhook", content=payload, headers=headers).status_code == 200
    )
    assert (
        client.post("/api/v1/billing/webhook", content=payload, headers=headers).status_code == 200
    )
    assert client.get("/api/v1/usage").json()["plan"] == "creator"
    assert (
        client.post("/api/v1/billing/webhook", content=payload + b" ", headers=headers).status_code
        == 400
    )
