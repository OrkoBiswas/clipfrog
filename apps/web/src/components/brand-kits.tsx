"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Check, Copy, Palette, Plus, Upload } from "lucide-react";
import { ConfirmDialog } from "./ui/primitives";
import { useToast } from "./ui/toast";
import { PositionGrid } from "./studio-controls";
import "./studio.css";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { CAPTION_FONTS } from "@/lib/editor-types";
import platforms from "../../../../packages/shared/platforms.json";
import { CaptionStudio, captionCSS } from "./caption-studio";

export type BrandConfig = {
  id?: string;
  name?: string;
  captions: {
    enabled: boolean;
    style: string;
    font: string;
    size: number;
    primary_color: string;
    highlight_color: string;
  };
  overlay: {
    title: string;
    watermark: string;
    title_style: string;
    logo_position: string;
    logo_enabled?: boolean;
    logo_asset_id?: string | null;
    logo_size?: number;
    logo_opacity?: number;
    logo_margin?: number;
  };
  ratios: string[];
  platform_preset?: string;
};
export type BrandKit = {
  id: string;
  name: string;
  config: BrandConfig;
  has_logo: boolean;
};
const styles = [
  "Clean",
  "Bold",
  "Minimal",
  "Karaoke",
  "Creator",
  "Podcast",
  "High Contrast",
];
const ratios = ["9:16", "16:9", "1:1", "4:5", "3:4", "4:3", "21:9", "Original"];
const defaults: BrandConfig = {
  captions: {
    enabled: true,
    style: "Clean",
    font: "DejaVu Sans",
    size: 54,
    primary_color: "#FFFFFF",
    highlight_color: "#0be881",
  },
  overlay: {
    title: "",
    watermark: "",
    title_style: "Bold",
    logo_position: "top-right",
    logo_enabled: true,
  },
  ratios: ["9:16"],
};

