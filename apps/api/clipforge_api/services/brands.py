import uuid
from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from clipforge_api.config import settings
from clipforge_api.models import BrandKit, Clip, MediaAsset, Project
from clipforge_api.services.usage import storage_check
from clipforge_api.storage import s3


def apply_brand(
    db: Session, project: Project, kit_id: uuid.UUID | None, existing: bool = False
) -> None:
    snapshot = {}
    if kit_id:
        kit = db.scalar(
            select(BrandKit)
            .where(BrandKit.id == kit_id, BrandKit.user_id == project.user_id)
            .with_for_update()
        )
        if not kit:
            raise HTTPException(404, "Brand kit not found.")
        snapshot = {"id": str(kit.id), "name": kit.name, **deepcopy(kit.config)}
        overlay = snapshot.setdefault("overlay", {})
        overlay["brand_kit_id"] = str(kit.id)
        overlay["logo_asset_id"] = None
        if kit.logo_key:
            storage_check(db, project.user_id, kit.logo_size)
            identifier = uuid.uuid4()
            key = f"users/{project.user_id}/projects/{project.id}/brands/{identifier}.png"
            s3().copy_object(
                Bucket=settings().s3_bucket,
                Key=key,
                CopySource={"Bucket": settings().s3_bucket, "Key": kit.logo_key},
            )
            db.add(
                MediaAsset(
                    id=identifier,
                    user_id=project.user_id,
                    project_id=project.id,
                    type="BRAND_LOGO",
                    storage_key=key,
                    original_filename="logo.png",
                    mime_type="image/png",
                    size_bytes=kit.logo_size,
                )
            )
            overlay["logo_asset_id"] = str(identifier)
    project.brand_config = snapshot
    project.processing_config = {
        **project.processing_config,
        "brand_kit_id": str(kit_id) if kit_id else None,
    }
    if snapshot:
        project.processing_config = {
            **project.processing_config,
            "ratios": snapshot.get("ratios", project.processing_config.get("ratios", ["9:16"])),
            "captions": snapshot["captions"]["enabled"],
            "caption_style": snapshot["captions"]["style"],
        }
    if existing:
        for clip in db.scalars(select(Clip).where(Clip.project_id == project.id)):
            # Preserve edited transcript text and clip-specific opening titles.
            if snapshot:
                clip.caption_config = {
                    **snapshot["captions"],
                    "cues": clip.caption_config.get("cues"),
                }
                clip.overlay_config = {
                    **snapshot["overlay"],
                    "title": clip.overlay_config.get("title", "")
                    or snapshot["overlay"].get("title", ""),
                }
            else:
                clip.overlay_config = {
                    **clip.overlay_config,
                    "brand_kit_id": None,
                    "logo_asset_id": None,
                }
            clip.revision += 1
            clip.status = "DRAFT"


def validate_logo(db: Session, project: Project, asset_id: uuid.UUID | None) -> None:
    if asset_id:
        asset = db.get(MediaAsset, asset_id)
        if (
            not asset
            or asset.project_id != project.id
            or asset.user_id != project.user_id
            or asset.type != "BRAND_LOGO"
        ):
            raise HTTPException(404, "Project logo not found.")
