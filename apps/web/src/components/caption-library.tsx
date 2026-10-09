"use client";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { CaptionStyle } from "@/lib/editor-types";
import {
  CAPTION_TEMPLATES,
  type CaptionTemplate,
} from "@/lib/caption-templates";

const LibraryContext = createContext<{
  templates: CaptionTemplate[];
  ready: boolean;
  save: (name: string, value: CaptionStyle) => void;
  remove: (id: string) => void;
}>({
  templates: CAPTION_TEMPLATES,
  ready: false,
  save: () => {},
  remove: () => {},
});

export function CaptionLibraryProvider({
  userId,
  children,
}: {
  userId: string;
  children: ReactNode;
}) {
  const [custom, setCustom] = useState<CaptionTemplate[]>([]);
  const [ready, setReady] = useState(false);
  const key = `clipforge-caption-library-v1-${userId}`;
  useEffect(() => {
    function read() {
      try {
        const data: unknown = JSON.parse(localStorage.getItem(key) ?? "[]");
        setCustom(
          Array.isArray(data)
            ? data
                .filter(
                  (item): item is CaptionTemplate =>
                    !!item &&
                    typeof item.id === "string" &&
                    item.id.startsWith("custom-") &&
                    typeof item.name === "string" &&
                    !!item.config &&
                    typeof item.config === "object",
                )
                .slice(0, 50)
            : [],
        );
      } catch {
        setCustom([]);
      }
      setReady(true);
    }
    read();
    window.addEventListener("storage", read);
    return () => window.removeEventListener("storage", read);
  }, [key]);
  function persist(next: CaptionTemplate[]) {
    localStorage.setItem(key, JSON.stringify(next));
    setCustom(next);
  }
  function save(name: string, value: CaptionStyle) {
    if (!ready) throw new Error("Your preset library is still loading.");
    if (!name.trim()) throw new Error("Give your preset a name.");
    if (custom.length >= 50)
      throw new Error(
        "Your library holds 50 presets. Remove one before saving another.",
      );
    const config = {
      ...value,
      style: name.trim(),
      cues: undefined,
      enabled: true,
    };
    persist([
      ...custom,
      {
        id: `custom-${crypto.randomUUID()}`,
        name: name.trim(),
        category: "My presets",
        description: "Your saved caption style.",
        sample: "Make it unmistakably yours",
        accent: value.highlight_color ?? "#BBE9D4",
        config,
      },
    ]);
  }
  return (
    <LibraryContext.Provider
      value={{
        templates: [...CAPTION_TEMPLATES, ...custom],
        ready,
        save,
        remove: (id) => persist(custom.filter((item) => item.id !== id)),
      }}
    >
      {children}
    </LibraryContext.Provider>
  );
}
export const useCaptionLibrary = () => useContext(LibraryContext);
