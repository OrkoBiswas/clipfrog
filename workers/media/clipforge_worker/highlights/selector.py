from clipforge_worker.highlights.heuristic_ranker import tokens
from clipforge_worker.highlights.models import Candidate


def overlap(a: Candidate, b: Candidate) -> float:
    return max(0, min(a.end, b.end) - max(a.start, b.start)) / max(
        0.01, min(a.end - a.start, b.end - b.start)
    )


def similarity(a: Candidate, b: Candidate) -> float:
    left, right = tokens(a.text), tokens(b.text)
    return len(left & right) / max(1, len(left | right))


def select_candidates(
    candidates: list[Candidate],
    count: int,
    minimum_score: float = 35,
    max_overlap: float = 0,
    separation: float = 0,
) -> list[Candidate]:
    remaining = sorted(candidates, key=lambda c: (-c.score, c.start, c.end))
    selected: list[Candidate] = []
    while remaining and len(selected) < count:
        ranked = []
        for candidate in remaining:
            if any(
                overlap(candidate, item) > max_overlap
                or (
                    separation > 0
                    and max(candidate.start, item.start) - min(candidate.end, item.end) < separation
                )
                for item in selected
            ):
                continue
            duplicate = max((similarity(candidate, item) for item in selected), default=0)
            if duplicate > 0.8:
                continue
            adjusted = candidate.score - candidate.breakdown.get("novelty", 10) * duplicate
            if adjusted >= minimum_score:
                ranked.append((adjusted, candidate))
        if not ranked:
            break
        score, chosen = max(ranked, key=lambda item: (item[0], -item[1].start, -item[1].end))
        breakdown = dict(chosen.breakdown)
        breakdown["novelty"] = round(breakdown.get("novelty", 10) - (chosen.score - score), 2)
        selected.append(
            chosen.model_copy(update={"score": round(score, 2), "breakdown": breakdown})
        )
        remaining.remove(chosen)
    return selected
