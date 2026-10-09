"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import {
  Clapperboard,
  Copy,
  Download,
  Film,
  LayoutGrid,
  List,
  MoreHorizontal,
  Play,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { api, API_URL, type Config } from "@/lib/api";
import { automaticFraming } from "@/lib/split-screen";
import type { BrandConfig } from "@/components/brand-kits";
import type {
  CaptionStyle,
  OverlayStyle,
  FramingStyle,
} from "@/lib/editor-types";
import {
  ConfirmDialog,
  Skeleton,
  StatusBadge,
} from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { timecode } from "./studio-controls";
import "./studio.css";

const EditorDialog = dynamic(
  () => import("./clip-editor").then((module) => module.EditorDialog),
  {
    loading: () => (
      <div role="status" className="notice">
        Opening your editor...
      </div>
    ),
  },
);

export type Clip = {
  id: string;
  title: string;
  start_ms: number;
  end_ms: number;
  aspect_ratio: string;
  status: string;
  revision: number;
  rendered_revision: number | null;
  output_asset_id: string | null;
  highlight_score?: number | null;
  caption_config: CaptionStyle;
  overlay_config: OverlayStyle;
  render_config: FramingStyle;
};
const ratios = ["9:16", "16:9", "1:1", "4:5", "3:4", "4:3", "21:9", "Original"];
const lockedStatuses = [
  "ANALYZING",
  "FINDING_HIGHLIGHTS",
  "RENDERING",
  "EXPORTING",
  "VALIDATING",
  "CANCEL_REQUESTED",
  "DELETING",
];

