import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Ratio = Literal["9:16", "16:9", "1:1", "4:5", "3:4", "4:3", "21:9", "Original"]


class CaptionCue(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(max_length=1000)

    @model_validator(mode="after")
    def ordered(self) -> "CaptionCue":
        if self.end_ms <= self.start_ms:
            raise ValueError("Caption end must follow its start.")
        return self


class CaptionConfig(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    template_id: str | None = Field(default=None, max_length=100)
    enabled: bool = True
    style: Literal["Clean", "Bold", "Minimal", "Karaoke", "Creator", "Podcast", "High Contrast"] = (
        "Clean"
    )
    font: Literal[
        "DejaVu Sans",
        "Noto Sans",
        "Bebas Neue",
        "Lato",
        "Montserrat",
        "Open Sans",
        "Roboto",
    ] = "DejaVu Sans"
    size: int = Field(default=54, ge=20, le=120)
    max_words: int = Field(default=5, ge=1, le=12)
    max_chars_per_line: int = Field(default=24, ge=1, le=80)
    lines: int = Field(default=2, ge=1, le=2)
    position: Literal["bottom", "middle", "top"] = "bottom"
    uppercase: bool = False
    punctuation: bool = True
    remove_special_characters: bool = False
    outline: int = Field(default=3, ge=0, le=8)
    shadow: int = Field(default=1, ge=0, le=5)
    background: bool = False
    highlight: bool = False
    cues: list[CaptionCue] | None = Field(default=None, max_length=500)
    primary_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9a-fA-F]{6}$")
    highlight_color: str = Field(default="#FFD700", pattern=r"^#[0-9a-fA-F]{6}$")
    weight: Literal[400, 700] = 700
    spacing: float = Field(default=0, ge=0, le=12)
    stroke_color: str = Field(default="#141414", pattern=r"^#[0-9a-fA-F]{6}$")
    background_color: str = Field(default="#000000", pattern=r"^#[0-9a-fA-F]{6}$")
    background_opacity: float = Field(default=0.65, ge=0, le=1)
    animation: Literal["none", "fade", "pop", "scale", "bounce", "slide", "word-pop", "karaoke"] = (
        "none"
    )
    x: float = Field(default=0.5, ge=0.05, le=0.95)
    y: float = Field(default=0.78, ge=0.05, le=0.95)
    width: float = Field(default=0.84, ge=0.2, le=0.94)
    alignment: Literal["left", "center", "right"] = "center"
    safe_bottom: float = Field(default=0.17, ge=0.02, le=0.35)


class OverlayConfig(BaseModel):
    title: str = Field(default="", max_length=160)
    watermark: str = Field(default="", max_length=60)
    brand_kit_id: uuid.UUID | None = None
    logo_asset_id: uuid.UUID | None = None
    logo_enabled: bool = True
    title_style: Literal["Bold", "Minimal", "Boxed"] = "Bold"
    logo_position: Literal[
        "top-left",
        "top-center",
        "top-right",
        "middle-left",
        "middle-center",
        "middle-right",
        "bottom-left",
        "bottom-center",
        "bottom-right",
    ] = "top-right"
    logo_size: float = Field(default=0.16, ge=0.05, le=0.30)
    logo_opacity: float = Field(default=1, ge=0, le=1)
    logo_margin: float = Field(default=0.04, ge=0, le=0.25)
    logo_x: float | None = Field(default=None, ge=0, le=1)
    logo_y: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def paired_logo(self) -> "OverlayConfig":
        if (self.logo_x is None) != (self.logo_y is None):
            raise ValueError("Provide both logo coordinates.")
        return self


class RenderConfig(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    quality: Literal["Draft", "Standard", "High"] = "Standard"
    crop_mode: Literal["STATIC_SUBJECT_LOCK", "SCENE_AWARE_LOCK"] = "STATIC_SUBJECT_LOCK"
    anchor_x: float | None = Field(default=None, ge=0, le=1)
    anchor_y: float | None = Field(default=None, ge=0, le=1)
    zoom: float = Field(default=1, ge=1, le=3)
    normalize_audio: bool = True
    eye_line: float = Field(default=0.34, ge=0.25, le=0.45)
    headroom: float = Field(default=0.08, ge=0.03, le=0.15)
    minimum_framing_score: int = Field(default=65, ge=0, le=100)
    subject: Literal["primary", "left", "right", "two-person"] = "primary"
    lock_camera: bool = True
    minimum_crop_hold_seconds: float = Field(default=4, ge=3, le=10)
    horizontal_dead_zone: float = Field(default=0.18, ge=0.05, le=0.4)
    vertical_dead_zone: float = Field(default=0.15, ge=0.05, le=0.4)

    @model_validator(mode="after")
    def paired_anchor(self) -> "RenderConfig":
        if (self.anchor_x is None) != (self.anchor_y is None):
            raise ValueError("Provide both crop anchor coordinates.")
        return self


class ClipInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    aspect_ratio: Ratio = "9:16"
    caption_config: CaptionConfig = Field(default_factory=CaptionConfig)
    overlay_config: OverlayConfig = Field(default_factory=OverlayConfig)
    render_config: RenderConfig = Field(default_factory=RenderConfig)

    @model_validator(mode="after")
    def duration(self) -> "ClipInput":
        if not 1000 <= self.end_ms - self.start_ms <= 180000:
            raise ValueError("Clip duration must be between 1 and 180 seconds.")
        return self


class GenerateClips(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    ratios: list[Ratio] = Field(default=["9:16"], min_length=1, max_length=8)
