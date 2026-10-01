from pathlib import Path

from clipforge_worker.media.ffmpeg import ffmpeg


def create_proxy(source: Path, output: Path) -> None:
    ffmpeg(
        [
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(source),
            "-vf",
            "scale='min(640,iw)':-2",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            str(output),
        ]
    )


def extract_audio(source: Path, output: Path) -> None:
    ffmpeg(
        [
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    )
