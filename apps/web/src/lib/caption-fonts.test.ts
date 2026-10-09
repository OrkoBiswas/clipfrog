import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  CAPTION_FONT_CATALOG,
  captionWidthCSS,
  normalizeCaptionTypography,
} from "./caption-fonts";
import { safeCharacterLimit } from "./caption-layout";
import { captionCSS } from "./caption-style";

const root = new URL("../../../../", import.meta.url);
function read(path: string) {
  return readFileSync(fileURLToPath(new URL(path, root)));
}

function tables(font: Buffer) {
  const result = new Map<string, { offset: number; checksum: number }>();
  for (let i = 0; i < font.readUInt16BE(4); i++) {
    const offset = 12 + i * 16;
    result.set(font.toString("ascii", offset, offset + 4), {
      checksum: font.readUInt32BE(offset + 4),
      offset: font.readUInt32BE(offset + 8),
    });
  }
  return result;
}

describe("bundled caption fonts", () => {
  it("ships every listed face, exact native weight and browser source with licenses", () => {
    const css = read("apps/web/src/app/caption-fonts.css").toString();
    const names = new Set<string>();
    expect(CAPTION_FONT_CATALOG).toHaveLength(16);
    expect(read("apps/api/clipforge_api/caption-fonts.json").toString()).toBe(
      read("packages/shared/caption-fonts.json").toString(),
    );
    for (const family of CAPTION_FONT_CATALOG) {
      const outlines = new Set<string>();
      expect(family.variants.filter((variant) => !variant.italic).map((v) => v.weight)).toEqual(family.weights);
      for (const variant of family.variants) {
        const font = read(`assets/fonts/${variant.file}`);
        const fontTables = tables(font);
        expect(font.readUInt32BE(0), variant.file).toBe(0x00010000);
        expect(fontTables.has("fvar"), variant.file).toBe(false);
        expect(font.readUInt16BE(fontTables.get("OS/2")!.offset + 4), variant.file).toBe(variant.weight);
        const outline = `${variant.italic}:${fontTables.get("glyf")!.checksum}`;
        expect(outlines.has(outline), `${variant.file} duplicates another weight`).toBe(false);
        outlines.add(outline);
        expect(names.has(variant.family)).toBe(false);
        names.add(variant.family);
        expect(read(`apps/web/public/fonts/${variant.web_file}`).toString("ascii", 0, 4)).toBe("wOF2");
        expect(css).toContain(`url("/fonts/${variant.web_file}")`);
        const folder = variant.file.slice(0, variant.file.lastIndexOf("/"));
        const license = family.family === "DejaVu Sans" ? "LICENSE.txt" : "OFL.txt";
        expect(read(`assets/fonts/${folder}/${license}`).length).toBeGreaterThan(1000);
      }
    }
  });

  it("keeps real Medium/Black/Italic and selects valid faces on family changes", () => {
    for (const weight of [500, 900]) {
      expect(normalizeCaptionTypography({ font: "Urbanist", weight, italic: true })).toMatchObject({ weight, italic: true });
    }
    expect(normalizeCaptionTypography({ font: "Bebas Neue", weight: 900, italic: true })).toMatchObject({ weight: 400, italic: false });
    expect(normalizeCaptionTypography({ font: "Lato", weight: 600 })).toMatchObject({ weight: 700 });
    expect(normalizeCaptionTypography({ font: "missing font", weight: 500 })).toMatchObject({ font: "DejaVu Sans", weight: 400 });
    expect(captionCSS({ font: "Oswald", weight: 900, italic: true })).toMatchObject({ fontWeight: 700, fontStyle: "normal", fontSynthesis: "none" });
  });

  it("fits condensed and wide lettering inside the same aligned caption box", () => {
    const base = { width: 0.84, max_chars_per_line: 80, size: 54 };
    expect(safeCharacterLimit({ ...base, font_width: 125 })).toBeLessThan(safeCharacterLimit(base));
    expect(safeCharacterLimit({ ...base, font_width: 75 })).toBeGreaterThan(safeCharacterLimit(base));
    expect(captionWidthCSS({ font_width: 125, alignment: "center" })).toMatchObject({ width: "80%", marginLeft: "10%", transform: "scaleX(1.25)", transformOrigin: "center center" });
    expect(captionWidthCSS({ font_width: 125, alignment: "left" }).marginLeft).toBe("0%");
    expect(captionWidthCSS({ font_width: 125, alignment: "right" }).marginLeft).toBe("20%");
    expect(normalizeCaptionTypography({ font_width: 999 }).font_width).toBe(150);
    expect(normalizeCaptionTypography({ font_width: Number.NaN }).font_width).toBe(100);
  });
});
