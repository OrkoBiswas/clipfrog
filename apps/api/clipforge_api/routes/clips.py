import uuid
from copy import deepcopy
from typing import Literal

from clipforge_worker.transcription.base import Segment
from clipforge_worker.transcription.export import subtitles
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from clipforge_api.clip_schemas import CaptionConfig, ClipInput, GenerateClips, Ratio
from clipforge_api.config import settings
from clipforge_api.models import (
    Analysis,
    CaptionLibrary,
    Clip,
    ClipCandidate,
    MediaAsset,
    ProcessingJob,
    Project,
    Scene,
    Transcript,
)
from clipforge_api.routes.jobs import dispatch
from clipforge_api.routes.projects import owned_project
from clipforge_api.security import CurrentUser, Db
from clipforge_api.services.brands import validate_logo
from clipforge_api.services.usage import reserve
from clipforge_api.storage import s3

router = APIRouter(tags=["Clips"])


def default_captions(db: Db, owner: uuid.UUID) -> dict:
    from clipforge_api.services.caption_templates import TEMPLATES

    library = db.get(CaptionLibrary, owner)
    if not library:
        return {}
    return next(
        (
            item["config"]
            for item in [*TEMPLATES, *library.data.get("custom", [])]
            if item["id"] == library.data.get("default")
        ),
        {},
    )


@router.post("/projects/{project_id}/editor-preview")
def editor_preview(project_id: uuid.UUID, body: ClipInput, db: Db, user: CurrentUser) -> dict:
    from clipforge_worker.reframing.planner import plan_crop
    from clipforge_worker.vision.face_detector import FaceFrame

    project = owned_project(db, user, project_id)
    validate_source(project, body, db)
    source = db.get(MediaAsset, project.source_asset_id)
    assert source and source.width and source.height
    analysis = db.scalar(select(Analysis).where(Analysis.project_id == project_id))
    transcript = db.scalar(select(Transcript).where(Transcript.project_id == project_id))
    cfg = body.render_config
    plan = plan_crop(
        source.width,
        source.height,
        body.aspect_ratio,
        body.start_ms / 1000,
        body.end_ms / 1000,
        [FaceFrame.model_validate(f) for f in analysis.face_frames] if analysis else [],
        [
            scene.start_ms / 1000
            for scene in db.scalars(select(Scene).where(Scene.project_id == project_id))
        ],
        cfg.crop_mode,
        (cfg.anchor_x, cfg.anchor_y)
        if cfg.anchor_x is not None and cfg.anchor_y is not None
        else None,
        cfg.zoom,
        eye_line=cfg.eye_line,
        headroom=cfg.headroom,
        subject=cfg.subject,
        lock_camera=cfg.lock_camera,
        minimum_hold=cfg.minimum_crop_hold_seconds,
        horizontal_dead_zone=cfg.horizontal_dead_zone,
        vertical_dead_zone=cfg.vertical_dead_zone,
        sentence_boundaries=[s["end"] for s in transcript.segments] if transcript else [],
    )

    def signed(key: str) -> str:
        return s3(public=True).generate_presigned_url(
            "get_object", Params={"Bucket": settings().s3_bucket, "Key": key}, ExpiresIn=900
        )

    logo = (
        db.get(MediaAsset, body.overlay_config.logo_asset_id)
        if body.overlay_config.logo_asset_id
        else None
    )
    result = plan.model_dump()
    if not user.is_admin:
        result["subjects"] = []
        result["quality"].pop("samples", None)
    return {
        "plan": result,
        "source_url": signed(source.storage_key),
        "logo_url": signed(logo.storage_key) if logo else None,
        "segments": [
            s
            for s in transcript.segments
            if s["end"] * 1000 > body.start_ms and s["start"] * 1000 < body.end_ms
        ]
        if transcript
        else [],
        "debug_allowed": user.is_admin,
    }


@router.post("/projects/{project_id}/render-preview", status_code=202)
def render_preview(project_id: uuid.UUID, body: ClipInput, db: Db, user: CurrentUser) -> dict:
    project = idle_project(project_id, db, user)
    validate_source(project, body, db)
    data = body.model_dump(mode="json")
    data["end_ms"] = min(body.end_ms, body.start_ms + 4000)
    clip = Clip(id=uuid.uuid4(), project_id=project_id, is_preview=True, **data)
    db.add(clip)
    return enqueue(project, [clip], db)


