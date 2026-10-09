import re
import shutil
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

from clipforge_api.caption_fonts import caption_variant
from clipforge_api.clip_schemas import CaptionConfig, OverlayConfig
from PIL import ImageFont

from clipforge_worker.transcription.base import Segment, Word
from clipforge_worker.transcription.caption_timing import speech_captions

REVEAL_ANIMATIONS = {"color-reveal", "typewriter", "word-reveal"}
WORD_ANIMATIONS = {
    "word-spring",
    "word-rise",
    "word-punch",
    "word-slide",
    "word-tilt",
    "word-focus",
    "word-flip",
    "word-stretch",
    "word-pill",
    "word-box",
    "word-underline",
    "word-glow",
}


def bundled_caption_font(file: str) -> Path:
    return Path(__file__).resolve().parents[4] / "assets" / "fonts" / file


def prepare_caption_fonts(root: Path, config: CaptionConfig, overlay: OverlayConfig) -> bool:
    """Make the selected bundled faces available to native desktop FFmpeg."""
    variants = [caption_variant(config.font, config.weight, config.italic)]
    if overlay.title:
        variants.append(
            caption_variant(config.font, 400 if overlay.title_style == "Minimal" else 700, False)
        )
    if overlay.watermark:
        variants.append(caption_variant(config.font, 400, False))
    copied = False
    for face in variants:
        source = bundled_caption_font(face["file"])
        if source.is_file():
            directory = root / "caption-fonts"
            directory.mkdir(exist_ok=True)
            shutil.copyfile(source, directory / source.name)
            copied = True
    # Containers install the same faces in fontconfig instead.
    return copied


@lru_cache(maxsize=512)
def caption_font(family: str, weight: int, italic: bool, size: int):
    # Each bundled face has its own native family. This selects the same real
    # medium/black/italic outlines used by the browser without synthetic bold.
    variant = caption_variant(family, weight, italic)
    bundled = bundled_caption_font(variant["file"])
    if bundled.is_file():
        font_path = str(bundled)
    else:
        match = (
            subprocess.check_output(
                ["fc-match", "-f", "%{family}\n%{file}", variant["family"]], text=True, timeout=5
            )
            .strip()
            .splitlines()
        )
        if len(match) != 2 or variant["family"] not in match[0].split(","):
            raise RuntimeError(f"Caption font {family} is not installed. Rebuild the media worker.")
        font_path = match[1]
    font = ImageFont.truetype(font_path, size=size)
    # libass sizes fonts by their ascender + descender rather than the EM square.
    ascent, descent = font.getmetrics()
    return font, size / max(1, ascent + descent)


def word_motion_tags(
    animation: str,
    x: float,
    y: float,
    size: int,
    ms: int,
    scale: float,
    font_width: float = 100,
) -> str:
    target = scale * 100
    target_x = scale * font_width
    pos = rf"\pos({x:.2f},{y:.2f})"
    final = rf"\fscx{target_x:.2f}\fscy{target:.2f}\frz0\blur0"
    if animation in {"word-spring", "word-pill"}:
        peak = max(1, round(ms * 0.65))
        return (
            pos
            + rf"\fscx{target_x * 0.8:.2f}\fscy{target * 0.8:.2f}\t(0,{peak},0.6,\fscx{target_x * 1.06:.2f}\fscy{target * 1.06:.2f})\t({peak},{ms},0.6,{final})"
        )
    if animation in {"word-rise", "word-slide"}:
        dx, dy = (-1.2, 0) if animation == "word-slide" else (0, 0.65)
        return rf"\move({x + dx * size:.2f},{y + dy * size:.2f},{x:.2f},{y:.2f},0,{ms})\fscx{target_x:.2f}\fscy{target:.2f}\fad({ms},0)"
    starts = {
        "word-punch": rf"\fscx{target_x * 1.65:.2f}\fscy{target * 1.65:.2f}\frz-5",
        "word-tilt": rf"\fscx{target_x * 0.9:.2f}\fscy{target * 0.9:.2f}\frz9",
        "word-focus": rf"\fscx{target_x:.2f}\fscy{target:.2f}\blur{size * 0.14:.2f}",
        "word-flip": rf"\fscx{target_x:.2f}\fscy{target * 0.05:.2f}",
        "word-stretch": rf"\fscx{target_x * 1.5:.2f}\fscy{target:.2f}",
        "word-box": rf"\fscx{target_x * 0.92:.2f}\fscy{target * 0.92:.2f}",
        "word-glow": rf"\fscx{target_x * 0.92:.2f}\fscy{target * 0.92:.2f}",
    }
    if animation in starts:
        fade = "" if animation in {"word-box", "word-glow"} else rf"\fad({ms},0)"
        return pos + fade + starts[animation] + rf"\t(0,{ms},0.6,{final})"
    return pos + final


