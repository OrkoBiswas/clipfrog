"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import {
  Film,
  ArrowUpRight,
  FolderOpen,
  Grid2X2,
  List,
  Search,
  Trash2,
} from "lucide-react";
import { api, type Project } from "@/lib/api";
import { ConfirmDialog, StatusBadge } from "./ui/primitives";
import "./project-experience.css";
export function ProjectsList({
  projects,
  isAdmin = false,
}: {
  projects: Project[];
  isAdmin?: boolean;
}) {
  const router = useRouter();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState<"list" | "grid">("list");
  const visible = useMemo(
    () =>
      projects.filter((project) => {
        const matchesSearch =
          `${project.name} ${project.content_type} ${isAdmin ? (project.owner_email ?? "") : ""}`
            .toLowerCase()
            .includes(query.trim().toLowerCase());
        const processing = [
          "UPLOADING",
          "VALIDATING",
          "ANALYZING",
          "FINDING_HIGHLIGHTS",
          "RENDERING",
          "EXPORTING",
          "CANCEL_REQUESTED",
        ].includes(project.status);
        const matchesFilter =
          filter === "all" ||
          (filter === "active" && processing) ||
          (filter === "ready" &&
            ["READY_FOR_CLIPS", "COMPLETED"].includes(project.status)) ||
          (filter === "draft" &&
            ["CREATED", "DRAFT", "UPLOADED"].includes(project.status)) ||
          (filter === "failed" &&
            ["FAILED", "CANCELED"].includes(project.status));
        return matchesSearch && matchesFilter;
      }),
    [projects, query, filter, isAdmin],
  );
  async function deleteSelected() {
    const selected = projects.filter((project) => selectedIds.has(project.id));
    if (!selected.length) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api<{
        deleted: string[];
        queued_for_cleanup: string[];
      }>("/admin/projects/bulk-delete", {
        method: "POST",
        body: JSON.stringify({
          project_ids: selected.map((project) => project.id),
        }),
      });
      setSelectedIds(new Set());
      setConfirm(false);
      setMessage(
        `${result.deleted.length + result.queued_for_cleanup.length} projects accepted for deletion. Stored media cleanup may take a short time.`,
      );
      router.refresh();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not delete selected projects",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!projects.length)
    return (
      <div className="empty">
        <FolderOpen size={42} strokeWidth={1.4} aria-hidden="true" />
        <h3>Your next great clip starts here.</h3>
        <p>
          Upload a video and turn your best moments into social-ready content.
        </p>
        <Link className="button primary" href="/projects/new">
          Create your first project
        </Link>
      </div>
    );
  return (
    <div>
      <div className="px-project-toolbar">
        <label className="px-project-search">
          <Search size={17} aria-hidden="true" />
          <input
            aria-label="Search projects"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search your projects…"
          />
        </label>
        <select
          aria-label="Filter projects by status"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="active">Processing</option>
          <option value="ready">Ready to edit</option>
          <option value="draft">Drafts & uploads</option>
          <option value="failed">Needs attention</option>
        </select>
        <div className="px-view-buttons" role="group" aria-label="Project view">
          <button
            type="button"
            className={`button secondary ${view === "list" ? "is-selected" : ""}`}
            aria-label="List view"
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            <List size={17} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={`button secondary ${view === "grid" ? "is-selected" : ""}`}
            aria-label="Grid view"
            aria-pressed={view === "grid"}
            onClick={() => setView("grid")}
          >
            <Grid2X2 size={17} aria-hidden="true" />
          </button>
        </div>
      </div>
      <p className="px-project-count" aria-live="polite">
        {visible.length} {visible.length === 1 ? "project" : "projects"}
        {query || filter !== "all"
          ? ` of ${projects.length}`
          : " in your workspace"}
      </p>
      {isAdmin && (
        <div className="admin-project-tools">
          <label className="admin-project-selection">
            <input
              type="checkbox"
              checked={
                visible.length > 0 &&
                visible.every((project) => selectedIds.has(project.id))
              }
              onChange={(event) => {
                setSelectedIds((current) => {
                  const next = new Set(current);
                  visible.forEach((project) => {
                    if (event.target.checked) next.add(project.id);
                    else next.delete(project.id);
                  });
                  return next;
                });
              }}
            />
            Select all visible ({visible.length})
          </label>
          <button
            type="button"
            className="button danger"
            disabled={busy || selectedIds.size === 0}
            onClick={() => setConfirm(true)}
          >
            <Trash2 size={16} aria-hidden="true" />
            Delete selected ({selectedIds.size})
          </button>
        </div>
      )}
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div
        className={`px-project-list ${view === "grid" ? "px-project-grid" : ""}`}
      >
        {visible.map((project) => (
          <div className="px-project-card" key={project.id}>
            {isAdmin && (
              <input
                type="checkbox"
                checked={selectedIds.has(project.id)}
                aria-label={`Select ${project.name} owned by ${project.owner_email ?? "unknown user"}`}
                onChange={(event) =>
                  setSelectedIds((current) => {
                    const next = new Set(current);
                    if (event.target.checked) next.add(project.id);
                    else next.delete(project.id);
                    return next;
                  })
                }
              />
            )}
            <Link className="px-project-link" href={`/projects/${project.id}`}>
              <div className="px-project-thumbnail">
                <Film size={25} strokeWidth={1.4} aria-hidden="true" />
              </div>
              <div className="px-project-info">
                <strong>{project.name}</strong>
                <small>
                  {project.content_type} ·{" "}
                  {project.processing_config.ratios.join(", ")} ·{" "}
                  {new Date(project.created_at).toLocaleDateString("en", {
                    month: "short",
                    day: "numeric",
                    timeZone: "UTC",
                  })}
                </small>
                {isAdmin && project.owner_email && (
                  <small>{project.owner_email}</small>
                )}
              </div>
            </Link>
            <div className="px-project-tail">
              <StatusBadge status={project.status} />
              <ArrowUpRight size={17} aria-hidden="true" />
            </div>
          </div>
        ))}
      </div>
      {!visible.length && (
        <div className="empty">
          <Search size={30} aria-hidden="true" />
          <h3>No matching projects</h3>
          <p>Try a different name or clear your filters.</p>
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setQuery("");
              setFilter("all");
            }}
          >
            Clear filters
          </button>
        </div>
      )}
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={deleteSelected}
        title={`Delete ${selectedIds.size} selected projects?`}
        description={
          <>
            Their source videos, clips, transcripts, and analysis will be
            permanently removed. This cannot be undone.
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
          </>
        }
        confirmLabel="Permanently delete"
        busy={busy}
      />
    </div>
  );
}