export function ClipsPanel({
  projectId,
  status,
  brand,
  processingConfig,
}: {
  projectId: string;
  status: string;
  brand?: Partial<BrandConfig>;
  processingConfig?: Config;
}) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [manual, setManual] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [archive, setArchive] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [acting, setActing] = useState(false);
  const [bulkRatio, setBulkRatio] = useState("9:16");
  const [confirmDelete, setConfirmDelete] = useState<string[]>([]);
  const [view, setView] = useState("grid");
  const router = useRouter();
  const { toast } = useToast();
  const locked = lockedStatuses.includes(status);
  async function refresh() {
    setClips(await api<Clip[]>(`/projects/${projectId}/clips`));
  }
  async function act(action: string, ids = selected, extra = {}) {
    setActing(true);
    setError("");
    try {
      await api(`/projects/${projectId}/clip-actions`, {
        method: "POST",
        body: JSON.stringify({ action, clip_ids: ids, ...extra }),
      });
      await refresh();
      setSelected([]);
      setConfirmDelete([]);
      router.refresh();
      toast(
        action === "render"
          ? "Rendering started"
          : action === "delete"
            ? "Clips deleted"
            : action === "duplicate"
              ? "Clips duplicated"
              : "Clip settings updated",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Clip action failed");
    } finally {
      setActing(false);
    }
  }
  async function exportClips() {
    setExporting(true);
    setError("");
    setArchive("");
    try {
      const task = await api<{ job_id: string }>(
        `/projects/${projectId}/export`,
        { method: "POST" },
      );
      router.refresh();
      for (let attempt = 0; attempt < 900; attempt++) {
        const jobs = await api<
          { id: string; status: string; error_message: string | null }[]
        >(`/projects/${projectId}/jobs`);
        const job = jobs.find((item) => item.id === task.job_id);
        if (job?.status === "SUCCEEDED") {
          const result = await api<{ url: string }>(
            `/projects/${projectId}/export/${task.job_id}`,
          );
          setArchive(result.url);
          toast("Your ZIP is ready", "Download the rendered clips below.");
          return;
        }
        if (job && ["FAILED", "CANCELED"].includes(job.status))
          throw new Error(job.error_message ?? "Export canceled");
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      throw new Error("Export is still running. Check processing status.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not export clips");
    } finally {
      setExporting(false);
      router.refresh();
    }
  }
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const value = await api<Clip[]>(`/projects/${projectId}/clips`);
        if (active) {
          setClips(value);
          setLoaded(true);
        }
      } catch (e) {
        if (active) {
          setError(e instanceof Error ? e.message : "Could not load clips");
          setLoaded(true);
        }
      }
    };
    void poll();
    const timer = setInterval(poll, 4000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [projectId]);
  const draft: Clip = {
    id: "",
    title: "Manual clip",
    start_ms: 0,
    end_ms: 10000,
    aspect_ratio: brand?.ratios?.[0] ?? "9:16",
    status: "DRAFT",
    revision: 1,
    rendered_revision: null,
    output_asset_id: null,
    caption_config: processingConfig?.caption_config ?? brand?.captions ?? { enabled: true, style: "Clean" },
    overlay_config: brand?.overlay ?? {},
    render_config: automaticFraming(processingConfig?.render_config ?? {
      quality: processingConfig?.quality ?? "Standard",
      crop_mode: processingConfig?.crop_mode ?? "STATIC_SUBJECT_LOCK",
    }),
  };
  return (
    <section className="panel studio-results">
      <div className="section-head">
        <div>
          <p className="eyebrow">Step 4 of 4</p>
          <h2>
            Your clips <span className="studio-count">{clips.length}</span>
          </h2>
        </div>
        <button
          className="button secondary"
          disabled={locked}
          onClick={() => setManual(true)}
        >
          <Plus size={16} aria-hidden="true" />
          Create manual clip
        </button>
      </div>
      <p className="muted">Preview a clip, use Edit clip to change its timing, captions or framing, then download the finished MP4. Render again after editing to update the video.</p>
      {!loaded && (
        <div className="studio-clips-grid">
          {[1, 2, 3].map((n) => (
            <Skeleton key={n} className="studio-card-skeleton" />
          ))}
        </div>
      )}
      {loaded && !clips.length && (
        <div className="studio-empty">
          <Clapperboard size={32} aria-hidden="true" />
          <h3>Create your first clip</h3>
          <p>
            In step 3, preview your highlights and select Render clips. You can also choose your own start and end times with Create manual clip.
          </p>
          <a className="button" href="#highlights">Go to highlights</a>
        </div>
      )}
      {!!clips.length && (
        <>
          <div className="studio-library-toolbar">
            <label className="check">
              <input
                type="checkbox"
                checked={selected.length === clips.length}
                disabled={locked || acting}
                onChange={(e) =>
                  setSelected(
                    e.target.checked ? clips.map((clip) => clip.id) : [],
                  )
                }
              />
              {selected.length ? `${selected.length} selected` : "Select all"}
            </label>
            <div className="actions">
              {clips.some((clip) => clip.output_asset_id) && (
                <button
                  className="button secondary"
                  disabled={locked || exporting}
                  onClick={exportClips}
                >
                  <Download size={16} aria-hidden="true" />
                  {exporting ? "Preparing archive…" : "Export all MP4s as ZIP"}
                </button>
              )}
              {archive && (
                <a className="button" href={archive}>
                  Download ZIP
                </a>
              )}
              <ViewToggle value={view} onChange={setView} />
            </div>
          </div>
          {!!selected.length && (
            <fieldset className="studio-bulk" disabled={locked || acting}>
              <legend>Selected clips</legend>
              <div className="actions">
                <select
                  aria-label="Bulk aspect ratio"
                  value={bulkRatio}
                  onChange={(e) => setBulkRatio(e.target.value)}
                >
                  {ratios.map((ratio) => (
                    <option key={ratio}>{ratio}</option>
                  ))}
                </select>
                <button
                  className="button secondary"
                  type="button"
                  onClick={() =>
                    act("update", selected, { aspect_ratio: bulkRatio })
                  }
                >
                  Apply ratio
                </button>
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => act("render")}
                >
                  Render selected
                </button>
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => act("duplicate")}
                >
                  Duplicate selected
                </button>
                <button
                  className="button danger"
                  type="button"
                  onClick={() => setConfirmDelete(selected)}
                >
                  Delete selected
                </button>
              </div>
            </fieldset>
          )}
          <div
            className={`studio-clips-grid ${view === "list" ? "is-list" : ""}`}
          >
            {clips.map((clip) => (
              <ClipCard
                key={clip.id}
                clip={clip}
                projectId={projectId}
                locked={locked || acting}
                selected={selected.includes(clip.id)}
                onSelect={(checked) =>
                  setSelected(
                    checked
                      ? [...selected, clip.id]
                      : selected.filter((id) => id !== clip.id),
                  )
                }
                onDuplicate={() => act("duplicate", [clip.id])}
                onDelete={() => setConfirmDelete([clip.id])}
                onRender={() => act("render", [clip.id])}
                onSaved={refresh}
              />
            ))}
          </div>
        </>
      )}
      {manual && (
        <EditorDialog
          clip={draft}
          projectId={projectId}
          onClose={() => setManual(false)}
          onSaved={async () => {
            setManual(false);
            await refresh();
            router.refresh();
          }}
        />
      )}
      <ConfirmDialog
        open={confirmDelete.length > 0}
        onClose={() => setConfirmDelete([])}
        onConfirm={() => act("delete", confirmDelete)}
        busy={acting}
        title={`Delete ${confirmDelete.length} ${confirmDelete.length === 1 ? "clip" : "clips"}?`}
        description="Their rendered files will be deleted. Your source video will stay available."
        confirmLabel="Confirm delete clips"
      />
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
    </section>
  );
}