def rounded_word_box(width: float, height: float, radius: float) -> str:
    w, h, r = width, height, radius
    k = r * 0.5523
    return (
        f"m {r:.2f} 0 l {w - r:.2f} 0 b {w - r + k:.2f} 0 {w:.2f} {r - k:.2f} {w:.2f} {r:.2f} "
        f"l {w:.2f} {h - r:.2f} b {w:.2f} {h - r + k:.2f} {w - r + k:.2f} {h:.2f} {w - r:.2f} {h:.2f} "
        f"l {r:.2f} {h:.2f} b {r - k:.2f} {h:.2f} 0 {h - r + k:.2f} 0 {h - r:.2f} "
        f"l 0 {r:.2f} b 0 {r - k:.2f} {r - k:.2f} 0 {r:.2f} 0"
    )


def word_events(
    group,
    config: CaptionConfig,
    start: float,
    left: float,
    right: float,
    width: int,
    py: int,
    size: int,
    event,
) -> None:
    """Independent, speech-timed word events with fixed layout (no reflow/jitter)."""
    font, metric_scale = caption_font(config.font, config.weight, config.italic, size)
    spacing = config.spacing * width / 1080
    words = [word for line in group for word, _ in line]
    word_index = 0
    ink = ass_color(config.effect_color)
    inactive_alpha = round((1 - config.inactive_opacity) * 255)
    text_flags = rf"\an5\q2\fs{size / metric_scale:.2f}\1a&H00&\bord{config.outline * width / 1080:.2f}\3c{ass_color(config.stroke_color)}"

    def measure(text):
        return (font.getlength(text) + len(text) * spacing) * config.font_width / 100

    for row, line in enumerate(group):
        strings = [word.text.upper() if config.uppercase else word.text for word, _ in line]
        widths = [measure(text) for text in strings]
        gaps = [measure(separator) for _, separator in line]
        total = sum(widths) + sum(gaps)
        cursor = config.x * width - total * {"left": 0, "center": 0.5, "right": 1}[config.alignment]
        y = py + (row - (len(group) - 1) / 2) * size * 1.2
        if config.background:
            box = rounded_word_box(total + size * 0.24, size * 1.15, size * 0.08)
            bg = ass_color(config.background_color)
            alpha = round((1 - config.background_opacity) * 255)
            event(
                left,
                right,
                "Caption",
                rf"{{\an5\pos({cursor + total / 2:.2f},{y:.2f})\fscx100\fscy100\bord0\shad0\1c{bg}\1a&H{alpha:02X}&\p1}}{box}",
                -2,
            )
        for (word, _), text, word_width, gap in zip(line, strings, widths, gaps, strict=True):
            cursor += gap
            x = cursor + word_width / 2
            cursor += word_width
            following = words[word_index + 1].start if word_index + 1 < len(words) else word.end
            begin = max(left, word.start - start)
            finish = min(right, following - start)
            ms = max(
                1, round(min(config.animation_duration, max(0.02, finish - begin) * 0.8) * 1000)
            )
            position = rf"\pos({x:.2f},{y:.2f})"
            plain = (
                text_flags
                + position
                + rf"\1a&H{inactive_alpha:02X}&\3a&H{inactive_alpha:02X}&\4a&H{round((1 - config.inactive_opacity * config.shadow_opacity) * 255):02X}&\1c{ass_color(config.primary_color)}"
            )
            if config.word_display != "build":
                event(left, min(right, begin), "Caption", "{" + plain + "}" + escaped(text), 1)
            event(max(left, finish), right, "Caption", "{" + plain + "}" + escaped(text), 1)
            color = config.highlight_color if config.highlight else config.primary_color
            motion = word_motion_tags(
                config.animation, x, y, size, ms, config.active_scale, config.font_width
            )
            if config.animation in {"word-pill", "word-box"}:
                # Geometry already includes the stretched glyph width.
                box_motion = word_motion_tags(config.animation, x, y, size, ms, config.active_scale)
                box = rounded_word_box(
                    word_width + size * 0.2,
                    size * 1.08,
                    size * (0.22 if config.animation == "word-pill" else 0.02),
                )
                event(
                    begin,
                    finish,
                    "Caption",
                    rf"{{\an5{box_motion}\bord0\shad0\1c{ink}\1a&H00&\p1}}{box}",
                    0,
                )
            if config.animation == "word-underline":
                top = y + size * 0.48
                box = rounded_word_box(word_width, size * 0.08, size * 0.04)
                tags = rf"\an7\pos({x - word_width / 2:.2f},{top:.2f})\fscx100\fscy100\bord0\shad0\1c{ink}\p1"
                tags += rf"\clip({round(x - word_width / 2)},0,{round(x - word_width / 2)},10000)\t(0,{ms},\clip({round(x - word_width / 2)},0,{round(x + word_width / 2)},10000))"
                event(begin, finish, "Caption", "{" + tags + "}" + box, 0)
            if config.animation == "word-glow":
                event(
                    begin,
                    finish,
                    "Caption",
                    rf"{{\an5\fs{size / metric_scale:.2f}{motion}\1c{ink}\3c{ink}\bord{size * 0.1:.2f}\blur{size * 0.16:.2f}\shad0}}"
                    + escaped(text),
                    0,
                )
            event(
                begin,
                finish,
                "Caption",
                "{" + text_flags + motion + rf"\1c{ass_color(color)}" + "}" + escaped(text),
                1,
            )
            word_index += 1


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


