from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from clipforge_api.config import settings
from clipforge_api.models import MediaAsset, ProcessingJob, Project, User
from clipforge_api.security import CurrentUser, Db

router = APIRouter(tags=["Operations"])


@router.get("/operations")
def operations(db: Db, user: CurrentUser) -> dict:
    if not user.is_admin:
        raise HTTPException(403, "Administrator access required.")
    counts = dict(db.execute(select(ProcessingJob.status, func.count()).group_by(ProcessingJob.status)).all())
    jobs = db.scalars(select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(100))
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "projects": db.scalar(select(func.count()).select_from(Project)),
        "storage_bytes": db.scalar(select(func.sum(MediaAsset.size_bytes))) or 0,
        "job_counts": counts,
        "retention_days": settings().media_retention_days,
        "jobs": [{"id": str(j.id), "project_id": str(j.project_id), "type": j.job_type,
                  "status": j.status, "progress": j.progress, "stage": j.stage,
                  "error": j.error_message, "created_at": j.created_at.isoformat(),
                  "heartbeat_at": j.heartbeat_at.isoformat() if j.heartbeat_at else None} for j in jobs],
    }
