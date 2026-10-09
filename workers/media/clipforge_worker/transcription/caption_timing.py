"""Speech-bounded captions shared by the editor, subtitles, and video renderer."""

from clipforge_api.clip_schemas import CaptionCue

from clipforge_worker.transcription.base import Segment, Word

# Bridge normal spacing between words, but clear captions at a real speech pause.
PAUSE_SECONDS = 0.25


def _timed_words(segment: Segment) -> list[Word]:
    if segment.words:
        return sorted(
            (word for word in segment.words if word.text.strip() and word.end >= word.start),
            key=lambda word: word.start,
        )
    tokens = segment.text.split()
    return [
        Word(
            start=segment.start + (segment.end - segment.start) * index / len(tokens),
            end=segment.start + (segment.end - segment.start) * (index + 1) / len(tokens),
            text=token,
        )
        for index, token in enumerate(tokens)
    ]


def _speech_runs(segments: list[Segment], start: float, end: float) -> list[Segment]:
    runs: list[Segment] = []
    for segment in segments:
        if segment.end <= start or segment.start >= end:
            continue
        words = [
            word.model_copy(update={"start": max(start, word.start), "end": min(end, word.end)})
            for word in _timed_words(segment)
            if word.end > start and word.start < end
        ]
        groups: list[list[Word]] = []
        last_end = start
        for word in words:
            if not groups or word.start - last_end >= PAUSE_SECONDS - 1e-6:
                groups.append([])
            groups[-1].append(word)
            last_end = max(last_end, word.end)
        for group in groups:
            finish = max(word.end for word in group)
            if finish > group[0].start:
                runs.append(
                    Segment(
                        start=group[0].start,
                        end=finish,
                        text=" ".join(word.text.strip() for word in group),
                        words=group,
                    )
                )
    return sorted(runs, key=lambda segment: segment.start)


def speech_captions(
    segments: list[Segment],
    start: float,
    end: float,
    cues: list[CaptionCue] | None = None,
) -> list[Segment]:
    """Keep real word timing, and fit edited wording into the source's spoken runs.

    Without a transcript, explicit cue/segment timing is the available fallback.
    An empty cue list intentionally disables all captions.
    """
    source_runs = _speech_runs(segments, start, end)
    if cues is None:
        return source_runs
    result: list[Segment] = []
    for cue in cues:
        left, right = max(start, start + cue.start_ms / 1000), min(end, start + cue.end_ms / 1000)
        tokens = cue.text.split()
        if right <= left or not tokens:
            continue
        runs = (
            _speech_runs(source_runs, left, right)
            if segments
            else _speech_runs([Segment(start=left, end=right, text=cue.text)], left, right)
        )
        original = [word for run in runs for word in run.words]
        if [word.text.strip().casefold() for word in original] == [
            token.casefold() for token in tokens
        ]:
            # Loading/saving unchanged transcript captions must retain word timestamps.
            offset = 0
            for run in runs:
                words = [
                    word.model_copy(update={"text": tokens[offset + index]})
                    for index, word in enumerate(run.words)
                ]
                result.append(
                    run.model_copy(
                        update={"words": words, "text": " ".join(word.text for word in words)}
                    )
                )
                offset += len(words)
            continue
        # Edited text has no word alignment. Distribute it over spoken time only;
        # each word belongs to one run, so none can linger through a pause.
        duration = sum(run.end - run.start for run in runs)
        elapsed = 0.0
        offset = 0
        for run in runs:
            elapsed += run.end - run.start
            boundary = min(len(tokens), round(len(tokens) * elapsed / duration))
            text = " ".join(tokens[offset:boundary])
            if text:
                result.extend(
                    _speech_runs([Segment(start=run.start, end=run.end, text=text)], left, right)
                )
            offset = boundary
    return sorted(result, key=lambda segment: segment.start)