function ViewToggle({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="studio-view-toggle" role="group" aria-label="Clip layout">
      <button
        type="button"
        aria-label="Grid view"
        aria-pressed={value === "grid"}
        onClick={() => onChange("grid")}
      >
        <LayoutGrid size={17} aria-hidden="true" />
      </button>
      <button
        type="button"
        aria-label="List view"
        aria-pressed={value === "list"}
        onClick={() => onChange("list")}
      >
        <List size={17} aria-hidden="true" />
      </button>
    </div>
  );
}

export function ClipCard({
  clip,
  projectId,
  locked = false,
  projectName,
  selected,
  onSelect,
  onDuplicate,
  onDelete,
  onRender,
  onSaved,
}: {
  clip: Clip;
  projectId: string;
  locked?: boolean;
  projectName?: string;
  selected?: boolean;
  onSelect?: (checked: boolean) => void;
  onDuplicate?: () => void;
  onDelete?: () => void;
  onRender?: () => void;
  onSaved?: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [preview, setPreview] = useState("");
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");
  const [mediaBusy, setMediaBusy] = useState(false);
  const card = useRef<HTMLElement>(null);
  const router = useRouter();
  useEffect(() => {
    if (!clip.output_asset_id || !card.current) return;
    let active = true;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        api<{ url: string }>(`/projects/${projectId}/clips/${clip.id}/media`)
          .then((result) => {
            if (active) setPreview(result.url);
          })
          .catch(() => {});
      },
      { rootMargin: "120px" },
    );
    observer.observe(card.current);
    return () => {
      active = false;
      observer.disconnect();
    };
  }, [clip.id, clip.output_asset_id, clip.rendered_revision, projectId]);
  async function media(download: boolean) {
    setError("");
    setMediaBusy(true);
    try {
      const result = await api<{ url: string }>(
        `/projects/${projectId}/clips/${clip.id}/media?download=${download}`,
      );
      if (download) {
        const link = document.createElement("a");
        link.href = result.url;
        link.click();
      } else {
        setPreview(result.url);
        setPlaying(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open media");
    } finally {
      setMediaBusy(false);
    }
  }
  return (
    <article
      ref={card}
      className={`studio-clip-card ${selected ? "is-selected" : ""}`}
    >
      <div className="studio-clip-visual">
        {preview ? (
          <video
            src={`${preview}#t=0.1`}
            preload="metadata"
            muted={!playing}
            controls={playing}
            playsInline
            aria-label={`Preview ${clip.title}`}
          />
        ) : (
          <div className="studio-clip-placeholder">
            <Film size={30} aria-hidden="true" />
            <span>
              {clip.output_asset_id ? "Loading preview" : "Ready to render"}
            </span>
          </div>
        )}
        {onSelect && (
          <label className="studio-clip-select">
            <input
              type="checkbox"
              aria-label={`Select ${clip.title}`}
              checked={selected}
              disabled={locked}
              onChange={(event) => onSelect(event.target.checked)}
            />
          </label>
        )}
        {!playing && clip.output_asset_id && (
          <button
            className="studio-clip-play"
            aria-label={`Preview ${clip.title}`}
            disabled={mediaBusy}
            onClick={() => media(false)}
          >
            <Play size={20} aria-hidden="true" />
          </button>
        )}
        {!playing && (
          <span className="studio-duration">
            {timecode(clip.end_ms - clip.start_ms)}
          </span>
        )}
        {!playing && <span className="studio-ratio">{clip.aspect_ratio}</span>}
      </div>
      <div className="studio-clip-content">
        <div className="section-head">
          <StatusBadge status={clip.status} />
          {clip.highlight_score != null && (
            <span
              className="studio-score"
              title="Highlight score considers hook strength, completeness, information value and visual quality. It is a heuristic, not a prediction."
            >
              <span />
              {Math.round(clip.highlight_score)} <small>highlight score</small>
            </span>
          )}
        </div>
        <h3>{clip.title}</h3>
        <p className="studio-clip-meta">
          {projectName && (
            <Link href={`/projects/${projectId}`}>{projectName}</Link>
          )}
          <span>
            {timecode(clip.start_ms)}–{timecode(clip.end_ms)} in source
          </span>
        </p>
        {clip.rendered_revision !== null &&
          clip.rendered_revision !== clip.revision && (
            <p className="studio-revision">
              Edits saved · Render to update preview
            </p>
          )}
        <div className="studio-clip-actions">
          <button
            className="button secondary"
            disabled={locked}
            onClick={() => setEditing(true)}
          >
            <SlidersHorizontal size={15} aria-hidden="true" />
            Edit clip
          </button>
          {clip.output_asset_id && (
            <button
              className="studio-icon-button"
              title="Download MP4"
              aria-label={`Download ${clip.title} MP4`}
              disabled={mediaBusy}
              onClick={() => media(true)}
            >
              <Download size={17} aria-hidden="true" />
            </button>
          )}
          <details className="studio-overflow">
            <summary aria-label={`More actions for ${clip.title}`}>
              <MoreHorizontal size={19} aria-hidden="true" />
            </summary>
            <div className="studio-overflow-menu">
              <a
                href={`${API_URL}/api/v1/projects/${projectId}/clips/${clip.id}/subtitles`}
              >
                <Download size={15} aria-hidden="true" />
                Download SRT
              </a>
              {onRender && (
                <button type="button" disabled={locked} onClick={onRender}>
                  <Play size={15} aria-hidden="true" />
                  Render clip
                </button>
              )}
              {onDuplicate && (
                <button type="button" disabled={locked} onClick={onDuplicate}>
                  <Copy size={15} aria-hidden="true" />
                  Duplicate {clip.title}
                </button>
              )}
              {onDelete && (
                <button
                  className="studio-danger-text"
                  type="button"
                  disabled={locked}
                  onClick={onDelete}
                >
                  <Trash2 size={15} aria-hidden="true" />
                  Delete {clip.title}
                </button>
              )}
            </div>
          </details>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </div>
      {editing && (
        <EditorDialog
          clip={clip}
          projectId={projectId}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            setPlaying(false);
            onSaved?.();
            router.refresh();
          }}
        />
      )}
    </article>
  );
}

