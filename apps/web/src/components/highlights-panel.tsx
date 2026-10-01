"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Highlights = {
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
    if (!result?.items.length) return;
    setBusy(true);
    setError("");
    try {
      await api(`/projects/${projectId}/clips/generate`, {
        method: "POST",
        body: JSON.stringify({
          candidate_ids: result.items.map((item) => item.id),
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
  return (
    <section className="panel">
      <div className="section-head">
        <h2>Important moments</h2>
        {["READY_FOR_CLIPS", "COMPLETED"].includes(status) && (
          <button className="button" disabled={busy} onClick={generate}>
            {busy ? "Queueing…" : "Find highlights"}
          </button>
        )}
      </div>
      <p className="muted">
        Complete ideas ranked using speech, audio and visual signals. Scores
        help you compare moments; they do not predict views.
      </p>
      {!!result?.items.length &&
        ["READY_FOR_CLIPS", "COMPLETED"].includes(status) && (
          <button className="button" disabled={busy} onClick={renderHighlights}>
            Render {result.items.length * ratios.length} clips
          </button>
        )}
      {result && result.candidates_evaluated > 0 && (
        <p>
          {result.items.length} distinct moments selected from{" "}
          {result.candidates_evaluated} candidate windows.{" "}
          {result.items.length < result.requested &&
            "Fewer moments meet your duration, score and diversity settings than requested."}
        </p>
      )}
      {result?.items.map((item) => (
        <article className="notice" key={item.id}>
          <div className="section-head">
            <h3>
              {item.rank}. {item.title}
            </h3>
            <span className="badge">{item.score.toFixed(1)} / 100</span>
          </div>
          <p className="muted">
            {(item.start_ms / 1000).toFixed(1)}–
            {(item.end_ms / 1000).toFixed(1)} seconds ·{" "}
            {((item.end_ms - item.start_ms) / 1000).toFixed(1)}s duration
          </p>
          <p>{item.text}</p>
          <details>
            <summary>Why this moment?</summary>
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
          Analyze the source, then find highlights. If no complete ideas fit,
          widen the duration range or lower the minimum score.
        </p>
      )}
      <div className="form-error" role="alert">
        {error}
      </div>
    </section>
  );
}
