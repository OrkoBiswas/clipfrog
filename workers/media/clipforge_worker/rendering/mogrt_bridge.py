import json
import os
import shutil
from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from clipforge_api.clip_schemas import CaptionConfig

from clipforge_worker.transcription.base import Segment

MOGRT_TEMPLATES = {
    f"mogrt-pack1-{index:02}": f"Subtitles {index:02}"
    for index in range(1, 5)
}


class RenderCue(TypedDict):
    text: str
    start: float
    end: float
    x: float
    y: float


def render_mogrt_overlay(
    destination: Path,
    segments: list[Segment],
    start: float,
    end: float,
    width: int,
    height: int,
    captions: CaptionConfig,
) -> Path | None:
    template = MOGRT_TEMPLATES.get(captions.animation)
    if not captions.enabled or not template:
        return None
    cues: list[RenderCue] = []
    if captions.cues is not None:
        cues = [
            {
                "text": cue.text,
                "start": max(0, cue.start_ms / 1000),
                "end": min(end - start, cue.end_ms / 1000),
                "x": captions.x,
                "y": captions.y,
            }
            for cue in captions.cues
        ]
    else:
        cues = [
            {
                "text": segment.text,
                "start": max(start, segment.start) - start,
                "end": min(end, segment.end) - start,
                "x": captions.x,
                "y": captions.y,
            }
            for segment in segments
            if segment.end > start and segment.start < end
        ]
    cues = [cue for cue in cues if cue["end"] > cue["start"] and cue["text"].strip()]
    if not cues:
        return None
    endpoint = os.environ.get("CLIPFORGE_MOGRT_AGENT_URL")
    token_path = Path(os.environ.get("CLIPFORGE_MOGRT_AGENT_TOKEN", "/app/.local/mogrt-agent/token"))
    if not endpoint or not token_path.is_file():
        raise RuntimeError(
            "This caption uses an original Adobe MOGRT. Start the local After Effects agent "
            "with scripts/mogrt_agent.py before rendering."
        )
    payload = json.dumps(
        {
            "template": captions.animation,
            "width": width,
            "height": height,
            "duration": end - start,
            "size": captions.size,
            "primary_color": captions.primary_color,
            "effect_color": captions.effect_color,
            "shadow_color": captions.shadow_color,
            "shadow_opacity": captions.shadow_opacity,
            "weight": captions.weight,
            "cues": cues,
        }
    ).encode("utf-8")
    request = Request(
        endpoint.rstrip("/") + "/render",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-ClipForge-MOGRT-Token": token_path.read_text(encoding="utf-8").strip(),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=max(600, len(cues) * 30)) as response:
            with destination.open("wb") as output:
                shutil.copyfileobj(response, output)
    except HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"After Effects MOGRT render failed: {detail}") from error
    except URLError as error:
        raise RuntimeError(
            "Could not reach the local After Effects agent. Start scripts/mogrt_agent.py "
            "on the Windows host and retry the render."
        ) from error
    return destination
