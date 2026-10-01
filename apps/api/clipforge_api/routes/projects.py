import uuid

from clipforge_worker.celery_app import celery
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, literal, or_, select

from clipforge_api.models import Clip, MediaAsset, ProcessingJob, Project, UsageLedger, User
from clipforge_api.schemas import ProjectInput, ProjectOut
from clipforge_api.security import CurrentUser, Db
from clipforge_api.services.brands import apply_brand

router = APIRouter(tags=["Projects"])


class BulkProjectDelete(BaseModel):
    project_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


def owned_project(
    db: Db, user: CurrentUser, project_id: uuid.UUID, *, lock: bool = False
) -> Project:
    query = select(Project).where(
        Project.id == project_id, or_(literal(user.is_admin), Project.user_id == user.id)
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    project = db.scalar(query)
    if not project:
        raise HTTPException(404, "Project not found.")
    return project


@router.get("/projects", response_model=list[ProjectOut])
def projects(db: Db, user: CurrentUser, offset: int = 0) -> list[ProjectOut]:
    rows = db.execute(
        select(Project, User.email)
        .join(User, Project.user_id == User.id)
        .where(or_(literal(user.is_admin), Project.user_id == user.id))
        .order_by(Project.created_at.desc())
        .offset(max(0, offset))
        .limit(100)
    )
    return [
        ProjectOut.model_validate(project).model_copy(
            update={"owner_email": email if user.is_admin else None}
        )
        for project, email in rows
    ]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create(body: ProjectInput, db: Db, user: CurrentUser) -> Project:
    project = Project(user_id=user.id, **body.model_dump(mode="json"))
    db.add(project)
    db.flush()
    if body.processing_config.brand_kit_id:
        apply_brand(db, project, body.processing_config.brand_kit_id)
        project.processing_config = body.processing_config.model_dump(mode="json")
    db.commit()
    return project


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get(project_id: uuid.UUID, db: Db, user: CurrentUser) -> Project:
    return owned_project(db, user, project_id)


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update(project_id: uuid.UUID, body: ProjectInput, db: Db, user: CurrentUser) -> Project:
    project = owned_project(db, user, project_id, lock=True)
    if project.status not in {
        "DRAFT",
        "UPLOADED",
        "READY_FOR_CLIPS",
        "FAILED",
        "COMPLETED",
        "CANCELED",
    }:
        raise HTTPException(409, "Wait for processing to finish before changing this project.")
    previous_brand = project.processing_config.get("brand_kit_id")
    for key, value in body.model_dump(mode="json").items():
        setattr(project, key, value)
    if previous_brand != project.processing_config.get("brand_kit_id"):
        apply_brand(db, project, body.processing_config.brand_kit_id)
        project.processing_config = body.processing_config.model_dump(mode="json")
    db.commit()
    return project


@router.delete("/projects/{project_id}", status_code=204)
def delete(project_id: uuid.UUID, db: Db, user: CurrentUser) -> None:
    project = owned_project(db, user, project_id, lock=True)
    if db.scalar(
        select(func.count())
        .select_from(ProcessingJob)
        .where(
            ProcessingJob.project_id == project.id,
            ProcessingJob.status.in_(["RUNNING", "QUEUED", "RETRYING", "CANCEL_REQUESTED"]),
        )
    ):
        raise HTTPException(409, "Cancel active jobs before deleting this project.")
    if stage_project_deletion(db, project):
        db.commit()
        celery.send_task("clipforge.cleanup", args=[str(project.id)], queue="maintenance")
        return
    db.commit()


def stage_project_deletion(db: Db, project: Project) -> bool:
    has_assets = db.scalar(
        select(MediaAsset.id).where(MediaAsset.project_id == project.id).limit(1)
    )
    if has_assets:
        project.status = "DELETING"
        return True
    db.delete(project)
    return False


@router.post("/admin/projects/bulk-delete")
def bulk_delete_projects(
    body: BulkProjectDelete, db: Db, user: CurrentUser
) -> dict[str, list[str]]:
    if not user.is_admin:
        raise HTTPException(403, "Administrator access is required.")
    if len(set(body.project_ids)) != len(body.project_ids):
        raise HTTPException(422, "Each project can only be selected once.")

    projects = list(
        db.scalars(
            select(Project)
            .where(Project.id.in_(body.project_ids))
            .order_by(Project.id)
            .with_for_update()
        )
    )
    if len(projects) != len(body.project_ids):
        raise HTTPException(404, "One or more projects were not found.")
    if any(project.status == "DELETING" for project in projects):
        raise HTTPException(409, "A selected project is already being removed.")

    active_project_ids = set(
        db.scalars(
            select(ProcessingJob.project_id).where(
                ProcessingJob.project_id.in_(body.project_ids),
                ProcessingJob.status.in_(
                    ["QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"]
                ),
            )
        )
    )
    if active_project_ids:
        raise HTTPException(409, "Cancel active jobs before deleting selected projects.")

    deleted: list[str] = []
    queued_for_cleanup: list[str] = []
    for project in projects:
        if stage_project_deletion(db, project):
            queued_for_cleanup.append(str(project.id))
        else:
            deleted.append(str(project.id))
    db.commit()

    for project_id in queued_for_cleanup:
        celery.send_task("clipforge.cleanup", args=[project_id], queue="maintenance")

    return {"deleted": deleted, "queued_for_cleanup": queued_for_cleanup}


@router.get("/dashboard")
def dashboard(db: Db, user: CurrentUser) -> dict[str, object]:
    return {
        "clips_created": db.scalar(
            select(func.count())
            .select_from(Clip)
            .join(Project, Clip.project_id == Project.id)
            .where(or_(literal(user.is_admin), Project.user_id == user.id))
        )
        or 0,
        "projects": db.scalar(
            select(func.count())
            .select_from(Project)
            .where(or_(literal(user.is_admin), Project.user_id == user.id))
        )
        or 0,
        "storage_bytes": db.scalar(
            select(func.sum(MediaAsset.size_bytes)).where(
                or_(literal(user.is_admin), MediaAsset.user_id == user.id)
            )
        )
        or 0,
        "processing_jobs": db.scalar(
            select(func.count())
            .select_from(ProcessingJob)
            .where(
                or_(literal(user.is_admin), ProcessingJob.user_id == user.id),
                ProcessingJob.status.in_(["QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"]),
            )
        )
        or 0,
        "minutes_processed": db.scalar(
            select(func.sum(UsageLedger.quantity)).where(
                or_(literal(user.is_admin), UsageLedger.user_id == user.id),
                UsageLedger.metric == "input_minutes",
                UsageLedger.details["status"].as_string() == "COMPLETED",
            )
        )
        or 0,
    }
