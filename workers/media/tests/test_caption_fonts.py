import re
import shutil
import subprocess
from pathlib import Path

import pytest
from clipforge_api.caption_fonts import caption_font_catalog, caption_variant
from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig
from clipforge_worker.rendering.captions import (
    WORD_ANIMATIONS,
    caption_font,
    caption_lines,
    entrance_tags,
    word_motion_tags,
    write_ass,
)
from clipforge_worker.transcription.base import Segment, Word
from PIL import Image, ImageChops
from pydantic import ValidationError


@pytest.mark.parametrize("weight", range(100, 1000, 100))
def test_complete_weight_range_round_trips(weight):
    config = CaptionConfig(font="Urbanist", weight=weight, italic=True, font_width=125)
    assert config.weight == weight
    assert config.italic is True
    assert CaptionConfig.model_validate(config.model_dump()) == config


@pytest.mark.parametrize(
    "font", ["Inter", "Poppins", "Oswald", "Roboto Condensed", "Playfair Display"]
)
def test_expanded_font_families_are_supported(font):
    assert CaptionConfig(font=font).font == font


def test_legacy_regular_only_font_normalizes_to_real_face():
    config = CaptionConfig(font="Bebas Neue", weight=700, italic=True)
    assert config.weight == 400
    assert config.italic is False


@pytest.mark.parametrize(
    "settings",
    [
        {"weight": 450},
        {"font_width": 74},
        {"font_width": 151},
        {"font_width": float("nan")},
        {"font": r"Unknown,\b900"},
    ],
)
def test_invalid_font_settings_are_rejected(settings):
    with pytest.raises(ValidationError):
        CaptionConfig.model_validate(settings)


def test_every_catalog_variant_can_be_selected_without_synthetic_styles():
    families = caption_font_catalog()
    assert len(families) >= 16
    for family, details in families.items():
        for face in details["variants"]:
            config = CaptionConfig(font=family, weight=face["weight"], italic=face["italic"])
            assert (config.weight, config.italic) == (face["weight"], face["italic"])
            assert caption_variant(family, config.weight, config.italic) == face


@pytest.mark.parametrize("weight,italic", [(500, False), (900, False), (500, True)])
def test_ass_uses_exact_native_face_and_numeric_weight(tmp_path, weight, italic):
    output = tmp_path / "caption.ass"
    config = CaptionConfig(font="Urbanist", weight=weight, italic=italic, font_width=125)
    write_ass(
        output,
        [Segment(start=0, end=1, text="Medium and black")],
        0,
        1,
        1080,
        1920,
        config,
        OverlayConfig(),
    )
    row = next(
        line for line in output.read_text().splitlines() if line.startswith("Style: Caption,")
    )
    values = row.split(",")
    assert values[1] == caption_variant("Urbanist", weight, italic)["family"]
    assert values[7:9] == [str(weight), "-1" if italic else "0"]
    assert values[11:13] == ["125", "100"]


@pytest.mark.parametrize(
    "animation", ["word-pop", "zoom-in", "zoom-out", "tilt", "stretch", "stamp", "bounce"]
)
def test_entrance_animation_settles_at_requested_width(animation):
    config = CaptionConfig(font_width=125, animation=animation)
    tags = entrance_tags(config, 600, 1080, 1920, 540, 900, 54, 1, 300)
    assert re.findall(r"\\fscx([\d.]+)", tags)[-1] == "125"


@pytest.mark.parametrize("animation", sorted(WORD_ANIMATIONS))
def test_word_animation_preserves_width_and_active_scale(animation):
    tags = word_motion_tags(animation, 540, 900, 54, 600, 1.2, 125)
    assert float(re.findall(r"\\fscx([\d.]+)", tags)[-1]) == 150
    assert float(re.findall(r"\\fscy([\d.]+)", tags)[-1]) == 120


def test_wide_text_wraps_earlier_at_both_render_resolutions():
    words = [
        Word(start=i, end=i + 1, text=word)
        for i, word in enumerate("make every moment count today".split())
    ]
    normal = CaptionConfig(size=100, width=0.5, max_chars_per_line=80, font_width=100)
    wide = normal.model_copy(update={"font_width": 150})
    assert len(caption_lines(words, wide, 1080)) > len(caption_lines(words, normal, 1080))
    assert caption_lines(words, wide, 1080) == caption_lines(words, wide, 540)


def test_word_box_geometry_is_not_stretched_twice(tmp_path):
    output = tmp_path / "caption.ass"
    write_ass(
        output,
        [Segment(start=0, end=1, text="Wide")],
        0,
        1,
        1080,
        1920,
        CaptionConfig(font="Urbanist", font_width=150, animation="word-pill", active_scale=1),
        OverlayConfig(),
    )
    rows = [line for line in output.read_text().splitlines() if line.startswith("Dialogue:")]
    box = next(line for line in rows if r"\p1" in line)
    text = next(line for line in rows if line.endswith("Wide"))
    assert re.findall(r"\\fscx([\d.]+)", box)[-1] == "100.00"
    assert re.findall(r"\\fscx([\d.]+)", text)[-1] == "150.00"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_real_export_distinguishes_medium_black_italic_and_wide(tmp_path):
    # Copy only the chosen native faces, so this verifies bundled fonts on both
    # Windows (DirectWrite) and the production Linux worker (fontconfig).
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    font_root = Path(__file__).resolve().parents[3] / "assets" / "fonts"
    for weight, italic in [(500, False), (900, False), (500, True)]:
        variant = caption_variant("Urbanist", weight, italic)
        source = font_root / variant["file"]
        if not source.is_file():
            source = Path(
                subprocess.check_output(
                    ["fc-match", "-f", "%{file}", variant["family"]], text=True
                ).strip()
            )
        shutil.copyfile(source, fonts / source.name)
    pictures = []
    for weight, italic, font_width in [
        (500, False, 100),
        (900, False, 100),
        (500, True, 100),
        (500, False, 150),
    ]:
        caption_font("Urbanist", weight, italic, 70)
        config = CaptionConfig(
            font="Urbanist",
            weight=weight,
            italic=italic,
            font_width=font_width,
            size=110,
            y=0.5,
            outline=0,
            shadow=0,
            animation="none",
        )
        write_ass(
            tmp_path / "caption.ass",
            [Segment(start=0, end=1, text="WIDE")],
            0,
            1,
            640,
            360,
            config,
            OverlayConfig(),
        )
        rendered = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "info",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=640x360:d=1",
                "-vf",
                "ass=caption.ass:fontsdir=fonts",
                "-frames:v",
                "1",
                "-y",
                "frame.png",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        # The native family must resolve, instead of silently falling back.
        family = caption_variant("Urbanist", weight, italic)["family"]
        selected = [line for line in rendered.stderr.splitlines() if "fontselect:" in line]
        assert any(family in line and "Clipfrog" in line.split("->")[-1] for line in selected)
        with Image.open(tmp_path / "frame.png") as frame:
            pictures.append(frame.convert("RGB"))
    regular, black, italic, wide = pictures
    assert all(picture.getbbox() for picture in pictures)
    assert ImageChops.difference(regular, black).getbbox()
    assert ImageChops.difference(regular, italic).getbbox()
    regular_bounds, wide_bounds = regular.getbbox(), wide.getbbox()
    assert wide_bounds[2] - wide_bounds[0] > (regular_bounds[2] - regular_bounds[0]) * 1.4
