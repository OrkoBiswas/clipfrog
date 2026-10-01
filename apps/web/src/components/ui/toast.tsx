"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { CircleCheck, CircleAlert, Info, X } from "lucide-react";
type Tone = "success" | "error" | "info";
type Toast = { id: number; title: string; description?: string; tone: Tone };
const ToastContext = createContext<{
  toast: (title: string, description?: string, tone?: Tone) => void;
}>({ toast: () => {} });
export const useToast = () => useContext(ToastContext);
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const sequence = useRef(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const toast = useCallback(
    (title: string, description?: string, tone: Tone = "success") => {
      const id = ++sequence.current;
      setItems((current) => [
        ...current.slice(-3),
        { id, title, description, tone },
      ]);
      timers.current.push(
        setTimeout(
          () => setItems((current) => current.filter((item) => item.id !== id)),
          6500,
        ),
      );
    },
    [],
  );
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div
        className="toast-region"
        aria-label="Notifications"
        aria-live="polite"
        aria-atomic="false"
      >
        {items.map((item) => {
          const Icon =
            item.tone === "success"
              ? CircleCheck
              : item.tone === "error"
                ? CircleAlert
                : Info;
          return (
            <div
              className={`toast toast-${item.tone}`}
              key={item.id}
              role={item.tone === "error" ? "alert" : "status"}
            >
              <Icon size={20} aria-hidden="true" />
              <div>
                <strong>{item.title}</strong>
                {item.description && <p>{item.description}</p>}
              </div>
              <button
                className="icon-button"
                aria-label="Dismiss notification"
                onClick={() =>
                  setItems((current) =>
                    current.filter((toast) => toast.id !== item.id),
                  )
                }
              >
                <X size={16} />
              </button>
              <span className="toast-timer" />
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
