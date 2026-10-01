from pathlib import Path


def detect_scenes(path: Path) -> list[tuple[float, float]]:
    from scenedetect import AdaptiveDetector, detect

    return [
        (start.get_seconds(), end.get_seconds())
        for start, end in detect(str(path), AdaptiveDetector(), start_in_scene=True)
    ]
