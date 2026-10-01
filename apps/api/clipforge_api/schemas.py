import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from clipforge_api.clip_schemas import CaptionConfig


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class Register(Credentials):
    name: str = Field(min_length=1, max_length=100)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    name: str
    email_verified: bool
    is_admin: bool


class ProcessingConfig(BaseModel):
    clip_count: int = Field(default=10, ge=1, le=100)
    duration_min: int = Field(default=20, ge=5, le=180)
    duration_max: int = Field(default=35, ge=5, le=180)
    ratios: list[Literal["9:16", "16:9", "1:1", "4:5", "3:4", "4:3", "21:9", "Original"]] = Field(
        default=["9:16"], min_length=1, max_length=8
    )
    captions: bool = True
    caption_style: Literal[
        "Clean", "Bold", "Minimal", "Karaoke", "Creator", "Podcast", "High Contrast"
    ] = "Clean"
    crop_mode: Literal["STATIC_SUBJECT_LOCK", "SCENE_AWARE_LOCK"] = "STATIC_SUBJECT_LOCK"
    quality: Literal["Draft", "Standard", "High"] = "Standard"
    keywords: list[str] = Field(default_factory=list, max_length=20)
    minimum_score: float = Field(default=35, ge=0, le=100)
    max_overlap: float = Field(default=0, ge=0, le=1)
    minimum_separation: float = Field(default=0, ge=0, le=180)
    semantic_ranking: bool = False
    brand_kit_id: uuid.UUID | None = None
    caption_config: CaptionConfig | None = None
    platform_preset: Literal[
        "Custom",
        "YouTube Shorts",
        "TikTok",
        "Instagram Reels",
        "Instagram Feed",
        "Facebook Reels",
        "Facebook Feed",
        "X",
        "LinkedIn",
        "YouTube Landscape",
    ] = "Custom"

    @model_validator(mode="after")
    def valid_duration(self) -> "ProcessingConfig":
        if self.duration_min > self.duration_max:
            raise ValueError("Minimum duration must not exceed maximum duration")
        return self


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=160, pattern=r"\S")
    content_type: Literal[
        "Auto",
        "Podcast",
        "Interview",
        "Talking Head",
        "Tutorial",
        "Webinar",
        "Gaming",
        "Presentation",
        "Other",
    ] = "Auto"
    language: str = Field(default="auto", min_length=2, max_length=20, pattern=r"^[a-zA-Z-]+$")
    processing_config: ProcessingConfig = Field(default_factory=ProcessingConfig)


class ProjectOut(ProjectInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    source_asset_id: uuid.UUID | None
    owner_email: str | None = None
    brand_config: dict = Field(default_factory=dict)