export function BrandKits({ initial }: { initial: BrandKit[] }) {
  const [kits, setKits] = useState(initial);
  const [step, setStep] = useState(0);
  const formRef = useRef<HTMLFormElement>(null);
  const { toast } = useToast();
  const steps = ["Identity", "Captions", "Placement", "Output"];
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [config, setConfig] = useState<BrandConfig>(defaults);
  const [logo, setLogo] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [fileKey, setFileKey] = useState(0);
  const [deleting, setDeleting] = useState<string | null>(null);
  function edit(kit?: BrandKit) {
    setStep(0);
    setEditing(kit?.id ?? null);
    setName(kit?.name ?? "");
    setConfig(kit?.config ?? defaults);
    setLogo(null);
    setFileKey((key) => key + 1);
    setError("");
    setMessage("");
  }
  async function reload() {
    setKits(await api<BrandKit[]>("/brand-kits"));
  }
  async function save() {
    if (!name.trim()) {
      setStep(0);
      setError("Give your brand kit a name before saving.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const kit = await api<BrandKit>(
        `/brand-kits${editing ? `/${editing}` : ""}`,
        {
          method: editing ? "PUT" : "POST",
          body: JSON.stringify({ name, ...config }),
        },
      );
      setEditing(kit.id);
      if (logo)
        await api(`/brand-kits/${kit.id}/logo`, {
          method: "PUT",
          headers: { "Content-Type": logo.type || "application/octet-stream" },
          body: logo,
        });
      setLogo(null);
      setFileKey((key) => key + 1);
      await reload();
      setMessage(
        "Brand kit saved. Apply it to a project to use these settings.",
      );
      toast("Brand kit saved", "Your identity is ready for your next project.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save brand kit");
      await reload().catch(() => {});
    } finally {
      setBusy(false);
    }
  }
  async function remove(id: string, onlyLogo = false) {
    setBusy(true);
    setError("");
    try {
      await api(`/brand-kits/${id}${onlyLogo ? "/logo" : ""}`, {
        method: "DELETE",
      });
      await reload();
      if (!onlyLogo && editing === id) edit();
      setDeleting(null);
      setMessage(
        onlyLogo
          ? "Logo removed. Existing projects keep their copy."
          : "Brand kit deleted. Existing projects keep their settings.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete brand kit");
    } finally {
      setBusy(false);
    }
  }
  async function preview(id: string) {
    try {
      const result = await api<{ url: string }>(`/brand-kits/${id}/logo`);
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not preview logo");
    }
  }
  async function duplicate(kit: BrandKit) {
    setBusy(true);
    setError("");
    try {
      let image: Blob | null = null;
      if (kit.has_logo) {
        const signed = await api<{ url: string }>(`/brand-kits/${kit.id}/logo`);
        const response = await fetch(signed.url);
        if (!response.ok)
          throw new Error("Could not copy the brand logo. Please try again.");
        image = await response.blob();
      }
      const next = await api<BrandKit>("/brand-kits", {
        method: "POST",
        body: JSON.stringify({
          ...kit.config,
          name: `${kit.name.slice(0, 90)} copy`,
        }),
      });
      if (image)
        await api(`/brand-kits/${next.id}/logo`, {
          method: "PUT",
          headers: { "Content-Type": image.type },
          body: image,
        });
      await reload();
      toast("Brand kit duplicated");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not duplicate brand kit",
      );
      await reload().catch(() => {});
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Your visual identity</p>
          <h1>Make every clip unmistakably yours.</h1>
          <p>
            Save your logo, caption colors and typography once, then apply them
            to any project.
          </p>
        </div>
        <button
          className="button"
          disabled={busy}
          onClick={() => {
            edit();
            formRef.current?.scrollIntoView({
              behavior: "smooth",
              block: "start",
            });
          }}
        >
          <Plus size={16} aria-hidden="true" />
          New brand kit
        </button>
      </div>
      <section className="panel studio-brands">
        <div className="section-head">
          <h2>Saved kits</h2>
          <span className="studio-count">{kits.length} / 20</span>
        </div>
        {!kits.length && (
          <div className="studio-empty">
            <Palette size={28} aria-hidden="true" />
            <h3>A consistent look, in every clip.</h3>
            <p>No brand kits yet. Create your first one below.</p>
          </div>
        )}
        <div className="studio-brand-grid">
          {kits.map((kit) => (
            <article
              className={`studio-brand-card ${editing === kit.id ? "is-selected" : ""}`}
              key={kit.id}
            >
              <div
                className="studio-brand-swatch"
                style={{ borderColor: kit.config.captions.highlight_color }}
              >
                <BrandLogo kit={kit} />
                <span style={captionCSS(kit.config.captions, 0.45)}>
                  Your story.
                  <br />
                  <span style={{ color: kit.config.captions.highlight_color }}>
                    Your signature.
                  </span>
                </span>
              </div>
              <div className="studio-brand-card-body">
                <h3>{kit.name}</h3>
                <div className="studio-brand-font">
                  <span
                    style={{ background: kit.config.captions.primary_color }}
                  />
                  <span
                    style={{ background: kit.config.captions.highlight_color }}
                  />
                  {kit.config.captions.font}
                </div>
                <p>
                  {kit.config.captions.style} captions ·{" "}
                  {kit.config.ratios.join(", ")}
                </p>
                <div className="actions">
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => edit(kit)}
                  >
                    Edit {kit.name}
                  </button>
                  <button
                    className="studio-icon-button"
                    type="button"
                    disabled={busy}
                    aria-label={`Duplicate ${kit.name}`}
                    title="Duplicate brand kit"
                    onClick={() => duplicate(kit)}
                  >
                    <Copy size={16} aria-hidden="true" />
                  </button>
                  {kit.has_logo && (
                    <button
                      className="text-button"
                      onClick={() => preview(kit.id)}
                    >
                      Preview logo
                    </button>
                  )}
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => setDeleting(kit.id)}
                  >
                    Delete {kit.name}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="panel studio-brand-builder">
        <h2>{editing ? "Edit brand kit" : "Create brand kit"}</h2>
        <div className="studio-brand-build-layout">
          <div>
            <div
              className="studio-brand-steps"
              role="group"
              aria-label="Brand kit setup"
            >
              {steps.map((label, index) => (
                <button
                  type="button"
                  key={label}
                  aria-pressed={step === index}
                  disabled={busy}
                  onClick={() => setStep(index)}
                >
                  <span>
                    {index < step ? (
                      <Check size={13} aria-hidden="true" />
                    ) : (
                      index + 1
                    )}
                  </span>
                  {label}
                </button>
              ))}
            </div>
            <form
              ref={formRef}
              className="form"
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
            >
              {step === 0 && (
                <fieldset disabled={busy}>
                  <legend>Identity</legend>
                  <label className="field">
                    Brand kit name
                    <input
                      required
                      maxLength={100}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </label>
                  <label className="field studio-logo-upload">
                    <Upload size={24} aria-hidden="true" />
                    Logo image
                    <input
                      key={fileKey}
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      onChange={(e) => {
                        const file = e.target.files?.[0] ?? null;
                        if (file && file.size > 2 * 1024 * 1024) {
                          setError("Choose a logo smaller than 2 MB.");
                          e.target.value = "";
                          return;
                        }
                        setError("");
                        setLogo(file);
                      }}
                    />
                  </label>
                  <p className="muted">
                    PNG, JPEG or WebP, up to 2 MB and four million pixels.
                    Transparent PNG works best.
                  </p>
                  {editing &&
                    kits.find((kit) => kit.id === editing)?.has_logo && (
                      <button
                        className="text-button"
                        type="button"
                        onClick={() => remove(editing, true)}
                      >
                        Remove saved logo
                      </button>
                    )}
                </fieldset>
              )}
              {step === 1 && (
                <fieldset disabled={busy}>
                  <legend>Caption appearance</legend>
                  <details>
                    <summary>Caption templates and customization</summary>
                    <CaptionStudio
                      value={config.captions}
                      onChange={(next) =>
                        setConfig({
                          ...config,
                          captions: { ...config.captions, ...next },
                        })
                      }
                    />
                  </details>
                  <div className="form-grid">
                    <label className="field">
                      Caption style
                      <select
                        value={config.captions.style}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            captions: {
                              ...config.captions,
                              style: e.target.value,
                            },
                          })
                        }
                      >
                        {styles.map((style) => (
                          <option key={style}>{style}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      Default font
                      <select
                        value={config.captions.font}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            captions: {
                              ...config.captions,
                              font: e.target.value,
                            },
                          })
                        }
                      >
                        {CAPTION_FONTS.map((font) => (
                          <option key={font}>{font}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      Caption size
                      <input
                        type="number"
                        min={20}
                        max={120}
                        value={config.captions.size}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            captions: {
                              ...config.captions,
                              size: Number(e.target.value),
                            },
                          })
                        }
                      />
                    </label>
                    <label className="field">
                      Primary color
                      <input
                        type="color"
                        value={config.captions.primary_color}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            captions: {
                              ...config.captions,
                              primary_color: e.target.value,
                            },
                          })
                        }
                      />
                    </label>
                    <label className="field">
                      Secondary color
                      <input
                        type="color"
                        value={config.captions.highlight_color}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            captions: {
                              ...config.captions,
                              highlight_color: e.target.value,
                            },
                          })
                        }
                      />
                    </label>
                  </div>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={config.captions.enabled}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          captions: {
                            ...config.captions,
                            enabled: e.target.checked,
                          },
                        })
                      }
                    />
                    Enable captions by default
                  </label>
                  <p
                    className="notice"
                    style={{
                      background: "#20232b",
                      color: config.captions.primary_color,
                      fontWeight: 700,
                    }}
                  >
                    Your story,{" "}
                    <span style={{ color: config.captions.highlight_color }}>
                      your colors.
                    </span>
                  </p>
                </fieldset>
              )}
              {step === 2 && (
                <fieldset disabled={busy}>
                  <legend>Logo and title</legend>
                  <div className="form-grid">
                    <div className="field">
                      <span>Logo and watermark position</span>
                      <PositionGrid
                        label="Logo and watermark position"
                        value={config.overlay.logo_position}
                        onChange={(logo_position) =>
                          setConfig({
                            ...config,
                            overlay: { ...config.overlay, logo_position },
                          })
                        }
                      />
                    </div>
                    <label className="field">
                      Logo size
                      <input
                        type="number"
                        min="0.05"
                        max="0.3"
                        step="0.01"
                        value={config.overlay.logo_size ?? 0.16}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            overlay: {
                              ...config.overlay,
                              logo_size: Number(e.target.value),
                            },
                          })
                        }
                      />
                    </label>
                    <label className="field">
                      Logo opacity
                      <input
                        type="number"
                        min="0"
                        max="1"
                        step="0.05"
                        value={config.overlay.logo_opacity ?? 1}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            overlay: {
                              ...config.overlay,
                              logo_opacity: Number(e.target.value),
                            },
                          })
                        }
                      />
                    </label>
                    <label className="field">
                      Logo margin
                      <input
                        type="number"
                        min="0"
                        max="0.25"
                        step="0.01"
                        value={config.overlay.logo_margin ?? 0.04}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            overlay: {
                              ...config.overlay,
                              logo_margin: Number(e.target.value),
                            },
                          })
                        }
                      />
                    </label>
                    <label className="field">
                      Title style
                      <select
                        value={config.overlay.title_style}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            overlay: {
                              ...config.overlay,
                              title_style: e.target.value,
                            },
                          })
                        }
                      >
                        {["Bold", "Minimal", "Boxed"].map((style) => (
                          <option key={style}>{style}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      Default opening title
                      <input
                        maxLength={160}
                        value={config.overlay.title}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            overlay: {
                              ...config.overlay,
                              title: e.target.value,
                            },
                          })
                        }
                      />
                    </label>
                    <label className="field">
                      Watermark text
                      <input
                        maxLength={60}
                        value={config.overlay.watermark}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            overlay: {
                              ...config.overlay,
                              watermark: e.target.value,
                            },
                          })
                        }
                      />
                    </label>
                  </div>
                </fieldset>
              )}
              {step === 3 && (
                <fieldset disabled={busy}>
                  <legend>Preferred output</legend>
                  <label className="field">
                    Platform preset
                    <select
                      value={config.platform_preset ?? "Custom"}
                      onChange={(e) => {
                        const preset = platforms.find(
                          (item) => item.name === e.target.value,
                        );
                        setConfig({
                          ...config,
                          platform_preset: e.target.value,
                          ratios:
                            preset && preset.name !== "Custom"
                              ? [preset.ratio]
                              : config.ratios,
                        });
                      }}
                    >
                      {platforms.map((preset) => (
                        <option key={preset.name}>{preset.name}</option>
                      ))}
                    </select>
                  </label>
                  <p className="muted">
                    Choose a platform aspect ratio or select custom ratios
                    below. Project duration settings stay unchanged.
                  </p>
                  <div className="checks">
                    {ratios.map((ratio) => (
                      <label className="check" key={ratio}>
                        <input
                          type="checkbox"
                          checked={config.ratios.includes(ratio)}
                          onChange={(e) =>
                            setConfig({
                              ...config,
                              platform_preset: "Custom",
                              ratios: e.target.checked
                                ? [...config.ratios, ratio]
                                : config.ratios.filter(
                                    (item) => item !== ratio,
                                  ),
                            })
                          }
                        />
                        {ratio}
                      </label>
                    ))}
                  </div>
                </fieldset>
              )}
              <div className="studio-brand-footer">
                <button
                  type="button"
                  className="button secondary"
                  disabled={step === 0 || busy}
                  onClick={() => setStep(step - 1)}
                >
                  Back
                </button>
                {step < 3 && (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={busy}
                    onClick={() => {
                      if (formRef.current?.reportValidity()) setStep(step + 1);
                    }}
                  >
                    Continue
                    <ArrowRight size={16} aria-hidden="true" />
                  </button>
                )}
                <button
                  className="button"
                  disabled={busy || !config.ratios.length}
                  type="submit"
                >
                  {busy ? "Saving…" : "Save brand kit"}
                </button>
              </div>
            </form>
          </div>
          <aside className="studio-brand-preview">
            <p className="eyebrow">Your identity, in frame</p>
            <div className="studio-brand-preview-stage">
              <div
                className={`studio-brand-logo-position position-${config.overlay.logo_position}`}
                style={{
                  opacity: config.overlay.logo_opacity ?? 1,
                  width: `${(config.overlay.logo_size ?? 0.16) * 100}%`,
                }}
              >
                <BrandLogo
                  key={`${editing}-${fileKey}`}
                  kit={kits.find((kit) => kit.id === editing)}
                  file={logo}
                />
              </div>
              <div
                className="studio-brand-preview-caption"
                style={captionCSS(config.captions, 0.52)}
              >
                Your story.
                <br />
                <span style={{ color: config.captions.highlight_color }}>
                  Your signature.
                </span>
              </div>
              <span className="studio-brand-watermark">
                {config.overlay.watermark || name || "Your brand"}
              </span>
            </div>
            <h3>{name || "Your brand kit"}</h3>
            <p>
              {config.captions.font} / {config.ratios.join(" / ")}
            </p>
            <Link href="/projects">
              Apply a saved kit to a project{" "}
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </aside>
        </div>
        {message && (
          <p className="studio-success" role="status">
            {message}
          </p>
        )}
        <div className="form-error" role="alert">
          {error}
        </div>
      </section>
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        onConfirm={() => {
          if (deleting) void remove(deleting);
        }}
        title="Delete this brand kit?"
        description="Existing projects will keep their saved branding and logo."
        confirmLabel="Confirm deletion"
        busy={busy}
      />
    </>
  );
}

