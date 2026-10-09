import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from clipforge_api.caption_fonts import CaptionWeight, caption_family, caption_variant

Ratio = Literal["9:16", "16:9", "1:1", "4:5", "3:4", "4:3", "21:9", "Original"]
CaptionAnimation = Literal[
    "none",
    "word-pop",
    "fade",
    "rise",
    "fall",
    "slide-left",
    "slide-right",
    "zoom-in",
    "zoom-out",
    "bounce",
    "blur-in",
    "tilt",
    "unfold",
    "stretch",
    "wipe",
    "lift-mask",
    "typewriter",
    "color-reveal",
    "word-reveal",
    "karaoke",
    "spotlight",
    "stamp",
    "word-spring",
    "word-rise",
    "word-punch",
    "word-slide",
    "word-tilt",
    "word-focus",
    "word-flip",
    "word-stretch",
    "word-pill",
    "word-box",
    "word-underline",
    "word-glow",
]
BASIC_CAPTION_SETTINGS = {
    "style": "Clean",
    "font": "DejaVu Sans",
    "size": 54,
    "max_words": 5,
    "max_chars_per_line": 24,
    "lines": 2,
    "position": "bottom",
    "uppercase": False,
    "punctuation": True,
    "remove_special_characters": False,
    "outline": 3,
    "shadow": 1,
    "shadow_color": "#000000",
    "shadow_opacity": 0.6,
    "background": False,
    "highlight": False,
    "primary_color": "#FFFFFF",
    "highlight_color": "#FFD700",
    "weight": 700,
    "font_width": 100,
    "spacing": 0,
    "stroke_color": "#141414",
    "background_color": "#000000",
    "background_opacity": 0.65,
    "animation": "word-pop",
    "animation_duration": 0.6,
    "effect_color": "#0054FF",
    "x": 0.5,
    "y": 0.78,
    "width": 0.84,
    "alignment": "center",
    "safe_bottom": 0.17,
}


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
    enabled: bool = True
    style: str = Field(default="Clean", max_length=80)
    font: str = Field(default="DejaVu Sans", min_length=1, max_length=80)
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
    shadow_color: str = Field(default="#000000", pattern=r"^#[0-9a-fA-F]{6}$")
    shadow_opacity: float = Field(default=0.6, ge=0, le=1)
    background: bool = False
    highlight: bool = False
    cues: list[CaptionCue] | None = Field(default=None, max_length=500)
    primary_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9a-fA-F]{6}$")
    highlight_color: str = Field(default="#FFD700", pattern=r"^#[0-9a-fA-F]{6}$")
    weight: CaptionWeight = 700
    italic: bool = False
    font_width: float = Field(default=100, ge=75, le=150)
    spacing: float = Field(default=0, ge=0, le=12)
    stroke_color: str = Field(default="#141414", pattern=r"^#[0-9a-fA-F]{6}$")
    background_color: str = Field(default="#000000", pattern=r"^#[0-9a-fA-F]{6}$")
    background_opacity: float = Field(default=0.65, ge=0, le=1)
    animation: CaptionAnimation = "word-pop"
    animation_duration: float = Field(default=0.6, ge=0.1, le=2)
    effect_color: str = Field(default="#0054FF", pattern=r"^#[0-9a-fA-F]{6}$")
    word_display: Literal["full", "build", "single"] = "full"
    active_scale: float = Field(default=1.06, ge=1, le=1.4)
    inactive_opacity: float = Field(default=1, ge=0.1, le=1)
    x: float = Field(default=0.5, ge=0.05, le=0.95)
    y: float = Field(default=0.78, ge=0.05, le=0.95)
    width: float = Field(default=0.84, ge=0.2, le=0.94)
    alignment: Literal["left", "center", "right"] = "center"
    safe_bottom: float = Field(default=0.17, ge=0.02, le=0.35)

    @field_validator("font")
    @classmethod
    def supported_font(cls, value: str) -> str:
        caption_family(value)
        return value

    @model_validator(mode="after")
    def supported_font_variant(self) -> "CaptionConfig":
        # Old clips may request bold/italic on a regular-only display face.
        # Persist the nearest real face so browser and exported text agree.
        variant = caption_variant(self.font, self.weight, self.italic)
        self.weight = variant["weight"]
        self.italic = variant["italic"]
        return self

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_config(cls, value: object) -> object:
        if isinstance(value, dict):
            normalized = dict(value)
            # Retired external renderer presets remain readable. Never discard
            # a user's typography, placement, colors or transcript on save.
            if normalized.get("animation") in {
                "mogrt-pack1-01",
                "mogrt-pack1-02",
                "mogrt-pack1-03",
                "mogrt-pack1-04",
                "blue-slice",
                "smoke-block",
                "vertical-snap",
                "blue-echo",
            }:
                normalized["animation"] = "word-pop"
            return normalized
        return value


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


class PanelConfig(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    subject: Literal[
        "primary", "left", "center", "right", "person-1", "person-2", "person-3", "person-4"
    ] = "primary"
    anchor_x: float | None = Field(default=None, ge=0, le=1)
    anchor_y: float | None = Field(default=None, ge=0, le=1)
    zoom: float = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def paired_anchor(self) -> "PanelConfig":
        if (self.anchor_x is None) != (self.anchor_y is None):
            raise ValueError("Provide both panel crop anchor coordinates.")
        return self


class RenderConfig(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    quality: Literal["Draft", "Standard", "High"] = "Standard"
    layout: Literal["single", "auto", "stacked", "side-by-side", "grid"] = "single"
    panels: list[PanelConfig] = Field(default_factory=list, max_length=4)
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
        if self.layout == "auto":
            self.panels = []
        elif self.layout != "single":
            if not self.panels:
                count = 4 if self.layout == "grid" else 2
                self.panels = [
                    PanelConfig.model_validate({"subject": f"person-{index + 1}"})
                    for index in range(count)
                ]
            allowed_counts = {3, 4} if self.layout == "grid" else {2}
            if len(self.panels) not in allowed_counts:
                raise ValueError("Choose two panels for a split or three to four for a grid.")
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
