import shutil
import subprocess

import pytest
from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig, RenderConfig
from clipforge_worker.media.probe import probe
from clipforge_worker.reframing.planner import RATIOS, plan_crop
from clipforge_worker.rendering.captions import write_ass
from clipforge_worker.rendering.renderer import render
from clipforge_worker.transcription.base import Segment, Word
from PIL import Image


def test_caption_timing_safe_zones_and_override_escaping(tmp_path):
    path = tmp_path / "captions.ass"
    segments = [
        Segment(
            start=10,
            end=12,
            text="Hello",
            words=[
                Word(start=10, end=11, text=r"{\pos(0,0)}Hello"),
                Word(start=11, end=12, text="world"),
            ],
        )
    ]
    write_ass(path, segments, 10, 12, 1080, 1920, CaptionConfig(style="Karaoke"), OverlayConfig())
    text = path.read_text(encoding="utf-8")
    assert r"\pos(0,0)" not in text
    assert r"{\k100}" not in text
    assert "0:00:00.00,0:00:02.00" in text
    assert ",326,1" in text
    write_ass(path, segments, 10, 12, 1080, 1920, CaptionConfig(enabled=False), OverlayConfig())
    assert "Dialogue:" not in path.read_text(encoding="utf-8")


def test_basic_caption_preserves_transcript_text(tmp_path):
    path = tmp_path / "wrapped.ass"
    segment = Segment(
        start=0,
        end=2,
        text="abcd, é😊xy!",
        words=[
            Word(start=0, end=1, text="abcd,"),
            Word(start=1, end=2, text="é😊xy!"),
        ],
    )
    config = CaptionConfig(punctuation=False, remove_special_characters=True, max_chars_per_line=4)
    write_ass(path, [segment], 0, 2, 1080, 1920, config, OverlayConfig())
    dialogues = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Dialogue:")
    ]
    assert len(dialogues) == 1
    assert r"abcd\Néxy" in dialogues[0]


def test_caption_schema_preserves_selected_fonts():
    assert CaptionConfig(font="Bebas Neue").font == "Bebas Neue"


def test_brand_colors_title_style_and_watermark_position(tmp_path):
    path = tmp_path / "brand.ass"
    write_ass(
        path,
        [],
        0,
        1,
        1080,
        1920,
        CaptionConfig(primary_color="#123456", highlight_color="#ABCDEF"),
        OverlayConfig(
            title="Brand", title_style="Boxed", logo_position="bottom-left", watermark="Mark"
        ),
    )
    text = path.read_text()
    assert "&H00563412,&H00EFCDAB" in text
    title = next(line for line in text.splitlines() if line.startswith("Style: Title"))
    assert ",0,0,3,3,1,8," in title
    watermark = next(line for line in text.splitlines() if line.startswith("Style: Watermark"))
    assert ",1,1,0,1," in watermark


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize(
    "position",
    [
        f"{vertical}-{horizontal}"
        for vertical in ["top", "middle", "bottom"]
        for horizontal in ["left", "center", "right"]
    ],
)
def test_real_logo_position_and_transparency(tmp_path, position):
    source, logo = tmp_path / "source.mp4", tmp_path / "logo.png"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
    )
    image = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    for x in range(30, 70):
        for y in range(30, 70):
            image.putpixel((x, y), (0, 0, 0, 0))
    image.save(logo)
    output = tmp_path / "output.mp4"
    render(
        source,
        output,
        tmp_path / "thumbnail.jpg",
        plan_crop(320, 240, "1:1", 0, 1, []),
        0,
        1,
        [],
        CaptionConfig(enabled=False),
        OverlayConfig(logo_position=position),
        RenderConfig(quality="Draft"),
        logo=logo,
    )
    frame = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1", str(frame)], check=True
    )
    with Image.open(frame) as picture:
        width, height = picture.size
        margin, side = round(width * 0.04), round(height * 0.12)
        x = (
            margin
            if position.endswith("left")
            else (width - side) // 2
            if position.endswith("center")
            else width - margin - side
        )
        y = (
            margin
            if position.startswith("top")
            else (height - side) // 2
            if position.startswith("middle")
            else height - margin - side
        )
        red = picture.getpixel((x + 8, y + 8))
        hole = picture.getpixel((x + side // 2, y + side // 2))
        assert red[0] > 200 and red[2] < 40
        assert hole[2] > 200 and hole[0] < 40


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("ratio", ["9:16", "16:9", "1:1"])
def test_custom_logo_opacity_aspect_and_margin(tmp_path, ratio):
    source, logo = tmp_path / "source.mp4", tmp_path / "logo.png"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=640x360:d=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
    )
    Image.new("RGBA", (200, 100), (255, 0, 0, 255)).save(logo)
    output = tmp_path / "out.mp4"
    plan = plan_crop(640, 360, ratio, 0, 1, [])
    render(
        source,
        output,
        tmp_path / "thumb.jpg",
        plan,
        0,
        1,
        [],
        CaptionConfig(enabled=False),
        OverlayConfig(logo_x=0.2, logo_y=0.3, logo_size=0.2, logo_opacity=0.5, logo_margin=0.05),
        RenderConfig(quality="Draft"),
        logo=logo,
    )
    frame = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1", str(frame)], check=True
    )
    with Image.open(frame) as image:
        red, green, blue = image.getpixel((round(image.width * 0.23), round(image.height * 0.32)))[
            :3
        ]
        assert 90 < red < 160 and green < 30 and 90 < blue < 160


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("ratio", [*RATIOS, "Original"])
def test_real_mp4_all_ratios(tmp_path, ratio):
    source, output, thumbnail = (
        tmp_path / "source.mp4",
        tmp_path / "output.mp4",
        tmp_path / "thumb.jpg",
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=1",
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
    plan = plan_crop(320, 240, ratio, 0, 1, [])
    render(
        source,
        output,
        thumbnail,
        plan,
        0,
        1,
        [Segment(start=0, end=1, text="Visible caption")],
        CaptionConfig(),
        OverlayConfig(),
        RenderConfig(quality="Draft"),
    )
    info = probe(output)
    assert info.width == int(plan.output_width * 0.5) // 2 * 2
    assert info.height == int(plan.output_height * 0.5) // 2 * 2
    assert info.has_audio and abs(info.duration_ms - 1000) < 100
    assert thumbnail.stat().st_size > 100