export function ProjectBrand({
  projectId,
  current,
  kits,
}: {
  projectId: string;
  current?: Partial<BrandConfig>;
  kits: BrandKit[];
}) {
  const [selected, setSelected] = useState(current?.id ?? "");
  const [existing, setExisting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();
  async function apply() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api(`/projects/${projectId}/brand`, {
        method: "PUT",
        body: JSON.stringify({
          kit_id: selected || null,
          include_existing: existing,
        }),
      });
      router.refresh();
      setMessage("Project branding saved. Render clips to see the changes.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not apply brand kit");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>Project branding</h2>
      <p>
        {current?.name ? `Applied: ${current.name}.` : "No brand kit applied."}{" "}
        Projects keep a copy of applied settings and logos.
      </p>
      <label className="field">
        Brand kit
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">No brand kit</option>
          {current?.id && !kits.some((kit) => kit.id === current.id) && (
            <option value={current.id} disabled>
              {current.name} (deleted kit; saved copy retained)
            </option>
          )}
          {kits.map((kit) => (
            <option key={kit.id} value={kit.id}>
              {kit.name}
            </option>
          ))}
        </select>
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={existing}
          onChange={(e) => setExisting(e.target.checked)}
        />
        Also update existing clips (re-render required)
      </label>
      <p className="muted">
        Applying replaces caption appearance and branding. Edited caption text
        is kept. Removing a kit clears its logo; existing caption and text
        styling stays editable.
      </p>
      <div className="actions">
        <button
          className="button secondary"
          disabled={
            busy || (!!selected && !kits.some((kit) => kit.id === selected))
          }
          onClick={apply}
        >
          {busy ? "Applying…" : "Apply brand kit"}
        </button>
        <a href="/brand-kit">Manage brand kits</a>
      </div>
      <p role="status">{message}</p>
      <div className="form-error" role="alert">
        {error}
      </div>
    </section>
  );
}

function BrandLogo({ kit, file }: { kit?: BrandKit; file?: File | null }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let active = true;
    if (file) {
      const next = URL.createObjectURL(file);
      const timer = requestAnimationFrame(() => setUrl(next));
      return () => {
        cancelAnimationFrame(timer);
        URL.revokeObjectURL(next);
      };
    }
    if (kit?.has_logo)
      api<{ url: string }>(`/brand-kits/${kit.id}/logo`)
        .then((result) => {
          if (active) setUrl(result.url);
        })
        .catch(() => {});
    return () => {
      active = false;
    };
  }, [kit?.id, kit?.has_logo, file]);
  return url ? (
    <Image
      unoptimized
      src={url}
      alt={kit?.name ? `${kit.name} logo` : "Your logo preview"}
      width={100}
      height={100}
    />
  ) : (
    <span className="studio-brand-monogram">
      {kit?.name?.slice(0, 2).toUpperCase() || "Aa"}
    </span>
  );
}
