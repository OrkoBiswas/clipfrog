import hashlib

from clipforge_worker.config import worker_settings
from clipforge_worker.highlights.heuristic_ranker import ENGINE_VERSION
from clipforge_worker.highlights.learning import Example, learn_weights
from sqlalchemy import select

from clipforge_api.models import ClipCandidate, HighlightFeedback


def fingerprint(candidate: ClipCandidate) -> str:
    return moment_fingerprint(candidate.start_ms, candidate.end_ms, candidate.transcript_text)


def moment_fingerprint(start_ms: int, end_ms: int, text: str) -> str:
    text = " ".join(text.casefold().split())
    return hashlib.sha256(f"{start_ms}:{end_ms}:{text}".encode()).hexdigest()


def rejected_moment(start_ms: int, end_ms: int, rejected: list[tuple[int, int]]) -> bool:
    return any(
        max(0, min(end_ms, end) - max(start_ms, start))
        / max(1, min(end_ms - start_ms, end - start))
        > 0.65
        for start, end in rejected
    )


def learning_report(db, user_id):
    rows = list(
        db.scalars(
            select(HighlightFeedback)
            .where(
                HighlightFeedback.user_id == user_id,
                HighlightFeedback.engine_version == ENGINE_VERSION,
            )
            .order_by(HighlightFeedback.updated_at.desc())
            .limit(400)
        )
    )
    return learn_weights(
        [Example(row.features, row.rating == "good") for row in reversed(rows)],
        worker_settings().highlight_weights,
    )
