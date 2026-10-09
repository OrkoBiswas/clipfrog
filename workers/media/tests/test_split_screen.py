import json
import shutil
import subprocess

import pytest
from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig, RenderConfig
from clipforge_worker.media.probe import probe
from clipforge_worker.reframing.planner import RATIOS, plan_composition, plan_crop
from clipforge_worker.rendering.renderer import render
from clipforge_worker.transcription.base import Segment
from clipforge_worker.vision.face_detector import COLLAGE_DETECTOR_VERSION, Face, FaceFrame
from PIL import Image


def speakers(count=4):
    return [
        Face(
            confidence=0.95,
            x=(index + 0.5) / count - 0.04,
            y=0.24,
            w=0.08,
            h=0.22,
            center_x=(index + 0.5) / count,
            center_y=0.35,
        )
        for index in range(count)
    ]


def composition(layout, count, frames=None, **options):
    config = RenderConfig.model_validate(
        {
            "layout": layout,
            "panels": [{"subject": f"person-{index + 1}"} for index in range(count)],
            **options,
        }
    )
    return plan_composition(1920, 1080, "9:16", 0, 10, frames or [], config=config)


@pytest.mark.parametrize(
    "layout,count", [("stacked", 2), ("side-by-side", 2), ("grid", 3), ("grid", 4)]
)
@pytest.mark.parametrize("ratio", [*RATIOS, "Original"])
def test_panels_tile_output_without_gaps_and_keep_crops_in_bounds(layout, count, ratio):
    config = RenderConfig.model_validate(
        {
            "layout": layout,
            "panels": [{"subject": f"person-{index + 1}"} for index in range(count)],
        }
    )
    plan = plan_composition(1920, 1080, ratio, 0, 10, [], config=config)
    assert (
        sum(panel.width * panel.height for panel in plan.panels)
        == plan.output_width * plan.output_height
    )
    for index, panel in enumerate(plan.panels):
        assert all(value % 2 == 0 for value in (panel.x, panel.y, panel.width, panel.height))
        assert panel.x + panel.width <= plan.output_width
        assert panel.y + panel.height <= plan.output_height
        assert panel.output_width == panel.width and panel.output_height == panel.height
        assert abs(panel.crop_width / panel.crop_height - panel.width / panel.height) < 0.02
        assert all(
            0 <= key.x <= 1920 - panel.crop_width and 0 <= key.y <= 1080 - panel.crop_height
            for key in panel.keyframes
        )
        for other in plan.panels[index + 1 :]:
            assert (
                panel.x + panel.width <= other.x
                or other.x + other.width <= panel.x
                or panel.y + panel.height <= other.y
                or other.y + other.height <= panel.y
            )


def test_four_panels_use_distinct_persistent_people_during_brief_detection_loss():
    faces = speakers()
    frames = [
        FaceFrame(
            timestamp=index / 3, faces=faces[1:] if index % 10 == 1 else list(reversed(faces))
        )
        for index in range(30)
    ]
    plan = composition("grid", 4, frames)
    assert [[sample["center_x"] for sample in panel.subjects] for panel in plan.panels] == [
        [face.center_x] * (27 if index == 0 else 30) for index, face in enumerate(faces)
    ]
    assert len({panel.keyframes[0].x for panel in plan.panels}) == 4
    assert plan.quality["score"] == min(panel.quality["score"] for panel in plan.panels)
    assert plan.quality["all_panels_validated"]


def test_missing_person_has_manual_fallback_and_independent_zoom():
    faces = speakers(2)
    frames = [FaceFrame(timestamp=index / 3, faces=faces) for index in range(30)]
    plan = composition(
        "grid",
        4,
        frames,
        panels=[
            {"subject": "person-1"},
            {"subject": "person-2"},
            {"subject": "person-3"},
            {"subject": "person-4", "anchor_x": 0.7, "anchor_y": 0.4, "zoom": 2},
        ],
    )
    assert plan.panels[2].warnings and not plan.panels[2].quality["validated"]
    assert plan.panels[3].mode == "MANUAL"
    assert plan.panels[3].crop_width < plan.panels[2].crop_width
    assert not plan.quality["all_panels_validated"]
    empty = composition("stacked", 2)
    assert empty.panels[0].keyframes[0].x < empty.panels[1].keyframes[0].x
    assert len(empty.warnings) == 2


