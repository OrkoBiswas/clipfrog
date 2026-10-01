"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Settings2, Trash2, X } from "lucide-react";
import { api, type Project } from "@/lib/api";
import { ProjectForm } from "./project-form";
import { ConfirmDialog } from "./ui/primitives";
import { useToast } from "./ui/toast";
import "./project-experience.css";
export function ProjectActions({ project }: { project: Project }) {
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const { toast } = useToast();
  async function remove() {
    setBusy(true);
    setError("");
    try {
      await api(`/projects/${project.id}`, { method: "DELETE" });
      toast("Project deleted", "Stored media cleanup may take a short time.");
      router.push("/projects");
      router.refresh();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not delete this project. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="px-project-actions">
        <div className="actions">
          <button
            type="button"
            className="button secondary"
            onClick={() => setEditing(!editing)}
            aria-expanded={editing}
            aria-controls="project-settings-panel"
          >
            {editing ? (
              <X size={16} aria-hidden="true" />
            ) : (
              <Settings2 size={16} aria-hidden="true" />
            )}
            {editing ? "Close settings" : "Edit project settings"}
          </button>
        </div>
        <button
          type="button"
          className="text-button"
          onClick={() => setConfirm(true)}
        >
          <Trash2 size={15} aria-hidden="true" /> Delete project
        </button>
      </div>
      {editing && (
        <div className="px-editor-settings" id="project-settings-panel">
          <ProjectForm project={project} onSaved={() => setEditing(false)} />
        </div>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={remove}
        title="Delete this project?"
        description={
          <>
            <strong>{project.name}</strong> and its source video, clips,
            transcript, and analysis will be permanently removed. This cannot be
            undone.
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
          </>
        }
        confirmLabel="Permanently delete"
        busy={busy}
      />
    </>
  );
}
