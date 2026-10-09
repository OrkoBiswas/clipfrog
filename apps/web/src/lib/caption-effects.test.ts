import { describe, expect, it } from "vitest";
import {
  CAPTION_ANIMATIONS,
  effectProgress,
  revealProgress,
  mixCaptionColor,
  normalizeCaptionAnimation,
  captionMotion,
  isWordAnimation,
  wordMotion,
} from "./caption-effects";
import { CAPTION_TEMPLATES, applyCaptionTemplate } from "./caption-templates";
describe("caption collection", () => {
  it("preserves all supported animations and safely falls back for retired values", () => {
    for (const animation of CAPTION_ANIMATIONS)
      expect(normalizeCaptionAnimation(animation)).toBe(animation);
    for (const legacy of [
      "pop",
      "scale",
      "slide",
      "ink-reveal",
      "echo",
      "mogrt-pack1-01",
      "mogrt-pack1-04",
      "blue-slice",
      "smoke-block",
      "vertical-snap",
      "blue-echo",
    ]) {
      expect(normalizeCaptionAnimation(legacy)).toBe("word-pop");
    }
  });

  it("has 24 distinct usable presets and preserves existing caption cues", () => {
    expect(CAPTION_TEMPLATES).toHaveLength(24);
    expect(
      new Set(CAPTION_TEMPLATES.map((t) => JSON.stringify(t.config))).size,
    ).toBe(24);
    const cues = [{ start_ms: 0, end_ms: 1000, text: "Keep my words" }];
    for (const preset of CAPTION_TEMPLATES) {
      expect(CAPTION_ANIMATIONS).toContain(preset.config.animation);
      expect(isWordAnimation(preset.config.animation!)).toBe(true);
      const applied = applyCaptionTemplate(
        { cues, enabled: false },
        preset.config,
      );
      expect(applied.cues).toEqual(cues);
      expect(applied.enabled).toBe(false);
      expect(applied.font).toBe(preset.config.font);
    }
  });

  it("all entrances settle and seeking is deterministic", () => {
    for (const animation of CAPTION_ANIMATIONS) {
      const settled = captionMotion(animation, 1);
      expect(settled).toMatchObject({
        x: 0,
        y: 0,
        sx: 1,
        sy: 1,
        rotate: 0,
        blur: 0,
        opacity: 1,
      });
      expect(captionMotion(animation, 0.25)).toEqual(
        captionMotion(animation, 0.25),
      );
    }
  });

  it("adapts entrances to short phrases and scrubs deterministically", () => {
    expect(effectProgress(0.4, 2, 0.5)).toBe(1);
    expect(effectProgress(0, 2, 0.5)).toBe(0);
    expect(effectProgress(-1, 1, 1)).toBe(0);
    expect(revealProgress(0, 3, 8)).toBe(0);
    expect(revealProgress(1, 7, 8)).toBe(1);
  });
  it("resolves accent colors into the chosen caption color", () => {
    expect(mixCaptionColor("#0054FF", "#FFFFFF", 0)).toBe("#0054ff");
    expect(mixCaptionColor("#0054FF", "#FF9922", 1)).toBe("#ff9922");
  });
  it("restarts motion for each word and settles before the next word", () => {
    expect(wordMotion("word-rise", 0, 0.3, 0.4).opacity).toBe(0);
    expect(wordMotion("word-rise", 0.31, 0.3, 0.4).opacity).toBe(1);
    expect(wordMotion("word-spring", 0.1, 0.3, 0.12).sx).toBe(1);
    expect(wordMotion("word-punch", 0, 0.3, 0.4, 1.12, true)).toMatchObject({
      sx: 1.12,
      opacity: 1,
      rotate: 0,
    });
  });
});
