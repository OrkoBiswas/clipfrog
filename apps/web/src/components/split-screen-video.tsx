"use client";

import { useEffect, useRef, type RefObject } from "react";
import type { PreviewData } from "@/lib/editor-types";
import { cropAtTime } from "@/lib/split-screen";

// One decoder and one audio track keep every view on exactly the same frame.
export function SplitScreenVideo({ video, plan, start }: {
  video: RefObject<HTMLVideoElement | null>;
  plan: PreviewData["plan"];
  start: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const source = video.current, surface = canvas.current;
    const context = surface?.getContext("2d");
    if (!source || !surface || !context) return;
    let frame = 0;
    function paint() {
      if (!source || !surface || !context || source.readyState < 2) return;
      context.clearRect(0, 0, surface.width, surface.height);
      const sx = surface.width / plan.output_width, sy = surface.height / plan.output_height;
      const relative = Math.max(0, source.currentTime - start);
      const scene = plan.scenes?.find((shot) => relative >= shot.start && relative < shot.end)
        ?? plan.scenes?.at(-1);
      const composition = scene ?? plan;
      const local = relative - (scene?.start ?? 0);
      if (!composition.panels?.length) {
        const crop = cropAtTime(composition.keyframes, local);
        context.drawImage(source, crop.x, crop.y, composition.crop_width, composition.crop_height,
          0, 0, surface.width, surface.height);
      }
      for (const panel of composition.panels ?? []) {
        const crop = cropAtTime(panel.keyframes, local);
        context.drawImage(source, crop.x, crop.y, panel.crop_width, panel.crop_height,
          panel.x * sx, panel.y * sy, panel.width * sx, panel.height * sy);
      }
    }
    function tick() {
      paint();
      if (source && !source.paused && !source.ended) frame = requestAnimationFrame(tick);
    }
    function play() { cancelAnimationFrame(frame); tick(); }
    const observer = new ResizeObserver(() => {
      const width = Math.max(2, Math.round(surface.clientWidth * Math.min(devicePixelRatio, 2)));
      surface.width = width;
      surface.height = Math.max(2, Math.round(width * plan.output_height / plan.output_width));
      paint();
    });
    observer.observe(surface);
    source.addEventListener("play", play);
    source.addEventListener("loadeddata", paint);
    source.addEventListener("seeked", paint);
    source.addEventListener("timeupdate", paint);
    play();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      source.removeEventListener("play", play);
      source.removeEventListener("loadeddata", paint);
      source.removeEventListener("seeked", paint);
      source.removeEventListener("timeupdate", paint);
    };
  }, [video, plan, start]);
  return <canvas ref={canvas} className="split-video-canvas" aria-hidden="true" />;
}
