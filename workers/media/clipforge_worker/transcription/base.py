from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field


class Word(BaseModel):
    start: float
    end: float
    text: str
    confidence: float = 1


class Segment(BaseModel):
    start: float
    end: float
    text: str
    words: list[Word] = Field(default_factory=list)


class TranscriptResult(BaseModel):
    language: str
    segments: list[Segment]


class TranscriptionProvider(Protocol):
    def transcribe(
        self, audio: Path, language: str | None, progress: Callable[[float], None]
    ) -> TranscriptResult: ...
