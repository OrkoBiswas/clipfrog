import { describe, expect, it } from "vitest";
import {
  layoutCaptionWords,
  sanitizeCaptionText,
  safeCharacterLimit,
} from "./caption-layout";

describe("caption text layout", () => {
  it("respects caption box width and words per line", () => {
    expect(safeCharacterLimit({ width: 0.3 })).toBeLessThan(
      safeCharacterLimit({ width: 0.84 }),
    );
    const lines = layoutCaptionWords(["one", "two", "three", "four"], 40, {
      max_words: 2,
    });
    expect(
      lines.map((line) =>
        line.map((token) => token.separator + token.text).join(""),
      ),
    ).toEqual(["one two", "three four"]);
  });
  it("removes punctuation and symbols when enabled", () => {
    expect(
      sanitizeCaptionText("Wait?! $5 😊", {
        punctuation: false,
        remove_special_characters: true,
      }),
    ).toBe("Wait 5");
  });

  it("wraps spaces and long words within the selected character count", () => {
    const lines = layoutCaptionWords(["changes", "everything"], 4, {});
    expect(
      lines.map((line) =>
        line.map((token) => token.separator + token.text).join(""),
      ),
    ).toEqual(["chan", "ges", "ever", "ythi", "ng"]);
  });
});