@router.post("/projects/{project_id}/export", status_code=202)
def export_project(project_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, str]:
    project = idle_project(project_id, db, user)
    clips = list(
        db.scalars(
            select(Clip)
            .where(
                Clip.project_id == project_id,
                Clip.output_asset_id.is_not(None),
                Clip.is_preview.is_(False),
            )
            .limit(101)
        )
    )
    if not clips or len(clips) > 100:
        raise HTTPException(422, "Export requires 1 to 100 rendered clips.")
    job = ProcessingJob(
        id=uuid.uuid4(),
        project_id=project_id,
        user_id=project.user_id,
        job_type="export",
        queue="maintenance",
        parameters={"clip_ids": [str(c.id) for c in clips]},
    )
    db.add(job)
    project.status = "EXPORTING"
    db.commit()
    dispatch(db, job)
    return {"job_id": str(job.id)}


@router.get("/projects/{project_id}/export/{job_id}")
def export_download(
    project_id: uuid.UUID, job_id: uuid.UUID, db: Db, user: CurrentUser
) -> dict[str, str]:
    owned_project(db, user, project_id)
    asset = db.get(MediaAsset, job_id)
    if not asset or asset.project_id != project_id or asset.type != "ARCHIVE":
        raise HTTPException(409, "The archive is not available yet.")
    return {
        "url": s3(public=True).generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings().s3_bucket,
                "Key": asset.storage_key,
                "ResponseContentDisposition": 'attachment; filename="clips.zip"',
            },
            ExpiresIn=900,
        )
    }


@router.get("/projects/{project_id}/clips/{clip_id}/subtitles")
def export_captions(
    project_id: uuid.UUID, clip_id: uuid.UUID, db: Db, user: CurrentUser
) -> Response:
    cues = caption_cues(project_id, clip_id, db, user)
    segments = [
        Segment(
            start=float(str(c["start_ms"])) / 1000,
            end=float(str(c["end_ms"])) / 1000,
            text=str(c["text"]),
        )
        for c in cues
    ]
    return Response(
        subtitles(segments),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="clip-{clip_id}.srt"'},
    )


def idle_project(project_id: uuid.UUID, db: Db, user: CurrentUser) -> Project:
    project = owned_project(db, user, project_id, lock=True)
    if project.status == "DELETING" or db.scalar(
        select(ProcessingJob.id).where(
            ProcessingJob.project_id == project_id,
            ProcessingJob.status.in_(["QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"]),
        )
    ):
        raise HTTPException(409, "Wait for the current operation to finish.")
    return project


def owned_clip(project_id: uuid.UUID, clip_id: uuid.UUID, db: Db) -> Clip:
    clip = db.get(Clip, clip_id)
    if not clip or clip.project_id != project_id:
        raise HTTPException(404, "Clip not found.")
    return clip


def enqueue(project: Project, clips: list[Clip], db: Db) -> dict[str, object]:
    job = ProcessingJob(
        id=uuid.uuid4(),
        project_id=project.id,
        user_id=project.user_id,
        job_type="render",
        queue="render",
        parameters={"clip_ids": [str(c.id) for c in clips]},
    )
    db.add(job)
    reserve(
        db,
        job,
        "render_minutes",
        sum(
            (c.end_ms - c.start_ms) / 60000
            for c in clips
            if c.rendered_revision != c.revision or not c.output_asset_id
        ),
    )
    project.status = "RENDERING"
    db.commit()
    dispatch(db, job)
    return {"job_id": str(job.id), "clip_ids": [str(c.id) for c in clips]}


