import { describe, expect, it } from "vitest";
import { projectSchema } from "./validation";
const valid = {
  name: "Episode one",
  content_type: "Podcast",
  language: "auto",
  clip_count: 10,
  duration_min: 20,
  duration_max: 35,
  ratios: ["9:16"],
  captions: true,
};
describe("project configuration", () => {
  it("accepts podcast defaults", () =>
    expect(projectSchema.safeParse(valid).success).toBe(true));
  it("rejects invalid duration ranges", () =>
    expect(
      projectSchema.safeParse({ ...valid, duration_min: 40 }).success,
    ).toBe(false));
  it("requires an aspect ratio", () =>
    expect(projectSchema.safeParse({ ...valid, ratios: [] }).success).toBe(
      false,
    ));
  it("enforces count and project name", () => {
    expect(projectSchema.safeParse({ ...valid, clip_count: 101 }).success).toBe(
      false,
    );
    expect(projectSchema.safeParse({ ...valid, name: " " }).success).toBe(
      false,
    );
  });
});
