"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
export const motion = { duration: 0.3, stagger: 0.035, ease: "power2.out" };
export function MotionReveal({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const path = usePathname();
  useEffect(() => {
    let disposed = false;
    let cleanup: (() => void) | undefined;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    void import("gsap").then(({ gsap }) => {
      if (disposed || !ref.current) return;
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        const ctx = gsap.context(() => {
          gsap.fromTo(
            ref.current,
            { opacity: 0.5, y: 8 },
            {
              opacity: 1,
              y: 0,
              duration: motion.duration,
              ease: motion.ease,
              clearProps: "all",
            },
          );
        }, ref);
        return () => ctx.revert();
      });
      cleanup = () => media.revert();
    });
    return () => {
      disposed = true;
      cleanup?.();
    };
  }, [path]);
  return (
    <div ref={ref} className="page-transition">
      {children}
    </div>
  );
}
