"use client";
import type { CaptionStyle, FramingStyle } from "@/lib/editor-types";
import { captionCSS } from "@/lib/caption-style";
import { CaptionLivePreview } from "./caption-live-preview";
import { CaptionControls } from "./caption-controls";
import "./studio.css";
export { captionCSS };

export function CaptionStudio({
  value,
  onChange,
  framing,
  onFramingChange,
  compact = false,
}: {
  value: CaptionStyle;
  onChange: (value: CaptionStyle) => void;
  framing?: FramingStyle;
  onFramingChange?: (value: FramingStyle) => void;
  compact?: boolean;
}) {
  const name =
    value.style && value.style !== "Clean" ? value.style : "Basic Word Pop";
  return (
    <section className="caption-studio" aria-label="Subtitles">
      <div className="studio-caption-heading">
        <h3>Subtitles</h3>
        <span className="muted">{name}</span>
      </div>
      <div
        className={`caption-studio-workbench ${compact ? "is-compact" : ""}`}
      >
        {compact && (
          <details className="caption-preview-details">
            <summary>Preview subtitles</summary>
            <CaptionLivePreview value={value} name={name} />
          </details>
        )}
        <CaptionControls
          value={value}
          onChange={onChange}
          framing={framing}
          onFramingChange={onFramingChange}
        />
        {!compact && <CaptionLivePreview value={value} name={name} />}
      </div>
    </section>
  );
}
