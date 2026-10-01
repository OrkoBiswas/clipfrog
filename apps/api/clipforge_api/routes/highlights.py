import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from clipforge_api.models import ClipCandidate, ProcessingJob, Transcript
from clipforge_api.routes.jobs import dispatch
from clipforge_api.routes.projects import owned_project
from clipforge_api.security import CurrentUser, Db

router = APIRouter(tags=["Highlights"])


@router.post("/projects/{project_id}/highlights", status_code=202)
def generate(project_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, str]:
    project = owned_project(db, user, project_id, lock=True)
    if project.status == "DELETING" or db.scalar(
        select(ProcessingJob.id).where(
            ProcessingJob.project_id == project_id,
            ProcessingJob.status.in_(["QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"]),
        )
    ):
        raise HTTPException(409, "Wait for the current operation to finish.")
    if not db.scalar(select(Transcript.id).where(Transcript.project_id == project_id)):
        raise HTTPException(409, "Analyze your source video first.")
    job = ProcessingJob(
        id=uuid.uuid4(), project_id=project_id, user_id=project.user_id, job_type="highlights"
    )
    db.add(job)
    project.status = "FINDING_HIGHLIGHTS"
    db.commit()
    dispatch(db, job)
    return {"job_id": str(job.id)}


@router.get("/projects/{project_id}/highlights")
def highlights(project_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, object]:
    project = owned_project(db, user, project_id)
    items = db.scalars(
        select(ClipCandidate)
        .where(ClipCandidate.project_id == project_id, ClipCandidate.selected.is_(True))
        .order_by(ClipCandidate.rank)
    )
    return {
        "requested": project.processing_config.get("clip_count", 10),
        "candidates_evaluated": db.scalar(
            select(func.count())
            .select_from(ClipCandidate)
            .where(ClipCandidate.project_id == project_id)
        )
        or 0,
        "items": [
            {
                "id": str(c.id),
                "start_ms": c.start_ms,
                "end_ms": c.end_ms,
                "title": c.title,
                "text": c.transcript_text,
                "score": c.score_total,
                "breakdown": c.score_breakdown,
                "reason": c.reason,
                "rank": c.rank,
            }
            for c in items
        ],
    }
