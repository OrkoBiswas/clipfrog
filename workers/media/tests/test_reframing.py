import math

import pytest
from clipforge_worker.reframing.planner import RATIOS, geometry, plan_crop
from clipforge_worker.rendering.renderer import coordinate
from clipforge_worker.vision.face_detector import Face, FaceFrame


def face(x, confidence=0.95, size=0.15):
    return Face(
        confidence=confidence, x=x - size / 2, y=0.2, w=size, h=0.25, center_x=x, center_y=0.325
    )


@pytest.mark.parametrize("ratio", [*RATIOS, "Original"])
def test_all_ratios_stay_in_bounds(ratio):
    plan = plan_crop(1920, 1080, ratio, 0, 20, [], manual_anchor=(1, 0), zoom=1.2)
    for key in plan.keyframes:
        assert 0 <= key.x <= 1920 - plan.crop_width
        assert 0 <= key.y <= 1080 - plan.crop_height
    assert abs(plan.crop_width / plan.crop_height - plan.output_width / plan.output_height) < 0.01


def test_podcast_jitter_and_outlier_produce_one_anchor():
    frames = [
        FaceFrame(timestamp=i / 3, faces=[face(0.3 + math.sin(i) * 0.008)]) for i in range(90)
    ]
    frames[20].faces = [face(0.85, 0.4)]
    plan = plan_crop(1920, 1080, "9:16", 0, 30, frames)
    assert len(plan.keyframes) == 1
    center = (plan.keyframes[0].x + plan.crop_width / 2) / 1920
    assert abs(center - 0.3) < 0.015


def test_persistent_person_beats_transient_larger_person():
    frames = [
        FaceFrame(timestamp=i / 3, faces=[face(0.3)] + ([face(0.75, size=0.3)] if i < 4 else []))
        for i in range(60)
    ]
    plan = plan_crop(1920, 1080, "9:16", 0, 20, frames)
    assert (plan.keyframes[0].x + plan.crop_width / 2) / 1920 < 0.4


def test_cut_switches_once_and_missing_faces_are_safe():
    frames = [FaceFrame(timestamp=i / 3, faces=[face(0.25 if i < 30 else 0.75)]) for i in range(60)]
    plan = plan_crop(1920, 1080, "9:16", 0, 20, frames, [10])
    assert len(plan.keyframes) == 2
    assert plan.keyframes[1].cut and plan.keyframes[1].time == 10
    assert plan.keyframes[1].x > plan.keyframes[0].x
    empty = plan_crop(1920, 1080, "9:16", 0, 20, [])
    assert empty.warnings and empty.confidence == 0
    assert abs(empty.keyframes[0].x - (1920 - empty.crop_width) / 2) <= 2


def test_invalid_geometry_is_rejected():
    with pytest.raises(ValueError):
        geometry(1920, 1080, "invalid")
    with pytest.raises(ValueError):
        plan_crop(1920, 1080, "9:16", 1, 0, [])


def test_static_lock_never_corrects_large_movement():
    frames = [FaceFrame(timestamp=i / 3, faces=[face(0.25 + i / 90 * 0.35)]) for i in range(90)]
    plan = plan_crop(1920, 1080, "9:16", 0, 30, frames)
    assert len(plan.keyframes) == 1
    assert "t-" not in coordinate(plan, "x")
    assert plan.quality["validated"]


def test_hard_cut_has_exact_step_and_no_interpolation():
    frames = [FaceFrame(timestamp=i / 3, faces=[face(0.30 if i < 30 else 0.70)]) for i in range(60)]
    plan = plan_crop(1920, 1080, "9:16", 0, 20, frames, [10])
    assert len(plan.keyframes) == 2
    assert coordinate(plan, "x") == f"if(lt(t,10.0000),{plan.keyframes[0].x},{plan.keyframes[1].x})"
    assert plan.quality["score"] >= 65


def test_manual_crop_wins_over_shots_and_subjects():
    frames = [FaceFrame(timestamp=0, faces=[face(0.2)]), FaceFrame(timestamp=10, faces=[face(0.8)])]
    plan = plan_crop(1920, 1080, "9:16", 0, 20, frames, [10], manual_anchor=(0.5, 0.5))
    assert plan.mode == "MANUAL" and len(plan.keyframes) == 1


def test_left_right_selection_and_edge_quality():
    frames = [FaceFrame(timestamp=i / 3, faces=[face(0.25), face(0.75)]) for i in range(30)]
    left = plan_crop(1920, 1080, "9:16", 0, 10, frames, subject="left")
    right = plan_crop(1920, 1080, "9:16", 0, 10, frames, subject="right")
    assert right.keyframes[0].x > left.keyframes[0].x
    edge = plan_crop(
        1920,
        1080,
        "9:16",
        0,
        10,
        [FaceFrame(timestamp=i / 3, faces=[face(0.02)]) for i in range(30)],
    )
    assert edge.quality["clipped_fraction"] > 0.2
