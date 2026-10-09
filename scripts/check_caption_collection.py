"""Render the gallery's exported preset manifest without a database or live projects."""

import json
import subprocess
from pathlib import Path

from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig
from clipforge_worker.rendering.captions import write_ass
from clipforge_worker.transcription.base import Segment
from PIL import Image, ImageDraw


def main() -> None:
    root = Path(".local/caption-collection")
    presets = json.loads((root / "presets.json").read_text())
    assert len(presets) >= 24
    sheet = Image.new("RGB", (1200, 6 * 290), "#101815")
    fonts = set()
    for index, preset in enumerate(presets):
        config = CaptionConfig.model_validate(preset["config"])
        fonts.add(config.font)
        family = subprocess.check_output(["fc-match", "-f", "%{family}", config.font], text=True)
        assert config.font.lower() in family.lower(), (
            f"Missing render font: {config.font} ({family})"
        )
        target = root / "renders" / preset["id"]
        target.mkdir(parents=True, exist_ok=True)
        write_ass(
            target / "captions.ass",
            [Segment(start=0, end=3, text=preset["sample"])],
            0,
            3,
            540,
            960,
            config,
            OverlayConfig(),
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x182326:s=540x960:r=30:d=3",
                "-vf",
                "ass=captions.ass",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "preview.mp4",
            ],
            cwd=target,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                "1.77",
                "-i",
                "preview.mp4",
                "-frames:v",
                "1",
                "frame.png",
            ],
            cwd=target,
            check=True,
            capture_output=True,
        )
        with Image.open(target / "frame.png") as frame:
            crop = frame.crop((0, 520, 540, 940)).resize((284, 220))
            x, y = index % 4 * 300 + 8, index // 4 * 290 + 40
            sheet.paste(crop, (x, y))
            ImageDraw.Draw(sheet).text((x, y - 24), preset["name"], fill="white")
    sheet.save(root / "render-contact-sheet.jpg")
    print(
        f"Rendered {len(presets)} real MP4s; verified {len(fonts)} installed preset font families."
    )


if __name__ == "__main__":
    main()
