import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text

from clipforge_api.config import settings
from clipforge_api.db import engine
from clipforge_api.logging_config import configure_logging
from clipforge_api.routes import (
    auth,
    billing,
    brands,
    clips,
    highlights,
    jobs,
    operations,
    projects,
    uploads,
)
from clipforge_api.schemas import UserOut
from clipforge_api.security import CurrentUser
from clipforge_api.services.usage import QuotaExceeded
from clipforge_api.storage import s3

configure_logging()
app = FastAPI(title="ClipForge API", version="0.1.0")
logger = logging.getLogger("clipforge")


@app.exception_handler(QuotaExceeded)
async def quota_error(request: Request, exc: QuotaExceeded) -> JSONResponse:
    return JSONResponse({"detail": str(exc), "code": exc.code}, status_code=402)


@app.middleware("http")
async def request_safety(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = str(uuid.uuid4())
    start = time.monotonic()
    # All browser mutations must originate from the configured frontend.
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and request.url.path != "/api/v1/billing/webhook"
    ):
        if request.headers.get("origin") not in settings().trusted_origins:
            return JSONResponse({"detail": "Untrusted request origin."}, status_code=403)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed", extra={"request_id": request_id, "path": request.url.path}
        )
        response = JSONResponse(
            {
                "detail": "The server could not complete this request. Please try again.",
                "request_id": request_id,
            },
            status_code=500,
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "status": response.status_code,
            "duration": time.monotonic() - start,
        },
    )
    return response


@app.get("/health")
@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    checks: dict[str, bool] = {}
    for name, check in {
        "postgres": lambda: database_check(),
        "redis": lambda: Redis.from_url(settings().redis_url).ping(),
        "storage": lambda: s3().head_bucket(Bucket=settings().s3_bucket),
        "worker": lambda: Redis.from_url(settings().redis_url).exists("clipforge:worker:heartbeat"),
    }.items():
        try:
            result = check()
            checks[name] = bool(result)
        except Exception:
            checks[name] = False
    return JSONResponse(checks, status_code=200 if all(checks.values()) else 503)


def database_check() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


@app.get("/api/v1/me", response_model=UserOut)
def me(user: CurrentUser) -> object:
    return user


app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(uploads.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(highlights.router, prefix="/api/v1")
app.include_router(clips.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(brands.router, prefix="/api/v1")
app.include_router(operations.router, prefix="/api/v1")

# Outside request_safety so handled server errors also carry CORS headers.
# Foreign origins remain blocked; never reflect arbitrary origins with cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().trusted_origins,
    allow_credentials=True,
    allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Request-ID"],
)
