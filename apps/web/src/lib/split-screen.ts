import type { CropKeyframe, FramingStyle, PanelStyle, SplitLayout } from "./editor-types";

export function automaticFraming(value: FramingStyle): FramingStyle {
  return value.layout && value.layout !== "single"
    ? { ...value, layout: "auto", panels: [] }
    : value;
}

export function multipleScreens(value: FramingStyle, enabled: boolean): FramingStyle {
  return { ...value, layout: enabled ? "auto" : "single", panels: [] };
}

export function defaultPanels(count: number): PanelStyle[] {
  return Array.from({ length: count }, (_, index) => ({
    subject: `person-${index + 1}` as PanelStyle["subject"],
    anchor_x: null,
    anchor_y: null,
    zoom: 1,
  }));
}

export function panelsForLayout(value: FramingStyle): PanelStyle[] {
  const count = value.layout === "grid" ? (value.panels?.length === 3 ? 3 : 4) : 2;
  return defaultPanels(count).map((panel, index) => value.panels?.[index] ?? panel);
}

export function changeLayout(value: FramingStyle, layout: SplitLayout, count?: number): FramingStyle {
  if (layout === "auto") return multipleScreens(value, true);
  if (layout === "single") return { ...value, layout };
  const size = layout === "grid" ? (count ?? (value.panels?.length === 3 ? 3 : 4)) : 2;
  return {
    ...value,
    layout,
    panels: defaultPanels(size).map((panel, index) => value.panels?.[index] ?? panel),
  };
}

// Match the export interpolation, holding the preceding crop until a hard cut.
export function cropAtTime(keys: CropKeyframe[], seconds: number): { x: number; y: number } {
  if (!keys.length) return { x: 0, y: 0 };
  for (let index = 1; index < keys.length; index++) {
    const previous = keys[index - 1], current = keys[index];
    if (seconds < current.time) {
      if (current.cut || current.time <= previous.time) return previous;
      const amount = Math.max(0, Math.min(1, (seconds - previous.time) / (current.time - previous.time)));
      return { x: previous.x + (current.x - previous.x) * amount, y: previous.y + (current.y - previous.y) * amount };
    }
  }
  return keys[keys.length - 1];
}
