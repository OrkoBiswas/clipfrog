import uuid
from copy import deepcopy
from typing import Literal

from clipforge_worker.highlights.candidates import complete_clip_end
from clipforge_worker.transcription.base import Segment
from clipforge_worker.transcription.caption_timing import speech_captions
from clipforge_worker.transcription.export import subtitles
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from clipforge_api.clip_schemas import CaptionConfig, ClipInput, GenerateClips, Ratio, RenderConfig
from clipforge_api.config import settings
from clipforge_api.models import (
    Analysis,
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
from clipforge_api.services.collage import collage_faces
from clipforge_api.services.usage import reserve
from clipforge_api.storage import s3

router = APIRouter(tags=["Clips"])


def project_render_config(project: Project, explicit: dict | None = None) -> RenderConfig:
    processing = project.processing_config
    try:
        config = RenderConfig.model_validate(
            {
                "quality": processing.get("quality", "Standard"),
                "crop_mode": processing.get("crop_mode", "STATIC_SUBJECT_LOCK"),
                **(processing.get("render_config") or {}),
                **(explicit or {}),
            }
        )
        if explicit is None and config.layout != "single":
            config = config.model_copy(update={"layout": "auto", "panels": []})
        return config
    except ValidationError as exc:
        raise HTTPException(422, "The layout settings are incompatible with this project.") from exc


@router.post("/projects/{project_id}/editor-preview")
def editor_preview(project_id: uuid.UUID, body: ClipInput, db: Db, user: CurrentUser) -> dict:
    from clipforge_worker.reframing.planner import plan_composition
    from clipforge_worker.vision.face_detector import FaceFrame

    project = owned_project(db, user, project_id)
    validate_source(project, body, db)
    source = db.get(MediaAsset, project.source_asset_id)
    assert source and source.width and source.height
    analysis = db.scalar(select(Analysis).where(Analysis.project_id == project_id))
    transcript = db.scalar(select(Transcript).where(Transcript.project_id == project_id))
    cfg = body.render_config
    frames = [FaceFrame.model_validate(f) for f in analysis.face_frames] if analysis else []
    if cfg.layout == "auto":
        original_url = s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings().s3_bucket, "Key": source.storage_key},
            ExpiresIn=900,
        )
        try:
            frames = collage_faces(
                db, project_id, original_url, body.start_ms / 1000, body.end_ms / 1000
            )
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
    plan = plan_composition(
        source.width,
        source.height,
        body.aspect_ratio,
        body.start_ms / 1000,
        body.end_ms / 1000,
        frames,
        [
            scene.start_ms / 1000
            for scene in db.scalars(select(Scene).where(Scene.project_id == project_id))
        ],
        config=cfg,
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
        for panel in result["panels"]:
            panel["subjects"] = []
            panel["quality"].pop("samples", None)
        for scene in result["scenes"]:
            scene["subjects"] = []
            scene["quality"].pop("samples", None)
            for panel in scene["panels"]:
                panel["subjects"] = []
                panel["quality"].pop("samples", None)
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
        "caption_segments": [
            segment.model_dump()
            for segment in speech_captions(
                [Segment.model_validate(s) for s in transcript.segments] if transcript else [],
                body.start_ms / 1000,
                body.end_ms / 1000,
                body.caption_config.cues,
            )
        ],
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
    owned_project(db, user, project_id)
    clip = owned_clip(project_id, clip_id, db)
    transcript = db.scalar(select(Transcript).where(Transcript.project_id == project_id))
    timed = speech_captions(
        [Segment.model_validate(s) for s in transcript.segments] if transcript else [],
        clip.start_ms / 1000,
        clip.end_ms / 1000,
        CaptionConfig.model_validate(clip.caption_config).cues,
    )
    segments = [
        segment.model_copy(
            update={
                "start": segment.start - clip.start_ms / 1000,
                "end": segment.end - clip.start_ms / 1000,
            }
        )
        for segment in timed
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
    transcript = db.scalar(select(Transcript).where(Transcript.project_id == project_id))
    source = db.get(MediaAsset, project.source_asset_id) if project.source_asset_id else None
    segments = (
        [Segment.model_validate(segment) for segment in transcript.segments] if transcript else []
    )
    endings: dict[uuid.UUID, int] = {}
    for candidate in candidates:
        ending = (
            complete_clip_end(
                segments,
                candidate.start_ms / 1000,
                candidate.end_ms / 1000,
                source.duration_ms / 1000,
            )
            if segments and source and source.duration_ms
            else candidate.end_ms / 1000
        )
        if ending is None:
            raise HTTPException(
                422,
                "This highlight has no complete ending nearby. Find highlights again to choose finished moments.",
            )
        endings[candidate.id] = round(ending * 1000)
    for candidate in candidates:
        for ratio in dict.fromkeys(body.ratios):
            clip = Clip(
                id=uuid.uuid4(),
                project_id=project_id,
                candidate_id=candidate.id,
                title=candidate.title,
                start_ms=candidate.start_ms,
                end_ms=endings[candidate.id],
                aspect_ratio=ratio,
                highlight_score=candidate.score_total,
                caption_config={
                    "enabled": cfg.get("captions", True),
                    "style": cfg.get("caption_style", "Clean"),
                    **project.brand_config.get("captions", {}),
                    **(cfg.get("caption_config") or {}),
                },
                overlay_config=project.brand_config.get("overlay", {}),
                render_config=project_render_config(project).model_dump(mode="json"),
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
            "start_ms": round(s.start * 1000) - clip.start_ms,
            "end_ms": round(s.end * 1000) - clip.start_ms,
            "text": s.text,
        }
        for s in speech_captions(
            [Segment.model_validate(segment) for segment in transcript.segments],
            clip.start_ms / 1000,
            clip.end_ms / 1000,
        )
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
    data["render_config"] = project_render_config(
        project, explicit.get("render_config")
    ).model_dump(mode="json")
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
    render_config: RenderConfig | None = None


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
            if (
                body.aspect_ratio is None
                and body.caption_config is None
                and body.render_config is None
            ):
                raise HTTPException(422, "Choose a ratio, caption style, or layout to apply.")
            if body.aspect_ratio is not None:
                clip.aspect_ratio = body.aspect_ratio
            if body.caption_config is not None:
                clip.caption_config = {
                    **body.caption_config.model_dump(mode="json"),
                    "cues": clip.caption_config.get("cues"),
                }
            if body.render_config is not None:
                try:
                    clip.render_config = RenderConfig.model_validate(
                        {
                            **clip.render_config,
                            **body.render_config.model_dump(mode="json", exclude_unset=True),
                        }
                    ).model_dump(mode="json")
                except ValidationError as exc:
                    raise HTTPException(
                        422, "The layout settings are incompatible with a selected clip."
                    ) from exc
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
