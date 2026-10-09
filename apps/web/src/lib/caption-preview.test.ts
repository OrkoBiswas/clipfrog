import { describe, expect, it } from "vitest";
import { captionFrame, sampleWords } from "./caption-preview";

describe("caption preview timeline", () => {
  it("keeps punctuation pauses and monotonically increasing sample timestamps", () => {
    const words = sampleWords("Wait. Make this count");
    expect(words[0].end).toBeGreaterThan(sampleWords("Wait")[0].end);
    expect(words[1].start).toBe(words[0].end);
    expect(words.at(-1)!.end).toBeGreaterThan(words[0].end);
  });
  it("seeks forward and backward across caption groups", () => {
    const words = sampleWords("one two three four five six");
    const style = { max_words: 2, lines: 1, animation: "word-pop" as const };
    expect(
      captionFrame(words, words[4].start + 0.01, style)
        .lines.flat()
        .map((word) => word.text),
    ).toEqual(["five", "six"]);
    expect(
      captionFrame(words, 0, style)
        .lines.flat()
        .map((word) => word.text),
    ).toEqual(["one", "two"]);
    expect(captionFrame(words, 100, style).activeWord).toBe(5);
  });
  it("handles empty or removed words without invalid timing", () => {
    expect(captionFrame([], 0, {}).lines).toEqual([]);
    const words = sampleWords("$ !!! hello");
    expect(
      captionFrame(words, 0, {
        remove_special_characters: true,
        punctuation: false,
      }).activeWord,
    ).toBe(2);
  });
  it("does not highlight a future word during a pause", () => {
    const words = [
      { text: "Wait", start: 0, end: 0.2 },
      { text: "now", start: 1, end: 1.5 },
    ];
    expect(captionFrame(words, 0.7, {}).activeWord).toBe(0);
    expect(captionFrame(words, 1.01, {}).activeWord).toBe(1);
  });
  it("keeps long single words intact instead of dropping the end", () => {
    const words = sampleWords("Something extraordinary happens");
    const frame = captionFrame(words, words[1].start + 0.1, {
      word_display: "single",
      size: 90,
      max_words: 5,
      lines: 2,
    });
    expect(frame.lines.flat().map((token) => token.text)).toEqual([
      "extraordinary",
    ]);
  });
});
