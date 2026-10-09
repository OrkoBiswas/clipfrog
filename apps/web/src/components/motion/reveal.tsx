"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
export const motion = { duration: 0.55, stagger: 0.065, ease: "power3.out" };
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
          const marked = ref.current!.querySelectorAll("[data-reveal]");
          const targets = marked.length ? marked : ref.current!.children;
          gsap.fromTo(
            targets,
            { opacity: 0.35, y: 18 },
            {
              opacity: 1,
              y: 0,
              duration: motion.duration,
              stagger: motion.stagger,
              ease: motion.ease,
              clearProps: "opacity,transform",
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
