import pytest
from clipforge_worker.highlights.heuristic_ranker import (
    HeuristicHighlightRanker,
    tokens,
)
from clipforge_worker.highlights.models import Candidate
from clipforge_worker.highlights.selector import select_candidates

# Editorial preference fixtures, not claims about actual social performance.
PREFERENCES = [
    (
        "Why do interviews fail? Asking leading questions hides the truth. Ask what the customer did yesterday instead, then test their actual behavior.",
        "Why how secret important mistake tip lesson never why how secret important mistake tip lesson never.",
    ),
    (
        "I lost my job and thought everything was over. I tried helping a neighbor fix her website. That small project turned into my first paying customer.",
        "Welcome back to the show. Like and subscribe. Thanks to our sponsor, use the promo code in the description.",
    ),
    (
        "How do you protect your savings? Keep three months of expenses in a separate account because emergencies should not force you to sell investments.",
        "How do you protect your savings?",
    ),
    (
        "The biggest mistake is editing before writing. Write one clear sentence first. Then remove every section that does not support it.",
        "The biggest mistake is editing before writing. Here is why. I'll tell you later.",
    ),
    (
        "This is a simple way to recover focus. Put your phone in another room and work for 20 minutes because removing interruptions makes starting easier.",
        "Um yeah okay um uh. So yeah okay, um, uh yeah.",
    ),
    (
        "কেন আপনার পড়া মনে থাকে না? কারণ শুধু পড়লে হয় না। প্রথমে বই বন্ধ করুন এবং নিজের ভাষায় লিখুন। ফলে ভুলগুলো বুঝতে পারবেন।",
        "আচ্ছা মানে আচ্ছা মানে আচ্ছা মানে। সাবস্ক্রাইব করুন।",
    ),
    (
        "I couldn't believe it. We were losing by ten points, but the final shot went in. We finally won the match and everyone started laughing.",
        "Okay guys okay yeah so yeah okay. The game is there and this is the thing that we did.",
    ),
]


@pytest.mark.parametrize("good,poor", PREFERENCES)
def test_editorial_preferences(good, poor):
    ranked = HeuristicHighlightRanker().score_candidates(
        [
            Candidate(start=0, end=20, text=good),
            Candidate(start=30, end=50, text=poor),
        ],
        [],
    )
    assert ranked[0].score > ranked[1].score + 10, [(c.score, c.reason) for c in ranked]
    assert sum(ranked[0].breakdown.values()) == pytest.approx(ranked[0].score)
    assert all(0 <= value <= 1 for value in ranked[0].features.values())


def test_filler_appending_and_speed_do_not_buy_a_higher_score():
    text = PREFERENCES[0][0]
    base, bloated = HeuristicHighlightRanker().score_candidates(
        [
            Candidate(start=0, end=20, text=text),
            Candidate(start=0, end=35, text=text + " Um yeah okay uh." * 10),
        ],
        [],
    )
    assert base.score > bloated.score + 15


def test_no_face_is_not_a_penalty_for_a_screen_tutorial():
    candidate = Candidate(start=0, end=20, text=PREFERENCES[0][0])
    absent, present = HeuristicHighlightRanker().score_candidates(
        [
            candidate,
            candidate.model_copy(update={"face_presence": 1}),
        ],
        [],
        content_type="Tutorial",
    )
    assert absent.score == present.score
    assert absent.content_profile == "educational"


def test_forced_cut_loses_to_complete_idea():
    candidate = Candidate(start=0, end=20, text=PREFERENCES[0][0])
    complete, partial = HeuristicHighlightRanker().score_candidates(
        [
            candidate.model_copy(update={"start_boundary_quality": 1, "end_boundary_quality": 1}),
            candidate.model_copy(
                update={"start_boundary_quality": 0.2, "end_boundary_quality": 0.2}
            ),
        ],
        [],
    )
    assert complete.score > partial.score + 15


def test_uncertain_transcription_is_not_presented_as_confident_editorial_value():
    candidate = Candidate(start=0, end=20, text=PREFERENCES[0][0])
    reliable, uncertain = HeuristicHighlightRanker().score_candidates(
        [
            candidate.model_copy(update={"transcript_confidence": 0.98}),
            candidate.model_copy(update={"transcript_confidence": 0.2}),
        ],
        [],
    )
    assert reliable.score > uncertain.score + 20
    assert "uncertain transcription" in uncertain.reason


def test_distinct_advice_on_same_topic_survives_and_repeated_take_does_not():
    candidates = [
        Candidate(
            start=0,
            end=20,
            text="Keep the camera still and lock exposure before every interview recording.",
            score=90,
        ),
        Candidate(
            start=25,
            end=45,
            text="Keep the camera still and lock exposure before every interview recording. Yeah.",
            score=89,
        ),
        Candidate(
            start=50,
            end=70,
            text="Check your microphone cable and record a short sound test before an interview.",
            score=88,
        ),
    ]
    selected = select_candidates(candidates, 3)
    assert len(selected) == 2
    assert {c.start for c in selected} == {0, 50}


def test_unicode_combining_marks_are_preserved_in_topic_tokens():
    assert "কীভাবে" in tokens("কীভাবে কাজ শিখবেন?")
