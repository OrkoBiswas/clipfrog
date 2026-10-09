import { describe, expect, it } from "vitest";
import { automaticFraming, changeLayout, cropAtTime, multipleScreens, panelsForLayout } from "./split-screen";

describe("split screen settings", () => {
  it("turns a legacy customized layout into automatic collage without changing quality", () => {
    const old = { layout: "grid" as const, quality: "High", panels: [{ subject: "center" as const, zoom: 2 }] };
    expect(automaticFraming(old)).toEqual({ layout: "auto", quality: "High", panels: [] });
    expect(multipleScreens(old, false)).toEqual({ layout: "single", quality: "High", panels: [] });
    expect(multipleScreens(old, true)).toEqual({ layout: "auto", quality: "High", panels: [] });
  });
  it("assigns different people and keeps manual crops when changing layouts", () => {
    const initial = changeLayout({ zoom: 1.5 }, "stacked");
    expect(initial.panels?.map((panel) => panel.subject)).toEqual(["person-1", "person-2"]);
    initial.panels![0] = { ...initial.panels![0], anchor_x: 0.2, anchor_y: 0.4, zoom: 2 };
    const grid = changeLayout(initial, "grid", 3);
    expect(grid.panels).toHaveLength(3);
    expect(grid.panels?.[0]).toMatchObject({ anchor_x: 0.2, anchor_y: 0.4, zoom: 2 });
    expect(grid.panels?.[2].subject).toBe("person-3");
    const single = changeLayout(grid, "single");
    expect(single.zoom).toBe(1.5);
    expect(changeLayout(single, "grid").panels).toEqual(grid.panels);
    expect(changeLayout(grid, "side-by-side").panels).toHaveLength(2);
  });

  it("supplies valid defaults to saved clips without split settings", () => {
    expect(panelsForLayout({ layout: "grid" })).toHaveLength(4);
    expect(panelsForLayout({ layout: "stacked" })).toHaveLength(2);
  });
});

describe("preview/export crop timing", () => {
  const keys = [
    { time: 0, x: 20, y: 40, cut: false },
    { time: 2, x: 100, y: 80, cut: false },
    { time: 4, x: 200, y: 200, cut: true },
  ];
  it("interpolates motion and holds a shot until its hard cut", () => {
    expect(cropAtTime(keys, -1)).toMatchObject({ x: 20, y: 40 });
    expect(cropAtTime(keys, 1)).toMatchObject({ x: 60, y: 60 });
    expect(cropAtTime(keys, 3.99)).toMatchObject({ x: 100, y: 80 });
    expect(cropAtTime(keys, 4)).toMatchObject({ x: 200, y: 200 });
    expect(cropAtTime(keys, 12)).toMatchObject({ x: 200, y: 200 });
  });
});
