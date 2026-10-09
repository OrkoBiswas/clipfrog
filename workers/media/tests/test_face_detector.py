from clipforge_worker.vision.face_detector import (
    COLLAGE_DETECTOR_VERSION,
    FaceFrame,
    collage_analysis_ready,
    collage_sample_times,
    merge_collage_frames,
)


def test_refined_cache_requires_every_sample_in_the_requested_range():
    frames = [
        FaceFrame(timestamp=t, faces=[], detector=COLLAGE_DETECTOR_VERSION)
        for t in collage_sample_times(2.1, 5.2)
    ]
    assert collage_analysis_ready(frames, 2.1, 5.2)
    assert collage_analysis_ready(frames, 3, 4)
    assert not collage_analysis_ready(frames[:-1], 2.1, 5.2)
    assert not collage_analysis_ready(
        [frame.model_copy(update={"detector": None}) for frame in frames], 2.1, 5.2
    )
    assert not collage_analysis_ready(frames, 2, 6)
    assert not collage_analysis_ready(
        [frame.model_copy(update={"detector": "yunet-collage-v1"}) for frame in frames], 2.1, 5.2
    )


def test_refinement_merges_only_its_range_and_keeps_real_empty_samples():
    legacy = [FaceFrame(timestamp=t, faces=[]) for t in range(7)]
    refined = [
        FaceFrame(timestamp=t, faces=[], detector=COLLAGE_DETECTOR_VERSION)
        for t in collage_sample_times(2, 4)
    ]
    merged = merge_collage_frames(legacy, refined, 2, 4)
    assert [frame.timestamp for frame in merged if frame.detector is None] == [0, 1, 4, 5, 6]
    assert collage_analysis_ready(merged, 2, 4)
    assert [frame.timestamp for frame in merged] == sorted(frame.timestamp for frame in merged)
