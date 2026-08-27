import { cn } from "@/lib/utils";

/** Shaped like the content it stands in for, not a generic grey bar. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-sm bg-surface-sunk", className)} aria-hidden />;
}

export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-rule border border-rule rounded-md">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4" style={{ height: 44 }}>
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="ms-auto h-4 w-20" />
        </div>
      ))}
    </div>
  );
}
