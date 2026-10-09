from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    worker_device: str = "cpu"
    whisper_model: str = "base"
    whisper_compute_type: str = "int8"
    model_cache: str = "/home/appuser/.cache/clipforge"
    face_model_path: str = "/opt/models/blaze_face_short_range.tflite"
    collage_face_model_path: str = "/opt/models/face_detection_yunet_2023mar.onnx"
    analysis_fps: float = 3
    highlight_weights: dict[str, int] = Field(
        default_factory=lambda: {
            "hook": 25,
            "completeness": 20,
            "insight": 20,
            "emphasis": 10,
            "visual": 10,
            "novelty": 10,
            "boundaries": 5,
        }
    )

    @model_validator(mode="after")
    def valid_weights(self) -> "WorkerSettings":
        if (
            set(self.highlight_weights)
            != {"hook", "completeness", "insight", "emphasis", "visual", "novelty", "boundaries"}
            or any(v < 0 for v in self.highlight_weights.values())
            or sum(self.highlight_weights.values()) != 100
        ):
            raise ValueError(
                "Highlight weights must contain the seven score components and sum to 100."
            )
        return self


@lru_cache
def worker_settings() -> WorkerSettings:
    return WorkerSettings()
