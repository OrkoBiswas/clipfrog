"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  CheckCircle2,
  Clock3,
  FileVideo2,
  HardDrive,
  LoaderCircle,
  Pause,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react";
import { api, type Project } from "@/lib/api";
import { ConfirmDialog, StatusBadge } from "@/components/ui/primitives";
import "./project-experience.css";

type Upload = {
  id: string;
  part_size: number;
  filename?: string;
  size_bytes?: number;
  status?: string;
  parts?: { number: number; size: number }[];
};
type Job = {
  id: string;
  status: string;
  stage: string;
  progress: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
};
type Source = {
  filename: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
  codec: string | null;
};
function bytes(size: number) {
  return size >= 1024 ** 3
    ? `${(size / 1024 ** 3).toFixed(2)} GB`
    : `${(size / 1024 ** 2).toFixed(1)} MB`;
}
function uploadPart(
  url: string,
  data: Blob,
  onProgress: (sent: number) => void,
  signal: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    signal.addEventListener("abort", abort);
    xhr.open("PUT", url);
    xhr.upload.onprogress = (event) => onProgress(event.loaded);
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(
            new Error(
              "This part could not be uploaded. Retry to resume from your last completed part.",
            ),
          );
    xhr.onerror = () =>
      reject(new Error("Connection interrupted. Retry to resume your upload."));
    xhr.onabort = () =>
      reject(new Error("Upload paused. Your completed parts are saved."));
    xhr.onloadend = () => signal.removeEventListener("abort", abort);
    if (signal.aborted) {
      signal.removeEventListener("abort", abort);
      reject(new Error("Upload paused."));
    } else xhr.send(data);
  });
}
export function SourceUpload({
  projectId,
  projectStatus = "CREATED",
  createProject,
  onFileSelected,
  onComplete,
  onBusyChange,
  wizard = false,
}: {
  projectId?: string;
  projectStatus?: string;
  createProject?: () => Promise<Project>;
  onFileSelected?: (file: File) => void;
  onComplete?: () => void;
  onBusyChange?: (busy: boolean) => void;
  wizard?: boolean;
}) {
  const router = useRouter();
  const [createdId, setCreatedId] = useState<string>();
  const resolvedId = projectId ?? createdId;
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [percent, setPercent] = useState(0);
  const [speed, setSpeed] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [upload, setUpload] = useState<Upload | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [observedAt, setObservedAt] = useState(0);
  const [confirm, setConfirm] = useState<"upload" | Job | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const callbacks = useRef({ onComplete, onBusyChange });
  useEffect(() => {
    callbacks.current = { onComplete, onBusyChange };
  }, [onComplete, onBusyChange]);
  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    const frame = requestAnimationFrame(() => setPreview(url));
    return () => {
      cancelAnimationFrame(frame);
      URL.revokeObjectURL(url);
    };
  }, [file]);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!resolvedId) return;
    let active = true;
    const base = `/projects/${resolvedId}`;
    const storageKey = `clipforge-upload:${resolvedId}`;
    async function refresh() {
      try {
        const [media, work] = await Promise.all([
          api<Source | null>(`${base}/source`),
          api<Job[]>(`${base}/jobs`),
        ]);
        if (!active) return;
        setSource(media);
        setJobs(work);
        setObservedAt(Date.now());
        if (media) callbacks.current.onComplete?.();
        if (
          !wizard &&
          ["SUCCEEDED", "FAILED", "CANCELED"].includes(work[0]?.status ?? "") &&
          [
            "VALIDATING",
            "ANALYZING",
            "FINDING_HIGHLIGHTS",
            "RENDERING",
            "EXPORTING",
            "CANCEL_REQUESTED",
          ].includes(projectStatus)
        )
          router.refresh();
      } catch (e) {
        if (active)
          setError(
            e instanceof Error
              ? e.message
              : "Could not refresh upload status. Please refresh to retry.",
          );
      }
    }
    const saved = localStorage.getItem(storageKey);
    if (saved)
      void api<Upload>(`${base}/upload/${saved}`)
        .then((value) => {
          if (active && value.status === "UPLOADING") setUpload(value);
          else localStorage.removeItem(storageKey);
        })
        .catch(() => {
          if (active)
            setError(
              "Your saved upload could not be restored. Refresh to try again.",
            );
        });
    void refresh();
    const timer = setInterval(refresh, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [resolvedId, projectStatus, router, wizard]);
  function choose(candidate: File | null) {
    if (!candidate) return;
    if (!/\.(mp4|mov|mkv|webm|m4v)$/i.test(candidate.name)) {
      setError("Choose an MP4, MOV, MKV, WebM, or M4V video.");
      return;
    }
    if (candidate.size === 0) {
      setError("This file is empty. Choose a video with content.");
      return;
    }
    setFile(candidate);
    setError("");
    onFileSelected?.(candidate);
  }
  async function start() {
    if (!file || busy) return;
    setError("");
    setBusy(true);
    callbacks.current.onBusyChange?.(true);
    const aborter = new AbortController();
    controller.current = aborter;
    try {
      let id = resolvedId;
      if (!id && createProject) {
        const created = await createProject();
        id = created.id;
        setCreatedId(id);
      }
      if (!id) throw new Error("Create a project before uploading your video.");
      const base = `/projects/${id}`;
      const storageKey = `clipforge-upload:${id}`;
      let session = upload;
      if (!session) {
        session = await api<Upload>(`${base}/upload/initiate`, {
          method: "POST",
          body: JSON.stringify({
            filename: file.name,
            size_bytes: file.size,
            mime_type: file.type || "application/octet-stream",
          }),
        });
        setUpload(session);
        localStorage.setItem(storageKey, session.id);
      }
      const current = await api<Upload>(`${base}/upload/${session.id}`);
      if (current.filename !== file.name || current.size_bytes !== file.size)
        throw new Error(
          "Choose the same file to resume, or cancel this upload and start again.",
        );
      const completeParts = new Set(current.parts?.map((part) => part.number));
      let sent =
        current.parts?.reduce((total, part) => total + part.size, 0) ?? 0;
      const initialSent = sent;
      const startedAt = performance.now();
      setPercent(Math.round((sent / file.size) * 100));
      for (
        let number = 1;
        number <= Math.ceil(file.size / session.part_size);
        number++
      ) {
        if (aborter.signal.aborted)
          throw new Error("Upload paused. Your completed parts are saved.");
        if (completeParts.has(number)) continue;
        const { url } = await api<{ url: string }>(
          `${base}/upload/${session.id}/parts/${number}`,
          { method: "POST" },
        );
        const part = file.slice(
          (number - 1) * session.part_size,
          number * session.part_size,
        );
        await uploadPart(
          url,
          part,
          (count) => {
            const transferred = sent + count;
            const rate =
              (transferred - initialSent) /
              Math.max(0.1, (performance.now() - startedAt) / 1000);
            setPercent(Math.round((transferred / file.size) * 100));
            setSpeed(rate);
            setRemaining(rate > 0 ? (file.size - transferred) / rate : 0);
          },
          aborter.signal,
        );
        sent += part.size;
      }
      if (aborter.signal.aborted)
        throw new Error("Upload paused. Resume to finish.");
      await api(`${base}/upload/${session.id}/complete`, { method: "POST" });
      localStorage.removeItem(storageKey);
      setUpload(null);
      setUploaded(true);
      callbacks.current.onComplete?.();
      if (!wizard) router.refresh();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Upload failed. Please try again.",
      );
    } finally {
      setBusy(false);
      callbacks.current.onBusyChange?.(false);
    }
  }
  async function confirmAction() {
    if (!resolvedId || !confirm) return;
    setActionBusy(true);
    try {
      if (confirm === "upload") {
        controller.current?.abort();
        if (upload)
          await api(`/projects/${resolvedId}/upload/${upload.id}`, {
            method: "DELETE",
          });
        localStorage.removeItem(`clipforge-upload:${resolvedId}`);
        setUpload(null);
        setPercent(0);
        setError("");
      } else
        await api(`/projects/${resolvedId}/jobs/${confirm.id}/cancel`, {
          method: "POST",
        });
      setConfirm(null);
      router.refresh();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not cancel. Please try again.",
      );
    } finally {
      setActionBusy(false);
    }
  }
  async function retryJob(job: Job) {
    setActionBusy(true);
    setError("");
    try {
      await api(`/projects/${resolvedId}/jobs/${job.id}/retry`, {
        method: "POST",
      });
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not retry processing.");
    } finally {
      setActionBusy(false);
    }
  }
  const complete = !!source || uploaded;
  const job = jobs[0];
  const processing =
    job &&
    ["QUEUED", "RUNNING", "RETRYING", "CANCEL_REQUESTED"].includes(job.status);
  return (
    <section
      className={wizard ? "px-upload" : "panel px-upload"}
      aria-label="Source video"
    >
      {!wizard && (
        <div className="section-head">
          <div>
            <p className="eyebrow">01 / SOURCE</p>
            <h2>Your source video</h2>
          </div>
          {complete && (
            <span className="badge px-success">
              <CheckCircle2 size={14} aria-hidden="true" /> Upload complete
            </span>
          )}
        </div>
      )}
      {complete ? (
        <div className="px-file-complete">
          <div className="px-file-visual">
            {preview ? (
              <video
                src={preview}
                muted
                playsInline
                preload="metadata"
                aria-label="Source video preview"
              />
            ) : (
              <FileVideo2 size={36} aria-hidden="true" />
            )}
            <span>
              <Check size={16} aria-hidden="true" />
            </span>
          </div>
          <div>
            <h3>{source?.filename ?? file?.name ?? "Source video uploaded"}</h3>
            <p className="muted">
              {bytes(source?.size_bytes ?? file?.size ?? 0)}
              {source?.width
                ? ` · ${source.width} × ${source.height} · ${((source.duration_ms ?? 0) / 1000).toFixed(1)} seconds · ${source.codec}`
                : " · Checking your video"}
            </p>
            {wizard && (
              <span className="px-success">
                <CheckCircle2 size={16} aria-hidden="true" /> Upload complete.
                Your video is safely in your project.
              </span>
            )}
          </div>
        </div>
      ) : (
        <>
          <div
            className={`px-dropzone ${dragging ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              if (!busy) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              if (!busy) choose(event.dataTransfer.files[0] ?? null);
            }}
          >
            {file ? (
              <div className="px-selected-file">
                <div className="px-upload-preview">
                  {preview ? (
                    <video
                      src={preview}
                      preload="metadata"
                      muted
                      playsInline
                      aria-label="Selected video preview"
                    />
                  ) : (
                    <FileVideo2 size={40} aria-hidden="true" />
                  )}
                </div>
                <h3>{file.name}</h3>
                <p className="muted">{bytes(file.size)} · Ready to upload</p>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => input.current?.click()}
                  disabled={busy || !!upload}
                >
                  Choose another video
                </button>
              </div>
            ) : (
              <>
                <span className="px-upload-icon">
                  <UploadCloud size={28} strokeWidth={1.7} aria-hidden="true" />
                </span>
                <h3>Big ideas start with a video.</h3>
                <p>Drag and drop your video here, or choose a file.</p>
                <button
                  type="button"
                  className="button primary"
                  onClick={() => input.current?.click()}
                >
                  <UploadCloud size={17} aria-hidden="true" /> Choose a video
                </button>
                <small>MP4, MOV, MKV, WebM, M4V</small>
              </>
            )}
            <input
              ref={input}
              className="px-file-input"
              type="file"
              aria-label="Choose source video"
              accept=".mp4,.mov,.mkv,.webm,.m4v"
              disabled={busy}
              onChange={(event) => choose(event.target.files?.[0] ?? null)}
            />
          </div>
          {upload?.filename && !busy && (
            <div className="notice">
              <RefreshCw size={16} aria-hidden="true" /> Saved upload:{" "}
              <strong>{upload.filename}</strong>. Choose the same file to pick
              up where you left off.
            </div>
          )}
          {(busy || percent > 0) && (
            <div className="px-upload-progress" role="status">
              <div className="px-progress-label">
                <strong>
                  {busy
                    ? percent === 100
                      ? "Finishing upload"
                      : "Uploading your video"
                    : "Upload paused"}
                </strong>
                <span>{percent}%</span>
              </div>
              <progress
                value={percent}
                max={100}
                aria-label="Upload progress"
              />
              <div className="px-progress-label muted">
                <span>
                  {speed > 0 && busy
                    ? `${bytes(speed)}/s`
                    : "Completed parts are saved"}
                </span>
                {busy && speed > 0 && percent < 100 && (
                  <span>
                    About{" "}
                    {remaining > 60
                      ? `${Math.ceil(remaining / 60)} min`
                      : `${Math.ceil(remaining)} sec`}{" "}
                    remaining
                  </span>
                )}
              </div>
            </div>
          )}
          {(file || upload) && (
            <div className="actions px-upload-actions">
              {busy ? (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => controller.current?.abort()}
                >
                  <Pause size={16} aria-hidden="true" /> Pause upload
                </button>
              ) : (
                <button
                  type="button"
                  className="button primary"
                  disabled={!file || actionBusy}
                  onClick={start}
                >
                  <UploadCloud size={16} aria-hidden="true" />
                  {upload ? "Resume upload" : "Upload video"}
                </button>
              )}
              {upload && (
                <button
                  type="button"
                  className="button secondary"
                  disabled={actionBusy}
                  onClick={() => setConfirm("upload")}
                >
                  <X size={16} aria-hidden="true" /> Cancel upload
                </button>
              )}
            </div>
          )}
          <div className="px-upload-assurances">
            <span>
              <ShieldCheck size={15} aria-hidden="true" /> Private by default
            </span>
            <span>
              <HardDrive size={15} aria-hidden="true" /> Resumable uploads
            </span>
            <span>
              <Clock3 size={15} aria-hidden="true" /> Original quality preserved
            </span>
          </div>
        </>
      )}
      {!wizard && job && (
        <div className="px-processing" aria-label="Processing activity">
          <div className="section-head">
            <div className="px-processing-title">
              {processing ? (
                <LoaderCircle
                  className="px-spin"
                  size={22}
                  aria-hidden="true"
                />
              ) : job.status === "SUCCEEDED" ? (
                <CheckCircle2 size={22} aria-hidden="true" />
              ) : (
                <Clock3 size={22} aria-hidden="true" />
              )}
              <div>
                <h3>{job.stage.replaceAll("_", " ")}</h3>
                <p className="muted">
                  {processing
                    ? "You can leave this page. We’ll keep working."
                    : "Latest processing activity"}
                </p>
              </div>
            </div>
            <StatusBadge status={job.status} />
          </div>
          {processing && (
            <>
              <div className="px-progress-label">
                <span>Reported progress</span>
                <strong>{Math.round(job.progress)}%</strong>
              </div>
              <progress
                value={job.progress}
                max={100}
                aria-label="Processing progress"
              />
              <div className="px-processing-stages">
                <span className="is-complete">
                  <Check size={14} aria-hidden="true" /> Uploaded
                </span>
                <span className="is-current">
                  <LoaderCircle size={14} aria-hidden="true" />{" "}
                  {job.stage.replaceAll("_", " ")}
                </span>
                <span>Next: review your results</span>
              </div>
            </>
          )}
          {job.started_at && (
            <p className="muted">
              {Math.max(
                0,
                Math.round(
                  ((job.finished_at
                    ? new Date(job.finished_at).getTime()
                    : observedAt) -
                    new Date(job.started_at).getTime()) /
                    1000,
                ),
              )}{" "}
              seconds elapsed
            </p>
          )}
          {job.error_message && (
            <p className="form-error" role="alert">
              {job.error_message}
            </p>
          )}
          <div className="actions">
            {processing && (
              <button
                type="button"
                className="button secondary"
                disabled={actionBusy || job.status === "CANCEL_REQUESTED"}
                onClick={() => setConfirm(job)}
              >
                {job.status === "CANCEL_REQUESTED"
                  ? "Cancellation requested"
                  : "Cancel processing"}
              </button>
            )}
            {["FAILED", "CANCELED"].includes(job.status) && (
              <button
                type="button"
                className="button secondary"
                disabled={actionBusy}
                onClick={() => retryJob(job)}
              >
                <RefreshCw size={15} aria-hidden="true" />
                {actionBusy ? "Retrying…" : "Retry processing"}
              </button>
            )}
          </div>
        </div>
      )}
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      <ConfirmDialog
        open={!!confirm}
        onClose={() => setConfirm(null)}
        onConfirm={confirmAction}
        title={
          confirm === "upload" ? "Cancel this upload?" : "Cancel processing?"
        }
        description={
          confirm === "upload"
            ? "Uploaded parts will be discarded. You can choose a video and start again."
            : "This job will stop at the next safe point. Your source video stays in the project, and you can retry later."
        }
        confirmLabel={
          confirm === "upload" ? "Cancel upload" : "Cancel processing"
        }
        busy={actionBusy}
      />
    </section>
  );
}
