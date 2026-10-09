from collections.abc import Callable
from pathlib import Path

from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig, RenderConfig

from clipforge_worker.media.ffmpeg import ffmpeg
from clipforge_worker.reframing.planner import CompositionScene, CropPlan, CropRegion
from clipforge_worker.rendering.captions import prepare_caption_fonts, write_ass
from clipforge_worker.rendering.mogrt_bridge import render_mogrt_overlay
from clipforge_worker.transcription.base import Segment


def coordinate(plan: CropRegion, axis: str) -> str:
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


def composition_graph(
    plan: CropPlan | CompositionScene,
    width: int,
    height: int,
    source: str = "0:v",
    prefix: str = "",
    output: str = "composed",
) -> str:
    """Crop branches share one decoded video and one clock; audio is mapped once."""
    count = len(plan.panels)
    pieces = [f"[{source}]split={count}" + "".join(f"[{prefix}source{i}]" for i in range(count))]
    positions = []
    for index, panel in enumerate(plan.panels):
        # Scale shared boundaries, not each width independently, to avoid seams
        # and odd pixels when Draft output rounds a half-panel dimension.
        left = round(panel.x / plan.output_width * width) // 2 * 2
        top = round(panel.y / plan.output_height * height) // 2 * 2
        right = round((panel.x + panel.width) / plan.output_width * width) // 2 * 2
        bottom = round((panel.y + panel.height) / plan.output_height * height) // 2 * 2
        pieces.append(
            f"[{prefix}source{index}]crop={panel.crop_width}:{panel.crop_height}:x='{coordinate(panel, 'x')}':y='{coordinate(panel, 'y')}',"
            f"scale={right - left}:{bottom - top}:flags=lanczos,setsar=1[{prefix}panel{index}]"
        )
        positions.append(f"{left}_{top}")
    pieces.append(
        "".join(f"[{prefix}panel{i}]" for i in range(count))
        + f"xstack=inputs={count}:layout={'|'.join(positions)}:fill=black[{output}]"
    )
    return ";".join(pieces)


def automatic_composition_graph(plan: CropPlan, width: int, height: int) -> str:
    # Keep every branch on the original clock and reuse matching layout/crop
    # sizes across camera cuts.
    groups: dict[tuple, list[CompositionScene]] = {}
    for scene in plan.scenes:
        groups.setdefault(
            (scene.layout, tuple((panel.crop_width, panel.crop_height) for panel in scene.panels)),
            [],
        ).append(scene)
    layouts = list(groups.values())
    pieces = [f"[0:v]split={len(layouts)}" + "".join(f"[scene{i}]" for i in range(len(layouts)))]
    for index, shots in enumerate(layouts):
        scene = shots[0].model_copy(deep=True)
        scene.keyframes = [
            key.model_copy(update={"time": key.time + shot.start, "cut": i == 0 or key.cut})
            for shot in shots
            for i, key in enumerate(shot.keyframes)
        ]
        for panel_index, panel in enumerate(scene.panels):
            panel.keyframes = [
                key.model_copy(update={"time": key.time + shot.start, "cut": i == 0 or key.cut})
                for shot in shots
                for i, key in enumerate(shot.panels[panel_index].keyframes)
            ]
        if scene.panels:
            pieces.append(
                composition_graph(
                    scene, width, height, f"scene{index}", f"s{index}_", f"collage{index}"
                )
            )
        else:
            pieces.append(
                f"[scene{index}]crop={scene.crop_width}:{scene.crop_height}:x='{coordinate(scene, 'x')}':y='{coordinate(scene, 'y')}',"
                f"scale={width}:{height}:flags=lanczos,setsar=1[collage{index}]"
            )
    current = "collage0"
    for index, shots in enumerate(layouts[1:], 1):
        enabled = "+".join(f"gte(t,{shot.start:.6f})*lt(t,{shot.end:.6f})" for shot in shots)
        pieces.append(
            f"[{current}][collage{index}]overlay=0:0:enable='{enabled}':eof_action=pass[active{index}]"
        )
        current = f"active{index}"
    pieces.append(f"[{current}]null[composed]")
    return ";".join(pieces)


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
    mogrt_overlay = render_mogrt_overlay(
        root / "mogrt-overlay.mov",
        segments,
        start,
        end,
        width,
        height,
        captions,
    )
    ass_captions = captions.model_copy(update={"enabled": False}) if mogrt_overlay else captions
    write_ass(root / "captions.ass", segments, start, end, width, height, ass_captions, overlay)
    filters = (
        []
        if plan.panels or plan.scenes
        else [
            f"crop={plan.crop_width}:{plan.crop_height}:x='{coordinate(plan, 'x')}':y='{coordinate(plan, 'y')}'",
            f"scale={width}:{height}:flags=lanczos",
            "setsar=1",
        ]
    )
    filters.append("fps=30")
    if captions.enabled or overlay.title or overlay.watermark:
        bundled_fonts = prepare_caption_fonts(root, ass_captions, overlay)
        filters.append("ass=captions.ass" + (":fontsdir=caption-fonts" if bundled_fonts else ""))
    args = [
        "-protocol_whitelist",
        "file,pipe",
        "-ss",
        str(start),
        "-i",
        str(source.resolve()),
    ]
    if plan.panels or plan.scenes or mogrt_overlay or (logo and overlay.logo_enabled):
        composition = (
            automatic_composition_graph(plan, width, height)
            if plan.scenes
            else (composition_graph(plan, width, height) if plan.panels else "")
        )
        graph = (
            composition + ";[composed]" if composition else "[0:v]"
        ) + f"{','.join(filters)}[video]"
        final_video = "video"
        logo_input = 1
        if mogrt_overlay:
            args += ["-i", str(mogrt_overlay.resolve())]
            graph += f";[1:v]fps=30,scale={width}:{height},format=rgba[mogrt];[video][mogrt]overlay=0:0:eof_action=pass[captioned]"
            final_video, logo_input = "captioned", 2
        if logo and overlay.logo_enabled:
            args += ["-i", str(logo.resolve())]
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
            graph += f";[{logo_input}:v]scale={round(width * overlay.logo_size)}:{round(height * min(0.3, overlay.logo_size * 0.75))}:force_original_aspect_ratio=decrease,format=rgba,colorchannelmixer=aa={overlay.logo_opacity}[logo];[{final_video}][logo]overlay=x='{x}':y='{y}':eof_action=repeat[out]"
            final_video = "out"
        args += ["-filter_complex", graph, "-map", f"[{final_video}]"]
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
