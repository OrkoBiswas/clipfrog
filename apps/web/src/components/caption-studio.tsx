"use client";
import { useEffect, useState, type CSSProperties } from "react";
import { api } from "@/lib/api";
import type { CaptionStyle, Library, Template } from "@/lib/editor-types";
import { CAPTION_FONTS } from "@/lib/editor-types";
import { layoutCaptionWords, safeCharacterLimit } from "@/lib/caption-layout";
import { Check, Search, Star, Type } from "lucide-react";
import { ConfirmDialog, Skeleton } from "./ui/primitives";
import { ColorField } from "./studio-controls";
import "./studio.css";

import { positions } from "@/lib/positions";
export { positions } from "@/lib/positions";
export function captionCSS(config: CaptionStyle, scale = 1): CSSProperties {
  return {
    fontFamily: `'${config.font ?? "DejaVu Sans"}', sans-serif`,
    fontWeight: config.weight ?? 700,
    fontSize: (config.size ?? 54) * scale,
    color: config.primary_color ?? "#ffffff",
    WebkitTextStroke: `${(config.outline ?? 3) * scale}px ${config.stroke_color ?? "#141414"}`,
    paintOrder: "stroke fill",
    letterSpacing: (config.spacing ?? 0) * scale,
    textTransform: config.uppercase ? "uppercase" : "none",
    textAlign: (config.alignment ?? "center") as CSSProperties["textAlign"],
    textShadow: `${(config.shadow ?? 1) * scale}px ${(config.shadow ?? 1) * scale}px ${2 * scale}px #0009`,
    backgroundColor: config.background
      ? `${config.background_color ?? "#000000"}${Math.round(
          (config.background_opacity ?? 0.65) * 255,
        )
          .toString(16)
          .padStart(2, "0")}`
      : "transparent",
    lineHeight: 1.2,
    padding: config.background ? `${4 * scale}px ${8 * scale}px` : 0,
  };
}

