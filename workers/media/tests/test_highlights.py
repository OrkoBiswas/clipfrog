from clipforge_worker.highlights.ai_ranker import OptionalCloudRanker
from clipforge_worker.highlights.candidates import create_candidates
from clipforge_worker.highlights.heuristic_ranker import HeuristicHighlightRanker
from clipforge_worker.highlights.models import Candidate
from clipforge_worker.highlights.selector import overlap, select_candidates
from clipforge_worker.transcription.base import Segment


def test_complete_insight_beats_filler():
    scored = HeuristicHighlightRanker().score_candidates(
        [
            Candidate(
                start=0,
                end=25,
                text="Here is an important lesson. First test your idea because practical examples help people understand the reason. Choose small steps instead.",
            ),
            Candidate(start=30, end=55, text="um yeah okay um uh yeah and that uh"),
        ],
        [],
    )
    assert scored[0].score > scored[1].score + 20
    assert abs(sum(scored[0].breakdown.values()) - scored[0].score) < 0.01


def test_duration_boundaries_diversity_and_short_source():
    segments = [
        Segment(start=i * 10, end=i * 10 + 9, text=f"Here is useful idea number {i}.")
        for i in range(8)
    ]
    candidates = create_candidates(segments, 20, 35, 80)
    assert all(20 <= c.end - c.start <= 43.75 for c in candidates)
    assert all(c.text.endswith(".") for c in candidates)
    ranked = HeuristicHighlightRanker().score_candidates(candidates, [])
    selected = select_candidates(ranked, 10)
    assert len(selected) < 10
    assert all(overlap(a, b) == 0 for i, a in enumerate(selected) for b in selected[i + 1 :])
    assert select_candidates(ranked, 10) == selected
    assert create_candidates(segments[:1], 20, 35, 10) == []


def test_provider_failure_falls_back(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai-compatible")
    monkeypatch.setenv("AI_API_KEY", "test")

    def fail(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr("httpx.post", fail)
    candidates = [
        Candidate(start=0, end=20, text="Here is the practical lesson because testing helps.")
    ]
    assert OptionalCloudRanker().score_candidates(
        candidates, []
    ) == HeuristicHighlightRanker().score_candidates(candidates, [])


def test_duplicate_ideas_do_not_fill_results():
    candidates = [
        Candidate(
            start=i * 30, end=i * 30 + 25, text="One identical important idea repeated.", score=90
        )
        for i in range(10)
    ]
    assert len(select_candidates(candidates, 10)) == 1
