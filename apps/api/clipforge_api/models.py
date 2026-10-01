import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clipforge_api.db import Base

json_type = JSON().with_variant(JSONB, "postgresql")


def now() -> datetime:
    return datetime.now(UTC)


class Identity:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(512))
    email_verified: Mapped[bool] = mapped_column(default=False)
    is_admin: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class AuthSession(Identity, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthToken(Identity, Base):
    __tablename__ = "auth_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Project(Identity, Base):
    __tablename__ = "projects"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    content_type: Mapped[str] = mapped_column(String(30), default="Auto")
    language: Mapped[str] = mapped_column(String(20), default="auto")
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    processing_config: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    brand_config: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class MediaAsset(Identity, Base):
    __tablename__ = "media_assets"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(30))
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None]
    height: Mapped[int | None]
    duration_ms: Mapped[int | None]
    fps: Mapped[float | None]
    codec: Mapped[str | None] = mapped_column(String(100))
    checksum: Mapped[str | None] = mapped_column(String(128))


class ProcessingJob(Identity, Base):
    __tablename__ = "processing_jobs"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[str] = mapped_column(String(30))
    queue: Mapped[str] = mapped_column(String(30), default="analysis")
    status: Mapped[str] = mapped_column(String(30), default="QUEUED")
    progress: Mapped[int] = mapped_column(default=0)
    stage: Mapped[str] = mapped_column(String(100), default="Queued")
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None]
    attempts: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageLedger(Identity, Base):
    __tablename__ = "usage_ledger"
    __table_args__ = (UniqueConstraint("idempotency_key"),)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    metric: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[float]
    unit: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)


class UploadSession(Identity, Base):
    __tablename__ = "upload_sessions"
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"))
    upload_id: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(30), default="UPLOADING")
    part_size: Mapped[int] = mapped_column(default=16 * 1024**2)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Transcript(Identity, Base):
    __tablename__ = "transcripts"
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True
    )
    language: Mapped[str] = mapped_column(String(20))
    full_text: Mapped[str]
    segments: Mapped[list[dict[str, Any]]] = mapped_column(json_type)
    provider: Mapped[str] = mapped_column(String(50), default="faster-whisper")


class Scene(Identity, Base):
    __tablename__ = "scenes"
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    start_ms: Mapped[int]
    end_ms: Mapped[int]
    confidence: Mapped[float] = mapped_column(default=1)


class Analysis(Identity, Base):
    __tablename__ = "analysis"
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True
    )
    face_frames: Mapped[list[dict[str, Any]]] = mapped_column(json_type, default=list)
    warnings: Mapped[list[str]] = mapped_column(json_type, default=list)


class ClipCandidate(Identity, Base):
    __tablename__ = "clip_candidates"
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    start_ms: Mapped[int]
    end_ms: Mapped[int]
    transcript_text: Mapped[str]
    score_total: Mapped[float]
    score_breakdown: Mapped[dict[str, float]] = mapped_column(json_type)
    reason: Mapped[str]
    title: Mapped[str] = mapped_column(String(120))
    selected: Mapped[bool] = mapped_column(default=False)
    rank: Mapped[int | None]


class Clip(Identity, Base):
    __tablename__ = "clips"
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clip_candidates.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(160))
    start_ms: Mapped[int]
    end_ms: Mapped[int]
    aspect_ratio: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    is_preview: Mapped[bool] = mapped_column(default=False)
    highlight_score: Mapped[float | None]
    crop_plan: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    caption_config: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    overlay_config: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    render_config: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    output_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    thumbnail_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    revision: Mapped[int] = mapped_column(default=1)
    rendered_revision: Mapped[int | None]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Subscription(Identity, Base):
    __tablename__ = "subscriptions"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    customer_id: Mapped[str] = mapped_column(String(100), unique=True)
    subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    plan: Mapped[str] = mapped_column(String(30), default="free")
    status: Mapped[str] = mapped_column(String(30), default="inactive")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class BillingEvent(Base):
    __tablename__ = "billing_events"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BrandKit(Identity, Base):
    __tablename__ = "brand_kits"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    logo_key: Mapped[str | None] = mapped_column(String(1024))
    logo_size: Mapped[int] = mapped_column(default=0)


class CaptionLibrary(Base):
    __tablename__ = "caption_libraries"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
