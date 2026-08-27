"use client";

import { Users } from "lucide-react";
import type { MockProfile } from "@/lib/types";

export function MockProfileLoader({
  profiles,
  onLoad,
}: {
  profiles: MockProfile[];
  onLoad: (p: MockProfile) => void;
}) {
  return (
    <div className="rounded-md border border-rule bg-surface-sunk p-4">
      <p className="flex items-center gap-2 text-label uppercase text-ink-muted">
        <Users size={13} strokeWidth={1.5} /> Quick demo — one click fills every step
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {profiles.map((p) => (
          <button
            key={p.id}
            onClick={() => onLoad(p)}
            className="rounded-sm border border-rule bg-surface p-3 text-start transition-tokens hover:bg-brand-tint"
          >
            <span className="text-body-strong text-ink">{p.display_name}</span>
            <span className="mt-0.5 block text-caption text-ink-muted">{p.headline}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
