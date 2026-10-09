import re
from dataclasses import dataclass

from clipforge_worker.highlights.models import Candidate
from clipforge_worker.transcription.base import Segment, Word

ENDING = re.compile(r"[.!?。！？।][\"\u201d\u2019\)\]]*$")
CLAUSE = re.compile(r"[,;:，；：][\"\u201d\u2019]*$")


def finished(text: str) -> bool:
    text = text.strip()
    if re.search(r"(?:\.{2,}|…)[\"\u201d\u2019\)\]]*$", text):
        return False
    return bool(ENDING.search(text)) and not bool(
        re.search(r"(?:\b(?:mr|mrs|ms|dr|prof|vs|etc)|\b[A-Z])\.$", text, re.I)
    )


def unresolved_ending(text: str) -> bool:
    """A closing question, trailing conjunction or promised answer needs more speech."""
    tail = re.split(r"[.!?。！？।]+", text.strip().rstrip('"”’)]'), flags=re.UNICODE)
    closing = next((part.strip().casefold() for part in reversed(tail) if part.strip()), "")
    return bool(
        re.search(r"[?？][\"\u201d\u2019\)\]]*$", text.strip())
        or re.search(r"(?:\.{2,}|…)[\"\u201d\u2019\)\]]*$", text.strip())
        or re.search(r"\b(?:because|and|but|if|when|the|to|of|with|so|like|কিন্তু|কারণ|যদি)$", closing)
        or re.search(
            r"\b(?:here(?:'s| is) why|let me explain|i(?:'ll| will) tell you|wait until|the reason is|what happened next)$",
            closing,
        )
    )


def ending_quality(unit: "Unit", following: "Unit | None", source_duration: float) -> float:
    if unresolved_ending(unit.segment.text):
        return 0.25
    gap = max(0, (following.segment.start if following else source_duration) - unit.segment.end)
    if (
        following
        and gap < 0.9
        and re.match(
            r"^(?:and\b|but\b|because\b|so\b|which\b|then\b|আর\b|কিন্তু\b|কারণ\b)",
            following.segment.text.strip(),
            re.I,
        )
    ):
        return 0.55
    if unit.end_quality < 0.7:
        return unit.end_quality
    # A punctuation mark alone is weaker evidence than the speaker pausing.
    if following and gap < 0.3:
        return 0.65
    return min(1 if gap >= 0.6 else 0.9, max(0.8, unit.end_quality))


@dataclass
class Unit:
    segment: Segment
    start_quality: float
    end_quality: float


def _units(segments: list[Segment], maximum: float | None = None) -> list[Unit]:
    """Whisper segments are transport chunks, not sentence boundaries."""
    result: list[Unit] = []
    pending: list[Word] = []
    start_quality = 1.0

    def flush(quality: float) -> None:
        nonlocal pending, start_quality
        if pending:
            result.append(
                Unit(
                    Segment(
                        start=pending[0].start,
                        end=pending[-1].end,
                        text=" ".join(w.text.strip() for w in pending),
                        words=list(pending),
                    ),
                    start_quality,
                    quality,
                )
            )
            pending = []
        start_quality = quality

    for segment in sorted(segments, key=lambda s: s.start):
        if not segment.words:
            flush(0.45)
            if not segment.text.strip() or segment.end <= segment.start:
                continue
            quality = 1.0 if finished(segment.text) else 0.45
            if (
                result
                and not finished(result[-1].segment.text)
                and (0 <= segment.start - result[-1].segment.end <= 1.2)
            ):
                previous = result.pop()
                result.append(
                    Unit(
                        Segment(
                            start=previous.segment.start,
                            end=segment.end,
                            text=previous.segment.text + " " + segment.text,
                            words=[],
                        ),
                        previous.start_quality,
                        quality,
                    )
                )
            else:
                start = result[-1].end_quality if result else 1.0
                if result and segment.start - result[-1].segment.end > 1.2:
                    start = 0.8
                result.append(Unit(segment, start, quality))
            start_quality = quality
            continue
        for word in sorted(segment.words, key=lambda w: w.start):
            if not word.text.strip() or word.end < word.start:
                continue
            last = (
                pending[-1]
                if pending
                else (result[-1].segment.words[-1] if result and result[-1].segment.words else None)
            )
            if last and word.start < last.end and word.text.strip() == last.text.strip():
                continue
            if pending and word.start - pending[-1].end > 1.2:
                flush(0.75)
            if pending and maximum and word.end - pending[0].start > maximum:
                pivot = pending[0].start + maximum * 0.55
                safe = [
                    i
                    for i in range(1, len(pending))
                    if (
                        CLAUSE.search(pending[i - 1].text)
                        or pending[i].start - pending[i - 1].end > 0.35
                    )
                ]
                split = (
                    min(safe, key=lambda i: abs(pending[i].start - pivot))
                    if safe
                    else min(
                        range(1, len(pending)),
                        key=lambda i: abs(pending[i].start - pivot),
                        default=1,
                    )
                )
                tail = pending[split:]
                pending = pending[:split]
                flush(0.65 if safe else 0.2)
                pending = tail
            pending.append(word)
            if finished(word.text):
                flush(1.0)
    flush(0.45)
    return result


