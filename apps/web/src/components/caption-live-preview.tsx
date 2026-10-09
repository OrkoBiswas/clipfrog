"use client";

import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type CSSProperties,
} from "react";
import { gsap } from "gsap";
import {
  Check,
  Film,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  Repeat2,
  RotateCcw,
  Scan,
} from "lucide-react";
import type { CaptionStyle } from "@/lib/editor-types";
import { normalizeCaptionAnimation } from "@/lib/caption-effects";
import { captionCSS } from "@/lib/caption-style";
import { captionFrame, sampleWords } from "@/lib/caption-preview";
import "./caption-live-preview.css";
import { CaptionText } from "./caption-text";

const motionQuery = "(prefers-reduced-motion: reduce)";
const previewFormats = {
  "9:16": { width: 1080, height: 1920, name: "Portrait" },
  "1:1": { width: 1080, height: 1080, name: "Square" },
  "16:9": { width: 1920, height: 1080, name: "Landscape" },
} as const;
function subscribeMotion(callback: () => void) {
  const media = matchMedia(motionQuery);
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}
function timestamp(seconds: number) {
  return `${Math.floor(seconds / 60)}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
}

export function CaptionLivePreview({
  value,
  name,
}: {
  value: CaptionStyle;
  name: string;
}) {
  const [text, setText] = useState(
    "Every great story starts with a moment. Make yours impossible to skip.",
  );
  const [seconds, setSeconds] = useState(0.22);
  const [playIntent, setPlayIntent] = useState(true);
  const [manualPlay, setManualPlay] = useState(false);
  const [loop, setLoop] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [ratio, setRatio] = useState<keyof typeof previewFormats>("9:16");
  const [backdrop, setBackdrop] = useState("studio");
  const [guides, setGuides] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [width, setWidth] = useState(240);
  const [visible, setVisible] = useState(false);
  const [foreground, setForeground] = useState(true);
  const root = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const animated = useRef<HTMLDivElement>(null);
  const clock = useRef<gsap.core.Tween | null>(null);
  const reduce = useSyncExternalStore(
    subscribeMotion,
    () => matchMedia(motionQuery).matches,
    () => true,
  );
  const words = useMemo(() => sampleWords(text), [text]);
  const duration = Math.max(1, words.at(-1)?.end ?? 0);
  const frame = captionFrame(words, seconds, value);
  const format = previewFormats[ratio];
  const aspect = format.width / format.height;
  const scale = width / format.width;
  const playing = playIntent && (!reduce || manualPlay) && words.length > 0;
  const animation = normalizeCaptionAnimation(value.animation);
  const y = Math.min(
    1 - (value.safe_bottom ?? 0.17),
    Math.max(
      0.08,
      value.y ??
        { top: 0.18, middle: 0.5, bottom: 0.78 }[value.position ?? "bottom"] ??
        0.78,
    ),
  );

  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const intersection = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.05 },
    );
    intersection.observe(element);
    const visibility = () => setForeground(!document.hidden);
    visibility();
    document.addEventListener("visibilitychange", visibility);
    return () => {
      intersection.disconnect();
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);

  useLayoutEffect(() => {
    const canvas = stage.current;
    if (!canvas) return;
    setWidth(canvas.getBoundingClientRect().width);
    const resize = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    );
    resize.observe(canvas);
    return () => resize.disconnect();
  }, [ratio, expanded]);

  useEffect(() => {
    const cursor = { seconds: 0 };
    const tween = gsap.to(cursor, {
      seconds: duration,
      duration,
      ease: "none",
      paused: true,
      onUpdate: () => setSeconds(Math.round(cursor.seconds * 30) / 30),
      onComplete: () => setPlayIntent(false),
    });
    clock.current = tween;
    tween.time(Math.min(0.22, duration));
    return () => {
      tween.kill();
      clock.current = null;
    };
  }, [duration, words]);

  useEffect(() => {
    clock.current
      ?.repeat(loop ? -1 : 0)
      .repeatDelay(loop ? 0.35 : 0)
      .timeScale(speed);
    clock.current?.paused(!playing || !visible || !foreground);
  }, [loop, speed, playing, visible, foreground, duration, words]);

  function seek(next: number) {
    const time = Math.max(0, Math.min(duration, next));
    clock.current?.totalTime(time, true);
    setSeconds(time);
  }
  function togglePlay() {
    if (!playing && seconds >= duration - 0.05) seek(0);
    setManualPlay(true);
    setPlayIntent(!playing);
  }

  return (
    <section
      ref={root}
      className={`caption-player ${expanded ? "is-expanded" : ""}`}
      aria-label="Live caption preview"
    >
      <header className="caption-player-header">
        <div>
          <span className="caption-player-eyebrow">
            <span /> LIVE PREVIEW
          </span>
          <h4>{name}</h4>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label={expanded ? "Reduce preview" : "Enlarge preview"}
          aria-expanded={expanded}
          title={expanded ? "Reduce preview" : "Enlarge preview"}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
        </button>
      </header>
      <div className="caption-player-toolbar">
        <div
          className="caption-ratios"
          role="group"
          aria-label="Preview aspect ratio"
        >
          {(Object.keys(previewFormats) as (keyof typeof previewFormats)[]).map((item) => (
            <button
              type="button"
              key={item}
              aria-pressed={ratio === item}
              onClick={() => setRatio(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label="Show safe-area guides"
          aria-pressed={guides}
          onClick={() => setGuides(!guides)}
        >
          <Scan size={18} />
        </button>
      </div>
      <div className="caption-canvas-info">
        <span>{format.name} <span aria-hidden="true">·</span> {ratio}</span>
        <span aria-label="Preview canvas dimensions">{format.width} × {format.height}</span>
      </div>
      <div className="caption-player-canvas">
        <div
          ref={stage}
          className={`caption-player-stage backdrop-${backdrop}`}
          style={
            {
              aspectRatio: aspect,
              "--preview-aspect": aspect,
            } as CSSProperties
          }
          role="img"
          aria-label={`Caption sample in ${ratio}. ${value.enabled === false ? "Captions are off." : frame.lines.map((line) => line.map((token) => token.separator + token.text).join("")).join(" ")}`}
        >
          <div className="caption-scene-art" aria-hidden="true">
            <div />
            <div />
            <div />
          </div>
          {guides && (
            <div
              className="caption-player-safe"
              aria-hidden="true"
              style={{ bottom: `${(value.safe_bottom ?? 0.17) * 100}%` }}
            >
              <span>Safe area</span>
            </div>
          )}
          <div
            className="caption-player-artboard"
            style={{
              width: format.width,
              height: format.height,
              transform: `scale(${scale})`,
            }}
          >
            <div
              className="caption-player-anchor"
              style={{
                left: `${(value.x ?? 0.5) * 100}%`,
                top: `${y * 100}%`,
                width: `${(value.width ?? 0.84) * 100}%`,
                transform: `translate(${value.alignment === "left" ? 0 : value.alignment === "right" ? -100 : -50}%, -50%)`,
              }}
            >
              <div
                ref={animated}
                className="caption-player-caption"
                data-animation={animation}
                data-active-word={frame.activeWord}
                style={{
                  ...captionCSS(value, format.width / 1080),
                  visibility: value.enabled === false ? "hidden" : "visible",
                }}
                aria-hidden="true"
              >
                <CaptionText
                  lines={frame.lines}
                  value={value}
                  activeWord={frame.activeWord}
                  words={words}
                  seconds={seconds}
                  elapsed={seconds - frame.start}
                  groupDuration={frame.end - frame.start}
                  reducedMotion={reduce}
                />
              </div>
            </div>
          </div>
          {(!words.length || value.enabled === false) && (
            <div className="caption-player-empty">
              {value.enabled === false
                ? "Captions are turned off"
                : "Your words go here"}
            </div>
          )}
        </div>
      </div>
      <div className="caption-canvas-meta">
        <span>
          <Film size={13} aria-hidden="true" /> Sample canvas
        </span>
        <span aria-label="Preview zoom">Fit · {Math.round(scale * 100)}%</span>
      </div>
      <div
        className="caption-player-backgrounds"
        role="group"
        aria-label="Preview background"
      >
        <span>Backdrop</span>
        {["studio", "light", "contrast"].map((item) => (
          <button
            type="button"
            key={item}
            aria-label={`${item} backdrop`}
            aria-pressed={backdrop === item}
            className={`backdrop-swatch backdrop-${item}`}
            onClick={() => setBackdrop(item)}
          >
            {backdrop === item && <Check size={13} />}
          </button>
        ))}
        <span className="caption-player-ratio">{ratio} canvas</span>
      </div>
      <div className="caption-player-transport">
        <div className="caption-player-scrub">
          <input
            type="range"
            min={0}
            max={duration}
            step={0.01}
            value={Math.min(seconds, duration)}
            aria-label="Caption preview playhead"
            aria-valuetext={`${timestamp(seconds)} of ${timestamp(duration)}`}
            onChange={(event) => {
              setPlayIntent(false);
              seek(Number(event.target.value));
            }}
          />
          <div>
            <span>{timestamp(seconds)}</span>
            <span>{timestamp(duration)}</span>
          </div>
        </div>
        <div className="caption-player-buttons">
          <button
            type="button"
            className="icon-button"
            aria-label="Replay caption preview"
            onClick={() => {
              seek(0);
              setManualPlay(true);
              setPlayIntent(true);
            }}
          >
            <RotateCcw size={17} />
          </button>
          <button
            type="button"
            className="caption-play-button"
            aria-label={
              playing ? "Pause caption preview" : "Play caption preview"
            }
            disabled={!words.length}
            onClick={togglePlay}
          >
            {playing ? (
              <Pause size={18} fill="currentColor" />
            ) : (
              <Play size={18} fill="currentColor" />
            )}
          </button>
          <button
            type="button"
            className="icon-button"
            aria-label="Loop caption preview"
            aria-pressed={loop}
            onClick={() => setLoop(!loop)}
          >
            <Repeat2 size={18} />
          </button>
          <label className="caption-speed">
            <span className="sr-only">Preview playback speed</span>
            <select
              value={speed}
              onChange={(event) => setSpeed(Number(event.target.value))}
            >
              {[0.5, 1, 1.5, 2].map((item) => (
                <option key={item} value={item}>
                  {item}×
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <details className="caption-sample-editor">
        <summary>
          Edit sample text <span>{words.length} words</span>
        </summary>
        <label className="field">
          Live preview text
          <textarea
            value={text}
            maxLength={240}
            rows={3}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <div
          className="caption-word-track"
          role="group"
          aria-label="Seek to sample word"
        >
          {words.map((word, index) => (
            <button
              type="button"
              key={index}
              aria-label={`Seek to word ${index + 1}: ${word.text}`}
              aria-current={frame.activeWord === index ? "true" : undefined}
              onClick={() => {
                setPlayIntent(false);
                seek(word.start + 0.01);
              }}
            >
              {word.text}
            </button>
          ))}
        </div>
      </details>
      <footer className="caption-player-note">
        {reduce
          ? "Reduced motion · press play to follow the words."
          : "Sample timing · style changes appear instantly."}
        <span>Use your clip’s rendered preview to check final output.</span>
      </footer>
    </section>
  );
}
