"""Exercise the API, queue and worker against real development dependencies."""

import httpx
from clipforge_worker.celery_app import ping

response = httpx.get("http://localhost:8000/ready", timeout=15)
response.raise_for_status()
assert all(response.json().values()), response.text
print("API readiness:", response.json())
result = ping.delay().get(timeout=30)
assert result == {"worker": "ok", "postgres": "ok", "storage": "ok"}, result
print("Redis -> Celery -> PostgreSQL/MinIO:", result)
