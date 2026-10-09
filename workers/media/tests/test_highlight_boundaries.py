import pytest
from clipforge_worker.highlights.candidates import create_candidates, sentences
from clipforge_worker.transcription.base import Segment, Word


def segment(start, texts, spacing=1):
    words = [
        Word(start=start + i * spacing, end=start + i * spacing + 0.8 * spacing, text=text)
        for i, text in enumerate(texts)
    ]
    return Segment(start=words[0].start, end=words[-1].end, text=" ".join(texts), words=words)


def test_a_sentence_across_whisper_chunks_is_one_idea():
    pieces = [
        segment(0, ["The", "biggest", "mistake", "is"]),
        segment(4, ["skipping", "the", "customer", "test."]),
    ]
    units = sentences(pieces)
    assert len(units) == 1
    assert units[0].text == "The biggest mistake is skipping the customer test."
    candidates = create_candidates(pieces, 5, 12, 10)
    assert len(candidates) == 1
    assert candidates[0].start == 0
    assert candidates[0].end >= pieces[-1].end
    assert candidates[0].end_boundary_quality == 1
    assert candidates[0].word_timing_coverage == 1


@pytest.mark.parametrize("ending", ['works."', "কাজ।", "成功。", "really？"])
def test_multilingual_punctuation_and_quotes_are_boundaries(ending):
    pieces = [segment(0, ["This", "idea", ending, "Next", "topic."])]
    assert len(sentences(pieces)) == 2


def test_short_sentence_is_not_forced_into_fragments():
    pieces = [segment(0, [f"word{i}" for i in range(9)] + ["done."])]
    candidates = create_candidates(pieces, 5, 12, 12)
    assert len(candidates) == 1
    assert candidates[0].end_boundary_quality == 1


def test_long_unpunctuated_speech_is_not_forced_into_unfinished_clips():
    pieces = [segment(0, [f"word{i}" for i in range(50)])]
    candidates = create_candidates(pieces, 5, 12, 51)
    assert candidates == []


def test_long_transcript_without_word_times_does_not_invent_cuts():
    assert (
        create_candidates(
            [Segment(start=0, end=40, text="A very long idea without word timestamps.")], 5, 12, 40
        )
        == []
    )


def test_complete_speech_has_breathing_room_after_target_duration():
    candidates = create_candidates(
        [Segment(start=1, end=13, text="A complete standalone thought.")], 5, 12, 15
    )
    assert len(candidates) == 1
    assert (candidates[0].start, candidates[0].end) == pytest.approx((0.92, 13.35))


def test_finishes_sentence_slightly_past_target_instead_of_cutting_words():
    pieces = [segment(1, ["A"] + [f"word{i}" for i in range(11)] + ["done."])]
    candidates = create_candidates(pieces, 5, 12, 16)
    assert len(candidates) == 1
    assert candidates[0].text.endswith("done.")
    assert candidates[0].end >= pieces[0].end + 0.3
    assert candidates[0].end - candidates[0].start <= 15


def test_question_needs_answer_and_rushed_followon_is_not_a_clean_ending():
    from clipforge_worker.highlights.selector import select_candidates

    pieces = [
        Segment(start=0, end=5, text="We need to discuss this. What should you do?"),
        Segment(start=5.2, end=10, text="Test the idea before spending any money."),
        Segment(start=10.08, end=12, text="And use the result to choose your next step."),
    ]
    candidates = create_candidates(pieces, 4, 12, 14)
    ranked = [candidate.model_copy(update={"score": 90}) for candidate in candidates]
    selected = select_candidates(ranked, 3)
    assert selected
    assert all(not candidate.text.endswith("?") for candidate in selected)
    assert all(candidate.end >= 12.3 for candidate in selected)


def test_outro_never_includes_the_start_of_the_next_sentence():
    pieces = [
        Segment(start=0, end=6, text="A complete and useful standalone explanation."),
        Segment(start=6.5, end=9, text="A different topic begins here."),
    ]
    candidate = create_candidates(pieces, 4, 7, 12)[0]
    assert candidate.end == pytest.approx(6.35)
    assert candidate.end < pieces[1].start


def test_zero_duration_transcript_words_keep_continuation_context():
    from clipforge_worker.highlights.selector import select_candidates
    from clipforge_worker.transcription.base import Word

    pieces = [
        Segment(start=0, end=5, text="A completed sentence.", words=[Word(start=0, end=5, text="A completed sentence.")]),
        Segment(start=5.4, end=8, text="And finish the point.", words=[Word(start=5.4, end=5.4, text="And"), Word(start=5.4, end=8, text="finish the point.")]),
    ]
    candidates = create_candidates(pieces, 4, 10, 12)
    assert any("And finish" in candidate.text for candidate in candidates)
    selected = select_candidates([candidate.model_copy(update={"score": 90}) for candidate in candidates], 1)
    assert len(selected) == 1 and selected[0].end >= 8.3


def test_far_apart_thoughts_are_not_glued_to_fill_minimum_duration():
    pieces = [segment(0, ["One", "idea."]), segment(15, ["Different", "topic."])]
    assert create_candidates(pieces, 5, 25, 20) == []


def test_context_is_available_without_leaking_it_into_clip_text():
    pieces = [segment(i * 7, ["Idea", str(i), "complete."]) for i in range(3)]
    candidate = next(c for c in create_candidates(pieces, 2, 5, 22) if "1" in c.text)
    assert "0" in candidate.context_before and "2" in candidate.context_after
    assert "0" not in candidate.text and "2" not in candidate.text
