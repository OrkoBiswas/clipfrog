import uuid
from typing import Literal

from clipforge_worker.highlights.heuristic_ranker import ENGINE_VERSION
from clipforge_worker.highlights.learning import valid_features
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from clipforge_api.config import settings
from clipforge_api.models import (
    ClipCandidate,
    HighlightFeedback,
    MediaAsset,
    ProcessingJob,
    Transcript,
)
from clipforge_api.routes.jobs import dispatch
from clipforge_api.routes.projects import owned_project
from clipforge_api.security import CurrentUser, Db
from clipforge_api.services.highlight_learning import fingerprint, learning_report
from clipforge_api.storage import s3

router = APIRouter(tags=["Highlights"])


class FeedbackInput(BaseModel):
    rating: Literal["good", "poor"] | None


@router.get("/projects/{project_id}/highlights/{candidate_id}/preview")
def preview_highlight(
    project_id: uuid.UUID, candidate_id: uuid.UUID, db: Db, user: CurrentUser
) -> dict:
    project = owned_project(db, user, project_id)
    candidate = db.get(ClipCandidate, candidate_id)
    if not candidate or candidate.project_id != project.id:
        raise HTTPException(404, "Highlight not found.")
    source = db.get(MediaAsset, project.source_asset_id) if project.source_asset_id else None
    if not source:
        raise HTTPException(409, "The source video is unavailable.")
    return {
        "url": s3(public=True).generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings().s3_bucket,
                "Key": source.storage_key,
            },
            ExpiresIn=900,
        ),
        "start_ms": candidate.start_ms,
        "end_ms": candidate.end_ms,
    }


@router.put("/projects/{project_id}/highlights/{candidate_id}/feedback")
def rate_highlight(
    project_id: uuid.UUID, candidate_id: uuid.UUID, body: FeedbackInput, db: Db, user: CurrentUser
) -> dict:
    project = owned_project(db, user, project_id, lock=True)
    candidate = db.get(ClipCandidate, candidate_id)
    if not candidate or candidate.project_id != project.id:
        raise HTTPException(404, "Highlight not found.")
    key = fingerprint(candidate)
    record = db.scalar(
        select(HighlightFeedback).where(
            HighlightFeedback.user_id == user.id,
            HighlightFeedback.project_id == project_id,
            HighlightFeedback.fingerprint == key,
        )
    )
    if body.rating is None:
        if record:
            db.delete(record)
    else:
        metadata = candidate.scoring_metadata
        if metadata.get("engine_version") != ENGINE_VERSION or not valid_features(
            metadata.get("features", {})
        ):
            raise HTTPException(
                409, "Find highlights again to rate moments with the current local engine."
            )
        if record:
            record.rating = body.rating
        else:
            db.add(
                HighlightFeedback(
                    user_id=user.id,
                    project_id=project_id,
                    fingerprint=key,
                    rating=body.rating,
                    start_ms=candidate.start_ms,
                    end_ms=candidate.end_ms,
                    features=dict(metadata["features"]),
                    engine_version=ENGINE_VERSION,
                )
            )
    db.commit()
    return {"rating": body.rating, "learning": learning_report(db, user.id)}


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
    items = list(
        db.scalars(
            select(ClipCandidate)
            .where(ClipCandidate.project_id == project_id, ClipCandidate.selected.is_(True))
            .order_by(ClipCandidate.rank)
        )
    )
    feedback = {
        row.fingerprint: row.rating
        for row in db.scalars(
            select(HighlightFeedback).where(
                HighlightFeedback.project_id == project_id, HighlightFeedback.user_id == user.id
            )
        )
    }
    latest = db.scalar(
        select(ProcessingJob)
        .where(
            ProcessingJob.project_id == project_id,
            ProcessingJob.job_type == "highlights",
            ProcessingJob.status == "SUCCEEDED",
        )
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )
    return {
        "engine": (latest.parameters.get("highlight_engine") if latest else None),
        "learning": learning_report(db, user.id),
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
                "feedback": feedback.get(fingerprint(c)),
                "can_rate": c.scoring_metadata.get("engine_version") == ENGINE_VERSION,
                "profile": c.scoring_metadata.get("content_profile", "general"),
            }
            for c in items
        ],
    }
