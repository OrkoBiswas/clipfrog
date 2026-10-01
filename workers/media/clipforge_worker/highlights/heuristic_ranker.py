import re

from clipforge_worker.config import worker_settings
from clipforge_worker.highlights.models import Candidate

DEFAULT_WEIGHTS = {
    "hook": 25,
    "completeness": 20,
    "insight": 20,
    "emphasis": 10,
    "visual": 10,
    "novelty": 10,
    "boundaries": 5,
}
HOOKS = {
    "why",
    "how",
    "secret",
    "important",
    "lesson",
    "mistake",
    "never",
    "imagine",
    "here",
    "what",
    "tip",
}
INSIGHTS = {
    "because",
    "learned",
    "instead",
    "example",
    "reason",
    "first",
    "steps",
    "result",
    "understand",
    "practical",
    "test",
    "choose",
}
FILLERS = {"um", "uh", "erm", "hmm", "yeah", "okay"}


def tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.casefold()))


class HeuristicHighlightRanker:
    def __init__(self, weights: dict[str, int] | None = None):
        self.weights = weights or worker_settings().highlight_weights

    def score_candidates(self, candidates: list[Candidate], keywords: list[str]) -> list[Candidate]:
        result = []
        for candidate in candidates:
            words = re.findall(r"\w+", candidate.text.casefold())
            unique = set(words)
            filler_ratio = sum(w in FILLERS for w in words) / max(1, len(words))
            complete = bool(re.search(r"[.!?。！？]$", candidate.text.rstrip()))
            dangling = bool(
                words and words[0] in {"and", "but", "so", "it", "that", "this", "they"}
            )
            hook = min(
                1,
                0.2
                + len(set(words[:18]) & HOOKS) * 0.2
                + (0.2 if "?" in candidate.text[:100] else 0),
            )
            insight = min(
                1,
                0.15
                + len(unique & INSIGHTS) * 0.16
                + len(unique & tokens(" ".join(keywords))) * 0.12
                + len(unique) / 220,
            )
            speech_density = min(1, len(words) / max(1, (candidate.end - candidate.start) * 2))
            features = {
                "hook": hook * (1 - filler_ratio),
                "completeness": max(0, (0.9 if complete else 0.4) - dangling * 0.3 - filler_ratio),
                "insight": insight * (1 - filler_ratio),
                "emphasis": (speech_density + candidate.audio_emphasis) / 2,
                "visual": (candidate.face_presence + candidate.visual_stability) / 2,
                "novelty": 1,
                "boundaries": 1 if complete else 0.4,
            }
            breakdown = {
                key: round(value * self.weights[key], 2) for key, value in features.items()
            }
            result.append(
                candidate.model_copy(
                    update={
                        "score": round(sum(breakdown.values()), 2),
                        "breakdown": breakdown,
                        "reason": f"{'Complete thought' if complete else 'Partial sentence ending'}; {len(unique & INSIGHTS)} explanation signals; {round(speech_density * 100)}% speech density. Heuristic, not a prediction of audience performance.",
                        "title": " ".join(candidate.text.split()[:10]).strip(" ,;:")[:100],
                    }
                )
            )
        return result
