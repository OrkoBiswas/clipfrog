"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import {
  ArrowRight,
  AudioLines,
  CircleAlert,
  FileVideo,
  Film,
  LoaderCircle,
  Palette,
  Scissors,
  Settings2,
  Sparkles,
  Upload,
} from "lucide-react";
import "./project-experience.css";

const sections = ["overview", "clips", "brand", "settings"] as const;
type Section = (typeof sections)[number];
const workflowAnchors = ["source", "analysis", "highlights"] as const;
const navigationEvent = "clipforge-project-navigation";

function subscribeToNavigation(callback: () => void) {
  window.addEventListener("hashchange", callback);
  window.addEventListener("popstate", callback);
  window.addEventListener(navigationEvent, callback);
  return () => {
    window.removeEventListener("hashchange", callback);
    window.removeEventListener("popstate", callback);
    window.removeEventListener(navigationEvent, callback);
  };
}

function currentDestination() {
  const hash = window.location.hash.slice(1);
  if ([...sections, ...workflowAnchors].some((section) => section === hash))
    return hash;
  const requested = new URLSearchParams(window.location.search).get("tab");
  return sections.find((section) => section === requested) ?? "overview";
}

function navigateTo(destination: string) {
  const unchanged = currentDestination() === destination;
  const url = new URL(window.location.href);
  url.hash = destination;
  if (url.href !== window.location.href)
    window.history.pushState(
      null,
      "",
      `${url.pathname}${url.search}${url.hash}`,
    );
  window.dispatchEvent(new Event(navigationEvent));
  if (unchanged) focusDestination(destination);
}

function focusDestination(destination: string) {
  if (!workflowAnchors.some((anchor) => anchor === destination)) return;
  const target = document.getElementById(destination);
  target?.focus({ preventScroll: true });
  target?.scrollIntoView({
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "instant"
      : "smooth",
    block: "start",
  });
}

function nextStep(status: string, hasSource: boolean, highlightCount: number) {
  switch (status) {
    case "UPLOADING":
      return {
        stage: 0,
        title: "Step 1: Upload your video",
        description:
          "Follow the upload below. Completed parts are saved if you need to pause.",
        action: "View upload",
        destination: "source",
        working: true,
      };
    case "VALIDATING":
      return {
        stage: 0,
        title: "Step 1: Checking your uploaded video",
        description:
          "We’re checking the source before analysis. Follow the reported progress below.",
        action: "View processing",
        destination: "source",
        working: true,
      };
    case "UPLOADED":
      return {
        stage: 1,
        title: "Step 2: Analyze your video",
        description:
          "Your source is ready. Analyze it to create a transcript and detect scenes, then find your highlights.",
        action: "Go to analysis",
        destination: "analysis",
      };
    case "ANALYZING":
      return {
        stage: 1,
        title: "Step 2: Analyzing your video",
        description:
          "Your video is being transcribed and analyzed. You can leave this page while we work.",
        action: "View processing",
        destination: "source",
        working: true,
      };
    case "FINDING_HIGHLIGHTS":
      return {
        stage: 2,
        title: "Step 3: Finding highlights",
        description:
          "Speech, audio, and visual signals help surface complete moments from your video.",
        action: "View processing",
        destination: "source",
        working: true,
      };
    case "READY_FOR_CLIPS":
      return {
        stage: 2,
        title: highlightCount ? "Step 3: Review your highlights" : "Step 3: Find highlights",
        description:
          highlightCount
            ? "Preview the suggested moments below. Mark unwanted moments as Poor clip, then render the rest into videos."
            : "Analysis is complete. Find highlights to get suggested moments you can preview before creating clips.",
        action: highlightCount ? "Review highlights" : "Go to highlights",
        destination: "highlights",
      };
    case "RENDERING":
      return {
        stage: 3,
        title: "Step 4: Creating your clip videos",
        description:
          "Framing, captions, and your style are coming together. Open your clips to follow their render status.",
        action: "View clips",
        destination: "clips",
        working: true,
      };
    case "EXPORTING":
      return {
        stage: 3,
        title: "Step 4: Preparing your download",
        description:
          "Your export is processing. Open your clips to check the archive and download completed videos.",
        action: "View exports",
        destination: "clips",
        working: true,
      };
    case "COMPLETED":
      return {
        stage: 3,
        title: "Step 4: Preview, edit and download",
        description:
          "Preview your clips, fine-tune captions and framing, then download the moments you’re ready to share.",
        action: "Open your clips",
        destination: "clips",
      };
    case "FAILED":
    case "CANCELED":
      return {
        stage: -1,
        title: status === "FAILED" ? "Processing failed — review and retry" : "Processing was canceled",
        description:
          "Review the latest processing details below. Your saved work stays here while you resolve the issue or retry.",
        action: "Review activity",
        destination: "source",
        attention: true,
      };
    case "CANCEL_REQUESTED":
      return {
        stage: -1,
        title: "Finishing the current step safely.",
        description:
          "Cancellation has been requested. Follow the activity below for the latest status.",
        action: "View processing",
        destination: "source",
        working: true,
      };
    case "QUEUED":
      return {
        stage: hasSource ? 1 : 0,
        title: "Your project is in the queue.",
        description:
          "Your next processing step will begin when a worker is available. You can follow its activity below.",
        action: "View processing",
        destination: "source",
        working: true,
      };
    case "DELETING":
      return {
        stage: 0,
        title: "Your project is being removed.",
        description:
          "Stored media cleanup is in progress. The processing activity below shows its latest status.",
        action: "View activity",
        destination: "source",
        working: true,
      };
    default:
      return {
        stage: 0,
        title: "Step 1: Upload your video",
        description:
          "Bring in your source video. This workspace takes you from the first upload to your final, shareable clips.",
        action: "Add your source",
        destination: "source",
      };
  }
}

