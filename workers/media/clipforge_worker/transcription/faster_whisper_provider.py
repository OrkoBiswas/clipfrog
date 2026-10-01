from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from clipforge_worker.config import worker_settings
from clipforge_worker.transcription.base import Segment, TranscriptResult, Word


@lru_cache(maxsize=1)
def model():  # type: ignore[no-untyped-def]
    from faster_whisper import WhisperModel

    cfg = worker_settings()
    return WhisperModel(
        cfg.whisper_model,
        device=cfg.worker_device,
        compute_type=cfg.whisper_compute_type,
        download_root=cfg.model_cache,
        cpu_threads=4,
        num_workers=1,
    )


class FasterWhisperProvider:
    def transcribe(
        self, audio: Path, language: str | None, progress: Callable[[float], None]
    ) -> TranscriptResult:
        segments, info = model().transcribe(
            str(audio),
            language=language,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        result = []
        for segment in segments:
            result.append(
                Segment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                    words=[
                        Word(
                            start=w.start, end=w.end, text=w.word.strip(), confidence=w.probability
                        )
                        for w in segment.words or []
                    ],
                )
            )
            progress(min(1, segment.end / max(info.duration, 1)))
        return TranscriptResult(language=info.language, segments=result)
