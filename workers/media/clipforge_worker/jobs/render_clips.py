import uuid
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig, RenderConfig
from clipforge_api.config import settings
from clipforge_api.db import SessionLocal
from clipforge_api.models import (
    Analysis,
    Clip,
    MediaAsset,
    ProcessingJob,
    Project,
    Scene,
    Transcript,
)
from clipforge_api.services.usage import storage_check
from clipforge_api.storage import s3
from sqlalchemy import select

from clipforge_worker.celery_app import celery
from clipforge_worker.jobs.runtime import run_job, succeed
from clipforge_worker.media.probe import probe
from clipforge_worker.reframing.planner import plan_crop
from clipforge_worker.rendering.renderer import render
from clipforge_worker.transcription.base import Segment
from clipforge_worker.vision.face_detector import FaceFrame


@celery.task(name="clipforge.render", soft_time_limit=14400, time_limit=14500)
def render_clips(job_id: str) -> None:
    with run_job(job_id, "RENDERING") as context:
        if context is None:
            return
        with SessionLocal() as db:
            job = db.get(ProcessingJob, context.id)
            assert job
            project = db.get(Project, job.project_id)
            assert project and project.source_asset_id
            source_asset = db.get(MediaAsset, project.source_asset_id)
            assert source_asset
            key, project_id, owner = source_asset.storage_key, project.id, project.user_id
            clip_ids = [uuid.UUID(value) for value in job.parameters["clip_ids"]]
            transcript = db.scalar(select(Transcript).where(Transcript.project_id == project_id))
            analysis = db.scalar(select(Analysis).where(Analysis.project_id == project_id))
            segments = (
                [Segment.model_validate(s) for s in transcript.segments] if transcript else []
            )
            faces = [FaceFrame.model_validate(f) for f in analysis.face_frames] if analysis else []
            cuts = [
                s.start_ms / 1000
                for s in db.scalars(select(Scene).where(Scene.project_id == project_id))
            ]
        with TemporaryDirectory(prefix=f"clipforge-render-{job_id}-") as directory:
            root = Path(directory)
            source = root / "source"
            context.progress("Reading original media", 2)
            s3().download_file(settings().s3_bucket, key, str(source))
            info = probe(source)
            for index, clip_id in enumerate(clip_ids):
                with SessionLocal() as db:
                    clip = db.get(Clip, clip_id)
                    assert clip and clip.project_id == project_id
                    if clip.rendered_revision == clip.revision and clip.output_asset_id:
                        continue
                    revision = clip.revision
                    config = RenderConfig.model_validate(clip.render_config)
                    caption = CaptionConfig.model_validate(clip.caption_config)
                    overlay = OverlayConfig.model_validate(clip.overlay_config)
                    start, end = clip.start_ms / 1000, clip.end_ms / 1000
                    if end > info.duration_ms / 1000 + 0.1:
                        raise ValueError("Clip ends beyond the source duration.")
                    anchor = (
                        (config.anchor_x, config.anchor_y)
                        if config.anchor_x is not None and config.anchor_y is not None
                        else None
                    )
                    plan = plan_crop(
                        info.width,
                        info.height,
                        clip.aspect_ratio,
                        start,
                        end,
                        faces,
                        cuts,
                        config.crop_mode,
                        anchor,
                        config.zoom,
                        eye_line=config.eye_line,
                        headroom=config.headroom,
                        subject=config.subject,
                        lock_camera=config.lock_camera,
                        minimum_hold=config.minimum_crop_hold_seconds,
                        horizontal_dead_zone=config.horizontal_dead_zone,
                        vertical_dead_zone=config.vertical_dead_zone,
                        sentence_boundaries=[s.end for s in segments],
                    )
                    clip.status = "RENDERING"
                    clip.crop_plan = plan.model_dump()
                    db.commit()
                    if (
                        anchor is None
                        and plan.quality.get("validated")
                        and (
                            plan.quality["score"] < config.minimum_framing_score
                            or plan.quality.get("clipped_fraction", 0) > 0.2
                        )
                    ):
                        raise ValueError(
                            f"Framing needs review (score {plan.quality['score']}/100). Reduce zoom, choose a subject, or set a manual crop before rendering."
                        )
                stage = f"Rendering clip {index + 1} of {len(clip_ids)}"
                percent = 5 + round(index / len(clip_ids) * 90)
                context.progress(stage, percent)
                output, thumbnail = root / "output.mp4", root / "thumbnail.jpg"
                logo_path = None
                if overlay.logo_enabled and overlay.logo_asset_id:
                    with SessionLocal() as db:
                        logo_asset = db.get(MediaAsset, overlay.logo_asset_id)
                        if (
                            not logo_asset
                            or logo_asset.project_id != project_id
                            or logo_asset.user_id != owner
                            or logo_asset.type != "BRAND_LOGO"
                        ):
                            raise ValueError(
                                "The project logo is unavailable. Apply a brand kit again."
                            )
                        logo_path = root / "logo.png"
                        s3().download_file(
                            settings().s3_bucket, logo_asset.storage_key, str(logo_path)
                        )
                render(
                    source,
                    output,
                    thumbnail,
                    plan,
                    start,
                    end,
                    segments,
                    caption,
                    overlay,
                    config,
                    partial(context.progress, stage, percent),
                    logo=logo_path,
                )
                rendered = probe(output)
                if abs(rendered.duration_ms - round((end - start) * 1000)) > 250:
                    raise ValueError("Rendered duration did not match the requested clip.")
                scale = 0.5 if config.quality == "Draft" else 1
                if (rendered.width, rendered.height) != (
                    int(plan.output_width * scale) // 2 * 2,
                    int(plan.output_height * scale) // 2 * 2,
                ):
                    raise ValueError("Rendered dimensions did not match the crop plan.")
                context.progress(f"Saving clip {index + 1}", percent + 1)
                # Stable per-revision keys make retries overwrite the same objects safely.
                prefix = f"users/{owner}/projects/{project_id}/clips/{clip_id}/v{revision}"
                with SessionLocal() as db:
                    for path, suffix, mime in [
                        (output, "output.mp4", "video/mp4"),
                        (thumbnail, "thumbnail.jpg", "image/jpeg"),
                    ]:
                        storage_key = f"{prefix}/{suffix}"
                        if not db.scalar(
                            select(MediaAsset.id).where(MediaAsset.storage_key == storage_key)
                        ):
                            storage_check(db, owner, path.stat().st_size)
                        s3().upload_file(
                            str(path),
                            settings().s3_bucket,
                            storage_key,
                            ExtraArgs={"ContentType": mime},
                        )
                        asset = db.scalar(
                            select(MediaAsset).where(MediaAsset.storage_key == storage_key)
                        )
                        if not asset:
                            asset = MediaAsset(
                                id=uuid.uuid4(),
                                user_id=owner,
                                project_id=project_id,
                                type="CLIP" if mime == "video/mp4" else "THUMBNAIL",
                                storage_key=storage_key,
                                original_filename=suffix,
                                mime_type=mime,
                                size_bytes=path.stat().st_size,
                            )
                            db.add(asset)
                        if mime == "video/mp4":
                            asset.width, asset.height, asset.duration_ms = (
                                rendered.width,
                                rendered.height,
                                rendered.duration_ms,
                            )
                            asset.fps, asset.codec = rendered.fps, rendered.codec
                            output_id = asset.id
                        else:
                            thumbnail_id = asset.id
                    current = db.get(Clip, clip_id)
                    assert current
                    current.output_asset_id, current.thumbnail_asset_id = output_id, thumbnail_id
                    current.rendered_revision, current.status = revision, "COMPLETED"
                    db.commit()
        succeed(context, "COMPLETED")
