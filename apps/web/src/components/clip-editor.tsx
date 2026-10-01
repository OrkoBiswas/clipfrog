"use client";
import { useEffect, useEffectEvent, useRef, useState } from "react";
import Link from "next/link";
import { Check } from "lucide-react";
import { api } from "@/lib/api";
import type { Clip } from "./clips-panel";
import { CaptionStudio } from "./caption-studio";
import { CompositionPreview, FramingControls } from "./composition-preview";
import { ConfirmDialog, Modal, Toggle } from "./ui/primitives";
import { useToast } from "./ui/toast";
import { PositionGrid, timecode } from "./studio-controls";
import "./studio.css";
type Cue = { start_ms: number; end_ms: number; text: string };
const ratios = ["9:16", "16:9", "1:1", "4:5", "3:4", "4:3", "21:9", "Original"];
export function EditorDialog({
  clip,
  projectId,
  onClose,
  onSaved,
}: {
  clip: Clip;
  projectId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [dirty, setDirty] = useState(false);
  const [discard, setDiscard] = useState(false);
  function close() {
    if (dirty) setDiscard(true);
    else onClose();
  }
  return (
    <>
      <Modal
        open
        onClose={close}
        title={clip.id ? "Clip editor" : "Create a clip"}
        className="studio-editor-modal"
      >
        <ClipEditor
          clip={clip}
          projectId={projectId}
          onClose={close}
          onSaved={onSaved}
          onDirty={setDirty}
        />
      </Modal>
      <ConfirmDialog
        open={discard}
        onClose={() => setDiscard(false)}
        onConfirm={onClose}
        title="Discard your edits?"
        description="Your unsaved changes will be lost. Save a draft to keep working later."
        confirmLabel="Discard changes"
      />
    </>
  );
}

function ClipEditor({
  clip,
  projectId,
  onClose,
  onSaved,
  onDirty,
}: {
  clip: Clip;
  projectId: string;
  onClose: () => void;
  onSaved: () => void;
  onDirty: (dirty: boolean) => void;
}) {
  const [value, setValue] = useState(clip);
  const [cues, setCues] = useState<Cue[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingCues, setLoadingCues] = useState(false);
  const [error, setError] = useState("");
  const [panel, setPanel] = useState("Captions");
  const { toast } = useToast();
  const form = useRef<HTMLFormElement>(null);
  const dirty = JSON.stringify(value) !== JSON.stringify(clip) || cues !== null;
  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  async function loadCaptions() {
    setLoadingCues(true);
    setError("");
    try {
      setCues(
        await api<Cue[]>(`/projects/${projectId}/clips/${clip.id}/captions`),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load captions");
    } finally {
      setLoadingCues(false);
    }
  }
  async function save(render: boolean) {
    if (!form.current?.reportValidity()) return;
    if (value.end_ms <= value.start_ms) {
      setError("End time must be after the start time.");
      setPanel("Timing");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = {
        title: value.title,
        start_ms: value.start_ms,
        end_ms: value.end_ms,
        aspect_ratio: value.aspect_ratio,
        caption_config: {
          ...value.caption_config,
          ...(cues !== null ? { cues } : {}),
        },
        overlay_config: value.overlay_config,
        render_config: value.render_config,
      };
      const result = await api<Clip>(
        `/projects/${projectId}/clips${clip.id ? `/${clip.id}` : ""}`,
        { method: clip.id ? "PUT" : "POST", body: JSON.stringify(body) },
      );
      if (render)
        await api(`/projects/${projectId}/clips/${result.id}/render`, {
          method: "POST",
        });
      toast(
        render ? "Rendering started" : "Clip saved",
        render
          ? "You can keep working while your clip renders."
          : "Your changes are ready for the next render.",
      );
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save clip");
    } finally {
      setBusy(false);
    }
  }
  const keyboardSave = useEffectEvent(() => {
    if (!busy) void save(false);
  });
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        keyboardSave();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  const overlay = value.overlay_config;
  return (
    <form
      ref={form}
      className="studio-editor"
      onSubmit={(event) => {
        event.preventDefault();
        void save(true);
      }}
    >
      <div className="studio-editor-heading">
        <div>
          <h3>{value.title || "Untitled clip"}</h3>
          <span>
            {timecode(value.end_ms - value.start_ms)} · {value.aspect_ratio} ·
            Revision {clip.revision}
          </span>
        </div>
        <span className="studio-save-state" role="status">
          <Check size={14} aria-hidden="true" />
          {busy
            ? "Saving changes…"
            : dirty
              ? "Unsaved changes"
              : "All changes saved"}
        </span>
      </div>
      <div className="studio-editor-layout">
        <div className="studio-editor-canvas">
          <CompositionPreview
            projectId={projectId}
            body={{
              ...value,
              caption_config: {
                ...value.caption_config,
                ...(cues !== null ? { cues } : {}),
              },
            }}
            onCaption={(caption_config) =>
              setValue({ ...value, caption_config })
            }
            onOverlay={(overlay_config) =>
              setValue({ ...value, overlay_config })
            }
            onFraming={(render_config) => setValue({ ...value, render_config })}
          />
        </div>
        <aside className="studio-inspector">
          <div
            className="studio-panel-tabs"
            role="group"
            aria-label="Editor tools"
          >
            {["Captions", "Timing", "Reframe", "Brand", "Export"].map((tab) => (
              <button
                type="button"
                key={tab}
                aria-pressed={panel === tab}
                onClick={() => setPanel(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="studio-inspector-body">
            {panel === "Captions" && (
              <>
                <Toggle
                  checked={value.caption_config.enabled ?? true}
                  onChange={(enabled) =>
                    setValue({
                      ...value,
                      caption_config: { ...value.caption_config, enabled },
                    })
                  }
                  label="Burn captions into video"
                />
                <CaptionStudio
                  compact
                  value={value.caption_config}
                  onChange={(caption_config) =>
                    setValue({ ...value, caption_config })
                  }
                />
                {clip.id && (
                  <button
                    className="button secondary"
                    type="button"
                    disabled={loadingCues}
                    onClick={loadCaptions}
                  >
                    {loadingCues ? "Loading captions…" : "Edit caption text"}
                  </button>
                )}
                {cues && (
                  <div className="studio-cues">
                    <p className="muted">
                      Times are relative to this clip. Text edits retain
                      sentence timing.
                    </p>
                    {!cues.length && (
                      <p>No transcript is available for this clip.</p>
                    )}
                    {cues.map((cue, index) => (
                      <label className="field" key={`${cue.start_ms}-${index}`}>
                        {timecode(cue.start_ms)}–{timecode(cue.end_ms)}
                        <textarea
                          value={cue.text}
                          onChange={(event) =>
                            setCues(
                              cues.map((item, i) =>
                                i === index
                                  ? { ...item, text: event.target.value }
                                  : item,
                              ),
                            )
                          }
                        />
                      </label>
                    ))}
                  </div>
                )}
              </>
            )}
            {panel === "Timing" && (
              <>
                <h3>The right moment</h3>
                <p className="muted">
                  Set the start and end in your source video.
                </p>
                <label className="field">
                  Clip title
                  <input
                    required
                    maxLength={160}
                    value={value.title}
                    onChange={(event) =>
                      setValue({ ...value, title: event.target.value })
                    }
                  />
                </label>
                <div className="form-grid">
                  {[
                    ["Start (seconds)", "start_ms"],
                    ["End (seconds)", "end_ms"],
                  ].map(([label, field]) => (
                    <label className="field" key={field}>
                      {label}
                      <input
                        required
                        type="number"
                        min={0}
                        step={0.01}
                        value={value[field as "start_ms" | "end_ms"] / 1000}
                        onChange={(event) =>
                          setValue({
                            ...value,
                            [field]: Math.round(
                              Number(event.target.value) * 1000,
                            ),
                          })
                        }
                      />
                    </label>
                  ))}
                </div>
                <label className="field">
                  Aspect ratio
                  <select
                    value={value.aspect_ratio}
                    onChange={(event) =>
                      setValue({ ...value, aspect_ratio: event.target.value })
                    }
                  >
                    {ratios.map((ratio) => (
                      <option key={ratio}>{ratio}</option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Opening title overlay
                  <input
                    maxLength={160}
                    value={overlay.title ?? ""}
                    onChange={(event) =>
                      setValue({
                        ...value,
                        overlay_config: {
                          ...overlay,
                          title: event.target.value,
                        },
                      })
                    }
                  />
                </label>
                <label className="field">
                  Title style
                  <select
                    value={overlay.title_style ?? "Bold"}
                    onChange={(event) =>
                      setValue({
                        ...value,
                        overlay_config: {
                          ...overlay,
                          title_style: event.target.value,
                        },
                      })
                    }
                  >
                    {["Bold", "Minimal", "Boxed"].map((style) => (
                      <option key={style}>{style}</option>
                    ))}
                  </select>
                </label>
              </>
            )}
            {panel === "Reframe" && (
              <FramingControls
                value={value.render_config}
                onChange={(render_config) =>
                  setValue({ ...value, render_config })
                }
              />
            )}
            {panel === "Brand" && (
              <>
                <h3>Your signature</h3>
                <p className="muted">
                  Keep your identity visible without covering the moment.
                </p>
                <label className="field">
                  Watermark text
                  <input
                    maxLength={60}
                    value={overlay.watermark ?? ""}
                    onChange={(event) =>
                      setValue({
                        ...value,
                        overlay_config: {
                          ...overlay,
                          watermark: event.target.value,
                        },
                      })
                    }
                  />
                </label>
                {overlay.logo_asset_id ? (
                  <>
                    <Toggle
                      checked={overlay.logo_enabled ?? true}
                      onChange={(logo_enabled) =>
                        setValue({
                          ...value,
                          overlay_config: { ...overlay, logo_enabled },
                        })
                      }
                      label="Show brand logo"
                    />
                    <span className="field">Logo placement</span>
                    <PositionGrid
                      value={overlay.logo_position ?? "top-right"}
                      onChange={(logo_position) =>
                        setValue({
                          ...value,
                          overlay_config: {
                            ...overlay,
                            logo_position,
                            logo_x: null,
                            logo_y: null,
                          },
                        })
                      }
                    />
                    {(
                      [
                        ["Logo size", "logo_size", 0.05, 0.3, 0.01, 0.16],
                        ["Logo opacity", "logo_opacity", 0, 1, 0.05, 1],
                        ["Logo margin", "logo_margin", 0, 0.25, 0.01, 0.04],
                      ] as const
                    ).map(([label, key, min, max, step, fallback]) => (
                      <label className="field studio-range" key={key}>
                        <span>
                          {label}
                          <output>
                            {Math.round((overlay[key] ?? fallback) * 100)}%
                          </output>
                        </span>
                        <input
                          aria-label={label}
                          type="range"
                          min={min}
                          max={max}
                          step={step}
                          value={overlay[key] ?? fallback}
                          onChange={(event) =>
                            setValue({
                              ...value,
                              overlay_config: {
                                ...overlay,
                                [key]: Number(event.target.value),
                              },
                            })
                          }
                        />
                      </label>
                    ))}
                  </>
                ) : (
                  <div className="notice">
                    Apply a <Link href="/brand-kit">brand kit</Link> to your
                    project to add a logo.
                  </div>
                )}
              </>
            )}
            {panel === "Export" && (
              <>
                <h3>Ready for your audience</h3>
                <p className="muted">
                  Save a draft or render your edits into a new MP4.
                </p>
                <dl className="studio-export-summary">
                  <div>
                    <dt>Format</dt>
                    <dd>MP4 · H.264 / AAC</dd>
                  </div>
                  <div>
                    <dt>Aspect ratio</dt>
                    <dd>{value.aspect_ratio}</dd>
                  </div>
                  <div>
                    <dt>Duration</dt>
                    <dd>
                      {((value.end_ms - value.start_ms) / 1000).toFixed(1)}{" "}
                      seconds
                    </dd>
                  </div>
                  <div>
                    <dt>Captions</dt>
                    <dd>
                      {value.caption_config.enabled === false
                        ? "Off"
                        : "Burned in"}
                    </dd>
                  </div>
                </dl>
                <label className="field">
                  Render quality
                  <select
                    value={value.render_config.quality ?? "Standard"}
                    onChange={(event) =>
                      setValue({
                        ...value,
                        render_config: {
                          ...value.render_config,
                          quality: event.target.value,
                        },
                      })
                    }
                  >
                    {["Draft", "Standard", "High"].map((quality) => (
                      <option key={quality}>{quality}</option>
                    ))}
                  </select>
                </label>
                <p className="notice">
                  Your existing render stays available until the new version is
                  ready.
                </p>
              </>
            )}
          </div>
        </aside>
      </div>
      <div className="studio-editor-footer">
        <button className="text-button" type="button" onClick={onClose}>
          Close
        </button>
        <span className="muted studio-keyboard-hint">Ctrl / ⌘ + S to save</span>
        <div className="actions">
          <button
            className="button secondary"
            disabled={busy}
            type="button"
            onClick={() => save(false)}
          >
            Save edits
          </button>
          <button className="button" disabled={busy} type="submit">
            {busy ? "Saving…" : "Save and render"}
          </button>
        </div>
      </div>
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
    </form>
  );
}

