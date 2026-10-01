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
        <h2>Transcript & analysis</h2>
        {["UPLOADED", "READY_FOR_CLIPS", "COMPLETED"].includes(status) && (
          <button className="button" disabled={busy} onClick={analyze}>
            {busy
              ? "Queueing…"
              : transcript
                ? "Analyze again"
                : "Analyze video"}
          </button>
        )}
      </div>
      {transcript ? (
        <>
          {transcript.warnings.map((warning) => (
            <p className="notice" key={warning}>
              {warning}
            </p>
          ))}
          <p className="muted">
            Language: {transcript.language} · {transcript.scenes.length} scenes
          </p>
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
                　{segment.text}
              </p>
            ))}
          </div>
        </>
      ) : (
        <p className="muted">
          After upload validation, analyze your video to transcribe speech and
          detect scenes and faces.
        </p>
      )}
      <div className="form-error" role="alert">
        {error}
      </div>
    </section>
  );
}
