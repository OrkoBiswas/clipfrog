import math
from dataclasses import dataclass, field
from statistics import median
from typing import Literal

from pydantic import BaseModel, Field

from clipforge_worker.vision.face_detector import Face, FaceFrame

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


class CropPlan(BaseModel):
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


@dataclass
class Track:
    samples: list[tuple[float, Face]] = field(default_factory=list)


def primary_track(frames: list[FaceFrame]) -> Track | None:
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

    def score(track: Track) -> float:
        faces = [f for _, f in track.samples]
        persistence = len(faces) / max(1, len(frames))
        size = median(f.w * f.h for f in faces)
        centrality = 1 - abs(median(f.center_x for f in faces) - 0.5)
        return persistence * 0.7 + min(1, size * 5) * 0.2 + centrality * 0.1

    return max(tracks, key=score) if tracks else None


def geometry(width: int, height: int, ratio: str, zoom: float = 1) -> tuple[int, int, int, int]:
    if width < 2 or height < 2 or not 1 <= zoom <= 3:
        raise ValueError("Invalid source dimensions or crop zoom.")
    if ratio == "Original":
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
) -> CropPlan:
    if end <= start:
        raise ValueError("Clip end must follow its start.")
    cw, ch, ow, oh = geometry(width, height, ratio, zoom)

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
    last_anchor = (0.5, 0.5)
    subjects: list[dict] = []
    for left, right in zip(boundaries, boundaries[1:], strict=False):
        samples = [f for f in frames if left <= f.timestamp < right]
        if subject in {"left", "right"}:
            samples = [
                FaceFrame(
                    timestamp=f.timestamp,
                    faces=[
                        sorted(f.faces, key=lambda item: item.center_x)[
                            0 if subject == "left" else -1
                        ]
                    ]
                    if f.faces
                    else [],
                )
                for f in samples
            ]
        track = primary_track(samples)
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
                last_anchor = (0.5, 0.5)
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


def framing_quality(plan: CropPlan, eye_line: float = 0.34, headroom: float = 0.08) -> dict:
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
            (float(face["eye_y"]) if face.get("eye_y") is not None else face["y"] + face["h"] * 0.35)
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

