"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, API_URL } from "@/lib/api";
type Transcript = {
  language: string;
  text: string;
  segments: { start: number; end: number; text: string }[];
  warnings: string[];
  scenes: { start_ms: number; end_ms: number }[];
};
export function AnalysisPanel({
  projectId,
  status,
}: {
  projectId: string;
  status: string;
}) {
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const canAnalyze = ["UPLOADED", "READY_FOR_CLIPS", "COMPLETED"].includes(status);
  const analyzing = status === "ANALYZING";
  useEffect(() => {
    let active = true;
    const refresh = () =>
      api<Transcript | null>(`/projects/${projectId}/transcript`)
        .then((value) => {
          if (active) setTranscript(value);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    void refresh();
    const timer = setInterval(refresh, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [projectId]);
  async function analyze() {
    setBusy(true);
    setError("");
    try {
      await api(`/projects/${projectId}/analyze`, { method: "POST" });
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start analysis");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">Step 2 of 4</p>
          <h2>Analyze your video</h2>
        </div>
        <button
          className={`button ${transcript ? "secondary" : ""}`}
          disabled={busy || !canAnalyze}
          onClick={analyze}
        >
          {busy
            ? "Starting analysis…"
            : analyzing
              ? "Analyzing…"
              : transcript
                ? "Analyze again"
                : "Analyze video"}
        </button>
      </div>
      <p className="muted">Analysis reads the speech and scenes so we can find complete moments for your clips.</p>
      {transcript ? (
        <>
          {transcript.warnings.map((warning) => (
            <p className="notice" key={warning}>
              {warning}
            </p>
          ))}
          <p className="px-step-confirmation">Analysis complete. Next, <a href="#highlights">find and review highlights</a>.</p>
          <details className="px-workflow-details">
            <summary>Read or download the transcript</summary>
            <p className="muted">Detected language: {transcript.language} · {transcript.scenes.length} scenes</p>
            <div className="checks">
              {["txt", "srt", "vtt", "json"].map((format) => (
                <a
                  key={format}
                  className="text-button"
                  href={`${API_URL}/api/v1/projects/${projectId}/transcript/export?format=${format}`}
                >
                  Download {format.toUpperCase()}
                </a>
              ))}
            </div>
            <div style={{ maxHeight: 360, overflow: "auto", marginTop: 20 }}>
              {transcript.segments.map((segment) => (
                <p key={segment.start}>
                  <small>
                    {Math.floor(segment.start / 60)}:
                    {String(Math.floor(segment.start % 60)).padStart(2, "0")}
                  </small>
                  {" "}{segment.text}
                </p>
              ))}
            </div>
          </details>
        </>
      ) : (
        <p className="muted">
          {analyzing
            ? "Analysis is in progress. You can leave this page and return when it is complete."
            : canAnalyze
              ? "Your video is ready. Select Analyze video to start."
              : "First, upload your video in step 1 and wait for the video check to finish."}
        </p>
      )}
      <div className="form-error" role="alert">
        {error}
      </div>
    </section>
  );
}
