import math
from dataclasses import dataclass, field
from functools import partial
from statistics import median
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from clipforge_worker.vision.face_detector import COLLAGE_DETECTOR_VERSION, Face, FaceFrame

if TYPE_CHECKING:
    from clipforge_api.clip_schemas import RenderConfig

RATIOS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "3:4": (1080, 1440),
    "4:3": (1440, 1080),
    "21:9": (2520, 1080),
}


class CropKeyframe(BaseModel):
    time: float
    x: int
    y: int
    cut: bool = False


class CropRegion(BaseModel):
    mode: str
    source_width: int
    source_height: int
    crop_width: int
    crop_height: int
    output_width: int
    output_height: int
    keyframes: list[CropKeyframe]
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    quality: dict = Field(default_factory=dict)
    subjects: list[dict] = Field(default_factory=list)


class PanelPlan(CropRegion):
    x: int
    y: int
    width: int
    height: int
    subject: str


class CropPlan(CropRegion):
    layout: Literal["single", "auto", "stacked", "side-by-side", "grid"] = "single"
    panels: list[PanelPlan] = Field(default_factory=list)
    scenes: list["CompositionScene"] = Field(default_factory=list)


class CompositionScene(CropRegion):
    start: float
    end: float
    layout: Literal["single", "stacked", "side-by-side", "grid"]
    panels: list[PanelPlan] = Field(default_factory=list)


@dataclass
class Track:
    samples: list[tuple[float, Face]] = field(default_factory=list)


def face_tracks(frames: list[FaceFrame]) -> list[Track]:
    """Greedy spatial association; persistence outweighs an occasional large face."""
    tracks: list[Track] = []
    for frame in frames:
        available = set(range(len(tracks)))
        for face in sorted(frame.faces, key=lambda f: -f.confidence):
            if face.confidence < 0.65 or face.w <= 0 or face.h <= 0:
                continue
            matches = [
                (
                    math.hypot(
                        face.center_x - track.samples[-1][1].center_x,
                        face.center_y - track.samples[-1][1].center_y,
                    ),
                    index,
                )
                for index, track in enumerate(tracks)
                if index in available and frame.timestamp - track.samples[-1][0] <= 2
            ]
            distance, index = min(matches, default=(1.0, -1))
            if distance < 0.18:
                tracks[index].samples.append((frame.timestamp, face))
                available.remove(index)
            else:
                tracks.append(Track([(frame.timestamp, face)]))

    return tracks


def primary_track(frames: list[FaceFrame], subject: str = "primary") -> Track | None:
    tracks = face_tracks(frames)
    if not tracks:
        return None
    if subject in {"left", "center", "right"} or subject.startswith("person-"):
        # Select a persistent track once per shot, rather than re-numbering faces
        # on each frame when a detector briefly loses one of the speakers.
        threshold = max(len(track.samples) for track in tracks) * 0.35
        ordered = sorted(
            (track for track in tracks if len(track.samples) >= threshold),
            key=lambda track: median(face.center_x for _, face in track.samples),
        )
        if subject == "center":
            return min(
                ordered,
                key=lambda track: abs(median(face.center_x for _, face in track.samples) - 0.5),
            )
        index = 0 if subject == "left" else -1 if subject == "right" else int(subject[-1]) - 1
        return ordered[index] if -len(ordered) <= index < len(ordered) else None

    def score(track: Track) -> float:
        faces = [f for _, f in track.samples]
        persistence = len(faces) / max(1, len(frames))
        size = median(f.w * f.h for f in faces)
        centrality = 1 - abs(median(f.center_x for f in faces) - 0.5)
        return persistence * 0.7 + min(1, size * 5) * 0.2 + centrality * 0.1

    return max(tracks, key=score)


