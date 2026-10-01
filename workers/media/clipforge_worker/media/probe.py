import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path

from pydantic import BaseModel


class MediaInfo(BaseModel):
    width: int
    height: int
    duration_ms: int
    fps: float
    codec: str
    has_audio: bool


def probe(path: Path) -> MediaInfo:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        data = json.loads(result.stdout)
        video = next(
            s
            for s in data["streams"]
            if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")
        )
        duration = float(data["format"].get("duration", video.get("duration", 0)))
        if (
            not math.isfinite(duration)
            or duration <= 0
            or video["width"] < 2
            or video["height"] < 2
        ):
            raise ValueError("Invalid video dimensions or duration")
        return MediaInfo(
            width=video["width"],
            height=video["height"],
            duration_ms=round(duration * 1000),
            fps=float(Fraction(video.get("avg_frame_rate", "0/1"))),
            codec=video["codec_name"],
            has_audio=any(s["codec_type"] == "audio" for s in data["streams"]),
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        KeyError,
        ValueError,
        StopIteration,
        ZeroDivisionError,
    ) as exc:
        raise ValueError("This file could not be read as a valid video.") from exc