export function CaptionStudio({
  value,
  onChange,
  compact = false,
}: {
  value: CaptionStyle;
  onChange: (value: CaptionStyle) => void;
  compact?: boolean;
}) {
  const [library, setLibrary] = useState<Library>({
    items: [],
    favorites: [],
    recent: [],
    default: null,
  });
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [tab, setTab] = useState("Templates");
  const [sample, setSample] = useState("THIS changes everything");
  const [name, setName] = useState("My caption style");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api<Library>("/caption-templates")
      .then((data) => {
        if (active) {
          setLibrary(data);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);
  const selected = library.items.find((item) => item.id === value.template_id);
  const custom = selected?.category === "My Templates";
  async function refresh() {
    setLibrary(await api<Library>("/caption-templates"));
  }
  async function preference(id: string, action: string) {
    try {
      await api(`/caption-templates/${id}/preference`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save preference");
    }
  }
  function apply(item: Template) {
    onChange({ ...item.config, template_id: item.id, cues: value.cues });
    setName(item.name);
    void preference(item.id, "recent");
  }
  async function save(action: "create" | "update" | "delete") {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api<Template>(
        `/caption-templates${action === "create" ? "" : `/${selected?.id}`}`,
        {
          method:
            action === "create"
              ? "POST"
              : action === "update"
                ? "PUT"
                : "DELETE",
          ...(action !== "delete"
            ? { body: JSON.stringify({ name, config: value }) }
            : {}),
        },
      );
      if (action !== "delete") onChange({ ...result.config, cues: value.cues });
      else onChange({ ...value, template_id: null });
      await refresh();
      setConfirmDelete(false);
      setMessage(
        action === "delete"
          ? "Template deleted. Clip styling is retained."
          : "Template saved to your library.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save template");
    } finally {
      setBusy(false);
    }
  }
  const number = (
    label: string,
    key: keyof CaptionStyle,
    min: number,
    max: number,
    step: number,
    fallback: number,
  ) => (
    <label className="field" key={key}>
      {label}
      <input
        aria-label={label}
        type="number"
        min={min}
        max={max}
        step={step}
        value={Number(value[key] ?? fallback)}
        onChange={(e) => onChange({ ...value, [key]: Number(e.target.value) })}
      />
    </label>
  );
  const previewLines = layoutCaptionWords(
    sample.split(/\s+/),
    safeCharacterLimit(value),
    value,
  ).slice(0, Math.max(1, value.lines ?? 2));
  const previewY = Math.min(
    0.95 - (value.safe_bottom ?? 0.17),
    Math.max(0.08, value.y ?? 0.78),
  );
  return (
    <section className="caption-studio" aria-label="Caption studio">
      <div className="studio-caption-heading">
        <h3>Caption studio</h3>
        <span className="muted">{selected?.name ?? "Custom style"}</span>
      </div>
      <div className="editor-tabs">
        {[
          "Templates",
          "Style",
          "Colors",
          "Effects",
          "Animation",
          "Position",
          "Layout",
        ].map((item) => (
          <button
            className={`button ${tab === item ? "" : "secondary"}`}
            key={item}
            aria-pressed={tab === item}
            type="button"
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </div>
      <details open={!compact} className="caption-preview-details">
      <summary hidden={!compact}>Sample caption preview</summary>
      <div className="caption-live-preview">
        <div>
          <label className="field">
            Live preview text
            <input
              maxLength={160}
              value={sample}
              onChange={(e) => setSample(e.target.value)}
            />
          </label>
          <p className="muted">
            Preview updates as you change the font, line length, position, and
            style.
          </p>
        </div>
        <div
          className="caption-live-stage"
          aria-label="Live caption style preview"
        >
          <div
            className="caption-live-safe-zone"
            style={{ height: `${(value.safe_bottom ?? 0.17) * 100}%` }}
          >
            <span>Safe area</span>
          </div>
          <div
            className="caption-live-text"
            style={{
              ...captionCSS(value, 0.2),
              position: "absolute",
              left: `${(value.x ?? 0.5) * 100}%`,
              top: `${previewY * 100}%`,
              width: `${(value.width ?? 0.84) * 100}%`,
              transform: `translate(${value.alignment === "left" ? 0 : value.alignment === "right" ? -100 : -50}%, -50%)`,
            }}
          >
            {previewLines.map((line, lineIndex) => (
              <span className="caption-live-line" key={lineIndex}>
                {line.map((token, tokenIndex) => (
                  <span
                    key={`${token.wordIndex}-${tokenIndex}`}
                    style={{
                      color:
                        value.highlight && token.wordIndex === 1
                          ? value.highlight_color
                          : undefined,
                    }}
                  >
                    {token.separator}
                    {token.text}
                  </span>
                ))}
                {lineIndex < previewLines.length - 1 && <br />}
              </span>
            ))}
          </div>
        </div>
      </div>
      </details>
      {tab === "Templates" && (
        <>
          <label className="studio-search">
            <Search size={16} aria-hidden="true" />
            <input
              aria-label="Search caption templates"
              placeholder="Find your style..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="editor-filters" aria-label="Template categories">
            {[
              "All",
              "Favorites",
              "Recently Used",
              "My Templates",
              ...new Set(
                library.items
                  .map((item) => item.category)
                  .filter((category) => category !== "My Templates"),
              ),
            ].map((category) => (
              <button
                key={category}
                type="button"
                className={`button ${filter === category ? "" : "secondary"}`}
                aria-pressed={filter === category}
                onClick={() => setFilter(category)}
              >
                {category}
              </button>
            ))}
          </div>
          <div className="template-grid">
            {loading &&
              [1, 2, 3, 4].map((key) => (
                <Skeleton key={key} className="studio-template-skeleton" />
              ))}
            {library.items
              .filter((item) =>
                `${item.name} ${item.category}`
                  .toLowerCase()
                  .includes(search.toLowerCase()),
              )
              .filter(
                (item) =>
                  filter === "All" ||
                  (filter === "Favorites"
                    ? library.favorites.includes(item.id)
                    : filter === "Recently Used"
                      ? library.recent.includes(item.id)
                      : item.category === filter),
              )
              .map((item) => (
                <article
                  className={`template-card ${value.template_id === item.id ? "selected" : ""}`}
                  key={item.id}
                >
                  <button
                    type="button"
                    aria-label={`Apply ${item.name}`}
                    aria-pressed={value.template_id === item.id}
                    onClick={() => apply(item)}
                  >
                    <div className="template-sample">
                      <span style={captionCSS(item.config, 0.24)}>
                        {sample.split(" ").map((word, i) => (
                          <span
                            key={i}
                            style={{
                              color:
                                item.config.highlight && i === 1
                                  ? item.config.highlight_color
                                  : undefined,
                            }}
                          >
                            {word}{" "}
                          </span>
                        ))}
                      </span>
                    </div>
                    <strong>
                      {item.name}
                      {value.template_id === item.id && (
                        <Check size={14} aria-hidden="true" />
                      )}
                    </strong>
                    <small>{item.category}</small>
                  </button>
                  <button
                    type="button"
                    className="text-button"
                    aria-label={`Favorite ${item.name}`}
                    aria-pressed={library.favorites.includes(item.id)}
                    onClick={() => preference(item.id, "favorite")}
                  >
                    <Star
                      size={14}
                      aria-hidden="true"
                      fill={
                        library.favorites.includes(item.id)
                          ? "currentColor"
                          : "none"
                      }
                    />
                    {library.favorites.includes(item.id)
                      ? "Favorited"
                      : "Favorite"}
                  </button>
                </article>
              ))}
          </div>
        </>
      )}
      {tab === "Style" && (
        <div className="form-grid">
          <label className="field">
            Caption font
            <select
              value={value.font ?? "DejaVu Sans"}
              onChange={(e) => onChange({ ...value, font: e.target.value })}
            >
              {CAPTION_FONTS.map((font) => (
                <option key={font}>{font}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Font weight
            <select
              value={value.weight ?? 700}
              onChange={(e) =>
                onChange({ ...value, weight: Number(e.target.value) })
              }
            >
              <option value={400}>Regular</option>
              <option value={700}>Bold</option>
            </select>
          </label>
          {number("Font size", "size", 20, 120, 1, 54)}
          {number("Letter spacing", "spacing", 0, 12, 0.5, 0)}
        </div>
      )}
      {tab === "Colors" && (
        <div className="form-grid">
          {(
            [
              ["Text color", "primary_color", "#FFFFFF"],
              ["Current word color", "highlight_color", "#FFD700"],
              ["Stroke color", "stroke_color", "#141414"],
              ["Background color", "background_color", "#000000"],
            ] as const
          ).map(([label, key, fallback]) => (
            <ColorField
              key={key}
              label={label}
              value={value[key] ?? fallback}
              onChange={(color) => onChange({ ...value, [key]: color })}
            />
          ))}
          <div
            className="studio-color-presets"
            role="group"
            aria-label="Highlight color presets"
          >
            {["#0be881", "#f5f6fa", "#FFD700", "#FF7A59"].map((color) => (
              <button
                key={color}
                type="button"
                aria-label={`Highlight color ${color}`}
                style={{ background: color }}
                onClick={() => onChange({ ...value, highlight_color: color })}
              />
            ))}
          </div>
        </div>
      )}
      {tab === "Effects" && (
        <div className="form-grid">
          {number("Stroke width", "outline", 0, 8, 1, 3)}
          <label className="check">
            <input
              type="checkbox"
              checked={value.uppercase ?? false}
              onChange={(e) =>
                onChange({ ...value, uppercase: e.target.checked })
              }
            />
            Uppercase
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={value.highlight ?? false}
              onChange={(e) =>
                onChange({ ...value, highlight: e.target.checked })
              }
            />
            Word highlight
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={value.background ?? false}
              onChange={(e) =>
                onChange({ ...value, background: e.target.checked })
              }
            />
            Caption background
          </label>
          {number("Background opacity", "background_opacity", 0, 1, 0.05, 0.65)}
        </div>
      )}
      {tab === "Animation" && (
        <label className="field">
          Caption animation
          <select
            value={value.animation ?? "none"}
            onChange={(e) => onChange({ ...value, animation: e.target.value })}
          >
            {[
              "none",
              "fade",
              "pop",
              "scale",
              "bounce",
              "slide",
              "word-pop",
              "karaoke",
            ].map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
        </label>
      )}
      {tab === "Position" && (
        <>
          <div className="position-grid">
            {positions.map((position) => (
              <button
                className="button secondary"
                type="button"
                key={position}
                onClick={() =>
                  onChange({
                    ...value,
                    x: position.endsWith("left")
                      ? 0.1
                      : position.endsWith("right")
                        ? 0.9
                        : 0.5,
                    y: position.startsWith("top")
                      ? 0.18
                      : position.startsWith("middle")
                        ? 0.5
                        : 0.78,
                    alignment: position.endsWith("left")
                      ? "left"
                      : position.endsWith("right")
                        ? "right"
                        : "center",
                  })
                }
              >
                {position.replaceAll("-", " ")}
              </button>
            ))}
          </div>
          <div className="form-grid">
            {number("Caption X", "x", 0.05, 0.95, 0.01, 0.5)}
            {number("Caption Y", "y", 0.05, 0.95, 0.01, 0.78)}
            {number("Caption width", "width", 0.2, 0.94, 0.01, 0.84)}
            <label className="field">
              Alignment
              <select
                value={value.alignment ?? "center"}
                onChange={(e) =>
                  onChange({ ...value, alignment: e.target.value })
                }
              >
                <option>left</option>
                <option>center</option>
                <option>right</option>
              </select>
            </label>
          </div>
        </>
      )}
      {tab === "Layout" && (
        <div className="form-grid">
          {number("Words per line", "max_words", 1, 12, 1, 5)}
          {number(
            "Maximum characters per line",
            "max_chars_per_line",
            1,
            80,
            1,
            24,
          )}
          {number("Maximum lines", "lines", 1, 2, 1, 2)}
          {number("Shadow", "shadow", 0, 5, 1, 1)}
          {number("Bottom safe zone", "safe_bottom", 0.02, 0.35, 0.01, 0.17)}
          <label className="check">
            <input
              type="checkbox"
              checked={value.punctuation ?? true}
              onChange={(e) =>
                onChange({ ...value, punctuation: e.target.checked })
              }
            />
            Keep punctuation
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={value.remove_special_characters ?? false}
              onChange={(e) =>
                onChange({
                  ...value,
                  remove_special_characters: e.target.checked,
                })
              }
            />
            Remove symbols and special characters
          </label>
        </div>
      )}
      <details>
        <summary>My templates: save, rename, duplicate or set default</summary>
        <label className="field">
          Custom template name
          <input
            maxLength={80}
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <div className="actions">
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={() => save("create")}
          >
            Save as My Template
          </button>
          {custom && (
            <>
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => save("update")}
              >
                Update / rename template
              </button>
              <button
                type="button"
                className="text-button"
                disabled={busy}
                onClick={() => setConfirmDelete(true)}
              >
                Delete template
              </button>
            </>
          )}
          {selected && (
            <button
              type="button"
              className="text-button"
              onClick={() => preference(selected.id, "default")}
            >
              {library.default === selected.id
                ? "Default template"
                : "Set as default"}
            </button>
          )}
        </div>
      </details>
      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => save("delete")}
        title="Delete this template?"
        description="Your existing clips will keep their caption styling."
        confirmLabel="Delete template"
        busy={busy}
      />
      {message && (
        <p className="studio-success" role="status">
          {message}
        </p>
      )}
      {error && (
        <div role="alert" className="form-error">
          {error}
        </div>
      )}
    </section>
  );
}

export function TemplateLibrary() {
  const [value, setValue] = useState<CaptionStyle>({
    enabled: true,
    style: "Clean",
    size: 54,
    font: "DejaVu Sans",
    primary_color: "#FFFFFF",
    highlight_color: "#0be881",
  });
  return (
    <div className="studio-template-library">
      <div className="studio-template-note">
        <Type size={20} aria-hidden="true" />
        <div>
          <strong>Find a style that sounds like you.</strong>
          <p>
            Try a template, personalize the details, then save it to your
            library or set it as your default for new clips.
          </p>
        </div>
      </div>
      <section className="panel">
        <CaptionStudio value={value} onChange={setValue} />
      </section>
    </div>
  );
}
