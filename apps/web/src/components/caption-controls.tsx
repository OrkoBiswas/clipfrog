"use client";
import { useState } from "react";
import { BookmarkPlus, RotateCcw } from "lucide-react";
import type { CaptionStyle, FramingStyle } from "@/lib/editor-types";
import {
  ANIMATION_LABELS,
  CAPTION_ANIMATIONS,
  isWordAnimation,
} from "@/lib/caption-effects";
import {
  DEFAULT_CAPTION,
  applyCaptionTemplate,
} from "@/lib/caption-templates";
import {
  CAPTION_FONT_CATALOG,
  FONT_WEIGHT_LABELS,
  captionFont,
  captionWidthCSS,
  normalizeCaptionTypography,
} from "@/lib/caption-fonts";
import { useCaptionLibrary } from "./caption-library";
import { SplitScreenControls } from "./split-screen-controls";
import "./caption-templates.css";

export function CaptionControls({
  value,
  onChange,
  framing,
  onFramingChange,
}: {
  value: CaptionStyle;
  onChange: (value: CaptionStyle) => void;
  framing?: FramingStyle;
  onFramingChange?: (value: FramingStyle) => void;
}) {
  const config = normalizeCaptionTypography({ ...DEFAULT_CAPTION, ...value });
  const font = captionFont(config.font);
  const { templates, save, ready } = useCaptionLibrary();
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  function update<K extends keyof CaptionStyle>(key: K, next: CaptionStyle[K]) {
    onChange(normalizeCaptionTypography({ ...config, [key]: next }));
  }
  function range(
    key: keyof CaptionStyle,
    label: string,
    min: number,
    max: number,
    step = 1,
    percent = false,
    suffix = "",
  ) {
    const number = Number(config[key] ?? min);
    return (
      <label className="ct-range" key={key}>
        <span>
          {label}
          <output>{percent ? `${Math.round(number * 100)}%` : `${number}${suffix}`}</output>
        </span>
        <input
          aria-label={label}
          type="range"
          min={min}
          max={max}
          step={step}
          value={number}
          onChange={(e) => update(key, Number(e.target.value))}
        />
      </label>
    );
  }
  function color(key: keyof CaptionStyle, label: string) {
    return (
      <label className="ct-color" key={key}>
        <span>{label}</span>
        <input
          aria-label={label}
          type="color"
          value={String(config[key])}
          onChange={(e) => update(key, e.target.value)}
        />
      </label>
    );
  }
  function check(key: keyof CaptionStyle, label: string, disabled = false) {
    return (
      <label className="check" key={key}>
        <input
          type="checkbox"
          disabled={disabled}
          checked={Boolean(config[key])}
          onChange={(e) => update(key, e.target.checked)}
        />
        {label}
      </label>
    );
  }
  return (
    <div className="ct-controls">
      <label className="field">
        Caption template
        <select
          aria-label="Caption template"
          value={templates.find((t) => t.name === value.style)?.id ?? ""}
          onChange={(e) => {
            const template = templates.find((t) => t.id === e.target.value);
            if (template)
              onChange(applyCaptionTemplate(value, template.config));
          }}
        >
          <option value="">Custom / Basic Word Pop</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </label>
      {check("enabled", "Subtitles enabled")}
      <details open>
        <summary>
          Typography <span>Aa</span>
        </summary>
        <div className="ct-fields">
          <label className="field">
            Font family
            <select
              aria-label="Font family"
              value={config.font}
              onChange={(e) => update("font", e.target.value)}
            >
              {CAPTION_FONT_CATALOG.map((font) => (
                <option key={font.family} value={font.family}>
                  {font.family} · {font.category}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Font weight
            <select
              aria-label="Font weight"
              value={config.weight}
              onChange={(e) => update("weight", Number(e.target.value))}
            >
              {font.weights.map((weight) => (
                <option key={weight} value={weight}>
                  {FONT_WEIGHT_LABELS[weight]} · {weight}
                </option>
              ))}
            </select>
          </label>
          {range("size", "Font size", 20, 120)}
          {range("font_width", "Font width", 75, 150, 1, false, "%")}
          <div className="ct-font-widths" role="group" aria-label="Font width presets">
            {[
              [75, "Condensed"],
              [100, "Normal"],
              [125, "Wide"],
              [150, "Extra wide"],
            ].map(([width, label]) => (
              <button
                key={width}
                type="button"
                aria-pressed={config.font_width === width}
                onClick={() => update("font_width", Number(width))}
              >
                {label}
              </button>
            ))}
          </div>
          {range("spacing", "Letter spacing", 0, 12, 0.5)}
          <div className="ct-checks">
            {check("uppercase", "Uppercase")}
            {check("italic", "Italic", !font.italic)}
          </div>
          <div className="ct-font-sample" aria-hidden="true">
            <span style={{
              ...captionWidthCSS(config),
              fontFamily: `'${font.family}', sans-serif`,
              fontWeight: config.weight,
              fontStyle: config.italic ? "italic" : "normal",
              fontSynthesis: "none",
            }}>
              Make it yours
            </span>
          </div>
          <p className="ct-hint">
            {font.weights.length} weights{font.italic ? " with matching italics" : " · upright only"}.
            {" "}Width stretches or condenses the letters; caption box width is in Layout.
          </p>
        </div>
      </details>
      <details open>
        <summary>
          Motion <span>↗</span>
        </summary>
        <div className="ct-fields">
          <label className="field">
            Animation
            <select
              aria-label="Animation"
              value={config.animation}
              onChange={(e) =>
                update("animation", e.target.value as CaptionStyle["animation"])
              }
            >
              {CAPTION_ANIMATIONS.map((animation) => (
                <option key={animation} value={animation}>
                  {ANIMATION_LABELS[animation]}
                </option>
              ))}
            </select>
          </label>
          {range(
            "animation_duration",
            "Motion duration (seconds)",
            0.1,
            2,
            0.1,
          )}
          {isWordAnimation(config.animation ?? "word-pop") && (
            <>
              <label className="field">
                Word display
                <select
                  aria-label="Word display"
                  value={config.word_display}
                  onChange={(e) =>
                    update(
                      "word_display",
                      e.target.value as CaptionStyle["word_display"],
                    )
                  }
                >
                  <option value="full">
                    Full phrase · animate the spoken word
                  </option>
                  <option value="build">
                    Build up · reveal words as spoken
                  </option>
                  <option value="single">One word at a time · centered</option>
                </select>
              </label>
              {range("active_scale", "Spoken word size", 1, 1.4, 0.01, true)}
              {range(
                "inactive_opacity",
                "Other words opacity",
                0.1,
                1,
                0.05,
                true,
              )}
              {color("effect_color", "Highlight / glow / underline")}
            </>
          )}
          <p className="ct-hint">
            Word-by-word styles follow transcript timestamps. Motion adapts to
            fast speech; edited cues use evenly spaced word timing.
          </p>
        </div>
      </details>
      <details>
        <summary>
          Color & emphasis <span>◐</span>
        </summary>
        <div className="ct-fields">
          {color("primary_color", "Text color")}
          {color("highlight_color", "Spoken word color")}
          {color("effect_color", "Ink reveal color")}
          {check("highlight", "Highlight the spoken word")}
          {range("outline", "Outline thickness", 0, 8)}
          {color("stroke_color", "Outline color")}
          {range("shadow", "Shadow distance", 0, 5)}
          {color("shadow_color", "Shadow color")}
          {range("shadow_opacity", "Shadow opacity", 0, 1, 0.05, true)}
        </div>
      </details>
      <details>
        <summary>
          Background <span>▣</span>
        </summary>
        <div className="ct-fields">
          {check("background", "Caption background")}
          {color("background_color", "Background color")}
          {range("background_opacity", "Background opacity", 0, 1, 0.05, true)}
        </div>
      </details>
      <details>
        <summary>
          Layout & safe area <span>⊞</span>
        </summary>
        <div className="ct-fields">
          {framing && onFramingChange && (
            <SplitScreenControls value={framing} onChange={onFramingChange} />
          )}
          <label className="field">
            Alignment
            <select
              aria-label="Alignment"
              value={config.alignment}
              onChange={(e) => update("alignment", e.target.value)}
            >
              <option value="left">Left</option>
              <option value="center">Center</option>
              <option value="right">Right</option>
            </select>
          </label>
          {range("x", "Horizontal position", 0.05, 0.95, 0.01, true)}
          {range("y", "Vertical position", 0.05, 0.95, 0.01, true)}
          {range("width", "Caption width", 0.2, 0.94, 0.01, true)}
          {range("safe_bottom", "Bottom safe area", 0.02, 0.35, 0.01, true)}
          {range("max_words", "Words per line", 1, 12)}
          {range("max_chars_per_line", "Characters per line", 1, 80)}
          {range("lines", "Lines per caption", 1, 2)}
          {check("punctuation", "Keep punctuation")}
          {check("remove_special_characters", "Remove symbols & emoji")}
        </div>
      </details>
      <details>
        <summary>
          Save your own preset <BookmarkPlus size={15} />
        </summary>
        <div className="ct-fields">
          <label className="field">
            Preset name
            <input
              maxLength={80}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My signature captions"
            />
          </label>
          <button
            type="button"
            className="button secondary"
            disabled={!ready || !name.trim()}
            onClick={() => {
              setError("");
              setMessage("");
              try {
                save(name, config);
                setMessage(`“${name.trim()}” saved to My presets.`);
                setName("");
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Could not save preset.",
                );
              }
            }}
          >
            Save preset
          </button>
          <p className="ct-hint">
            Personal presets are saved for your account in this browser. Styles
            applied to clips are saved with the clip.
          </p>
          {message && (
            <p role="status" className="notice">
              {message}
            </p>
          )}
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
        </div>
      </details>
      <button
        type="button"
        className="text-button"
        onClick={() =>
          onChange(
            applyCaptionTemplate(
              value,
              templates.find((t) => t.name === value.style)?.config ??
                DEFAULT_CAPTION,
            ),
          )
        }
      >
        <RotateCcw size={14} /> Reset style settings
      </button>
    </div>
  );
}