def test_single_layout_preserves_existing_manual_crop_with_saved_panels():
    config = RenderConfig.model_validate(
        {"anchor_x": 0.3, "anchor_y": 0.4, "zoom": 1.4, "panels": [{"subject": "person-1"}]}
    )
    expected = plan_crop(1920, 1080, "9:16", 0, 10, [], manual_anchor=(0.3, 0.4), zoom=1.4)
    assert plan_composition(1920, 1080, "9:16", 0, 10, [], config=config) == expected


@pytest.mark.parametrize("count,layout", [(1, "single"), (2, "stacked"), (3, "grid"), (4, "grid")])
def test_auto_collage_chooses_layout_from_detected_people(count, layout):
    frames = [FaceFrame(timestamp=i / 3, faces=speakers(count)) for i in range(30)]
    plan = plan_composition(1920, 1080, "9:16", 0, 10, frames, config=RenderConfig(layout="auto"))
    assert plan.layout == layout
    assert len(plan.panels) == (0 if count == 1 else count)


def test_auto_collage_handles_closeups_missing_faces_and_detector_glitches():
    cfg = RenderConfig(layout="auto")
    for frames in [
        [],
        [
            FaceFrame(timestamp=i / 3, faces=speakers(1) if i != 4 else speakers(3))
            for i in range(30)
        ],
    ]:
        assert plan_composition(1920, 1080, "9:16", 0, 10, frames, config=cfg).layout == "single"
    frames = [FaceFrame(timestamp=i / 3, faces=[speakers(2)[i % 2]]) for i in range(30)]
    assert plan_composition(1920, 1080, "9:16", 0, 10, frames, config=cfg).layout == "single"


def test_auto_collage_keeps_a_lower_confidence_person_at_the_source_edge():
    faces = [
        Face(confidence=0.69, x=0.01, y=0.25, w=0.18, h=0.4, center_x=0.1, center_y=0.45),
        Face(confidence=0.94, x=0.47, y=0.2, w=0.16, h=0.35, center_x=0.55, center_y=0.375),
    ]
    frames = [FaceFrame(timestamp=i / 3, faces=faces) for i in range(12)]
    plan = plan_composition(
        1920,
        1080,
        "9:16",
        0,
        4,
        frames,
        config=RenderConfig(layout="auto", minimum_framing_score=90),
    )
    assert plan.layout == "stacked" and len(plan.panels) == 2
    assert plan.panels[0].quality["score"] < 90, "An off-center visible face must still get a panel"
    assert plan.panels[0].crop_width < 1000, "Panels should focus on individual people"
    assert plan.panels[0].keyframes[0].x < plan.panels[1].keyframes[0].x
    assert plan.quality["collage_detector"] == COLLAGE_DETECTOR_VERSION


@pytest.mark.parametrize("duplicates", [2, 4])
def test_auto_collage_does_not_make_panels_from_duplicate_head_detections(duplicates):
    face = speakers(1)[0]
    faces = [
        face.model_copy(
            update={"x": face.x + index * 0.005, "center_x": face.center_x + index * 0.005}
        )
        for index in range(duplicates)
    ]
    frames = [FaceFrame(timestamp=i / 3, faces=faces) for i in range(30)]
    plan = plan_composition(1920, 1080, "9:16", 0, 10, frames, config=RenderConfig(layout="auto"))
    assert plan.layout == "single" and not plan.panels


def test_auto_collage_does_not_assign_two_fragments_of_one_person_to_panels():
    left, right = speakers(2)
    moved = left.model_copy(update={"x": left.x + 0.19, "center_x": left.center_x + 0.19})
    frames = [
        FaceFrame(timestamp=i / 3, faces=[left if i < 15 else moved, right]) for i in range(30)
    ]
    plan = plan_composition(1920, 1080, "9:16", 0, 10, frames, config=RenderConfig(layout="auto"))
    assert len(plan.panels) == 2
    assert {sample["center_x"] for sample in plan.panels[1].subjects} == {right.center_x}


