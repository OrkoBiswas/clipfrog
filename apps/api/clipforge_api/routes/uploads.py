import math
import uuid
from datetime import timedelta
from pathlib import PurePath

from clipforge_worker.celery_app import celery
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from clipforge_api.config import settings
from clipforge_api.models import MediaAsset, ProcessingJob, UploadSession, now
from clipforge_api.routes.projects import owned_project
from clipforge_api.security import CurrentUser, Db
from clipforge_api.services.multipart import discard, finalize, uploaded_parts
from clipforge_api.services.usage import storage_check
from clipforge_api.storage import s3

router = APIRouter(prefix="/projects/{project_id}/upload", tags=["Uploads"])
EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
MIMES = {
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
    "video/x-m4v",
    "application/octet-stream",
}


class InitiateInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    mime_type: str = Field(max_length=100)


def upload_for(
    db: Db, user: CurrentUser, project_id: uuid.UUID, upload_session_id: uuid.UUID
) -> tuple[UploadSession, MediaAsset]:
    owned_project(db, user, project_id, lock=True)
    upload = db.scalar(
        select(UploadSession)
        .where(UploadSession.id == upload_session_id, UploadSession.project_id == project_id)
        .with_for_update()
    )
    if not upload:
        raise HTTPException(404, "Upload not found.")
    asset = db.get(MediaAsset, upload.asset_id)
    assert asset is not None
    return upload, asset


@router.post("/initiate", status_code=201)
def initiate(
    project_id: uuid.UUID, body: InitiateInput, db: Db, user: CurrentUser
) -> dict[str, object]:
    project = owned_project(db, user, project_id, lock=True)
    if project.source_asset_id or project.status not in {"DRAFT", "FAILED", "CANCELED"}:
        raise HTTPException(409, "This project already has a source or active upload.")
    if body.size_bytes > settings().max_upload_bytes:
        raise HTTPException(413, "The source exceeds the upload size limit.")
    storage_check(db, project.user_id, body.size_bytes)
    suffix = PurePath(body.filename).suffix.lower()
    if suffix not in EXTENSIONS or body.mime_type not in MIMES:
        raise HTTPException(415, "Choose an MP4, MOV, MKV, WebM or M4V video.")
    asset = MediaAsset(
        id=uuid.uuid4(),
        user_id=project.user_id,
        project_id=project.id,
        type="source",
        storage_key=f"users/{project.user_id}/projects/{project.id}/source/{uuid.uuid4()}{suffix}",
        original_filename=body.filename,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
    )
    response = s3().create_multipart_upload(
        Bucket=settings().s3_bucket, Key=asset.storage_key, ContentType=asset.mime_type
    )
    upload = UploadSession(
        id=uuid.uuid4(),
        project_id=project.id,
        asset_id=asset.id,
        upload_id=response["UploadId"],
        part_size=16 * 1024**2,
        expires_at=now() + timedelta(days=1),
    )
    try:
        db.add(asset)
        db.flush()
        db.add(upload)
        project.status = "UPLOADING"
        db.commit()
    except Exception:
        s3().abort_multipart_upload(
            Bucket=settings().s3_bucket, Key=asset.storage_key, UploadId=upload.upload_id
        )
        raise
    return {
        "id": str(upload.id),
        "part_size": upload.part_size,
        "part_count": math.ceil(asset.size_bytes / upload.part_size),
    }


@router.get("/{upload_session_id}")
def status(
    project_id: uuid.UUID, upload_session_id: uuid.UUID, db: Db, user: CurrentUser
) -> dict[str, object]:
    upload, asset = upload_for(db, user, project_id, upload_session_id)
    parts: list[dict[str, object]] = []
    if upload.status == "UPLOADING":
        try:
            stored = uploaded_parts(
                s3(), settings().s3_bucket, asset.storage_key, upload.upload_id, asset.size_bytes
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if stored is None:
            parts = [
                {
                    "number": index + 1,
                    "size": min(upload.part_size, asset.size_bytes - index * upload.part_size),
                }
                for index in range(math.ceil(asset.size_bytes / upload.part_size))
            ]
        else:
            parts = [{"number": p["PartNumber"], "size": p["Size"]} for p in stored]
    return {
        "id": str(upload.id),
        "status": upload.status,
        "filename": asset.original_filename,
        "size_bytes": asset.size_bytes,
        "part_size": upload.part_size,
        "parts": parts,
    }


@router.post("/{upload_session_id}/parts/{number}")
def sign_part(
    project_id: uuid.UUID, upload_session_id: uuid.UUID, number: int, db: Db, user: CurrentUser
) -> dict[str, str]:
    upload, asset = upload_for(db, user, project_id, upload_session_id)
    if upload.status != "UPLOADING" or upload.expires_at < now():
        raise HTTPException(409, "This upload is no longer active.")
    if not 1 <= number <= math.ceil(asset.size_bytes / upload.part_size):
        raise HTTPException(422, "Invalid part number.")
    expected_size = min(upload.part_size, asset.size_bytes - (number - 1) * upload.part_size)
    url = s3(public=True).generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": settings().s3_bucket,
            "Key": asset.storage_key,
            "UploadId": upload.upload_id,
            "PartNumber": number,
            "ContentLength": expected_size,
        },
        ExpiresIn=900,
    )
    return {"url": url}


@router.post("/{upload_session_id}/complete")
def complete(
    project_id: uuid.UUID, upload_session_id: uuid.UUID, db: Db, user: CurrentUser
) -> dict[str, str]:
    upload, asset = upload_for(db, user, project_id, upload_session_id)
    if upload.status == "COMPLETED":
        existing = db.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.project_id == project_id, ProcessingJob.job_type == "probe")
            .order_by(ProcessingJob.created_at.desc())
        )
        return {"status": "VALIDATING", "job_id": str(existing.id) if existing else ""}
    if upload.status != "UPLOADING":
        raise HTTPException(409, "This upload was canceled.")
    try:
        finalize(
            s3(),
            settings().s3_bucket,
            asset.storage_key,
            upload.upload_id,
            asset.size_bytes,
            upload.part_size,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    project = owned_project(db, user, project_id)
    project.source_asset_id = asset.id
    project.status = "VALIDATING"
    upload.status = "COMPLETED"
    job = ProcessingJob(
        id=uuid.uuid4(), user_id=project.user_id, project_id=project_id, job_type="probe"
    )
    db.add(job)
    db.commit()
    try:
        celery.send_task(
            "clipforge.probe", args=[str(job.id)], task_id=str(job.id), queue="analysis"
        )
    except Exception:
        job.status = "FAILED"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = "Your upload is safe. Retry validation when the worker is available."
        project.status = "FAILED"
        db.commit()
        raise HTTPException(503, job.error_message) from None
    return {"status": project.status, "job_id": str(job.id)}


@router.delete("/{upload_session_id}", status_code=204)
def abort(project_id: uuid.UUID, upload_session_id: uuid.UUID, db: Db, user: CurrentUser) -> None:
    upload, asset = upload_for(db, user, project_id, upload_session_id)
    if upload.status != "UPLOADING":
        raise HTTPException(409, "Only an active upload can be canceled.")
    discard(s3(), settings().s3_bucket, asset.storage_key, upload.upload_id)
    upload.status = "CANCELED"
    asset.size_bytes = 0
    owned_project(db, user, project_id).status = "DRAFT"
    db.commit()
