import math
from collections import Counter

from clipforge_worker.highlights.candidates import unresolved_ending
from clipforge_worker.highlights.heuristic_ranker import STOPWORDS, tokens, word_list
from clipforge_worker.highlights.models import Candidate


def overlap(a: Candidate, b: Candidate) -> float:
    return max(0, min(a.end, b.end) - max(a.start, b.start)) / max(
        0.01, min(a.end - a.start, b.end - b.start)
    )


def similarity(a: Candidate, b: Candidate) -> float:
    left, right = tokens(a.text) - STOPWORDS, tokens(b.text) - STOPWORDS
    return len(left & right) / max(1, len(left | right))


def _duplicate(a: Candidate, b: Candidate) -> bool:
    if " ".join(a.text.casefold().split()) == " ".join(b.text.casefold().split()):
        return True
    left = [w for w in word_list(a.text) if w not in STOPWORDS]
    right = [w for w in word_list(b.text) if w not in STOPWORDS]
    if min(len(left), len(right)) < 5:
        return False
    la, lb = set(zip(left, left[1:], strict=False)), set(zip(right, right[1:], strict=False))
    phrase_overlap = len(la & lb) / max(1, min(len(la), len(lb)))
    coverage = len(set(left) & set(right)) / max(1, min(len(set(left)), len(set(right))))
    return coverage > 0.88 and phrase_overlap > 0.65


def select_candidates(
    candidates: list[Candidate],
    count: int,
    minimum_score: float = 35,
    max_overlap: float = 0,
    separation: float = 0,
) -> list[Candidate]:
    if count <= 0:
        return []
    remaining = sorted(
        (
            c
            for c in candidates
            if not unresolved_ending(c.text)
            and (c.end_boundary_quality is None or c.end_boundary_quality >= 0.75)
            and (c.start_boundary_quality is None or c.start_boundary_quality >= 0.6)
        ),
        key=lambda c: (-c.score, c.end - c.start, c.start),
    )
    # Corpus-weighted lexical similarity reduces duplicate topics without
    # treating generic conversational words as evidence of the same idea.
    documents = [tokens(c.text) - STOPWORDS for c in candidates]
    signatures = {
        (c.start, c.end): document for c, document in zip(candidates, documents, strict=True)
    }
    frequency = Counter(word for document in documents for word in document)
    idf = {word: 1 + math.log((len(documents) + 1) / (n + 1)) for word, n in frequency.items()}

    def related(a: Candidate, b: Candidate) -> float:
        left, right = signatures[(a.start, a.end)], signatures[(b.start, b.end)]
        shared = sum(idf[w] ** 2 for w in left & right)
        norm = math.sqrt(sum(idf[w] ** 2 for w in left) * sum(idf[w] ** 2 for w in right))
        return shared / max(1e-9, norm)

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
            if any(_duplicate(candidate, item) for item in selected):
                continue
            duplicate = max((related(candidate, item) for item in selected), default=0)
            adjusted = candidate.score - candidate.breakdown.get("novelty", 10) * duplicate
            if adjusted >= minimum_score:
                ranked.append((adjusted, candidate))
        if not ranked:
            break
        score, chosen = max(
            ranked, key=lambda item: (item[0], -(item[1].end - item[1].start), -item[1].start)
        )
        breakdown = dict(chosen.breakdown)
        breakdown["novelty"] = round(breakdown.get("novelty", 10) - (chosen.score - score), 2)
        reason = chosen.reason
        if chosen.score - score > 0.1:
            reason += " Diversity adjustment for related topics."
        selected.append(
            chosen.model_copy(
                update={
                    "score": round(sum(breakdown.values()), 2)
                    if chosen.breakdown
                    else round(score, 2),
                    "breakdown": breakdown,
                    "reason": reason,
                }
            )
        )
        remaining.remove(chosen)
    return selected
