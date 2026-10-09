import math
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from clipforge_worker.config import worker_settings

COLLAGE_DETECTOR_VERSION = "yunet-collage-v1"
COLLAGE_FPS = 3


class Face(BaseModel):
    confidence: float
    x: float
    y: float
    w: float
    h: float
    center_x: float
    center_y: float
    eye_y: float | None = None


class FaceFrame(BaseModel):
    timestamp: float
    faces: list[Face]
    detector: str | None = None


def collage_sample_times(start: float, end: float) -> list[float]:
    return [
        index / COLLAGE_FPS
        for index in range(math.ceil(start * COLLAGE_FPS), math.ceil(end * COLLAGE_FPS))
    ]


def collage_analysis_ready(frames: list[FaceFrame], start: float, end: float) -> bool:
    samples = {
        round(frame.timestamp, 4) for frame in frames if frame.detector == COLLAGE_DETECTOR_VERSION
    }
    required = collage_sample_times(start, end)
    return bool(required) and all(round(timestamp, 4) in samples for timestamp in required)


def merge_collage_frames(
    frames: list[FaceFrame], refined: list[FaceFrame], start: float, end: float
) -> list[FaceFrame]:
    return sorted(
        [frame for frame in frames if not start <= frame.timestamp < end] + refined,
        key=lambda frame: frame.timestamp,
    )


class CollageFaceDetector:
    """Inspect the original clip with a profile-capable detector before composing panels."""

    def analyze(
        self,
        source: Path | str,
        start: float,
        end: float,
        progress: Callable[[float], None] = lambda value: None,
    ) -> list[FaceFrame]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("Multiple-screen detection is unavailable on this server.") from exc

        model = Path(worker_settings().collage_face_model_path)
        if not model.is_file():
            model = (
                Path(__file__).resolve().parents[4]
                / "assets"
                / "vision"
                / "face_detection_yunet_2023mar.onnx"
            )
        if not model.is_file():
            raise RuntimeError(
                "The multiple-screen detector is unavailable. Rebuild the API and media worker."
            )
        detector = cv2.FaceDetectorYN.create(str(model), "", (960, 540), 0.65, 0.3, 5000)
        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("Could not open the original footage for multiple-screen detection.")
        times = collage_sample_times(start, end)
        fps = capture.get(cv2.CAP_PROP_FPS) or 30
        results: list[FaceFrame] = []
        try:
            if not times:
                return []
            capture.set(cv2.CAP_PROP_POS_MSEC, times[0] * 1000)
            frame_index = -1
            for index, timestamp in enumerate(times):
                target = round((timestamp - times[0]) * fps)
                while frame_index < target:
                    if not capture.grab():
                        raise RuntimeError(
                            "Original footage ended during multiple-screen detection."
                        )
                    frame_index += 1
                ok, frame = capture.retrieve()
                if not ok:
                    raise RuntimeError(
                        "Could not decode original footage for multiple-screen detection."
                    )
                height, width = frame.shape[:2]
                scale = min(1, 960 / width)
                frame = cv2.resize(frame, (round(width * scale), round(height * scale)))
                height, width = frame.shape[:2]
                detector.setInputSize((width, height))
                _, detections = detector.detect(frame)
                faces = []
                for detection in detections if detections is not None else []:
                    x = max(0, float(detection[0]) / width)
                    y = max(0, float(detection[1]) / height)
                    right = min(1, float(detection[0] + detection[2]) / width)
                    bottom = min(1, float(detection[1] + detection[3]) / height)
                    w, h = right - x, bottom - y
                    if w <= 0 or h <= 0:
                        continue
                    faces.append(
                        Face(
                            confidence=float(detection[-1]),
                            x=x,
                            y=y,
                            w=w,
                            h=h,
                            center_x=x + w / 2,
                            center_y=y + h / 2,
                            eye_y=float(detection[5] + detection[7]) / (2 * height),
                        )
                    )
                results.append(
                    FaceFrame(timestamp=timestamp, faces=faces, detector=COLLAGE_DETECTOR_VERSION)
                )
                if index % 15 == 0:
                    progress((index + 1) / len(times))
            progress(1)
        finally:
            capture.release()
        return results


class FaceDetector(Protocol):
    def analyze(self, source: Path, progress: Callable[[float], None]) -> list[FaceFrame]: ...


class MediaPipeFaceDetector:
    def analyze(self, source: Path, progress: Callable[[float], None]) -> list[FaceFrame]:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        cfg = worker_settings()
        options = vision.FaceDetectorOptions(
            base_options=python.BaseOptions(model_asset_path=cfg.face_model_path),
            running_mode=vision.RunningMode.IMAGE,
            min_detection_confidence=0.6,
        )
        capture = cv2.VideoCapture(str(source))
        fps = capture.get(cv2.CAP_PROP_FPS) or 25
        count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        stride = max(1, round(fps / cfg.analysis_fps))
        results: list[FaceFrame] = []
        try:
            with vision.FaceDetector.create_from_options(options) as detector:
                frame_index = 0
                while capture.grab():
                    if frame_index % stride == 0:
                        ok, frame = capture.retrieve()
                        if not ok:
                            break
                        height, width = frame.shape[:2]
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        detections = detector.detect(
                            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                        )
                        faces = []
                        for detection in detections.detections:
                            box = detection.bounding_box
                            x, y = max(0, box.origin_x / width), max(0, box.origin_y / height)
                            w, h = min(1 - x, box.width / width), min(1 - y, box.height / height)
                            faces.append(
                                Face(
                                    confidence=detection.categories[0].score,
                                    x=x,
                                    y=y,
                                    w=w,
                                    h=h,
                                    center_x=x + w / 2,
                                    center_y=y + h / 2,
                                    eye_y=(
                                        sum(point.y for point in detection.keypoints[:2]) / 2
                                        if len(detection.keypoints) >= 2
                                        else None
                                    ),
                                )
                            )
                        results.append(FaceFrame(timestamp=frame_index / fps, faces=faces))
                        if len(results) % 15 == 0:
                            progress(frame_index / max(count, 1))
                    frame_index += 1
        finally:
            capture.release()
        return results
