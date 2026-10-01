import uuid
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from clipforge_api.config import settings
from clipforge_api.db import SessionLocal
from clipforge_api.models import Clip, MediaAsset, ProcessingJob
from clipforge_api.services.usage import storage_check
from clipforge_api.storage import s3

from clipforge_worker.celery_app import celery
from clipforge_worker.jobs.runtime import run_job, succeed


@celery.task(name="clipforge.export", soft_time_limit=3600, time_limit=3700)
def export_clips(job_id: str) -> None:
    with run_job(job_id, "EXPORTING") as context:
        if context is None:
            return
        with SessionLocal() as db:
            job = db.get(ProcessingJob, context.id)
            assert job
            project_id, owner = job.project_id, job.user_id
            keys = []
            for value in job.parameters["clip_ids"]:
                clip = db.get(Clip, uuid.UUID(value))
                assert clip and clip.project_id == project_id and clip.output_asset_id
                asset = db.get(MediaAsset, clip.output_asset_id)
                assert asset
                keys.append((str(clip.id), asset.storage_key))
        with TemporaryDirectory(prefix=f"clipforge-export-{job_id}-") as directory:
            root = Path(directory)
            archive = root / "clips.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
                for index, (clip_id, key) in enumerate(keys):
                    context.progress(
                        f"Packaging clip {index + 1} of {len(keys)}", round(index / len(keys) * 90)
                    )
                    local = root / "clip.mp4"
                    s3().download_file(settings().s3_bucket, key, str(local))
                    output.write(local, f"clip-{clip_id}.mp4")
                    local.unlink()
            context.progress("Saving archive", 95)
            storage_key = f"users/{owner}/projects/{project_id}/exports/{job_id}.zip"
            with SessionLocal() as db:
                existing = db.get(MediaAsset, context.id)
                if not existing:
                    storage_check(db, owner, archive.stat().st_size)
                    s3().upload_file(
                        str(archive),
                        settings().s3_bucket,
                        storage_key,
                        ExtraArgs={"ContentType": "application/zip"},
                    )
                    db.add(
                        MediaAsset(
                            id=context.id,
                            project_id=project_id,
                            user_id=owner,
                            type="ARCHIVE",
                            storage_key=storage_key,
                            original_filename="clips.zip",
                            mime_type="application/zip",
                            size_bytes=archive.stat().st_size,
                        )
                    )
                db.commit()
        succeed(context, "COMPLETED", "Archive ready")
