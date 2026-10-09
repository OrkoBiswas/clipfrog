import shutil
import subprocess
from typing import get_args

import pytest
from clipforge_api.clip_schemas import CaptionAnimation, CaptionConfig, OverlayConfig
from clipforge_worker.rendering.captions import caption_lines, write_ass
from clipforge_worker.transcription.base import Segment, Word
from PIL import Image, ImageChops

ANIMATIONS = list(get_args(CaptionAnimation))


@pytest.mark.parametrize(
    "animation",
    ["mogrt-pack1-01", "mogrt-pack1-04", "blue-slice", "blue-echo"],
)
def test_removed_animations_normalize_to_word_pop(animation):
    assert CaptionConfig(animation=animation).animation == "word-pop"


def test_caption_layout_is_independent_of_render_resolution():
    words = [
        Word(start=i, end=i + 1, text=word)
        for i, word in enumerate("make every moment count today".split())
    ]
    config = CaptionConfig(size=54, width=0.6)
    assert caption_lines(words, config, 1080) == caption_lines(words, config, 540)


def test_build_words_follow_actual_timestamps_and_preserve_pauses(tmp_path):
    output = tmp_path / "caption.ass"
    write_ass(
        output,
        [
            Segment(
                start=5,
                end=9,
                text="Wait now",
                words=[Word(start=5, end=5.3, text="Wait"), Word(start=7.2, end=9, text="now")],
            )
        ],
        5,
        9,
        540,
        960,
        CaptionConfig(animation="word-rise", word_display="build"),
        OverlayConfig(),
    )
    events = [line for line in output.read_text().splitlines() if line.startswith("Dialogue")]
    future = [line for line in events if line.endswith("now")]
    assert len(future) == 1
    assert future[0].split(",")[1:3] == ["0:00:02.20", "0:00:04.00"]
    first = next(
        line for line in events if line.endswith("Wait") and line.split(",")[1] == "0:00:00.00"
    )
    assert first.split(",")[2] == "0:00:00.30"
    assert r"\move(" in first and r"\move(" in future[0]


@pytest.mark.parametrize("animation", ANIMATIONS)
@pytest.mark.parametrize("display", ["full", "build", "single"])
def test_caption_text_and_effect_events_never_span_a_pause(tmp_path, animation, display):
    output = tmp_path / "captions.ass"
    write_ass(
        output,
        [
            Segment(
                start=0,
                end=4,
                text="Before after",
                words=[
                    Word(start=0.2, end=1, text="Before"),
                    Word(start=2.5, end=3.5, text="after"),
                ],
            )
        ],
        0,
        4,
        540,
        960,
        CaptionConfig(animation=animation, word_display=display, background=True),
        OverlayConfig(),
    )
    events = [
        line.split(",", 9)
        for line in output.read_text().splitlines()
        if line.startswith("Dialogue")
    ]
    assert events
    for event in events:
        assert (event[1] >= "0:00:00.20" and event[2] <= "0:00:01.00") or (
            event[1] >= "0:00:02.50" and event[2] <= "0:00:03.50"
        ), "Text, word effects, and backgrounds must all clear during silence"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("animation", ["none", "fade", "word-rise", "word-pill", "word-glow"])
def test_real_caption_frames_clear_and_resume_after_silence(tmp_path, animation):
    write_ass(
        tmp_path / "captions.ass",
        [
            Segment(
                start=0,
                end=4,
                text="Before after",
                words=[
                    Word(start=0.2, end=1, text="Before"),
                    Word(start=2.5, end=3.5, text="after"),
                ],
            )
        ],
        0,
        4,
        270,
        480,
        CaptionConfig(animation=animation, background=True, size=100, y=0.5),
        OverlayConfig(),
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=270x480:r=10:d=4",
            "-vf",
            "ass=captions.ass",
            "frame-%02d.png",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    assert Image.open(tmp_path / "frame-08.png").convert("RGB").getbbox() is not None
    assert Image.open(tmp_path / "frame-31.png").convert("RGB").getbbox() is not None
    for index in [1, 12, 20, 24, 38]:
        assert Image.open(tmp_path / f"frame-{index:02d}.png").convert("RGB").getbbox() is None


def test_single_word_keeps_long_word_and_original_timing(tmp_path):
    output = tmp_path / "caption.ass"
    config = CaptionConfig(
        animation="word-punch", word_display="single", size=100, max_chars_per_line=8
    )
    words = [Word(start=0, end=1.1, text="extraordinary"), Word(start=1.1, end=2, text="ideas")]
    lines = caption_lines(words, config, 540)
    assert lines[0][0][0] == words[0]
    write_ass(
        output,
        [Segment(start=0, end=2, text="extraordinary ideas", words=words)],
        0,
        2,
        540,
        960,
        config,
        OverlayConfig(),
    )
    events = [line for line in output.read_text().splitlines() if line.startswith("Dialogue")]
    assert len(events) == 2
    assert events[0].endswith("extraordinary")
    assert events[0].split(",")[1:3] == ["0:00:00.00", "0:00:01.10"]
    assert events[1].split(",")[1:3] == ["0:00:01.10", "0:00:02.00"]


@pytest.mark.parametrize("animation", ANIMATIONS)
def test_supported_animation_generates_bounded_ass(tmp_path, animation):
    output = tmp_path / "caption.ass"
    config = CaptionConfig(
        animation=animation,
        font="Urbanist",
        effect_color="#00FF88",
        animation_duration=1.2,
    )
    write_ass(
        output,
        [Segment(start=0, end=2, text=r"{\pos(0,0)} Test")],
        0,
        2,
        1080,
        1920,
        config,
        OverlayConfig(),
    )
    content = output.read_text(encoding="utf-8")
    assert r"\pos(0,0)" not in content
    assert "Urbanist" in content
    assert "&H00FFFFFF" in content
    assert r"\pos(" in content or r"\move(" in content
    assert len(content) < 15000


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("animation", ANIMATIONS)
def test_supported_animation_really_renders_and_settles(tmp_path, animation):
    config = CaptionConfig(
        animation=animation,
        animation_duration=1.0,
        size=110,
        y=0.5,
    )
    write_ass(
        tmp_path / "captions.ass",
        [Segment(start=0, end=2, text="One two")],
        0,
        2,
        540,
        960,
        config,
        OverlayConfig(),
    )
    # Render on black: differences must come from the captions, not source motion.
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=540x960:r=30:d=2",
            "-vf",
            "ass=captions.ass",
            "-frames:v",
            "60",
            "frame-%02d.png",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    early_frame = "frame-01.png" if animation == "word-pop" else "frame-04.png"
    early = Image.open(tmp_path / early_frame).convert("RGB")
    # The second word begins at 1s and gets its own entrance (up to .8s).
    settled = Image.open(tmp_path / "frame-56.png").convert("RGB")
    assert settled.getbbox() is not None, "Caption must be visible in final output"
    if animation != "none":
        assert ImageChops.difference(early, settled).getbbox() is not None, (
            "Entrance or word emphasis must visibly animate"
        )
    later = Image.open(tmp_path / "frame-59.png").convert("RGB")
    assert ImageChops.difference(settled, later).getbbox() is None, (
        "Caption must settle to a stable readable state"
    )
