import { Skeleton } from "@/components/ui/primitives";
export default function Loading() {
  return (
    <div role="status" aria-label="Loading workspace">
      <span className="sr-only">Loading your workspace</span>
      <Skeleton className="skeleton-heading" />
      <Skeleton className="skeleton-copy" />
      <div className="stats">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton className="skeleton-card" key={i} />
        ))}
      </div>
      <Skeleton className="skeleton-content" />
    </div>
  );
}