def geometry(
    width: int,
    height: int,
    ratio: str,
    zoom: float = 1,
    output_size: tuple[int, int] | None = None,
) -> tuple[int, int, int, int]:
    if width < 2 or height < 2 or not 1 <= zoom <= 3:
        raise ValueError("Invalid source dimensions or crop zoom.")
    if output_size is not None:
        ow, oh = output_size
        if min(ow, oh) < 2 or ow % 2 or oh % 2:
            raise ValueError("Output dimensions must be positive, even pixels.")
    elif ratio == "Original":
        ow, oh = width // 2 * 2, height // 2 * 2
    elif ratio in RATIOS:
        ow, oh = RATIOS[ratio]
    else:
        raise ValueError("Unsupported aspect ratio.")
    target = ow / oh
    cw, ch = (
        (height * target, float(height))
        if width / height > target
        else (float(width), width / target)
    )
    return max(2, int(cw / zoom) // 2 * 2), max(2, int(ch / zoom) // 2 * 2), ow, oh


def plan_crop(
    width: int,
    height: int,
    ratio: str,
    start: float,
    end: float,
    frames: list[FaceFrame],
    scene_cuts: list[float] | None = None,
    mode: Literal["STATIC_SUBJECT_LOCK", "SCENE_AWARE_LOCK"] = "STATIC_SUBJECT_LOCK",
    manual_anchor: tuple[float, float] | None = None,
    zoom: float = 1,
    eye_line: float = 0.34,
    headroom: float = 0.08,
    subject: str = "primary",
    lock_camera: bool = True,
    minimum_hold: float = 4,
    horizontal_dead_zone: float = 0.18,
    vertical_dead_zone: float = 0.15,
    sentence_boundaries: list[float] | None = None,
    output_size: tuple[int, int] | None = None,
    fallback_anchor: tuple[float, float] = (0.5, 0.5),
) -> CropPlan:
    if end <= start:
        raise ValueError("Clip end must follow its start.")
    cw, ch, ow, oh = geometry(width, height, ratio, zoom, output_size)

    def position(cx: float, cy: float) -> tuple[int, int]:
        return (
            round(max(0, min(width - cw, cx * width - cw / 2))) // 2 * 2,
            round(max(0, min(height - ch, cy * height - ch / 2))) // 2 * 2,
        )

    if manual_anchor is not None:
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in manual_anchor):
            raise ValueError("Manual anchor must be inside the source.")
        x, y = position(*manual_anchor)
        return CropPlan(
            mode="MANUAL",
            source_width=width,
            source_height=height,
            crop_width=cw,
            crop_height=ch,
            output_width=ow,
            output_height=oh,
            keyframes=[CropKeyframe(time=0, x=x, y=y)],
            confidence=1,
        )
    boundaries = [start, *sorted(set(c for c in scene_cuts or [] if start < c < end)), end]
    keyframes: list[CropKeyframe] = []
    confidence: list[float] = []
    warnings: list[str] = []
    last_anchor = fallback_anchor
    subjects: list[dict] = []
    for left, right in zip(boundaries, boundaries[1:], strict=False):
        samples = [f for f in frames if left <= f.timestamp < right]
        track = primary_track(samples, subject)
        if track:
            # Median rejects occasional detection offsets; head sits near the upper third.
            faces = [f for _, f in track.samples]
            cx = median(f.center_x for f in faces)
            cy = median(f.eye_y if f.eye_y is not None else f.y + f.h * 0.35 for f in faces) + (
                ch / height
            ) * (0.5 - eye_line)
            deviations = [abs(f.center_x - cx) for f in faces]
            threshold = max(0.03, 3 * median(deviations))
            my = median(f.center_y for f in faces)
            mh = median(f.h for f in faces)
            reliable = [
                f
                for f in faces
                if abs(f.center_x - cx) <= threshold
                and abs(f.center_y - my) <= max(0.04, mh * 0.6)
                and 0.5 * mh <= f.h <= 1.8 * mh
            ]
            if not reliable:
                reliable = faces
            cx = median(f.center_x for f in reliable)
            # Eye-line target is constrained by estimated forehead/head and chin bounds.
            eye = median(f.eye_y if f.eye_y is not None else f.y + f.h * 0.35 for f in reliable)
            top = median(f.y - f.h * 0.12 for f in reliable) * height
            bottom = median(f.y + f.h * 1.05 for f in reliable) * height
            ideal_y = eye * height - ch * eye_line
            ideal_y = max(bottom - ch * 0.94, min(ideal_y, top - ch * headroom))
            cy = (ideal_y + ch / 2) / height
            if subject == "two-person":
                all_faces = [
                    face for frame in samples for face in frame.faces if face.confidence >= 0.65
                ]
                if all_faces:
                    cx = (min(f.x for f in all_faces) + max(f.x + f.w for f in all_faces)) / 2
                    reliable = all_faces
            subjects.extend(
                {
                    "time": timestamp - start,
                    "scene_start": left - start,
                    "subject": subject,
                    **face.model_dump(),
                }
                for timestamp, face in (
                    [(frame.timestamp, face) for frame in samples for face in frame.faces]
                    if subject == "two-person"
                    else track.samples
                )
                if face in reliable
            )
            last_anchor = (cx, cy)
            confidence.append(len(faces) / max(1, len(samples)))
        else:
            # Brief misses keep framing; longer absence falls back to source center.
            if right - left > 5 or not keyframes:
                last_anchor = fallback_anchor
            confidence.append(0)
            warnings.append("No persistent face in a shot; retained anchor or center framing used.")
        x, y = position(*last_anchor)
        keyframes.append(CropKeyframe(time=left - start, x=x, y=y, cut=left != start))
        if track and mode == "SCENE_AWARE_LOCK" and not lock_camera:
            # Conservative reframe only after a sustained large departure. Tiny motions
            # never create keyframes. Hold >=3s; median window and bounded speed avoid jitter.
            hold = left
            previous = (x, y)
            window: list[tuple[float, Face]] = []
            for timestamp, face in track.samples:
                window = [(t, f) for t, f in window if timestamp - t <= 1.5]
                window.append((timestamp, face))
                if (
                    timestamp - hold < minimum_hold
                    or len(window) < 3
                    or timestamp - window[0][0] < 1
                ):
                    continue
                if not any(
                    abs(timestamp - boundary) < 0.2 for boundary in sentence_boundaries or []
                ):
                    continue
                target_x = median(f.center_x for _, f in window)
                anchor_x = (previous[0] + cw / 2) / width
                target_y = median(f.center_y for _, f in window)
                anchor_y = (previous[1] + ch * eye_line) / height
                if (
                    abs(target_x - anchor_x) * width <= cw * horizontal_dead_zone
                    and abs(target_y - anchor_y) * height <= ch * vertical_dead_zone
                ):
                    continue
                tx, ty = position(target_x, last_anchor[1])
                if abs(tx - previous[0]) < width * 0.035:
                    continue
                # Exponential damping then velocity cap; linear interpolation by renderer.
                tx = round(previous[0] + (tx - previous[0]) * 0.65) // 2 * 2
                travel = max(1, abs(tx - previous[0]) / (width * 0.08))
                finish = min(right - 0.01, timestamp + travel)
                if finish <= timestamp:
                    continue
                tx = (
                    round(previous[0] + (tx - previous[0]) * (finish - timestamp) / travel) // 2 * 2
                )
                keyframes.extend(
                    [
                        CropKeyframe(time=timestamp - start, x=previous[0], y=previous[1]),
                        CropKeyframe(time=finish - start, x=tx, y=ty),
                    ]
                )
                previous, hold = (tx, ty), finish
    plan = CropPlan(
        mode=mode,
        source_width=width,
        source_height=height,
        crop_width=cw,
        crop_height=ch,
        output_width=ow,
        output_height=oh,
        keyframes=keyframes,
        confidence=sum(confidence) / len(confidence),
        warnings=list(dict.fromkeys(warnings)),
        subjects=subjects,
    )
    plan.quality = framing_quality(plan, eye_line, headroom)
    return plan


