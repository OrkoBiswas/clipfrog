"use client";

import { useEffect, useId, useRef } from "react";
import { AlertTriangle, Check, LoaderCircle, X } from "lucide-react";

const scrollLocks = new Set<HTMLDialogElement>();
let originalOverflow = "";

export function Modal({
  open,
  onClose,
  title,
  children,
  className = "",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
    if (!open) return;
    if (scrollLocks.size === 0) originalOverflow = document.body.style.overflow;
    scrollLocks.add(dialog);
    document.body.style.overflow = "hidden";
    return () => {
      scrollLocks.delete(dialog);
      if (dialog.open) dialog.close();
      if (scrollLocks.size === 0) document.body.style.overflow = originalOverflow;
    };
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`ui-dialog ${className}`}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          const bounds = e.currentTarget.getBoundingClientRect();
          if (
            e.clientX < bounds.left ||
            e.clientX > bounds.right ||
            e.clientY < bounds.top ||
            e.clientY > bounds.bottom
          )
            onClose();
        }
      }}
    >
      <div className="dialog-header">
        <h2 id={titleId}>{title}</h2>
        <button
          className="icon-button"
          type="button"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <X size={20} />
        </button>
      </div>
      {open && children}
    </dialog>
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  busy = false,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: React.ReactNode;
  confirmLabel?: string;
  busy?: boolean;
}) {
  return (
    <Modal
      open={open}
      onClose={() => {
        if (!busy) onClose();
      }}
      title={title}
    >
      <div className="confirm-description">
        <AlertTriangle size={24} aria-hidden="true" />
        <div>{description}</div>
      </div>
      <div className="actions">
        <button
          autoFocus
          type="button"
          className="button secondary"
          disabled={busy}
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          className="button danger"
          disabled={busy}
          onClick={onConfirm}
        >
          {busy && <LoaderCircle className="spin" size={16} />}
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <label className="toggle-row" htmlFor={id}>
      <span>
        <strong>{label}</strong>
        {description && <small>{description}</small>}
      </span>
      <input
        id={id}
        className="toggle-input"
        role="switch"
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
    </label>
  );
}

const statusNames: Record<string, string> = {
  READY_FOR_CLIPS: "Ready for clips",
  SUCCEEDED: "Completed",
  CANCEL_REQUESTED: "Canceling",
  FINDING_HIGHLIGHTS: "Finding highlights",
};
export function StatusBadge({ status }: { status: string }) {
  const done = ["COMPLETED", "SUCCEEDED", "READY", "READY_FOR_CLIPS"].includes(
    status,
  );
  const active = [
    "ANALYZING",
    "RENDERING",
    "UPLOADING",
    "VALIDATING",
    "QUEUED",
    "RUNNING",
    "FINDING_HIGHLIGHTS",
    "EXPORTING",
  ].includes(status);
  return (
    <span
      className={`badge status-badge ${done ? "status-success" : status === "FAILED" ? "status-error" : active ? "status-active" : ""}`}
    >
      {done ? (
        <Check size={12} aria-hidden="true" />
      ) : active ? (
        <LoaderCircle size={12} className="spin" aria-hidden="true" />
      ) : (
        <span className="status-dot" />
      )}
      {statusNames[status] ?? status.toLowerCase().replaceAll("_", " ")}
    </span>
  );
}
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`skeleton ${className}`} />;
}
