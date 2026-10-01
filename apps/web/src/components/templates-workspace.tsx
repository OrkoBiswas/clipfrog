"use client";
import { useState } from "react";
import { CaptionStudio } from "./caption-studio";
import type { CaptionStyle } from "@/lib/editor-types";
export function TemplatesWorkspace() {
  const [value, setValue] = useState<CaptionStyle>({
    enabled: true,
    style: "Clean",
  });
  return (
    <section className="templates-workspace">
      <CaptionStudio value={value} onChange={setValue} />
    </section>
  );
}