def color_reveal_text(lines: list[str], config: CaptionConfig, duration_ms: int) -> str:
    """Build a bounded per-character color reveal in native ASS."""
    count = max(1, sum(len(line) for line in lines))
    position = 0
    result = []
    for line in lines:
        parts = []
        for character in line:
            delay = round(position / count * duration_ms * 0.75)
            finish = delay + max(1, round(duration_ms * 0.25))
            position += 1
            tags = (
                rf"\alpha&HFF&\1c{ass_color(config.effect_color if config.animation == 'color-reveal' else config.primary_color)}"
                + rf"\t({delay},{delay + 1},\alpha&H00&\4a&H{round((1 - config.shadow_opacity) * 255):02X}&)"
                + rf"\t({delay},{finish},\1c{ass_color(config.primary_color)})"
            )
            parts.append("{" + tags + "}" + escaped(character))
        result.append("".join(parts))
    return r"\N".join(result)


def entrance_tags(
    config: CaptionConfig,
    duration: int,
    width: int,
    height: int,
    x: int,
    y: int,
    size: int,
    line_count: int,
    text_width: float,
) -> str:
    """Native libass motion; no external editor or frame-generation service required."""
    animation = config.animation
    position = rf"\pos({x},{y})"
    fade = rf"\fad({duration},0)"
    stretch = config.font_width
    target = rf"\fscx{stretch:g}\fscy100\frz0\blur0"
    starts = {
        "word-pop": rf"\fscx{stretch * 0.92:g}\fscy92",
        "zoom-in": rf"\fscx{stretch * 0.7:g}\fscy70",
        "zoom-out": rf"\fscx{stretch * 1.3:g}\fscy130",
        "blur-in": rf"\blur{size * 0.14:.2f}",
        "tilt": rf"\frz9\fscx{stretch * 0.9:g}\fscy90",
        "unfold": r"\fscy5",
        "stretch": rf"\fscx{stretch * 1.5:g}",
        "stamp": rf"\fscx{stretch * 1.65:g}\fscy165\frz-5",
    }
    if animation in starts:
        return (
            position
            + ("" if animation == "word-pop" else fade)
            + starts[animation]
            + rf"\t(0,{duration},0.6,{target})"
        )
    if animation == "bounce":
        peak = round(duration * 0.65)
        return (
            position
            + rf"\fscx{stretch * 0.8:g}\fscy80\t(0,{peak},0.6,\fscx{stretch * 1.06:g}\fscy106)\t({peak},{duration},0.6,\fscx{stretch:g}\fscy100)"
        )
    offsets = {
        "rise": (0, 0.65),
        "fall": (0, -0.55),
        "slide-left": (-1.2, 0),
        "slide-right": (1.2, 0),
    }
    if animation in offsets:
        dx, dy = offsets[animation]
        return rf"\move({round(x + dx * size)},{round(y + dy * size)},{x},{y},0,{duration})" + fade
    if animation in {"wipe", "lift-mask"}:
        left = x - text_width * {"left": 0, "center": 0.5, "right": 1}[config.alignment]
        top = y - line_count * size * 0.65
        if animation == "wipe":
            initial = (
                f"{round(left)},{round(top - size)},{round(left)},{round(y + line_count * size)}"
            )
        else:
            bottom = round(y + line_count * size * 0.65)
            initial = f"0,{bottom},{width},{bottom}"
        return position + rf"\clip({initial})\t(0,{duration},\clip(0,0,{width},{height}))"
    return position + (fade if animation == "fade" else "")


