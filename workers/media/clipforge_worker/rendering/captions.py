import re
import unicodedata
from pathlib import Path

from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig

from clipforge_worker.transcription.base import Segment, Word


def escaped(text: str) -> str:
    # Strip ASS override syntax from untrusted transcript/user content.
    return (
        text.replace("\\", "／")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def timestamp(seconds: float) -> str:
    ticks = max(0, round(seconds * 100))
    return f"{ticks // 360000}:{ticks // 6000 % 60:02}:{ticks // 100 % 60:02}.{ticks % 100:02}"


def ass_color(color: str, alpha: str = "00") -> str:
    return f"&H{alpha}{color[5:7]}{color[3:5]}{color[1:3]}"


def clean_caption_text(text: str, config: CaptionConfig) -> str:
    cleaned = []
    for character in text:
        category = unicodedata.category(character)
        if not config.punctuation and category.startswith("P"):
            continue
        if config.remove_special_characters and category.startswith(("S", "C")):
            continue
        cleaned.append(character)
    return re.sub(r"\s+", " ", "".join(cleaned)).strip()


def caption_lines(
    words: list[Word], config: CaptionConfig, output_width: int
) -> list[list[tuple[Word, str]]]:
    available = output_width * config.width
    estimated_char_width = config.size * 0.82 + config.spacing + config.outline * 2
    safe_char_limit = max(1, int(available / max(1, estimated_char_width)))
    char_limit = min(config.max_chars_per_line, safe_char_limit)
    tokens: list[tuple[Word, bool]] = []
    for word in words:
        text = clean_caption_text(word.text.strip(), config)
        if not text:
            continue
        characters = list(text)
        chunks = [
            "".join(characters[index : index + char_limit])
            for index in range(0, len(characters), char_limit)
        ]
        duration = word.end - word.start
        for index, chunk in enumerate(chunks):
            tokens.append(
                (
                    Word(
                        start=word.start + duration * index / len(chunks),
                        end=word.start + duration * (index + 1) / len(chunks),
                        text=chunk,
                    ),
                    index == 0,
                )
            )

    lines: list[list[tuple[Word, str]]] = []
    current: list[tuple[Word, str]] = []
    current_length = 0
    current_word_count = 0
    for word, has_space in tokens:
        separator = " " if current and has_space else ""
        if current and (
            current_length + len(separator) + len(word.text) > char_limit
            or (has_space and current_word_count >= config.max_words)
        ):
            lines.append(current)
            current = []
            current_length = 0
            current_word_count = 0
            separator = ""
        if not current or has_space:
            current_word_count += 1
        current.append((word, separator))
        current_length += len(separator) + len(word.text)
    if current:
        lines.append(current)
    return lines


def write_ass(
    path: Path,
    segments: list[Segment],
    start: float,
    end: float,
    width: int,
    height: int,
    config: CaptionConfig,
    overlay: OverlayConfig,
) -> None:
    bold = -1 if config.weight == 700 else 0
    size = round(config.size * width / 1080)
    align = {"left": 4, "center": 5, "right": 6}[config.alignment]
    border = 3 if config.background or config.style in {"Podcast", "High Contrast"} else 1
    outline = 0 if config.style == "Minimal" else config.outline
    if border == 3:
        outline = max(4, outline)
    margin = round(height * 0.17)
    primary, secondary = ass_color(config.primary_color), ass_color(config.highlight_color)
    if config.highlight or config.style == "Karaoke" or config.animation == "karaoke":
        primary, secondary = secondary, primary
    stroke = ass_color(config.stroke_color)
    background = ass_color(
        config.background_color, f"{round((1 - config.background_opacity) * 255):02X}"
    )
    # Legacy presets retain their position until normalized coordinates are customized.
    y = (
        config.y
        if "y" in config.model_fields_set
        else {"bottom": 0.78, "middle": 0.5, "top": 0.18}[config.position]
    )
    px, py = round(config.x * width), round(min(1 - config.safe_bottom, max(0.08, y)) * height)
    animation = config.animation
    animation_tags = {
        "none": "",
        "fade": r"\fad(120,120)",
        "pop": r"\fscx90\fscy90\t(0,120,\fscx100\fscy100)",
        "scale": r"\fscx96\fscy96\t(0,180,\fscx100\fscy100)",
        "bounce": r"\fscx94\fscy94\t(0,90,\fscx103\fscy103)\t(90,180,\fscx100\fscy100)",
        "slide": "",
        "word-pop": r"\fscx92\fscy92\t(0,100,\fscx100\fscy100)",
        "karaoke": "",
    }[animation]
    placement = (
        f"\\move({px},{py + round(height * 0.015)},{px},{py},0,150)"
        if animation == "slide"
        else f"\\pos({px},{py})"
    )
    title_bold = 0 if overlay.title_style == "Minimal" else -1
    title_border = 3 if overlay.title_style == "Boxed" else 1
    watermark_margin = round(
        height * (0.18 if overlay.logo_asset_id and overlay.logo_enabled else 0.04)
    )
    watermark_align = {
        "top-left": 7,
        "top-center": 8,
        "top-right": 9,
        "middle-left": 4,
        "middle-center": 5,
        "middle-right": 6,
        "bottom-left": 1,
        "bottom-center": 2,
        "bottom-right": 3,
    }[overlay.logo_position]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{config.font},{size},{primary},{secondary},{background if border == 3 else stroke},{background},{bold},0,0,0,100,100,{config.spacing * width / 1080},0,{border},{outline},{config.shadow},{align},{round(width * (1 - config.width) / 2)},{round(width * (1 - config.width) / 2)},{margin},1
Style: Title,{config.font},{round(size * 1.15)},{primary},{secondary},&H00141414,&H80000000,{title_bold},0,0,0,100,100,0,0,{title_border},3,1,8,{round(width * 0.08)},{round(width * 0.08)},{round(height * 0.1)},1
Style: Watermark,{config.font},{max(14, round(size * 0.55))},{ass_color(config.primary_color, "70")},{secondary},&H00141414,&H80000000,0,0,0,0,100,100,0,0,1,1,0,{watermark_align},{round(width * 0.04)},{round(width * 0.04)},{watermark_margin},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []

    def event(left: float, right: float, style: str, text: str) -> None:
        if right > left:
            events.append(
                f"Dialogue: 0,{timestamp(left)},{timestamp(right)},{style},,0,0,0,,{text}"
            )

    if config.enabled:
        if config.cues is not None:
            segments = [
                Segment(
                    start=start + cue.start_ms / 1000, end=start + cue.end_ms / 1000, text=cue.text
                )
                for cue in config.cues
            ]
        for segment in segments:
            if segment.end <= start or segment.start >= end:
                continue
            words = [w for w in segment.words if w.end > start and w.start < end]
            if not words:
                tokens = segment.text.split()
                words = [
                    Word(
                        start=segment.start
                        + (segment.end - segment.start) * i / max(1, len(tokens)),
                        end=segment.start
                        + (segment.end - segment.start) * (i + 1) / max(1, len(tokens)),
                        text=token,
                    )
                    for i, token in enumerate(tokens)
                ]
            lines = caption_lines(words, config, width)
            group_size = 1 if animation == "word-pop" else config.lines
            for index in range(0, len(lines), group_size):
                group = lines[index : index + group_size]
                group_words = [word for line in group for word, _ in line]
                parts = []
                word_position = 0
                for line in group:
                    line_parts = []
                    for word, separator in line:
                        text = escaped(word.text)
                        if config.uppercase:
                            text = text.upper()
                        if config.highlight or config.style == "Karaoke" or animation == "karaoke":
                            # \k uses word timestamp gaps, clipped to the output interval.
                            following = (
                                group_words[word_position + 1].start
                                if word_position + 1 < len(group_words)
                                else word.end
                            )
                            duration = max(
                                1, round((min(end, following) - max(start, word.start)) * 100)
                            )
                            text = f"{{\\k{duration}}}" + text
                        line_parts.append(separator + text)
                        word_position += 1
                    parts.append("".join(line_parts))
                event(
                    max(start, group_words[0].start) - start,
                    min(end, group_words[-1].end) - start,
                    "Caption",
                    "{" + placement + animation_tags + "}" + r"\N".join(parts),
                )
    if overlay.title:
        event(0, min(5, end - start), "Title", escaped(overlay.title))
    if overlay.watermark:
        event(0, end - start, "Watermark", escaped(overlay.watermark))
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
