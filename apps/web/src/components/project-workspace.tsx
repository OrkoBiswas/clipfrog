"use client";
import { useRef, useState } from "react";
import { FileVideo, Film, Palette, Settings2 } from "lucide-react";
export function ProjectWorkspace({
  overview,
  clips,
  brand,
  settings,
}: {
  overview: React.ReactNode;
  clips: React.ReactNode;
  brand: React.ReactNode;
  settings: React.ReactNode;
}) {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const tabs = [
    { label: "Overview", icon: FileVideo, content: overview },
    { label: "Clips", icon: Film, content: clips },
    { label: "Brand", icon: Palette, content: brand },
    { label: "Settings", icon: Settings2, content: settings },
  ];
  return (
    <>
      <div
        className="project-section-tabs"
        role="tablist"
        aria-label="Project sections"
      >
        {tabs.map(({ label, icon: Icon }, index) => (
          <button
            key={label}
            type="button"
            role="tab"
            ref={(node) => {
              refs.current[index] = node;
            }}
            aria-selected={active === index}
            aria-controls={`project-panel-${index}`}
            id={`project-tab-${index}`}
            tabIndex={active === index ? 0 : -1}
            onClick={() => setActive(index)}
            onKeyDown={(event) => {
              const next =
                event.key === "ArrowRight"
                  ? (index + 1) % tabs.length
                  : event.key === "ArrowLeft"
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? tabs.length - 1
                        : null;
              if (next !== null) {
                event.preventDefault();
                setActive(next);
                refs.current[next]?.focus();
              }
            }}
          >
            <Icon size={16} aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`project-panel-${active}`}
        aria-labelledby={`project-tab-${active}`}
        tabIndex={0}
      >
        {tabs[active].content}
      </div>
    </>
  );
}
