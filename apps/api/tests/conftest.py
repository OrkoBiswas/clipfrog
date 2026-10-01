import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from clipforge_api.db import Base, get_db  # noqa: E402
from clipforge_api.main import app  # noqa: E402
from clipforge_api.security import rate_limit  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)

    def db():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[rate_limit] = lambda: None
    monkeypatch.setattr("clipforge_api.routes.auth.send_token", lambda *args: None)
    with TestClient(app, headers={"Origin": "http://localhost:3000"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
