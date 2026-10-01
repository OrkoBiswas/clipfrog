import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from clipforge_api.config import settings
from clipforge_api.db import SessionLocal
from clipforge_api.models import MediaAsset, ProcessingJob, Project
from clipforge_api.storage import s3

from clipforge_worker.celery_app import celery
from clipforge_worker.jobs.runtime import run_job, succeed
from clipforge_worker.media.probe import probe


@celery.task(name="clipforge.probe", soft_time_limit=900, time_limit=960)
def probe_source(job_id: str) -> None:
    with run_job(job_id, "VALIDATING") as context:
        if not context:
            return
        with SessionLocal() as db:
            job = db.get(ProcessingJob, context.id)
            assert job
            project = db.get(Project, job.project_id)
            assert project and project.source_asset_id
            asset = db.get(MediaAsset, project.source_asset_id)
            assert asset
            asset_id, key, size = asset.id, asset.storage_key, asset.size_bytes
        with TemporaryDirectory(prefix=f"clipforge-{job_id}-") as directory:
            source = Path(directory) / "source"
            context.progress("Reading media", 10)
            s3().download_file(settings().s3_bucket, key, str(source))
            if source.stat().st_size != size:
                raise ValueError("Uploaded file size does not match the declared size.")
            info = probe(source)
            if info.duration_ms > settings().max_source_duration_minutes * 60_000:
                raise ValueError("The video exceeds the source duration limit.")
            context.progress("Saving metadata", 90)
            with source.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            with SessionLocal() as db:
                asset = db.get(MediaAsset, asset_id)
                assert asset
                for field in ("width", "height", "duration_ms", "fps", "codec"):
                    setattr(asset, field, getattr(info, field))
                asset.checksum = checksum
                db.commit()
        succeed(context, "UPLOADED", "Upload complete")