def panel_bounds(
    layout: str, count: int, width: int, height: int
) -> list[tuple[int, int, int, int]]:
    """Even boundaries tile the entire output, including odd half-size ratios."""
    half_width, half_height = width // 4 * 2, height // 4 * 2
    if layout == "stacked" and count == 2:
        return [(0, 0, width, half_height), (0, half_height, width, height - half_height)]
    if layout == "side-by-side" and count == 2:
        return [(0, 0, half_width, height), (half_width, 0, width - half_width, height)]
    if layout == "grid" and count in {3, 4}:
        top = (
            [(0, 0, width, half_height)]
            if count == 3
            else [(0, 0, half_width, half_height), (half_width, 0, width - half_width, half_height)]
        )
        return [
            *top,
            (0, half_height, half_width, height - half_height),
            (half_width, half_height, width - half_width, height - half_height),
        ]
    raise ValueError("Split screen requires two panels, or three to four panels in a grid.")


def plan_composition(
    width: int,
    height: int,
    ratio: str,
    start: float,
    end: float,
    frames: list[FaceFrame],
    scene_cuts: list[float] | None = None,
    *,
    config: "RenderConfig",
    sentence_boundaries: list[float] | None = None,
) -> CropPlan:
    """Use exactly the same source crops for the editor and the exported video."""
    if config.layout == "auto":
        plan = plan_automatic_collage(
            width,
            height,
            ratio,
            start,
            end,
            frames,
            scene_cuts or [],
            config=config,
            sentence_boundaries=sentence_boundaries,
        )
        plan.quality["collage_detector"] = COLLAGE_DETECTOR_VERSION
        return plan
    plan_region = partial(
        plan_crop,
        mode=config.crop_mode,
        eye_line=config.eye_line,
        headroom=config.headroom,
        lock_camera=config.lock_camera,
        minimum_hold=config.minimum_crop_hold_seconds,
        horizontal_dead_zone=config.horizontal_dead_zone,
        vertical_dead_zone=config.vertical_dead_zone,
        sentence_boundaries=sentence_boundaries,
    )
    if config.layout == "single":
        return plan_region(
            width,
            height,
            ratio,
            start,
            end,
            frames,
            scene_cuts,
            manual_anchor=(config.anchor_x, config.anchor_y)
            if config.anchor_x is not None and config.anchor_y is not None
            else None,
            zoom=config.zoom,
            subject=config.subject,
        )
    _, _, output_width, output_height = geometry(width, height, ratio)
    bounds = panel_bounds(config.layout, len(config.panels), output_width, output_height)
    panels = []
    for index, (panel_config, (x, y, panel_width, panel_height)) in enumerate(
        zip(config.panels, bounds, strict=True)
    ):
        fallback_x = (index + 0.5) / len(config.panels)
        if panel_config.subject == "left":
            fallback_x = 0.25
        elif panel_config.subject == "right":
            fallback_x = 0.75
        elif panel_config.subject == "center":
            fallback_x = 0.5
        elif panel_config.subject.startswith("person-"):
            fallback_x = min(1, (int(panel_config.subject[-1]) - 0.5) / len(config.panels))
        region = plan_region(
            width,
            height,
            ratio,
            start,
            end,
            frames,
            scene_cuts,
            manual_anchor=(panel_config.anchor_x, panel_config.anchor_y)
            if panel_config.anchor_x is not None and panel_config.anchor_y is not None
            else None,
            zoom=panel_config.zoom,
            subject=panel_config.subject,
            output_size=(panel_width, panel_height),
            fallback_anchor=(fallback_x, 0.5),
        )
        if region.warnings:
            region.warnings = [
                "Speaker was not detected in part of this clip. Check this panel or set its crop manually."
            ]
        panels.append(
            PanelPlan(
                **region.model_dump(exclude={"layout", "panels", "scenes"}),
                x=x,
                y=y,
                width=panel_width,
                height=panel_height,
                subject=panel_config.subject,
            )
        )
    assessed = [panel.quality for panel in panels if panel.quality.get("validated")]
    quality = {
        "score": min(item["score"] for item in assessed) if assessed else None,
        "validated": bool(assessed),
        "all_panels_validated": all(
            panel.quality.get("validated") or panel.mode == "MANUAL" for panel in panels
        ),
        "clipped_fraction": max((item.get("clipped_fraction", 0) for item in assessed), default=0),
        "panels": [
            {
                "index": index,
                **{key: value for key, value in panel.quality.items() if key != "samples"},
            }
            for index, panel in enumerate(panels)
        ],
        "samples": [
            {**sample, "panel_index": index}
            for index, panel in enumerate(panels)
            for sample in panel.quality.get("samples", [])
        ],
    }
    return CropPlan(
        **panels[0].model_dump(
            exclude={
                "x",
                "y",
                "width",
                "height",
                "subject",
                "mode",
                "output_width",
                "output_height",
                "confidence",
                "warnings",
                "quality",
                "subjects",
                "scenes",
            }
        ),
        mode="SPLIT_SCREEN",
        layout=config.layout,
        output_width=output_width,
        output_height=output_height,
        confidence=sum(panel.confidence for panel in panels) / len(panels),
        warnings=[
            f"Panel {index + 1}: {warning}"
            for index, panel in enumerate(panels)
            for warning in panel.warnings
        ],
        quality=quality,
        subjects=[
            {**subject, "panel_index": index}
            for index, panel in enumerate(panels)
            for subject in panel.subjects
        ],
        panels=panels,
    )


