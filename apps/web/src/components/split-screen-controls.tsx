"use client";

import type { FramingStyle } from "@/lib/editor-types";
import { multipleScreens } from "@/lib/split-screen";
import { Toggle } from "./ui/primitives";
import "./split-screen.css";

export function SplitScreenControls({ value, onChange }: {
  value: FramingStyle;
  onChange: (value: FramingStyle) => void;
}) {
  return (
    <div className="split-screen-controls">
      <Toggle label="Multiple screens" checked={!!value.layout && value.layout !== "single"}
        onChange={(enabled) => onChange(multipleScreens(value, enabled))} />
      <p className="muted">Automatically arrange detected people in a collage. Shots with one person stay full screen.</p>
    </div>
  );
}
