from clipforge_worker.transcription.base import Segment


def timestamp(seconds: float, vtt: bool = False) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, rest = divmod(milliseconds, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}{'.' if vtt else ','}{millis:03}"


def subtitles(segments: list[Segment], vtt: bool = False) -> str:
    header = "WEBVTT\n\n" if vtt else ""
    return (
        header
        + "\n\n".join(
            f"{i + 1}\n{timestamp(s.start, vtt)} --> {timestamp(s.end, vtt)}\n{s.text.replace('-->', '→')}"
            for i, s in enumerate(segments)
        )
        + "\n"
    )