def detected_people(frames: list[FaceFrame]) -> int:
    """Require repeated simultaneous detections, not alternating close-ups."""
    if not frames:
        return 1
    counts = [
        min(
            4,
            len(
                [
                    face
                    for face in frame.faces
                    if face.confidence >= 0.65 and face.w > 0 and face.h > 0
                ]
            ),
        )
        for frame in frames
    ]
    required = min(len(frames), max(2, math.ceil(len(frames) * 0.3)))
    return next((count for count in (4, 3, 2) if sum(n >= count for n in counts) >= required), 1)


def collage_boundaries(
    start: float, end: float, frames: list[FaceFrame], cuts: list[float]
) -> list[float]:
    native = sorted({start, end, *(cut for cut in cuts if start < cut < end)})
    changes = list(native)
    for left, right in zip(native, native[1:], strict=False):
        samples = sorted(
            (frame for frame in frames if left <= frame.timestamp < right),
            key=lambda frame: frame.timestamp,
        )
        if len(samples) < 4:
            continue
        counts = [
            min(
                4,
                sum(face.confidence >= 0.65 and face.w > 0 and face.h > 0 for face in frame.faces),
            )
            for frame in samples
        ]
        # Median sampling holds a layout through brief detection losses.
        smoothed = [
            int(
                median(
                    [
                        count
                        for other, count in zip(samples, counts, strict=True)
                        if abs(other.timestamp - frame.timestamp) <= 0.75
                    ]
                )
            )
            for frame in samples
        ]
        current, pending, since = smoothed[0], smoothed[0], samples[0].timestamp
        for frame, count in zip(samples[1:], smoothed[1:], strict=True):
            if count != pending:
                pending, since = count, frame.timestamp
            if count != current and frame.timestamp - since >= 1:
                changes.append(since)
                current = count
    # Use the output frame clock so concatenated shots cannot accumulate drift.
    return sorted(
        {
            start,
            end,
            *(
                min(end, max(start, start + round((cut - start) * 30) / 30))
                for cut in changes
                if start < cut < end
            ),
        }
    )


