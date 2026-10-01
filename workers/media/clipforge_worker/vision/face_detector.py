from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from clipforge_worker.config import worker_settings


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
                                    eye_y=(sum(point.y for point in detection.keypoints[:2]) / 2 if len(detection.keypoints) >= 2 else None),
                                )
                            )
                        results.append(FaceFrame(timestamp=frame_index / fps, faces=faces))
                        if len(results) % 15 == 0:
                            progress(frame_index / max(count, 1))
                    frame_index += 1
        finally:
            capture.release()
        return results