@router.post("/projects/{project_id}/clips/generate", status_code=202)
def generate(
    project_id: uuid.UUID, body: GenerateClips, db: Db, user: CurrentUser
) -> dict[str, object]:
    project = idle_project(project_id, db, user)
    candidates = list(
        db.scalars(
            select(ClipCandidate).where(
                ClipCandidate.project_id == project_id,
                ClipCandidate.id.in_(set(body.candidate_ids)),
            )
        )
    )
    if len(candidates) != len(set(body.candidate_ids)):
        raise HTTPException(404, "Candidate not found.")
    if len(candidates) * len(set(body.ratios)) > 100:
        raise HTTPException(422, "Render at most 100 outputs in one batch.")
    clips = []
    cfg = project.processing_config
    for candidate in candidates:
        for ratio in dict.fromkeys(body.ratios):
            clip = Clip(
                id=uuid.uuid4(),
                project_id=project_id,
                candidate_id=candidate.id,
                title=candidate.title,
                start_ms=candidate.start_ms,
                end_ms=candidate.end_ms,
                aspect_ratio=ratio,
                highlight_score=candidate.score_total,
                caption_config={
                    "enabled": cfg.get("captions", True),
                    "style": cfg.get("caption_style", "Clean"),
                    **default_captions(db, project.user_id),
                    **project.brand_config.get("captions", {}),
                    **(cfg.get("caption_config") or {}),
                },
                overlay_config=project.brand_config.get("overlay", {}),
                render_config={
                    "quality": cfg.get("quality", "Standard"),
                    "crop_mode": cfg.get("crop_mode", "STATIC_SUBJECT_LOCK"),
                },
            )
            db.add(clip)
            clips.append(clip)
    return enqueue(project, clips, db)


@router.get("/projects/{project_id}/clips")
def list_clips(project_id: uuid.UUID, db: Db, user: CurrentUser) -> list[dict[str, object]]:
    owned_project(db, user, project_id)
    return [
        serialize(c)
        for c in db.scalars(
            select(Clip)
            .where(Clip.project_id == project_id, Clip.is_preview.is_(False))
            .order_by(Clip.created_at.desc())
        )
    ]


def serialize(clip: Clip) -> dict[str, object]:
    return {
        name: getattr(clip, name)
        for name in [
            "id",
            "title",
            "start_ms",
            "end_ms",
            "aspect_ratio",
            "status",
            "highlight_score",
            "crop_plan",
            "caption_config",
            "overlay_config",
            "render_config",
            "revision",
            "rendered_revision",
            "output_asset_id",
        ]
    }


@router.get("/projects/{project_id}/clips/{clip_id}/captions")
def caption_cues(
    project_id: uuid.UUID, clip_id: uuid.UUID, db: Db, user: CurrentUser
) -> list[dict[str, object]]:
    owned_project(db, user, project_id)
    clip = owned_clip(project_id, clip_id, db)
    if clip.caption_config.get("cues") is not None:
        return list(clip.caption_config["cues"])
    transcript = db.scalar(select(Transcript).where(Transcript.project_id == project_id))
    if not transcript:
        return []
    return [
        {
            "start_ms": max(0, round(s["start"] * 1000) - clip.start_ms),
            "end_ms": min(clip.end_ms, round(s["end"] * 1000)) - clip.start_ms,
            "text": s["text"],
        }
        for s in transcript.segments
        if s["end"] * 1000 > clip.start_ms and s["start"] * 1000 < clip.end_ms
    ]


def validate_source(project: Project, body: ClipInput, db: Db) -> None:
    validate_logo(db, project, body.overlay_config.logo_asset_id)
    asset = db.get(MediaAsset, project.source_asset_id) if project.source_asset_id else None
    if not asset or not asset.duration_ms or body.end_ms > asset.duration_ms:
        raise HTTPException(422, "The clip must fit inside a validated source video.")


@router.post("/projects/{project_id}/clips", status_code=201)
def create(project_id: uuid.UUID, body: ClipInput, db: Db, user: CurrentUser) -> dict[str, object]:
    project = idle_project(project_id, db, user)
    validate_source(project, body, db)
    data = body.model_dump(mode="json")
    explicit = body.model_dump(mode="json", exclude_unset=True)
    data["caption_config"] = {**data["caption_config"], **default_captions(db, project.user_id)}
    if "aspect_ratio" not in explicit and project.brand_config.get("ratios"):
        data["aspect_ratio"] = project.brand_config["ratios"][0]
    for field, brand_field in [("caption_config", "captions"), ("overlay_config", "overlay")]:
        data[field] = {
            **data[field],
            **project.brand_config.get(brand_field, {}),
            **(
                (project.processing_config.get("caption_config") or {})
                if field == "caption_config"
                else {}
            ),
            **explicit.get(field, {}),
        }
    clip = Clip(project_id=project_id, **data)
    db.add(clip)
    db.commit()
    return serialize(clip)


