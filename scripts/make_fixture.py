"""Create a tiny real MP4 for integration checks; no binary fixture is committed."""

import os
import subprocess
from pathlib import Path

target = Path(os.environ.get("FIXTURE_PATH", "/tmp/fixture.mp4"))
target.parent.mkdir(exist_ok=True)
subprocess.run(
    [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x360:rate=24",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000",
        "-t",
        "4",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(target),
    ],
    check=True,
    capture_output=True,
)
print(target)