def test_auto_collage_uses_alternative_layout_when_wide_crops_repeat_heads():
    faces = [
        Face(confidence=0.95, x=x - 0.05, y=0.2, w=0.1, h=0.35, center_x=x, center_y=0.375)
        for x in (0.4, 0.6)
    ]
    frames = [FaceFrame(timestamp=i / 3, faces=faces) for i in range(12)]
    plan = plan_composition(1080, 1920, "9:16", 0, 4, frames, config=RenderConfig(layout="auto"))
    assert plan.layout == "side-by-side" and len(plan.panels) == 2
    for index, panel in enumerate(plan.panels):
        key = panel.keyframes[0]
        assert key.x <= faces[index].center_x * 1080 < key.x + panel.crop_width
        assert not key.x <= faces[1 - index].center_x * 1080 < key.x + panel.crop_width


def test_auto_collage_falls_back_when_people_cannot_have_separate_crops():
    faces = [
        Face(confidence=0.95, x=x - 0.12, y=0.2, w=0.24, h=0.4, center_x=x, center_y=0.4)
        for x in (0.43, 0.57)
    ]
    frames = [FaceFrame(timestamp=i / 3, faces=faces) for i in range(12)]
    plan = plan_composition(1920, 1080, "9:16", 0, 4, frames, config=RenderConfig(layout="auto"))
    assert plan.layout == "single" and not plan.panels


def test_auto_collage_changes_at_shots_and_keeps_a_single_person_fullscreen():
    frames = [FaceFrame(timestamp=i / 3, faces=speakers(1 if i < 15 else 2)) for i in range(30)]
    plan = plan_composition(
        1920, 1080, "9:16", 0, 10, frames, [5], config=RenderConfig(layout="auto")
    )
    assert plan.layout == "auto"
    assert [(scene.start, scene.end, scene.layout) for scene in plan.scenes] == [
        (0, 5, "single"),
        (5, 10, "stacked"),
    ]
    assert len(plan.scenes[1].panels) == 2


