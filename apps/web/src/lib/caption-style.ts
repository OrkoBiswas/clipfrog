import type { CSSProperties } from "react";
import type { CaptionStyle } from "./editor-types";
import { normalizeCaptionTypography } from "./caption-fonts";

export function captionCSS(config: CaptionStyle, scale = 1): CSSProperties {
  const typography = normalizeCaptionTypography(config);
  return {
    fontFamily: `'${typography.font}', sans-serif`,
    fontWeight: typography.weight,
    fontStyle: typography.italic ? "italic" : "normal",
    fontSynthesis: "none",
    fontSize: (config.size ?? 54) * scale,
    color: config.primary_color ?? "#ffffff",
    WebkitTextStroke: `${(config.outline ?? 3) * scale}px ${config.stroke_color ?? "#141414"}`,
    paintOrder: "stroke fill",
    letterSpacing: (config.spacing ?? 0) * scale,
    textTransform: config.uppercase ? "uppercase" : "none",
    textAlign: (config.alignment ?? "center") as CSSProperties["textAlign"],
    textShadow:
      config.shadow === 0
        ? "none"
        : `${(config.shadow ?? 1) * scale}px ${(config.shadow ?? 1) * scale}px ${2 * scale}px ${config.shadow_color ?? "#000000"}${Math.round(
            (config.shadow_opacity ?? 0.6) * 255,
          )
            .toString(16)
            .padStart(2, "0")}`,
    backgroundColor: config.background
      ? `${config.background_color ?? "#000000"}${Math.round(
          (config.background_opacity ?? 0.65) * 255,
        )
          .toString(16)
          .padStart(2, "0")}`
      : "transparent",
    lineHeight: 1.2,
    padding: config.background ? `${4 * scale}px ${8 * scale}px` : 0,
  };
}
