import uuid

from botocore.exceptions import ClientError
from clipforge_api.config import settings
from clipforge_api.db import SessionLocal
from clipforge_api.models import MediaAsset, Project, UploadSession
from clipforge_api.storage import s3
from sqlalchemy import select

from clipforge_worker.celery_app import celery


@celery.task(
    name="clipforge.cleanup", autoretry_for=(Exception,), retry_backoff=True, max_retries=8
)
def cleanup(project_id: str) -> None:
    """Delete remote objects before removing their database ownership records."""
    with SessionLocal() as db:
        project = db.get(Project, uuid.UUID(project_id))
        if not project or project.status != "DELETING":
            return
        client = s3()
        for upload in db.scalars(
            select(UploadSession).where(
                UploadSession.project_id == project.id, UploadSession.status == "UPLOADING"
            )
        ):
            asset = db.get(MediaAsset, upload.asset_id)
            if asset:
                try:
                    client.abort_multipart_upload(
                        Bucket=settings().s3_bucket,
                        Key=asset.storage_key,
                        UploadId=upload.upload_id,
                    )
                except ClientError as exc:
                    if exc.response["Error"]["Code"] != "NoSuchUpload":
                        raise
        for asset in db.scalars(select(MediaAsset).where(MediaAsset.project_id == project.id)):
            client.delete_object(Bucket=settings().s3_bucket, Key=asset.storage_key)
        db.delete(project)
        db.commit()
