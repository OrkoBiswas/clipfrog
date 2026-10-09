"use client";

import {
  createContext,
  useContext,
  useEffect,
  useSyncExternalStore,
} from "react";
import { Monitor, Moon, Sun } from "lucide-react";

type Theme = "dark" | "light" | "system";
const ThemeContext = createContext<{
  theme: Theme;
  setTheme: (theme: Theme) => void;
}>({ theme: "dark", setTheme: () => {} });
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("clipforge-theme", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("clipforge-theme", callback);
  };
}
let sessionTheme: Theme | undefined;
function snapshot(): Theme {
  try {
    const value = sessionTheme ?? localStorage.getItem("clipforge-theme");
    return value === "light" || value === "system" ? value : "dark";
  } catch {
    return sessionTheme ?? "dark";
  }
}
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useSyncExternalStore(
    subscribe,
    snapshot,
    () => "dark" as Theme,
  );
  useEffect(() => {
    const query = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.dataset.theme =
        theme === "system" ? (query.matches ? "dark" : "light") : theme;
    };
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, [theme]);
  function setTheme(value: Theme) {
    try {
      localStorage.setItem("clipforge-theme", value);
      sessionTheme = undefined;
    } catch {
      sessionTheme = value;
    }
    window.dispatchEvent(new Event("clipforge-theme"));
  }
  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function ThemeControl() {
  const { theme, setTheme } = useContext(ThemeContext);
  return (
    <div
      className="segmented theme-control"
      role="group"
      aria-label="Color theme"
    >
      {(
        [
          ["dark", Moon],
          ["light", Sun],
          ["system", Monitor],
        ] as const
      ).map(([value, Icon]) => (
        <button
          type="button"
          key={value}
          aria-pressed={theme === value}
          onClick={() => setTheme(value)}
        >
          <Icon size={16} aria-hidden="true" />
          {value[0].toUpperCase() + value.slice(1)}
        </button>
      ))}
    </div>
  );
}
