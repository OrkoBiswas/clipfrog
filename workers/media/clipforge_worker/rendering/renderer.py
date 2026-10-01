from collections.abc import Callable
from pathlib import Path

from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig, RenderConfig

from clipforge_worker.media.ffmpeg import ffmpeg
from clipforge_worker.reframing.planner import CropPlan
from clipforge_worker.rendering.captions import write_ass
from clipforge_worker.transcription.base import Segment


def coordinate(plan: CropPlan, axis: str) -> str:
    keys = plan.keyframes
    expression = str(getattr(keys[-1], axis))
    for previous, current in reversed(list(zip(keys, keys[1:], strict=False))):
        left, right = getattr(previous, axis), getattr(current, axis)
        if current.cut or current.time <= previous.time:
            value = str(left)
        else:
            value = f"{left}+({right - left})*max(0,min(1,(t-{previous.time:.4f})/{current.time - previous.time:.4f}))"
        expression = f"if(lt(t,{current.time:.4f}),{value},{expression})"
    return expression


def render(
    source: Path,
    output: Path,
    thumbnail: Path,
    plan: CropPlan,
    start: float,
    end: float,
    segments: list[Segment],
    captions: CaptionConfig,
    overlay: OverlayConfig,
    config: RenderConfig,
    check_cancel: Callable[[], None] | None = None,
    logo: Path | None = None,
) -> None:
    root = output.parent
    scale = 0.5 if config.quality == "Draft" else 1
    width, height = (
        int(plan.output_width * scale) // 2 * 2,
        int(plan.output_height * scale) // 2 * 2,
    )
    write_ass(root / "captions.ass", segments, start, end, width, height, captions, overlay)
    filters = [
        f"crop={plan.crop_width}:{plan.crop_height}:x='{coordinate(plan, 'x')}':y='{coordinate(plan, 'y')}'",
        f"scale={width}:{height}:flags=lanczos",
        "setsar=1",
        "fps=30",
    ]
    if captions.enabled or overlay.title or overlay.watermark:
        filters.append("ass=captions.ass")
    args = [
        "-protocol_whitelist",
        "file,pipe",
        "-ss",
        str(start),
        "-i",
        str(source.resolve()),
    ]
    if logo and overlay.logo_enabled:
        margin = round(min(width, height) * overlay.logo_margin)
        x = (
            str(margin)
            if overlay.logo_position.endswith("left")
            else ("(W-w)/2" if overlay.logo_position.endswith("center") else f"W-w-{margin}")
        )
        y = (
            str(margin)
            if overlay.logo_position.startswith("top")
            else ("(H-h)/2" if overlay.logo_position.startswith("middle") else f"H-h-{margin}")
        )
        if overlay.logo_x is not None and overlay.logo_y is not None:
            x, y = (
                f"max({margin},min(W-w-{margin},W*{overlay.logo_x}))",
                f"max({margin},min(H-h-{margin},H*{overlay.logo_y}))",
            )
        graph = f"[0:v]{','.join(filters)}[video];[1:v]scale={round(width * overlay.logo_size)}:{round(height * min(0.3, overlay.logo_size * 0.75))}:force_original_aspect_ratio=decrease,format=rgba,colorchannelmixer=aa={overlay.logo_opacity}[logo];[video][logo]overlay=x='{x}':y='{y}':eof_action=repeat[out]"
        args += ["-i", str(logo.resolve()), "-filter_complex", graph, "-map", "[out]"]
    else:
        args += ["-map", "0:v:0", "-vf", ",".join(filters)]
    args += [
        "-t",
        str(end - start),
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18" if config.quality == "High" else "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-map_metadata",
        "-1",
        "-threads",
        "2",
    ]
    if config.normalize_audio:
        args += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    ffmpeg([*args, str(output.resolve())], cwd=root, check_cancel=check_cancel)
    ffmpeg(
        [
            "-ss",
            str(min(1, (end - start) / 2)),
            "-i",
            str(output.resolve()),
            "-frames:v",
            "1",
            "-vf",
            "scale=360:-2",
            str(thumbnail.resolve()),
        ],
        check_cancel=check_cancel,
    )
