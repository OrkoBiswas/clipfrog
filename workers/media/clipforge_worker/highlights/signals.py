import math
import statistics
import sys
import wave
from array import array
from bisect import bisect_left, bisect_right
from pathlib import Path

from clipforge_worker.highlights.models import Candidate
from clipforge_worker.vision.face_detector import FaceFrame


def audio_energy(path: Path) -> list[float]:
    """Half-second RMS windows from actual mono signed-16-bit PCM audio."""
    result: list[float] = []
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2 or stream.getnchannels() != 1:
            raise ValueError("Audio analysis requires mono 16-bit PCM.")
        while chunk := stream.readframes(stream.getframerate() // 2):
            samples = array("h", chunk)
            if sys.byteorder != "little":
                samples.byteswap()
            result.append(math.sqrt(sum(float(s) ** 2 for s in samples) / len(samples)))
    return result


def enrich(
    candidates: list[Candidate],
    frames: list[FaceFrame],
    energy: list[float],
    scene_boundaries: list[float],
) -> list[Candidate]:
    # Silence must not lower the reference until every spoken window saturates.
    active = [value for value in energy if value > max(energy, default=0) * 0.02]
    reference = max(1, statistics.median(active)) if active else 1
    ordered_frames = sorted(frames, key=lambda frame: frame.timestamp)
    timestamps = [frame.timestamp for frame in ordered_frames]
    ordered_cuts = sorted(scene_boundaries)
    for candidate in candidates:
        sampled = ordered_frames[bisect_left(timestamps, candidate.start):bisect_right(timestamps, candidate.end)]
        faces = [
            max(frame.faces, key=lambda f: f.w * f.h * f.confidence)
            for frame in sampled
            if frame.faces
        ]
        candidate.face_presence = len(faces) / max(1, len(sampled))
        jitter = statistics.pstdev([f.center_x for f in faces]) if len(faces) > 1 else 0
        cuts = max(0, bisect_left(ordered_cuts, candidate.end - 0.5) - bisect_right(ordered_cuts, candidate.start + 0.5))
        candidate.visual_stability = max(
            0, 1 - jitter * 3 - cuts / max(1, (candidate.end - candidate.start) / 5)
        )
        window = energy[int(candidate.start * 2) : math.ceil(candidate.end * 2)]
        if window:
            relative = min(1, statistics.mean(window) / (reference * 2))
            dynamic = min(1, statistics.pstdev(window) / reference) if len(window) > 1 else 0
            candidate.audio_emphasis = min(1, relative * 0.8 + dynamic * 0.2)
        else:
            candidate.audio_emphasis = 0
    return candidates
