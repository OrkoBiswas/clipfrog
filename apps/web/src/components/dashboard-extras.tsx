"use client";
import Link from "next/link";
import { Check, Film, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Project } from "@/lib/api";
import type { Clip } from "./clips-panel";
export function DashboardOnboarding({
  userId,
  hasProject,
  hasSource,
  projectId,
}: {
  userId: string;
  hasProject: boolean;
  hasSource: boolean;
  projectId?: string;
}) {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      try {
        setHidden(
          localStorage.getItem(`clipforge-onboarded-${userId}`) === "yes",
        );
      } catch {}
    });
    return () => cancelAnimationFrame(frame);
  }, [userId]);
  if (hidden) return null;
  return (
    <section className="onboarding">
      <div className="section-head">
        <h3>Three steps to your first clip</h3>
        <button
          className="icon-button"
          aria-label="Dismiss getting started"
          onClick={() => {
            setHidden(true);
            try {
              localStorage.setItem(`clipforge-onboarded-${userId}`, "yes");
            } catch {}
          }}
        >
          <X size={15} />
        </button>
      </div>
      <ol>
        {[
          {
            label: "Create a project",
            done: hasProject,
            href: "/projects/new",
          },
          {
            label: "Add your video",
            done: hasSource,
            href: projectId ? `/projects/${projectId}#source` : "/projects/new",
          },
          {
            label: "Create your first clip",
            done: false,
            href: projectId ? `/projects/${projectId}` : "/projects/new",
          },
        ].map(({ label, done, href }, index) => (
          <li key={label} className={done ? "complete" : ""}>
            <span>
              {done ? <Check size={12} aria-label="Completed" /> : index + 1}
            </span>
            <Link href={href}>{label}</Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
export function RecentClips({
  items,
}: {
  items: { clip: Clip; project: Project }[];
}) {
  if (!items.length)
    return (
      <div className="recent-clips-empty">
        <Film size={26} aria-hidden="true" />
        <div>
          <strong>Your best moments are ahead.</strong>
          <p>Generate clips from a project and pick up your edits here.</p>
        </div>
      </div>
    );
  return (
    <div className="recent-clips">
      {items.map((item) => (
        <RecentClip key={item.clip.id} {...item} />
      ))}
    </div>
  );
}
function RecentClip({ clip, project }: { clip: Clip; project: Project }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let active = true;
    if (clip.output_asset_id)
      void api<{ url: string }>(
        `/projects/${project.id}/clips/${clip.id}/media`,
      )
        .then((result) => {
          if (active) setUrl(result.url);
        })
        .catch(() => {});
    return () => {
      active = false;
    };
  }, [clip.id, clip.output_asset_id, project.id]);
  return (
    <Link className="recent-clip" href={`/projects/${project.id}#clips`}>
      <div className="recent-clip-visual">
        {url ? (
          <video
            src={`${url}#t=0.1`}
            muted
            playsInline
            preload="metadata"
            aria-hidden="true"
          />
        ) : (
          <Film size={25} aria-hidden="true" />
        )}
        <span className="badge">
          {Math.round((clip.end_ms - clip.start_ms) / 1000)}s ·{" "}
          {clip.aspect_ratio}
        </span>
      </div>
      <div className="recent-clip-copy">
        <strong>{clip.title}</strong>
        <small>{project.name}</small>
      </div>
    </Link>
  );
}
