from celery import Celery
from celery.signals import heartbeat_sent, setup_logging
from clipforge_api.config import settings
from clipforge_api.logging_config import configure_logging
from redis import Redis

celery = Celery("clipforge", broker=settings().redis_url, backend=settings().redis_url)
setup_logging.connect(configure_logging)
celery.conf.imports = [
    "clipforge_worker.jobs.probe_source",
    "clipforge_worker.jobs.cleanup",
    "clipforge_worker.jobs.analyze_project",
    "clipforge_worker.jobs.find_highlights",
    "clipforge_worker.jobs.render_clips",
    "clipforge_worker.jobs.export_clips",
    "clipforge_worker.jobs.maintenance",
]
celery.conf.update(
    task_default_queue="analysis",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "maintenance": {
            "task": "clipforge.maintenance",
            "schedule": 60.0,
            "options": {"queue": "maintenance"},
        }
    },
)


@heartbeat_sent.connect
def heartbeat(**kwargs: object) -> None:
    Redis.from_url(settings().redis_url).set("clipforge:worker:heartbeat", "ready", ex=30)


@celery.task(name="clipforge.ping")
def ping() -> dict[str, str]:
    from clipforge_api.db import engine
    from clipforge_api.storage import s3
    from sqlalchemy import text

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    s3().head_bucket(Bucket=settings().s3_bucket)
    return {"worker": "ok", "postgres": "ok", "storage": "ok"}
