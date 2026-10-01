import math
import statistics
import sys
import wave
from array import array
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
    reference = max(1, statistics.median(energy)) if energy else 1
    for candidate in candidates:
        sampled = [frame for frame in frames if candidate.start <= frame.timestamp <= candidate.end]
        faces = [
            max(frame.faces, key=lambda f: f.w * f.h * f.confidence)
            for frame in sampled
            if frame.faces
        ]
        candidate.face_presence = len(faces) / max(1, len(sampled))
        jitter = statistics.pstdev([f.center_x for f in faces]) if len(faces) > 1 else 0
        cuts = sum(candidate.start + 0.5 < cut < candidate.end - 0.5 for cut in scene_boundaries)
        candidate.visual_stability = max(
            0, 1 - jitter * 3 - cuts / max(1, (candidate.end - candidate.start) / 5)
        )
        window = energy[int(candidate.start * 2) : math.ceil(candidate.end * 2)]
        candidate.audio_emphasis = (
            min(1, statistics.mean(window) / (reference * 2)) if window else 0
        )
    return candidates
