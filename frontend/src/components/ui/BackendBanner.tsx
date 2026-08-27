"use client";

import { PlugZap } from "lucide-react";
import { DEMO_MODE } from "@/lib/mockProfiles";

/** Inline recovery banner shown whenever the API is unreachable. */
export function BackendBanner({ demoActive }: { demoActive?: boolean }) {
  return (
    <div className="mb-5 rounded-md border border-band-high/40 bg-band-high-tint px-4 py-3">
      <p className="flex items-center gap-2 text-body-strong text-band-high">
        <PlugZap size={15} strokeWidth={1.5} aria-hidden />
        Backend not running
      </p>
      <p className="mt-1 text-caption text-ink-muted">
        Start it with{" "}
        <code className="rounded-sm bg-surface px-1 font-mono">uvicorn app.main:app --reload</code>{" "}
        from the <code className="font-mono">backend/</code> directory, then retry.
        {DEMO_MODE && demoActive
          ? " Showing cached demo data in the meantime."
          : null}
      </p>
    </div>
  );
}
