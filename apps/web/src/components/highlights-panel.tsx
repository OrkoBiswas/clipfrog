"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Highlights = {
  engine?: { version: string; mode: string; personalized: boolean } | null;
  learning: {
    status: string;
    good_ratings: number;
    poor_ratings: number;
    message: string;
  };
  requested: number;
  candidates_evaluated: number;
  items: {
    id: string;
    title: string;
    text: string;
    start_ms: number;
    end_ms: number;
    score: number;
    breakdown: Record<string, number>;
    reason: string;
    rank: number;
    feedback: "good" | "poor" | null;
    can_rate: boolean;
    profile: string;
  }[];
};

export function HighlightsPanel({
  projectId,
  status,
  ratios,
}: {
  projectId: string;
  status: string;
  ratios: string[];
}) {
  const [result, setResult] = useState<Highlights | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [ratingBusy, setRatingBusy] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ id: string; url: string; start_ms: number; end_ms: number } | null>(null);
  const usable = result?.items.filter((item) => item.feedback !== "poor") ?? [];
  const canFind = ["READY_FOR_CLIPS", "COMPLETED"].includes(status);
  const finding = status === "FINDING_HIGHLIGHTS";
  const clipCount = usable.length * ratios.length;
  const router = useRouter();
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const value = await api<Highlights>(
          `/projects/${projectId}/highlights`,
        );
        if (active) setResult(value);
      } catch (e) {
        if (active)
          setError(
            e instanceof Error ? e.message : "Could not load highlights",
          );
      }
    };
    void refresh();
    const timer = setInterval(refresh, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [projectId]);
  async function generate() {
    setBusy(true);
    setError("");
    try {
      await api(`/projects/${projectId}/highlights`, { method: "POST" });
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not find highlights");
    } finally {
      setBusy(false);
    }
  }
  async function renderHighlights() {
    if (!usable.length) return;
    setBusy(true);
    setError("");
    try {
      await api(`/projects/${projectId}/clips/generate`, {
        method: "POST",
        body: JSON.stringify({
          candidate_ids: usable.map((item) => item.id),
          ratios,
        }),
      });
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not render highlights");
    } finally {
      setBusy(false);
    }
  }
  async function rate(item: Highlights["items"][number], rating: "good" | "poor") {
    setRatingBusy(item.id);
    setError("");
    const next = item.feedback === rating ? null : rating;
    try {
      const response = await api<{ rating: "good" | "poor" | null; learning: Highlights["learning"] }>(
        `/projects/${projectId}/highlights/${item.id}/feedback`,
        { method: "PUT", body: JSON.stringify({ rating: next }) },
      );
      setResult((current) => current && ({ ...current, learning: response.learning,
        items: current.items.map((value) => value.id === item.id ? { ...value, feedback: response.rating } : value),
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save your rating");
    } finally {
      setRatingBusy(null);
    }
  }
  async function previewMoment(id: string) {
    setError("");
    try {
      const value = await api<{ url: string; start_ms: number; end_ms: number }>(
        `/projects/${projectId}/highlights/${id}/preview`,
      );
      setPreview({ ...value, id });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not preview this moment");
    }
  }
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">Step 3 of 4</p>
          <h2>Find and review highlights</h2>
        </div>
          <button className={`button ${result?.items.length ? "secondary" : ""}`} disabled={busy || !canFind} onClick={generate}>
            {busy ? "Starting…" : finding ? "Finding highlights…" : "Find highlights"}
          </button>
      </div>
      <p className="muted">
        Find suggested moments, preview them, then create the clips you want to keep.
      </p>
      {!canFind && <p className="px-step-hint" role="status">{finding ? "We’re finding moments in your video. Results will appear here automatically." : status === "RENDERING" || status === "EXPORTING" ? "Your clips are processing. Follow their progress in step 4." : "Complete video analysis in step 2 to unlock highlight search."}</p>}
      {!!usable.length &&
        canFind && (
          <div className="px-step-confirmation">
          <p><strong>{usable.length} {usable.length === 1 ? "moment" : "moments"} ready</strong> · {ratios.length} {ratios.length === 1 ? "video format" : "video formats"}</p>
          <p className="muted">Render creates downloadable videos with your captions and framing. Afterward, open step 4 to edit or download.</p>
          <button className="button" disabled={busy} onClick={renderHighlights}>
            Render {clipCount} {clipCount === 1 ? "clip" : "clips"}
          </button>
          </div>
        )}
      {result && result.candidates_evaluated > 0 && (
        <p>
          {result.items.length} {result.items.length === 1 ? "highlight found" : "highlights found"}.{" "}
          {result.items.length < result.requested &&
            "Your video has fewer suitable moments than requested. You can adjust the clip length or search settings in Settings."}
        </p>
      )}
      {result?.learning && (
        <>
        {!!result.items.length && !usable.length && <p className="px-step-hint">All moments are marked Poor clip. Undo a rating to include a moment, or find highlights again for new suggestions.</p>}
        <details className="px-workflow-details">
          <summary>Optional: improve future suggestions with ratings</summary>
          <p>Good clip teaches the engine what you like. Poor clip skips a moment in this batch and future searches. Select the same rating again to undo it.</p>
          <strong>{!result.engine ? "Earlier results · find highlights to update" : result.engine.personalized ? "Local engine · learned preferences" : "Local engine · editorial scoring"}</strong>
          <p>{result.learning.message}</p>
          <p className="muted">{result.learning.good_ratings} good · {result.learning.poor_ratings} poor ratings.
            {" "}Ratings apply to future searches. Poor moments are excluded from this render batch.</p>
        </details>
        </>
      )}
      {result?.items.map((item) => (
        <article className="notice" key={item.id}>
          <div className="section-head">
            <h3>
              {item.rank}. {item.title}
            </h3>
            <span className="badge" title="Editorial quality score; not a prediction of views">{item.score.toFixed(1)} / 100</span>
          </div>
          <p className="muted">
            {(item.start_ms / 1000).toFixed(1)}–
            {(item.end_ms / 1000).toFixed(1)} seconds ·{" "}
            {((item.end_ms - item.start_ms) / 1000).toFixed(1)}s duration
          </p>
          {item.feedback === "poor" && <p className="px-step-hint">Skipped — this moment won’t be rendered. Select Poor clip again to include it.</p>}
          <div className="button-row" style={{ display: "flex", flexWrap: "wrap", gap: 8 }} role="group" aria-label={`Review highlight ${item.rank}`}>
            <button className="button secondary" onClick={() => void previewMoment(item.id)}>Preview moment</button>
            <button className="button secondary" aria-pressed={item.feedback === "good"}
              disabled={!item.can_rate || ratingBusy !== null} onClick={() => void rate(item, "good")}>Good clip</button>
            <button className="button secondary" aria-pressed={item.feedback === "poor"}
              disabled={!item.can_rate || ratingBusy !== null} onClick={() => void rate(item, "poor")}>Poor clip</button>
          </div>
          {!item.can_rate && <p className="muted">Find highlights again to use the new scoring and learning.</p>}
          {preview?.id === item.id && <video key={item.id} controls preload="metadata" src={preview.url}
            aria-label={`Highlight ${item.rank} preview`} style={{ width: "100%", maxHeight: 360, marginTop: 12 }}
            onLoadedMetadata={(event) => { event.currentTarget.currentTime = preview.start_ms / 1000; }}
            onPlay={(event) => {
              const video = event.currentTarget;
              if (video.currentTime < preview.start_ms / 1000 || video.currentTime >= preview.end_ms / 1000)
                video.currentTime = preview.start_ms / 1000;
            }}
            onTimeUpdate={(event) => {
              const video = event.currentTarget;
              if (video.currentTime >= preview.end_ms / 1000 && !video.paused) video.pause();
            }} />}
          <details>
            <summary>Read transcript and see why this moment was chosen</summary>
            <p>{item.text}</p>
            <p>{item.reason}</p>
            <dl className="meta-grid">
              {Object.entries(item.breakdown).map(([name, value]) => (
                <div key={name}>
                  <dt>{name.replaceAll("_", " ")}</dt>
                  <dd>{value.toFixed(1)}</dd>
                </div>
              ))}
            </dl>
          </details>
        </article>
      ))}
      {!result?.items.length && (
        <p className="muted">
          {canFind ? "Select Find highlights to search your video. You’ll be able to preview each moment before rendering." : "Your suggested moments will appear here after highlight search."}
        </p>
      )}
      <div className="form-error" role="alert">
        {error}
      </div>
    </section>
  );
}