def plan_automatic_collage(
    width: int,
    height: int,
    ratio: str,
    start: float,
    end: float,
    frames: list[FaceFrame],
    scene_cuts: list[float],
    *,
    config: "RenderConfig",
    sentence_boundaries: list[float] | None = None,
) -> CropPlan:
    from clipforge_api.clip_schemas import PanelConfig

    boundaries = collage_boundaries(start, end, frames, scene_cuts)
    _, _, ow, oh = geometry(width, height, ratio)

    panel_configs: dict[int, list[PanelConfig]] = {}

    def panels_for(count: int, layout: str) -> list[PanelConfig]:
        if count not in panel_configs:
            panels = []
            for index, (_, _, pw, ph) in enumerate(panel_bounds(layout, count, ow, oh)):
                cw, _, _, _ = geometry(width, height, ratio, output_size=(pw, ph))
                targets = []
                for frame in frames:
                    if not start <= frame.timestamp < end:
                        continue
                    faces = sorted(
                        (face for face in frame.faces if face.confidence >= 0.65),
                        key=lambda face: face.center_x,
                    )
                    if len(faces) < count:
                        continue
                    face = faces[index]
                    spacing = min(
                        abs(face.center_x - other.center_x) for other in faces if other is not face
                    )
                    targets.append(
                        max(
                            face.w * width * 1.55,
                            face.h * height * 1.4 * pw / ph,
                            spacing * width * 0.8,
                        )
                    )
                # A common crop size per layout keeps all camera cuts on one
                # render clock, while framing each person rather than the group.
                target = sorted(targets)[int((len(targets) - 1) * 0.95)] if targets else cw
                panels.append(
                    PanelConfig.model_validate(
                        {
                            "subject": f"person-{index + 1}",
                            "zoom": round(max(1, min(3, cw / max(2, target))), 3),
                        }
                    )
                )
            panel_configs[count] = panels
        return panel_configs[count]

    shots: list[CropPlan] = []
    shot_configs: list[RenderConfig] = []
    scenes: list[CompositionScene] = []
    for left, right in zip(boundaries, boundaries[1:], strict=False):
        samples = [frame for frame in frames if left <= frame.timestamp < right]
        count = detected_people(samples)
        layout = (
            "single"
            if count == 1
            else (("stacked" if oh >= ow else "side-by-side") if count == 2 else "grid")
        )
        automatic = config.model_copy(
            update={
                "layout": layout,
                "panels": panels_for(count, layout) if count > 1 else [],
                "anchor_x": None,
                "anchor_y": None,
                "zoom": 1,
                "subject": "primary",
            }
        )
        shot = plan_composition(
            width,
            height,
            ratio,
            left,
            right,
            samples,
            [],
            config=automatic,
            sentence_boundaries=sentence_boundaries,
        )
        # Edge positioning lowers the aesthetic score even when the head is
        # fully visible. It must not suppress a real second person.
        if count > 1 and shot.quality.get("clipped_fraction", 0) > 0.2:
            automatic = automatic.model_copy(
                update={
                    "panels": [panel.model_copy(update={"zoom": 1}) for panel in automatic.panels]
                }
            )
            shot = plan_composition(
                width,
                height,
                ratio,
                left,
                right,
                samples,
                [],
                config=automatic,
            )
        if count > 1 and not shot.quality.get("all_panels_validated"):
            automatic = automatic.model_copy(update={"layout": "single", "panels": []})
            shot = plan_composition(
                width,
                height,
                ratio,
                left,
                right,
                samples,
                [],
                config=automatic,
            )
        shots.append(shot)
        shot_configs.append(automatic)
        scenes.append(
            CompositionScene(
                **shot.model_dump(exclude={"scenes"}),
                start=left - start,
                end=right - start,
            )
        )
    if len(shots) == 1:
        return shots[0]
    if (
        len(
            {
                (shot.layout, tuple((panel.crop_width, panel.crop_height) for panel in shot.panels))
                for shot in shots
            }
        )
        == 1
    ):
        fixed = config.model_copy(
            update={
                "layout": shots[0].layout,
                "panels": shot_configs[0].panels,
                "anchor_x": None,
                "anchor_y": None,
                "zoom": 1,
                "subject": "primary",
            }
        )
        return plan_composition(
            width,
            height,
            ratio,
            start,
            end,
            frames,
            boundaries[1:-1],
            config=fixed,
            sentence_boundaries=sentence_boundaries,
        )
    assessed = [shot.quality for shot in shots if shot.quality.get("validated")]
    return shots[0].model_copy(
        update={
            "mode": "AUTO_COLLAGE",
            "layout": "auto",
            "panels": [],
            "scenes": scenes,
            "warnings": list(dict.fromkeys(warning for shot in shots for warning in shot.warnings)),
            "quality": {
                "score": min((item["score"] for item in assessed), default=None),
                "validated": bool(assessed),
                "clipped_fraction": max(
                    (item.get("clipped_fraction", 0) for item in assessed), default=0
                ),
            },
        }
    )