def test_auto_collage_changes_when_a_second_person_enters_without_a_camera_cut():
    frames = [FaceFrame(timestamp=i / 3, faces=speakers(1 if i < 15 else 2)) for i in range(30)]
    plan = plan_composition(1920, 1080, "9:16", 0, 10, frames, config=RenderConfig(layout="auto"))
    assert [scene.layout for scene in plan.scenes] == ["single", "stacked"]
    assert plan.scenes[0].end == plan.scenes[1].start


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_real_auto_collage_renders_distinct_people_when_stacked_crops_would_repeat(tmp_path):
    source = tmp_path / "portrait.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=360x640:d=1,drawbox=x=180:y=0:w=180:h=640:color=blue:t=fill",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
    )
    faces = [
        Face(confidence=0.95, x=x - 0.05, y=0.2, w=0.1, h=0.35, center_x=x, center_y=0.375)
        for x in (0.4, 0.6)
    ]
    frames = [FaceFrame(timestamp=i / 3, faces=faces) for i in range(3)]
    config = RenderConfig(layout="auto", quality="Draft", normalize_audio=False)
    plan = plan_composition(360, 640, "9:16", 0, 1, frames, config=config)
    assert plan.layout == "side-by-side"
    output = tmp_path / "output.mp4"
    render(
        source,
        output,
        tmp_path / "thumbnail.jpg",
        plan,
        0,
        1,
        [],
        CaptionConfig(enabled=False),
        OverlayConfig(),
        config,
    )
    info = probe(output)
    assert info.has_audio and abs(info.duration_ms - 1000) < 70
    frame = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(output), "-frames:v", "1", str(frame)],
        check=True,
    )
    with Image.open(frame) as picture:
        for x, expected in [(0.25, (255, 0, 0)), (0.75, (0, 0, 255))]:
            actual = picture.getpixel((round(picture.width * x), picture.height // 2))[:3]
            assert all(abs(a - b) < 25 for a, b in zip(actual, expected, strict=True))


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_real_automatic_collage_switches_layout_without_cutting_audio_or_duration(tmp_path):
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=640x360:d=1.5,drawbox=x=320:y=0:w=320:h=360:color=blue:t=fill",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
    )
    faces = speakers(2)
    frames = [FaceFrame(timestamp=i / 30, faces=faces[:1] if i < 20 else faces) for i in range(45)]
    cfg = RenderConfig(layout="auto", quality="Draft", normalize_audio=False)
    plan = plan_composition(640, 360, "9:16", 0.2, 1.2, frames, [2 / 3], config=cfg)
    assert [scene.layout for scene in plan.scenes] == ["single", "stacked"]
    output, thumbnail = tmp_path / "output.mp4", tmp_path / "thumbnail.jpg"
    render(
        source,
        output,
        thumbnail,
        plan,
        0.2,
        1.2,
        [],
        CaptionConfig(enabled=False),
        OverlayConfig(),
        cfg,
    )
    info = probe(output)
    assert abs(info.duration_ms - 1000) < 70 and info.has_audio
    for time, colors in [(0.1, [(255, 0, 0), (255, 0, 0)]), (0.8, [(255, 0, 0), (0, 0, 255)])]:
        frame = tmp_path / f"frame-{time}.png"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                str(time),
                "-i",
                str(output),
                "-frames:v",
                "1",
                str(frame),
            ],
            check=True,
        )
        with Image.open(frame) as picture:
            for y, expected in zip((0.25, 0.75), colors, strict=True):
                actual = picture.getpixel((picture.width // 2, round(picture.height * y)))[:3]
                assert all(abs(a - b) < 25 for a, b in zip(actual, expected, strict=True)), (
                    actual,
                    expected,
                )


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize(
    "layout,count", [("stacked", 2), ("side-by-side", 2), ("grid", 3), ("grid", 4)]
)
def test_real_split_render_distinct_regions_audio_caption_and_logo(tmp_path, layout, count):
    source = tmp_path / "source.mp4"
    # Four colored vertical regions stand in for four people in ONE video.
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=640x360:d=1.4,drawbox=x=160:y=0:w=160:h=360:color=green:t=fill,drawbox=x=320:y=0:w=160:h=360:color=blue:t=fill,drawbox=x=480:y=0:w=160:h=360:color=yellow:t=fill",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1.4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
    )
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (40, 40), (255, 255, 255, 255)).save(logo)
    config = RenderConfig.model_validate(
        {
            "quality": "Draft",
            "layout": layout,
            "normalize_audio": False,
            "panels": [
                {
                    "subject": f"person-{index + 1}",
                    "anchor_x": (index + 0.5) / 4,
                    "anchor_y": 0.5,
                    "zoom": 3,
                }
                for index in range(count)
            ],
        }
    )
    plan = plan_composition(640, 360, "4:5", 0.2, 1.2, [], config=config)
    output, thumbnail = tmp_path / "output.mp4", tmp_path / "thumbnail.jpg"
    render(
        source,
        output,
        thumbnail,
        plan,
        0.2,
        1.2,
        [Segment(start=0.2, end=1.2, text="Shared caption")],
        CaptionConfig(animation="none"),
        OverlayConfig(logo_position="top-left"),
        config,
        logo=logo,
    )
    info = probe(output)
    assert (info.width, info.height) == (540, 674)
    assert abs(info.duration_ms - 1000) < 100 and info.has_audio
    streams = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)]
        )
    )["streams"]
    assert sum(stream["codec_type"] == "audio" for stream in streams) == 1
    frame = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "0.4", "-i", str(output), "-frames:v", "1", str(frame)],
        check=True,
    )
    with Image.open(frame) as picture:
        for panel, expected in zip(
            plan.panels, [(255, 0, 0), (0, 128, 0), (0, 0, 255), (255, 255, 0)], strict=False
        ):
            x = round((panel.x + panel.width / 2) / plan.output_width * picture.width)
            y = round((panel.y + panel.height / 2) / plan.output_height * picture.height)
            actual = picture.getpixel((x, y))[:3]
            assert all(abs(a - b) < 25 for a, b in zip(actual, expected, strict=True)), (
                actual,
                expected,
            )
        # The logo is placed once on the final composition.
        assert min(picture.getpixel((30, 30))[:3]) > 225
        # White glyphs sit on the complete canvas below all crop/composite work.
        caption_area = picture.crop((100, 465, 440, 575)).convert("RGB")
        assert sum(min(pixel) > 225 for pixel in caption_area.getdata()) > 25
    assert thumbnail.stat().st_size > 100
