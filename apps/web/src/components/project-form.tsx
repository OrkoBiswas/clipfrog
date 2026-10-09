"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useForm, useWatch, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowLeft,
  ArrowRight,
  Captions,
  Check,
  CheckCircle2,
  Clapperboard,
  Gamepad2,
  GraduationCap,
  Layers3,
  LoaderCircle,
  Mic2,
  MonitorPlay,
  Palette,
  Presentation,
  Scissors,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  UsersRound,
  Video,
} from "lucide-react";
import { api, type Project } from "@/lib/api";
import { automaticFraming } from "@/lib/split-screen";
import { projectSchema, type ProjectFormValues } from "@/lib/validation";
import platforms from "../../../../packages/shared/platforms.json";
import { CaptionStudio } from "./basic-caption-studio";
import { SourceUpload } from "./source-upload";
import { Toggle } from "./ui/primitives";
import { useToast } from "./ui/toast";
import type { BrandKit } from "./brand-kits";
import type { CaptionStyle, FramingStyle } from "@/lib/editor-types";
import "./project-experience.css";

const contentTypes = [
  { name: "Podcast", icon: Mic2, description: "Conversations worth sharing" },
  {
    name: "Interview",
    icon: UsersRound,
    description: "Questions. Answers. Insights.",
  },
  {
    name: "Talking Head",
    icon: Video,
    description: "One voice, a clear message",
  },
  {
    name: "Tutorial",
    icon: GraduationCap,
    description: "Teach something useful",
  },
  {
    name: "Gaming",
    icon: Gamepad2,
    description: "Highlights from your session",
  },
  {
    name: "Webinar",
    icon: MonitorPlay,
    description: "Your best live takeaways",
  },
  {
    name: "Presentation",
    icon: Presentation,
    description: "Ideas that deserve attention",
  },
  {
    name: "Other",
    icon: Clapperboard,
    description: "Something a little different",
  },
  { name: "Auto", icon: Sparkles, description: "Let analysis find the format" },
] as const;
const steps = [
  { label: "Upload", icon: UploadCloud },
  { label: "Video details", icon: Video },
  { label: "Clip options", icon: Scissors },
  { label: "Captions & brand", icon: Palette },
  { label: "Review", icon: CheckCircle2 },
];
const headings = [
  "Upload your original video",
  "Name your project and describe the video",
  "Choose the clips you want to create",
  "Choose captions and your brand",
  "Everything look right?",
];
const descriptions = [
  "Choose a video from your device. You can also finish setup now and upload later.",
  "Choose Auto if you want highlight ranking to adapt to the video. Set the spoken language or let us detect it.",
  "Set the maximum number of highlights, their length, and the video formats. You can edit each clip later.",
  "Turn subtitles on or off and choose their appearance. Adding a brand kit is optional.",
  "Check your choices, then open the project to analyze your video and find highlights.",
];