def framing_quality(plan: CropRegion, eye_line: float = 0.34, headroom: float = 0.08) -> dict:
    """Evaluate sampled detected subjects in the actual crop coordinate system."""
    if not plan.subjects:
        return {
            "score": None,
            "validated": False,
            "reason": "No reliable face samples; inspect framing manually.",
            "samples": [],
        }
    metrics = []
    for face in plan.subjects:
        key = next(k for k in reversed(plan.keyframes) if k.time <= face["time"])
        x = (face["center_x"] * plan.source_width - key.x) / plan.crop_width
        y = (face["center_y"] * plan.source_height - key.y) / plan.crop_height
        eye = (
            (
                float(face["eye_y"])
                if face.get("eye_y") is not None
                else face["y"] + face["h"] * 0.35
            )
            * plan.source_height
            - key.y
        ) / plan.crop_height
        top = ((face["y"] - face["h"] * 0.12) * plan.source_height - key.y) / plan.crop_height
        bottom = ((face["y"] + face["h"] * 1.05) * plan.source_height - key.y) / plan.crop_height
        left = (face["x"] * plan.source_width - key.x) / plan.crop_width
        right = ((face["x"] + face["w"]) * plan.source_width - key.x) / plan.crop_width
        visible = (
            max(0, min(1, right) - max(0, left))
            * max(0, min(1, bottom) - max(0, top))
            / max(0.00001, (right - left) * (bottom - top))
        )
        stable = all(k.cut for k in plan.keyframes[1:])
        score = (
            30 * max(0, 1 - abs(x - 0.5) / 0.35)
            + 20 * max(0, 1 - abs(eye - eye_line) / 0.35)
            + 15 * max(0, 1 - abs(top - headroom) / 0.3)
            + 15 * visible
            + (20 if stable else 10)
        )
        metrics.append(
            {
                "time": face["time"],
                "face_center_x": x,
                "face_center_y": y,
                "eye_line_y": eye,
                "headroom": top,
                "face_visibility": visible,
                "head_visibility": max(0, min(1, bottom) - max(0, top))
                / max(0.00001, bottom - top),
                "crop_boundary_distance": min(left, top, 1 - right, 1 - bottom),
                "score": round(score, 1),
            }
        )
    # Low-tail score catches sustained bad composition without failing on a single detector glitch.
    scores = sorted(m["score"] for m in metrics)
    return {
        "score": scores[int((len(scores) - 1) * 0.1)],
        "validated": True,
        "samples": metrics,
        "clipped_fraction": sum(m["face_visibility"] < 0.98 for m in metrics) / len(metrics),
    }