def sentences(segments: list[Segment]) -> list[Segment]:
    return [unit.segment for unit in _units(segments)]


def complete_clip_end(
    segments: list[Segment],
    start: float,
    end: float,
    source_duration: float,
) -> float | None:
    """Repair older highlight endpoints by finishing the exchange within 12 seconds."""
    units = _units(segments)
    limit = min(source_duration, start + 180, end + 12)
    for index, unit in enumerate(units):
        if unit.segment.end < end - 0.45 or unit.segment.end <= start:
            continue
        if unit.segment.end > limit:
            break
        following = units[index + 1] if index + 1 < len(units) else None
        if ending_quality(unit, following, source_duration) < 0.75:
            continue
        next_start = following.segment.start if following else source_duration
        return min(
            limit, unit.segment.end + min(0.35, max(0, next_start - unit.segment.end - 0.06))
        )
    return None


def _speech_duration(units: list[Unit]) -> tuple[float, float]:
    spans: list[tuple[float, float]] = []
    timed, total = 0, 0
    for unit in units:
        segment = unit.segment
        total += max(1, len(segment.text.split()))
        if segment.words:
            timed += len(segment.words)
            spans.extend((w.start, w.end) for w in segment.words)
        else:
            spans.append((segment.start, segment.end))
    merged: list[list[float]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return sum(end - start for start, end in merged), min(1, timed / max(1, total))


def create_candidates(
    segments: list[Segment], minimum: float, maximum: float, source_duration: float
) -> list[Candidate]:
    if minimum <= 0 or maximum < minimum or source_duration <= 0:
        return []
    # Duration is a target. Do not manufacture boundaries inside a sentence.
    units = _units(segments)
    finish_limit = min(180, maximum + min(12, maximum * 0.25))
    candidates: list[Candidate] = []
    for index, first in enumerate(units):
        proposals: list[Candidate] = []
        for last_index in range(index, len(units)):
            last = units[last_index]
            if last_index > index and (
                last.segment.start - units[last_index - 1].segment.end > 3.5
            ):
                break
            raw_start, raw_end = first.segment.start, last.segment.end
            if raw_end - raw_start > finish_limit:
                break
            if last.segment.start - raw_start >= maximum:
                break
            if raw_start < 0 or raw_end > source_duration:
                continue
            previous_end = units[index - 1].segment.end if index else 0
            next_start = (
                units[last_index + 1].segment.start
                if last_index + 1 < len(units)
                else source_duration
            )
            start = max(0, raw_start - min(0.08, max(0, raw_start - previous_end) / 2))
            end = min(source_duration, raw_end + min(0.35, max(0, next_start - raw_end - 0.06)))
            if end - start > finish_limit:
                start, end = raw_start, raw_end
            if end - start < minimum:
                continue
            window = units[index : last_index + 1]
            speech_duration, timing = _speech_duration(window)
            confidence = [word.confidence for unit in window for word in unit.segment.words]
            proposals.append(
                Candidate(
                    start=start,
                    end=end,
                    text=" ".join(u.segment.text for u in window),
                    start_boundary_quality=first.start_quality,
                    end_boundary_quality=ending_quality(
                        last,
                        units[last_index + 1] if last_index + 1 < len(units) else None,
                        source_duration,
                    ),
                    speech_ratio=min(1, speech_duration / (end - start)),
                    word_timing_coverage=timing,
                    transcript_confidence=max(0, min(1, sum(confidence) / len(confidence)))
                    if confidence
                    else None,
                    context_before=" ".join(
                        u.segment.text for u in units[max(0, index - 2) : index]
                    )[-600:],
                    context_after=" ".join(
                        u.segment.text for u in units[last_index + 1 : last_index + 3]
                    )[:600],
                    sentence_count=sum(finished(u.segment.text) for u in window),
                )
            )
        if len(proposals) > 12:
            indices = sorted({round(i * (len(proposals) - 1) / 11) for i in range(12)})
            proposals = [proposals[i] for i in indices]
        candidates.extend(proposals)
    return candidates
