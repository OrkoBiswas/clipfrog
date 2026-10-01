import shutil
import subprocess

import pytest
from clipforge_worker.media.probe import probe


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required; runs in worker container")
def test_real_probe_and_corrupt_file(tmp_path):
    video = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=320x240:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(video),
        ],
        check=True,
    )
    info = probe(video)
    assert info.width == 320 and info.height == 240
    assert 950 <= info.duration_ms <= 1100
    assert info.has_audio and info.fps == 25
    bad = tmp_path / "bad.mp4"
    bad.write_text("not a video")
    with pytest.raises(ValueError, match="valid video"):
        probe(bad)
