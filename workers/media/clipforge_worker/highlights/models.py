from typing import Protocol

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    start: float
    end: float
    text: str
    score: float = 0
    breakdown: dict[str, float] = Field(default_factory=dict)
    features: dict[str, float] = Field(default_factory=dict)
    reason: str = ""
    title: str = ""
    face_presence: float = 0
    visual_stability: float = 1
    audio_emphasis: float = 0.5
    start_boundary_quality: float | None = Field(default=None, ge=0, le=1)
    end_boundary_quality: float | None = Field(default=None, ge=0, le=1)
    speech_ratio: float | None = Field(default=None, ge=0, le=1)
    word_timing_coverage: float | None = Field(default=None, ge=0, le=1)
    transcript_confidence: float | None = Field(default=None, ge=0, le=1)
    context_before: str = ""
    context_after: str = ""
    sentence_count: int = Field(default=0, ge=0)
    content_profile: str = "general"


class HighlightRanker(Protocol):
    def score_candidates(
        self, candidates: list[Candidate], keywords: list[str]
    ) -> list[Candidate]: ...
