"use client";

import Image from "next/image";
import { useState } from "react";
import { Captions, Maximize2, ScanLine } from "lucide-react";

const formats = [
  { ratio: "9:16", label: "Shorts & Reels", className: "portrait" },
  { ratio: "1:1", label: "Social posts", className: "square" },
  { ratio: "16:9", label: "Widescreen", className: "landscape" },
] as const;

/** An explicit style sample, never presented as the user's media or a render. */
export function StudioShowcase() {
  const [format, setFormat] = useState(0);
  const [captions, setCaptions] = useState(true);
  return (
    <div className="studio-showcase">
      <div className="showcase-topline">
        <span>
          <ScanLine size={13} aria-hidden="true" /> THE SAME STORY. A NEW
          FORMAT.
        </span>
        <span className="showcase-demo-label">Style preview</span>
      </div>
      <div className="showcase-stage">
        <div className="showcase-source">
          <Image
            src="/images/creator-studio.png"
            alt="Podcast creator recording a conversation in a studio"
            fill
            sizes="(max-width: 767px) 90vw, 540px"
            priority
          />
          <span className="showcase-source-label">YOUR LONG-FORM STORY</span>
        </div>
        <div
          className={`showcase-cut showcase-cut-${formats[format].className}`}
        >
          <Image
            src="/images/creator-studio.png"
            alt=""
            fill
            sizes="260px"
            priority
          />
          <span className="showcase-format">
            <Maximize2 size={11} /> {formats[format].ratio}
          </span>
          {captions && (
            <div className="showcase-caption" key={format}>
              Every story
              <br />
              has <mark>a moment.</mark>
            </div>
          )}
          <span className="showcase-cut-label">MAKE IT YOURS</span>
        </div>
      </div>
      <div className="showcase-controls">
        <div
          className="showcase-ratios"
          role="group"
          aria-label="Preview aspect ratio"
        >
          {formats.map((item, index) => (
            <button
              key={item.ratio}
              type="button"
              aria-pressed={index === format}
              title={item.label}
              onClick={() => setFormat(index)}
            >
              {item.ratio}
            </button>
          ))}
        </div>
        <button
          className="showcase-caption-toggle"
          type="button"
          aria-label="Show sample captions"
          aria-pressed={captions}
          onClick={() => setCaptions(!captions)}
        >
          <Captions size={16} />
          <span>Captions</span>
        </button>
      </div>
    </div>
  );
}