export function ProjectForm({
  project,
  onSaved,
}: {
  project?: Project;
  onSaved?: () => void;
}) {
  const router = useRouter();
  const { toast } = useToast();
  const [error, setError] = useState("");
  const [step, setStep] = useState(project ? 1 : 0);
  const [furthest, setFurthest] = useState(project ? 4 : 0);
  const [draft, setDraft] = useState<Project | null>(null);
  const draftRef = useRef<Project | null>(null);
  const [finished, setFinished] = useState<Project | null>(null);
  const [uploaded, setUploaded] = useState(!!project?.source_asset_id);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [sourceName, setSourceName] = useState("");
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [brand, setBrand] = useState(
    project?.processing_config.brand_kit_id ?? "",
  );
  const [platform, setPlatform] = useState(
    project?.processing_config.platform_preset ?? "Custom",
  );
  const [captions, setCaptions] = useState<CaptionStyle>(
    project?.processing_config.caption_config ??
      project?.brand_config.captions ?? { enabled: true, style: "Clean" },
  );
  const [framing, setFraming] = useState<FramingStyle>(
    automaticFraming(project?.processing_config.render_config ?? {
      layout: "single",
      quality: project?.processing_config.quality ?? "Standard",
      crop_mode: project?.processing_config.crop_mode ?? "STATIC_SUBJECT_LOCK",
    }),
  );
  const [usage, setUsage] = useState<{
    allowance: Record<string, number | null>;
    usage: Record<string, number>;
  } | null>(null);
  const errorSummary = useRef<HTMLDivElement>(null);
  const stepHeading = useRef<HTMLHeadingElement>(null);
  const {
    register,
    handleSubmit,
    control,
    trigger,
    setValue,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<ProjectFormValues>({
    resolver: zodResolver(projectSchema),
    mode: "onBlur",
    defaultValues: {
      name: project?.name ?? "",
      content_type:
        (project?.content_type as ProjectFormValues["content_type"]) ??
        "Auto",
      language: project?.language ?? "auto",
      clip_count: project?.processing_config.clip_count ?? 10,
      duration_min: project?.processing_config.duration_min ?? 20,
      duration_max: project?.processing_config.duration_max ?? 35,
      ratios: project?.processing_config.ratios ?? ["9:16"],
      captions: project?.processing_config.captions ?? true,
      keywords: project?.processing_config.keywords?.join(", ") ?? "",
      minimum_score: project?.processing_config.minimum_score ?? 35,
      minimum_separation: project?.processing_config.minimum_separation ?? 0,
      max_overlap: project?.processing_config.max_overlap ?? 0,
      semantic_ranking: false,
    },
  });
  const values = useWatch({ control }) as ProjectFormValues;
  useEffect(() => {
    let active = true;
    void Promise.allSettled([
      api<BrandKit[]>("/brand-kits"),
      api<{
        allowance: Record<string, number | null>;
        usage: Record<string, number>;
      }>("/usage"),
    ]).then(([kitResult, usageResult]) => {
      if (!active) return;
      if (kitResult.status === "fulfilled") setKits(kitResult.value);
      if (usageResult.status === "fulfilled") setUsage(usageResult.value);
      if (kitResult.status === "rejected")
        setError(
          "Brand kits could not be loaded. You can continue without one, or refresh to try again.",
        );
    });
    return () => {
      active = false;
    };
  }, []);
  function body(value: ProjectFormValues) {
    return {
      name: value.name,
      content_type: value.content_type,
      language: value.language,
      processing_config: {
        ...project?.processing_config,
        brand_kit_id: brand || null,
        caption_config: { ...captions, enabled: value.captions },
        render_config: framing,
        platform_preset: platform,
        clip_count: value.clip_count,
        duration_min: value.duration_min,
        duration_max: value.duration_max,
        ratios: value.ratios,
        captions: value.captions,
        keywords:
          value.keywords
            ?.split(",")
            .map((word) => word.trim())
            .filter(Boolean) ?? [],
        minimum_score: value.minimum_score,
        minimum_separation: value.minimum_separation,
        max_overlap: value.max_overlap,
        semantic_ranking: value.semantic_ranking,
      },
    };
  }
  async function createDraft() {
    if (draftRef.current) return draftRef.current;
    const valid = await trigger("name");
    if (!valid) throw new Error("Give your project a name before uploading.");
    const result = await api<Project>("/projects", {
      method: "POST",
      body: JSON.stringify(body(getValues())),
    });
    draftRef.current = result;
    setDraft(result);
    return result;
  }
  function navigate(next: number) {
    setStep(next);
    setFurthest((current) => Math.max(current, next));
    requestAnimationFrame(() =>
      stepHeading.current?.focus({ preventScroll: true }),
    );
  }
  async function next() {
    const fields: FieldPath<ProjectFormValues>[] =
      step === 1
        ? ["name", "content_type", "language"]
        : step === 2
          ? [
              "clip_count",
              "duration_min",
              "duration_max",
              "ratios",
              "minimum_score",
              "minimum_separation",
              "max_overlap",
              "keywords",
            ]
          : [];
    if (await trigger(fields)) navigate(step + 1);
    else requestAnimationFrame(() => errorSummary.current?.focus());
  }
  async function save(value: ProjectFormValues) {
    setError("");
    try {
      const existing = project ?? draftRef.current;
      const result = await api<Project>(
        existing ? `/projects/${existing.id}` : "/projects",
        {
          method: existing ? "PUT" : "POST",
          body: JSON.stringify(body(value)),
        },
      );
      toast(
        project ? "Project settings saved" : "Your project is ready",
        "Everything is saved in your workspace.",
        "success",
      );
      if (project) {
        router.refresh();
        onSaved?.();
      } else {
        setFinished(result);
      }
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not save project. Please try again.",
      );
      requestAnimationFrame(() => errorSummary.current?.focus());
    }
  }
  const renderMinimum = (
    (values.clip_count * values.duration_min * values.ratios.length) /
    60
  ).toFixed(1);
  const renderMaximum = (
    (values.clip_count * values.duration_max * values.ratios.length) /
    60
  ).toFixed(1);
  if (finished)
    return (
      <section className="panel px-wizard-success">
        <span className="px-success-orbit">
          <CheckCircle2 size={42} aria-hidden="true" />
        </span>
        <p className="eyebrow">ALL SET</p>
        <h2>Project setup complete</h2>
        <p>
          <strong>{finished.name}</strong> is ready.{" "}
          {uploaded
            ? "Open your project to analyze your video and discover its best moments."
            : "Add your source video in the project workspace when you’re ready."}
        </p>
        <div className="actions">
          <Link className="button primary" href={`/projects/${finished.id}`}>
            Open project <ArrowRight size={17} aria-hidden="true" />
          </Link>
          <Link className="button secondary" href="/projects">
            All projects
          </Link>
        </div>
      </section>
    );
  return (
    <section className="panel px-wizard">
      <nav className="px-steps" aria-label="Project setup progress">
        {steps.map(({ label, icon: Icon }, index) => (
          <button
            type="button"
            key={label}
            className={`px-step ${step === index ? "is-active" : ""} ${index < step ? "is-complete" : ""}`}
            disabled={uploadBusy || (project ? index === 0 : index > furthest)}
            onClick={() => navigate(index)}
            aria-current={step === index ? "step" : undefined}
          >
            <span className="px-step-number">
              {index < step ? (
                <Check size={16} aria-hidden="true" />
              ) : (
                <Icon size={17} aria-hidden="true" />
              )}
            </span>
            <span>
              <small>STEP {index + 1}</small>
              {label}
            </span>
          </button>
        ))}
      </nav>
      <form
        onSubmit={(event) => {
          void handleSubmit(save, () => {
            requestAnimationFrame(() => errorSummary.current?.focus());
          })(event);
        }}
        noValidate
      >
        <div className="px-wizard-layout">
          <div className="px-wizard-main">
            <div className="px-step-heading">
              <p className="eyebrow">Setup step {step + 1} of {steps.length} · {steps[step].label}</p>
              <h2 ref={stepHeading} tabIndex={-1}>
                {headings[step]}
              </h2>
              <p>{descriptions[step]}</p>
            </div>
            {(error || Object.keys(errors).length > 0) && (
              <div
                ref={errorSummary}
                className="form-error px-error-summary"
                role="alert"
                tabIndex={-1}
              >
                <strong>A quick check before we continue</strong>
                {error && <p>{error}</p>}
                {Object.entries(errors).map(([name, fieldError]) => (
                  <p key={name}>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => {
                        navigate(
                          ["name", "content_type", "language"].includes(name)
                            ? 1
                            : 2,
                        );
                        requestAnimationFrame(() =>
                          document.getElementById(`project-${name}`)?.focus(),
                        );
                      }}
                    >
                      {fieldError.message}
                    </button>
                  </p>
                ))}
              </div>
            )}
            {!project && (
              <div hidden={step !== 0}>
                <SourceUpload
                  wizard
                  projectId={draft?.id}
                  createProject={createDraft}
                  onFileSelected={(file) => {
                    setSourceName(file.name);
                    if (!getValues("name"))
                      setValue(
                        "name",
                        file.name.replace(/\.[^.]+$/, "").slice(0, 160),
                      );
                  }}
                  onComplete={() => setUploaded(true)}
                  onBusyChange={setUploadBusy}
                />
                {sourceName && step === 0 && (
                  <label className="field px-upload-name">
                    Project name
                    <input
                      id="project-upload-name"
                      value={values.name}
                      maxLength={160}
                      onChange={(event) =>
                        setValue("name", event.target.value, {
                          shouldValidate: true,
                        })
                      }
                    />
                  </label>
                )}
              </div>
            )}
            {step === 1 && (
              <div className="px-step-body">
                <label className="field">
                  Project name
                  <input
                    id="project-name"
                    {...register("name")}
                    maxLength={160}
                    placeholder="e.g. The creative process — Episode 12"
                    aria-invalid={!!errors.name}
                    aria-describedby={
                      errors.name ? "project-name-error" : undefined
                    }
                  />
                  {errors.name && (
                    <span id="project-name-error" className="form-error">
                      {errors.name.message}
                    </span>
                  )}
                </label>
                <fieldset className="px-fieldset">
                  <legend>What kind of video is this?</legend>
                  <div className="px-content-grid">
                    {contentTypes.map(({ name, icon: Icon, description }) => (
                      <label
                        className={`px-content-card ${values.content_type === name ? "is-selected" : ""}`}
                        key={name}
                      >
                        <input
                          type="radio"
                          value={name}
                          {...register("content_type")}
                        />
                        <span className="px-content-icon">
                          <Icon
                            size={21}
                            strokeWidth={1.7}
                            aria-hidden="true"
                          />
                        </span>
                        <strong>{name}</strong>
                        <small>{description}</small>
                        {values.content_type === name && (
                          <CheckCircle2
                            className="px-selection-check"
                            size={16}
                            aria-hidden="true"
                          />
                        )}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <label className="field">
                  Spoken language
                  <select id="project-language" {...register("language")}>
                    <option value="auto">Detect automatically</option>
                    {[
                      ["en", "English"],
                      ["bn", "Bengali"],
                      ["es", "Spanish"],
                      ["hi", "Hindi"],
                      ["ar", "Arabic"],
                      ["fr", "French"],
                      ["de", "German"],
                    ].map(([code, label]) => (
                      <option value={code} key={code}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <small className="muted">
                    Choose the language spoken in your source video.
                  </small>
                </label>
              </div>
            )}
            {step === 2 && (
              <div className="px-step-body">
                <div className="px-control-group">
                  <div className="px-control-title">
                    <h3>Number of clips</h3>
                    <span className="muted">Maximum highlights to find</span>
                  </div>
                  <div
                    className="px-chips"
                    role="group"
                    aria-label="Number of clips"
                  >
                    {[5, 10, 20, 30, 50, 75, 100].map((count) => (
                      <button
                        type="button"
                        className={`px-chip ${values.clip_count === count ? "is-selected" : ""}`}
                        aria-pressed={values.clip_count === count}
                        onClick={() =>
                          setValue("clip_count", count, {
                            shouldValidate: true,
                          })
                        }
                        key={count}
                      >
                        {count}
                      </button>
                    ))}
                    <label className="px-custom-number">
                      Custom
                      <input
                        id="project-clip_count"
                        type="number"
                        min={1}
                        max={100}
                        aria-label="Custom number of clips"
                        {...register("clip_count", { valueAsNumber: true })}
                      />
                    </label>
                  </div>
                  {errors.clip_count && (
                    <p className="form-error">{errors.clip_count.message}</p>
                  )}
                </div>
                <div className="px-control-group">
                  <div className="px-control-title">
                    <h3>Clip duration</h3>
                    <span className="muted">Keep the complete idea</span>
                  </div>
                  <div
                    className="px-chips"
                    role="group"
                    aria-label="Clip duration"
                  >
                    {[15, 30, 45, 60].map((duration) => (
                      <button
                        type="button"
                        className={`px-chip ${values.duration_min === duration && values.duration_max === duration ? "is-selected" : ""}`}
                        aria-pressed={
                          values.duration_min === duration &&
                          values.duration_max === duration
                        }
                        onClick={() => {
                          setValue("duration_min", duration);
                          setValue("duration_max", duration, {
                            shouldValidate: true,
                          });
                        }}
                        key={duration}
                      >
                        {duration} sec
                      </button>
                    ))}
                    <button
                      type="button"
                      className={`px-chip ${values.duration_min === 20 && values.duration_max === 60 ? "is-selected" : ""}`}
                      aria-pressed={
                        values.duration_min === 20 && values.duration_max === 60
                      }
                      onClick={() => {
                        setValue("duration_min", 20);
                        setValue("duration_max", 60);
                      }}
                    >
                      Flexible · 20–60s
                    </button>
                  </div>
                  <div className="form-grid px-duration-fields">
                    <label className="field">
                      Minimum duration (seconds)
                      <input
                        id="project-duration_min"
                        type="number"
                        min={5}
                        max={180}
                        {...register("duration_min", { valueAsNumber: true })}
                        aria-invalid={!!errors.duration_min}
                      />
                    </label>
                    <label className="field">
                      Target maximum duration (seconds)
                      <input
                        id="project-duration_max"
                        type="number"
                        min={5}
                        max={180}
                        {...register("duration_max", { valueAsNumber: true })}
                        aria-invalid={!!errors.duration_max}
                      />
                    </label>
                  </div>
                  {(errors.duration_min || errors.duration_max) && (
                    <p className="form-error">
                      {errors.duration_min?.message ??
                        errors.duration_max?.message}
                    </p>
                  )}
                  <p className="muted">Clips can run a few seconds longer to finish a sentence. Endings follow natural pauses.</p>
                </div>
                <fieldset className="px-fieldset">
                  <legend>Choose video formats</legend>
                  <p className="muted">
                    Vertical 9:16 works for Shorts and Reels. Landscape 16:9 fits wider screens. Choose more than one to create a video in each format.
                  </p>
                  <div className="px-ratio-grid">
                    {[
                      "9:16",
                      "16:9",
                      "1:1",
                      "4:5",
                      "Original",
                      "3:4",
                      "4:3",
                      "21:9",
                    ].map((ratio) => (
                      <label
                        key={ratio}
                        className={`px-ratio-card ${values.ratios.includes(ratio) ? "is-selected" : ""}`}
                      >
                        <input
                          type="checkbox"
                          value={ratio}
                          {...register("ratios", {
                            onChange: () => setPlatform("Custom"),
                          })}
                        />
                        <span className="px-ratio-frame-area">
                          <span
                            className="px-ratio-frame"
                            style={{
                              aspectRatio:
                                ratio === "Original"
                                  ? "16/10"
                                  : ratio.replace(":", "/"),
                              width:
                                ratio === "9:16"
                                  ? 23
                                  : ratio === "3:4" || ratio === "4:5"
                                    ? 30
                                    : 42,
                            }}
                          />
                        </span>
                        <strong>{ratio}</strong>
                        <small>
                          {
                            {
                              "9:16": "Vertical",
                              "16:9": "Landscape",
                              "1:1": "Square",
                              "4:5": "Feed",
                              Original: "Source",
                              "3:4": "Portrait",
                              "4:3": "Classic",
                              "21:9": "Wide",
                            }[ratio]
                          }
                        </small>
                        {values.ratios.includes(ratio) && (
                          <CheckCircle2
                            className="px-selection-check"
                            size={13}
                            aria-hidden="true"
                          />
                        )}
                      </label>
                    ))}
                  </div>
                  {errors.ratios && (
                    <p id="project-ratios" className="form-error">
                      {errors.ratios.message}
                    </p>
                  )}
                </fieldset>
                <label className="field">
                  Quick setup for a platform
                  <select
                    value={platform}
                    onChange={(event) => {
                      const preset = platforms.find(
                        (item) => item.name === event.target.value,
                      )!;
                      setPlatform(preset.name);
                      if (preset.name !== "Custom") {
                        setValue("ratios", [preset.ratio]);
                        setValue(
                          "duration_max",
                          Math.min(values.duration_max, preset.maxDuration),
                        );
                        setValue(
                          "duration_min",
                          Math.min(values.duration_min, preset.maxDuration),
                        );
                      }
                    }}
                  >
                    {platforms.map((preset) => (
                      <option key={preset.name}>{preset.name}</option>
                    ))}
                  </select>
                </label>
                <details className="px-advanced">
                  <summary>
                    Advanced highlight search settings
                    <span className="muted">Optional</span>
                  </summary>
                  <div className="px-step-body">
                    <label className="field">
                      Topics or keywords
                      <input
                        id="project-keywords"
                        {...register("keywords")}
                        maxLength={500}
                        placeholder="e.g. creativity, leadership, practical advice"
                      />
                      <small className="muted">
                        Separate topics with commas.
                      </small>
                    </label>
                    <div className="form-grid">
                      <label className="field">
                        Minimum highlight score (0–100)
                        <input
                          id="project-minimum_score"
                          type="number"
                          min={0}
                          max={100}
                          {...register("minimum_score", {
                            valueAsNumber: true,
                          })}
                        />
                        <small className="muted">Higher values are more selective and may return fewer highlights.</small>
                      </label>
                      <label className="field">
                        Minimum separation (seconds)
                        <input
                          id="project-minimum_separation"
                          type="number"
                          min={0}
                          max={180}
                          {...register("minimum_separation", {
                            valueAsNumber: true,
                          })}
                        />
                        <small className="muted">The minimum gap between selected moments. Use 0 for no required gap.</small>
                      </label>
                      <label className="field">
                        Maximum overlap (0–1)
                        <input
                          id="project-max_overlap"
                          type="number"
                          min={0}
                          max={1}
                          step={0.1}
                          {...register("max_overlap", { valueAsNumber: true })}
                        />
                        <small className="muted">0 avoids shared footage; 1 allows moments to overlap completely.</small>
                      </label>
                    </div>
                    <p className="muted">
                      Highlight ranking and preference learning run locally. Rate good and poor
                      moments after analysis to improve future selections.
                    </p>
                  </div>
                </details>
              </div>
            )}
            {step === 3 && (
              <div className="px-step-body">
                <Toggle
                  checked={values.captions}
                  onChange={(checked) => {
                    setValue("captions", checked);
                    setCaptions({ ...captions, enabled: checked });
                  }}
                  label="Auto captions"
                  description="Burn readable, styled captions into your clips."
                />
                <label className="field">
                  Brand kit
                  <select
                    value={brand}
                    onChange={(event) => {
                      setBrand(event.target.value);
                      const kit = kits.find(
                        (item) => item.id === event.target.value,
                      );
                      if (kit) {
                        setCaptions(kit.config.captions);
                        setValue(
                          "captions",
                          kit.config.captions.enabled ?? true,
                        );
                      }
                    }}
                  >
                    <option value="">Start with a clean canvas</option>
                    {kits.map((kit) => (
                      <option value={kit.id} key={kit.id}>
                        {kit.name}
                      </option>
                    ))}
                  </select>
                  <small className="muted">
                    Your logo and caption styling will be copied to this
                    project.
                  </small>
                </label>
                <CaptionStudio
                  value={captions}
                  framing={framing}
                  onFramingChange={setFraming}
                  onChange={(value) => {
                    setCaptions(value);
                    setValue("captions", value.enabled ?? true);
                  }}
                />
                <p className="muted">Screen layout applies to new clips. To change an existing clip, open Edit clip and use Layout &amp; safe area.</p>
              </div>
            )}
            {step === 4 && (
              <div className="px-step-body">
                <div className="px-review-source">
                  <span className="px-content-icon">
                    <Video size={26} aria-hidden="true" />
                  </span>
                  <div>
                    <h3>{values.name}</h3>
                    <p className="muted">
                      {sourceName ||
                        (uploaded
                          ? "Source video attached"
                          : "Add your source video after setup")}
                    </p>
                  </div>
                  {uploaded && (
                    <CheckCircle2
                      className="px-success"
                      size={22}
                      aria-hidden="true"
                    />
                  )}
                </div>
                <dl className="px-review-grid">
                  {[
                    ["Content", values.content_type],
                    [
                      "Language",
                      values.language === "auto"
                        ? "Detect automatically"
                        : values.language.toUpperCase(),
                    ],
                    ["Clips requested", `${values.clip_count} clips`],
                    [
                      "Duration",
                      `${values.duration_min}–${values.duration_max} seconds`,
                    ],
                    ["Aspect ratios", values.ratios.join(" · ")],
                    ["Multiple screens", framing.layout === "auto" ? "Automatic collage" : "Off"],
                    ["Captions", values.captions ? captions.style : "Disabled"],
                    [
                      "Brand kit",
                      kits.find((kit) => kit.id === brand)?.name ??
                        "No brand kit",
                    ],
                    ["Platform", platform],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
                <div className="px-estimate">
                  <ClockLabel />
                  <div>
                    <strong>
                      {renderMinimum}–{renderMaximum} render minutes
                    </strong>
                    <p>
                      Estimated across {values.ratios.length} output{" "}
                      {values.ratios.length === 1 ? "format" : "formats"}.
                      Actual usage depends on your selected moments and
                      re-renders.
                    </p>
                  </div>
                </div>
                {usage && (
                  <p className="muted">
                    {usage.allowance.render_minutes === null
                      ? "Your plan includes unlimited render minutes."
                      : `${Math.max(0, (usage.allowance.render_minutes ?? 0) - (usage.usage.render_minutes ?? 0)).toFixed(1)} render minutes remaining this month.`}{" "}
                    {usage.allowance.input_minutes === null
                      ? "Input minutes are unlimited."
                      : `${Math.max(0, (usage.allowance.input_minutes ?? 0) - (usage.usage.input_minutes ?? 0)).toFixed(1)} input minutes remaining.`}
                  </p>
                )}
                <p className="muted">
                  The final number of clips depends on how many complete,
                  distinct moments your video contains.
                </p>
                <div className="px-step-confirmation">
                  <strong>What happens next?</strong>
                  <p>{uploaded ? "Open your project and analyze the video." : "Open your project, upload a video, then analyze it."} Find and preview highlights, then render your selected moments into downloadable clips.</p>
                </div>
              </div>
            )}
          </div>
          <aside className="px-wizard-aside">
            <div className="px-aside-visual" aria-hidden="true">
              <Image
                src="/images/creator-studio.png"
                alt=""
                fill
                sizes="220px"
                className="px-aside-photo"
              />
              <span className="px-aside-preview-label">Style preview</span>
              <div className="px-aside-caption">
                Good stories.
                <br />
                <strong>Great moments.</strong>
              </div>
            </div>
            <p className="eyebrow">YOUR PROJECT, AT A GLANCE</p>
            <dl className="px-aside-summary">
              <div>
                <dt>
                  <Layers3 size={15} aria-hidden="true" /> Output
                </dt>
                <dd>{values.clip_count} clips</dd>
              </div>
              <div>
                <dt>
                  <Video size={15} aria-hidden="true" /> Format
                </dt>
                <dd>
                  {values.ratios.length
                    ? values.ratios.join(", ")
                    : "Choose a ratio"}
                </dd>
              </div>
              <div>
                <dt>
                  <Captions size={15} aria-hidden="true" /> Captions
                </dt>
                <dd>{values.captions ? "Enabled" : "Disabled"}</dd>
              </div>
            </dl>
            <div className="px-aside-tip">
              <ShieldCheck size={19} aria-hidden="true" />
              <p>
                {step === 0
                  ? "Your videos stay private. Only you and your workspace can access them."
                  : values.content_type === "Podcast"
                    ? "Podcast framing keeps the speaker steady, without chasing small head movements."
                    : "You stay in control. Refine your captions, framing, and timing in the editor."}
              </p>
            </div>
          </aside>
        </div>
        <footer className="px-wizard-footer">
          <div>
            {step > (project ? 1 : 0) ? (
              <button
                type="button"
                className="button secondary"
                onClick={() => navigate(step - 1)}
                disabled={uploadBusy || isSubmitting}
              >
                <ArrowLeft size={16} aria-hidden="true" /> Back
              </button>
            ) : (
              <Link className="text-button" href="/projects">
                Cancel setup
              </Link>
            )}
          </div>
          <div className="actions">
            {step < 4 && <span className="px-continue-hint">Next: {steps[step + 1].label}</span>}
            {step === 0 && !uploaded && (
              <button
                type="button"
                className="text-button"
                disabled={uploadBusy}
                onClick={() => navigate(1)}
              >
                Set up first, upload later
              </button>
            )}
            {step < 4 ? (
              <button
                type="button"
                className="button primary"
                disabled={uploadBusy || (step === 0 && !uploaded)}
                key="continue"
                onClick={(event) => {
                  event.preventDefault();
                  void next();
                }}
              >
                Continue <ArrowRight size={17} aria-hidden="true" />
              </button>
            ) : (
              <button
                key="submit"
                type="submit"
                className="button primary"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <LoaderCircle
                    size={17}
                    className="px-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <CheckCircle2 size={17} aria-hidden="true" />
                )}
                {isSubmitting
                  ? "Saving…"
                  : project
                    ? "Save changes"
                    : "Create project"}
              </button>
            )}
          </div>
        </footer>
      </form>
    </section>
  );
}
function ClockLabel() {
  return (
    <span className="px-content-icon">
      <Scissors size={22} aria-hidden="true" />
    </span>
  );
}
