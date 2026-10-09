import type { CaptionStyle } from "./editor-types";

export type CaptionToken = {
  text: string;
  wordIndex: number;
  separator: string;
};

export function sanitizeCaptionText(text: string, style: CaptionStyle): string {
  let cleaned = text;
  if (style.punctuation === false) cleaned = cleaned.replace(/\p{P}+/gu, "");
  if (style.remove_special_characters)
    cleaned = cleaned.replace(/[\p{S}\p{C}]/gu, "");
  return cleaned.replace(/\s+/gu, " ").trim();
}

export function safeCharacterLimit(style: CaptionStyle): number {
  const requested = style.max_chars_per_line ?? 24;
  const width = Math.max(0.01, style.width ?? 0.84) * 1080;
  const glyphEstimate =
    ((style.size ?? 54) * 0.82 + (style.spacing ?? 0) + (style.outline ?? 0) * 2) *
    (Math.max(75, Math.min(150, style.font_width ?? 100)) / 100);
  return Math.max(1, Math.min(requested, Math.floor(width / glyphEstimate)));
}

export function layoutCaptionWords(
  words: string[],
  characterLimit: number,
  style: CaptionStyle,
): CaptionToken[][] {
  const limit = Math.max(1, Math.floor(characterLimit));
  const lines: CaptionToken[][] = [];
  let line: CaptionToken[] = [];
  let lineLength = 0;
  let wordCount = 0;

  words.forEach((rawWord, wordIndex) => {
    const word = sanitizeCaptionText(rawWord, style);
    if (!word) return;
    const characters = Array.from(word);
    const chunks: string[] = [];
    if (style.word_display === "single") chunks.push(word);
    else
      for (let index = 0; index < characters.length; index += limit)
        chunks.push(characters.slice(index, index + limit).join(""));

    chunks.forEach((chunk, chunkIndex) => {
      let separator = line.length && chunkIndex === 0 ? " " : "";
      if (
        line.length &&
        (lineLength + separator.length + Array.from(chunk).length > limit ||
          (chunkIndex === 0 && wordCount >= (style.max_words ?? 5)))
      ) {
        lines.push(line);
        line = [];
        lineLength = 0;
        wordCount = 0;
        separator = "";
      }
      if (!line.length || chunkIndex === 0) wordCount += 1;
      line.push({ text: chunk, wordIndex, separator });
      lineLength += separator.length + Array.from(chunk).length;
    });
  });

  if (line.length) lines.push(line);
  return lines;
}