export function ClipsLibrary({
  groups,
}: {
  groups: {
    project: { id: string; name: string; status: string };
    clips: Clip[];
  }[];
}) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState("grid");
  const processing = groups.some(
    ({ project, clips }) =>
      lockedStatuses.includes(project.status) ||
      clips.some((clip) => ["QUEUED", "RENDERING"].includes(clip.status)),
  );
  useEffect(() => {
    if (!processing) return;
    const refresh = () => {
      if (!document.hidden) router.refresh();
    };
    const timer = setInterval(refresh, 4000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [processing, router]);
  const clips = groups.flatMap(({ project, clips }) =>
    clips.map((clip) => ({ clip, project })),
  );
  const filtered = clips.filter(
    ({ clip, project }) =>
      `${clip.title} ${project.name}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (filter === "all" ||
        (filter === "rendered"
          ? !!clip.output_asset_id
          : !clip.output_asset_id)),
  );
  return (
    <>
      <div className="studio-library-toolbar">
        <label className="studio-search">
          <Search size={17} aria-hidden="true" />
          <input
            aria-label="Search clips"
            placeholder="Search clips or projects…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div className="actions">
          <select
            aria-label="Filter clips"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="all">All clips ({clips.length})</option>
            <option value="rendered">Rendered</option>
            <option value="draft">Awaiting render</option>
          </select>
          <ViewToggle value={view} onChange={setView} />
        </div>
      </div>
      {!filtered.length ? (
        <div className="panel studio-empty">
          <Clapperboard size={36} aria-hidden="true" />
          <h2>
            {clips.length
              ? "No matching clips"
              : "Your next great clip starts here."}
          </h2>
          <p>
            {clips.length
              ? "Try a different title or project name."
              : "Turn a long video into moments worth sharing."}
          </p>
          {!clips.length && (
            <Link className="button" href="/projects/new">
              <Plus size={16} aria-hidden="true" />
              Create Project
            </Link>
          )}
        </div>
      ) : (
        <div
          className={`studio-clips-grid ${view === "list" ? "is-list" : ""}`}
        >
          {filtered.map(({ clip, project }) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              projectId={project.id}
              projectName={project.name}
              locked={lockedStatuses.includes(project.status)}
            />
          ))}
        </div>
      )}
    </>
  );
}
