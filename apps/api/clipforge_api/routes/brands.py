import io
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig, Ratio
from clipforge_api.config import settings
from clipforge_api.models import BrandKit, User
from clipforge_api.security import CurrentUser, Db
from clipforge_api.services.usage import storage_check
from clipforge_api.storage import s3

router = APIRouter(tags=["Brand kits"])


class BrandInput(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"\S")
    captions: CaptionConfig = Field(default_factory=CaptionConfig)
    overlay: OverlayConfig = Field(default_factory=OverlayConfig)
    ratios: list[Ratio] = Field(default=["9:16"], min_length=1, max_length=8)
    platform_preset: Literal[
        "YouTube Shorts",
        "TikTok",
        "Instagram Reels",
        "Instagram Feed",
        "Facebook Reels",
        "Facebook Feed",
        "X",
        "LinkedIn",
        "YouTube Landscape",
        "Custom",
    ] = "Custom"

    def configuration(self) -> dict:
        value = self.model_dump(mode="json", exclude={"name"})
        value["overlay"]["brand_kit_id"] = None
        value["overlay"]["logo_asset_id"] = None
        value["captions"]["cues"] = None
        return value


def owned(kit_id: uuid.UUID, db: Db, user: CurrentUser) -> BrandKit:
    kit = db.scalar(
        select(BrandKit).where(BrandKit.id == kit_id, BrandKit.user_id == user.id).with_for_update()
    )
    if not kit:
        raise HTTPException(404, "Brand kit not found.")
    return kit


def serialize(kit: BrandKit) -> dict[str, object]:
    return {
        "id": str(kit.id),
        "name": kit.name,
        "config": kit.config,
        "has_logo": bool(kit.logo_key),
    }


@router.get("/brand-kits")
def list_kits(db: Db, user: CurrentUser) -> list[dict[str, object]]:
    return [
        serialize(kit)
        for kit in db.scalars(
            select(BrandKit).where(BrandKit.user_id == user.id).order_by(BrandKit.created_at.desc())
        )
    ]


@router.post("/brand-kits", status_code=201)
def create(body: BrandInput, db: Db, user: CurrentUser) -> dict[str, object]:
    db.execute(select(User).where(User.id == user.id).with_for_update())
    if (
        db.scalar(select(func.count()).select_from(BrandKit).where(BrandKit.user_id == user.id))
        or 0
    ) >= 20:
        raise HTTPException(422, "Keep at most 20 brand kits.")
    kit = BrandKit(user_id=user.id, name=body.name, config=body.configuration())
    db.add(kit)
    db.commit()
    return serialize(kit)


@router.put("/brand-kits/{kit_id}")
def update(kit_id: uuid.UUID, body: BrandInput, db: Db, user: CurrentUser) -> dict[str, object]:
    kit = owned(kit_id, db, user)
    kit.name, kit.config = body.name, body.configuration()
    db.commit()
    return serialize(kit)


@router.put("/brand-kits/{kit_id}/logo")
async def logo(kit_id: uuid.UUID, request: Request, db: Db, user: CurrentUser) -> dict[str, object]:
    kit = owned(kit_id, db, user)
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 2 * 1024**2:
            raise HTTPException(413, "Logo must be smaller than 2 MB.")
    try:
        with Image.open(io.BytesIO(payload), formats=["PNG", "JPEG", "WEBP"]) as source:
            if source.width * source.height > 4_000_000:
                raise ValueError("Logo exceeds four million pixels.")
            source.load()
            image = source.convert("RGBA")
            image.thumbnail((1024, 1024))
            output = io.BytesIO()
            image.save(output, format="PNG")
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(
            422, "Choose a valid PNG, JPEG or WebP logo up to four million pixels."
        ) from None
    key = f"users/{user.id}/brands/{kit_id}/{uuid.uuid4()}.png"
    storage_check(db, user.id, len(output.getvalue()) - kit.logo_size)
    s3().put_object(
        Bucket=settings().s3_bucket, Key=key, Body=output.getvalue(), ContentType="image/png"
    )
    previous = kit.logo_key
    kit.logo_key, kit.logo_size = key, len(output.getvalue())
    db.commit()
    if previous:
        s3().delete_object(Bucket=settings().s3_bucket, Key=previous)
    return serialize(kit)


@router.get("/brand-kits/{kit_id}/logo")
def preview_logo(kit_id: uuid.UUID, db: Db, user: CurrentUser) -> dict[str, str]:
    kit = owned(kit_id, db, user)
    if not kit.logo_key:
        raise HTTPException(404, "This kit has no logo.")
    return {
        "url": s3(public=True).generate_presigned_url(
            "get_object",
            Params={"Bucket": settings().s3_bucket, "Key": kit.logo_key},
            ExpiresIn=900,
        )
    }


@router.delete("/brand-kits/{kit_id}/logo", status_code=204)
def remove_logo(kit_id: uuid.UUID, db: Db, user: CurrentUser) -> None:
    kit = owned(kit_id, db, user)
    if kit.logo_key:
        s3().delete_object(Bucket=settings().s3_bucket, Key=kit.logo_key)
    kit.logo_key, kit.logo_size = None, 0
    db.commit()


class ApplyBrand(BaseModel):
    kit_id: uuid.UUID | None = None
    include_existing: bool = False


@router.put("/projects/{project_id}/brand")
def apply_to_project(project_id: uuid.UUID, body: ApplyBrand, db: Db, user: CurrentUser) -> dict:
    from clipforge_api.routes.clips import idle_project
    from clipforge_api.services.brands import apply_brand

    project = idle_project(project_id, db, user)
    apply_brand(db, project, body.kit_id, body.include_existing)
    db.commit()
    return project.brand_config


@router.delete("/brand-kits/{kit_id}", status_code=204)
def delete(kit_id: uuid.UUID, db: Db, user: CurrentUser) -> None:
    kit = owned(kit_id, db, user)
    if kit.logo_key:
        s3().delete_object(Bucket=settings().s3_bucket, Key=kit.logo_key)
    db.delete(kit)
    db.commit()
