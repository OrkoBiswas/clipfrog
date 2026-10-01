"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Database,
  FolderOpen,
  LoaderCircle,
  RefreshCw,
  Search,
  Users,
} from "lucide-react";
import { api } from "@/lib/api";
import "./account-pages.css";

export type OperationsData = {
  users: number;
  projects: number;
  storage_bytes: number;
  retention_days: number;
  job_counts: Record<string, number>;
  jobs: {
    id: string;
    project_id: string;
    type: string;
    status: string;
    stage: string;
    progress: number;
    error: string | null;
    created_at: string;
    heartbeat_at: string | null;
  }[];
};

function readable(value: string) {
  return value.replaceAll("_", " ");
}
function dateTime(value: string) {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

export function OperationsPanel({
  initialData,
}: {
  initialData: OperationsData;
}) {
  const [data, setData] = useState(initialData);
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState(false);
  const jobs = useMemo(
    () =>
      data.jobs.filter(
        (job) =>
          (status === "all" || job.status === status) &&
          `${job.id} ${job.project_id} ${job.type} ${job.stage}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [data.jobs, query, status],
  );
  const statuses = Array.from(
    new Set([
      ...Object.keys(data.job_counts),
      ...data.jobs.map((job) => job.status),
    ]),
  );
  async function refresh() {
    if (busy) return;
    setBusy(true);
    setError("");
    setUpdated(false);
    try {
      setData(await api<OperationsData>("/operations"));
      setUpdated(true);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to refresh operations.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="account-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">ADMINISTRATOR WORKSPACE</p>
          <h1>Operations</h1>
          <p>A clear picture of processing activity across your workspace.</p>
        </div>
        <button className="button secondary" onClick={refresh} disabled={busy}>
          {busy ? (
            <LoaderCircle
              size={16}
              className="account-spin"
              aria-hidden="true"
            />
          ) : (
            <RefreshCw size={16} aria-hidden="true" />
          )}
          {busy ? "Refreshing…" : "Refresh status"}
        </button>
      </header>
      {error && (
        <div className="account-feedback account-feedback-error" role="alert">
          {error}
        </div>
      )}
      {updated && (
        <p className="account-refresh-feedback" role="status">
          <CheckCircle2 size={15} aria-hidden="true" /> Status is up to date.
        </p>
      )}
      <section
        className="account-operations-metrics"
        aria-label="Workspace totals"
      >
        {[
          {
            label: "Total users",
            value: data.users.toLocaleString(),
            icon: Users,
          },
          {
            label: "Projects",
            value: data.projects.toLocaleString(),
            icon: FolderOpen,
          },
          {
            label: "Media stored",
            value: `${(data.storage_bytes / 1024 ** 3).toFixed(2)} GB`,
            icon: Database,
          },
          {
            label: "Media retention",
            value: data.retention_days
              ? `${data.retention_days} days`
              : "No auto-delete",
            icon: Clock3,
          },
        ].map(({ label, value, icon: Icon }) => (
          <article key={label}>
            <div>
              <span>{label}</span>
              <Icon size={18} aria-hidden="true" />
            </div>
            <strong>{value}</strong>
            {label === "Media retention" && (
              <small>
                {data.retention_days
                  ? "Since last project activity"
                  : "Projects are kept until removed"}
              </small>
            )}
          </article>
        ))}
      </section>
      <section className="account-operations-jobs">
        <div className="account-jobs-heading">
          <div>
            <h2>
              Processing activity
              <span className="account-label">
                {data.jobs.length} latest jobs
              </span>
            </h2>
            <p>Open a project to inspect, retry, or cancel its jobs.</p>
          </div>
          <div className="account-job-counts">
            {Object.entries(data.job_counts).map(([state, count]) => (
              <span
                className={`account-label account-state-${state}`}
                key={state}
              >
                {readable(state)}
                <strong>{count}</strong>
              </span>
            ))}
          </div>
        </div>
        <div className="account-jobs-toolbar">
          <label className="account-search">
            <Search size={17} aria-hidden="true" />
            <input
              aria-label="Search jobs by type, stage, or project ID"
              placeholder="Search jobs, stages, or project IDs…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label className="account-status-filter">
            <span>Status</span>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="all">All statuses</option>
              {statuses.map((state) => (
                <option value={state} key={state}>
                  {readable(state)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {jobs.length ? (
          <div className="account-jobs-list">
            {jobs.map((job) => (
              <article key={job.id} className="account-job">
                <div className="account-job-main">
                  <span className="account-icon">
                    <Activity size={19} aria-hidden="true" />
                  </span>
                  <div>
                    <Link href={`/projects/${job.project_id}`}>
                      {readable(job.type)}
                      <ArrowUpRight size={14} aria-hidden="true" />
                    </Link>
                    <span className="account-job-id" title={job.project_id}>
                      Project {job.project_id.slice(0, 8)}
                    </span>
                  </div>
                </div>
                <div className="account-job-stage">
                  <div>
                    <span>{readable(job.stage || "Waiting to start")}</span>
                    <strong>{Math.round(job.progress)}%</strong>
                  </div>
                  <progress
                    aria-label={`${readable(job.type)} progress`}
                    max={100}
                    value={job.progress}
                  />
                </div>
                <span className={`account-label account-state-${job.status}`}>
                  {readable(job.status)}
                </span>
                <div className="account-job-time">
                  <span>{dateTime(job.created_at)} UTC</span>
                  <small>
                    {job.heartbeat_at
                      ? `Heartbeat ${dateTime(job.heartbeat_at)} UTC`
                      : "No heartbeat recorded"}
                  </small>
                </div>
                {job.error && (
                  <div className="account-job-error">
                    <strong>Job error</strong>
                    <p>{job.error}</p>
                  </div>
                )}
              </article>
            ))}
          </div>
        ) : (
          <div className="account-jobs-empty">
            <Activity size={32} aria-hidden="true" />
            <h3>
              {data.jobs.length ? "No matching jobs" : "Nothing in the queue"}
            </h3>
            <p>
              {data.jobs.length
                ? "Try a different search or status to find a job."
                : "Processing jobs will appear here as videos move through the workspace."}
            </p>
            {(query || status !== "all") && (
              <button
                className="button secondary"
                onClick={() => {
                  setQuery("");
                  setStatus("all");
                }}
              >
                Clear filters
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
