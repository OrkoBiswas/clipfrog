import uuid
from typing import Literal

from clipforge_worker.celery_app import celery
from clipforge_worker.transcription.base import Segment
from clipforge_worker.transcription.export import subtitles
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select

from clipforge_api.models import (
    Analysis,
    MediaAsset,
    ProcessingJob,
    Project,
    Scene,
    Transcript,
    now,
)
from clipforge_api.routes.projects import owned_project
from clipforge_api.security import CurrentUser, Db
from clipforge_api.services.usage import reserve, settle

router = APIRouter(tags=["Processing"])


@router.get("/projects/{project_id}/transcript/export")
def export_transcript(
    project_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    format: Literal["txt", "srt", "vtt", "json"] = "txt",
) -> Response:
    import json

    owned_project(db, user, project_id)
    item = db.scalar(select(Transcript).where(Transcript.project_id == project_id))
    if not item:
        raise HTTPException(404, "Transcript is not available yet.")
    if format == "txt":
        content = item.full_text
    elif format == "json":
        content = json.dumps(
            {"language": item.language, "segments": item.segments}, ensure_ascii=False
        )
    else:
        content = subtitles([Segment.model_validate(s) for s in item.segments], format == "vtt")
    return Response(
        content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="transcript.{format}"'},
    )


@router.post("/projects/{project_id}/analyze", status_code=202)
def analyze(project_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, str]:
    project = owned_project(db, user, project_id, lock=True)
    if project.status == "DELETING":
        raise HTTPException(409, "This project is being deleted.")
    asset = db.get(MediaAsset, project.source_asset_id) if project.source_asset_id else None
    if not asset or not asset.duration_ms:
        raise HTTPException(409, "Upload and validate a source video first.")
    if db.scalar(
        select(ProcessingJob.id).where(
            ProcessingJob.project_id == project_id,
            ProcessingJob.status.in_(["QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"]),
        )
    ):
        raise HTTPException(409, "A job is already active for this project.")
    job = ProcessingJob(
        id=uuid.uuid4(), user_id=project.user_id, project_id=project_id, job_type="analyze"
    )
    db.add(job)
    reserve(db, job, "input_minutes", asset.duration_ms / 60000)
    project.status = "ANALYZING"
    db.commit()
    dispatch(db, job)
    return {"job_id": str(job.id)}


def dispatch(db: Db, job: ProcessingJob) -> None:
    try:
        celery.send_task(
            f"clipforge.{job.job_type}", args=[str(job.id)], task_id=str(job.id), queue=job.queue
        )
    except Exception:
        settle(db, job, False)
        job.status = "FAILED"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = "The queue is unavailable. Your source is safe; retry shortly."
        job.finished_at = now()
        project = db.get(Project, job.project_id)
        if project:
            project.status = "FAILED"
        db.commit()
        raise HTTPException(503, job.error_message) from None


@router.get("/projects/{project_id}/transcript")
def transcript(project_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, object] | None:
    owned_project(db, user, project_id)
    item = db.scalar(select(Transcript).where(Transcript.project_id == project_id))
    if not item:
        return None
    analysis = db.scalar(select(Analysis).where(Analysis.project_id == project_id))
    scenes = db.scalars(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.start_ms)
    )
    return {
        "language": item.language,
        "text": item.full_text,
        "segments": item.segments,
        "warnings": analysis.warnings if analysis else [],
        "scenes": [{"start_ms": s.start_ms, "end_ms": s.end_ms} for s in scenes],
    }


@router.get("/projects/{project_id}/jobs")
def jobs(project_id: uuid.UUID, db: Db, user: CurrentUser) -> list[dict[str, object]]:
    owned_project(db, user, project_id)
    items = db.scalars(
        select(ProcessingJob)
        .where(ProcessingJob.project_id == project_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(50)
    )
    return [
        {
            "id": str(j.id),
            "status": j.status,
            "stage": j.stage,
            "progress": j.progress,
            "error_code": j.error_code,
            "error_message": j.error_message,
            "started_at": j.started_at,
            "finished_at": j.finished_at,
            "job_type": j.job_type,
        }
        for j in items
    ]


@router.get("/projects/{project_id}/source")
def source(project_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, object] | None:
    project = owned_project(db, user, project_id)
    asset = db.get(MediaAsset, project.source_asset_id) if project.source_asset_id else None
    if not asset:
        return None
    return {
        "filename": asset.original_filename,
        "size_bytes": asset.size_bytes,
        "width": asset.width,
        "height": asset.height,
        "duration_ms": asset.duration_ms,
        "codec": asset.codec,
    }


@router.post("/projects/{project_id}/jobs/{job_id}/retry")
def retry(project_id: uuid.UUID, job_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, str]:
    project = owned_project(db, user, project_id, lock=True)
    if project.status == "DELETING" or db.scalar(
        select(ProcessingJob.id).where(
            ProcessingJob.project_id == project_id,
            ProcessingJob.status.in_(["QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"]),
        )
    ):
        raise HTTPException(409, "Wait for the active operation to finish before retrying.")
    job = db.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.id == job_id, ProcessingJob.project_id == project_id)
        .with_for_update()
    )
    if not job or job.status not in {"FAILED", "CANCELED"}:
        raise HTTPException(409, "Only a failed or canceled job can be retried.")
    job.status = "RETRYING"
    job.error_code = None
    job.error_message = None
    job.finished_at = None
    if job.parameters.get("usage_metric"):
        reserve(
            db, job, str(job.parameters["usage_metric"]), float(job.parameters["usage_quantity"])
        )
    project.status = {
        "probe": "VALIDATING",
        "highlights": "FINDING_HIGHLIGHTS",
        "render": "RENDERING",
        "export": "EXPORTING",
    }.get(job.job_type, "ANALYZING")
    db.commit()
    dispatch(db, job)
    return {"status": job.status}


@router.post("/projects/{project_id}/jobs/{job_id}/cancel")
def cancel(project_id: uuid.UUID, job_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, str]:
    project = owned_project(db, user, project_id, lock=True)
    job = db.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.id == job_id, ProcessingJob.project_id == project_id)
        .with_for_update()
    )
    if not job or job.status not in {"QUEUED", "RUNNING", "RETRYING"}:
        raise HTTPException(409, "This job is no longer active.")
    job.status = "CANCEL_REQUESTED" if job.status == "RUNNING" else "CANCELED"
    job.finished_at = now() if job.status == "CANCELED" else None
    if job.status == "CANCELED":
        settle(db, job, False)
    project.status = job.status
    db.commit()
    return {"status": job.status}
