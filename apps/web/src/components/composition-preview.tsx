"use client";
import Image from "next/image";
import { useEffect, useRef, useState, type PointerEvent } from "react";
import { api } from "@/lib/api";
import { layoutCaptionWords, safeCharacterLimit } from "@/lib/caption-layout";
import { captionCSS } from "./caption-studio";
import { Maximize, Pause, Play, Volume2 } from "lucide-react";
import { Toggle } from "./ui/primitives";
import { timecode } from "./studio-controls";
import "./studio.css";
import type {
  CaptionStyle,
  OverlayStyle,
  FramingStyle,
  PreviewData,
} from "@/lib/editor-types";

type Body = {
  title: string;
  start_ms: number;
  end_ms: number;
  aspect_ratio: string;
  caption_config: CaptionStyle;
  overlay_config: OverlayStyle;
  render_config: FramingStyle;
};
export function CompositionPreview({
  projectId,
  body,
  onCaption,
  onOverlay,
  onFraming,
}: {
  projectId: string;
  body: Body;
  onCaption: (value: CaptionStyle) => void;
  onOverlay: (value: OverlayStyle) => void;
  onFraming: (value: FramingStyle) => void;
}) {
  const [data, setData] = useState<PreviewData | null>(null);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [width, setWidth] = useState(360);
  const [logoRatio, setLogoRatio] = useState(1);
  const [safe, setSafe] = useState("YouTube Shorts");
  const [debug, setDebug] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [rendered, setRendered] = useState("");
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(1);
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    kind: string;
    x: number;
    y: number;
    ax: number;
    ay: number;
  } | null>(null);
  const previewKey = JSON.stringify({
    start_ms: body.start_ms,
    end_ms: body.end_ms,
    aspect_ratio: body.aspect_ratio,
    render_config: body.render_config,
    overlay_config: {
      logo_asset_id: body.overlay_config.logo_asset_id ?? null,
    },
  });
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      api<PreviewData>(`/projects/${projectId}/editor-preview`, {
        method: "POST",
        body: JSON.stringify({
          title: "Composition preview",
          ...JSON.parse(previewKey),
        }),
      })
        .then((value) => {
          if (active) {
            setData(value);
            setError("");
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [previewKey, projectId]);
  useEffect(() => {
    if (!canvas.current) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(entries[0].contentRect.width),
    );
    observer.observe(canvas.current);
    return () => observer.disconnect();
  }, [data]);
  const caption = body.caption_config,
    overlay = body.overlay_config,
    framing = body.render_config;
  const plan = data?.plan;
  const relative = Math.max(0, seconds - body.start_ms / 1000);
  const key =
    plan?.keyframes.filter((key) => key.time <= relative).at(-1) ??
    plan?.keyframes[0];
  const scale = width / 1080;
  const aspect = plan ? plan.output_width / plan.output_height : 9 / 16;
  const height = width / aspect;
  const margin = (overlay.logo_margin ?? 0.04) * Math.min(width, height);
  const logoWidth = Math.min(
    width * (overlay.logo_size ?? 0.16),
    height * Math.min(0.3, (overlay.logo_size ?? 0.16) * 0.75) * logoRatio,
  );
  const logoHeight = logoWidth / logoRatio;
  const logoX = Math.max(
    margin,
    Math.min(
      width - logoWidth - margin,
      overlay.logo_x != null
        ? overlay.logo_x * width
        : (overlay.logo_position ?? "top-right").endsWith("left")
          ? margin
          : (overlay.logo_position ?? "top-right").endsWith("center")
            ? (width - logoWidth) / 2
            : width - logoWidth - margin,
    ),
  );
  const logoY = Math.max(
    margin,
    Math.min(
      height - logoHeight - margin,
      overlay.logo_y != null
        ? overlay.logo_y * height
        : (overlay.logo_position ?? "top-right").startsWith("top")
          ? margin
          : (overlay.logo_position ?? "top-right").startsWith("middle")
            ? (height - logoHeight) / 2
            : height - logoHeight - margin,
    ),
  );
  const segments = caption.cues
    ? caption.cues.map((cue) => ({
        start: body.start_ms / 1000 + cue.start_ms / 1000,
        end: body.start_ms / 1000 + cue.end_ms / 1000,
        text: cue.text,
        words: [],
      }))
    : (data?.segments ?? []);
  const segment = segments.find(
    (segment) => seconds >= segment.start && seconds < segment.end,
  );
  const words = segment?.words.length
    ? segment.words
    : (segment?.text.split(/\s+/).map((text, index, array) => ({
        text,
        start:
          segment.start +
          ((segment.end - segment.start) * index) / array.length,
        end:
          segment.start +
          ((segment.end - segment.start) * (index + 1)) / array.length,
      })) ?? []);
  const activeWord = Math.max(
    0,
    words.findIndex((word) => word.end > seconds),
  );
  const wrappedLines = layoutCaptionWords(
    words.map((word) => word.text),
    safeCharacterLimit(caption),
    caption,
  );
  const activeLine = Math.max(
    0,
    wrappedLines.findIndex((line) =>
      line.some((token) => token.wordIndex === activeWord),
    ),
  );
  const linesPerGroup =
    caption.animation === "word-pop" ? 1 : (caption.lines ?? 2);
  const groupStart = Math.floor(activeLine / linesPerGroup) * linesPerGroup;
  const displayLines = wrappedLines.slice(
    groupStart,
    groupStart + linesPerGroup,
  );
  const showingSample = !segment;
  const safeBottom =
    safe === "TikTok"
      ? 0.25
      : safe === "Instagram Reels" || safe === "Facebook Reels"
        ? 0.22
        : 0.17;
  const captionY = Math.min(
    1 - (caption.safe_bottom ?? 0.17),
    Math.max(0.08, caption.y ?? 0.78),
  );
  const warning =
    captionY > 1 - safeBottom ||
    (overlay.logo_enabled !== false &&
      !!data?.logo_url &&
      (logoY + logoHeight) / height > 1 - safeBottom);
  function begin(event: PointerEvent, kind: string) {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = {
      kind,
      x: event.clientX,
      y: event.clientY,
      ax:
        kind === "caption"
          ? (caption.x ?? 0.5)
          : kind === "logo"
            ? logoX / width
            : plan && key
              ? (key.x + plan.crop_width / 2) / plan.source_width
              : 0.5,
      ay:
        kind === "caption"
          ? (caption.y ?? 0.78)
          : kind === "logo"
            ? logoY / height
            : plan && key
              ? (key.y + plan.crop_height / 2) / plan.source_height
              : 0.5,
    };
  }
  function move(event: PointerEvent) {
    const d = drag.current;
    if (!d) return;
    const dx = (event.clientX - d.x) / width,
      dy = (event.clientY - d.y) / height;
    const clamp = (n: number, min = 0, max = 1) =>
      Math.max(min, Math.min(max, n));
    if (d.kind === "caption")
      onCaption({
        ...caption,
        x: clamp(d.ax + dx, 0.05, 0.95),
        y: clamp(d.ay + dy, 0.05, 0.95),
      });
    if (d.kind === "logo")
      onOverlay({
        ...overlay,
        logo_x: clamp(d.ax + dx),
        logo_y: clamp(d.ay + dy),
      });
    if (d.kind === "video" && plan)
      onFraming({
        ...framing,
        anchor_x: clamp(d.ax - (dx * plan.crop_width) / plan.source_width),
        anchor_y: clamp(d.ay - (dy * plan.crop_height) / plan.source_height),
        lock_camera: true,
      });
  }
  async function renderSample() {
    setRendering(true);
    setError("");
    try {
      const task = await api<{ job_id: string; clip_ids: string[] }>(
        `/projects/${projectId}/render-preview`,
        { method: "POST", body: JSON.stringify(body) },
      );
      for (let i = 0; i < 120; i++) {
        const jobs = await api<
          { id: string; status: string; error_message: string }[]
        >(`/projects/${projectId}/jobs`);
        const job = jobs.find((item) => item.id === task.job_id);
        if (job?.status === "SUCCEEDED") {
          const media = await api<{ url: string }>(
            `/projects/${projectId}/clips/${task.clip_ids[0]}/media`,
          );
          setRendered(media.url);
          return;
        }
        if (job && ["FAILED", "CANCELED"].includes(job.status))
          throw new Error(job.error_message ?? "Preview canceled");
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      throw new Error("Preview is still processing; check project status.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setRendering(false);
    }
  }
  return (
    <section className="composition-editor">
      <div className="section-head">
        <h3>Composition preview</h3>
        <span className="badge">{body.aspect_ratio} · Instant preview</span>
      </div>
      <div className="studio-preview-workspace">
        <div
          className="composition-stage"
          ref={canvas}
        tabIndex={0}
        role="group"
        aria-label="Video composition. Space to play or pause. Arrow keys to seek."
        onKeyDown={(event) => {
          if (!video.current) return;
          if (event.key === " ") { event.preventDefault(); if (video.current.paused) void video.current.play().catch(() => setError("Playback could not start. Try again.")); else video.current.pause(); }
          if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); video.current.currentTime = Math.max(body.start_ms / 1000, Math.min(body.end_ms / 1000, video.current.currentTime + (event.key === "ArrowRight" ? 1 : -1))); }
        }}
          style={{
            aspectRatio: aspect,
            width: `min(100%, ${aspect * 420}px)`,
            height: "auto",
          }}
          onPointerMove={move}
          onPointerUp={() => {
            drag.current = null;
          }}
          onPointerCancel={() => {
            drag.current = null;
          }}
        >
          {!data && (
            <div className="studio-preview-loading" role="status">
              Preparing your preview...
            </div>
          )}
          {data && plan && key && (
            <video
              ref={video}
              src={data.source_url}
              playsInline
              preload="metadata"
              onLoadedMetadata={(e) => {
                e.currentTarget.currentTime = body.start_ms / 1000;
                setSeconds(body.start_ms / 1000);
              }}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onTimeUpdate={(e) => {
                setSeconds(e.currentTarget.currentTime);
                if (e.currentTarget.currentTime >= body.end_ms / 1000) {
                  e.currentTarget.pause();
                  e.currentTarget.currentTime = body.start_ms / 1000;
                }
              }}
              style={{
                position: "absolute",
                maxWidth: "none",
                width: `${(plan.source_width / plan.crop_width) * 100}%`,
                height: `${(plan.source_height / plan.crop_height) * 100}%`,
                left: `${(-key.x / plan.crop_width) * 100}%`,
                top: `${(-key.y / plan.crop_height) * 100}%`,
              }}
              onPointerDown={(e) => begin(e, "video")}
              onError={() =>
                setError(
                  "This source codec cannot play in this browser. Use the four-second render preview to check the composition.",
                )
              }
            />
          )}
          {safe !== "Off" && (
            <div
              className="safe-zone"
              style={{ bottom: `${safeBottom * 100}%` }}
            >
              <small>{safe} safe area</small>
            </div>
          )}
          {caption.enabled !== false && (
            <div
              className={`live-caption caption-${caption.animation ?? "none"}`}
              key={`${groupStart}-${segment?.start ?? "sample"}-${caption.animation}`}
              onPointerDown={(e) => begin(e, "caption")}
              style={{
                ...captionCSS(caption, scale),
                position: "absolute",
                left: `${(caption.x ?? 0.5) * 100}%`,
                top: `${captionY * 100}%`,
                width: `${(caption.width ?? 0.84) * 100}%`,
                transform: `translate(${caption.alignment === "left" ? 0 : caption.alignment === "right" ? -100 : -50}%, -50%)`,
              }}
            >
              {displayLines.map((line, lineIndex) => (
                <span className="caption-live-line" key={lineIndex}>
                  {line.map((token, tokenIndex) => (
                    <span
                      key={`${token.wordIndex}-${tokenIndex}`}
                      style={{
                        color:
                          (caption.highlight ||
                            caption.animation === "karaoke") &&
                          words[token.wordIndex]?.start <= seconds &&
                          words[token.wordIndex]?.end > seconds
                            ? caption.highlight_color
                            : undefined,
                      }}
                    >
                      {token.separator}
                      {token.text}
                    </span>
                  ))}
                  {lineIndex < displayLines.length - 1 && <br />}
                </span>
              ))}
            </div>
          )}
          {data?.logo_url && overlay.logo_enabled !== false && (
            <Image
              unoptimized
              src={data.logo_url}
              alt="Brand logo"
              width={300}
              height={300}
              draggable={false}
              onLoad={(e) =>
                setLogoRatio(
                  e.currentTarget.naturalWidth / e.currentTarget.naturalHeight,
                )
              }
              onPointerDown={(e) => begin(e, "logo")}
              style={{
                position: "absolute",
                left: logoX,
                top: logoY,
                width: logoWidth,
                height: logoHeight,
                opacity: overlay.logo_opacity ?? 1,
                cursor: "move",
                touchAction: "none",
              }}
            />
          )}
          {overlay.title && relative < 5 && (
            <div
              className="preview-title"
              style={{
                ...captionCSS(
                  {
                    ...caption,
                    size: (caption.size ?? 54) * 1.15,
                    background: overlay.title_style === "Boxed",
                    weight: overlay.title_style === "Minimal" ? 400 : 700,
                  },
                  scale,
                ),
              }}
            >
              {overlay.title}
            </div>
          )}
          {overlay.watermark && (
            <div
              className="preview-watermark"
              style={{
                ...captionCSS(
                  { ...caption, size: (caption.size ?? 54) * 0.55 },
                  scale,
                ),
                opacity: 0.56,
                left: (overlay.logo_position ?? "top-right").endsWith("left")
                  ? "4%"
                  : undefined,
                right: (overlay.logo_position ?? "top-right").endsWith("left")
                  ? undefined
                  : "4%",
                top: (overlay.logo_position ?? "top-right").startsWith("bottom")
                  ? undefined
                  : overlay.logo_asset_id && overlay.logo_enabled !== false
                    ? "18%"
                    : "4%",
                bottom: (overlay.logo_position ?? "top-right").startsWith(
                  "bottom",
                )
                  ? overlay.logo_asset_id && overlay.logo_enabled !== false
                    ? "18%"
                    : "4%"
                  : undefined,
              }}
            >
              {overlay.watermark}
            </div>
          )}
          {debug && data?.debug_allowed && plan && key && (
            <svg
              className="crop-debug"
              viewBox={`0 0 ${plan.crop_width} ${plan.crop_height}`}
            >
              {plan.subjects
                .filter((face) => Math.abs(face.time - relative) < 0.35)
                .map((face, i) => (
                  <g key={i}>
                    <rect
                      x={face.x * plan.source_width - key.x}
                      y={face.y * plan.source_height - key.y}
                      width={face.w * plan.source_width}
                      height={face.h * plan.source_height}
                      fill="none"
                      stroke="lime"
                      strokeWidth={3}
                    />
                    <text
                      x={face.x * plan.source_width - key.x}
                      y={face.y * plan.source_height - key.y}
                      fill="lime"
                      fontSize={18}
                    >
                      {face.subject} · shot {face.scene_start}
                    </text>
                  </g>
                ))}
            </svg>
          )}
        </div>
      </div>
      <div className="preview-transport">
        <button
          className="button secondary"
          type="button"
          onClick={() => {
            if (video.current?.paused) void video.current.play();
            else video.current?.pause();
          }}
        >
          {playing ? (
            <Pause size={17} aria-hidden="true" />
          ) : (
            <Play size={17} aria-hidden="true" />
          )}
          {playing ? "Pause" : "Play"}
        </button>
        <input
          aria-label="Preview timeline"
          type="range"
          min={body.start_ms / 1000}
          max={body.end_ms / 1000}
          step={0.05}
          value={Math.max(
            body.start_ms / 1000,
            Math.min(body.end_ms / 1000, seconds),
          )}
          onChange={(e) => {
            if (video.current)
              video.current.currentTime = Number(e.target.value);
            setSeconds(Number(e.target.value));
          }}
        />
        <span className="studio-preview-time">
          {timecode(relative * 1000)} / {timecode(body.end_ms - body.start_ms)}
        </span>
        <button
          type="button"
          className="studio-icon-button"
          aria-label="Fullscreen preview"
          onClick={() =>
            void canvas.current
              ?.requestFullscreen()
              .catch(() =>
                setError("Fullscreen is unavailable in this browser."),
              )
          }
        >
          <Maximize size={18} aria-hidden="true" />
        </button>
      </div>
      <div className="studio-volume">
        <Volume2 size={16} aria-hidden="true" />
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          aria-label="Preview volume"
          value={volume}
          onChange={(event) => {
            const next = Number(event.target.value);
            setVolume(next);
            if (video.current) video.current.volume = next;
          }}
        />
      </div>
      <p className="muted">
        Drag the video to set a fixed manual crop. Drag captions or the logo to
        reposition.{" "}
        {showingSample
          ? "Sample caption shown where no transcript is available."
          : "Previewing transcript text."}
      </p>
      {!!segments.length && (
        <details>
          <summary>Transcript — click to seek</summary>
          <div style={{ maxHeight: 220, overflow: "auto" }}>
            {segments
              .filter(
                (s) =>
                  s.end > body.start_ms / 1000 && s.start < body.end_ms / 1000,
              )
              .map((s, i) => (
                <button
                  type="button"
                  key={i}
                  className="text-button"
                  style={{ display: "block", textAlign: "left", padding: 8 }}
                  onClick={() => {
                    const time = Math.max(body.start_ms / 1000, s.start);
                    if (video.current) video.current.currentTime = time;
                    setSeconds(time);
                  }}
                >
                  {s.start.toFixed(1)}s · {s.text}
                </button>
              ))}
          </div>
        </details>
      )}
      <label className="field">
        Platform safe zones
        <select value={safe} onChange={(e) => setSafe(e.target.value)}>
          {[
            "Off",
            "YouTube Shorts",
            "TikTok",
            "Instagram Reels",
            "Facebook Reels",
          ].map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
      </label>
      {warning && (
        <p className="notice">
          Captions or logo overlap the platform control area. Move them inward
          before exporting.
        </p>
      )}
      <details className="studio-framing-detail">
        <summary>Framing quality and diagnostics</summary>
        <p className="notice">
          Framing score: {plan?.quality.score ?? "Not scored"}
          {plan?.quality.reason ? ` — ${plan.quality.reason}` : ""}.{" "}
          {plan?.warnings.join(" ")}
        </p>
        {data?.debug_allowed && (
          <label className="check">
            <input
              type="checkbox"
              checked={debug}
              onChange={(e) => setDebug(e.target.checked)}
            />
            Developer framing overlay
          </label>
        )}
      </details>
      <button
        className="button secondary"
        type="button"
        disabled={rendering || !data}
        onClick={renderSample}
      >
        {rendering ? "Rendering sample…" : "Render 4-second preview"}
      </button>
      <p className="muted">
        The short render uses your exact saved settings and counts toward render
        usage. Browser animation and text wrapping are approximate; use this
        sample to check the final appearance.
      </p>
      {rendered && (
        <video
          aria-label="Rendered style preview"
          src={rendered}
          controls
          style={{ maxHeight: 500, width: "100%" }}
        />
      )}
      <div className="form-error" role="alert">
        {error}
      </div>
    </section>
  );
}

export function FramingControls({
  value,
  onChange,
}: {
  value: FramingStyle;
  onChange: (value: FramingStyle) => void;
}) {
  return (
    <div className="studio-framing-controls">
      <h3>Keep the focus</h3>
      <p className="muted">
        Stable framing keeps your subject centered within each shot.
      </p>
      <label className="field">
        Framing subject
        <select
          value={value.subject ?? "primary"}
          onChange={(event) =>
            onChange({
              ...value,
              subject: event.target.value,
              anchor_x: null,
              anchor_y: null,
            })
          }
        >
          <option value="primary">Stable primary person</option>
          <option value="left">Left person</option>
          <option value="right">Right person</option>
          <option value="two-person">Two people when they fit</option>
        </select>
      </label>
      <Toggle
        label="Lock camera within each source shot"
        checked={value.lock_camera ?? true}
        onChange={(lock_camera) =>
          onChange({
            ...value,
            lock_camera,
            crop_mode: lock_camera ? "STATIC_SUBJECT_LOCK" : "SCENE_AWARE_LOCK",
          })
        }
      />
      <Toggle
        label="Set a manual crop anchor"
        checked={value.anchor_x != null}
        onChange={(manual) =>
          onChange({
            ...value,
            anchor_x: manual ? 0.5 : null,
            anchor_y: manual ? 0.5 : null,
          })
        }
      />
      {value.anchor_x != null && (
        <div className="form-grid">
          {(
            [
              ["Horizontal anchor", "anchor_x"],
              ["Vertical anchor", "anchor_y"],
            ] as const
          ).map(([label, key]) => (
            <label className="field studio-range" key={key}>
              <span>
                {label}
                <output>{Math.round((value[key] ?? 0.5) * 100)}%</output>
              </span>
              <input
                aria-label={label}
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={value[key] ?? 0.5}
                onChange={(event) =>
                  onChange({ ...value, [key]: Number(event.target.value) })
                }
              />
            </label>
          ))}
        </div>
      )}
      <label className="field studio-range">
        <span>
          Crop zoom<output>{(value.zoom ?? 1).toFixed(2)}x</output>
        </span>
        <input
          aria-label="Crop zoom"
          type="range"
          min={1}
          max={3}
          step={0.05}
          value={value.zoom ?? 1}
          onChange={(event) =>
            onChange({ ...value, zoom: Number(event.target.value) })
          }
        />
      </label>
      <details>
        <summary>Advanced framing</summary>
        <div className="form-grid">
          {(
            [
              ["Target eye line", "eye_line", 0.25, 0.45, 0.01, 0.34],
              ["Headroom", "headroom", 0.03, 0.15, 0.01, 0.08],
              ["Minimum framing score", "minimum_framing_score", 0, 100, 1, 65],
              [
                "Minimum crop hold (seconds)",
                "minimum_crop_hold_seconds",
                3,
                10,
                0.5,
                4,
              ],
              [
                "Horizontal dead zone",
                "horizontal_dead_zone",
                0.05,
                0.4,
                0.01,
                0.18,
              ],
              [
                "Vertical dead zone",
                "vertical_dead_zone",
                0.05,
                0.4,
                0.01,
                0.15,
              ],
            ] as const
          ).map(([label, key, min, max, step, fallback]) => (
            <label className="field" key={key}>
              {label}
              <input
                type="number"
                min={min}
                max={max}
                step={step}
                value={value[key] ?? fallback}
                onChange={(event) =>
                  onChange({ ...value, [key]: Number(event.target.value) })
                }
              />
            </label>
          ))}
        </div>
      </details>
      <button
        className="button secondary"
        type="button"
        onClick={() => onChange({ ...value, anchor_x: null, anchor_y: null })}
      >
        Reset to automatic framing
      </button>
    </div>
  );
}
