import {
  layoutCaptionWords,
  safeCharacterLimit,
  sanitizeCaptionText,
} from "./caption-layout";
import type { CaptionStyle } from "./editor-types";

// Sample timing is illustrative. Actual clip previews use transcript timestamps.
export function sampleWords(text: string) {
  let cursor = 0;
  return text
    .trim()
    .split(/\s+/u)
    .filter(Boolean)
    .map((text) => {
      const start = cursor;
      cursor +=
        Math.min(0.65, Math.max(0.28, Array.from(text).length * 0.055)) +
        (/[,.!?;:]$/u.test(text) ? 0.2 : 0);
      return { text, start, end: cursor };
    });
}

export function captionFrame(
  words: ReturnType<typeof sampleWords>,
  seconds: number,
  style: CaptionStyle,
) {
  const visibleWords = words
    .map((word, index) => ({ ...word, index }))
    .filter((word) => sanitizeCaptionText(word.text, style));
  const activeWord =
    visibleWords.findLast((word) => word.start <= seconds)?.index ??
    visibleWords[0]?.index ??
    -1;
  const lines = layoutCaptionWords(
    words.map((word) => word.text),
    safeCharacterLimit(style),
    style.word_display === "single" ? { ...style, max_words: 1 } : style,
  );
  const activeLine = Math.max(
    0,
    lines.findIndex((line) =>
      line.some((token) => token.wordIndex === activeWord),
    ),
  );
  const count =
    style.word_display === "single" ? 1 : Math.max(1, style.lines ?? 2);
  const group = Math.floor(activeLine / count) * count;
  const shown = lines.slice(group, group + count);
  const first = shown[0]?.[0]?.wordIndex;
  const last = shown.at(-1)?.at(-1)?.wordIndex;
  return {
    lines: shown,
    activeWord,
    group,
    start: words[first ?? 0]?.start ?? 0,
    end: words[last ?? 0]?.end ?? 1,
  };
}
