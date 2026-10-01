from typing import Protocol

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    start: float
    end: float
    text: str
    score: float = 0
    breakdown: dict[str, float] = Field(default_factory=dict)
    reason: str = ""
    title: str = ""
    face_presence: float = 0
    visual_stability: float = 1
    audio_emphasis: float = 0.5


class HighlightRanker(Protocol):
    def score_candidates(
        self, candidates: list[Candidate], keywords: list[str]
    ) -> list[Candidate]: ...