def caption_lines(
    words: list[Word], config: CaptionConfig, output_width: int
) -> list[list[tuple[Word, str]]]:
    available = output_width * config.width
    estimated_char_width = (
        (config.size * 0.82 + config.spacing + config.outline * 2)
        * config.font_width
        / 100
        * output_width
        / 1080
    )
    safe_char_limit = max(1, int(available / max(1, estimated_char_width)))
    char_limit = min(config.max_chars_per_line, safe_char_limit)
    tokens: list[tuple[Word, bool]] = []
    for word in words:
        text = clean_caption_text(word.text.strip(), config)
        if not text:
            continue
        characters = list(text)
        chunks = (
            [text]
            if config.word_display == "single"
            else [
                "".join(characters[index : index + char_limit])
                for index in range(0, len(characters), char_limit)
            ]
        )
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
    face = caption_variant(config.font, config.weight, config.italic)
    size = round(config.size * width / 1080)
    align = {"left": 4, "center": 5, "right": 6}[config.alignment]
    border = 3 if config.background and config.animation not in WORD_ANIMATIONS else 1
    outline = config.outline * width / 1080
    if border == 3:
        outline = max(4 * width / 1080, outline)
    margin = round(height * 0.17)
    primary, secondary = ass_color(config.primary_color), ass_color(config.highlight_color)
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
    py = round(min(1 - config.safe_bottom, max(0.08, y)) * height)
    animation = config.animation
    title_face = caption_variant(
        config.font, 400 if overlay.title_style == "Minimal" else 700, False
    )
    watermark_face = caption_variant(config.font, 400, False)
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
; Caption font: {config.font}, weight {face["weight"]}, italic {face["italic"]}
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{face["family"]},{size},{primary},{secondary},{background if border == 3 else stroke},{ass_color(config.shadow_color, f"{round((1 - config.shadow_opacity) * 255):02X}")},{face["weight"]},{-1 if face["italic"] else 0},0,0,{config.font_width:g},100,{config.spacing * width / 1080},0,{border},{outline},{config.shadow * width / 1080},{align},{round(width * (1 - config.width) / 2)},{round(width * (1 - config.width) / 2)},{margin},1
Style: Title,{title_face["family"]},{round(size * 1.15)},{primary},{secondary},&H00141414,&H80000000,{title_face["weight"]},0,0,0,100,100,0,0,{title_border},3,1,8,{round(width * 0.08)},{round(width * 0.08)},{round(height * 0.1)},1
Style: Watermark,{watermark_face["family"]},{max(14, round(size * 0.55))},{ass_color(config.primary_color, "70")},{secondary},&H00141414,&H80000000,{watermark_face["weight"]},0,0,0,100,100,0,0,1,1,0,{watermark_align},{round(width * 0.04)},{round(width * 0.04)},{watermark_margin},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []

    def event(left: float, right: float, style: str, text: str, layer: int = 0) -> None:
        if right > left:
            events.append(
                f"Dialogue: {layer},{timestamp(left)},{timestamp(right)},{style},,0,0,0,,{text}"
            )

    if config.enabled:
        for segment in speech_captions(segments, start, end, config.cues):
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
            layout = (
                config.model_copy(update={"max_words": 1, "lines": 1})
                if config.word_display == "single"
                else config
            )
            lines = caption_lines(words, layout, width)
            group_size = layout.lines
            for index in range(0, len(lines), group_size):
                group = lines[index : index + group_size]
                group_words = [word for line in group for word, _ in line]
                left = max(start, group_words[0].start) - start
                right = min(end, group_words[-1].end) - start
                if animation in WORD_ANIMATIONS:
                    word_size = size
                    if config.word_display == "single":
                        char_limit = min(
                            config.max_chars_per_line,
                            max(
                                1,
                                int(
                                    config.width
                                    * 1080
                                    / (
                                        (config.size * 0.82 + config.spacing + config.outline * 2)
                                        * config.font_width
                                        / 100
                                    )
                                ),
                            ),
                        )
                        word_size = max(
                            1, round(size * min(1, char_limit / max(1, len(group_words[0].text))))
                        )
                    word_events(group, config, start, left, right, width, py, word_size, event)
                    continue
                duration_ms = max(
                    1, round(min(config.animation_duration, (right - left) * 0.8) * 1000)
                )
                parts = []
                word_position = 0
                for line in group:
                    line_parts = []
                    for word, separator in line:
                        text = escaped(word.text)
                        if config.uppercase:
                            text = text.upper()
                        if animation not in REVEAL_ANIMATIONS and (
                            config.highlight or animation in {"karaoke", "spotlight"}
                        ):
                            following = (
                                group_words[word_position + 1].start
                                if word_position + 1 < len(group_words)
                                else word.end
                            )
                            begin = max(0, round((word.start - start - left) * 1000))
                            finish = max(begin + 1, round((following - start - left) * 1000))
                            tags = (
                                rf"\1c{primary}\1a&H{'99' if animation == 'spotlight' else '00'}&"
                            )
                            tags += rf"\t({begin},{begin + 1},\1c{secondary}\1a&H00&)"
                            if animation != "karaoke":
                                tags += rf"\t({finish},{finish + 1},\1c{primary}\1a&H{'99' if animation == 'spotlight' else '00'}&)"
                            text = "{" + tags + "}" + text
                        elif animation == "word-reveal":
                            delay = round(word_position / len(group_words) * duration_ms)
                            text = (
                                rf"{{\alpha&HFF&\t({delay},{delay + 1},\alpha&H00&\4a&H{round((1 - config.shadow_opacity) * 255):02X}&)}}"
                                + text
                            )
                        line_parts.append(separator + text)
                        word_position += 1
                    parts.append("".join(line_parts))
                text = r"\N".join(parts)
                raw_lines = [
                    "".join(separator + word.text for word, separator in line) for line in group
                ]
                if config.uppercase:
                    raw_lines = [line.upper() for line in raw_lines]
                tags = entrance_tags(
                    config,
                    duration_ms,
                    width,
                    height,
                    round(config.x * width),
                    py,
                    size,
                    len(group),
                    max(len(line) for line in raw_lines)
                    * (size * 0.82 + config.spacing * width / 1080)
                    * config.font_width
                    / 100,
                )
                if animation in {"color-reveal", "typewriter"}:
                    text = color_reveal_text(raw_lines, config, duration_ms)
                event(
                    left,
                    right,
                    "Caption",
                    "{" + tags + "}" + text,
                )
    if overlay.title:
        event(0, min(5, end - start), "Title", escaped(overlay.title))
    if overlay.watermark:
        event(0, end - start, "Watermark", escaped(overlay.watermark))
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
