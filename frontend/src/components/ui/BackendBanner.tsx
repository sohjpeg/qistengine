"use client";

import { useEffect, useState } from "react";
import { PlugZap } from "lucide-react";
import { DEMO_MODE } from "@/lib/mockProfiles";

const AUTO_RETRY_SECONDS = 12;

/**
 * Inline recovery banner shown whenever the API is unreachable. On the hosted
 * demo the backend is a free instance that sleeps after ~15 min of inactivity
 * and takes ~40s to wake, so the banner counts down and reloads the page on its
 * own — a judge does not need to do anything.
 */
export function BackendBanner({ demoActive }: { demoActive?: boolean }) {
  const [left, setLeft] = useState(AUTO_RETRY_SECONDS);

  useEffect(() => {
    const t = setInterval(() => {
      setLeft((s) => {
        if (s <= 1) {
          window.location.reload();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="mb-5 rounded-md border border-band-high/40 bg-band-high-tint px-4 py-3">
      <p className="flex items-center gap-2 text-body-strong text-band-high">
        <PlugZap size={15} strokeWidth={1.5} aria-hidden />
        Waking the demo server
      </p>
      <p className="mt-1 text-caption text-ink-muted">
        The API runs on a free instance that sleeps after 15 minutes of inactivity;
        the first request takes about 40 seconds. Retrying automatically in {left}s —
        or{" "}
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="font-mono underline underline-offset-2 hover:text-ink"
        >
          reload now
        </button>
        .
        {DEMO_MODE && demoActive
          ? " Showing cached demo data in the meantime."
          : null}
      </p>
    </div>
  );
}
