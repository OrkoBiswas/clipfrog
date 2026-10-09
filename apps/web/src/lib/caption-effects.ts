export const CAPTION_ANIMATIONS = [
  "none",
  "word-pop",
  "fade",
  "rise",
  "fall",
  "slide-left",
  "slide-right",
  "zoom-in",
  "zoom-out",
  "bounce",
  "blur-in",
  "tilt",
  "unfold",
  "stretch",
  "wipe",
  "lift-mask",
  "typewriter",
  "color-reveal",
  "word-reveal",
  "karaoke",
  "spotlight",
  "stamp",
  "word-spring",
  "word-rise",
  "word-punch",
  "word-slide",
  "word-tilt",
  "word-focus",
  "word-flip",
  "word-stretch",
  "word-pill",
  "word-box",
  "word-underline",
  "word-glow",
] as const;

export type CaptionAnimation = (typeof CAPTION_ANIMATIONS)[number];

export const REVEAL_ANIMATIONS: readonly CaptionAnimation[] = [
  "typewriter",
  "color-reveal",
  "word-reveal",
];

export const ANIMATION_LABELS: Record<CaptionAnimation, string> = {
  none: "Still",
  "word-pop": "Word pop",
  fade: "Soft fade",
  rise: "Smooth rise",
  fall: "Soft drop",
  "slide-left": "Slide from left",
  "slide-right": "Slide from right",
  "zoom-in": "Gentle zoom in",
  "zoom-out": "Gentle zoom out",
  bounce: "Soft bounce",
  "blur-in": "Focus pull",
  tilt: "Tilt & settle",
  unfold: "Unfold",
  stretch: "Elastic width",
  wipe: "Horizontal reveal",
  "lift-mask": "Vertical reveal",
  typewriter: "Typewriter",
  "color-reveal": "Ink reveal",
  "word-reveal": "Word cascade",
  karaoke: "Karaoke fill",
  spotlight: "Word spotlight",
  stamp: "Impact stamp",
  "word-spring": "Word by word · Spring",
  "word-rise": "Word by word · Rise",
  "word-punch": "Word by word · Punch",
  "word-slide": "Word by word · Slide",
  "word-tilt": "Word by word · Tilt",
  "word-focus": "Word by word · Focus",
  "word-flip": "Word by word · Flip",
  "word-stretch": "Word by word · Elastic",
  "word-pill": "Word by word · Highlight pill",
  "word-box": "Word by word · Highlight block",
  "word-underline": "Word by word · Underline",
  "word-glow": "Word by word · Glow",
};

export const WORD_MOTIONS = {
  "word-spring": "bounce",
  "word-rise": "rise",
  "word-punch": "stamp",
  "word-slide": "slide-left",
  "word-tilt": "tilt",
  "word-focus": "blur-in",
  "word-flip": "unfold",
  "word-stretch": "stretch",
  "word-pill": "bounce",
  "word-box": "word-pop",
  "word-underline": "none",
  "word-glow": "word-pop",
} as const;

export function isWordAnimation(
  animation: CaptionAnimation,
): animation is keyof typeof WORD_MOTIONS {
  return animation in WORD_MOTIONS;
}

/** Word-local time, not phrase-local time. Safe to scrub backwards or seek. */
export function wordMotion(
  animation: CaptionAnimation,
  elapsed: number,
  duration: number,
  wordDuration: number,
  activeScale = 1,
  reduced = false,
) {
  const progress = reduced
    ? 1
    : effectProgress(elapsed, duration, wordDuration);
  const motion = captionMotion(
    isWordAnimation(animation) ? WORD_MOTIONS[animation] : "none",
    progress,
  );
  return {
    ...motion,
    sx: motion.sx * activeScale,
    sy: motion.sy * activeScale,
    progress,
  };
}

/** Seekable motion: the same normalized curves are implemented in native ASS. */
export function captionMotion(animation: CaptionAnimation, progress: number) {
  const p = Math.min(1, Math.max(0, progress));
  const remaining = 1 - Math.pow(p, 0.6);
  let x = 0,
    y = 0,
    sx = 1,
    sy = 1,
    rotate = 0,
    blur = 0,
    opacity = 1;
  switch (animation) {
    case "fade":
      opacity = p;
      break;
    case "rise":
      y = 0.65 * (1 - p);
      opacity = p;
      break;
    case "fall":
      y = -0.55 * (1 - p);
      opacity = p;
      break;
    case "slide-left":
      x = -1.2 * (1 - p);
      opacity = p;
      break;
    case "slide-right":
      x = 1.2 * (1 - p);
      opacity = p;
      break;
    case "word-pop":
      sx = sy = 1 - 0.08 * remaining;
      break;
    case "zoom-in":
      sx = sy = 1 - 0.3 * remaining;
      opacity = p;
      break;
    case "zoom-out":
      sx = sy = 1 + 0.3 * remaining;
      opacity = p;
      break;
    case "bounce":
      sx = sy =
        p < 0.65
          ? 0.8 + 0.26 * Math.pow(p / 0.65, 0.6)
          : 1.06 - 0.06 * Math.pow((p - 0.65) / 0.35, 0.6);
      break;
    case "blur-in":
      blur = 0.14 * remaining;
      opacity = p;
      break;
    case "tilt":
      rotate = -9 * remaining;
      sx = sy = 1 - 0.1 * remaining;
      opacity = p;
      break;
    case "unfold":
      sy = 1 - 0.95 * remaining;
      opacity = p;
      break;
    case "stretch":
      sx = 1 + 0.5 * remaining;
      opacity = p;
      break;
    case "stamp":
      sx = sy = 1 + 0.65 * remaining;
      rotate = 5 * remaining;
      opacity = p;
      break;
  }
  return {
    x: x || 0,
    y: y || 0,
    sx,
    sy,
    rotate: rotate || 0,
    blur: blur || 0,
    opacity,
    clip:
      animation === "wipe"
        ? `inset(0 ${(1 - p) * 100}% 0 0)`
        : animation === "lift-mask"
          ? `inset(${(1 - p) * 100}% 0 0 0)`
          : undefined,
  };
}

export function normalizeCaptionAnimation(
  animation: string | null | undefined,
): CaptionAnimation {
  return CAPTION_ANIMATIONS.includes(animation as CaptionAnimation)
    ? (animation as CaptionAnimation)
    : "word-pop";
}

export function isRevealAnimation(animation: CaptionAnimation): boolean {
  return REVEAL_ANIMATIONS.includes(animation);
}
export function effectProgress(
  elapsed: number,
  duration: number,
  groupDuration: number,
) {
  const actualDuration = Math.max(
    0.01,
    Math.min(duration, groupDuration * 0.8),
  );
  return Math.min(1, Math.max(0, elapsed / actualDuration));
}
export function revealProgress(progress: number, index: number, count: number) {
  return Math.min(
    1,
    Math.max(0, (progress - (index / Math.max(1, count)) * 0.75) / 0.25),
  );
}
export function mixCaptionColor(from: string, to: string, progress: number) {
  const mix = (offset: number) =>
    Math.round(
      parseInt(from.slice(offset, offset + 2), 16) * (1 - progress) +
        parseInt(to.slice(offset, offset + 2), 16) * progress,
    )
      .toString(16)
      .padStart(2, "0");
  return `#${mix(1)}${mix(3)}${mix(5)}`;
}
