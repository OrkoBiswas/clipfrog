import { describe, expect, it } from "vitest";
import { layoutCaptionWords, sanitizeCaptionText } from "./caption-layout";

describe("caption text layout", () => {
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
