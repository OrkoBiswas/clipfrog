import re

from clipforge_worker.highlights.models import Candidate
from clipforge_worker.transcription.base import Segment, Word


def sentences(segments: list[Segment]) -> list[Segment]:
    """Split at timestamped punctuation or long pauses, never invent word times."""
    result: list[Segment] = []
    for segment in segments:
        if not segment.words:
            result.append(segment)
            continue
        words: list[Word] = []
        for word in segment.words:
            if words and word.start - words[-1].end > 0.7:
                result.append(
                    Segment(
                        start=words[0].start,
                        end=words[-1].end,
                        text=" ".join(w.text for w in words),
                        words=words,
                    )
                )
                words = []
            words.append(word)
            if re.search(r"[.!?。！？]$", word.text):
                result.append(
                    Segment(
                        start=words[0].start,
                        end=word.end,
                        text=" ".join(w.text for w in words),
                        words=words,
                    )
                )
                words = []
        if words:
            result.append(
                Segment(
                    start=words[0].start,
                    end=words[-1].end,
                    text=" ".join(w.text for w in words),
                    words=words,
                )
            )
    return result


def create_candidates(
    segments: list[Segment], minimum: float, maximum: float, source_duration: float
) -> list[Candidate]:
    units = sentences(segments)
    candidates = []
    for index, first in enumerate(units):
        for last_index in range(index, len(units)):
            last = units[last_index]
            start = max(0, first.start - 0.08)
            end = min(source_duration, last.end + 0.12)
            duration = end - start
            if duration > maximum:
                break
            if duration >= minimum:
                candidates.append(
                    Candidate(
                        start=start,
                        end=end,
                        text=" ".join(unit.text for unit in units[index : last_index + 1]),
                    )
                )
    return candidates