class ClipActions(BaseModel):
    clip_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: Literal["duplicate", "delete", "render", "update"]
    aspect_ratio: Ratio | None = None
    caption_config: CaptionConfig | None = None


@router.post("/projects/{project_id}/clip-actions")
def clip_actions(project_id: uuid.UUID, body: ClipActions, db: Db, user: CurrentUser) -> dict:
    project = idle_project(project_id, db, user)
    clips = [owned_clip(project_id, identifier, db) for identifier in dict.fromkeys(body.clip_ids)]
    if any(clip.is_preview for clip in clips):
        raise HTTPException(422, "Preview clips cannot be managed as saved clips.")
    if body.action == "render":
        return enqueue(project, clips, db)
    result = []
    for clip in clips:
        if body.action == "duplicate":
            copy = Clip(
                project_id=project_id,
                title=(clip.title[:150] + " (copy)"),
                start_ms=clip.start_ms,
                end_ms=clip.end_ms,
                aspect_ratio=clip.aspect_ratio,
                caption_config=deepcopy(clip.caption_config),
                overlay_config=deepcopy(clip.overlay_config),
                render_config=deepcopy(clip.render_config),
            )
            db.add(copy)
            db.flush()
            result.append(str(copy.id))
        elif body.action == "delete":
            # Render revisions use a clip-specific prefix. Retain source and brand assets.
            prefix = f"users/{project.user_id}/projects/{project.id}/clips/{clip.id}/"
            assets = list(
                db.scalars(
                    select(MediaAsset).where(
                        MediaAsset.project_id == project_id,
                        MediaAsset.storage_key.startswith(prefix),
                    )
                )
            )
            for asset in assets:
                s3().delete_object(Bucket=settings().s3_bucket, Key=asset.storage_key)
            db.delete(clip)
            db.flush()
            for asset in assets:
                db.delete(asset)
        else:
            if body.aspect_ratio is None and body.caption_config is None:
                raise HTTPException(422, "Choose a ratio or caption style to apply.")
            if body.aspect_ratio is not None:
                clip.aspect_ratio = body.aspect_ratio
            if body.caption_config is not None:
                clip.caption_config = {
                    **body.caption_config.model_dump(mode="json"),
                    "cues": clip.caption_config.get("cues"),
                }
            clip.revision += 1
            clip.status = "DRAFT"
    db.commit()
    return {"clip_ids": result, "affected": len(clips)}


@router.put("/projects/{project_id}/clips/{clip_id}")
def update(
    project_id: uuid.UUID, clip_id: uuid.UUID, body: ClipInput, db: Db, user: CurrentUser
) -> dict[str, object]:
    project = idle_project(project_id, db, user)
    clip = owned_clip(project_id, clip_id, db)
    validate_source(project, body, db)
    for name, value in body.model_dump(mode="json").items():
        setattr(clip, name, value)
    clip.revision += 1
    clip.status = "DRAFT"
    db.commit()
    return serialize(clip)


@router.post("/projects/{project_id}/clips/{clip_id}/render", status_code=202)
def rerender(
    project_id: uuid.UUID, clip_id: uuid.UUID, db: Db, user: CurrentUser
) -> dict[str, object]:
    project = idle_project(project_id, db, user)
    clip = owned_clip(project_id, clip_id, db)
    return enqueue(project, [clip], db)


@router.get("/projects/{project_id}/clips/{clip_id}/media")
def media(
    project_id: uuid.UUID, clip_id: uuid.UUID, db: Db, user: CurrentUser, download: bool = False
) -> dict[str, str]:
    owned_project(db, user, project_id)
    clip = owned_clip(project_id, clip_id, db)
    asset = db.get(MediaAsset, clip.output_asset_id) if clip.output_asset_id else None
    if not asset:
        raise HTTPException(409, "Render this clip before previewing it.")
    params = {"Bucket": settings().s3_bucket, "Key": asset.storage_key}
    if download:
        params["ResponseContentDisposition"] = f'attachment; filename="clip-{clip.id}.mp4"'
    url = s3(public=True).generate_presigned_url("get_object", Params=params, ExpiresIn=900)
    return {"url": url}
