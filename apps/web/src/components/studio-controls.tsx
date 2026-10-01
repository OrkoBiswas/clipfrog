"use client";

import { Check } from "lucide-react";
import { useState } from "react";
import { positions } from "@/lib/positions";
import "./studio.css";

export function PositionGrid({
  value,
  onChange,
  label = "Logo placement",
}: {
  value: string;
  onChange: (position: string) => void;
  label?: string;
}) {
  return (
    <div className="studio-placement" role="group" aria-label={label}>
      {positions.map((position) => (
        <button
          type="button"
          key={position}
          aria-label={`${label}: ${position.replaceAll("-", " ")}`}
          title={position.replaceAll("-", " ")}
          aria-pressed={value === position}
          onClick={() => onChange(position)}
        >
          {value === position ? (
            <Check size={16} aria-hidden="true" />
          ) : (
            <span />
          )}
        </button>
      ))}
    </div>
  );
}

export function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <div className="field">
      <span>{label}</span>
      <div className="studio-color-input">
        <input
          type="color"
          aria-label={label}
          value={/^#[0-9a-fA-F]{6}$/.test(value) ? value : "#ffffff"}
          onChange={(event) => onChange(event.target.value)}
        />
        <input
          aria-label={`${label} hex`}
          value={draft ?? value}
          maxLength={7}
          pattern="#[0-9a-fA-F]{6}"
          aria-invalid={draft !== null && !/^#[0-9a-fA-F]{6}$/.test(draft)}
          onFocus={() => setDraft(value)}
          onBlur={() => setDraft(null)}
          onChange={(event) => { const next = event.target.value; setDraft(next); if (/^#[0-9a-fA-F]{6}$/.test(next)) onChange(next); }}
        />
      </div>
    </div>
  );
}

export function timecode(milliseconds: number) {
  const total = Math.max(0, Math.floor(milliseconds / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}
