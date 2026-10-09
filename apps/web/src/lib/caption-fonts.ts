import catalog from "../../../../packages/shared/caption-fonts.json";
import type { CSSProperties } from "react";
import type { CaptionStyle } from "./editor-types";

export const CAPTION_FONT_CATALOG = catalog;
export const CAPTION_FONTS = catalog.map((font) => font.family);
export const FONT_WEIGHT_LABELS: Record<number, string> = {
  100: "Thin",
  200: "Extra Light",
  300: "Light",
  400: "Regular",
  500: "Medium",
  600: "Semi Bold",
  700: "Bold",
  800: "Extra Bold",
  900: "Black",
};

export function captionFont(family?: string) {
  return (
    catalog.find((font) => font.family === family) ??
    catalog.find((font) => font.family === "DejaVu Sans")!
  );
}

export function normalizeCaptionTypography(style: CaptionStyle): CaptionStyle {
  const font = captionFont(style.font);
  const requested = Number.isFinite(style.weight) ? style.weight! : 700;
  const weight = font.weights.reduce((nearest, next) =>
    Math.abs(next - requested) <= Math.abs(nearest - requested) ? next : nearest,
  );
  return {
    ...style,
    font: font.family,
    weight,
    italic: !!style.italic && font.italic,
    font_width: Math.max(
      75,
      Math.min(150, Number.isFinite(style.font_width) ? style.font_width! : 100),
    ),
  };
}

/** Keep the scaled text inside the same caption box at every alignment. */
export function captionWidthCSS(style: CaptionStyle): CSSProperties {
  const factor = (normalizeCaptionTypography(style).font_width ?? 100) / 100;
  const alignment = style.alignment ?? "center";
  const anchor = alignment === "left" ? 0 : alignment === "right" ? 1 : 0.5;
  return {
    display: "block",
    width: `${100 / factor}%`,
    marginLeft: `${(100 - 100 / factor) * anchor}%`,
    transform: `scaleX(${factor})`,
    transformOrigin: `${alignment} center`,
  };
}
