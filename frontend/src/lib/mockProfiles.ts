/**
 * Demo fallback. When NEXT_PUBLIC_DEMO_MODE=true and the backend is unreachable,
 * the app serves these cached score responses so a live demo never dead-ends.
 * Generated from the real scoring pipeline (backend/app/services/pipeline.py).
 */
import rawData from "./_mock_data.json";
import type { MockProfile, ScoreResponse } from "./types";

interface Bundle {
  profile: MockProfile;
  score: ScoreResponse;
}

export const MOCK_BUNDLES = rawData as unknown as Bundle[];

export const MOCK_PROFILES: MockProfile[] = MOCK_BUNDLES.map((b) => b.profile);

export const MOCK_SCORES: Record<string, ScoreResponse> = Object.fromEntries(
  MOCK_BUNDLES.map((b) => [b.profile.id, b.score]),
);

export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

/** Find the closest cached score for a given feature set (used as a last resort). */
export function nearestMockScore(features: Record<string, number>): ScoreResponse {
  let best = MOCK_BUNDLES[0];
  let bestDist = Infinity;
  for (const b of MOCK_BUNDLES) {
    let d = 0;
    for (const k of Object.keys(features)) {
      const a = features[k];
      const c = b.profile.features[k];
      if (typeof a === "number" && typeof c === "number") {
        const scale = Math.abs(a) + Math.abs(c) + 1;
        d += ((a - c) / scale) ** 2;
      }
    }
    if (d < bestDist) {
      bestDist = d;
      best = b;
    }
  }
  return best.score;
}