export function ProjectWorkspace({
  status,
  hasSource,
  highlightCount = 0,
  overview,
  clips,
  brand,
  settings,
}: {
  status: string;
  hasSource: boolean;
  highlightCount?: number;
  overview: React.ReactNode;
  clips: React.ReactNode;
  brand: React.ReactNode;
  settings: React.ReactNode;
}) {
  const destination = useSyncExternalStore(
    subscribeToNavigation,
    currentDestination,
    () => "overview",
  );
  const active: Section = sections.some((section) => section === destination)
    ? (destination as Section)
    : "overview";
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const panelRefs = useRef<(HTMLDivElement | null)[]>([]);
  const tabs = [
    { id: "overview", label: "Overview", icon: FileVideo, content: overview },
    { id: "clips", label: "Clips", icon: Film, content: clips },
    { id: "brand", label: "Brand", icon: Palette, content: brand },
    { id: "settings", label: "Settings", icon: Settings2, content: settings },
  ];
  const next = nextStep(status, hasSource, highlightCount);
  const stages = [
    {
      title: "Upload",
      detail: "Add the original video",
      anchor: "source",
      icon: Upload,
    },
    {
      title: "Analyze",
      detail: "Read speech and scenes",
      anchor: "analysis",
      icon: AudioLines,
    },
    {
      title: "Review highlights",
      detail: "Preview suggested moments",
      anchor: "highlights",
      icon: Sparkles,
    },
    {
      title: "Edit & download",
      detail: "Get your finished videos",
      anchor: "clips",
      icon: Scissors,
    },
  ];

  useEffect(() => {
    // Keep upload/form state while preventing hidden previews from playing.
    panelRefs.current.forEach((panel) => {
      if (!panel?.hidden) return;
      panel
        .querySelectorAll<HTMLMediaElement>("video, audio")
        .forEach((media) => media.pause());
    });
  }, [active]);

  useEffect(() => {
    if (!workflowAnchors.some((anchor) => anchor === destination)) return;
    const frame = requestAnimationFrame(() => focusDestination(destination));
    return () => cancelAnimationFrame(frame);
  }, [destination]);

  return (
    <div className="px-project-studio">
      <section
        className={`px-studio-next ${next.attention ? "needs-attention" : ""}`}
        aria-label="Your next step"
      >
        <div className="px-studio-next-copy">
          <p className="eyebrow">
            {next.working ? (
              <LoaderCircle className="px-spin" size={13} aria-hidden="true" />
            ) : next.attention ? (
              <CircleAlert size={13} aria-hidden="true" />
            ) : (
              <Sparkles size={13} aria-hidden="true" />
            )}
            {next.working
              ? "IN PROGRESS"
              : next.attention
                ? "NEEDS YOUR ATTENTION"
                : "YOUR NEXT STEP"}
          </p>
          <h2>{next.title}</h2>
          <p>{next.description}</p>
        </div>
        <button
          type="button"
          className="button px-next-action"
          onClick={() => navigateTo(next.destination)}
        >
          {next.action}
          <ArrowRight size={17} aria-hidden="true" />
        </button>
      </section>

      <nav className="px-workflow" aria-label="Video workflow">
        <ol>
          {stages.map(({ title, detail, anchor, icon: Icon }, index) => (
            <li
              key={anchor}
              className={`${index < next.stage ? "is-earlier" : ""} ${index === next.stage ? "is-current" : ""}`}
            >
              <button
                type="button"
                onClick={() => navigateTo(anchor)}
                aria-current={index === next.stage ? "step" : undefined}
              >
                <span className="px-workflow-icon">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <span className="px-workflow-label">
                  <small>0{index + 1}</small>
                  <strong>{title}</strong>
                  <span>{detail}</span>
                </span>
                <ArrowRight
                  className="px-workflow-arrow"
                  size={15}
                  aria-hidden="true"
                />
              </button>
            </li>
          ))}
        </ol>
      </nav>

      <div
        className="project-section-tabs px-studio-tabs"
        role="tablist"
        aria-label="Project sections"
      >
        {tabs.map(({ id, label, icon: Icon }, index) => (
          <button
            key={id}
            type="button"
            role="tab"
            ref={(node) => {
              refs.current[index] = node;
            }}
            aria-selected={active === id}
            aria-controls={`project-panel-${id}`}
            id={`project-tab-${id}`}
            tabIndex={active === id ? 0 : -1}
            onClick={() => navigateTo(id)}
            onKeyDown={(event) => {
              const nextIndex =
                event.key === "ArrowRight"
                  ? (index + 1) % tabs.length
                  : event.key === "ArrowLeft"
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? tabs.length - 1
                        : null;
              if (nextIndex !== null) {
                event.preventDefault();
                navigateTo(tabs[nextIndex].id);
                refs.current[nextIndex]?.focus();
              }
            }}
          >
            <Icon size={16} aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>
      {tabs.map(({ id, content }, index) => (
        <div
          ref={(node) => {
            panelRefs.current[index] = node;
          }}
          className="px-studio-panel"
          role="tabpanel"
          key={id}
          id={`project-panel-${id}`}
          aria-labelledby={`project-tab-${id}`}
          tabIndex={0}
          hidden={active !== id}
        >
          {content}
        </div>
      ))}
    </div>
  );
}
