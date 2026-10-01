"""Render all caption configurations and a deterministic hard-cut framing fixture."""

import subprocess
from pathlib import Path

from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig, RenderConfig
from clipforge_api.services.caption_templates import TEMPLATES
from clipforge_worker.reframing.planner import plan_crop
from clipforge_worker.rendering.renderer import render
from clipforge_worker.transcription.base import Segment, Word
from clipforge_worker.vision.face_detector import Face, FaceFrame
from PIL import Image, ImageDraw


def main():
    root = Path(".local/editor-validation").resolve()
    root.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, center in enumerate([0.3, 0.7]):
        image = Image.new("RGB", (1280, 720), (27, 36, 52))
        draw = ImageDraw.Draw(image)
        draw.ellipse(
            (int(center * 1280) - 65, 130, int(center * 1280) + 65, 310), fill=(224, 173, 126)
        )
        draw.rectangle(
            (int(center * 1280) - 105, 310, int(center * 1280) + 105, 700), fill=(61, 119, 151)
        )
        draw.ellipse((int(center * 1280) - 30, 190, int(center * 1280) - 15, 203), fill="black")
        draw.ellipse((int(center * 1280) + 15, 190, int(center * 1280) + 30, 203), fill="black")
        still = root / f"shot-{index}.png"
        image.save(still)
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-loop",
                "1",
                "-i",
                str(still),
                "-t",
                "2",
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(root / f"shot-{index}.mp4"),
            ],
            check=True,
        )
        frames.extend(
            FaceFrame(
                timestamp=index * 2 + i / 3,
                faces=[
                    Face(
                        confidence=0.99,
                        x=center - 0.05,
                        y=130 / 720,
                        w=0.1,
                        h=0.25,
                        center_x=center,
                        center_y=220 / 720,
                        eye_y=196 / 720,
                    )
                ],
            )
            for i in range(6)
        )
    source = root / "two-shots.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(root / "shot-0.mp4"),
            "-i",
            str(root / "shot-1.mp4"),
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            str(source),
        ],
        check=True,
    )
    plan = plan_crop(1280, 720, "9:16", 0, 4, frames, [2])
    assert len(plan.keyframes) == 2 and plan.keyframes[1].cut
    assert plan.quality["score"] >= 65, plan.quality
    output = root / "static-cut.mp4"
    render(
        source,
        output,
        root / "static-thumb.jpg",
        plan,
        0,
        4,
        [],
        CaptionConfig(enabled=False),
        OverlayConfig(),
        RenderConfig(quality="Draft"),
    )
    checks = []
    for index, time in enumerate([0.5, 1.8, 2.1, 3.5]):
        path = root / f"cut-check-{index}.png"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                str(time),
                "-i",
                str(output),
                "-frames:v",
                "1",
                str(path),
            ],
            check=True,
        )
        with Image.open(path) as image:
            # The annotated head remains centered on both sides of the source cut.
            pixels = image.convert("RGB")
            xs = [
                x
                for x in range(image.width)
                if (lambda p: p[0] > 150 and p[1] > 100 and p[2] < 160)(pixels.getpixel((x, 270)))
            ]
            assert xs and abs((min(xs) + max(xs)) / 2 - image.width / 2) < 8
            checks.append((min(xs), max(xs)))
    assert max(x[0] for x in checks) - min(x[0] for x in checks) < 4
    words = [
        Word(start=0.1 + i * 0.32, end=0.4 + i * 0.32, text=text)
        for i, text in enumerate("This changes everything you thought about editing".split())
    ]
    segments = [
        Segment(
            start=0.1,
            end=2.7,
            text="This changes everything you thought about editing",
            words=words,
        )
    ]
    sheet = Image.new("RGB", (5 * 220, 5 * 420), "#111827")
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(TEMPLATES):
        folder = root / item["id"]
        folder.mkdir(exist_ok=True)
        render(
            source,
            folder / "output.mp4",
            folder / "thumb.jpg",
            plan,
            0,
            3,
            segments,
            CaptionConfig.model_validate(item["config"]),
            OverlayConfig(),
            RenderConfig(quality="Draft"),
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                "0.65",
                "-i",
                str(folder / "output.mp4"),
                "-frames:v",
                "1",
                str(folder / "frame.png"),
            ],
            check=True,
        )
        with Image.open(folder / "frame.png") as image:
            image.thumbnail((210, 380))
            sheet.paste(image, (index % 5 * 220, index // 5 * 420))
        draw.text((index % 5 * 220 + 4, index // 5 * 420 + 385), item["name"], fill="white")
        print(f"Rendered {item['name']}", flush=True)
    sheet.save(root / "caption-contact-sheet.png")
    print("All 25 caption renders and static hard-cut pixel checks passed.", flush=True)


if __name__ == "__main__":
    main()
