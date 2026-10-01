import subprocess
from collections.abc import Callable
from pathlib import Path


def ffmpeg(
    args: list[str], cwd: Path | None = None, check_cancel: Callable[[], None] | None = None
) -> None:
    """Arguments never go through a shell; cancellation kills the child process."""
    with subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    ) as process:
        try:
            while True:
                try:
                    _, error = process.communicate(timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    if check_cancel:
                        check_cancel()
            if process.returncode:
                raise ValueError(
                    "FFmpeg could not process this media: " + error.decode(errors="replace")[-300:]
                )
        except BaseException:
            process.kill()
            process.communicate()
            raise
