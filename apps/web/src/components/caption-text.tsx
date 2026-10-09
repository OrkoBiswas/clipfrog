"use client";
import { Fragment, useSyncExternalStore } from "react";
import type { CaptionStyle } from "@/lib/editor-types";
import type { CaptionToken } from "@/lib/caption-layout";
import { safeCharacterLimit } from "@/lib/caption-layout";
import { captionWidthCSS } from "@/lib/caption-fonts";
import {
  effectProgress,
  mixCaptionColor,
  revealProgress,
  isRevealAnimation,
  normalizeCaptionAnimation,
  captionMotion,
  isWordAnimation,
  wordMotion,
} from "@/lib/caption-effects";

function subscribeMotion(callback: () => void) {
  const query = matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

// Both the sample player and real-video composition share these animation effects.
export function CaptionText(props: CaptionTextProps) {
  return (
    <span data-caption-width={props.value.font_width ?? 100} style={captionWidthCSS(props.value)}>
      <CaptionTextContent {...props} />
    </span>
  );
}

type CaptionTextProps = {
  lines: CaptionToken[][];
  value: CaptionStyle;
  activeWord: number;
  elapsed?: number;
  groupDuration?: number;
  reducedMotion?: boolean;
  words?: { start: number; end: number }[];
  seconds?: number;
};

function CaptionTextContent({
  lines,
  value,
  activeWord,
  elapsed = 1,
  groupDuration = 1,
  reducedMotion = false,
  words = [],
  seconds = 0,
}: CaptionTextProps) {
  const prefersReduced = useSyncExternalStore(
    subscribeMotion,
    () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => true,
  );
  const animation = normalizeCaptionAnimation(value.animation);
  const revealAnimation = isRevealAnimation(animation);
  const progress =
    reducedMotion || prefersReduced
      ? 1
      : effectProgress(elapsed, value.animation_duration ?? 0.6, groupDuration);
  const effect = value.effect_color ?? "#0054FF";
  const primary = value.primary_color ?? "#FFFFFF";
  const highlight =
    !revealAnimation &&
    (value.highlight || animation === "karaoke" || animation === "spotlight");
  const motion = captionMotion(animation, progress);
  if (isWordAnimation(animation)) {
    const fit =
      value.word_display === "single"
        ? Math.min(
            1,
            safeCharacterLimit(value) /
              Math.max(
                1,
                ...lines.flat().map((token) => Array.from(token.text).length),
              ),
          )
        : 1;
    return (
      <span
        data-caption-effect={animation}
        style={{ display: "block", fontSize: `${fit}em` }}
      >
        {lines.map((line, index) => (
          <span key={index} style={{ display: "block" }}>
            {line.map((token, i) => {
              const timing = words[token.wordIndex];
              const spoken = !!timing && seconds >= timing.start;
              const active = spoken && token.wordIndex === activeWord;
              const duration = Math.max(
                0.02,
                (words[token.wordIndex + 1]?.start ?? timing?.end ?? 1) -
                  (timing?.start ?? 0),
              );
              const m = wordMotion(
                animation,
                seconds - (timing?.start ?? 0),
                value.animation_duration ?? 0.25,
                duration,
                active ? (value.active_scale ?? 1.06) : 1,
                reducedMotion || prefersReduced,
              );
              const moving =
                spoken && (active || value.word_display === "build");
              const hidden = value.word_display === "build" && !spoken;
              const card =
                active &&
                (animation === "word-pill" || animation === "word-box");
              const ink = value.effect_color ?? "#7856FF";
              return (
                <Fragment key={i}>
                  {token.separator}
                  <span
                    data-word-index={token.wordIndex}
                    data-active={active}
                    style={{
                      display: "inline-block",
                      position: "relative",
                      isolation: "isolate",
                      zIndex: active ? 1 : 0,
                      color:
                        active && value.highlight !== false
                          ? (value.highlight_color ?? "#FFD700")
                          : primary,
                      opacity: hidden
                        ? 0
                        : (moving ? m.opacity : 1) *
                          (active ? 1 : (value.inactive_opacity ?? 1)),
                      transform: moving
                        ? `translate(${m.x}em, ${m.y}em) scale(${m.sx}, ${m.sy}) rotate(${m.rotate}deg)`
                        : undefined,
                      filter:
                        moving && m.blur ? `blur(${m.blur}em)` : undefined,
                      textShadow:
                        active && animation === "word-glow"
                          ? `0 0 .12em ${ink}, 0 0 .3em ${ink}`
                          : undefined,
                    }}
                  >
                    {card && (
                      <span
                        style={{
                          position: "absolute",
                          zIndex: -1,
                          inset: ".06em -.1em",
                          background: ink,
                          borderRadius:
                            animation === "word-pill" ? ".22em" : ".02em",
                        }}
                      />
                    )}
                    {active && animation === "word-underline" && (
                      <span
                        style={{
                          position: "absolute",
                          left: 0,
                          bottom: ".02em",
                          height: ".08em",
                          width: `${m.progress * 100}%`,
                          background: ink,
                          borderRadius: ".04em",
                        }}
                      />
                    )}
                    {value.uppercase ? token.text.toUpperCase() : token.text}
                  </span>
                </Fragment>
              );
            })}
          </span>
        ))}
      </span>
    );
  }
  const charCount = lines
    .flat()
    .reduce(
      (sum, token) =>
        sum +
        Array.from(
          token.separator +
            (value.uppercase ? token.text.toUpperCase() : token.text),
        ).length,
      0,
    );
  let charIndex = 0;
  const text = lines.map((line, index) => (
    <span key={index} style={{ display: "block" }}>
      {line.map((token, i) => {
        const target =
          highlight &&
          (animation === "karaoke"
            ? token.wordIndex <= activeWord
            : token.wordIndex === activeWord)
            ? (value.highlight_color ?? "#FFD700")
            : primary;
        const content =
          token.separator +
          (value.uppercase ? token.text.toUpperCase() : token.text);
        return (
          <span
            key={i}
            data-active={token.wordIndex === activeWord}
            style={{
              color: target,
              opacity:
                animation === "spotlight" && token.wordIndex !== activeWord
                  ? 0.4
                  : animation === "word-reveal" &&
                      progress <
                        (token.wordIndex - (lines[0]?.[0]?.wordIndex ?? 0)) /
                          Math.max(1, lines.flat().length)
                    ? 0
                    : 1,
            }}
          >
            {revealAnimation && animation !== "word-reveal"
              ? Array.from(content).map((character) => {
                  const key = charIndex++;
                  const p = revealProgress(progress, key, charCount);
                  return (
                    <span
                      key={key}
                      style={{
                        opacity: p > 0 ? 1 : 0,
                        color:
                          animation === "color-reveal"
                            ? mixCaptionColor(effect, target, p)
                            : target,
                      }}
                    >
                      {character}
                    </span>
                  );
                })
              : content}
          </span>
        );
      })}
    </span>
  ));
  return (
    <span
      data-caption-effect={animation}
      style={{
        display: "block",
        position: "relative",
        opacity: motion.opacity,
        transform: `translate(${motion.x}em, ${motion.y}em) scale(${motion.sx}, ${motion.sy}) rotate(${motion.rotate}deg)`,
        filter: motion.blur ? `blur(${motion.blur}em)` : undefined,
        clipPath: motion.clip,
      }}
    >
      <span style={{ position: "relative" }}>{text}</span>
    </span>
  );
}
