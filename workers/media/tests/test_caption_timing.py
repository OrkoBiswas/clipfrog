from clipforge_api.clip_schemas import CaptionCue
from clipforge_worker.transcription.base import Segment, Word
from clipforge_worker.transcription.caption_timing import speech_captions


def spoken():
    return [
        Segment(
            start=4,
            end=10,
            text="Wait a moment now",
            words=[
                Word(start=4.2, end=4.6, text="Wait"),
                Word(start=4.7, end=5, text="a"),
                Word(start=7, end=7.5, text="moment"),
                Word(start=7.5, end=8.2, text="now"),
            ],
        )
    ]


def test_speech_boundaries_hide_leading_trailing_and_internal_silence():
    runs = speech_captions(spoken(), 4, 10)
    assert [(run.start, run.end, run.text) for run in runs] == [
        (4.2, 5, "Wait a"),
        (7, 8.2, "moment now"),
    ]
    assert runs[0].words[0].start == 4.2


def test_clip_trimming_removes_out_of_range_words():
    runs = speech_captions(spoken(), 4.8, 7.2)
    assert [(run.start, run.end, run.text) for run in runs] == [
        (4.8, 5, "a"),
        (7, 7.2, "moment"),
    ]


def test_unchanged_edited_cues_keep_real_word_timing():
    cue = CaptionCue(start_ms=0, end_ms=6000, text="Wait a moment now")
    assert speech_captions(spoken(), 4, 10, [cue]) == speech_captions(spoken(), 4, 10)


def test_changed_cue_text_is_distributed_only_during_speech():
    cues = [CaptionCue(start_ms=0, end_ms=6000, text="New corrected words here")]
    runs = speech_captions(spoken(), 4, 10, cues)
    assert " ".join(run.text for run in runs) == cues[0].text
    assert [(run.start, run.end) for run in runs] == [(4.2, 5), (7, 8.2)]
    assert all(run.words for run in runs)


def test_manual_cue_in_known_silence_is_hidden():
    cues = [CaptionCue(start_ms=2000, end_ms=2500, text="No speech here")]
    assert speech_captions(spoken(), 4, 10, cues) == []


def test_manual_captions_without_transcript_keep_explicit_timing():
    cues = [CaptionCue(start_ms=500, end_ms=1500, text="Manual text")]
    runs = speech_captions([], 4, 10, cues)
    assert [(run.start, run.end, run.text) for run in runs] == [(4.5, 5.5, "Manual text")]
    assert speech_captions(spoken(), 4, 10, []) == []


def test_words_without_timestamps_use_segment_boundary():
    runs = speech_captions([Segment(start=1, end=2, text="Two words")], 0, 4)
    assert [(run.start, run.end, run.text) for run in runs] == [(1, 2, "Two words")]


def test_invalid_word_durations_do_not_create_lingering_captions():
    runs = speech_captions(
        [
            Segment(
                start=0,
                end=4,
                text="Hello",
                words=[
                    Word(start=1, end=2, text="Hello"),
                    Word(start=2, end=2, text="."),
                    Word(start=3, end=2, text="invalid"),
                ],
            )
        ],
        0,
        4,
    )
    assert [(run.start, run.end, run.text) for run in runs] == [(1, 2, "Hello .")]
