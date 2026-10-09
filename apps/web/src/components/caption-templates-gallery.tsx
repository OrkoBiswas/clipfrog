"use client";
import Link from "next/link";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import {
  ArrowUpRight,
  Captions,
  Check,
  Play,
  Pause,
  Search,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { api, type Project } from "@/lib/api";
import type { CaptionStyle, FramingStyle } from "@/lib/editor-types";
import {
  CAPTION_TEMPLATES,
  type CaptionTemplate,
} from "@/lib/caption-templates";
import { ANIMATION_LABELS } from "@/lib/caption-effects";
import { captionCSS } from "@/lib/caption-style";
import { captionFrame, sampleWords } from "@/lib/caption-preview";
import { useCaptionLibrary } from "./caption-library";
import { CaptionText } from "./caption-text";
import { CaptionControls } from "./caption-controls";
import { CaptionLivePreview } from "./caption-live-preview";
import { Modal } from "./ui/primitives";
import type { Clip } from "./clips-panel";
import "./caption-templates.css";

function TemplateSample({
  template,
  playing,
}: {
  template: CaptionTemplate;
  playing: boolean;
}) {
  const [seconds, setSeconds] = useState(0.9);
  const sample = useRef<HTMLDivElement>(null);
  const [sampleWidth, setSampleWidth] = useState(320);
  useEffect(() => {
    if (!sample.current) return;
    const observer = new ResizeObserver(([entry]) =>
      setSampleWidth(entry.contentRect.width),
    );
    observer.observe(sample.current);
    return () => observer.disconnect();
  }, []);
  const words = useMemo(() => sampleWords(template.sample), [template.sample]);
  useEffect(() => {
    if (!playing || matchMedia("(prefers-reduced-motion: reduce)").matches)
      return;
    const started = performance.now();
    const timer = window.setInterval(() => {
      if (!document.hidden)
        setSeconds(
          ((performance.now() - started) / 1000) %
            ((words.at(-1)?.end ?? 2) + 0.7),
        );
    }, 33);
    return () => clearInterval(timer);
  }, [playing, words]);
  const frame = captionFrame(words, playing ? seconds : 0.9, template.config);
  return (
    <div
      className="ct-sample"
      ref={sample}
      style={captionCSS(template.config, Math.min(0.5, sampleWidth / 760))}
      aria-hidden="true"
    >
      <CaptionText
        value={template.config}
        lines={frame.lines}
        activeWord={frame.activeWord}
        words={words}
        seconds={playing ? seconds : 0.9}
        elapsed={playing ? seconds - frame.start : 2}
        groupDuration={frame.end - frame.start}
        reducedMotion={!playing}
      />
    </div>
  );
}

function ApplyCaptionStyle({ value, framing, onKeepLayout }: {
  value: CaptionStyle;
  framing?: FramingStyle;
  onKeepLayout: () => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [clips, setClips] = useState<Clip[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<{
    message: string;
    config: string;
  } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const configKey = JSON.stringify({ value, framing });
  useEffect(() => {
    let canceled = false;
    const load = projectId
      ? api<Clip[]>(`/projects/${projectId}/clips`).then((data) => {
          if (!canceled) setClips(data);
        })
      : api<Project[]>("/projects").then((data) => {
          if (!canceled) setProjects(data);
        });
    load
      .catch((e) => {
        if (!canceled)
          setError(e instanceof Error ? e.message : "Could not load clips.");
      })
      .finally(() => {
        if (!canceled) setLoading(false);
      });
    return () => {
      canceled = true;
    };
  }, [projectId, attempt]);
  async function apply() {
    setBusy(true);
    setError("");
    setSaved(null);
    try {
      const result = await api<{ affected: number }>(
        `/projects/${projectId}/clip-actions`,
        {
          method: "POST",
          body: JSON.stringify({
            action: "update",
            clip_ids: selected,
            caption_config: { ...value, cues: undefined },
            ...(framing ? { render_config: { layout: framing.layout, panels: framing.panels } } : {}),
          }),
        },
      );
      setSaved({
        message: `Style saved to ${result.affected} ${result.affected === 1 ? "clip" : "clips"}. Render the clips to update their videos.`,
        config: configKey,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not apply this style.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="ct-apply" aria-label="Apply caption template">
      <h3>Use on your clips</h3>
      <p className="ct-hint">
        Apply the current settings. Your caption text and clip timing are
        preserved.
      </p>
      <p className="ct-hint">
        {framing ? `Multiple screens: ${framing.layout === "auto" ? "automatic collage" : "off"}. ` : "Use Multiple screens in Layout & safe area to apply automatic collage too. "}
        {framing && <button type="button" className="text-button" onClick={onKeepLayout}>Keep existing clip layouts</button>}
      </p>
      <label className="field">
        Project
        <select
          aria-label="Project"
          value={projectId}
          disabled={busy || loading}
          onChange={(e) => {
            setLoading(true);
            setError("");
            setProjectId(e.target.value);
            setClips([]);
            setSelected([]);
            setSaved(null);
          }}
        >
          <option value="">Choose a project</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      {loading ? (
        <p role="status">Loading…</p>
      ) : projectId ? (
        clips.length ? (
          <div className="ct-clip-options">
            {clips.map((clip) => (
              <label className="check" key={clip.id}>
                <input
                  type="checkbox"
                  disabled={busy}
                  checked={selected.includes(clip.id)}
                  onChange={(e) => {
                    setSaved(null);
                    setSelected(
                      e.target.checked
                        ? [...selected, clip.id].slice(0, 100)
                        : selected.filter((id) => id !== clip.id),
                    );
                  }}
                />
                <span>
                  {clip.title}
                  <small>
                    {clip.aspect_ratio} ·{" "}
                    {Math.round((clip.end_ms - clip.start_ms) / 1000)}s
                  </small>
                </span>
              </label>
            ))}
          </div>
        ) : (
          <p className="ct-hint">
            This project has no clips yet. Create a clip first, then choose a
            style.
          </p>
        )
      ) : (
        !projects.length && (
          <p>
            No projects yet.{" "}
            <Link href="/projects/new">Upload your first video</Link> to use
            these captions.
          </p>
        )
      )}
      {error && (
        <div role="alert" className="form-error">
          {error}{" "}
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setLoading(true);
              setError("");
              setAttempt((n) => n + 1);
            }}
          >
            Reload
          </button>
        </div>
      )}
      {saved?.config === configKey && (
        <p role="status" className="notice">
          <Check size={16} /> {saved.message}{" "}
          <Link href={`/projects/${projectId}#clips`}>Open clips</Link>
        </p>
      )}
      <button
        type="button"
        className="button primary"
        disabled={busy || loading || !selected.length}
        onClick={() => void apply()}
      >
        {busy
          ? "Applying…"
          : `Apply to ${selected.length || "selected"} ${selected.length === 1 ? "clip" : "clips"}`}
        <ArrowUpRight size={16} />
      </button>
    </section>
  );
}

function TemplateEditor({
  template,
  onClose,
}: {
  template: CaptionTemplate;
  onClose: () => void;
}) {
  const [value, setValue] = useState<CaptionStyle>(template.config);
  const [framing, setFraming] = useState<FramingStyle | undefined>(undefined);
  const [panel, setPanel] = useState("preview");
  return (
    <Modal
      open
      onClose={onClose}
      title={`Customize ${template.name}`}
      className="ct-customize-dialog"
    >
      <div
        className="ct-mobile-tabs"
        role="group"
        aria-label="Template workbench view"
      >
        {[
          ["preview", "Preview"],
          ["customize", "Customize"],
          ["apply", "Use on clips"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-pressed={panel === id}
            onClick={() => setPanel(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="ct-workbench" data-panel={panel}>
        <div className="ct-workbench-preview">
          <CaptionLivePreview
            value={value}
            name={value.style ?? template.name}
          />
          <ApplyCaptionStyle value={value} framing={framing} onKeepLayout={() => setFraming(undefined)} />
        </div>
        <CaptionControls value={value} onChange={setValue} framing={framing ?? { layout: "single" }} onFramingChange={setFraming} />
      </div>
    </Modal>
  );
}

export function CaptionTemplatesGallery() {
  const { templates, remove } = useCaptionLibrary();
  const [category, setCategory] = useState("All styles");
  const [query, setQuery] = useState("");
  const [hovered, setHovered] = useState("");
  const [featuredPlaying, setFeaturedPlaying] = useState(true);
  const [selected, setSelected] = useState<CaptionTemplate | null>(null);
  const [error, setError] = useState("");
  const categories = [
    "All styles",
    "Clean",
    "Creator",
    "Karaoke",
    "Editorial",
    "Expressive",
    "My presets",
  ];
  const visible = templates.filter(
    (t) =>
      (category === "All styles" || t.category === category) &&
      `${t.name} ${t.category} ${t.config.font} ${t.description}`
        .toLowerCase()
        .includes(query.toLowerCase().trim()),
  );
  return (
    <div className="ct-gallery">
      <header className="ct-header">
        <div>
          <p className="eyebrow">
            <Captions size={14} /> THE CAPTION COLLECTION
          </p>
          <h1>
            Words with <em>presence.</em>
          </h1>
          <p>Find your signature style. Set split screen in Layout &amp; safe area when customizing.</p>
        </div>
        <div className="ct-library-count">
          <strong>24</strong>
          <span>
            crafted styles
            <br />
            endless possibilities
          </span>
        </div>
      </header>
      <section className="ct-feature" aria-label="Featured caption style">
        <div>
          <span className="ct-overline">SMALL WORDS. BIG FEELING.</span>
          <h2>
            Your voice.
            <br />
            <span>A whole new look.</span>
          </h2>
          <p>
            Word-by-word motion, bold type, and full creative control.
            <br />
            Preview a style, make it yours, then put it to work.
          </p>
          <button
            type="button"
            className="button primary"
            onClick={() => setSelected(CAPTION_TEMPLATES[0])}
          >
            Explore Studio Rise <ArrowUpRight size={16} />
          </button>
        </div>
        <div className="ct-feature-art">
          <span className="ct-film-label">STUDIO RISE / 01</span>
          <button
            type="button"
            className="ct-feature-toggle icon-button"
            aria-label={
              featuredPlaying
                ? "Pause featured captions"
                : "Play featured captions"
            }
            onClick={() => setFeaturedPlaying(!featuredPlaying)}
          >
            {featuredPlaying ? <Pause size={15} /> : <Play size={15} />}
          </button>
          <TemplateSample
            template={CAPTION_TEMPLATES[0]}
            playing={featuredPlaying}
          />
          <div className="ct-wave" aria-hidden="true">
            {Array.from({ length: 32 }, (_, i) => (
              <i key={i} style={{ height: `${8 + ((i * 19) % 37)}px` }} />
            ))}
          </div>
          <span className="ct-film-foot">
            <span /> MOTION, MEET MEANING
          </span>
        </div>
      </section>
      <div className="ct-browse-header">
        <h2>
          Find your type<span>{visible.length} styles</span>
        </h2>
        <label className="ct-search">
          <Search size={17} />
          <input
            aria-label="Search caption templates"
            placeholder="Search styles, fonts, moods…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      <div className="ct-filters" role="group" aria-label="Template categories">
        {categories.map((item) => (
          <button
            type="button"
            key={item}
            aria-pressed={category === item}
            onClick={() => setCategory(item)}
          >
            {item}
          </button>
        ))}
        <span>Hover to see the motion</span>
      </div>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <div className="ct-grid">
        {visible.map((template, index) => (
          <article
            className="ct-card"
            key={template.id}
            style={{ "--ct-accent": template.accent } as CSSProperties}
          >
            <button
              type="button"
              className="ct-card-preview"
              aria-label={`Preview ${template.name}`}
              onMouseEnter={() => setHovered(template.id)}
              onMouseLeave={() => setHovered("")}
              onFocus={() => setHovered(template.id)}
              onBlur={() => setHovered("")}
              onClick={() => setSelected(template)}
            >
              <span className="ct-card-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="ct-card-motion">
                <Play size={10} fill="currentColor" />{" "}
                {ANIMATION_LABELS[template.config.animation ?? "word-pop"]}
              </span>
              <TemplateSample
                template={template}
                playing={hovered === template.id}
              />
              <span className="ct-card-font">{template.config.font}</span>
              <span className="ct-preview-action">
                <SlidersHorizontal size={13} /> Preview & customize
              </span>
            </button>
            <div className="ct-card-info">
              <div>
                <h3>{template.name}</h3>
                <p>{template.description}</p>
              </div>
              <span>{template.category}</span>
            </div>
            {template.id.startsWith("custom-") && (
              <button
                type="button"
                className="text-button ct-remove"
                onClick={() => {
                  try {
                    remove(template.id);
                  } catch {
                    setError("Could not remove this browser preset.");
                  }
                }}
              >
                <Trash2 size={13} /> Remove saved preset
              </button>
            )}
          </article>
        ))}
      </div>
      {!visible.length && (
        <div className="empty">
          <Captions size={32} />
          <h3>
            {category === "My presets"
              ? "Your signature starts here"
              : "No matching styles"}
          </h3>
          <p>
            {category === "My presets"
              ? "Customize any style, then save it to your personal presets."
              : "Try another font, mood, or category."}
          </p>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setQuery("");
              setCategory("All styles");
            }}
          >
            Browse all styles
          </button>
        </div>
      )}
      <footer className="ct-gallery-foot">
        <span>Designed to be read. Made to be remembered.</span>
        <span>
          24 word-timed styles · 8 font families · Full creative control
        </span>
      </footer>
      {selected && (
        <TemplateEditor
          key={selected.id}
          template={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
